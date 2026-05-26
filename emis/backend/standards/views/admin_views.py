"""
standards.views.admin_views — 后台标准管理视图层
"""

from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser
from standards.models import Standard
from standards.serializers import StandardListSerializer, StandardDetailSerializer
from standards import services

class StandardAdminListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/admin/standards/ — 获取标准列表
    POST /api/admin/standards/ — 新建标准
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return StandardListSerializer
        return StandardDetailSerializer

    def get_queryset(self):
        # 默认只列出企业标准类型 (enterprise)，供企标管理使用
        qs = Standard.objects.filter(type='enterprise').select_related('company')
        
        # 支持按标准号、标准名称、或者所属企业筛选
        params = self.request.query_params
        if params.get('keyword'):
            from django.db.models import Q
            kw = params['keyword']
            qs = qs.filter(Q(standard_no__icontains=kw) | Q(title__icontains=kw))
            
        if params.get('company_id'):
            qs = qs.filter(company_id=params['company_id'])
            
        if params.get('status'):
            qs = qs.filter(status=params['status'])
            
        return qs.order_by('-created_at')


class StandardAdminDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/admin/standards/{id}/ — 获取标准详情
    PUT    /api/admin/standards/{id}/ — 更新标准
    DELETE /api/admin/standards/{id}/ — 物理删除标准
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = StandardDetailSerializer
    queryset = Standard.objects.all()


class StandardImportView(APIView):
    """
    POST /api/admin/standards/import/ — 拖拽上传爬取格式 Excel 一键批量导入企标和企业
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser]

    def post(self, request):
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({'error': '请上传 Excel 文件'}, status=status.HTTP_400_BAD_REQUEST)

        if not file_obj.name.endswith(('.xlsx', '.xls')):
            return Response({'error': '仅支持 .xlsx 或 .xls 格式的文件'}, status=status.HTTP_400_BAD_REQUEST)

        # 调用我们高精对准业务的 Excel 企标空间导入引擎！
        result = services.import_standards_from_excel(file_obj)
        return Response(result, status=status.HTTP_200_OK)


class StandardIndicatorImportView(APIView):
    """
    POST /api/admin/standards/import-indicators/ — 导入指标解析 Excel 并将解析状态修改为已完成指标解析
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser]

    def post(self, request):
        import pandas as pd
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({'error': '请上传 Excel 文件'}, status=status.HTTP_400_BAD_REQUEST)

        if not file_obj.name.endswith(('.xlsx', '.xls')):
            return Response({'error': '仅支持 .xlsx 或 .xls 格式的文件'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            df = pd.read_excel(file_obj)
            std_col = None
            for col in ['标准编号', '企标号', '标准号']:
                if col in df.columns:
                    std_col = col
                    break
            
            if not std_col:
                return Response({'error': 'Excel 中未找到标准编号/企标号/标准号列'}, status=status.HTTP_400_BAD_REQUEST)

            standard_nos = df[std_col].dropna().astype(str).str.strip().tolist()
            if not standard_nos:
                return Response({'error': 'Excel 中无有效标准编号数据'}, status=status.HTTP_400_BAD_REQUEST)

            updated_count = Standard.objects.filter(
                standard_no__in=standard_nos
            ).update(is_parsed='indicators_parsed')

            return Response({
                'success': True,
                'message': f'导入成功！已将 {updated_count} 条企标的解析状态更新为“已完成指标解析”'
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': f'解析 Excel 失败: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

