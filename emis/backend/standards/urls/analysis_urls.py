"""
standards.urls.analysis_urls — 引用解析路由（模块二）
"""

from django.urls import path
from standards.views.analysis_views import (
    NormativeReferenceUploadView,
    CitationRankingView,
    ExportCitationRankingView,
)

urlpatterns = [
    path('upload/', NormativeReferenceUploadView.as_view(), name='analysis-upload'),
    path('citation-rank/', CitationRankingView.as_view(), name='analysis-citation-rank'),
    path('export-excel/', ExportCitationRankingView.as_view(), name='analysis-export-excel'),
]
