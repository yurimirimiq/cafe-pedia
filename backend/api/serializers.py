from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import User


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
