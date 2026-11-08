from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .serializers import SignupSerializer, UserSerializer


@api_view(['GET'])
def hello(request):
    """프론트엔드와 백엔드 연결 확인용 API"""
    return Response({'message': '안녕하세요, 카페피디아 API예요'})


@api_view(['POST'])
@permission_classes([AllowAny])
def signup(request):
    """회원가입: 아이디, 닉네임, 비밀번호"""
    serializer = SignupSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    """현재 로그인한 사용자 정보 (토큰이 없거나 만료되면 401)"""
    return Response(UserSerializer(request.user).data)
