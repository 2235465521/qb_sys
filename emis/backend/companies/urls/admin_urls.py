"""
companies.urls.admin_urls — 后台企业管理路由
"""

from django.urls import path
from companies.views.admin_views import (
    CompanyAdminListCreateView,
    CompanyAdminDetailView,
    CompanyImportView,
    CompanyImportTemplateView,
    CompanyExportView,
    AdminDashboardStatsView,
    AdminCompanyLeadViewSet,
)

urlpatterns = [
    path('', CompanyAdminListCreateView.as_view(), name='admin-company-list'),
    path('<int:pk>/', CompanyAdminDetailView.as_view(), name='admin-company-detail'),
    path('import/', CompanyImportView.as_view(), name='admin-company-import'),
    path('import/template/', CompanyImportTemplateView.as_view(), name='admin-company-import-template'),
    path('export/', CompanyExportView.as_view(), name='admin-company-export'),
    path('dashboard/stats/', AdminDashboardStatsView.as_view(), name='admin-dashboard-stats'),
    path('leads/', AdminCompanyLeadViewSet.as_view({'get': 'list', 'post': 'create'}), name='admin-lead-list'),
    path('leads/<int:pk>/', AdminCompanyLeadViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='admin-lead-detail'),
]
