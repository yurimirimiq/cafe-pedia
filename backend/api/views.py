from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db.models import Avg, Count, Max, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken

from . import kakao
from .models import TAG_OPTIONS, Place, Review, User, Wishlist
from .serializers import (
    MyReviewSerializer,
    PlaceSerializer,
    ReviewSerializer,
    SignupSerializer,
    UserSerializer,
)


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

    places = save_places(documents)
    return Response(PlaceSerializer(places, many=True).data)


def save_places(documents):
    """카카오 장소 목록을 DB에 저장(이미 있으면 갱신)하고, 같은 순서로 평균 별점이 붙은 Place 목록을 돌려준다"""
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

    fill_thumbnails(Place.objects.filter(kakao_id__in=kakao_ids, thumbnail_checked_at__isnull=True))
    # 카카오가 준 순서(관련도 순·거리 순)를 그대로 유지한다
    places = {p.kakao_id: p for p in with_ratings(Place.objects.filter(kakao_id__in=kakao_ids))}
    return [places[k] for k in kakao_ids]


def fill_thumbnails(places):
    """아직 썸네일을 찾지 않은 장소들의 사진을 카카오 이미지 검색으로 찾아 저장한다 (동시에 여러 개)"""

    def find(place):
        area = ' '.join(place.address.split()[1:2])  # "서울 마포구 망원로 1" → "마포구"
        try:
            return kakao.image_search(f'{place.name} {area}') or ('', '')
        except kakao.KakaoError:
            return None  # 실패하면 저장하지 않고 다음에 다시 시도

    places = list(places)
    if not places:
        return
    # 카카오 호출(네트워크)만 동시에 하고, DB 저장은 여기(메인 스레드)에서 한다
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(find, places))
    for place, found in zip(places, results):
        if found is not None:
            place.thumbnail_url, place.thumbnail_source = found
            place.thumbnail_checked_at = timezone.now()
            place.save(update_fields=['thumbnail_url', 'thumbnail_source', 'thumbnail_checked_at'])


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([AnonRateThrottle, UserRateThrottle])
def nearby_places(request):
    """내 주변: ?lat=37.556&lng=126.901&radius=1000&category=CE7

    위치는 카카오에 검색할 때만 쓰고 저장하지 않는다.
    """
    try:
        lat, lng = float(request.query_params['lat']), float(request.query_params['lng'])
        radius = int(request.query_params.get('radius', 1000))
    except (KeyError, ValueError):
        return Response({'detail': 'lat, lng 를 숫자로 보내 주세요.'}, status=status.HTTP_400_BAD_REQUEST)
    # 대한민국 대략 범위 밖이면 카카오가 결과를 주지 않으니 미리 막는다
    if not (33 <= lat <= 39 and 124 <= lng <= 132):
        return Response({'detail': '국내 위치에서만 찾을 수 있어요.'}, status=status.HTTP_400_BAD_REQUEST)
    radius = min(max(radius, 100), 5000)
    category = request.query_params.get('category') or None
    if category and category not in kakao.ALLOWED_CATEGORIES:
        return Response({'detail': '분류는 CE7(카페) 또는 FD6(식당)이에요.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        documents = kakao.nearby_places(lat, lng, category, radius)
    except kakao.KakaoError:
        return Response({'detail': '지금은 주변을 찾을 수 없어요. 잠시 후 다시 시도하세요.'}, status=status.HTTP_502_BAD_GATEWAY)

    distances = {d['id']: int(d['distance'] or 0) for d in documents}
    return Response([
        {**PlaceSerializer(p).data, 'distance': distances[p.kakao_id]} for p in save_places(documents)
    ])


@api_view(['GET'])
@permission_classes([AllowAny])
def place_detail(request, place_id):
    """장소 상세: 장소 정보 + 평균 별점 + 한 줄 평 목록 (+ 로그인했다면 내 별점·가고 싶어요 여부)"""
    fill_thumbnails(Place.objects.filter(pk=place_id, thumbnail_checked_at__isnull=True))
    place = get_object_or_404(with_ratings(Place.objects.all()), pk=place_id)
    reviews = place.reviews.select_related('user').exclude(comment='')[:20]
    data = {
        **PlaceSerializer(place).data,
        'comments': ReviewSerializer(reviews, many=True).data,
        'tag_options': TAG_OPTIONS[place.category],
        'my_review': None,
        'wished': False,
    }
    if request.user.is_authenticated:
        mine = place.reviews.filter(user=request.user).first()
        data['my_review'] = MyReviewSerializer(mine).data if mine else None
        data['wished'] = place.wishlisted_by.filter(user=request.user).exists()
    return Response(data)


def place_summary(place_id):
    """별점이 바뀐 뒤 새 평균 별점·평가 수를 돌려주기 위한 헬퍼"""
    place = with_ratings(Place.objects.filter(pk=place_id)).get()
    return {'avg_rating': PlaceSerializer(place).data['avg_rating'], 'review_count': place.review_count}


@api_view(['PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def my_review(request, place_id):
    """내 별점 남기기·고치기(PUT) / 지우기(DELETE). 한 장소에 하나라서 있으면 수정한다"""
    place = get_object_or_404(Place, pk=place_id)
    review = Review.objects.filter(user=request.user, place=place).first()

    if request.method == 'DELETE':
        if review:
            review.delete()
        return Response({'my_review': None, **place_summary(place_id)})

    serializer = MyReviewSerializer(review, data=request.data, partial=review is not None, context={'place': place})
    serializer.is_valid(raise_exception=True)
    serializer.save(user=request.user, place=place)
    return Response({'my_review': serializer.data, **place_summary(place_id)})


@api_view(['POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def wish(request, place_id):
    """가고 싶어요 추가(POST) / 취소(DELETE)"""
    place = get_object_or_404(Place, pk=place_id)
    if request.method == 'POST':
        Wishlist.objects.get_or_create(user=request.user, place=place)
    else:
        Wishlist.objects.filter(user=request.user, place=place).delete()
    return Response({'wished': request.method == 'POST'})


def category_filter(request):
    """?category=CE7|FD6 이 있으면 그 분류만, 없으면 전체"""
    category = request.query_params.get('category')
    return {'category': category} if category in kakao.ALLOWED_CATEGORIES else {}


# 홈의 "요즘 뜨는 동네" 줄 (우리 별점이 쌓이기 전에도 홈이 비어 보이지 않도록)
TRENDING_AREAS = ['성수동', '망원동', '연남동', '익선동']
AREA_CACHE_SECONDS = 6 * 60 * 60  # 카카오 호출을 아끼려고 동네별 결과를 6시간 저장


def trending_areas(category):
    """동네별 카카오 검색 상위 장소. 카카오가 실패한 동네는 건너뛴다"""
    code = category or 'CE7'  # 홈(전체) 탭에서는 카페
    word = '맛집' if code == 'FD6' else '카페'
    areas = []
    for area in TRENDING_AREAS:
        key = f'trending:{area}:{code}'
        kakao_ids = cache.get(key)
        if kakao_ids is None:
            try:
                kakao_ids = [p.kakao_id for p in save_places(kakao.search_places(f'{area} {word}', code)[:10])]
            except kakao.KakaoError:
                continue
            cache.set(key, kakao_ids, AREA_CACHE_SECONDS)
        # 별점은 저장해 둔 값이 아니라 지금 DB 기준으로 다시 계산한다
        places = {p.kakao_id: p for p in with_ratings(Place.objects.filter(kakao_id__in=kakao_ids))}
        rows = [places[k] for k in kakao_ids if k in places]
        if rows:
            areas.append({'name': area, 'places': PlaceSerializer(rows, many=True).data})
    return areas


@api_view(['GET'])
@permission_classes([AllowAny])
def home(request):
    """홈 화면: 누적 평가 수, 이번 주 가장 많이 평가된 곳, 인기 랭킹, 최근 평가된 곳"""
    places = with_ratings(Place.objects.filter(**category_filter(request), reviews__isnull=False).distinct())
    week_ago = timezone.now() - timedelta(days=7)

    featured = (
        places.annotate(week_count=Count('reviews', filter=Q(reviews__created_at__gte=week_ago)))
        .filter(week_count__gt=0)
        .order_by('-week_count', '-avg_rating')
        .first()
    )
    # shortcut: 평가 1개짜리 5.0점이 1등이 될 수 있음, 평가가 쌓이면 최소 평가 수를 두거나 베이지안 평균으로 바꾼다
    ranking = places.order_by('-avg_rating', '-review_count', 'name')[:14]
    recent = places.annotate(last_reviewed=Max('reviews__updated_at')).order_by('-last_reviewed')[:14]

    return Response({
        'total_reviews': Review.objects.filter(**{f'place__{k}': v for k, v in category_filter(request).items()}).count(),
        'featured': {**PlaceSerializer(featured).data, 'week_count': featured.week_count} if featured else None,
        'ranking': PlaceSerializer(ranking, many=True).data,
        'recent': PlaceSerializer(recent, many=True).data,
        'areas': trending_areas(category_filter(request).get('category')),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_calendar(request):
    """캘린더: ?year=2026&month=11 → 그 달에 방문한 장소 (방문일 기준)"""
    try:
        year, month = int(request.query_params['year']), int(request.query_params['month'])
        if not 1 <= month <= 12:
            raise ValueError
    except (KeyError, ValueError):
        return Response({'detail': 'year 와 month(1~12)를 숫자로 보내 주세요.'}, status=status.HTTP_400_BAD_REQUEST)

    reviews = (
        request.user.reviews.select_related('place')
        .filter(visited_on__year=year, visited_on__month=month)
        .filter(**{f'place__{k}': v for k, v in category_filter(request).items()})
        .order_by('visited_on')
    )
    return Response([
        {
            'date': r.visited_on,
            'rating': str(r.rating),  # 다른 API처럼 "4.0" 문자열로
            'place': {'id': r.place.id, 'name': r.place.name, 'category': r.place.category},
        }
        for r in reviews
    ])


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_summary(request):
    """나의 기록: 평가·한 줄 평·가고 싶어요 수, 분류별 평가 수, 별점 분포, 최근 평가, 가고 싶어요 목록"""
    reviews = request.user.reviews.select_related('place')
    distribution = {f'{r / 2:.1f}': 0 for r in range(1, 11)}  # "0.5" ~ "5.0"
    for rating, n in reviews.values_list('rating').annotate(n=Count('id')):
        distribution[f'{rating:.1f}'] = n
    top = max(distribution, key=lambda k: (distribution[k], float(k))) if reviews.exists() else None

    def place_with_my_rating(r):
        return {**PlaceSerializer(with_ratings(Place.objects.filter(pk=r.place_id)).get()).data, 'my_rating': str(r.rating)}

    wished = with_ratings(Place.objects.filter(wishlisted_by__user=request.user)).order_by('-wishlisted_by__created_at')
    return Response({
        'counts': {
            'reviews': reviews.count(),
            'comments': reviews.exclude(comment='').count(),
            'wishes': request.user.wishlist.count(),
            'cafe': reviews.filter(place__category=Place.Category.CAFE).count(),
            'restaurant': reviews.filter(place__category=Place.Category.RESTAURANT).count(),
        },
        'distribution': distribution,
        'top_rating': top,
        'recent': [place_with_my_rating(r) for r in reviews.order_by('-updated_at')[:12]],
        'wishlist': PlaceSerializer(wished[:12], many=True).data,
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def kakao_login_url(request):
    """카카오 로그인 화면 주소. state 는 프론트가 만든 임의 값 (돌아왔을 때 같은지 확인해 위조 요청을 막는다)"""
    state = request.query_params.get('state', '')
    if not 16 <= len(state) <= 64:
        return Response({'detail': 'state 가 필요해요.'}, status=status.HTTP_400_BAD_REQUEST)
    return Response({'url': kakao.login_url(settings.KAKAO_REDIRECT_URI, state)})


def unique_nickname(base):
    """닉네임이 이미 있으면 뒤에 숫자를 붙인다: 유림 → 유림2 → 유림3"""
    base = (base or '카카오 사용자')[:17]
    nickname, n = base, 1
    while User.objects.filter(nickname=nickname).exists():
        n += 1
        nickname = f'{base}{n}'
    return nickname


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AnonRateThrottle])
def kakao_login(request):
    """카카오 로그인: {code} → 우리 회원 찾기(없으면 만들기) → 우리 JWT (access / refresh)"""
    code = request.data.get('code')
    if not code:
        return Response({'detail': '인가 코드가 없어요.'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        kakao_id, nickname = kakao.login_user(code, settings.KAKAO_REDIRECT_URI)
    except kakao.KakaoError:
        return Response({'detail': '카카오 로그인에 실패했어요. 다시 시도해 주세요.'}, status=status.HTTP_401_UNAUTHORIZED)

    user = User.objects.filter(kakao_id=kakao_id).first()
    if user is None:
        user = User(username=f'kakao_{kakao_id}', kakao_id=kakao_id, nickname=unique_nickname(nickname))
        user.set_unusable_password()  # 카카오로만 로그인하는 회원 (비밀번호 로그인 불가)
        user.save()
    if not user.is_active:
        return Response({'detail': '사용할 수 없는 계정이에요.'}, status=status.HTTP_403_FORBIDDEN)

    refresh = RefreshToken.for_user(user)
    return Response({'access': str(refresh.access_token), 'refresh': str(refresh)})
