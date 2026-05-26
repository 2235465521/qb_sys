"""
users.urls.auth_urls — 认证路由
POST /api/auth/login/   — 登录获取 JWT
POST /api/auth/refresh/ — 刷新 Token
POST /api/auth/logout/  — 登出（清除客户端 Token）
"""

from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from users.views import UserInfoView, UserRegisterView

urlpatterns = [
    path('login/', TokenObtainPairView.as_view(), name='auth-login'),
    path('register/', UserRegisterView.as_view(), name='auth-register'),
    path('refresh/', TokenRefreshView.as_view(), name='auth-refresh'),
    path('me/', UserInfoView.as_view(), name='auth-me'),
]
