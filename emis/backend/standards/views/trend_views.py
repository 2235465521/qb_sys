from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from standards import trend_services

class WordCloudView(APIView):
    """
    GET /api/admin/analysis/trends/word-cloud/
    产业风向词云图
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        days = int(request.query_params.get('days', 30))
        limit = int(request.query_params.get('limit', 50))
        data = trend_services.get_trend_word_cloud(days=days, limit=limit)
        return Response(data)

class GrowthRankingView(APIView):
    """
    GET /api/admin/analysis/trends/growth-ranking/
    新兴品类增速榜
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        days = int(request.query_params.get('days', 30))
        limit = int(request.query_params.get('limit', 10))
        data = trend_services.get_growth_ranking(days=days, limit=limit)
        return Response(data)

class RegionalDistributionView(APIView):
    """
    GET /api/admin/analysis/trends/regional-dist/
    区域产业集群画像
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        keyword = request.query_params.get('keyword', '')
        if not keyword:
            return Response({'error': '请提供 keyword 参数'}, status=status.HTTP_400_BAD_REQUEST)
        
        data = trend_services.get_regional_distribution(keyword=keyword)
        return Response(data)
