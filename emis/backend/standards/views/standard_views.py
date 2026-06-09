from django.core.cache import cache
import json
from rest_framework import generics, permissions
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from standards.models import Standard
from standards.serializers import StandardListSerializer, StandardDetailSerializer


class StandardSearchPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


def parse_date_param(param_start, param_end):
    from datetime import date, datetime
    try:
        if len(param_start) == 4:
            start_date = date(int(param_start), 1, 1)
        else:
            start_date = datetime.strptime(param_start, '%Y-%m-%d').date()

        if len(param_end) == 4:
            end_date = date(int(param_end), 12, 31)
        else:
            end_date = datetime.strptime(param_end, '%Y-%m-%d').date()

        return start_date, end_date
    except Exception:
        return None, None


class StandardListView(generics.ListAPIView):
    """
    GET /api/client/standards/
    支持参数：
      type        — enterprise/group/national
      is_parsed   — true/false（模块二解析状态筛选）
      company_id  — 企业 ID
      keyword     — 标准号/名称关键词
      search_mode — title/full_text (检索模式，默认为 title)
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = StandardListSerializer
    pagination_class = StandardSearchPagination

    def get_queryset(self):
        from standards.services import search_standards_service
        return search_standards_service(self.request.query_params)

    def list(self, request, *args, **kwargs):
        params = request.query_params
        # 构造唯一的缓存 Key
        cache_parts = []
        for key in sorted(params.keys()):
            cache_parts.append(f"{key}={params.get(key)}")
        cache_key = "standard_search:" + ":".join(cache_parts) if cache_parts else "standard_search:default"

        # 尝试从缓存读取
        try:
            cached_data = cache.get(cache_key)
            if cached_data is not None:
                return Response(json.loads(cached_data))
        except Exception:
            pass

        # 缓存未命中，查询并序列化
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            self.attach_snippets(page, params.get('keyword'), params.get('search_mode'))
            serializer = self.get_serializer(page, many=True)
            response_data = self.get_paginated_response(serializer.data).data
        else:
            queryset = list(queryset)
            self.attach_snippets(queryset, params.get('keyword'), params.get('search_mode'))
            serializer = self.get_serializer(queryset, many=True)
            response_data = serializer.data

        # 写入缓存（300 秒过期）
        try:
            cache.set(cache_key, json.dumps(response_data), timeout=300)
        except Exception:
            pass

        return Response(response_data)

    def attach_snippets(self, standards, keyword, search_mode):
        if not keyword or not standards or search_mode != 'full_text':
            return

        from standards.models import StandardContent
        std_ids = [std.id for std in standards]

        # 查询匹配关键词的所有页面文本，按 standard_id 和 page_number 排序
        contents = StandardContent.objects.filter(
            standard_id__in=std_ids,
            content__icontains=keyword
        ).order_by('standard_id', 'page_number')

        # 分组保留第一个匹配页面的内容
        std_content_map = {}
        for c in contents:
            if c.standard_id not in std_content_map:
                std_content_map[c.standard_id] = c

        for std in standards:
            sc = std_content_map.get(std.id)
            if sc:
                std.snippet = self.generate_snippet_text(sc.content, keyword, sc.page_number)
            else:
                std.snippet = ""

    def generate_snippet_text(self, content, keyword, page_number):
        import re
        if not content or not keyword:
            return ""

        # 不区分大小写匹配关键字
        match = re.search(re.escape(keyword), content, re.IGNORECASE)
        if not match:
            return content[:80] + "..." if len(content) > 80 else content

        start, end = match.start(), match.end()
        total_len = len(content)
        context_len = 70  # 片段字符长度

        # 在匹配词两边分配长度
        left_len = max(0, (context_len - len(keyword)) // 2)
        right_len = context_len - len(keyword) - left_len

        # 计算切片边界
        start_idx = max(0, start - left_len)
        end_idx = min(total_len, end + right_len)

        # 边界校正
        if start_idx == 0:
            end_idx = min(total_len, context_len)
        if end_idx == total_len:
            start_idx = max(0, total_len - context_len)

        snippet_raw = content[start_idx:end_idx]

        # 添加省略号
        prefix = "..." if start_idx > 0 else ""
        suffix = "..." if end_idx < total_len else ""

        # 替换高亮匹配项（保留原有大小写）
        def replace_func(m):
            return f'<mark style="color:red;">{m.group(0)}</mark>'

        highlighted = re.sub(re.escape(keyword), replace_func, snippet_raw, flags=re.IGNORECASE)

        return f"第 {page_number} 页: {prefix}{highlighted}{suffix}"



class StandardDetailView(generics.RetrieveAPIView):
    """GET /api/client/standards/{id}/"""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = StandardDetailSerializer
    queryset = Standard.objects.select_related('company')


from rest_framework.views import APIView
from rest_framework import status

class ScanPdfSyncView(APIView):
    r"""
    POST /api/client/standards/scan-pdf-sync/
    手动触发共享磁盘的 PDF 扫盘比对，通过 Celery 异步任务执行对齐。
    
    GET /api/client/standards/scan-pdf-sync/
    查询当前或最近一次后台扫盘任务的执行状态及结果。
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from django.core.cache import cache
        task_info = cache.get('scan_pdf_sync_task')
        if not task_info:
            return Response({'status': 'idle', 'message': '当前没有运行的扫盘任务'})
        return Response(task_info, status=status.HTTP_200_OK)

    def post(self, request):
        from django.core.cache import cache
        from standards.tasks import align_disk_files_task
        
        # 校验防止并发冲突
        task_info = cache.get('scan_pdf_sync_task')
        if task_info and task_info.get('status') == 'running':
            return Response({'error': '已有扫盘任务在后台运行中，请勿重复提交'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            task = align_disk_files_task.delay()
            return Response({
                'message': '扫盘匹配任务已在后台提交，正在异步处理中...',
                'task_id': task.id
            }, status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            return Response({
                'error': f"异步扫盘任务启动失败: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




import os
from django.http import FileResponse, Http404, HttpResponse
from django.conf import settings

from rest_framework import permissions
from rest_framework_simplejwt.tokens import AccessToken
from users.models import AdminUser
from urllib.parse import quote
from django.utils.decorators import method_decorator
from django.views.decorators.clickjacking import xframe_options_exempt

@method_decorator(xframe_options_exempt, name='dispatch')
class StandardDownloadView(APIView):
    """
    GET /api/client/standards/{pk}/download/
    提供企标/国标文件的绝对安全下载，基于 Nginx X-Accel-Redirect 卸载传输，防止 Django 进程阻塞与内存溢出。
    支持：
      1. 正常的 JWT Authorization 头认证（由 Django REST Framework 校验）
      2. 浏览器直接 GET 跳转的 URL Query Parameter (?token=xxx) 认证

    优先策略：
      1. 优先使用 disk_filename（共享磁盘阵列）
      2. 如果 disk_filename 不存在，则降级到 pdf_file（项目 media 目录或共享磁盘备用路径）
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, pk):
        # 1. 权限校验：优先基于 request.user，其次基于 url query token
        user = request.user
        if not user or not user.is_authenticated:
            token = request.query_params.get('token')
            if token:
                try:
                    access_token = AccessToken(token)
                    user = AdminUser.objects.get(id=access_token['user_id'])
                except Exception:
                    pass

        if not user or not user.is_authenticated:
            return Response(
                {'error': '凭证无效或已过期，请登录后重试'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # 2. 获取标准
        try:
            standard = Standard.objects.get(pk=pk)
        except Standard.DoesNotExist:
            raise Http404("标准不存在")

        shared_root = getattr(settings, 'SHARED_DISK_ROOT', r"Y:\磁盘阵列\标准文件下载\企标下载")
        file_path = None
        redirect_url = None

        # 3. 优先策略：先尝试 disk_filename
        if standard.disk_filename:
            # 兼容 Windows 导入的含有反斜杠 \ 的旧路径，在 Linux 环境下转换为正斜杠 /
            norm_disk_filename = standard.disk_filename.replace('\\', '/')
            disk_file_path = os.path.join(shared_root, norm_disk_filename)
            if os.path.exists(disk_file_path):
                file_path = disk_file_path
                redirect_url = f"/protected_shared_disk/{norm_disk_filename}"

        # 4. 降级策略：如果 disk_filename 不存在或为空，尝试 pdf_file
        if not file_path and standard.pdf_file:
            rel_path = standard.pdf_file.name.replace('\\', '/')

            # 先在共享网络磁盘阵列中查找
            disk_file_path = os.path.join(shared_root, rel_path)
            if os.path.exists(disk_file_path):
                file_path = disk_file_path
                redirect_url = f"/protected_shared_disk/{rel_path}"
            else:
                # 再在本地 media 物理目录中查找
                media_file_path = os.path.join(settings.MEDIA_ROOT, rel_path)
                if os.path.exists(media_file_path):
                    file_path = media_file_path
                    redirect_url = f"/protected_media/{rel_path}"
                else:
                    # 兜底清理 media/ 前缀
                    if rel_path.startswith('media/'):
                        clean_path = rel_path.replace('media/', '', 1)
                        clean_file_path = os.path.join(settings.MEDIA_ROOT, clean_path)
                        if os.path.exists(clean_file_path):
                            file_path = clean_file_path
                            redirect_url = f"/protected_media/{clean_path}"

        # 5. 文件不存在检查
        if not file_path:
            raise Http404("此标准尚未关联有效的 PDF 文件")

        # 6. 直接流式返回 PDF（兼容中文路径，规避 Nginx X-Accel-Redirect 中文乱码问题）
        filename = os.path.basename(file_path)

        mode = request.query_params.get('mode', 'download')
        disp_type = 'inline' if mode == 'preview' else 'attachment'

        try:
            content_disposition = f"{disp_type}; filename*=UTF-8''{quote(filename)}"
        except Exception:
            content_disposition = f"{disp_type}; filename={quote(filename)}"

        response = FileResponse(open(file_path, 'rb'), content_type='application/pdf')
        response['Content-Type'] = 'application/pdf'
        response['Content-Disposition'] = content_disposition
        return response


import openpyxl
import io

class ExportStandardReferencesView(APIView):
    """
    GET /api/client/standards/<int:pk>/export-references/
    将某个标准关联的规范性引用标准列表导出为 Excel 文件
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        try:
            try:
                standard = Standard.objects.get(pk=pk)
            except Standard.DoesNotExist:
                return Response({'detail': '标准不存在'}, status=status.HTTP_404_NOT_FOUND)

            references = standard.normative_references.all()
            
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "规范性引用标准目录"
            
            # 写入标题行
            ws.append(["序号", "被引用标准号", "最新标准号"])
            
            # 写入数据行
            for idx, ref in enumerate(references):
                # 防止可能为空（null）的关联字段直接调用属性
                cited_no = ref.cited_standard_no if ref.cited_standard_no is not None else ""
                latest_no = ref.latest_standard_no if ref.latest_standard_no is not None else ""
                ws.append([
                    idx + 1,
                    cited_no,
                    latest_no or "暂无最新标准"
                ])
                
            buffer = io.BytesIO()
            wb.save(buffer)
            buffer.seek(0)
            
            response = HttpResponse(
                buffer.getvalue(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            
            # 中文文件名防乱码
            filename = f"{standard.standard_no}_规范性引用标准.xlsx"
            try:
                response['Content-Disposition'] = f"attachment; filename*=UTF-8''{quote(filename)}"
            except Exception:
                response['Content-Disposition'] = f"attachment; filename={quote(filename)}"
                
            return response
        except Exception as e:
            return Response({"detail": f"Excel导出失败: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)


class StandardGraphView(APIView):
    """
    GET /api/client/standards/<int:pk>/graph/
    获取当前企业标准的引用关系知识图谱数据 (ECharts Graph 结构)
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        try:
            standard = Standard.objects.get(pk=pk)
        except Standard.DoesNotExist:
            return Response({'error': '标准不存在'}, status=status.HTTP_404_NOT_FOUND)

        from standards.models import NormativeReference
        references = NormativeReference.objects.filter(source_standard=standard).select_related('cited_standard')

        # 1. 中心企标节点
        nodes = [{
            "id": f"std_{standard.id}",
            "name": f"{standard.standard_no} (中心企标)",
            "symbolSize": 60,
            "category": 0,
            "title": standard.title,
            "type_display": standard.get_type_display(),
            "status_display": standard.get_status_display(),
            "company_name": standard.company.name if standard.company else ""
        }]

        links = []
        seen_nodes = {f"std_{standard.id}"}

        # 2. 级联遍历引用子表
        for ref in references:
            if ref.cited_standard:
                node_id = f"std_{ref.cited_standard.id}"
                node_name = ref.cited_standard.standard_no
                title = ref.cited_standard.title
                status_display = ref.cited_standard.get_status_display()
                type_display = ref.cited_standard.get_type_display()
                company_name = ref.cited_standard.company.name if ref.cited_standard.company else ""
            else:
                node_id = f"no_{ref.cited_standard_no}"
                node_name = ref.cited_standard_no
                title = ""
                status_display = "未知"
                type_display = "国家标准" if (node_name.startswith("GB") or node_name.startswith("GB/T")) else "行业/其他标准"
                company_name = ""

            if node_id not in seen_nodes:
                seen_nodes.add(node_id)
                nodes.append({
                    "id": node_id,
                    "name": node_name,
                    "symbolSize": 40,
                    "category": 1,
                    "title": title,
                    "type_display": type_display,
                    "status_display": status_display,
                    "company_name": company_name,
                    "latest_standard_no": ref.latest_standard_no or ""
                })

            links.append({
                "source": f"std_{standard.id}",
                "target": node_id,
                "label": {
                    "show": True,
                    "formatter": "规范性引用"
                }
            })

        response_data = {
            "nodes": nodes,
            "links": links,
            "categories": [
                {"name": "中心企标"},
                {"name": "引用标准"}
            ]
        }
        return Response(response_data, status=status.HTTP_200_OK)


class StandardDownloadEstimateView(APIView):
    """
    GET/POST /api/client/standards/download-estimate/
    根据当前高级查询条件，快速计算企业数、文件数和预估文件总体积
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return self._handle_estimate(request.query_params)

    def post(self, request):
        return self._handle_estimate(request.data)

    def _handle_estimate(self, params):
        qs = Standard.objects.filter(type='enterprise')

        # 1. 地域级联筛选
        province_id = params.get('province_id')
        city_id = params.get('city_id')
        district_id = params.get('district_id')

        if province_id:
            qs = qs.filter(company__province_id=province_id)
        if city_id:
            qs = qs.filter(company__city_id=city_id)
        if district_id:
            qs = qs.filter(company__district_id=district_id)

        # 时间维度筛选 (AND 并列关系)
        pub_start = params.get('pub_start')
        pub_end = params.get('pub_end')
        imp_start = params.get('imp_start')
        imp_end = params.get('imp_end')

        if (pub_start and pub_end) or (imp_start and imp_end):
            from django.db.models import Q
            time_filters = Q()
            if pub_start and pub_end:
                pub_s, pub_e = parse_date_param(pub_start, pub_end)
                if pub_s and pub_e:
                    time_filters &= Q(publish_date__range=(pub_s, pub_e))
            if imp_start and imp_end:
                imp_s, imp_e = parse_date_param(imp_start, imp_end)
                if imp_s and imp_e:
                    time_filters &= Q(implement_date__range=(imp_s, imp_e))
            if time_filters:
                qs = qs.filter(time_filters)

        # 2. 解析状态筛选
        parse_status = params.get('parse_status')
        if parse_status:
            from django.db.models import Q
            statuses = parse_status.split(',') if isinstance(parse_status, str) else parse_status
            q_status = Q()
            if 'pending_reference' in statuses:
                q_status |= Q(is_parsed='unparsed')
            if 'pending_indicator' in statuses:
                q_status |= Q(is_parsed='references_parsed')
            if q_status:
                qs = qs.filter(q_status)

        # 3. 关键词 & 检索模式筛选
        keyword = params.get('keyword')
        search_mode = params.get('search_mode', 'title')
        if keyword:
            if search_mode == 'full_text':
                from standards.models import StandardContent
                matching_std_ids = StandardContent.objects.filter(
                    content__icontains=keyword
                ).values_list('standard_id', flat=True).distinct()
                qs = qs.filter(id__in=matching_std_ids)
            else:
                from django.db.models import Q
                qs = qs.filter(Q(standard_no__icontains=keyword) | Q(title__icontains=keyword))

        # 4. 聚合计算（企业数量，文件总数，预估总体积）
        # 有效 PDF 规则：pdf_file 不为空 或 disk_filename 不为空
        from django.db.models import Q
        file_qs = qs.filter(
            (Q(pdf_file__isnull=False) & ~Q(pdf_file='')) |
            (Q(disk_filename__isnull=False) & ~Q(disk_filename=''))
        )

        company_count = qs.values('company').distinct().count()
        files_count = file_qs.count()
        estimated_size_mb = files_count * 2.0  # 每个文件按 2MB 估算

        return Response({
            'company_count': company_count,
            'files_count': files_count,
            'estimated_size_mb': round(estimated_size_mb, 2)
        }, status=status.HTTP_200_OK)


class ExportStandardListView(APIView):
    """
    GET /api/client/standards/export/
    导出当前高级过滤条件下的企业标准目录为 Excel 文件
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        params = request.query_params
        qs = Standard.objects.filter(type='enterprise').select_related('company')

        # 1. 地域级联筛选
        province_id = params.get('province_id')
        city_id = params.get('city_id')
        district_id = params.get('district_id')

        if province_id:
            qs = qs.filter(company__province_id=province_id)
        if city_id:
            qs = qs.filter(company__city_id=city_id)
        if district_id:
            qs = qs.filter(company__district_id=district_id)

        # 时间维度筛选 (AND 并列关系)
        pub_start = params.get('pub_start')
        pub_end = params.get('pub_end')
        imp_start = params.get('imp_start')
        imp_end = params.get('imp_end')

        if (pub_start and pub_end) or (imp_start and imp_end):
            from django.db.models import Q
            time_filters = Q()
            if pub_start and pub_end:
                pub_s, pub_e = parse_date_param(pub_start, pub_end)
                if pub_s and pub_e:
                    time_filters &= Q(publish_date__range=(pub_s, pub_e))
            if imp_start and imp_end:
                imp_s, imp_e = parse_date_param(imp_start, imp_end)
                if imp_s and imp_e:
                    time_filters &= Q(implement_date__range=(imp_s, imp_e))
            if time_filters:
                qs = qs.filter(time_filters)

        # 2. 解析状态筛选
        parse_status = params.get('parse_status')
        if parse_status:
            from django.db.models import Q
            statuses = parse_status.split(',') if isinstance(parse_status, str) else parse_status
            q_status = Q()
            if 'pending_reference' in statuses:
                q_status |= Q(is_parsed='unparsed')
            if 'pending_indicator' in statuses:
                q_status |= Q(is_parsed='references_parsed')
            if q_status:
                qs = qs.filter(q_status)

        # 3. 关键词筛选
        keyword = params.get('keyword')
        search_mode = params.get('search_mode', 'title')
        if keyword:
            if search_mode == 'full_text':
                from standards.models import StandardContent
                matching_std_ids = StandardContent.objects.filter(
                    content__icontains=keyword
                ).values_list('standard_id', flat=True).distinct()
                qs = qs.filter(id__in=matching_std_ids)
            else:
                from django.db.models import Q
                qs = qs.filter(Q(standard_no__icontains=keyword) | Q(title__icontains=keyword))

        standards = qs.order_by('-created_at')

        # 4. 生成 Excel
        import openpyxl
        import io
        from django.http import HttpResponse
        from urllib.parse import quote
        from django.utils import timezone

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "企业标准目录"

        headers = ["序号", "标准编号", "标准名称", "所属省份", "所属城市", "所属区县", "起草单位/企业", "标准状态", "发布日期"]
        ws.append(headers)

        for idx, std in enumerate(standards):
            prov = std.company.province.name if std.company and std.company.province else "--"
            city = std.company.city.name if std.company and std.company.city else "--"
            dist = std.company.district.name if std.company and std.company.district else "--"
            company_name = std.company.name if std.company else "--"
            
            ws.append([
                idx + 1,
                std.standard_no,
                std.title or "--",
                prov,
                city,
                dist,
                company_name,
                std.get_status_display() or "现行",
                std.publish_date.strftime('%Y-%m-%d') if std.publish_date else "--"
            ])

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        response = HttpResponse(
            buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

        filename = f"企标检索导出清单_{timezone.now().strftime('%Y%m%d%H%M')}.xlsx"
        try:
            response['Content-Disposition'] = f"attachment; filename*=UTF-8''{quote(filename)}"
        except Exception:
            response['Content-Disposition'] = f"attachment; filename={quote(filename)}"

        return response



