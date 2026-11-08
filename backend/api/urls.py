from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from . import views
from .serializers import SafeTokenRefreshSerializer

urlpatterns = [
    path('hello/', views.hello),
    path('auth/signup/', views.signup),
    # 로그인: 아이디·비밀번호 → access / refresh 토큰
    path('auth/login/', TokenObtainPairView.as_view()),
    # access 토큰이 만료되면 refresh 토큰으로 새로 받는다
    path('auth/refresh/', TokenRefreshView.as_view(serializer_class=SafeTokenRefreshSerializer)),
    path('auth/me/', views.me),
    path('places/search/', views.search_places),
]
