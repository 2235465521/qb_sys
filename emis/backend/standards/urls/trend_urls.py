from django.urls import path
from standards.views.trend_views import WordCloudView, GrowthRankingView, RegionalDistributionView

urlpatterns = [
    path('word-cloud/', WordCloudView.as_view(), name='trends-word-cloud'),
    path('growth-ranking/', GrowthRankingView.as_view(), name='trends-growth-ranking'),
    path('regional-dist/', RegionalDistributionView.as_view(), name='trends-regional-dist'),
]
