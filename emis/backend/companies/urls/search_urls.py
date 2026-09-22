"""
companies.urls.search_urls — 前台搜企路由（模块一）
"""

from django.urls import path
from companies.views.search_views import CompanySearchView, CompanyStandardsView, CompanyExportView, ClientLeadCreateView, CompanyStandardExportView
from companies.views.standard_sync_views import CompanyFederatedStandardsAPIView, FederatedStandardDownloadAPIView
from companies.views.association_batch_views import AssociationBatchQueryView, AssociationBatchExportView

urlpatterns = [
    path('companies/', CompanySearchView.as_view(), name='client-company-search'),
    path('companies/<int:pk>/standards/', CompanyStandardsView.as_view(), name='client-company-standards'),
    path('companies/<int:pk>/federated_standards/', CompanyFederatedStandardsAPIView.as_view(), name='client-company-federated-standards'),
    path('companies/<int:pk>/export-standards/', CompanyStandardExportView.as_view(), name='client-company-export-standards'),
    path('federated_download/', FederatedStandardDownloadAPIView.as_view(), name='client-federated-download'),
    path('companies/export/', CompanyExportView.as_view(), name='client-company-export'),
    path('leads/', ClientLeadCreateView.as_view(), name='client-lead-create'),
    # ── 社团与协会批量查标与合并导出 ──────────────────────────
    path('associations/batch-query/', AssociationBatchQueryView.as_view(), name='client-association-batch-query'),
    path('associations/batch-export/', AssociationBatchExportView.as_view(), name='client-association-batch-export'),
]

