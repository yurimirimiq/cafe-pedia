from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenRefreshSerializer

from collections import Counter

from .models import MAX_TAGS, TAG_OPTIONS, Place, Review, User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'nickname']


class SignupSerializer(serializers.ModelSerializer):
    # 비밀번호는 응답에 절대 포함하지 않는다
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['username', 'nickname', 'password']

    def validate_password(self, value):
        # Django 기본 규칙: 8자 이상, 너무 흔한 비밀번호·숫자만 금지
        validate_password(value)
        return value

    def create(self, validated_data):
        # create_user 가 비밀번호를 해시로 바꿔 저장한다
        return User.objects.create_user(**validated_data)


class PlaceSerializer(serializers.ModelSerializer):
    category_label = serializers.CharField(source='get_category_display', read_only=True)
    # 평균 별점·평가 수는 view 에서 annotate 로 계산해 넘긴다
    avg_rating = serializers.DecimalField(max_digits=2, decimal_places=1, read_only=True, allow_null=True)
    review_count = serializers.IntegerField(read_only=True)
    top_tags = serializers.SerializerMethodField()

    def get_top_tags(self, place):
        """이 장소 리뷰에서 가장 많이 고른 키워드 3개"""
        # shortcut: 장소마다 쿼리 1번 (목록 15~30개라 괜찮음), 느려지면 Place 에 집계 칸을 두고 리뷰 저장 때 갱신
        counts = Counter(tag for tags in place.reviews.values_list('tags', flat=True) for tag in tags)
        return [tag for tag, _ in counts.most_common(MAX_TAGS)]

    class Meta:
        model = Place
        fields = [
            'id', 'kakao_id', 'name', 'category', 'category_label', 'category_detail',
            'address', 'latitude', 'longitude', 'avg_rating', 'review_count', 'top_tags',
            'thumbnail_url', 'thumbnail_source',
        ]


class SafeTokenRefreshSerializer(TokenRefreshSerializer):
    """탈퇴·삭제된 사용자의 refresh 토큰이면 500 대신 401(다시 로그인 필요)로 답한다"""

    def validate(self, attrs):
        try:
            return super().validate(attrs)
        except User.DoesNotExist:
            raise AuthenticationFailed('사용자를 찾을 수 없어요. 다시 로그인하세요.')


class ReviewSerializer(serializers.ModelSerializer):
    """다른 사람에게 보여줄 리뷰 (닉네임만 공개)"""

    nickname = serializers.CharField(source='user.nickname', read_only=True)

    class Meta:
        model = Review
        fields = ['id', 'nickname', 'rating', 'comment', 'tags', 'visited_on', 'updated_at']


class MyReviewSerializer(serializers.ModelSerializer):
    """내 별점 저장용. 별점 범위·0.5 단위 검사는 모델의 validators 를 그대로 쓴다"""

    class Meta:
        model = Review
        fields = ['rating', 'comment', 'visited_on', 'tags']

    def validate_tags(self, value):
        """장소 분류에 맞는 키워드만, 중복 없이 최대 3개 (place 는 view 가 context 로 넘긴다)"""
        if not isinstance(value, list) or not all(isinstance(t, str) for t in value):
            raise serializers.ValidationError('키워드는 글자 목록으로 보내 주세요.')
        tags = list(dict.fromkeys(value))  # 순서를 지키며 중복 제거
        if len(tags) > MAX_TAGS:
            raise serializers.ValidationError(f'키워드는 {MAX_TAGS}개까지 고를 수 있어요.')
        allowed = TAG_OPTIONS[self.context['place'].category]
        if wrong := [t for t in tags if t not in allowed]:
            raise serializers.ValidationError(f'이 장소에 고를 수 없는 키워드예요: {", ".join(wrong)}')
        return tags

    def validate_visited_on(self, value):
        if value > timezone.localdate():
            raise serializers.ValidationError('미래 날짜는 고를 수 없어요.')
        return value
