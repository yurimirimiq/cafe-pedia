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
    path('auth/kakao/url/', views.kakao_login_url),
    path('auth/kakao/', views.kakao_login),
    path('places/search/', views.search_places),
    path('places/nearby/', views.nearby_places),
    path('places/<int:place_id>/', views.place_detail),
    path('places/<int:place_id>/review/', views.my_review),
    path('places/<int:place_id>/review/photos/', views.my_review_photos),
    path('places/<int:place_id>/review/receipt/', views.my_review_receipt),
    path('places/<int:place_id>/review/photos/<int:photo_id>/', views.my_review_photo),
    path('places/<int:place_id>/wish/', views.wish),
    path('home/', views.home),
    path('rankings/', views.rankings),
    path('me/calendar/', views.my_calendar),
    path('me/summary/', views.my_summary),
    path('recommendations/', views.recommendations),
    path('users/<int:user_id>/', views.user_profile),
    path('users/<int:user_id>/follow/', views.follow),
]
