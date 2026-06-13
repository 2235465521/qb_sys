"""
standards.urls.admin_urls — 后台标准管理路由
"""

from django.urls import path
from standards.views.admin_views import (
    StandardAdminListCreateView,
    StandardAdminDetailView,
    StandardImportView,
    StandardImportTemplateView,
    StandardIndicatorImportView,
    StandardReferenceImportView,
    StandardReferenceImportTemplateView,
    StandardMixedImportView,
    StandardMixedImportStatusView,
    StandardMixedImportTemplateView,
    StandardSmartImportView,
    StandardForceReparseDatesView
)

urlpatterns = [
    path('', StandardAdminListCreateView.as_view(), name='admin-standard-list'),
    path('<int:pk>/', StandardAdminDetailView.as_view(), name='admin-standard-detail'),
    path('import/', StandardImportView.as_view(), name='admin-standard-import'),
    path('import/template/', StandardImportTemplateView.as_view(), name='admin-standard-import-template'),
    path('import-indicators/', StandardIndicatorImportView.as_view(), name='admin-standard-import-indicators'),
    path('import-references/', StandardReferenceImportView.as_view(), name='admin-standard-import-references'),
    path('import-references/template/', StandardReferenceImportTemplateView.as_view(), name='admin-standard-import-references-template'),
    path('import-mixed/', StandardMixedImportView.as_view(), name='admin-standard-import-mixed'),
    path('import-mixed/status/', StandardMixedImportStatusView.as_view(), name='admin-standard-import-mixed-status'),
    path('import-mixed/template/', StandardMixedImportTemplateView.as_view(), name='admin-standard-import-mixed-template'),
    path('import-smart/', StandardSmartImportView.as_view(), name='admin-standard-import-smart'),
    path('force-reparse-dates/', StandardForceReparseDatesView.as_view(), name='admin-standard-force-reparse-dates'),
]

