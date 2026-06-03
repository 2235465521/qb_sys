from django.urls import path
from .views import UsageLogListView, StatisticsSummaryView, StatisticsChartView

urlpatterns = [
    path('summary/', StatisticsSummaryView.as_view(), name='admin-statistics-summary'),
    path('charts/', StatisticsChartView.as_view(), name='admin-statistics-charts'),
    path('logs/', UsageLogListView.as_view(), name='admin-statistics-logs'),
]
