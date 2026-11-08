from django.test import TestCase
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
        for page in ['user', 'place', 'review', 'wishlist']:
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
        self.assertEqual(res['counts'], {'reviews': 2, 'comments': 1, 'wishes': 1, 'cafe': 1, 'restaurant': 1})
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
