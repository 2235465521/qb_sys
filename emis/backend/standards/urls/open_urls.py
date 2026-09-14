"""
standards.urls.open_urls — 豆包大模型连接器开放路由
"""

from django.urls import path
from standards.views.open_views import (
    DoubaoCompanyStandardsView,
    DoubaoStandardDownloadView,
    DoubaoSchemaView,
)

urlpatterns = [
    path('company-standards/', DoubaoCompanyStandardsView.as_view(), name='open-doubao-company-standards'),
    path('download/<int:pk>/', DoubaoStandardDownloadView.as_view(), name='open-doubao-download'),
    path('schema/', DoubaoSchemaView.as_view(), name='open-doubao-schema'),
]
