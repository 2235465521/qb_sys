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
            from standards.utils.search_utils import build_smart_search_q
            kw = params['keyword']
            search_q = build_smart_search_q(kw, ['standard_no', 'title'], clean_id_field='clean_id')
            qs = qs.filter(search_q)
            
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
            alias_list = ['标准编号*', '标准编号', '企标编号*', '企标编号', '企标号', '标准号*', '标准号', '企标']
            for col in df.columns:
                col_clean = str(col).strip()
                if col_clean in alias_list or col_clean.replace('*', '').strip() in [a.replace('*', '') for a in alias_list]:
                    std_col = col
                    break
            
            if not std_col:
                return Response({'error': 'Excel 中未找到标准编号/企标编号/标准号列'}, status=status.HTTP_400_BAD_REQUEST)

            standard_nos = df[std_col].dropna().astype(str).str.strip().tolist()
            if not standard_nos:
                return Response({'error': 'Excel 中无有效标准编号数据'}, status=status.HTTP_400_BAD_REQUEST)

            from standards.services import generate_clean_id
            clean_ids = [generate_clean_id(s) for s in standard_nos]
            updated_count = Standard.objects.filter(
                clean_id__in=clean_ids
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
        import threading
        import logging
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

        # 分发异步任务：若处于同步模式，在独立线程中执行，防止 HTTP 阻塞挂起
        if getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
            def run_in_thread():
                try:
                    import_standards_and_references_task(str(file_path), task_token)
                except Exception as e:
                    logging.getLogger('django.request').error(f"Thread standard import error: {e}", exc_info=True)
            t = threading.Thread(target=run_in_thread, daemon=True)
            t.start()
        else:
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


class StandardSmartImportView(APIView):
    """
    POST /api/admin/standards/import-smart/
    智能探测表头，分发至不同的导入逻辑
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser]

    def post(self, request):
        import uuid
        import os
        import threading
        import logging
        import pandas as pd
        from django.conf import settings
        from standards.tasks import import_standards_and_references_task
        from standards import services

        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({'error': '请上传 Excel 文件'}, status=status.HTTP_400_BAD_REQUEST)

        if not file_obj.name.endswith(('.xlsx', '.xls')):
            return Response({'error': '仅支持 .xlsx 或 .xls 格式的文件'}, status=status.HTTP_400_BAD_REQUEST)

        # 1. 尝试读取前几行提取表头
        try:
            df = pd.read_excel(file_obj, nrows=10)
            columns = [str(c).strip() for c in df.columns]
            columns_clean = [str(c).replace('*', '').strip() for c in df.columns]
        except Exception as e:
            return Response({'error': f'读取文件失败: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

        # 重置文件指针，供底层读取全量数据
        file_obj.seek(0)

        # 2. 探测关键字段别名列表
        company_keys = ['统一社会信用代码', '信用代码', '统一信用代码', '起草单位', '起草单位/企业名称', '公司名称', '企业名称', '起草企业', '单位名称']
        reference_keys = ['引用的国标/行标编号', '企标中引用的标准号', '被引用标准号', '引用的标准号', '引用标准号', '引用标准编号', '被引用的标准号', '被引用标准', '引用标准', '发布时引用的完整标准号', '最新标准号', '最新被引用标准号']
        std_no_keys = ['企标编号', '标准编号', '企标号', '标准号', '企标']
        std_title_keys = ['企标名称', '标准名称', '企标名', '标准名']

        has_company = any(k in columns or k in columns_clean for k in company_keys)
        has_reference = any(k in columns or k in columns_clean for k in reference_keys)
        has_std_no = any(k in columns or k in columns_clean for k in std_no_keys)
        has_std_title = any(k in columns or k in columns_clean for k in std_title_keys)

        # 3. 决策路由
        if has_reference and (has_company or has_std_title):
            # 混合导入（包含企标主信息与引用关系） -> 走异步
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

            if getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
                def run_in_thread():
                    try:
                        import_standards_and_references_task(str(file_path), task_token)
                    except Exception as e:
                        logging.getLogger('django.request').error(f"Thread smart import error: {e}", exc_info=True)
                t = threading.Thread(target=run_in_thread, daemon=True)
                t.start()
            else:
                import_standards_and_references_task.delay(str(file_path), task_token)

            return Response({
                'type': 'async',
                'task_id': task_token,
                'message': '文件包含企业/企标与引用关系，已提交后台异步排队处理。'
            }, status=status.HTTP_202_ACCEPTED)

        elif has_reference and not has_company and not has_std_title:
            # 纯引用导入 -> 走同步
            result = services.import_references_from_excel_v2(file_obj)
            return Response({
                'type': 'sync',
                'data': result,
                'message': '解析完成，纯引用关系导入成功。'
            }, status=status.HTTP_200_OK)

        elif has_std_no or has_company:
            # 纯企标及企业导入 -> 走同步
            result = services.import_standards_from_excel(file_obj)
            return Response({
                'type': 'sync',
                'data': result,
                'message': '解析完成，企业与企标资产导入成功。'
            }, status=status.HTTP_200_OK)

        else:
            return Response({'error': '无法识别文件内容，未发现有效的企业、企标编号或引用号列，请使用官方模板'}, status=status.HTTP_400_BAD_REQUEST)


class StandardForceReparseDatesView(APIView):
    """
    POST /api/admin/standards/force-reparse-dates/
    触发全量重新扫描修复 PDF 中的发布和实施日期
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from standards.tasks import force_reparse_all_dates_task
        force_reparse_all_dates_task.delay()
        return Response({
            'success': True,
            'message': '已触发全量重新扫描修复企标发布和实施日期的后台异步任务，请稍后查看结果。'
        }, status=status.HTTP_200_OK)
