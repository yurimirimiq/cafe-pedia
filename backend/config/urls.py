from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    # 모든 API 주소는 /api/ 로 시작한다
    path('api/', include('api.urls')),
]
