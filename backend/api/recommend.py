"""취향 기반 추천: 기준선 + 이웃 (KNNBaseline, README "이렇게 동작해요")

1. 기준선 = 전체 평균 μ + 이 사람의 성향 b_u + 이 장소의 수준 b_i
   - 평가가 적은 장소·사람의 b 는 0 쪽으로 당긴다 (랭킹의 베이지안 평균과 같은 원리)
2. 별점에서 기준선을 뺀 나머지(잔차)로 피어슨 유사도를 구하고, 같이 평가한 곳이 적으면 n/(n+SIM_SHRINK) 로 깎는다
3. 예상 별점 = 기준선 + 비슷한 사람들의 잔차를 유사도로 가중 평균한 값. 비슷한 사람이 안 가본 곳은 기준선만
4. 평가가 MIN_REVIEWS 개 미만이면 예상 별점 대신 세부 분류·동네·평균 별점으로 고른다 (콜드 스타트)
"""
from collections import Counter, defaultdict
from math import sqrt

from .models import Review

MIN_COMMON = 3  # 같이 평가한 장소가 이만큼은 있어야 취향을 비교한다
MIN_REVIEWS = 5  # 내 평가가 이보다 적으면 예상 별점을 내지 않는다 (콜드 스타트)
NEIGHBORS = 30  # 예상 별점에 쓰는 가장 비슷한 사람 수
LIKE_FROM = 3.5  # 예상 별점이 이 이상이어야 "좋아할 만한 곳"에 넣는다
PLACE_SHRINK = 3  # 장소 수준 b_i 를 0 쪽으로 당기는 세기 (랭킹 BAYES_WEIGHT 와 같은 값)
USER_SHRINK = 5  # 사람 성향 b_u 를 0 쪽으로 당기는 세기
SIM_SHRINK = 10  # 같이 평가한 곳이 n 곳이면 유사도에 n/(n+10) 을 곱한다


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


def clip(rating):
    return min(5.0, max(0.5, rating))


def baseline(table):
    """(μ, {사용자: b_u}, {장소: b_i}). 장소 수준을 먼저 구하고, 그걸 뺀 나머지로 사람 성향을 구한다"""
    ratings = [r for rows in table.values() for r in rows.values()]
    mu = sum(ratings) / len(ratings) if ratings else 0.0
    diffs = defaultdict(list)
    for rows in table.values():
        for place, r in rows.items():
            diffs[place].append(r - mu)
    b_place = {p: sum(d) / (PLACE_SHRINK + len(d)) for p, d in diffs.items()}
    b_user = {u: sum(r - mu - b_place[p] for p, r in rows.items()) / (USER_SHRINK + len(rows)) for u, rows in table.items()}
    return mu, b_user, b_place


def similarity(a, b):
    """두 사람의 잔차 {장소: 별점 - 기준선} 로 구한 취향 유사도. 같이 평가한 곳이 적거나 비교할 수 없으면 None"""
    common = a.keys() & b.keys()
    n = len(common)
    if n < MIN_COMMON:
        return None
    den = sqrt(sum(a[p] ** 2 for p in common)) * sqrt(sum(b[p] ** 2 for p in common))
    return sum(a[p] * b[p] for p in common) / den * n / (n + SIM_SHRINK) if den else None


def predict_from(table, user_id, place_ids=None):
    """table 에서 user_id 가 안 가본 장소(평가가 1개 이상 있는 곳)의 예상 별점 {장소 id: 4.27}"""
    mine = table.get(user_id, {})
    if len(mine) < MIN_REVIEWS:
        return {}
    mu, b_user, b_place = baseline(table)
    residual = {u: {p: r - (mu + b_user[u] + b_place[p]) for p, r in rows.items()} for u, rows in table.items()}

    neighbors = []
    for other in table:
        if other != user_id:
            sim = similarity(residual[user_id], residual[other])
            if sim and sim > 0:  # 취향이 반대인 사람은 쓰지 않는다
                neighbors.append((sim, other))
    neighbors = sorted(neighbors, reverse=True)[:NEIGHBORS]

    targets = b_place.keys() - mine.keys()
    if place_ids is not None:
        targets &= set(place_ids)
    num, den = defaultdict(float), defaultdict(float)
    for sim, other in neighbors:
        for place, d in residual[other].items():
            if place in targets:
                num[place] += sim * d
                den[place] += sim
    return {p: clip(mu + b_user[user_id] + b_place[p] + (num[p] / den[p] if den[p] else 0)) for p in targets}


def predict(user, place_ids=None):
    """내가 안 가본 장소의 예상 별점 {장소 id: 4.3}. place_ids 를 주면 그 장소만 계산한다"""
    return {p: round(r, 1) for p, r in predict_from(rating_table(), user.id, place_ids).items()}


def evaluate(table):
    """평가를 하나씩 가리고 맞혀 보는 leave-one-out RMSE (낮을수록 정확). {방식: (RMSE, 맞혀 본 수)}"""
    # shortcut: 평가마다 기준선을 다시 계산해 O(리뷰 수²), 리뷰가 수만 개가 되면 일부만 무작위로 가린다
    errors = defaultdict(list)
    for user, rows in table.items():
        if len(rows) <= MIN_REVIEWS:  # 하나를 가려도 예상 별점을 낼 수 있는 사람만
            continue
        for place, actual in list(rows.items()):
            del rows[place]
            mu, b_user, b_place = baseline(table)
            base = clip(mu + b_user[user] + b_place.get(place, 0))
            errors['전체 평균'].append(mu - actual)
            errors['기준선'].append(base - actual)
            errors['기준선 + 이웃'].append(predict_from(table, user, {place}).get(place, base) - actual)
            rows[place] = actual
    return {name: (sqrt(sum(e * e for e in errs) / len(errs)), len(errs)) for name, errs in errors.items()}


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
