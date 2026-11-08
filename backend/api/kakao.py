"""카카오 로컬 API 호출. 키가 브라우저에 노출되지 않도록 반드시 서버에서만 부른다."""

import json
import logging
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

AUTHORIZE_URL = 'https://kauth.kakao.com/oauth/authorize'
TOKEN_URL = 'https://kauth.kakao.com/oauth/token'
USER_URL = 'https://kapi.kakao.com/v2/user/me'

logger = logging.getLogger(__name__)

SEARCH_URL = 'https://dapi.kakao.com/v2/local/search/keyword.json'
# 카페피디아가 다루는 분류 (카카오 카테고리 그룹 코드)
ALLOWED_CATEGORIES = {'CE7', 'FD6'}


class KakaoError(Exception):
    """카카오 API 호출 실패 (키 없음, 권한 없음, 네트워크 오류 등)"""


CATEGORY_URL = 'https://dapi.kakao.com/v2/local/search/category.json'
IMAGE_URL = 'https://dapi.kakao.com/v2/search/image'


def _get(url, params):
    """카카오 API GET 호출 → documents 목록"""
    key = os.environ.get('KAKAO_REST_API_KEY')
    if not key:
        raise KakaoError('KAKAO_REST_API_KEY 가 .env 에 없어요.')
    req = Request(f'{url}?{urlencode(params)}', headers={'Authorization': f'KakaoAK {key}'})
    try:
        with urlopen(req, timeout=5) as res:
            return json.load(res)['documents']
    except HTTPError as e:
        raise KakaoError(f'카카오 API 오류 {e.code}') from e
    except (URLError, TimeoutError) as e:
        raise KakaoError('카카오 API에 연결하지 못했어요.') from e


def nearby_places(lat, lng, category=None, radius=1000):
    """좌표 주변 카페·식당을 가까운 순으로. 각 document 에 distance(미터, 문자열)가 들어 있다.

    카카오 카테고리 검색은 분류를 하나만 받아서, 전체면 카페·식당을 각각 불러 합친다.
    """
    documents = []
    for code in [category] if category else sorted(ALLOWED_CATEGORIES):
        documents += _get(CATEGORY_URL, {
            'category_group_code': code, 'x': lng, 'y': lat, 'radius': radius, 'sort': 'distance', 'size': 15,
        })
    return sorted(documents, key=lambda d: int(d['distance'] or 0))


def search_places(query, category=None):
    """키워드로 카페·식당을 검색해 카카오 응답의 documents 목록을 돌려준다.

    category 가 없으면 전체를 검색한 뒤 카페·식당만 남긴다.
    """
    params = {'query': query, 'size': 15}
    if category:
        params['category_group_code'] = category
    documents = _get(SEARCH_URL, params)
    return [d for d in documents if d['category_group_code'] in ALLOWED_CATEGORIES]


def image_search(query):
    """다음(카카오) 이미지 검색에서 가장 정확한 결과 1개 → (썸네일 주소, 출처 글 주소) 또는 None"""
    documents = _get(IMAGE_URL, {'query': query, 'sort': 'accuracy', 'size': 1})
    return (documents[0]['thumbnail_url'], documents[0]['doc_url']) if documents else None


def login_url(redirect_uri, state):
    """카카오 로그인 화면 주소. client_id 는 REST API 키 (카카오 방식)"""
    return f"{AUTHORIZE_URL}?{urlencode({'client_id': os.environ.get('KAKAO_REST_API_KEY', ''), 'redirect_uri': redirect_uri, 'response_type': 'code', 'state': state})}"


def login_user(code, redirect_uri):
    """카카오가 준 1회용 인가 코드 → 카카오 토큰 → 카카오 회원 정보 (회원 번호, 닉네임)"""
    key = os.environ.get('KAKAO_REST_API_KEY')
    if not key:
        raise KakaoError('KAKAO_REST_API_KEY 가 .env 에 없어요.')
    form = {'grant_type': 'authorization_code', 'client_id': key, 'redirect_uri': redirect_uri, 'code': code}
    # 카카오 콘솔에서 Client Secret 을 켰다면 함께 보내야 한다
    if secret := os.environ.get('KAKAO_CLIENT_SECRET'):
        form['client_secret'] = secret
    try:
        with urlopen(Request(TOKEN_URL, data=urlencode(form).encode()), timeout=5) as res:
            access = json.load(res)['access_token']
        with urlopen(Request(USER_URL, headers={'Authorization': f'Bearer {access}'}), timeout=5) as res:
            me = json.load(res)
    except HTTPError as e:
        # 카카오가 알려준 실패 이유(error_code, 설명)를 서버 로그에 남긴다. 키·코드 값은 남기지 않는다
        try:
            body = json.load(e)
        except ValueError:
            body = {}
        reason = f"{e.code} {body.get('error_code', '')} {body.get('error', '')} {body.get('error_description', '')}".strip()
        logger.warning('카카오 로그인 실패: %s', reason)
        raise KakaoError(f'카카오 로그인 오류 {reason}') from e
    except (URLError, TimeoutError) as e:
        raise KakaoError('카카오에 연결하지 못했어요.') from e
    nickname = me.get('kakao_account', {}).get('profile', {}).get('nickname') or me.get('properties', {}).get('nickname')
    return str(me['id']), nickname
