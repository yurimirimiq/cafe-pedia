from django.test import TestCase
from unittest.mock import patch as _patch

# 테스트에서는 실제 카카오 이미지 검색을 부르지 않는다 (썸네일 테스트만 따로 바꿔 끼움)
_patch('api.kakao.image_search', return_value=None).start()
from django.utils import timezone


class HelloApiTest(TestCase):
    def test_hello(self):
        res = self.client.get('/api/hello/')
        self.assertEqual(res.status_code, 200)
        self.assertIn('message', res.json())

    def test_cors_allows_frontend(self):
        res = self.client.get('/api/hello/', HTTP_ORIGIN='http://localhost:5173')
        self.assertEqual(res['Access-Control-Allow-Origin'], 'http://localhost:5173')


import json
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from .models import Place, Review, User, Wishlist


class ModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='yurim', password='test-pass-1234', nickname='유림')
        self.cafe = Place.objects.create(
            kakao_id='12345', category=Place.Category.CAFE, name='카페 온기', address='서울 마포구 망원동',
            latitude=Decimal('37.5560000'), longitude=Decimal('126.9010000'),
        )

    def review(self, rating):
        return Review(user=self.user, place=self.cafe, rating=Decimal(rating))

    def test_rating_accepts_half_steps(self):
        for r in ['0.5', '3.5', '5.0']:
            self.review(r).full_clean()

    def test_rating_rejects_bad_values(self):
        for r in ['0.0', '3.7', '5.5']:
            with self.assertRaises(ValidationError, msg=r):
                self.review(r).full_clean()

    def test_db_blocks_out_of_range_rating(self):
        with self.assertRaises(IntegrityError):
            self.review('6.0').save()

    def test_one_review_per_user_and_cafe(self):
        self.review('4.0').save()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.review('3.0').save()

    def test_visited_on_defaults_to_today(self):
        from django.utils import timezone
        r = self.review('4.0')
        r.save()
        self.assertEqual(r.visited_on, timezone.localdate())

    def test_restaurant_category(self):
        p = Place.objects.create(
            kakao_id='999', category=Place.Category.RESTAURANT, category_detail='음식점 > 한식 > 국밥',
            name='망원 국밥', address='서울 마포구 망원동', latitude=0, longitude=0,
        )
        self.assertEqual(p.get_category_display(), '식당')

    def test_kakao_id_is_unique(self):
        with self.assertRaises(IntegrityError):
            Place.objects.create(kakao_id='12345', category=Place.Category.CAFE, name='중복', address='-', latitude=0, longitude=0)

    def test_one_wish_per_user_and_cafe(self):
        Wishlist.objects.create(user=self.user, place=self.cafe)
        with self.assertRaises(IntegrityError):
            Wishlist.objects.create(user=self.user, place=self.cafe)


class AdminTest(TestCase):
    def test_admin_pages_open(self):
        admin = User.objects.create_superuser(username='admin', password='test-pass-1234', nickname='관리자', email='')
        self.client.force_login(admin)
        for page in ['user', 'place', 'review', 'wishlist', 'follow']:
            res = self.client.get(f'/admin/api/{page}/')
            self.assertEqual(res.status_code, 200, page)


class AuthApiTest(TestCase):
    signup_data = {'username': 'yurim', 'nickname': '유림', 'password': 'latte-and-cake-77'}

    def signup(self, **override):
        return self.client.post('/api/auth/signup/', {**self.signup_data, **override}, content_type='application/json')

    def login(self, password='latte-and-cake-77'):
        return self.client.post('/api/auth/login/', {'username': 'yurim', 'password': password}, content_type='application/json')

    def test_signup_creates_user_without_returning_password(self):
        res = self.signup()
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()['nickname'], '유림')
        self.assertNotIn('password', res.json())
        # 비밀번호는 평문이 아니라 해시로 저장된다
        self.assertNotEqual(User.objects.get(username='yurim').password, 'latte-and-cake-77')

    def test_signup_rejects_duplicate_nickname(self):
        self.signup()
        res = self.signup(username='other')
        self.assertEqual(res.status_code, 400)
        self.assertIn('nickname', res.json())

    def test_signup_rejects_weak_password(self):
        res = self.signup(password='1234')
        self.assertEqual(res.status_code, 400)
        self.assertIn('password', res.json())

    def test_login_returns_tokens_and_me_works(self):
        self.signup()
        res = self.login()
        self.assertEqual(res.status_code, 200)
        access = res.json()['access']
        self.assertIn('refresh', res.json())
        me = self.client.get('/api/auth/me/', HTTP_AUTHORIZATION=f'Bearer {access}')
        self.assertEqual(me.json()['nickname'], '유림')

    def test_login_fails_with_wrong_password(self):
        self.signup()
        self.assertEqual(self.login('wrong-password').status_code, 401)

    def test_me_requires_login(self):
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 401)

    def test_refresh_for_deleted_user_returns_401(self):
        self.signup()
        refresh = self.login().json()['refresh']
        User.objects.filter(username='yurim').delete()
        res = self.client.post('/api/auth/refresh/', {'refresh': refresh}, content_type='application/json')
        self.assertEqual(res.status_code, 401)

    def test_refresh_gives_new_access_token(self):
        self.signup()
        refresh = self.login().json()['refresh']
        res = self.client.post('/api/auth/refresh/', {'refresh': refresh}, content_type='application/json')
        self.assertEqual(res.status_code, 200)
        self.assertIn('access', res.json())


from unittest.mock import patch

from django.core.cache import cache

from . import kakao


def kakao_doc(kakao_id, name, code='CE7', detail='음식점 > 카페'):
    """카카오 검색 응답의 장소 한 개 (테스트용)"""
    return {
        'id': kakao_id, 'place_name': name, 'category_group_code': code, 'category_name': detail,
        'road_address_name': '서울 마포구 망원로 1', 'address_name': '서울 마포구 망원동 1',
        'x': '126.9010000', 'y': '37.5560000',
    }


class PlaceSearchApiTest(TestCase):
    def setUp(self):
        cache.clear()  # 호출 횟수 제한 기록 초기화

    def search(self, q='망원동 카페', **params):
        return self.client.get('/api/places/search/', {'q': q, **params})

    @patch('api.kakao.search_places')
    def test_search_saves_places_and_keeps_order(self, mock):
        mock.return_value = [kakao_doc('2', '두번째'), kakao_doc('1', '첫번째', 'FD6', '음식점 > 한식 > 국밥')]
        res = self.search()
        self.assertEqual(res.status_code, 200)
        self.assertEqual([p['name'] for p in res.json()], ['두번째', '첫번째'])
        self.assertEqual(res.json()[1]['category_label'], '식당')
        self.assertEqual(Place.objects.count(), 2)

    @patch('api.kakao.search_places')
    def test_same_place_is_not_duplicated_and_gets_updated(self, mock):
        mock.return_value = [kakao_doc('1', '옛 이름')]
        self.search()
        mock.return_value = [kakao_doc('1', '새 이름')]
        self.search()
        self.assertEqual(Place.objects.count(), 1)
        self.assertEqual(Place.objects.get().name, '새 이름')

    @patch('api.kakao.search_places')
    def test_result_includes_average_rating(self, mock):
        mock.return_value = [kakao_doc('1', '카페 온기')]
        self.search()
        place = Place.objects.get()
        for i, rating in enumerate(['4.0', '5.0']):
            user = User.objects.create_user(username=f'u{i}', password='x', nickname=f'n{i}')
            Review.objects.create(user=user, place=place, rating=Decimal(rating))
        body = self.search().json()[0]
        self.assertEqual(body['avg_rating'], '4.5')
        self.assertEqual(body['review_count'], 2)

    @patch('api.kakao.search_places')
    def test_category_is_passed_to_kakao(self, mock):
        mock.return_value = []
        self.search(category='FD6')
        mock.assert_called_once_with('망원동 카페', 'FD6')

    def test_empty_query_is_rejected(self):
        self.assertEqual(self.search(q='  ').status_code, 400)

    def test_unknown_category_is_rejected(self):
        self.assertEqual(self.search(category='AT4').status_code, 400)

    @patch('api.kakao.search_places', side_effect=kakao.KakaoError('down'))
    def test_kakao_failure_returns_502(self, mock):
        self.assertEqual(self.search().status_code, 502)

    def test_kakao_client_drops_non_cafe_restaurant(self):
        fake = {'documents': [kakao_doc('1', '카페'), kakao_doc('2', '지하철역', 'SW8'), kakao_doc('3', '식당', 'FD6')]}
        with patch.dict('os.environ', {'KAKAO_REST_API_KEY': 'test'}), patch('api.kakao.urlopen') as urlopen:
            urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(fake).encode()
            names = [d['place_name'] for d in kakao.search_places('망원동')]
        self.assertEqual(names, ['카페', '식당'])

    def test_kakao_client_requires_key(self):
        with patch.dict('os.environ', {'KAKAO_REST_API_KEY': ''}):
            with self.assertRaises(kakao.KakaoError):
                kakao.search_places('망원동')


from datetime import timedelta

from rest_framework.test import APITestCase


class ReviewApiTest(APITestCase):
    def setUp(self):
        self.place = Place.objects.create(
            kakao_id='1', category=Place.Category.CAFE, name='카페 온기', address='서울 마포구',
            latitude=0, longitude=0,
        )
        self.url = f'/api/places/{self.place.id}/'
        self.me = User.objects.create_user(username='me', password='x', nickname='나')
        self.other = User.objects.create_user(username='other', password='x', nickname='남')

    def put_review(self, user, **data):
        self.client.force_authenticate(user)  # JWT 대신 테스트용으로 로그인 처리
        return self.client.put(self.url + 'review/', data, format='json')

    def test_detail_for_anonymous(self):
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['name'], '카페 온기')
        self.assertIsNone(res.json()['my_review'])
        self.assertIsNone(res.json()['avg_rating'])

    def test_detail_404(self):
        self.assertEqual(self.client.get('/api/places/9999/').status_code, 404)

    def test_create_then_update_review(self):
        res = self.put_review(self.me, rating='4.0', comment='라떼 맛집')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['avg_rating'], '4.0')
        self.assertEqual(res.json()['my_review']['visited_on'], str(timezone.localdate()))
        # 같은 장소에 다시 PUT 하면 새로 만들지 않고 고친다 (보낸 값만 바뀜)
        res = self.put_review(self.me, rating='3.5')
        self.assertEqual(Review.objects.count(), 1)
        self.assertEqual(res.json()['my_review']['comment'], '라떼 맛집')
        self.assertEqual(res.json()['my_review']['rating'], '3.5')

    def test_average_across_users(self):
        self.put_review(self.me, rating='4.0')
        res = self.put_review(self.other, rating='5.0')
        self.assertEqual(res.json()['avg_rating'], '4.5')
        self.assertEqual(res.json()['review_count'], 2)

    def test_rejects_bad_rating_and_future_date(self):
        self.assertEqual(self.put_review(self.me, rating='3.7').status_code, 400)
        self.assertEqual(self.put_review(self.me, rating='0').status_code, 400)
        tomorrow = str(timezone.localdate() + timedelta(days=1))
        self.assertEqual(self.put_review(self.me, rating='4.0', visited_on=tomorrow).status_code, 400)

    def test_review_requires_login(self):
        res = self.client.put(self.url + 'review/', {'rating': '4.0'}, format='json')
        self.assertEqual(res.status_code, 401)

    def test_delete_review(self):
        self.put_review(self.me, rating='4.0')
        res = self.client.delete(self.url + 'review/')
        self.assertIsNone(res.json()['my_review'])
        self.assertEqual(res.json()['review_count'], 0)

    def test_detail_shows_my_review_and_only_comments(self):
        self.put_review(self.other, rating='5.0', comment='또 갈래요')
        self.put_review(self.me, rating='3.0')  # 한 줄 평 없이 별점만
        res = self.client.get(self.url).json()
        self.assertEqual(res['my_review']['rating'], '3.0')
        self.assertEqual([c['nickname'] for c in res['comments']], ['남'])

    def test_wish_toggle(self):
        self.client.force_authenticate(self.me)
        self.assertTrue(self.client.post(self.url + 'wish/').json()['wished'])
        self.client.post(self.url + 'wish/')  # 두 번 눌러도 하나만
        self.assertEqual(Wishlist.objects.count(), 1)
        self.assertTrue(self.client.get(self.url).json()['wished'])
        self.assertFalse(self.client.delete(self.url + 'wish/').json()['wished'])
        self.assertEqual(Wishlist.objects.count(), 0)


class HomeAndMeApiTest(APITestCase):
    def setUp(self):
        cache.clear()
        # 홈의 "요즘 뜨는 동네" 줄이 실제 카카오를 부르지 않도록
        patcher = patch('api.kakao.search_places', return_value=[])
        patcher.start()
        self.addCleanup(patcher.stop)
        def place(kid, name, cat):
            return Place.objects.create(kakao_id=kid, category=cat, name=name, address='서울 마포구', latitude=0, longitude=0)

        self.cafe = place('1', '카페 온기', Place.Category.CAFE)
        self.cafe2 = place('2', '달빛 카페', Place.Category.CAFE)
        self.food = place('3', '망원 국밥', Place.Category.RESTAURANT)
        place('4', '평가 없는 곳', Place.Category.CAFE)
        self.me = User.objects.create_user(username='me', password='x', nickname='나')
        self.other = User.objects.create_user(username='other', password='x', nickname='남')
        today = timezone.localdate()
        Review.objects.create(user=self.me, place=self.cafe, rating=Decimal('4.0'), comment='좋아요', visited_on=today.replace(day=1))
        Review.objects.create(user=self.me, place=self.food, rating=Decimal('4.0'), visited_on=today)
        Review.objects.create(user=self.other, place=self.cafe2, rating=Decimal('5.0'))
        Wishlist.objects.create(user=self.me, place=self.cafe2)
        self.today = today

    def test_home_ranking_and_counts(self):
        res = self.client.get('/api/home/').json()
        self.assertEqual(res['total_reviews'], 3)
        # 같은 평균·평가 수면 이름순
        self.assertEqual([p['name'] for p in res['ranking']], ['달빛 카페', '망원 국밥', '카페 온기'])
        self.assertIsNotNone(res['featured'])

    def test_home_category_filter(self):
        res = self.client.get('/api/home/', {'category': 'FD6'}).json()
        self.assertEqual(res['total_reviews'], 1)
        self.assertEqual([p['name'] for p in res['ranking']], ['망원 국밥'])

    def test_home_empty(self):
        Review.objects.all().delete()
        res = self.client.get('/api/home/').json()
        self.assertEqual(res['ranking'], [])
        self.assertIsNone(res['featured'])

    def test_calendar_month_and_filter(self):
        self.client.force_authenticate(self.me)
        params = {'year': self.today.year, 'month': self.today.month}
        res = self.client.get('/api/me/calendar/', params).json()
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0]['rating'], '4.0')
        self.assertEqual(res[0]['date'], str(self.today.replace(day=1)))  # 방문일 순
        res = self.client.get('/api/me/calendar/', {**params, 'category': 'CE7'}).json()
        self.assertEqual([r['place']['name'] for r in res], ['카페 온기'])

    def test_calendar_validates_and_requires_login(self):
        self.assertEqual(self.client.get('/api/me/calendar/', {'year': 2026, 'month': 11}).status_code, 401)
        self.client.force_authenticate(self.me)
        self.assertEqual(self.client.get('/api/me/calendar/', {'year': 2026, 'month': 13}).status_code, 400)
        self.assertEqual(self.client.get('/api/me/calendar/').status_code, 400)

    def test_summary(self):
        self.client.force_authenticate(self.me)
        res = self.client.get('/api/me/summary/').json()
        self.assertEqual(res['counts'], {'reviews': 2, 'comments': 1, 'wishes': 1, 'cafe': 1, 'restaurant': 1, 'followers': 0, 'following': 0})
        self.assertEqual(res['distribution']['4.0'], 2)
        self.assertEqual(res['top_rating'], '4.0')
        self.assertEqual({p['my_rating'] for p in res['recent']}, {'4.0'})
        self.assertEqual([p['name'] for p in res['wishlist']], ['달빛 카페'])

    def test_summary_for_new_user(self):
        self.client.force_authenticate(User.objects.create_user(username='new', password='x', nickname='새'))
        res = self.client.get('/api/me/summary/').json()
        self.assertEqual(res['counts']['reviews'], 0)
        self.assertIsNone(res['top_rating'])


class NearbyApiTest(TestCase):
    def setUp(self):
        cache.clear()

    def nearby(self, **params):
        return self.client.get('/api/places/nearby/', {'lat': '37.556', 'lng': '126.901', **params})

    @patch('api.kakao.nearby_places')
    def test_returns_places_with_distance_in_order(self, mock):
        mock.return_value = [{**kakao_doc('1', '가까운 카페'), 'distance': '120'}, {**kakao_doc('2', '먼 식당', 'FD6'), 'distance': '850'}]
        res = self.nearby(radius='500')
        self.assertEqual(res.status_code, 200)
        self.assertEqual([(p['name'], p['distance']) for p in res.json()], [('가까운 카페', 120), ('먼 식당', 850)])
        mock.assert_called_once_with(37.556, 126.901, None, 500)
        self.assertEqual(Place.objects.count(), 2)  # 검색처럼 DB에 저장된다

    @patch('api.kakao.nearby_places', return_value=[])
    def test_radius_is_clamped(self, mock):
        self.nearby(radius='99999')
        self.assertEqual(mock.call_args.args[3], 5000)

    def test_rejects_bad_coordinates(self):
        self.assertEqual(self.client.get('/api/places/nearby/').status_code, 400)
        self.assertEqual(self.nearby(lat='abc').status_code, 400)
        self.assertEqual(self.nearby(lat='51.5', lng='-0.12').status_code, 400)  # 국외
        self.assertEqual(self.nearby(category='AT4').status_code, 400)

    @patch('api.kakao.nearby_places', side_effect=kakao.KakaoError('down'))
    def test_kakao_failure(self, mock):
        self.assertEqual(self.nearby().status_code, 502)

    def test_client_merges_cafe_and_restaurant_by_distance(self):
        responses = {
            'CE7': [{**kakao_doc('1', '카페'), 'distance': '300'}],
            'FD6': [{**kakao_doc('2', '식당', 'FD6'), 'distance': '100'}],
        }
        with patch('api.kakao._get', side_effect=lambda url, p: responses[p['category_group_code']]):
            names = [d['place_name'] for d in kakao.nearby_places(37.5, 126.9)]
        self.assertEqual(names, ['식당', '카페'])


class TagApiTest(APITestCase):
    def setUp(self):
        self.cafe = Place.objects.create(kakao_id='1', category=Place.Category.CAFE, name='카페', address='서울 마포구', latitude=0, longitude=0)
        self.url = f'/api/places/{self.cafe.id}/'
        self.users = [User.objects.create_user(username=f'u{i}', password='x', nickname=f'n{i}') for i in range(3)]

    def rate(self, user, tags, rating='4.0'):
        self.client.force_authenticate(user)
        return self.client.put(self.url + 'review/', {'rating': rating, 'tags': tags}, format='json')

    def test_save_tags_and_dedupe(self):
        res = self.rate(self.users[0], ['커피 맛집', '조용함', '커피 맛집'])
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['my_review']['tags'], ['커피 맛집', '조용함'])

    def test_rejects_too_many_and_wrong_category(self):
        self.assertEqual(self.rate(self.users[0], ['커피 맛집', '조용함', '뷰 맛집', '좌석 넓음']).status_code, 400)
        res = self.rate(self.users[0], ['가성비'])  # 식당 키워드
        self.assertEqual(res.status_code, 400)
        self.assertIn('가성비', str(res.json()))
        self.assertEqual(self.rate(self.users[0], '커피 맛집').status_code, 400)  # 목록이 아님

    def test_top_tags_by_count_and_options(self):
        self.rate(self.users[0], ['커피 맛집', '조용함'])
        self.rate(self.users[1], ['커피 맛집', '뷰 맛집'])
        self.rate(self.users[2], ['커피 맛집', '조용함', '좌석 넓음'])
        res = self.client.get(self.url).json()
        # 3번 / 2번 선택된 순서대로, 세 번째는 1번씩 고른 것 중 하나
        self.assertEqual(res['top_tags'][:2], ['커피 맛집', '조용함'])
        self.assertIn(res['top_tags'][2], ['뷰 맛집', '좌석 넓음'])
        self.assertEqual(res['tag_counts'][:2], [{'tag': '커피 맛집', 'count': 3}, {'tag': '조용함', 'count': 2}])
        self.assertIn('작업하기 좋음', res['tag_options'])
        self.assertNotIn('가성비', res['tag_options'])

    def test_updating_rating_keeps_tags(self):
        self.rate(self.users[0], ['조용함'])
        self.client.put(self.url + 'review/', {'rating': '5.0'}, format='json')
        self.assertEqual(Review.objects.get().tags, ['조용함'])

    def test_no_tags_by_default(self):
        self.client.force_authenticate(self.users[0])
        self.client.put(self.url + 'review/', {'rating': '3.0'}, format='json')
        self.assertEqual(self.client.get(self.url).json()['top_tags'], [])



class ThumbnailTest(APITestCase):
    def setUp(self):
        self.place = Place.objects.create(kakao_id='1', category=Place.Category.CAFE, name='카페 온기', address='서울 마포구 망원로 1', latitude=0, longitude=0)

    @patch('api.kakao.image_search', return_value=('https://img/thumb.jpg', 'https://blog/post'))
    def test_detail_finds_thumbnail_once(self, mock):
        res = self.client.get(f'/api/places/{self.place.id}/').json()
        self.assertEqual((res['thumbnail_url'], res['thumbnail_source']), ('https://img/thumb.jpg', 'https://blog/post'))
        mock.assert_called_once_with('카페 온기 마포구')
        self.client.get(f'/api/places/{self.place.id}/')
        self.assertEqual(mock.call_count, 1)  # 저장해 두고 다시 찾지 않는다

    @patch('api.kakao.image_search', return_value=None)
    def test_no_image_is_remembered(self, mock):
        self.client.get(f'/api/places/{self.place.id}/')
        self.client.get(f'/api/places/{self.place.id}/')
        self.assertEqual(mock.call_count, 1)
        self.assertEqual(Place.objects.get().thumbnail_url, '')

    @patch('api.kakao.image_search', side_effect=kakao.KakaoError('down'))
    def test_failure_retries_later(self, mock):
        res = self.client.get(f'/api/places/{self.place.id}/')
        self.assertEqual(res.status_code, 200)  # 사진 실패해도 상세는 보인다
        self.assertIsNone(Place.objects.get().thumbnail_checked_at)


class KakaoLoginTest(APITestCase):
    def login(self, code='abc'):
        return self.client.post('/api/auth/kakao/', {'code': code}, format='json')

    @patch('api.kakao.login_user', return_value=('12345', '유림'))
    def test_first_login_creates_user_and_returns_tokens(self, mock):
        res = self.login()
        self.assertEqual(res.status_code, 200)
        user = User.objects.get(kakao_id='12345')
        self.assertEqual(user.nickname, '유림')
        self.assertFalse(user.has_usable_password())  # 비밀번호 로그인 불가
        me = self.client.get('/api/auth/me/', HTTP_AUTHORIZATION=f"Bearer {res.json()['access']}")
        self.assertEqual(me.json()['nickname'], '유림')

    @patch('api.kakao.login_user', return_value=('12345', '유림'))
    def test_second_login_reuses_same_user(self, mock):
        self.login()
        self.login()
        self.assertEqual(User.objects.filter(kakao_id='12345').count(), 1)

    @patch('api.kakao.login_user', return_value=('999', '유림'))
    def test_duplicate_nickname_gets_number(self, mock):
        User.objects.create_user(username='yurim', password='x', nickname='유림')
        self.login()
        self.assertEqual(User.objects.get(kakao_id='999').nickname, '유림2')

    @patch('api.kakao.login_user', return_value=('777', None))
    def test_missing_nickname(self, mock):
        self.login()
        self.assertEqual(User.objects.get(kakao_id='777').nickname, '카카오 사용자')

    @patch('api.kakao.login_user', side_effect=kakao.KakaoError('bad code'))
    def test_kakao_failure(self, mock):
        self.assertEqual(self.login().status_code, 401)
        self.assertEqual(User.objects.count(), 0)

    def test_missing_code(self):
        self.assertEqual(self.client.post('/api/auth/kakao/', {}, format='json').status_code, 400)

    def test_login_url_requires_state_and_uses_redirect(self):
        self.assertEqual(self.client.get('/api/auth/kakao/url/').status_code, 400)
        url = self.client.get('/api/auth/kakao/url/', {'state': 'x' * 32}).json()['url']
        self.assertTrue(url.startswith('https://kauth.kakao.com/oauth/authorize?'))
        self.assertIn('redirect_uri=http%3A%2F%2Flocalhost%3A5173%2Fauth%2Fkakao', url)
        self.assertIn('state=' + 'x' * 32, url)



class TrendingAreaTest(APITestCase):
    def setUp(self):
        cache.clear()

    @patch('api.kakao.search_places')
    def test_home_has_area_rows_and_caches_kakao(self, mock):
        mock.side_effect = lambda q, c: [kakao_doc(f'{q}-{i}', f'{q} {i}') for i in range(12)]
        res = self.client.get('/api/home/').json()
        self.assertEqual([a['name'] for a in res['areas']], ['성수동', '망원동', '연남동', '익선동'])
        self.assertEqual(len(res['areas'][0]['places']), 10)
        mock.assert_any_call('성수동 카페', 'CE7')
        calls = mock.call_count
        self.client.get('/api/home/')
        self.assertEqual(mock.call_count, calls)  # 두 번째는 저장해 둔 결과를 쓴다

    @patch('api.kakao.search_places', return_value=[])
    def test_restaurant_tab_searches_matjip(self, mock):
        self.client.get('/api/home/', {'category': 'FD6'})
        mock.assert_any_call('망원동 맛집', 'FD6')

    @patch('api.kakao.search_places', side_effect=kakao.KakaoError('down'))
    def test_kakao_failure_still_shows_home(self, mock):
        res = self.client.get('/api/home/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['areas'], [])


import shutil
import tempfile
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image

from .models import ReviewPhoto

TEMP_MEDIA = tempfile.mkdtemp()


def make_jpeg(size=(3000, 2000), with_gps=True):
    """테스트용 JPEG (촬영 위치 EXIF 포함)"""
    img = Image.new('RGB', size, 'brown')
    exif = Image.Exif()
    if with_gps:
        exif[0x8825] = {1: 'N', 2: (37.0, 33.0, 0.0)}  # GPSInfo
    out = BytesIO()
    img.save(out, 'JPEG', exif=exif)
    return SimpleUploadedFile('latte.jpg', out.getvalue(), content_type='image/jpeg')


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class ReviewPhotoTest(APITestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.place = Place.objects.create(kakao_id='1', category=Place.Category.CAFE, name='카페', address='서울 마포구', latitude=0, longitude=0, thumbnail_url='https://img/search.jpg')
        self.url = f'/api/places/{self.place.id}/review/photos/'
        self.me = User.objects.create_user(username='me', password='x', nickname='나')
        self.client.force_authenticate(self.me)

    def rate(self):
        self.client.put(f'/api/places/{self.place.id}/review/', {'rating': '4.0'}, format='json')

    def upload(self, *files):
        return self.client.post(self.url, {'photos': list(files)}, format='multipart')

    def test_needs_rating_first(self):
        self.assertEqual(self.upload(make_jpeg()).status_code, 400)

    def test_upload_resizes_and_removes_location(self):
        self.rate()
        res = self.upload(make_jpeg(), make_jpeg())
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()['my_review']['photos']), 2)
        saved = Image.open(ReviewPhoto.objects.first().image.path)
        self.assertLessEqual(max(saved.size), 1600)
        self.assertNotIn(0x8825, saved.getexif())  # GPS 정보가 지워졌다

    def test_max_three_photos(self):
        self.rate()
        self.upload(make_jpeg(), make_jpeg())
        res = self.upload(make_jpeg(), make_jpeg())
        self.assertEqual(res.status_code, 400)
        self.assertEqual(ReviewPhoto.objects.count(), 2)  # 하나도 추가되지 않음

    def test_rejects_non_image(self):
        self.rate()
        fake = SimpleUploadedFile('virus.jpg', b'not an image', content_type='image/jpeg')
        self.assertEqual(self.upload(fake).status_code, 400)

    def test_delete_own_photo_only(self):
        self.rate()
        photo_id = self.upload(make_jpeg()).json()['my_review']['photos'][0]['id']
        other = User.objects.create_user(username='o', password='x', nickname='남')
        self.client.force_authenticate(other)
        self.assertEqual(self.client.delete(f'{self.url}{photo_id}/').status_code, 404)
        self.client.force_authenticate(self.me)
        self.assertEqual(self.client.delete(f'{self.url}{photo_id}/').json()['my_review']['photos'], [])

    def test_review_photo_becomes_place_poster_and_shows_in_list(self):
        self.rate()  # 한 줄 평 없이 사진만
        self.upload(make_jpeg())
        detail = self.client.get(f'/api/places/{self.place.id}/').json()
        self.assertTrue(detail['thumbnail_url'].startswith('/media/reviews/'))
        self.assertEqual(detail['thumbnail_source'], '')
        self.assertEqual(len(detail['comments']), 1)
        self.assertEqual(len(detail['comments'][0]['photos']), 1)


from datetime import date

from . import receipts

SAMPLE_RECEIPT = """(주)온기에프앤비 카페 온기 성수점
서울 성동구 연무장길 12
2026-11-07 14:32:10
아메리카노 1 4,500
바스크치즈케이크 1 8,000
합계 12,500
승인번호 30012345"""


class ReceiptRulesTest(TestCase):
    def place(self, name='카페 온기 성수점', address='서울 성동구 연무장길 12'):
        return Place(name=name, address=address, category='CE7', kakao_id='x', latitude=0, longitude=0)

    def test_finds_recent_paid_date_in_many_formats(self):
        today = date(2026, 11, 9)
        for text, expected in [
            ('2026-11-07 14:32', date(2026, 11, 7)),
            ('2026.11.07', date(2026, 11, 7)),
            ('2026년 11월 7일', date(2026, 11, 7)),
            ('26/11/07 결제', date(2026, 11, 7)),
            ('2026-12-01', None),  # 미래
            ('2025-01-01', None),  # 90일보다 오래됨
            ('2026-13-40', None),  # 없는 날짜
        ]:
            self.assertEqual(receipts.find_paid_date(text, today), expected, text)

    def test_store_name_matching(self):
        place = self.place()
        self.assertTrue(receipts.matches_place('카페온기 성수점 영수증', place))
        self.assertTrue(receipts.matches_place('(주)온기 망원', place))  # "카페"·지점명 빼고도 맞음
        self.assertTrue(receipts.matches_place('주소 연무장길 12', self.place(name='전혀 다른 이름')))  # 주소로 맞음
        self.assertFalse(receipts.matches_place('스타벅스 성수역점 2026-11-07', place))

    def test_fingerprint_uses_approval_number(self):
        a = receipts.fingerprint('승인번호 30012345 합계 12,500', 1, date(2026, 11, 7))
        b = receipts.fingerprint('승인 번호: 30012345 (다시 찍음)', 1, date(2026, 11, 7))
        c = receipts.fingerprint('승인번호 99999999', 1, date(2026, 11, 7))
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)


class ReceiptApiTest(APITestCase):
    def setUp(self):
        cache.clear()
        self.place = Place.objects.create(kakao_id='1', category=Place.Category.CAFE, name='카페 온기 성수점', address='서울 성동구 연무장길 12', latitude=0, longitude=0)
        self.url = f'/api/places/{self.place.id}/'
        self.me = User.objects.create_user(username='me', password='x', nickname='나')
        self.client.force_authenticate(self.me)

    def rate(self, user=None, rating='4.0'):
        self.client.force_authenticate(user or self.me)
        self.client.put(self.url + 'review/', {'rating': rating}, format='json')

    def send(self, text=SAMPLE_RECEIPT):
        # 가짜 OCR + "오늘"을 2026-11-09로 고정
        with patch('api.receipts.read_text', return_value=text), patch('api.views.timezone.localdate', return_value=date(2026, 11, 9)):
            return self.client.post(self.url + 'review/receipt/', {'receipt': make_jpeg(with_gps=False)}, format='multipart')

    def test_needs_rating_first(self):
        self.assertEqual(self.send().status_code, 400)

    def test_verifies_and_sets_visit_date(self):
        self.rate()
        res = self.send()
        self.assertEqual(res.status_code, 200, res.json())
        self.assertTrue(res.json()['my_review']['verified'])
        self.assertEqual(res.json()['my_review']['visited_on'], '2026-11-07')
        detail = self.client.get(self.url).json()
        self.assertEqual((detail['verified_count'], detail['verified_avg']), (1, '4.0'))
        self.assertTrue(detail['comments'][0]['verified'])  # 한 줄 평이 없어도 인증 리뷰는 목록에

    def test_wrong_store_or_no_date_is_rejected_with_reason(self):
        self.rate()
        res = self.send('스타벅스 성수역점 2026-11-07 승인번호 1234')
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.json()['check']['store'])
        res = self.send('카페 온기 성수점 합계 12,500')
        self.assertEqual(res.status_code, 400)
        self.assertIsNone(res.json()['check']['date'])

    def test_same_receipt_cannot_be_reused_by_others(self):
        self.rate()
        self.send()
        other = User.objects.create_user(username='o', password='x', nickname='남')
        self.rate(other)
        res = self.send()
        self.assertEqual(res.status_code, 400)
        self.assertIn('이미', res.json()['detail'])

    def test_verified_visit_date_is_locked(self):
        self.rate()
        self.send()
        res = self.client.put(self.url + 'review/', {'visited_on': '2026-11-01'}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertEqual(self.client.put(self.url + 'review/', {'rating': '5.0'}, format='json').status_code, 200)

    def test_ocr_not_configured(self):
        self.rate()
        with patch.dict('os.environ', {'CLOVA_OCR_URL': '', 'CLOVA_OCR_SECRET': ''}):
            res = self.client.post(self.url + 'review/receipt/', {'receipt': make_jpeg(with_gps=False)}, format='multipart')
        self.assertEqual(res.status_code, 400)
        self.assertIn('준비 중', res.json()['detail'])

    def test_rejects_non_image(self):
        self.rate()
        fake = SimpleUploadedFile('r.jpg', b'nope', content_type='image/jpeg')
        self.assertEqual(self.client.post(self.url + 'review/receipt/', {'receipt': fake}, format='multipart').status_code, 400)


from . import recommend
from .models import Follow


class RecommendTest(APITestCase):
    def setUp(self):
        # 1~7번: 마포구 카페 (7번만 디저트카페), 8번: 강남구 카페
        self.places = [
            Place.objects.create(
                kakao_id=str(i), category=Place.Category.CAFE,
                category_detail='음식점 > 카페 > 디저트카페' if i == 7 else '음식점 > 카페',
                name=f'카페{i}', address='서울 마포구 망원로 1' if i < 8 else '서울 강남구 역삼로 1', latitude=0, longitude=0,
            )
            for i in range(1, 9)
        ]
        self.me = self.user('me')
        self.twin = self.user('twin')  # 나와 취향이 같은 사람
        self.opposite = self.user('opp')  # 나와 취향이 반대인 사람
        mine = ['5.0', '4.0', '2.0', '1.0', '3.0']
        self.rate(self.me, mine)
        self.rate(self.twin, mine + ['5.0', '1.0'])  # 6번은 좋아하고 7번은 싫어함
        self.rate(self.opposite, ['1.0', '2.0', '4.0', '5.0', '3.0', '1.0'])

    def user(self, name):
        return User.objects.create_user(username=name, password='x', nickname=name)

    def rate(self, user, ratings):
        for place, r in zip(self.places, ratings):
            Review.objects.create(user=user, place=place, rating=Decimal(r))

    def test_similarity(self):
        self.assertAlmostEqual(recommend.similarity({1: 5, 2: 1, 3: 3}, {1: 4, 2: 2, 3: 3}, 3, 3), 1.0)
        self.assertAlmostEqual(recommend.similarity({1: 5, 2: 1, 3: 3}, {1: 1, 2: 5, 3: 3}, 3, 3), -1.0)
        self.assertIsNone(recommend.similarity({1: 5, 2: 1}, {1: 4, 2: 2}, 3, 3))  # 같이 평가한 곳이 3곳 미만

    def test_predict_uses_similar_people_only(self):
        p6, p7 = self.places[5].id, self.places[6].id
        # 반대 취향인 사람이 6번에 1점을 줬지만 무시되고, 같은 취향인 사람의 5점·1점을 따른다
        self.assertEqual(recommend.predict(self.me), {p6: 5.0, p7: 1.0})
        self.assertEqual(recommend.predict(self.me, {p6}), {p6: 5.0})

    def test_recommendations_api_and_detail_prediction(self):
        self.client.force_authenticate(self.me)
        res = self.client.get('/api/recommendations/').json()
        self.assertEqual([(p['name'], p['predicted_rating']) for p in res], [('카페6', '5.0')])  # 예상 1.0인 7번은 빠진다
        self.assertEqual(self.client.get('/api/recommendations/', {'area': '강남구'}).json(), [])
        self.assertEqual(self.client.get(f'/api/places/{self.places[5].id}/').json()['predicted_rating'], '5.0')
        # 이미 평가한 곳은 예상 별점이 없다
        self.assertIsNone(self.client.get(f'/api/places/{self.places[0].id}/').json()['predicted_rating'])

    def test_cold_start_prefers_liked_detail_then_my_area(self):
        Review.objects.create(user=self.twin, place=self.places[7], rating=Decimal('5.0'))  # 강남 카페, 평균 5.0
        dessert = Place.objects.create(
            kakao_id='99', category='CE7', category_detail='음식점 > 카페 > 디저트카페', name='강남 디저트',
            address='서울 강남구 1', latitude=0, longitude=0,
        )
        Review.objects.create(user=self.twin, place=dessert, rating=Decimal('3.0'))
        new = self.user('new')
        Review.objects.create(user=new, place=self.places[6], rating=Decimal('4.5'))  # 마포 디저트카페를 좋아함
        self.client.force_authenticate(new)
        res = self.client.get('/api/recommendations/').json()
        self.assertTrue(all(p['predicted_rating'] is None for p in res))  # 평가 5개 미만 → 예상 별점 없음
        names = [p['name'] for p in res]
        self.assertNotIn('카페7', names)  # 이미 평가한 곳은 빠진다
        self.assertEqual(names[0], '강남 디저트')  # 좋아하는 세부 분류가 먼저
        self.assertEqual(names[-1], '카페8')  # 그다음 자주 가는 동네(마포)가 평균 별점 높은 강남보다 먼저

    def test_requires_login(self):
        self.assertEqual(self.client.get('/api/recommendations/').status_code, 401)


class TasteAndFollowTest(APITestCase):
    def setUp(self):
        self.cafe = Place.objects.create(
            kakao_id='1', category='CE7', category_detail='음식점 > 카페 > 디저트카페', name='카페 온기',
            address='서울 마포구 망원로 1', latitude=0, longitude=0,
        )
        self.me = User.objects.create_user(username='me', password='x', nickname='나')
        self.friend = User.objects.create_user(username='friend-login-id', password='x', nickname='친구')
        Review.objects.create(user=self.me, place=self.cafe, rating=Decimal('4.5'), tags=['디저트 맛집', '조용함'])
        Review.objects.create(user=self.friend, place=self.cafe, rating=Decimal('3.5'), comment='무난')

    def test_taste(self):
        self.client.force_authenticate(self.me)
        taste = self.client.get('/api/me/summary/').json()['taste']
        self.assertEqual(taste['avg'], '4.5')
        self.assertEqual(taste['everyone_avg'], '4.0')
        self.assertEqual([t['name'] for t in taste['tags']], ['디저트 맛집', '조용함'])
        self.assertEqual(taste['details'], [{'name': '디저트카페', 'count': 1}])
        self.assertEqual(taste['areas'], [{'name': '마포구', 'count': 1}])

    def test_follow_profile_and_feed(self):
        url = f'/api/users/{self.friend.id}/'
        self.assertEqual(self.client.post(url + 'follow/').status_code, 401)
        self.client.force_authenticate(self.me)
        self.assertEqual(self.client.post(url + 'follow/').json(), {'is_following': True, 'followers': 1})
        self.client.post(url + 'follow/')  # 두 번 눌러도 하나만
        self.assertEqual(Follow.objects.count(), 1)

        profile = self.client.get(url).json()
        self.assertEqual(profile['counts'], {'reviews': 1, 'followers': 1, 'following': 0})
        self.assertTrue(profile['is_following'])
        self.assertIsNone(profile['top_tag'])  # 친구는 키워드를 고르지 않았다
        self.assertEqual(profile['reviews'][0]['rating'], '3.5')
        self.assertNotIn('friend-login-id', json.dumps(profile))  # 로그인 아이디는 공개하지 않는다

        summary = self.client.get('/api/me/summary/').json()
        self.assertEqual(summary['counts']['following'], 1)
        self.assertEqual([(p['name'], p['nickname'], p['rating']) for p in summary['feed']], [('카페 온기', '친구', '3.5')])

        self.assertFalse(self.client.delete(url + 'follow/').json()['is_following'])
        self.assertEqual(Follow.objects.count(), 0)

    def test_cannot_follow_self_and_place_reviews_link_user(self):
        self.client.force_authenticate(self.me)
        self.assertEqual(self.client.post(f'/api/users/{self.me.id}/follow/').status_code, 400)
        comments = self.client.get(f'/api/places/{self.cafe.id}/').json()['comments']
        self.assertEqual(comments[0]['user_id'], self.friend.id)
        self.assertEqual(self.client.get('/api/users/9999/').status_code, 404)


class RankingTest(APITestCase):
    def setUp(self):
        def place(kid, name, cat='CE7', addr='서울 마포구 망원로 1'):
            return Place.objects.create(kakao_id=kid, category=cat, name=name, address=addr, latitude=0, longitude=0)

        self.one_hit = place('1', '한 명만 5점')
        self.steady = place('2', '꾸준한 4.5', addr='서울 성동구 연무장길 1')
        self.food = place('3', '국밥집', 'FD6')
        users = [User.objects.create_user(username=f'u{i}', password='x', nickname=f'u{i}') for i in range(6)]
        Review.objects.create(user=users[0], place=self.one_hit, rating=Decimal('5.0'))
        for u in users:
            Review.objects.create(user=u, place=self.steady, rating=Decimal('4.5'), tags=['조용함'])
        for u in users[:3]:  # 전체 평균 4.1 (5점·4.5점·3점이 섞여 있다)
            Review.objects.create(user=u, place=self.food, rating=Decimal('3.0'), tags=['가성비'])

    def names(self, **params):
        return [p['name'] for p in self.client.get('/api/rankings/', params).json()['places']]

    def test_bayesian_average_beats_single_perfect_score(self):
        # 단순 평균이면 5.0(1명)이 1등이지만, 평가가 적어 전체 평균 쪽으로 당겨진다
        self.assertEqual(self.names(), ['꾸준한 4.5', '한 명만 5점', '국밥집'])
        self.assertEqual(self.client.get('/api/home/').json()['ranking'][0]['name'], '꾸준한 4.5')

    def test_filters(self):
        self.assertEqual(self.names(category='FD6'), ['국밥집'])
        self.assertEqual(self.names(tag='조용함'), ['꾸준한 4.5'])
        self.assertEqual(self.names(area='마포구'), ['한 명만 5점', '국밥집'])
        self.assertEqual(len(self.names(tag='없는 키워드')), 3)  # 모르는 키워드는 무시

    def test_options(self):
        res = self.client.get('/api/rankings/', {'category': 'CE7'}).json()
        self.assertIn('조용함', res['tags'])
        self.assertNotIn('가성비', res['tags'])
        self.assertEqual(set(res['areas']), {'마포구', '성동구'})
