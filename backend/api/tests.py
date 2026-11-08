from django.test import TestCase


class HelloApiTest(TestCase):
    def test_hello(self):
        res = self.client.get('/api/hello/')
        self.assertEqual(res.status_code, 200)
        self.assertIn('message', res.json())

    def test_cors_allows_frontend(self):
        res = self.client.get('/api/hello/', HTTP_ORIGIN='http://localhost:5173')
        self.assertEqual(res['Access-Control-Allow-Origin'], 'http://localhost:5173')


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
