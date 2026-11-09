from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Place, Review, ReviewPhoto, User, Wishlist


@admin.register(User)
class CafepediaUserAdmin(UserAdmin):
    list_display = ['username', 'nickname', 'email', 'is_staff']
    # 기본 사용자 화면에 닉네임 칸을 추가
    fieldsets = UserAdmin.fieldsets + (('카페피디아', {'fields': ['nickname']}),)
    add_fieldsets = UserAdmin.add_fieldsets + (('카페피디아', {'fields': ['nickname']}),)


@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'category_detail', 'address', 'created_at']
    list_filter = ['category']
    search_fields = ['name', 'address']


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['place', 'user', 'rating', 'comment', 'visited_on']
    list_filter = ['rating', 'place__category']
    search_fields = ['place__name', 'user__nickname', 'comment']


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ['user', 'place', 'created_at']


@admin.register(ReviewPhoto)
class ReviewPhotoAdmin(admin.ModelAdmin):
    list_display = ['review', 'image', 'created_at']
