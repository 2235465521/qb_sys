"""
EMIS 后端主路由
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('django-admin/', admin.site.urls),

    # ── 认证 ──────────────────────────────────────────────
    path('api/auth/', include('users.urls.auth_urls')),

    # ── 后台管理 API ──────────────────────────────────────
    path('api/admin/companies/', include('companies.urls.admin_urls')),
    path('api/admin/dict/', include('companies.urls.dict_urls')),
    path('api/admin/sms-templates/', include('notifications.urls.template_urls')),
    path('api/admin/members/', include('users.urls.member_admin_urls')),
    path('api/admin/standards/', include('standards.urls.admin_urls')),
    path('api/admin/users/', include('users.urls.user_admin_urls')),
    path('api/admin/analysis/trends/', include('standards.urls.trend_urls')),

    # ── 前台模块一：搜企与下载 ────────────────────────────
    path('api/client/search/', include('companies.urls.search_urls')),
    path('api/client/standards/', include('standards.urls.standard_urls')),

    # ── 前台模块二：引用解析统计 ──────────────────────────
    path('api/client/analysis/', include('standards.urls.analysis_urls')),
    path('api/client/analysis/trends/', include('standards.urls.trend_urls')),

    # ── 前台模块三：会员与通知 ────────────────────────────
    path('api/client/members/', include('users.urls.member_urls')),
    path('api/client/notifications/', include('notifications.urls.task_urls')),
]

# 开发环境：挂载媒体文件服务
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
