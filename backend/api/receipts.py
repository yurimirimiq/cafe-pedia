"""영수증 인증: 사진 → 글자 읽기(OCR) → 가게 이름·결제일 확인 → 재사용 막는 지문

영수증 사진은 메모리에서만 다루고 파일로 저장하지 않는다.
"""

import base64
import hashlib
import json
import logging
import os
import re
import time
import uuid
from datetime import date, timedelta
from io import BytesIO
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from PIL import Image, ImageOps, UnidentifiedImageError

logger = logging.getLogger(__name__)

MAX_UPLOAD_MB = 10
MAX_AGE_DAYS = 90  # 이보다 오래된 영수증은 받지 않는다


class ReceiptError(ValueError):
    """사용자에게 그대로 보여줄 실패 이유"""


def to_jpeg(upload):
    """업로드 파일 → OCR 에 보낼 JPEG 바이트 (회전 바로잡고 크기 줄임). 이미지가 아니면 ReceiptError"""
    if upload.size > MAX_UPLOAD_MB * 1024 * 1024:
        raise ReceiptError(f'사진은 {MAX_UPLOAD_MB}MB 이하만 올릴 수 있어요.')
    try:
        img = Image.open(upload)
        img.load()
    except (UnidentifiedImageError, OSError):
        raise ReceiptError('이미지 파일만 올릴 수 있어요.')
    img = ImageOps.exif_transpose(img).convert('RGB')
    img.thumbnail((2000, 2000))
    out = BytesIO()
    img.save(out, 'JPEG', quality=90)
    return out.getvalue()


def _texts(node):
    """OCR 응답(JSON) 어디에 있든 inferText 값을 순서대로 모은다 (일반 OCR·영수증 특화 응답 모두)"""
    if isinstance(node, dict):
        if isinstance(node.get('inferText'), str):
            yield node['inferText']
        for v in node.values():
            yield from _texts(v)
    elif isinstance(node, list):
        for v in node:
            yield from _texts(v)


def read_text(jpeg):
    """네이버 CLOVA OCR 로 영수증 글자 읽기 → 한 덩어리 문자열"""
    url, secret = os.environ.get('CLOVA_OCR_URL'), os.environ.get('CLOVA_OCR_SECRET')
    if not url or not secret:
        raise ReceiptError('영수증 인증을 아직 준비 중이에요.')  # 서버 설정(.env)이 없음
    body = {
        'version': 'V2',
        'requestId': str(uuid.uuid4()),
        'timestamp': int(time.time() * 1000),
        'images': [{'format': 'jpg', 'name': 'receipt', 'data': base64.b64encode(jpeg).decode()}],
    }
    req = Request(url, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json', 'X-OCR-SECRET': secret})
    try:
        with urlopen(req, timeout=15) as res:
            return ' '.join(_texts(json.load(res)))
    except HTTPError as e:
        logger.warning('영수증 OCR 실패: %s', e.code)
        raise ReceiptError('영수증을 읽지 못했어요. 잠시 후 다시 시도해 주세요.') from e
    except (URLError, TimeoutError) as e:
        raise ReceiptError('영수증을 읽지 못했어요. 잠시 후 다시 시도해 주세요.') from e


def _squash(s):
    """비교용: 공백·기호를 빼고 소문자로 ("카페 온기(성수점)" → "카페온기성수점")"""
    return re.sub(r'[^0-9a-z가-힣]', '', s.lower())


DATE_PATTERNS = [
    r'(20\d{2})\s*[-./년]\s*(\d{1,2})\s*[-./월]\s*(\d{1,2})',  # 2026-11-07, 2026.11.07, 2026년 11월 7일
    r'(?<!\d)(\d{2})[-./](\d{1,2})[-./](\d{1,2})(?!\d)',       # 26.11.07
]


def find_paid_date(text, today):
    """영수증 속 날짜 중 '오늘 이전, 90일 이내'인 가장 최근 날짜. 없으면 None"""
    found = []
    for pattern in DATE_PATTERNS:
        for y, m, d in re.findall(pattern, text):
            year = int(y) if len(y) == 4 else 2000 + int(y)
            try:
                found.append(date(year, int(m), int(d)))
            except ValueError:
                continue
    valid = [d for d in found if today - timedelta(days=MAX_AGE_DAYS) <= d <= today]
    return max(valid) if valid else None


def name_candidates(place_name):
    """가게 이름에서 영수증에 찍힐 법한 형태들: "카페 온기 성수점" → 카페온기성수점, 카페온기, 온기"""
    full = _squash(place_name)
    core = _squash(re.sub(r'\S+점$', '', place_name.strip()))  # 지점명 빼기
    bare = re.sub(r'^(카페|cafe)', '', core)  # 앞의 "카페" 빼기
    return [c for c in dict.fromkeys([full, core, bare]) if len(c) >= 2]


def matches_place(text, place):
    """영수증에 이 가게 이름이 있거나, 도로명 주소(길 이름 + 번지)가 있으면 같은 가게로 본다"""
    squashed = _squash(text)
    if any(c in squashed for c in name_candidates(place.name)):
        return True
    street = place.address.split()[-2:]  # "서울 성동구 연무장길 12" → ["연무장길", "12"]
    return len(street) == 2 and _squash(''.join(street)) in squashed


def fingerprint(text, place_id, paid):
    """같은 영수증을 다른 사람·다른 리뷰가 다시 쓰지 못하게 하는 지문 (원문은 저장하지 않고 해시만)"""
    approval = re.search(r'(승인\s*번호|영수증\s*번호|거래\s*번호)\D{0,3}(\d{4,})', text)
    if approval:
        key = f'{place_id}:approval:{approval.group(2)}'
    else:
        # 승인번호를 못 읽었으면 날짜 + 금액들 + 시각으로 대신한다
        amounts = sorted(set(re.findall(r'\d{1,3}(?:,\d{3})+', text)))
        times = sorted(set(re.findall(r'(?<!\d)\d{1,2}:\d{2}(?::\d{2})?', text)))
        key = f'{place_id}:{paid}:{amounts}:{times}'
    return hashlib.sha256(key.encode()).hexdigest()
