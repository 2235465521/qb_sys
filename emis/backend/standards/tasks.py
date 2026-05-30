"""
Celery 异步任务定义

tasks/
  - pack_standards_zip  — 标准文件打包（模块一）
  - send_sms_task       — 短信批量发送（模块三）
"""

from celery import shared_task
from django.utils import timezone


# ============================================================
# 模块一：ZIP 打包任务
# ============================================================

@shared_task(bind=True, name='standards.pack_zip')
def pack_standards_zip(self, standard_ids: list, download_token: str, include_excel: bool = False):
    """
    异步打包选中标准文件为 ZIP

    Args:
        standard_ids:   要打包的标准 ID 列表
        download_token: 唯一下载令牌（用于前端轮询 + 后台存储结果）
        include_excel:  是否生成包含企业地域信息的 Excel 清单
    """
    from django.core.cache import cache
    from standards.services import create_zip_from_standards
    import os
    import tempfile

    try:
        # 更新进度
        cache.set(f'zip_task_{download_token}', {'status': 'running', 'progress': 0}, timeout=3600)

        zip_bytes = create_zip_from_standards(standard_ids, include_excel=include_excel)

        # 将 ZIP 写入临时文件（供 Nginx X-Accel-Redirect 使用）
        from django.conf import settings
        temp_dir = settings.MEDIA_ROOT / 'temp_zips'
        temp_dir.mkdir(parents=True, exist_ok=True)
        zip_path = temp_dir / f'{download_token}.zip'

        with open(zip_path, 'wb') as f:
            f.write(zip_bytes)

        # 更新任务状态，使用安全 API 包装器下载
        cache.set(f'zip_task_{download_token}', {
            'status': 'done',
            'download_url': f'/api/client/standards/pack/download/?token={download_token}',
            'file_size': len(zip_bytes),
        }, timeout=3600)

    except Exception as exc:
        cache.set(f'zip_task_{download_token}', {
            'status': 'failed',
            'error': str(exc),
        }, timeout=3600)
        raise self.retry(exc=exc, countdown=5, max_retries=2)


@shared_task(bind=True, name='standards.pack_enterprises_zip')
def pack_enterprises_zip_task(self, enterprise_ids: list = None, filters: dict = None, export_all: bool = False, uuid_str: str = ""):
    """
    异步打包选中企业或检索条件名下的所有 PDF 企标文件。
    最大限制 200 家企业。
    目录结构：企业名称/标准号_标准名称.pdf
    """
    import os
    import zipfile
    from django.conf import settings
    from companies.models import Company
    from standards.models import Standard
    from django.db.models import Q
    from companies.services import search_companies

    # 1. 准备临时导出目录
    export_dir = os.path.join(settings.MEDIA_ROOT, 'exports')
    os.makedirs(export_dir, exist_ok=True)
    
    zip_filename = f"{uuid_str}.zip"
    zip_filepath = os.path.join(export_dir, zip_filename)
    
    shared_root = getattr(settings, 'SHARED_DISK_ROOT', r"Y:\磁盘阵列\标准文件下载\企标下载")
    
    added_count = 0
    skipped_count = 0

    # 2. 确定目标企业 ID 列表，上限限制 200 家
    target_ids = []
    if export_all and filters:
        lat = filters.get('lat')
        lng = filters.get('lng')
        radius_km = filters.get('radius_km')
        
        center_lat = float(lat) if lat else None
        center_lng = float(lng) if lng else None
        radius = float(radius_km) if radius_km else None

        try:
            province_id = int(filters.get('province_id')) if filters.get('province_id') else None
        except (ValueError, TypeError):
            province_id = None
        try:
            city_id = int(filters.get('city_id')) if filters.get('city_id') else None
        except (ValueError, TypeError):
            city_id = None
        try:
            district_id = int(filters.get('district_id')) if filters.get('district_id') else None
        except (ValueError, TypeError):
            district_id = None

        qs = search_companies(
            keyword=filters.get('keyword', ''),
            province_id=province_id,
            city_id=city_id,
            district_id=district_id,
            center_lat=center_lat,
            center_lng=center_lng,
            radius_km=radius,
            ics=filters.get('ics', ''),
            ccs=filters.get('ccs', ''),
            standard_logic=filters.get('standard_logic', 'OR'),
        )
        target_ids = list(qs.values_list('id', flat=True)[:200])
    elif enterprise_ids:
        target_ids = enterprise_ids[:200]

    if not target_ids:
        raise ValueError("没有找到符合条件的企业记录或企业列表为空")

    # 3. 查找目标企业并进行打包
    companies = Company.objects.filter(id__in=target_ids)

    with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zf:
        for company in companies:
            # 查找该公司名下的所有企标（存在 pdf_file 或 disk_filename）
            standards = Standard.objects.filter(
                company=company,
                type='enterprise'
            ).filter(
                (Q(pdf_file__isnull=False) & ~Q(pdf_file='')) | 
                (Q(disk_filename__isnull=False) & ~Q(disk_filename=''))
            )
            
            # 清理企业名称中的非法目录字符
            safe_company_name = "".join(c for c in company.name if c not in r'\/:*?"<>|').strip()
            if not safe_company_name:
                safe_company_name = f"Enterprise_{company.id}"

            for std in standards:
                file_path = None
                
                # 优先使用 disk_filename
                if std.disk_filename:
                    norm_disk_filename = std.disk_filename.replace('\\', '/')
                    full_path = os.path.join(shared_root, norm_disk_filename)
                    if os.path.exists(full_path):
                        file_path = full_path

                # 降级使用 pdf_file
                if not file_path and std.pdf_file and std.pdf_file.name:
                    rel_path = std.pdf_file.name.replace('\\', '/')
                    disk_file_path = os.path.join(shared_root, rel_path)
                    media_file_path = os.path.join(settings.MEDIA_ROOT, rel_path)
                    
                    if os.path.exists(disk_file_path):
                        file_path = disk_file_path
                    elif os.path.exists(media_file_path):
                        file_path = media_file_path
                    elif rel_path.startswith('media/'):
                        clean_path = rel_path.replace('media/', '', 1)
                        clean_file_path = os.path.join(settings.MEDIA_ROOT, clean_path)
                        if os.path.exists(clean_file_path):
                            file_path = clean_file_path

                if file_path:
                    # 去除非法文件名字符并把标准号中本身有的/替换为_
                    safe_std_no = "".join(c for c in std.standard_no if c not in r'\/:*?"<>|').strip()
                    safe_std_no = safe_std_no.replace('/', '_')
                    safe_title = "".join(c for c in std.title if c not in r'\/:*?"<>|').strip() if std.title else ""
                    
                    if safe_title:
                        arcname = f"{safe_company_name}/{safe_std_no}_{safe_title}.pdf"
                    else:
                        arcname = f"{safe_company_name}/{safe_std_no}.pdf"
                        
                    try:
                        zf.write(file_path, arcname=arcname)
                        added_count += 1
                    except Exception:
                        skipped_count += 1
                else:
                    skipped_count += 1

    if added_count == 0:
        if os.path.exists(zip_filepath):
            try:
                os.remove(zip_filepath)
            except OSError:
                pass
        raise ValueError("所选企业下未找到任何可供打包的标准 PDF 文件")

    return f"exports/{zip_filename}"




# ============================================================
# 模块三：短信批量发送任务
# ============================================================

@shared_task(bind=True, name='notifications.send_sms')
def send_sms_task(self, task_id: int):
    """
    异步批量发送短信

    从 SmsTask 读取配置 → 查询目标会员 → 逐条发送 → 写入日志

    Args:
        task_id: SmsTask 的数据库 ID
    """
    from notifications.models import SmsTask, SmsLog
    from users.models import Member

    try:
        task = SmsTask.objects.get(id=task_id)
    except SmsTask.DoesNotExist:
        return

    # 标记为执行中
    task.status = 'running'
    task.started_at = timezone.now()
    task.save(update_fields=['status', 'started_at'])

    # 查询目标会员
    if task.target_group == 'all_active':
        members = Member.objects.filter(status='active')
    elif task.target_group == 'specific_company':
        members = Member.objects.filter(
            status='active', company__icontains=task.target_company
        )
    else:
        members = Member.objects.filter(status='active')

    task.total_count = members.count()
    task.save(update_fields=['total_count'])

    sent = 0
    failed = 0

    for member in members.iterator():
        try:
            # 渲染短信内容
            content = task.template.render(member)

            # TODO: 调用真实短信服务商 API
            # 当前为模拟发送，集成后替换此处
            _mock_send_sms(member.phone, content)

            SmsLog.objects.create(
                task=task,
                member=member,
                phone=member.phone,
                content=content,
                status='success',
            )
            sent += 1

        except Exception as e:
            SmsLog.objects.create(
                task=task,
                member=member,
                phone=member.phone,
                content='',
                status='failed',
                error_message=str(e),
            )
            failed += 1

    # 完成任务
    task.status = 'done' if failed == 0 else 'partial'
    task.sent_count = sent
    task.failed_count = failed
    task.finished_at = timezone.now()
    task.save(update_fields=['status', 'sent_count', 'failed_count', 'finished_at'])


def _mock_send_sms(phone: str, content: str):
    """
    模拟短信发送（开发阶段占位）
    实际部署时替换为阿里云短信 SDK / 腾讯云短信 SDK
    """
    import logging
    logging.getLogger('emis.sms').info(f'[MOCK SMS] → {phone}: {content[:30]}...')


# ============================================================
# 模块四：磁盘文件对齐任务
# ============================================================

@shared_task(bind=True, name='standards.align_disk_files_task')
def align_disk_files_task(self):
    """
    扫描磁盘阵列并与数据库clean_id对齐，更新到 disk_filename 字段，并在缓存中维护执行状态
    """
    import os
    from django.core.cache import cache
    from django.utils import timezone
    from standards.models import Standard

    # 1. 写入运行状态
    cache.set('scan_pdf_sync_task', {
        'status': 'running',
        'started_at': timezone.now().strftime("%Y-%m-%d %H:%M:%S")
    }, timeout=3600)

    try:
        from django.conf import settings
        shared_root = getattr(settings, 'SHARED_DISK_ROOT', r"Y:\磁盘阵列\标准文件下载\企标下载")
        target_dir = os.path.join(shared_root, "整合")
        
        if not os.path.exists(target_dir):
            err_msg = f"找不到目标磁盘阵列路径: {target_dir}"
            cache.set('scan_pdf_sync_task', {'status': 'failed', 'error': err_msg}, timeout=3600)
            return {"success": False, "matched_count": 0, "error": err_msg}

        try:
            disk_files = [f for f in os.listdir(target_dir) if f.lower().endswith('.pdf')]
        except Exception as e:
            err_msg = f"读取目录失败: {str(e)}"
            cache.set('scan_pdf_sync_task', {'status': 'failed', 'error': err_msg}, timeout=3600)
            return {"success": False, "matched_count": 0, "error": err_msg}

        def normalize(s):
            return "".join(c for c in s if c.isalnum()).lower() if s else ""

        file_norms = [(f, normalize(f)) for f in disk_files]
        
        # 优化1：避免一次性加载所有记录导致内存溢出 (OOM)，只查询需要的字段并使用游标按块流式获取
        standards = Standard.objects.only('id', 'clean_id', 'pdf_file').iterator(chunk_size=10000)
        
        success_count = 0
        updates = []

        for std in standards:
            if not std.clean_id:
                continue
            
            clean_norm = normalize(std.clean_id)
            if not clean_norm:
                continue
            
            matched_file = None
            for filename, fnorm in file_norms:
                if clean_norm in fnorm:
                    matched_file = filename
                    break
            
            if matched_file:
                relative_path = f"整合/{matched_file}"
                if std.pdf_file.name != relative_path:
                    std.pdf_file.name = relative_path
                    updates.append(std)
                success_count += 1
                
            # 优化2：每积攒 1000 条记录执行一次批量更新，极大减少数据库 I/O 压力
            if len(updates) >= 1000:
                Standard.objects.bulk_update(updates, ['pdf_file'])
                updates = []

        # 将剩余未满 1000 条的记录更新掉
        if updates:
            Standard.objects.bulk_update(updates, ['pdf_file'])

        # 2. 写入成功结果
        cache.set('scan_pdf_sync_task', {
            'status': 'done',
            'matched_count': success_count,
            'finished_at': timezone.now().strftime("%Y-%m-%d %H:%M:%S")
        }, timeout=3600)

        return {"success": True, "matched_count": success_count}

    except Exception as e:
        cache.set('scan_pdf_sync_task', {
            'status': 'failed',
            'error': str(e)
        }, timeout=3600)
        raise self.retry(exc=e, countdown=5, max_retries=2)


@shared_task(bind=True, name='standards.import_standards_and_references')
def import_standards_and_references_task(self, file_path: str, task_token: str):
    """
    异步解耦导入任务：解析企业标准与规范性引用混合表，并利用事务完成拆分写入
    """
    import os
    import pandas as pd
    from django.core.cache import cache
    from django.db import transaction
    from django.db.models import F
    from django.utils import timezone
    from companies.models import Company
    from standards.models import Standard, NormativeReference
    from standards.services import generate_clean_id, scan_and_align_pdf_assets

    # 1. 初始化任务状态缓存
    cache.set(f'import_task_{task_token}', {
        'status': 'running',
        'progress': 0,
        'success_count': 0,
        'failed_count': 0,
        'errors': []
    }, timeout=86400)

    errors = []
    success_count = 0

    try:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"暂存的导入文件未找到: {file_path}")

        df = pd.read_excel(file_path)
        total_rows = len(df)

        if total_rows == 0:
            raise ValueError("Excel 数据为空")

        # 归一化表头匹配
        headers_mapping = {
            'std_no': ['企标编号*', '企标编号', '标准编号*', '标准编号', '企标号'],
            'std_title': ['企标名称*', '企标名称', '标准名称*', '标准名称', '企标名'],
            'company_name': ['起草单位*', '起草单位', '起草单位/企业名称*', '起草单位/企业名称', '公司名称'],
            'credit_code': ['统一社会信用代码*', '统一社会信用代码', '信用代码*', '信用代码'],
            'cited_no': ['引用的国标/行标编号*', '引用的国标/行标编号', '被引用标准号*', '被引用标准号', '引用的标准号'],
            'latest_no': ['最新标准号', '最新被引用标准号']
        }

        # 映射实际列名
        actual_cols = {}
        for key, aliases in headers_mapping.items():
            for alias in aliases:
                if alias in df.columns:
                    actual_cols[key] = alias
                    break

        # 检查必要列是否具备
        required_keys = ['std_no', 'std_title', 'company_name', 'credit_code', 'cited_no']
        missing_cols = [k for k in required_keys if k not in actual_cols]
        if missing_cols:
            raise ValueError(f"Excel 格式不匹配，缺失核心必要列，未匹配键: {missing_cols}")

        col_std_no = actual_cols['std_no']
        col_std_title = actual_cols['std_title']
        col_company_name = actual_cols['company_name']
        col_credit_code = actual_cols['credit_code']
        col_cited_no = actual_cols['cited_no']
        col_latest_no = actual_cols.get('latest_no')

        # 2. 循环遍历各行
        for idx, row in df.iterrows():
            row_idx = idx + 2  # Excel 行号以 2 开始

            # 每处理 5% 更新一次进度以避免过频的缓存操作
            current_progress = int((idx + 1) / total_rows * 95)  # 留 5% 给后置处理
            if idx % max(1, int(total_rows / 20)) == 0:
                cache.set(f'import_task_{task_token}', {
                    'status': 'running',
                    'progress': current_progress,
                    'success_count': success_count,
                    'failed_count': len(errors),
                    'errors': errors
                }, timeout=86400)

            # 获取当前行字段
            std_no = str(row.get(col_std_no, '')).strip() if pd.notna(row.get(col_std_no)) else ''
            std_title = str(row.get(col_std_title, '')).strip() if pd.notna(row.get(col_std_title)) else ''
            company_name = str(row.get(col_company_name, '')).strip() if pd.notna(row.get(col_company_name)) else ''
            credit_code = str(row.get(col_credit_code, '')).strip() if pd.notna(row.get(col_credit_code)) else ''
            cited_no = str(row.get(col_cited_no, '')).strip() if pd.notna(row.get(col_cited_no)) else ''
            latest_no = str(row.get(col_latest_no, '')) if col_latest_no and pd.notna(row.get(col_latest_no)) else ''
            latest_no = latest_no.strip()

            # 数据完整性必填校验
            if not std_no or std_no == 'nan':
                errors.append({'row': row_idx, 'reason': "企标编号不能为空"})
                continue
            if not std_title or std_title == 'nan':
                errors.append({'row': row_idx, 'reason': "企标名称不能为空"})
                continue
            if not company_name or company_name == 'nan':
                errors.append({'row': row_idx, 'reason': "起草单位不能为空"})
                continue
            if not credit_code or credit_code == 'nan':
                errors.append({'row': row_idx, 'reason': "统一社会信用代码不能为空"})
                continue
            if not cited_no or cited_no == 'nan':
                errors.append({'row': row_idx, 'reason': "引用的国标/行标编号不能为空"})
                continue

            # 使用行级数据库事务（原子性写入主表+子表）
            try:
                with transaction.atomic():
                    # A. 查找或建档起草企业
                    company, _ = Company.objects.get_or_create(
                        credit_code=credit_code,
                        defaults={
                            'name': company_name,
                            'status': 'active'
                        }
                    )

                    # B. 查找或建档企业标准主表
                    clean_id = generate_clean_id(std_no)
                    standard, created_std = Standard.objects.get_or_create(
                        standard_no=std_no,
                        defaults={
                            'clean_id': clean_id,
                            'title': std_title,
                            'company': company,
                            'type': 'enterprise',
                            'is_parsed': 'references_parsed'
                        }
                    )

                    if not created_std:
                        # 联动更新主表状态为“已完成引用解析”
                        if standard.is_parsed == 'unparsed':
                            standard.is_parsed = 'references_parsed'
                            standard.save(update_fields=['is_parsed'])

                    # C. 对齐系统中已有的被引标准
                    cited_std = Standard.objects.filter(standard_no=cited_no).first()

                    # D. 写入关联引用记录明细
                    ref, created_ref = NormativeReference.objects.get_or_create(
                        source_standard=standard,
                        cited_standard_no=cited_no,
                        defaults={
                            'cited_standard': cited_std,
                            'latest_standard_no': latest_no or cited_no
                        }
                    )

                    if created_ref:
                        # 累加被引统计计数
                        if cited_std:
                            Standard.objects.filter(pk=cited_std.pk).update(citation_count=F('citation_count') + 1)
                    else:
                        # 如已存在则安全更新最新标准号
                        if latest_no and ref.latest_standard_no != latest_no:
                            ref.latest_standard_no = latest_no
                            ref.save(update_fields=['latest_standard_no'])

                success_count += 1

            except Exception as row_err:
                errors.append({'row': row_idx, 'reason': f"数据库写入失败: {str(row_err)}"})

        # 3. 后置扫盘 PDF 对齐
        try:
            scan_and_align_pdf_assets()
        except Exception:
            pass

        # 4. 成功完结更新缓存
        cache.set(f'import_task_{task_token}', {
            'status': 'done',
            'progress': 100,
            'success_count': success_count,
            'failed_count': len(errors),
            'errors': errors
        }, timeout=86400)

        # 5. 清理临时上传的 Excel
        if os.path.exists(file_path):
            os.remove(file_path)

    except Exception as e:
        cache.set(f'import_task_{task_token}', {
            'status': 'failed',
            'progress': 100,
            'error': str(e),
            'success_count': success_count,
            'failed_count': len(errors),
            'errors': errors
        }, timeout=86400)
        
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass


