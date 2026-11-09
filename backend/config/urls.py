from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    # 모든 API 주소는 /api/ 로 시작한다
    path('api/', include('api.urls')),
]

# 개발 중에만 Django 가 올린 사진 파일을 직접 보여준다
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
