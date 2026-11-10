from decimal import Decimal

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    """기본 사용자 + 닉네임. 프로젝트 시작 시 만들어 두지 않으면 나중에 바꾸기 매우 어렵다."""

    nickname = models.CharField('닉네임', max_length=20, unique=True)
    # 카카오로 가입한 사람의 카카오 회원 번호 (아이디·비밀번호 가입자는 비어 있음)
    kakao_id = models.CharField('카카오 회원 번호', max_length=30, unique=True, null=True, blank=True)

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
    # 썸네일: 카카오 이미지 검색 결과 (사진 주소 + 출처 글 주소). 한 번 찾으면 저장해 두고 다시 찾지 않는다
    thumbnail_url = models.URLField('썸네일', max_length=500, blank=True)
    thumbnail_source = models.URLField('썸네일 출처', max_length=500, blank=True)
    thumbnail_checked_at = models.DateTimeField('썸네일 찾은 시각', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


# 별점 남길 때 고르는 키워드 (분류별). 리뷰에는 이 글자 그대로 저장한다
TAG_OPTIONS = {
    'CE7': ['커피 맛집', '디저트 맛집', '작업하기 좋음', '조용함', '대화하기 좋음', '뷰 맛집', '좌석 넓음', '콘센트 많음'],
    'FD6': ['혼밥하기 좋음', '가성비', '양 많음', '데이트', '모임하기 좋음', '웨이팅 있음', '친절함', '또 갈래요'],
}
MAX_TAGS = 3


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
    # 고른 키워드 최대 3개 (예: ["커피 맛집", "조용함"])
    tags = models.JSONField('키워드', default=list, blank=True)
    # 영수증 인증: 인증된 시각, 같은 영수증 재사용을 막는 지문(영수증 사진은 저장하지 않음)
    receipt_verified_at = models.DateTimeField('영수증 인증 시각', null=True, blank=True)
    receipt_fingerprint = models.CharField('영수증 지문', max_length=64, unique=True, null=True, blank=True)
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


MAX_PHOTOS = 3  # 리뷰 하나에 올릴 수 있는 사진 수


class ReviewPhoto(models.Model):
    """리뷰 사진. 서버에서 크기를 줄이고 위치 정보(EXIF)를 지운 JPEG 로 저장한다"""

    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name='photos')
    image = models.ImageField('사진', upload_to='reviews/%Y/%m/')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']


class Follow(models.Model):
    """팔로우: follower 가 following 을 따라간다"""

    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name='following')
    following = models.ForeignKey(User, on_delete=models.CASCADE, related_name='followers')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['follower', 'following'], name='one_follow_per_pair'),
            models.CheckConstraint(condition=~models.Q(follower=models.F('following')), name='no_self_follow'),
        ]

    def __str__(self):
        return f'{self.follower} → {self.following}'
