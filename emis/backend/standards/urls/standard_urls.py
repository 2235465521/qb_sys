"""
standards.urls.standard_urls — 标准路由（模块一）
"""

from django.urls import path
from standards.views.standard_views import StandardListView, StandardDetailView, ScanPdfSyncView, StandardDownloadView, ExportStandardReferencesView, StandardGraphView, StandardDownloadEstimateView, ExportStandardListView
from standards.views.pack_views import PackRequestView, PackStatusView, RandomPackRequestView, ZipDownloadView, EnterprisePackRequestView, PackTaskStatusView

urlpatterns = [
    path('', StandardListView.as_view(), name='client-standard-list'),
    path('<int:pk>/', StandardDetailView.as_view(), name='client-standard-detail'),
    path('<int:pk>/graph/', StandardGraphView.as_view(), name='client-standard-graph'),
    path('<int:pk>/export-references/', ExportStandardReferencesView.as_view(), name='client-standard-export-references'),
    path('download-estimate/', StandardDownloadEstimateView.as_view(), name='client-standard-download-estimate'),
    path('export/', ExportStandardListView.as_view(), name='client-standard-export'),



    path('<int:pk>/download/', StandardDownloadView.as_view(), name='client-standard-download'),
    path('pack/', PackRequestView.as_view(), name='client-standard-pack'),
    path('pack/<str:token>/status/', PackStatusView.as_view(), name='client-standard-pack-status'),
    path('pack/download/', ZipDownloadView.as_view(), name='client-standard-pack-download'),
    path('random-pack/', RandomPackRequestView.as_view(), name='client-standard-random-pack'),
    path('scan-pdf-sync/', ScanPdfSyncView.as_view(), name='client-standard-scan-pdf-sync'),
    path('pack-enterprises/', EnterprisePackRequestView.as_view(), name='client-enterprise-pack'),
    path('pack-tasks/<str:task_id>/', PackTaskStatusView.as_view(), name='client-pack-task-status'),
]
