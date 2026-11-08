"""카카오 로컬 API 호출. 키가 브라우저에 노출되지 않도록 반드시 서버에서만 부른다."""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SEARCH_URL = 'https://dapi.kakao.com/v2/local/search/keyword.json'
# 카페피디아가 다루는 분류 (카카오 카테고리 그룹 코드)
ALLOWED_CATEGORIES = {'CE7', 'FD6'}


class KakaoError(Exception):
    """카카오 API 호출 실패 (키 없음, 권한 없음, 네트워크 오류 등)"""


def search_places(query, category=None):
    """키워드로 카페·식당을 검색해 카카오 응답의 documents 목록을 돌려준다.

    category 가 없으면 전체를 검색한 뒤 카페·식당만 남긴다.
    """
    key = os.environ.get('KAKAO_REST_API_KEY')
    if not key:
        raise KakaoError('KAKAO_REST_API_KEY 가 .env 에 없어요.')

    params = {'query': query, 'size': 15}
    if category:
        params['category_group_code'] = category
    req = Request(f'{SEARCH_URL}?{urlencode(params)}', headers={'Authorization': f'KakaoAK {key}'})

    try:
        with urlopen(req, timeout=5) as res:
            documents = json.load(res)['documents']
    except HTTPError as e:
        raise KakaoError(f'카카오 API 오류 {e.code}') from e
    except (URLError, TimeoutError) as e:
        raise KakaoError('카카오 API에 연결하지 못했어요.') from e

    return [d for d in documents if d['category_group_code'] in ALLOWED_CATEGORIES]
