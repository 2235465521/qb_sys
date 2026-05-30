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
        params = self.request.query_params
        std_type = params.get('type', 'enterprise') # 默认列出企标
        if std_type == 'all':
            qs = Standard.objects.all().select_related('company')
        else:
            qs = Standard.objects.filter(type=std_type).select_related('company')
        
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
    POST /api/admin/standards/import/ — 上传 Excel 一键批量导入各类型标准与关联企业
    支持 URL 参数 ?type=enterprise/national/industry/local/group
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser]

    def post(self, request):
        file_obj = request.FILES.get('file')
        std_type = request.query_params.get('type') or request.data.get('type') or 'enterprise'
        
        if not file_obj:
            return Response({'error': '请上传 Excel 文件'}, status=status.HTTP_400_BAD_REQUEST)

        if not file_obj.name.endswith(('.xlsx', '.xls')):
            return Response({'error': '仅支持 .xlsx 或 .xls 格式的文件'}, status=status.HTTP_400_BAD_REQUEST)

        # 调用支持多维分类的 Excel 导入引擎
        result = services.import_standards_by_type(file_obj, std_type)
        return Response(result, status=status.HTTP_200_OK)


class StandardImportTemplateView(APIView):
    """
    GET /api/admin/standards/import/template/ — 下载各标准类型的 Excel 导入模板
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from django.http import HttpResponse
        std_type = request.query_params.get('type', 'enterprise')
        try:
            excel_bytes, filename = services.generate_standard_import_template(std_type)
            response = HttpResponse(
                excel_bytes,
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            from urllib.parse import quote
            response['Content-Disposition'] = f"attachment; filename*=UTF-8''{quote(filename)}"
            return response
        except Exception as e:
            return Response({'error': f'生成模板失败: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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


class StandardReferenceImportView(APIView):
    """
    POST /api/admin/standards/import-references/ — 上传 Excel 批量导入企标规范性引用明细，支持严格的容错校验
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser]

    def post(self, request):
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({'error': '请上传 Excel 文件'}, status=status.HTTP_400_BAD_REQUEST)

        if not file_obj.name.endswith(('.xlsx', '.xls')):
            return Response({'error': '仅支持 .xlsx 或 .xls 格式的文件'}, status=status.HTTP_400_BAD_REQUEST)

        result = services.import_references_from_excel_v2(file_obj)
        return Response(result, status=status.HTTP_200_OK)


class StandardReferenceImportTemplateView(APIView):
    """
    GET /api/admin/standards/import-references/template/ — 下载引用目录 Excel 导入模板
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from django.http import HttpResponse
        from urllib.parse import quote
        try:
            excel_bytes, filename = services.generate_reference_import_template_v2()
            response = HttpResponse(
                excel_bytes,
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f"attachment; filename*=UTF-8''{quote(filename)}"
            return response
        except Exception as e:
            return Response({'error': f'生成模板失败: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class StandardMixedImportView(APIView):
    """
    POST /api/admin/standards/import-mixed/
    接收混合 Excel，存入临时目录，开启 Celery 异步拆分与事务入库
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser]

    def post(self, request):
        import uuid
        import os
        from django.conf import settings
        from standards.tasks import import_standards_and_references_task

        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({'error': '请上传 Excel 文件'}, status=status.HTTP_400_BAD_REQUEST)

        if not file_obj.name.endswith(('.xlsx', '.xls')):
            return Response({'error': '仅支持 .xlsx 或 .xls 格式的文件'}, status=status.HTTP_400_BAD_REQUEST)

        # 保存为临时文件
        task_token = str(uuid.uuid4())
        temp_dir = settings.MEDIA_ROOT / 'temp_uploads'
        temp_dir.mkdir(parents=True, exist_ok=True)
        file_path = temp_dir / f'{task_token}.xlsx'

        try:
            with open(file_path, 'wb') as f:
                for chunk in file_obj.chunks():
                    f.write(chunk)
        except Exception as e:
            return Response({'error': f'文件写入临时盘失败: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 分发 Celery 异步任务
        import_standards_and_references_task.delay(str(file_path), task_token)

        return Response({
            'task_id': task_token,
            'message': '文件上传成功，异步入库任务已提交后台处理'
        }, status=status.HTTP_202_ACCEPTED)


class StandardMixedImportStatusView(APIView):
    """
    GET /api/admin/standards/import-mixed/status/
    根据 task_id 查询 Celery 任务进度与行级校验结果报告
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from django.core.cache import cache
        task_id = request.query_params.get('task_id')
        if not task_id:
            return Response({'error': '缺失 task_id 参数'}, status=status.HTTP_400_BAD_REQUEST)

        task_info = cache.get(f'import_task_{task_id}')
        if not task_info:
            return Response({'status': 'pending', 'message': '任务在队列中排队等待'}, status=status.HTTP_200_OK)

        return Response(task_info, status=status.HTTP_200_OK)


class StandardMixedImportTemplateView(APIView):
    """
    GET /api/admin/standards/import-mixed/template/
    下载企业标准基础信息与引用关系混合导入模板
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from django.http import HttpResponse
        from urllib.parse import quote
        try:
            excel_bytes, filename = services.generate_mixed_import_template_v2()
            response = HttpResponse(
                excel_bytes,
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f"attachment; filename*=UTF-8''{quote(filename)}"
            return response
        except Exception as e:
            return Response({'error': f'生成模板失败: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

