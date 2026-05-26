"""
companies.urls.search_urls — 前台搜企路由（模块一）
"""

from django.urls import path
from companies.views.search_views import CompanySearchView, CompanyStandardsView, CompanyExportView, ClientLeadCreateView

urlpatterns = [
    path('companies/', CompanySearchView.as_view(), name='client-company-search'),
    path('companies/<int:pk>/standards/', CompanyStandardsView.as_view(), name='client-company-standards'),
    path('companies/export/', CompanyExportView.as_view(), name='client-company-export'),
    path('leads/', ClientLeadCreateView.as_view(), name='client-lead-create'),
]
