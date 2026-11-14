from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError
from django.db.models import Avg, Count, F as models_f, FloatField, Max, Prefetch, Q, Sum
from django.db.models.functions import Cast
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken

from . import kakao, photos, receipts, recommend
from .models import (
    MAX_COLLECTION_PLACES, MAX_COLLECTIONS, MAX_PHOTOS, TAG_OPTIONS,
    Collection, CollectionItem, CollectionLike, Follow, Place, Review, ReviewPhoto, User, Wishlist,
)
from .serializers import (
    CollectionSerializer,
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
    """장소 검색: ?q=망원동 카페&category=CE7(카페)|FD6(식당)|BAR(술집)&page=1~3&lat=37.556&lng=126.901

    카카오에서 찾은 장소를 DB에 저장(이미 있으면 갱신)하고, 우리 DB의 id·평균 별점과 함께 돌려준다.
    위치를 주면 가까운 순 + 거리. 위치는 카카오에 검색할 때만 쓰고 저장하지 않는다.
    → {places: [...], has_more: 다음 페이지가 있는지}
    """
    params = request.query_params
    query = params.get('q', '').strip()
    category = params.get('category') or None
    if not query:
        return Response({'detail': '검색어를 입력하세요.'}, status=status.HTTP_400_BAD_REQUEST)
    if category and category not in kakao.ALLOWED_CATEGORIES:
        return Response({'detail': '분류는 CE7(카페), FD6(식당), BAR(술집) 중 하나예요.'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        page = int(params.get('page', 1))
    except ValueError:
        page = 0
    if not 1 <= page <= kakao.MAX_SEARCH_PAGE:
        return Response({'detail': f'page 는 1~{kakao.MAX_SEARCH_PAGE} 이에요.'}, status=status.HTTP_400_BAD_REQUEST)
    lat = lng = None
    if 'lat' in params or 'lng' in params:
        coords = parse_coords(params)
        if isinstance(coords, Response):
            return coords
        lat, lng = coords

    try:
        documents, has_more = kakao.search_page(query, category, page, lat, lng)
    except kakao.KakaoError:
        return Response({'detail': '지금은 검색할 수 없어요. 잠시 후 다시 시도하세요.'}, status=status.HTTP_502_BAD_GATEWAY)

    rows = PlaceSerializer(save_places(documents), many=True).data
    if lat is not None:
        distances = {d['id']: int(d['distance'] or 0) for d in documents}
        rows = [{**row, 'distance': distances[row['kakao_id']]} for row in rows]
    return Response({'places': rows, 'has_more': has_more})


def parse_coords(params):
    """?lat=&lng= → (lat, lng), 잘못됐으면 400 Response"""
    try:
        lat, lng = float(params['lat']), float(params['lng'])
    except (KeyError, ValueError):
        return Response({'detail': 'lat, lng 를 숫자로 보내 주세요.'}, status=status.HTTP_400_BAD_REQUEST)
    # 대한민국 대략 범위 밖이면 카카오가 결과를 주지 않으니 미리 막는다
    if not (33 <= lat <= 39 and 124 <= lng <= 132):
        return Response({'detail': '국내 위치에서만 찾을 수 있어요.'}, status=status.HTTP_400_BAD_REQUEST)
    return lat, lng


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
            return kakao.pick_image(kakao.image_search(f'{place.name} {area}'), place.hidden_images) or ('', '', '')
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
            place.image_url, place.thumbnail_url, place.thumbnail_source = found
            place.thumbnail_checked_at = timezone.now()
            place.save(update_fields=['image_url', 'thumbnail_url', 'thumbnail_source', 'thumbnail_checked_at'])


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle])
def report_photo(request, place_id):
    """대표 사진이 이상해요: 지금 사진을 숨기고 다음 후보로 바꾼다 (이미지 검색 사진만, 리뷰 사진은 대상이 아니다)"""
    place = get_object_or_404(Place, pk=place_id)
    current = place.image_url or place.thumbnail_url
    if not current or ReviewPhoto.objects.filter(review__place=place).exists():
        return Response({'detail': '바꿀 수 있는 사진이 없어요.'}, status=status.HTTP_400_BAD_REQUEST)
    place.hidden_images = [*place.hidden_images, current]
    place.thumbnail_checked_at = None
    place.save(update_fields=['hidden_images', 'thumbnail_checked_at'])
    fill_thumbnails([place])
    data = PlaceSerializer(with_ratings(Place.objects.filter(pk=place.pk)).get()).data
    return Response({k: data[k] for k in ['thumbnail_url', 'thumbnail_fallback', 'thumbnail_source']})


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([AnonRateThrottle, UserRateThrottle])
def nearby_places(request):
    """내 주변: ?lat=37.556&lng=126.901&radius=1000&category=CE7

    위치는 카카오에 검색할 때만 쓰고 저장하지 않는다.
    """
    coords = parse_coords(request.query_params)
    if isinstance(coords, Response):
        return coords
    lat, lng = coords
    try:
        radius = int(request.query_params.get('radius', 1000))
    except ValueError:
        return Response({'detail': 'radius 는 숫자로 보내 주세요.'}, status=status.HTTP_400_BAD_REQUEST)
    radius = min(max(radius, 100), 5000)
    category = request.query_params.get('category') or None
    if category and category not in kakao.ALLOWED_CATEGORIES:
        return Response({'detail': '분류는 CE7(카페), FD6(식당), BAR(술집) 중 하나예요.'}, status=status.HTTP_400_BAD_REQUEST)

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
    # 한 줄 평·사진이 있거나 영수증 인증된 리뷰를 목록에 보여준다 (인증된 리뷰 먼저)
    reviews = (
        place.reviews.select_related('user').prefetch_related('photos')
        .exclude(comment='', photos__isnull=True, receipt_verified_at__isnull=True)
        .distinct()
        .order_by(models_f('receipt_verified_at').desc(nulls_last=True), '-created_at')[:50]
    )
    verified = place.reviews.filter(receipt_verified_at__isnull=False).aggregate(avg=Avg('rating'), n=Count('id'))
    data = {
        **PlaceSerializer(place).data,
        'comments': ReviewSerializer(reviews, many=True).data,
        # 영수증 인증된 사람 수와 그 사람들만의 평균 별점
        'verified_count': verified['n'],
        'verified_avg': f"{verified['avg']:.1f}" if verified['avg'] is not None else None,
        'tag_options': TAG_OPTIONS[place.category],
        # 키워드별로 고른 사람 수 (많은 순 3개): [{"tag": "디저트 맛집", "count": 42}, ...]
        'tag_counts': [
            {'tag': tag, 'count': n}
            for tag, n in Counter(t for tags in place.reviews.values_list('tags', flat=True) for t in tags).most_common(3)
        ],
        'my_review': None,
        'wished': False,
        'predicted_rating': None,
    }
    if request.user.is_authenticated:
        mine = place.reviews.filter(user=request.user).first()
        data['my_review'] = MyReviewSerializer(mine).data if mine else None
        data['wished'] = place.wishlisted_by.filter(user=request.user).exists()
        if not mine:
            guess = recommend.predict(request.user, {place.id}).get(place.id)
            data['predicted_rating'] = f'{guess:.1f}' if guess is not None else None
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
            for photo in review.photos.all():
                photo.image.delete(save=False)  # 파일도 지운다
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
    """?category=CE7|FD6|BAR 이 있으면 그 분류만, 없으면 전체"""
    category = request.query_params.get('category')
    return {'category': category} if category in kakao.ALLOWED_CATEGORIES else {}


# 홈의 "요즘 뜨는 동네" 줄 (우리 별점이 쌓이기 전에도 홈이 비어 보이지 않도록)
TRENDING_AREAS = ['성수동', '망원동', '연남동', '익선동', '을지로', '한남동', '문래동', '서촌']
AREA_CACHE_SECONDS = 6 * 60 * 60  # 카카오 호출을 아끼려고 동네별 결과를 6시간 저장


def trending_areas(category):
    """동네별 카카오 검색 상위 장소. 카카오가 실패한 동네는 건너뛴다"""
    code = category or 'CE7'  # 홈(전체) 탭에서는 카페
    word = {'FD6': '맛집', 'BAR': '술집'}.get(code, '카페')
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


BAYES_WEIGHT = 3  # 평가가 이 정도 쌓이기 전까지는 전체 평균 쪽으로 당겨서 순위를 매긴다


def ranked(places):
    """베이지안 평균 순: (별점 합 + m × 전체 평균) / (평가 수 + m)

    평가 1개짜리 5.0이 평가 50개짜리 4.6보다 위에 오지 않게, 평가가 적을수록 전체 평균 쪽으로 당긴다.
    places 는 with_ratings 로 평가 수가 붙어 있어야 한다.
    """
    overall = float(Review.objects.aggregate(avg=Avg('rating'))['avg'] or 0)
    m = BAYES_WEIGHT
    return places.annotate(
        rank_score=(Cast(Sum('reviews__rating'), FloatField()) + m * overall) / (Cast('review_count', FloatField()) + m)
    ).order_by('-rank_score', '-review_count', 'name')


@api_view(['GET'])
@permission_classes([AllowAny])
def rankings(request):
    """랭킹: ?category=CE7&tag=조용함&area=마포구 → 베이지안 평균 순 상위 30곳 + 고를 수 있는 키워드·동네"""
    reviewed = Place.objects.filter(**category_filter(request), reviews__isnull=False).distinct()
    category = category_filter(request).get('category')
    tags = TAG_OPTIONS[category] if category else sum(TAG_OPTIONS.values(), [])
    # 평가된 장소가 많은 동네 순으로 8곳까지 칩으로 보여준다
    areas = [a for a, _ in Counter(' '.join(addr.split()[1:2]) for addr in reviewed.values_list('address', flat=True)).most_common(8)]

    places = with_ratings(reviewed)
    if (tag := request.query_params.get('tag')) in tags:
        # shortcut: 키워드 필터를 파이썬에서 함 (SQLite 는 JSON 목록 안을 찾는 검색을 못 함), 리뷰가 많아지면 PostgreSQL 의 tags__contains 로
        ids = {place_id for place_id, chosen in Review.objects.values_list('place_id', 'tags') if tag in chosen}
        places = places.filter(pk__in=ids)
    if area := request.query_params.get('area', '').strip()[:20]:
        places = places.filter(address__contains=f' {area} ')
    return Response({'tags': tags, 'areas': areas, 'places': PlaceSerializer(ranked(places)[:30], many=True).data})


@api_view(['GET'])
@permission_classes([AllowAny])
def home(request):
    """홈 화면: 누적 평가 수, 인기 랭킹, 최근 평가된 곳, 동네별 줄 (큰 사진은 고른 동네의 장소)"""
    places = with_ratings(Place.objects.filter(**category_filter(request), reviews__isnull=False).distinct())
    ranking = ranked(places)[:14]
    recent = places.annotate(last_reviewed=Max('reviews__updated_at')).order_by('-last_reviewed')[:14]

    return Response({
        'total_reviews': Review.objects.filter(**{f'place__{k}': v for k, v in category_filter(request).items()}).count(),
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

    wished = with_ratings(Place.objects.filter(wishlisted_by__user=request.user)).order_by('-wishlisted_by__created_at')
    return Response({
        'counts': {
            'reviews': reviews.count(),
            'comments': reviews.exclude(comment='').count(),
            'wishes': request.user.wishlist.count(),
            'cafe': reviews.filter(place__category=Place.Category.CAFE).count(),
            'restaurant': reviews.filter(place__category=Place.Category.RESTAURANT).count(),
            'bar': reviews.filter(place__category=Place.Category.BAR).count(),
            'followers': request.user.followers.count(),
            'following': request.user.following.count(),
        },
        'distribution': distribution,
        'top_rating': top,
        'taste': taste(reviews),
        'recent': [rated_place(r, 'my_rating') for r in reviews.order_by('-updated_at')[:12]],
        'wishlist': PlaceSerializer(wished[:12], many=True).data,
        # 내가 팔로우한 사람들이 최근 남긴 별점
        'feed': [
            rated_place(r, nickname=r.user.nickname, user_id=r.user_id)
            for r in Review.objects.filter(user__followers__follower=request.user).select_related('user').order_by('-updated_at')[:12]
        ],
    })


def rated_place(review, key='rating', **extra):
    """평가 하나 → 장소 정보(평균 별점 포함) + 그 사람이 준 별점"""
    return {**PlaceSerializer(with_ratings(Place.objects.filter(pk=review.place_id)).get()).data, key: str(review.rating), **extra}


def taste(reviews):
    """내 취향 분석: 평균 별점(전체 사용자 평균과 비교), 자주 고른 키워드, 높게 준 세부 분류, 자주 간 동네"""
    rows = list(reviews)
    if not rows:
        return None
    mine = sum(r.rating for r in rows) / len(rows)
    everyone = Review.objects.aggregate(avg=Avg('rating'))['avg']
    count = lambda values, n: [{'name': k, 'count': v} for k, v in Counter(values).most_common(n)]
    return {
        'avg': f'{mine:.1f}',
        'everyone_avg': f'{everyone:.1f}',
        'tags': count((t for r in rows for t in r.tags), 5),
        'details': count((recommend.detail_of(r.place) for r in rows if r.rating >= 4), 3),
        'areas': count((recommend.area_of(r.place) for r in rows), 3),
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def recommendations(request):
    """좋아할 만한 곳: ?category=CE7&area=마포구 → 내가 안 가본 곳을 예상 별점 높은 순으로 (데이터가 적으면 콜드 스타트)"""
    candidates = with_ratings(
        Place.objects.filter(**category_filter(request), reviews__isnull=False).exclude(reviews__user=request.user).distinct()
    )
    if area := request.query_params.get('area', '').strip()[:20]:
        candidates = candidates.filter(address__contains=f' {area} ')
    return Response([
        {**PlaceSerializer(p).data, 'predicted_rating': f'{guess:.1f}' if guess is not None else None}
        for p, guess in recommend.recommend(request.user, candidates)
    ])


@api_view(['GET'])
@permission_classes([AllowAny])
def user_profile(request, user_id):
    """다른 사용자 프로필: 닉네임, 평가·팔로워·팔로잉 수, 최근 평가한 곳 (아이디는 공개하지 않는다)"""
    person = get_object_or_404(User, pk=user_id, is_active=True)
    reviews = person.reviews.order_by('-updated_at')
    return Response({
        'id': person.id,
        'nickname': person.nickname,
        'counts': {
            'reviews': reviews.count(),
            'followers': person.followers.count(),
            'following': person.following.count(),
        },
        'is_following': request.user.is_authenticated and person.followers.filter(follower=request.user).exists(),
        # 가장 자주 고른 키워드 하나 (프로필 소개 줄)
        'top_tag': next(iter(Counter(t for tags in reviews.values_list('tags', flat=True) for t in tags).most_common(1)), (None,))[0],
        'reviews': [rated_place(r) for r in reviews[:24]],
    })


@api_view(['POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def follow(request, user_id):
    """팔로우(POST) / 언팔로우(DELETE)"""
    person = get_object_or_404(User, pk=user_id, is_active=True)
    if person == request.user:
        return Response({'detail': '나를 팔로우할 수는 없어요.'}, status=status.HTTP_400_BAD_REQUEST)
    if request.method == 'POST':
        Follow.objects.get_or_create(follower=request.user, following=person)
    else:
        Follow.objects.filter(follower=request.user, following=person).delete()
    return Response({'is_following': request.method == 'POST', 'followers': person.followers.count()})


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


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def my_review_photos(request, place_id):
    """내 리뷰에 사진 올리기 (form-data 의 photos, 여러 장). 리뷰당 최대 3장"""
    review = Review.objects.filter(user=request.user, place_id=place_id).first()
    if review is None:
        return Response({'detail': '별점을 먼저 남겨 주세요.'}, status=status.HTTP_400_BAD_REQUEST)
    files = request.FILES.getlist('photos')
    if not files:
        return Response({'detail': '사진을 골라 주세요.'}, status=status.HTTP_400_BAD_REQUEST)
    if review.photos.count() + len(files) > MAX_PHOTOS:
        return Response({'detail': f'사진은 {MAX_PHOTOS}장까지 올릴 수 있어요.'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        processed = [photos.process(f) for f in files]  # 하나라도 문제면 아무것도 저장하지 않는다
    except photos.PhotoError as e:
        return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    for content in processed:
        ReviewPhoto.objects.create(review=review, image=content)
    return Response({'my_review': MyReviewSerializer(review).data})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def my_review_photo(request, place_id, photo_id):
    """내 리뷰 사진 하나 지우기 (남의 사진은 404)"""
    photo = get_object_or_404(ReviewPhoto, pk=photo_id, review__user=request.user, review__place_id=place_id)
    review = photo.review
    photo.image.delete(save=False)
    photo.delete()
    return Response({'my_review': MyReviewSerializer(review).data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle])
def my_review_receipt(request, place_id):
    """영수증 인증: form-data 의 receipt(사진) → 가게 이름·결제일 확인 → 내 리뷰에 인증 표시, 방문일을 결제일로

    실패하면 400 과 함께 무엇이 맞고 틀렸는지(check)를 돌려준다. 영수증 사진은 저장하지 않는다.
    """
    place = get_object_or_404(Place, pk=place_id)
    review = Review.objects.filter(user=request.user, place=place).first()
    if review is None:
        return Response({'detail': '별점을 먼저 남겨 주세요.'}, status=status.HTTP_400_BAD_REQUEST)
    if review.receipt_verified_at:
        return Response({'detail': '이미 영수증 인증을 받은 리뷰예요.'}, status=status.HTTP_400_BAD_REQUEST)
    upload = request.FILES.get('receipt')
    if not upload:
        return Response({'detail': '영수증 사진을 골라 주세요.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        text = receipts.read_text(receipts.to_jpeg(upload))
    except receipts.ReceiptError as e:
        return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    paid = receipts.find_paid_date(text, timezone.localdate())
    check = {'store': receipts.matches_place(text, place), 'date': paid}
    if not check['store']:
        reason = f'영수증에서 "{place.name}"을(를) 찾지 못했어요. 가게 이름이 잘 보이게 다시 찍어 주세요.'
    elif not paid:
        reason = f'최근 {receipts.MAX_AGE_DAYS}일 안의 결제일을 찾지 못했어요. 날짜가 잘 보이게 다시 찍어 주세요.'
    else:
        reason = None
    if reason:
        return Response({'detail': reason, 'check': check}, status=status.HTTP_400_BAD_REQUEST)

    review.receipt_fingerprint = receipts.fingerprint(text, place.id, paid)
    review.receipt_verified_at = timezone.now()
    review.visited_on = paid
    try:
        review.save(update_fields=['receipt_fingerprint', 'receipt_verified_at', 'visited_on'])
    except IntegrityError:  # 같은 영수증 지문이 이미 있음
        return Response({'detail': '이미 다른 리뷰 인증에 쓰인 영수증이에요.', 'check': check}, status=status.HTTP_400_BAD_REQUEST)
    return Response({'check': check, 'my_review': MyReviewSerializer(review).data})


def collections_qs():
    """컬렉션 + 담긴 장소 수 + 좋아요 수 (카드 사진용 장소는 한 번에 불러 둔다)"""
    return Collection.objects.select_related('user').prefetch_related(
        Prefetch('items', queryset=CollectionItem.objects.select_related('place'))
    ).annotate(place_count=Count('items', distinct=True), like_count=Count('likes', distinct=True))


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticatedOrReadOnly])
def collections(request):
    """컬렉션 둘러보기: ?q=카공&user=3&sort=popular|recent / 만들기(POST {title, description})"""
    ctx = {'request': request}
    if request.method == 'POST':
        if request.user.collections.count() >= MAX_COLLECTIONS:
            return Response({'detail': f'컬렉션은 {MAX_COLLECTIONS}개까지 만들 수 있어요.'}, status=status.HTTP_400_BAD_REQUEST)
        serializer = CollectionSerializer(data=request.data, context=ctx)
        serializer.is_valid(raise_exception=True)
        created = serializer.save(user=request.user)
        return Response(CollectionSerializer(collections_qs().get(pk=created.pk), context=ctx).data, status=status.HTTP_201_CREATED)

    qs = collections_qs()
    if q := request.query_params.get('q', '').strip()[:40]:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))
    owner = request.query_params.get('user', '')
    if owner.isdigit():
        qs = qs.filter(user_id=int(owner))
    # 빈 컬렉션은 만든 사람 본인에게만 보인다
    if not (owner.isdigit() and int(owner) == request.user.id):
        qs = qs.filter(place_count__gt=0)
    order = ['-like_count', '-updated_at'] if request.query_params.get('sort') == 'popular' else ['-updated_at']
    return Response(CollectionSerializer(qs.order_by(*order)[:30], many=True, context=ctx).data)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticatedOrReadOnly])
def collection_detail(request, collection_id):
    """컬렉션 하나: 담긴 장소(담은 순서) / 제목·소개 고치기(PATCH) / 지우기(DELETE). 고치고 지우기는 만든 사람만"""
    ctx = {'request': request}
    collection = get_object_or_404(collections_qs(), pk=collection_id)
    if request.method != 'GET' and collection.user_id != request.user.id:
        return Response({'detail': '내 컬렉션만 고칠 수 있어요.'}, status=status.HTTP_403_FORBIDDEN)
    if request.method == 'DELETE':
        collection.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    if request.method == 'PATCH':
        serializer = CollectionSerializer(collection, data=request.data, partial=True, context=ctx)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        collection = collections_qs().get(pk=collection_id)

    ids = list(collection.items.values_list('place_id', flat=True))
    fill_thumbnails(Place.objects.filter(pk__in=ids, thumbnail_checked_at__isnull=True))
    by_id = {p.id: p for p in with_ratings(Place.objects.filter(pk__in=ids))}
    return Response({
        **CollectionSerializer(collection, context=ctx).data,
        'places': PlaceSerializer([by_id[i] for i in ids], many=True).data,
    })


@api_view(['POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def collection_place(request, collection_id, place_id):
    """내 컬렉션에 장소 담기(POST) / 빼기(DELETE). 남의 컬렉션은 404"""
    collection = get_object_or_404(Collection, pk=collection_id, user=request.user)
    place = get_object_or_404(Place, pk=place_id)
    if request.method == 'POST':
        if not collection.items.filter(place=place).exists() and collection.items.count() >= MAX_COLLECTION_PLACES:
            return Response({'detail': f'컬렉션 하나에 {MAX_COLLECTION_PLACES}곳까지 담을 수 있어요.'}, status=status.HTTP_400_BAD_REQUEST)
        CollectionItem.objects.get_or_create(collection=collection, place=place)
    else:
        collection.items.filter(place=place).delete()
    collection.save(update_fields=['updated_at'])
    return Response({'in_collection': request.method == 'POST', 'place_count': collection.items.count()})


@api_view(['POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def collection_like(request, collection_id):
    """컬렉션 좋아요(POST) / 취소(DELETE)"""
    collection = get_object_or_404(Collection, pk=collection_id)
    if request.method == 'POST':
        CollectionLike.objects.get_or_create(user=request.user, collection=collection)
    else:
        CollectionLike.objects.filter(user=request.user, collection=collection).delete()
    return Response({'liked': request.method == 'POST', 'like_count': collection.likes.count()})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_collections(request):
    """장소 상세의 "컬렉션에 담기" 목록: 내 컬렉션 + ?place= 장소가 이미 담겼는지"""
    place = request.query_params.get('place', '')
    rows = request.user.collections.annotate(place_count=Count('items'))
    has = set(CollectionItem.objects.filter(collection__user=request.user, place_id=place).values_list('collection_id', flat=True)) if place.isdigit() else set()
    return Response([{'id': c.id, 'title': c.title, 'place_count': c.place_count, 'has_place': c.id in has} for c in rows])
