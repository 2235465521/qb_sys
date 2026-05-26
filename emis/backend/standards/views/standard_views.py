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


class StandardListView(generics.ListAPIView):
    """
    GET /api/client/standards/
    支持参数：
      type       — enterprise/group/national
      is_parsed  — true/false（模块二解析状态筛选）
      company_id — 企业 ID
      keyword    — 标准号/名称关键词
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = StandardListSerializer
    pagination_class = StandardSearchPagination

    def get_queryset(self):
        params = self.request.query_params
        qs = Standard.objects.select_related('company')

        if params.get('type'):
            qs = qs.filter(type=params['type'])

        if params.get('is_parsed') in ('true', 'false'):
            qs = qs.filter(is_parsed=params['is_parsed'] == 'true')

        if params.get('company_id'):
            qs = qs.filter(company_id=params['company_id'])

        if params.get('keyword'):
            from django.db.models import Q
            kw = params['keyword']
            qs = qs.filter(Q(standard_no__icontains=kw) | Q(title__icontains=kw))

        return qs.order_by('-created_at')

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
        response = super().list(request, *args, **kwargs)

        # 写入缓存（300 秒过期）
        try:
            cache.set(cache_key, json.dumps(response.data), timeout=300)
        except Exception:
            pass

        return response


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
from django.http import FileResponse, Http404
from django.conf import settings

from rest_framework import permissions

from django.http import HttpResponse, Http404
from rest_framework_simplejwt.tokens import AccessToken
from users.models import AdminUser
from urllib.parse import quote

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
            disk_file_path = os.path.join(shared_root, standard.disk_filename)
            if os.path.exists(disk_file_path):
                file_path = disk_file_path
                redirect_url = f"/protected_shared_disk/{standard.disk_filename.replace(chr(92), '/')}"

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

        # 6. 构造返回响应
        filename = os.path.basename(file_path)
        is_production = not settings.DEBUG

        if is_production:
            response = HttpResponse()
            response['Content-Type'] = 'application/pdf'
            response['X-Accel-Redirect'] = redirect_url
        else:
            response = FileResponse(open(file_path, 'rb'), content_type='application/pdf')

        # 7. 设置文件名（解决中文乱码）
        try:
            response['Content-Disposition'] = f"attachment; filename*=UTF-8''{quote(filename)}"
        except Exception:
            response['Content-Disposition'] = f"attachment; filename={quote(filename)}"

        return response
