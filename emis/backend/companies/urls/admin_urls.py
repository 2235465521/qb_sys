"""
companies.urls.admin_urls — 后台企业管理路由
"""

from django.urls import path
from companies.views.admin_views import (
    CompanyAdminListCreateView,
    CompanyAdminDetailView,
    CompanyQuickCreateView,
    CompanyImportView,
    CompanyImportTemplateView,
    CompanyExportView,
    AdminDashboardStatsView,
    AdminLeadViewSet,
)

urlpatterns = [
    path('', CompanyAdminListCreateView.as_view(), name='admin-company-list'),
    path('quick_create/', CompanyQuickCreateView.as_view(), name='admin-company-quick-create'),
    path('<int:pk>/', CompanyAdminDetailView.as_view(), name='admin-company-detail'),
    path('import/', CompanyImportView.as_view(), name='admin-company-import'),
    path('import/template/', CompanyImportTemplateView.as_view(), name='admin-company-import-template'),
    path('export/', CompanyExportView.as_view(), name='admin-company-export'),
    path('dashboard/stats/', AdminDashboardStatsView.as_view(), name='admin-dashboard-stats'),
    path('leads/', AdminLeadViewSet.as_view({'get': 'list', 'post': 'create'}), name='admin-lead-list'),
    path('leads/<int:pk>/', AdminLeadViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='admin-lead-detail'),
    path('leads/<int:pk>/followup/', AdminLeadViewSet.as_view({'post': 'add_followup'}), name='admin-lead-followup'),
    path('leads/export/', AdminLeadViewSet.as_view({'get': 'export', 'post': 'export'}), name='admin-lead-export'),
]

