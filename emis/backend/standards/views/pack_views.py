"""
standards.views.pack_views — ZIP 打包视图（模块一）
"""

import uuid
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView


class PackRequestView(APIView):
    """
    POST /api/client/standards/pack/
    提交打包任务

    Body: { "standard_ids": [1, 2, 3], ... }
    Returns: { "token": "xxx", "status": "pending", "count": 3 }
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        standard_ids = request.data.get('standard_ids', [])
        if not standard_ids:
            from standards.models import Standard
            from django.db.models import Q
            qs = Standard.objects.filter(type='enterprise')

            province_id = request.data.get('province_id')
            city_id = request.data.get('city_id')
            district_id = request.data.get('district_id')
            if province_id:
                qs = qs.filter(company__province_id=province_id)
            if city_id:
                qs = qs.filter(company__city_id=city_id)
            if district_id:
                qs = qs.filter(company__district_id=district_id)

            parse_status = request.data.get('parse_status')
            if parse_status:
                statuses = parse_status.split(',') if isinstance(parse_status, str) else parse_status
                q_status = Q()
                if 'pending_reference' in statuses:
                    q_status |= Q(is_parsed='unparsed')
                if 'pending_indicator' in statuses:
                    q_status |= Q(is_parsed='references_parsed')
                if q_status:
                    qs = qs.filter(q_status)

            keyword = request.data.get('keyword')
            search_mode = request.data.get('search_mode', 'title')
            if keyword:
                from standards.utils.search_utils import build_smart_search_q, normalize_search_keyword
                if search_mode == 'full_text':
                    from standards.models import StandardContent
                    norm_kw = normalize_search_keyword(keyword)
                    tokens = norm_kw.split() if norm_kw else [keyword]
                    content_q = Q()
                    for token in tokens:
                        content_q &= Q(content__icontains=token)
                    matching_std_ids = StandardContent.objects.filter(
                        content_q
                    ).values_list('standard_id', flat=True).distinct()
                    qs = qs.filter(id__in=matching_std_ids)
                else:
                    search_q = build_smart_search_q(keyword, ['standard_no', 'title'], clean_id_field='clean_id')
                    qs = qs.filter(search_q)

            # 只提取有有效 PDF 文件的标准进行打包
            file_qs = qs.filter(
                (Q(pdf_file__isnull=False) & ~Q(pdf_file='')) |
                (Q(disk_filename__isnull=False) & ~Q(disk_filename=''))
            )
            standard_ids = list(file_qs.values_list('id', flat=True)[:500])

        if not standard_ids or not isinstance(standard_ids, list):
            return Response(
                {'error': '未找到符合条件的企标文件，或 standard_ids 不能为空'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if len(standard_ids) > 500:
            return Response(
                {'error': '单次最多打包 500 个标准'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 生成唯一下载令牌
        token = str(uuid.uuid4()).replace('-', '')

        # 提交 Celery 异步任务
        from standards.tasks import pack_standards_zip
        pack_standards_zip.delay(standard_ids=standard_ids, download_token=token)

        return Response({'token': token, 'status': 'pending', 'count': len(standard_ids)}, status=status.HTTP_202_ACCEPTED)


class PackStatusView(APIView):
    """
    GET /api/client/standards/pack/{token}/status/
    查询打包任务状态

    Returns:
      { "status": "running"|"done"|"failed", "download_url": "...", "file_size": 1024 }
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, token):
        from django.core.cache import cache
        task_info = cache.get(f'zip_task_{token}')

        if not task_info:
            return Response({'status': 'pending'})

        # 动态转换 download_url 为绝对地址，消除前端相对路径前缀处理分歧
        if task_info.get('status') == 'done' and task_info.get('download_url'):
            rel_url = task_info['download_url']
            if not rel_url.startswith('/api/'):
                if rel_url.startswith('/'):
                    rel_url = f"/api{rel_url}"
                else:
                    rel_url = f"/api/{rel_url}"
            task_info['download_url'] = rel_url

        return Response(task_info)


import os
from django.conf import settings
from django.http import HttpResponse, Http404
from django.utils import timezone
from urllib.parse import quote

class ZipDownloadView(APIView):
    """
    GET /api/client/standards/pack/download/
    参数: ?token=xxx
    验证打包 Token 的合法性后，重定向由 Nginx 安全下载生成的 ZIP（或本地调试时采用 FileResponse 兜底）
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        token = request.query_params.get('token')
        if not token:
            return Response({'error': 'Token 不能为空'}, status=status.HTTP_400_BAD_REQUEST)

        # 1. 从缓存校验任务状态与合法性
        from django.core.cache import cache
        task_info = cache.get(f'zip_task_{token}')
        if not task_info:
            return Response({'error': '下载链接已失效或无效的下载凭据'}, status=status.HTTP_401_UNAUTHORIZED)
            
        if task_info.get('status') != 'done':
            return Response({'error': '文件尚未打包完成'}, status=status.HTTP_400_BAD_REQUEST)

        # 2. 定位 ZIP 文件
        zip_filename = f"{token}.zip"
        zip_file_path = os.path.join(settings.MEDIA_ROOT, 'temp_zips', zip_filename)
        
        if not os.path.exists(zip_file_path):
            raise Http404("物理打包文件已不存在或已被系统清理")

        # 3. 检测是否经过 Nginx
        use_nginx = request.META.get('HTTP_X_USING_NGINX') == 'yes'
        download_name = f"企标打包下载_{timezone.now().strftime('%Y%m%d%H%M')}.zip"

        if use_nginx:
            response = HttpResponse()
            response['Content-Type'] = 'application/zip'
            response['X-Accel-Redirect'] = f"/protected_media/temp_zips/{zip_filename}"
        else:
            # 降级直接由 Django 返回，以兼容本地 Vite 代理开发环境
            from django.http import FileResponse
            response = FileResponse(open(zip_file_path, 'rb'), content_type='application/zip')

        # 4. 中文文件名防乱码
        try:
            response['Content-Disposition'] = f"attachment; filename*=UTF-8''{quote(download_name)}"
        except Exception:
            response['Content-Disposition'] = f"attachment; filename={quote(download_name)}"
            
        return response


class RandomPackRequestView(APIView):
    """
    “””
    POST /api/client/standards/random-pack/
    支持三种打包模式：
      1. mode: 'standards' — 随机选择 100 个企标
      2. mode: 'companies_20'/'companies_50' — 随机选择 20/50 家企业名下的企标
      3. mode: 'selected_companies' — 打包指定企业列表下所有有 disk_filename 的企标

    Body:
      - 模式 1/2: { “mode”: “standards” | “companies_20” | “companies_50” }
      - 模式 3: { “mode”: “selected_companies”, “company_ids”: [1, 2, 3] }
    “””
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        mode = request.data.get('mode', 'standards')

        from standards.models import Standard
        from companies.models import Company
        from django.db.models import Q
        import random
        import uuid

        standard_ids = []

        if mode == 'standards':
            # 优先选择”未解析过”且具有 PDF 文件的企标 (is_parsed = 'unparsed')
            qs = Standard.objects.filter(
                type='enterprise',
                is_parsed='unparsed'
            ).filter(
                (Q(pdf_file__isnull=False) & ~Q(pdf_file='')) | (Q(disk_filename__isnull=False) & ~Q(disk_filename=''))
            ).values_list('id', flat=True)

            id_list = list(qs)
            sample_size = min(len(id_list), 100)
            standard_ids = random.sample(id_list, sample_size) if id_list else []

        elif mode in ('companies_20', 'companies_50'):
            # 随机选择 20 或 50 家企业，然后提取名下的企标（最多 100 个）
            company_count = 20 if mode == 'companies_20' else 50

            # 先选出拥有具有 PDF 企标的企业 ID 列表
            companies_with_pdfs = Standard.objects.filter(
                type='enterprise',
                pdf_file__isnull=False
            ).exclude(pdf_file='').values_list('company_id', flat=True).distinct()

            company_id_list = list(companies_with_pdfs)
            selected_companies = random.sample(company_id_list, min(len(company_id_list), company_count)) if company_id_list else []

            # 提取选定企业名下的企标 ID
            qs = Standard.objects.filter(
                company_id__in=selected_companies,
                type='enterprise',
                pdf_file__isnull=False
            ).exclude(pdf_file='').values_list('id', flat=True)

            standard_ids = list(qs)

        elif mode == 'selected_companies':
            # 新增模式：打包指定企业列表下所有有 disk_filename 的企标
            company_ids = request.data.get('company_ids', [])
            if not company_ids or not isinstance(company_ids, list):
                return Response(
                    {'error': 'company_ids 必须是非空列表'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # 查询具有 disk_filename 或 pdf_file 的企标
            qs = Standard.objects.filter(
                company_id__in=company_ids,
                type='enterprise'
            ).filter(
                (Q(pdf_file__isnull=False) & ~Q(pdf_file='')) | (Q(disk_filename__isnull=False) & ~Q(disk_filename=''))
            ).values_list('id', flat=True)

            standard_ids = list(qs)

        elif mode == 'custom_filter':
            # 自定义选择下载模式
            province_ids = request.data.get('province_ids', [])
            city_ids = request.data.get('city_ids', [])
            parse_target = request.data.get('parse_target', 'normative')
            
            # 构建地域查询条件 (省份 or 城市)
            region_q = Q()
            if province_ids:
                region_q |= Q(company__province_id__in=province_ids)
            if city_ids:
                region_q |= Q(company__city_id__in=city_ids)
                
            # 如果没有选择任何地域，则不加地域限制（或者报错，按需处理）
            
            # 解析状态条件
            # normative: 暂未解析 -> 需要规范性引用解析 -> is_parsed='unparsed'
            # indicator: 已完成规范性引用解析 -> 需要指标解析 -> is_parsed='references_parsed'
            is_parsed_val = 'unparsed' if parse_target == 'normative' else 'references_parsed'
            
            qs = Standard.objects.filter(
                type='enterprise',
                is_parsed=is_parsed_val
            ).filter(
                (Q(pdf_file__isnull=False) & ~Q(pdf_file='')) | (Q(disk_filename__isnull=False) & ~Q(disk_filename=''))
            )
            
            if region_q:
                qs = qs.filter(region_q)
                
            qs = qs.values_list('id', flat=True)
            id_list = list(qs)
            
            # 随机选取最多 100 个
            sample_size = min(len(id_list), 100)
            standard_ids = random.sample(id_list, sample_size) if id_list else []

        if not standard_ids:
            return Response(
                {'error': '未找到符合条件的企标文件'},
                status=status.HTTP_404_NOT_FOUND
            )

        # 生成唯一下载令牌并提交 Celery 异步任务
        token = str(uuid.uuid4()).replace('-', '')
        from standards.tasks import pack_standards_zip
        
        # 如果是自定义过滤模式，包含 Excel 清单
        include_excel = mode == 'custom_filter'
        pack_standards_zip.delay(standard_ids=standard_ids, download_token=token, include_excel=include_excel)

        return Response({
            'token': token,
            'status': 'pending',
            'count': len(standard_ids)
        }, status=status.HTTP_202_ACCEPTED)


class EnterprisePackRequestView(APIView):
    """
    POST /api/client/standards/pack-enterprises/
    支持两种模式批量打包所有 PDF 企标文件：
      1. 传入已勾选企业 ID 列表 {"enterprise_ids": [1, 2, ...]}
      2. 传入当前检索条件全选导出 {"export_all": true, "filters": {...}}
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        export_all = request.data.get('export_all', False)
        enterprise_ids = request.data.get('enterprise_ids', [])
        filters = request.data.get('filters', {})

        if not export_all and not enterprise_ids:
            return Response(
                {'error': 'enterprise_ids 不能为空，或必须指定检索过滤条件开展全选导出'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 模式一企业数限制为 200 家（前端限制 200，后端双重校验限制）
        if not export_all and len(enterprise_ids) > 200:
            return Response(
                {'error': '单次打包最多选择 200 家企业'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 生成唯一下载 UUID
        import uuid
        uuid_str = str(uuid.uuid4())

        # 调度 Celery 异步打包任务
        from standards.tasks import pack_enterprises_zip_task
        task = pack_enterprises_zip_task.delay(
            enterprise_ids=enterprise_ids,
            filters=filters,
            export_all=export_all,
            uuid_str=uuid_str
        )

        return Response({
            'task_id': task.id,
            'status': 'PENDING'
        }, status=status.HTTP_202_ACCEPTED)


class AdvancedExportRequestView(APIView):
    """
    POST /api/client/standards/export-advanced/
    高级导出接口：根据机构类型包含/排除模式、地区、范围及选择格式，异步生成企业目录与企标目录。
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        export_scope = request.data.get('export_scope', 'filtered')
        enterprise_ids = request.data.get('enterprise_ids', [])
        base_filters = request.data.get('base_filters', {})
        advanced_filters = request.data.get('advanced_filters', {})
        export_content = request.data.get('export_content', 'both')
        file_format = request.data.get('file_format', 'single_excel')

        if export_scope == 'selected' and not enterprise_ids:
            return Response(
                {'error': '未选中任何企业记录，无法导出'},
                status=status.HTTP_400_BAD_REQUEST
            )

        import uuid
        uuid_str = str(uuid.uuid4())

        from standards.tasks import advanced_export_task
        task = advanced_export_task.delay(
            enterprise_ids=enterprise_ids,
            base_filters=base_filters,
            advanced_filters=advanced_filters,
            export_scope=export_scope,
            export_content=export_content,
            file_format=file_format,
            uuid_str=uuid_str
        )

        return Response({
            'task_id': task.id,
            'status': 'PENDING',
            'message': '高级导出任务已成功分发'
        }, status=status.HTTP_202_ACCEPTED)



class PackTaskStatusView(APIView):
    """
    GET /api/client/standards/pack-tasks/<str:task_id>/
    查询 Celery 异步打包任务的状态与下载 URL
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, task_id):
        from celery.result import AsyncResult
        from django.conf import settings

        result = AsyncResult(task_id)
        response_data = {
            'task_id': task_id,
            'status': result.status, # PENDING, SUCCESS, FAILURE, etc.
        }

        if result.status == 'SUCCESS':
            relative_url = result.result # 'exports/{uuid}.zip'
            if relative_url:
                response_data['download_url'] = settings.MEDIA_URL + relative_url
            response_data['progress'] = 100
        elif result.status == 'FAILURE':
            # Celery 异常信息
            res_info = result.result or result.info
            if isinstance(res_info, dict) and 'exc_message' in res_info:
                response_data['error'] = res_info['exc_message']
            else:
                response_data['error'] = str(res_info or '打包过程中发生未知错误')
        else:
            if isinstance(result.info, dict):
                response_data['progress'] = result.info.get('progress')
                response_data['message'] = result.info.get('message', '处理中...')

        return Response(response_data)



class SampledPackRequestView(APIView):
    """
    POST /api/client/standards/sampled-pack/
    按搜索条件进行内存抽样，然后提交 Celery 打包任务。
    若预估 ZIP 体积 > 1 GB，则自动拆分为多批次，每批次均返回独立 token。

    Body:
      {
        "strategy":  "random" | "latest",   // 抽样策略，默认 random
        "count":     100,                    // 抽样数量，默认 100
        "filters":   { ...与搜索页相同的参数 }
      }

    Returns:
      {
        "parts": [
          {"token": "xxx", "count": 50, "status": "pending"},
          {"token": "yyy", "count": 50, "status": "pending"}
        ],
        "total_sampled": 100,
        "split_count": 2
      }
    """
    permission_classes = [permissions.IsAuthenticated]

    # 单批次体积上限：1 GB
    MAX_BYTES_PER_PART = 1 * 1024 * 1024 * 1024

    def post(self, request):
        import random
        from standards.models import Standard
        from django.db.models import Q
        from django.conf import settings
        import os

        strategy = request.data.get('strategy', 'random')
        try:
            count = int(request.data.get('count', 100))
        except (ValueError, TypeError):
            return Response({'error': 'count 必须为整数'}, status=status.HTTP_400_BAD_REQUEST)

        if count < 1:
            return Response({'error': 'count 最小为 1'}, status=status.HTTP_400_BAD_REQUEST)
        if count > 5000:
            return Response({'error': 'count 最大为 5000'}, status=status.HTTP_400_BAD_REQUEST)

        filters = request.data.get('filters', {})

        # ── 1. 构建基础 QuerySet（与搜索页过滤逻辑保持一致）──────────
        qs = Standard.objects.filter(type='enterprise').filter(
            (Q(pdf_file__isnull=False) & ~Q(pdf_file='')) |
            (Q(disk_filename__isnull=False) & ~Q(disk_filename=''))
        )

        province_id = filters.get('province_id')
        city_id = filters.get('city_id')
        district_id = filters.get('district_id')
        if province_id:
            qs = qs.filter(company__province_id=province_id)
        if city_id:
            qs = qs.filter(company__city_id=city_id)
        if district_id:
            qs = qs.filter(company__district_id=district_id)

        parse_status = filters.get('parse_status', '')
        if parse_status and parse_status != 'all':
            statuses = parse_status.split(',') if isinstance(parse_status, str) else parse_status
            q_status = Q()
            if 'pending_reference' in statuses:
                q_status |= Q(is_parsed='unparsed')
            if 'pending_indicator' in statuses:
                q_status |= Q(is_parsed='references_parsed')
            if q_status:
                qs = qs.filter(q_status)

        keyword = filters.get('keyword', '')
        search_mode = filters.get('search_mode', 'title')
        if keyword:
            from standards.utils.search_utils import build_smart_search_q, normalize_search_keyword
            if search_mode == 'full_text':
                from standards.models import StandardContent
                norm_kw = normalize_search_keyword(keyword)
                tokens = norm_kw.split() if norm_kw else [keyword]
                content_q = Q()
                for token in tokens:
                    content_q &= Q(content__icontains=token)
                matching_std_ids = StandardContent.objects.filter(
                    content_q
                ).values_list('standard_id', flat=True).distinct()
                qs = qs.filter(id__in=matching_std_ids)
            else:
                search_q = build_smart_search_q(keyword, ['standard_no', 'title'], clean_id_field='clean_id')
                qs = qs.filter(search_q)

        pub_start = filters.get('pub_start')
        pub_end = filters.get('pub_end')
        if pub_start:
            qs = qs.filter(publish_date__gte=pub_start)
        if pub_end:
            qs = qs.filter(publish_date__lte=pub_end)

        # ── 2. 内存抽样（严禁 order_by('?')）───────────────────────
        if strategy == 'latest':
            # 按发布日期倒序取前 count 条
            id_list = list(
                qs.order_by('-publish_date', '-id').values_list('id', flat=True)[:count]
            )
        else:
            # 默认：随机抽样
            all_ids = list(qs.values_list('id', flat=True))
            sample_size = min(count, len(all_ids))
            id_list = random.sample(all_ids, sample_size) if all_ids else []

        if not id_list:
            return Response(
                {'error': '未找到符合条件的企标文件，请调整搜索条件后重试'},
                status=status.HTTP_404_NOT_FOUND
            )

        # ── 3. 预估文件大小并按 1 GB 拆分批次 ───────────────────────
        shared_root = getattr(settings, 'SHARED_DISK_ROOT', r'Y:\磁盘阵列\标准文件下载\企标下载')
        standards = Standard.objects.filter(id__in=id_list).only(
            'id', 'pdf_file', 'disk_filename'
        )

        # 按文件大小分批
        parts = []          # [[id, ...], [id, ...]]
        current_part = []
        current_size = 0

        for std in standards:
            file_size = 0
            # 优先检查 disk_filename
            if std.disk_filename:
                fp = os.path.join(shared_root, std.disk_filename.replace('\\', '/'))
                if os.path.exists(fp):
                    file_size = os.path.getsize(fp)
            # 降级检查 pdf_file
            if file_size == 0 and std.pdf_file:
                rel = std.pdf_file.name.replace('\\', '/')
                for base in [shared_root, str(settings.MEDIA_ROOT)]:
                    fp = os.path.join(base, rel)
                    if os.path.exists(fp):
                        file_size = os.path.getsize(fp)
                        break
            # 若无法获取大小，以 5 MB 估算
            if file_size == 0:
                file_size = 5 * 1024 * 1024

            if current_size + file_size > self.MAX_BYTES_PER_PART and current_part:
                parts.append(current_part)
                current_part = [std.id]
                current_size = file_size
            else:
                current_part.append(std.id)
                current_size += file_size

        if current_part:
            parts.append(current_part)

        # ── 4. 为每个分片提交 Celery 任务 ───────────────────────────
        from standards.tasks import pack_standards_zip
        result_parts = []
        for part_ids in parts:
            token = str(uuid.uuid4()).replace('-', '')
            pack_standards_zip.delay(standard_ids=part_ids, download_token=token)
            result_parts.append({
                'token': token,
                'count': len(part_ids),
                'status': 'pending',
            })

        return Response({
            'parts': result_parts,
            'total_sampled': len(id_list),
            'split_count': len(result_parts),
        }, status=status.HTTP_202_ACCEPTED)
