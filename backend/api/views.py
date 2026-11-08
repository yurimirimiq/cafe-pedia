from django.db.models import Avg, Count
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle

from . import kakao
from .models import Place
from .serializers import PlaceSerializer, SignupSerializer, UserSerializer


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


def with_ratings(places):
    """장소 목록에 평균 별점(avg_rating)과 평가 수(review_count)를 붙인다"""
    return places.annotate(avg_rating=Avg('reviews__rating'), review_count=Count('reviews'))


@api_view(['GET'])
@permission_classes([AllowAny])
# 카카오 API 하루 호출 한도를 지키기 위해 검색 횟수를 제한한다
@throttle_classes([AnonRateThrottle, UserRateThrottle])
def search_places(request):
    """장소 검색: ?q=망원동 카페&category=CE7(카페)|FD6(식당)

    카카오에서 찾은 장소를 DB에 저장(이미 있으면 갱신)하고, 우리 DB의 id·평균 별점과 함께 돌려준다.
    """
    query = request.query_params.get('q', '').strip()
    category = request.query_params.get('category') or None
    if not query:
        return Response({'detail': '검색어를 입력하세요.'}, status=status.HTTP_400_BAD_REQUEST)
    if category and category not in kakao.ALLOWED_CATEGORIES:
        return Response({'detail': '분류는 CE7(카페) 또는 FD6(식당)이에요.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        documents = kakao.search_places(query, category)
    except kakao.KakaoError:
        return Response({'detail': '지금은 검색할 수 없어요. 잠시 후 다시 시도하세요.'}, status=status.HTTP_502_BAD_GATEWAY)

    kakao_ids = []
    for d in documents:
        Place.objects.update_or_create(
            kakao_id=d['id'],
            defaults={
                'category': d['category_group_code'],
                'category_detail': d['category_name'],
                'name': d['place_name'],
                # 도로명 주소가 없는 곳도 있어 지번 주소로 대신한다
                'address': d['road_address_name'] or d['address_name'],
                'latitude': d['y'],
                'longitude': d['x'],
            },
        )
        kakao_ids.append(d['id'])

    # 카카오가 준 순서(관련도 순)를 그대로 유지한다
    places = {p.kakao_id: p for p in with_ratings(Place.objects.filter(kakao_id__in=kakao_ids))}
    return Response(PlaceSerializer([places[k] for k in kakao_ids], many=True).data)
