"""리뷰 사진 처리: 진짜 이미지인지 확인 → 회전 바로잡기 → 크기 줄이기 → 위치 정보 없는 JPEG"""

from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD_MB = 10
MAX_SIDE = 1600  # 긴 변 기준 픽셀


class PhotoError(ValueError):
    pass


def process(upload):
    """업로드 파일 → 저장할 ContentFile. 문제가 있으면 PhotoError(사용자에게 보여줄 문장)"""
    if upload.size > MAX_UPLOAD_MB * 1024 * 1024:
        raise PhotoError(f'사진은 {MAX_UPLOAD_MB}MB 이하만 올릴 수 있어요.')
    try:
        img = Image.open(upload)
        img.load()
    except (UnidentifiedImageError, OSError):
        raise PhotoError('이미지 파일만 올릴 수 있어요.')
    # 휴대폰 사진은 회전 정보가 EXIF 에 따로 있어서, 지우기 전에 실제로 돌려 둔다
    img = ImageOps.exif_transpose(img).convert('RGB')
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    out = BytesIO()
    # EXIF 를 넘기지 않고 다시 저장 → 촬영 위치(GPS) 같은 개인정보가 남지 않는다
    img.save(out, 'JPEG', quality=85, optimize=True)
    return ContentFile(out.getvalue(), name='photo.jpg')
