from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenRefreshSerializer

from .models import Place, Review, User


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

    class Meta:
        model = Place
        fields = [
            'id', 'kakao_id', 'name', 'category', 'category_label', 'category_detail',
            'address', 'latitude', 'longitude', 'avg_rating', 'review_count',
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
        fields = ['id', 'nickname', 'rating', 'comment', 'visited_on', 'updated_at']


class MyReviewSerializer(serializers.ModelSerializer):
    """내 별점 저장용. 별점 범위·0.5 단위 검사는 모델의 validators 를 그대로 쓴다"""

    class Meta:
        model = Review
        fields = ['rating', 'comment', 'visited_on']

    def validate_visited_on(self, value):
        if value > timezone.localdate():
            raise serializers.ValidationError('미래 날짜는 고를 수 없어요.')
        return value
