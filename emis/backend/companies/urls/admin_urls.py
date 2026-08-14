"""
companies.urls.admin_urls — 后台企业管理路由
"""

from django.urls import path
from companies.views.admin_views import (
    CompanyAdminListCreateView,
    CompanyAdminDetailView,
    CompanyQuickCreateView,
    CompanyImportView,
    CompanyImportStatusView,
    CompanyImportTemplateView,
    CompanyExportView,
    AdminDashboardStatsView,
    AdminLeadViewSet,
    AdminAttachmentViewSet,
    AdminLeadOptionViewSet,
    CompanyBatchTagView,
    CompanySyncOwnershipView,
)
from companies.views.standard_sync_views import CompanyFederatedStandardsAPIView

urlpatterns = [
    path('', CompanyAdminListCreateView.as_view(), name='admin-company-list'),
    path('quick_create/', CompanyQuickCreateView.as_view(), name='admin-company-quick-create'),
    path('batch_tag/', CompanyBatchTagView.as_view(), name='admin-company-batch-tag'),
    path('<int:pk>/', CompanyAdminDetailView.as_view(), name='admin-company-detail'),
    path('<int:pk>/sync_ownership/', CompanySyncOwnershipView.as_view(), name='admin-company-sync-ownership'),
    path('<int:pk>/federated_standards/', CompanyFederatedStandardsAPIView.as_view(), name='admin-company-federated-standards'),
    path('import/', CompanyImportView.as_view(), name='admin-company-import'),
    path('import/status/<str:task_id>/', CompanyImportStatusView.as_view(), name='admin-company-import-status'),
    path('import/template/', CompanyImportTemplateView.as_view(), name='admin-company-import-template'),
    path('export/', CompanyExportView.as_view(), name='admin-company-export'),
    path('dashboard/stats/', AdminDashboardStatsView.as_view(), name='admin-dashboard-stats'),
    path('leads/', AdminLeadViewSet.as_view({'get': 'list', 'post': 'create'}), name='admin-lead-list'),
    path('leads/<int:pk>/', AdminLeadViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='admin-lead-detail'),
    path('leads/<int:pk>/followup/', AdminLeadViewSet.as_view({'post': 'add_followup'}), name='admin-lead-followup'),
    path('leads/<int:pk>/delete_attachment/', AdminLeadViewSet.as_view({'post': 'delete_attachment'}), name='admin-lead-delete-attachment'),
    path('leads/attachments/<int:pk>/', AdminAttachmentViewSet.as_view({'delete': 'destroy'}), name='admin-lead-attachment-detail'),
    path('leads/export/', AdminLeadViewSet.as_view({'get': 'export', 'post': 'export'}), name='admin-lead-export'),
    path('leads/options/', AdminLeadOptionViewSet.as_view({'get': 'list', 'post': 'create'}), name='admin-lead-option-list'),
    path('leads/options/<int:pk>/', AdminLeadOptionViewSet.as_view({'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='admin-lead-option-detail'),
]

