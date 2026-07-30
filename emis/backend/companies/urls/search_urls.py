"""
companies.urls.search_urls — 前台搜企路由（模块一）
"""

from django.urls import path
from companies.views.search_views import CompanySearchView, CompanyStandardsView, CompanyExportView, ClientLeadCreateView, CompanyStandardExportView
from companies.views.standard_sync_views import CompanyFederatedStandardsAPIView, FederatedStandardDownloadAPIView

urlpatterns = [
    path('companies/', CompanySearchView.as_view(), name='client-company-search'),
    path('companies/<int:pk>/standards/', CompanyStandardsView.as_view(), name='client-company-standards'),
    path('companies/<int:pk>/federated_standards/', CompanyFederatedStandardsAPIView.as_view(), name='client-company-federated-standards'),
    path('companies/<int:pk>/export-standards/', CompanyStandardExportView.as_view(), name='client-company-export-standards'),
    path('federated_download/', FederatedStandardDownloadAPIView.as_view(), name='client-federated-download'),
    path('companies/export/', CompanyExportView.as_view(), name='client-company-export'),
    path('leads/', ClientLeadCreateView.as_view(), name='client-lead-create'),
]

