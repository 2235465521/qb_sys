"""
standards.urls.admin_urls — 后台标准管理路由
"""

from django.urls import path
from standards.views.admin_views import (
    StandardAdminListCreateView,
    StandardAdminDetailView,
    StandardImportView,
    StandardImportTemplateView,
    StandardIndicatorImportView
)

urlpatterns = [
    path('', StandardAdminListCreateView.as_view(), name='admin-standard-list'),
    path('<int:pk>/', StandardAdminDetailView.as_view(), name='admin-standard-detail'),
    path('import/', StandardImportView.as_view(), name='admin-standard-import'),
    path('import/template/', StandardImportTemplateView.as_view(), name='admin-standard-import-template'),
    path('import-indicators/', StandardIndicatorImportView.as_view(), name='admin-standard-import-indicators'),
]

