"""취향 기반 추천: 사용자 기반 협업 필터링 (README "추천 알고리즘")

1. 나와 같이 평가한 장소가 MIN_COMMON 곳 이상인 사람끼리, 각자의 평균을 뺀 별점으로 피어슨 유사도를 구한다
2. 내가 안 가본 장소마다 비슷한 사람들의 (별점 - 그 사람 평균)을 유사도로 가중 평균해 내 평균에 더한다 → 예상 별점
3. 평가가 MIN_REVIEWS 개 미만이거나 비슷한 사람이 없으면, 내가 높게 준 세부 분류·자주 가는 동네·평균 별점 순으로 대신 고른다
"""
from collections import Counter, defaultdict
from math import sqrt

from .models import Review

MIN_COMMON = 3  # 같이 평가한 장소가 이만큼은 있어야 취향을 비교한다
MIN_REVIEWS = 5  # 내 평가가 이보다 적으면 예상 별점을 내지 않는다 (콜드 스타트)
NEIGHBORS = 30  # 예상 별점에 쓰는 가장 비슷한 사람 수
LIKE_FROM = 3.5  # 예상 별점이 이 이상이어야 "좋아할 만한 곳"에 넣는다


def detail_of(place):
    """"음식점 > 카페 > 디저트카페" → "디저트카페\""""
    return place.category_detail.split(' > ')[-1]


def area_of(place):
    """"서울 마포구 망원로 1" → "마포구\""""
    return ' '.join(place.address.split()[1:2])


def rating_table():
    """{사용자 id: {장소 id: 별점}}"""
    # shortcut: 요청마다 전체 리뷰를 읽음, 리뷰가 수만 개가 되면 하루 한 번 미리 계산해 캐시하거나 행렬 분해로 바꾼다
    table = defaultdict(dict)
    for user_id, place_id, rating in Review.objects.values_list('user_id', 'place_id', 'rating'):
        table[user_id][place_id] = float(rating)
    return table


def similarity(a, b, mean_a, mean_b):
    """두 사람의 취향 유사도 (-1 ~ 1). 같이 평가한 곳이 적거나 비교할 수 없으면 None"""
    common = a.keys() & b.keys()
    if len(common) < MIN_COMMON:
        return None
    da = [a[p] - mean_a for p in common]
    db = [b[p] - mean_b for p in common]
    den = sqrt(sum(x * x for x in da)) * sqrt(sum(y * y for y in db))
    return sum(x * y for x, y in zip(da, db)) / den if den else None


def predict(user, place_ids=None):
    """내가 안 가본 장소의 예상 별점 {장소 id: 4.3}. place_ids 를 주면 그 장소만 계산한다"""
    table = rating_table()
    mine = table.get(user.id, {})
    if len(mine) < MIN_REVIEWS:
        return {}
    means = {u: sum(r.values()) / len(r) for u, r in table.items()}

    neighbors = []
    for other, theirs in table.items():
        if other != user.id:
            sim = similarity(mine, theirs, means[user.id], means[other])
            if sim and sim > 0:  # 취향이 반대인 사람은 쓰지 않는다
                neighbors.append((sim, other))
    neighbors = sorted(neighbors, reverse=True)[:NEIGHBORS]

    num, den = defaultdict(float), defaultdict(float)
    for sim, other in neighbors:
        for place_id, rating in table[other].items():
            if place_id in mine or (place_ids is not None and place_id not in place_ids):
                continue
            num[place_id] += sim * (rating - means[other])
            den[place_id] += sim
    return {p: round(min(5.0, max(0.5, means[user.id] + num[p] / den[p])), 1) for p in num}


def cold_start(user, places):
    """예상 별점이 없을 때: 내가 4점 이상 준 세부 분류 → 내가 자주 간 동네 → 평균 별점 높은 순"""
    reviews = list(user.reviews.select_related('place'))
    liked = Counter(detail_of(r.place) for r in reviews if r.rating >= 4)
    areas = Counter(area_of(r.place) for r in reviews)
    return sorted(places, key=lambda p: (-liked[detail_of(p)], -areas[area_of(p)], -(p.avg_rating or 0), -p.review_count))


def recommend(user, candidates, limit=12):
    """candidates(평균 별점이 붙은 장소 queryset) 중 좋아할 만한 곳 [(장소, 예상 별점 또는 None)]"""
    predicted = predict(user)
    liked = [p for p, r in predicted.items() if r >= LIKE_FROM]
    picks = sorted(candidates.filter(pk__in=liked), key=lambda p: -predicted[p.id])[:limit]
    # 예상 별점이 낮은 곳은 콜드 스타트로도 다시 넣지 않는다
    # shortcut: 콜드 스타트 후보는 평균 별점 상위 100곳에서만 고름, 장소가 많아지면 동네·분류로 먼저 거른다
    rest = cold_start(user, candidates.exclude(pk__in=predicted).order_by('-avg_rating', '-review_count')[:100])
    return [(p, predicted[p.id]) for p in picks] + [(p, None) for p in rest[: limit - len(picks)]]
