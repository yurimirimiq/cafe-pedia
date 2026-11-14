from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

urlpatterns = [
    path('admin/', admin.site.urls),
    # 모든 API 주소는 /api/ 로 시작한다
    path('api/', include('api.urls')),
    # 리뷰 사진. shortcut: Django 가 서버 디스크의 파일을 직접 내보낸다. Render 디스크는 재배포·재시작 때 지워져
    # 올린 사진이 사라지므로, 사진을 오래 보관하려면 Cloudinary·S3 같은 이미지 저장소로 옮긴다
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]
