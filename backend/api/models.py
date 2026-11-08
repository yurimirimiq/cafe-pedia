from decimal import Decimal

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    """기본 사용자 + 닉네임. 프로젝트 시작 시 만들어 두지 않으면 나중에 바꾸기 매우 어렵다."""

    nickname = models.CharField('닉네임', max_length=20, unique=True)

    # createsuperuser 할 때 닉네임도 묻도록
    REQUIRED_FIELDS = ['email', 'nickname']

    def __str__(self):
        return self.nickname or self.username


class Place(models.Model):
    """카카오 로컬 API에서 가져온 장소(카페 또는 식당). 카카오 장소 ID로 중복을 막는다."""

    class Category(models.TextChoices):
        # 값은 카카오 카테고리 그룹 코드와 맞춘다 (CE7 = 카페, FD6 = 음식점)
        CAFE = 'CE7', '카페'
        RESTAURANT = 'FD6', '식당'

    kakao_id = models.CharField('카카오 장소 ID', max_length=20, unique=True)
    category = models.CharField('분류', max_length=3, choices=Category.choices)
    # 카카오가 주는 세부 분류 (예: "음식점 > 한식 > 국밥") — 나중에 필터에 활용
    category_detail = models.CharField('세부 분류', max_length=100, blank=True)
    name = models.CharField('이름', max_length=100)
    address = models.CharField('주소', max_length=200)
    # 위도·경도: 소수점 7자리면 약 1cm 정밀도
    latitude = models.DecimalField('위도', max_digits=10, decimal_places=7)
    longitude = models.DecimalField('경도', max_digits=10, decimal_places=7)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


def validate_half_step(value):
    """별점은 0.5 단위만 허용 (3.5 O, 3.7 X)"""
    if (value * 2) % 1 != 0:
        raise ValidationError('별점은 0.5 단위로만 줄 수 있어요.')


class Review(models.Model):
    """별점 + 한 줄 평. 한 사용자는 한 장소에 하나만 남길 수 있다."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    place = models.ForeignKey(Place, on_delete=models.CASCADE, related_name='reviews')
    rating = models.DecimalField(
        '별점',
        max_digits=2,
        decimal_places=1,
        validators=[MinValueValidator(Decimal('0.5')), MaxValueValidator(Decimal('5.0')), validate_half_step],
    )
    comment = models.CharField('한 줄 평', max_length=200, blank=True)
    # 캘린더에 표시할 방문 날짜 (기본값: 평가한 날)
    # shortcut: 장소당 리뷰 1개라 재방문은 날짜만 바뀜, 방문 기록을 여러 개 남기려면 Visit 모델 분리
    visited_on = models.DateField('방문일', default=timezone.localdate)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            # 같은 장소를 두 번 평가하지 못하게 DB 차원에서 막는다
            models.UniqueConstraint(fields=['user', 'place'], name='one_review_per_user_place'),
            # 검증을 거치지 않은 저장도 DB가 범위를 막는다
            models.CheckConstraint(
                condition=models.Q(rating__gte=Decimal('0.5'), rating__lte=Decimal('5.0')),
                name='rating_between_0_5_and_5',
            ),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user} → {self.place} ({self.rating})'


class Wishlist(models.Model):
    """가고 싶어요"""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wishlist')
    place = models.ForeignKey(Place, on_delete=models.CASCADE, related_name='wishlisted_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'place'], name='one_wish_per_user_place'),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user} ♡ {self.place}'
