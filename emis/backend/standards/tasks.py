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
    from standards.utils.archive_helpers import create_zip_from_standards
    import os

    def _update_progress(progress: int, message: str = ''):
        """向缓存写入当前进度，供前端轮询读取"""
        cache.set(f'zip_task_{download_token}', {
            'status': 'running',
            'progress': progress,
            'message': message,
        }, timeout=3600)

    try:
        # 阶段 1：任务开始 (0%)
        _update_progress(0, '正在准备打包任务...')

        # 阶段 2：开始 I/O 读取文件 (30%)
        _update_progress(30, f'正在读取 {len(standard_ids)} 个标准文件...')
        zip_bytes = create_zip_from_standards(standard_ids, include_excel=include_excel)

        # 阶段 3：写入磁盘 (80%)
        _update_progress(80, '正在写入 ZIP 文件到磁盘...')
        from django.conf import settings
        temp_dir = settings.MEDIA_ROOT / 'temp_zips'
        temp_dir.mkdir(parents=True, exist_ok=True)
        zip_path = temp_dir / f'{download_token}.zip'

        with open(zip_path, 'wb') as f:
            f.write(zip_bytes)

        # 阶段 4：完成 (100%)
        cache.set(f'zip_task_{download_token}', {
            'status': 'done',
            'progress': 100,
            'download_url': f'/api/client/standards/pack/download/?token={download_token}',
            'file_size': len(zip_bytes),
        }, timeout=3600)

    except Exception as exc:
        cache.set(f'zip_task_{download_token}', {
            'status': 'failed',
            'progress': 0,
            'error': str(exc),
        }, timeout=3600)
        self.update_state(
            state='FAILURE',
            meta={
                'exc_type': type(exc).__name__,
                'exc_message': str(exc)
            }
        )
        raise exc


@shared_task(bind=True, name='standards.pack_enterprises_zip')
def pack_enterprises_zip_task(self, enterprise_ids: list = None, filters: dict = None, export_all: bool = False, uuid_str: str = ""):
    """
    异步打包选中企业或检索条件名下的所有 PDF 企标文件。
    最大限制 200 家企业。
    目录结构：企业名称/标准号_标准名称.pdf
    """
    from standards.utils.archive_helpers import pack_enterprises_to_zip
    try:
        return pack_enterprises_to_zip(
            enterprise_ids=enterprise_ids,
            filters=filters,
            export_all=export_all,
            uuid_str=uuid_str
        )
    except Exception as exc:
        self.update_state(
            state='FAILURE',
            meta={
                'exc_type': type(exc).__name__,
                'exc_message': str(exc)
            }
        )
        raise exc




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
        updated_ids = []

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
                    updated_ids.append(std.id)
                success_count += 1
                
            # 优化2：每积攒 1000 条记录执行一次批量更新，极大减少数据库 I/O 压力
            if len(updates) >= 1000:
                Standard.objects.bulk_update(updates, ['pdf_file'])
                for std_id in updated_ids:
                    parse_standard_pdf_task.delay(std_id)
                updates = []
                updated_ids = []

        # 将剩余未满 1000 条的记录更新掉
        if updates:
            Standard.objects.bulk_update(updates, ['pdf_file'])
            for std_id in updated_ids:
                parse_standard_pdf_task.delay(std_id)

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

        # 4. 成功完结，精准失效搜索缓存（保留任务进度 key 不受影响）
        try:
            from standards.models import _invalidate_search_cache
            _invalidate_search_cache()
        except Exception:
            pass

        cache.set(f'import_task_{task_token}', {
            'status': 'done',
            'progress': 100,
            'success_count': success_count,
            'failed_count': len(errors),
            'errors': errors
        }, timeout=86400)

        # 5. 清理临时上传的 Excel
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass

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


def extract_dates_from_text(first_page_text: str):
    """
    从标准封面页文本中提取发布日期和实施日期。
    
    优化：
    1. 在按行过滤时，自动排除包含时分的时间戳行（如 "公开 2018年07月16日 09点39分"），过滤水印。
    2. 发布日期的关键字移除 "公开"，防止误识别国家/企业标准平台水印上的公示/公开时间。
    """
    import datetime
    import re

    extracted_publish_date = None
    extracted_implement_date = None

    # ── 预处理：修正 PDF/OCR 常见误识别字符 ──────────────────
    def _normalize_date_text(text):
        # 全角数字转半角
        result = text.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
        # 全角连字符 → 半角
        result = result.replace('－', '-').replace('—', '-')
        # 将紧靠数字的大写 O 替换为 0
        result = re.sub(r'(?<=\d)O(?=\d)', '0', result)
        result = re.sub(r'(?<=\d)O(?!\d)', '0', result)
        result = re.sub(r'(?<!\d)O(?=\d)', '0', result)
        # 将紧靠数字的小写 l 替换为 1
        result = re.sub(r'(?<=\d)l(?=\d)', '1', result)
        result = re.sub(r'(?<=\d)l(?!\d)', '1', result)
        result = re.sub(r'(?<!\d)l(?=\d)', '1', result)
        return result

    norm_text = _normalize_date_text(first_page_text)

    # ── 预处理：按行分割，过滤水印 ──────────────────────
    lines = norm_text.split('\n')
    clean_lines = []
    for line in lines:
        if '公共服务平台' in line or '企业标准信息' in line:
            continue
        # 过滤时分秒等时间戳字样，判定为水印/打印记录，而非标准发布/实施日期
        if '点' in line and '分' in line:
            continue
        clean_lines.append(line)

    # ── 提取正则 ──────────────────────
    date_pattern = r'(\d{4})\s*[-/年.·]\s*(\d{1,2})\s*[-/月.·]\s*(\d{1,2})\s*日?'

    def extract_closest_date(line_text, keyword):
        """在行内提取与关键字最近的日期"""
        if keyword not in line_text:
            return None

        matches = list(re.finditer(date_pattern, line_text))
        if not matches:
            return None

        kw_idx = line_text.find(keyword)
        best_candidate = None
        min_dist = float('inf')

        for match in matches:
            try:
                y, m, d = int(match.group(1)), int(match.group(2)), int(match.group(3))
                if 1980 <= y <= 2099 and 1 <= m <= 12 and 1 <= d <= 31:
                    match_center = (match.start() + match.end()) / 2
                    dist = abs(match_center - kw_idx)
                    if dist < min_dist:
                        min_dist = dist
                        best_candidate = datetime.date(y, m, d)
            except ValueError:
                pass

        return best_candidate

    # ── 行级扫描：发布日期 / 实施日期 ──────────────────────
    for line in clean_lines:
        # 只保留“发布”和“公布”，不再匹配“公开”，避免被平台水印“公开 YYYY年MM月DD日”干扰
        if '发布' in line or '公布' in line:
            kw = '发布' if '发布' in line else '公布'
            d = extract_closest_date(line, kw)
            if d and not extracted_publish_date:
                extracted_publish_date = d

        if '实施' in line or '施行' in line:
            kw = '实施' if '实施' in line else '施行'
            d = extract_closest_date(line, kw)
            if d and not extracted_implement_date:
                extracted_implement_date = d

    return extracted_publish_date, extracted_implement_date


@shared_task(bind=True, name='standards.parse_standard_pdf')
def parse_standard_pdf_task(self, standard_id: int, force: bool = False):
    """
    异步提取 PDF 文本并批量存入 StandardContent 表
    """
    import os
    from django.conf import settings
    from django.db import transaction
    from standards.models import Standard, StandardContent

    try:
        standard = Standard.objects.get(id=standard_id)
    except Standard.DoesNotExist:
        return f"Standard {standard_id} not found."

    # 仅企标才需要全文解析，双重校验
    if standard.type != 'enterprise':
        return f"Standard {standard.standard_no} is not an enterprise standard. Skipped."

    shared_root = getattr(settings, 'SHARED_DISK_ROOT', r"Y:\磁盘阵列\标准文件下载\企标下载")
    file_path = None

    # 1. 优先策略：先尝试 disk_filename
    if standard.disk_filename:
        norm_disk_filename = standard.disk_filename.replace('\\', '/')
        disk_file_path = os.path.join(shared_root, norm_disk_filename)
        if os.path.exists(disk_file_path):
            file_path = disk_file_path

    # 2. 降级策略：尝试 pdf_file
    if not file_path and standard.pdf_file:
        rel_path = standard.pdf_file.name.replace('\\', '/')
        # 网络共享盘
        disk_file_path = os.path.join(shared_root, rel_path)
        if os.path.exists(disk_file_path):
            file_path = disk_file_path
        else:
            # 本地 media 物理目录
            media_file_path = os.path.join(settings.MEDIA_ROOT, rel_path)
            if os.path.exists(media_file_path):
                file_path = media_file_path
            elif rel_path.startswith('media/'):
                clean_path = rel_path.replace('media/', '', 1)
                clean_file_path = os.path.join(settings.MEDIA_ROOT, clean_path)
                if os.path.exists(clean_file_path):
                    file_path = clean_file_path

    if not file_path:
        return f"Standard {standard.standard_no} has no valid PDF file."

    # 3. 提取 PDF 文本内容
    pages_text = []
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(file_path)
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            pages_text.append((page_num + 1, page.get_text()))
        doc.close()
    except ImportError:
        import pdfplumber
        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                pages_text.append((page_num + 1, text))

    if not pages_text:
        return f"No text extracted from Standard {standard.standard_no} PDF."

    # 4. 提取第一页文本，必要时 OCR 降级处理
    import re
    import datetime

    first_page_text = pages_text[0][1] if pages_text else ""

    # 若第一页文本极短（< 10 字符），判定为扫描图片 PDF，启动 OCR 降级
    if len(first_page_text.strip()) < 10:
        ocr_text = ""
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                if pdf.pages:
                    pil_image = pdf.pages[0].to_image(resolution=200).original
            # 优先使用 easyocr
            try:
                import easyocr
                reader = easyocr.Reader(['ch_sim', 'en'], gpu=False)
                results = reader.readtext(pil_image)
                ocr_text = "\n".join([res[1] for res in results])
            except ImportError:
                pass

            # 降级使用 pytesseract
            if not ocr_text:
                try:
                    import pytesseract
                    ocr_text = pytesseract.image_to_string(pil_image, lang='chi_sim+eng')
                except ImportError:
                    pass

            if ocr_text:
                # 将 OCR 识别结果合并回第一页
                pages_text[0] = (pages_text[0][0], ocr_text)
                first_page_text = ocr_text
        except Exception as ocr_err:
            # OCR 失败不影响主流程，记录日志后继续
            import logging
            logging.getLogger('standards').warning(
                f"OCR fallback failed for {standard.standard_no}: {ocr_err}"
            )

    # 5. 日期正则提取（发布日期 / 实施日期）
    from standards.tasks import extract_dates_from_text
    extracted_publish_date, extracted_implement_date = extract_dates_from_text(first_page_text)

    # 6. 批量保存全文内容并回填日期字段
    try:
        with transaction.atomic():
            # 先删除旧内容
            StandardContent.objects.filter(standard=standard).delete()

            # 批量创建新内容
            content_objects = [
                StandardContent(
                    standard=standard,
                    page_number=pnum,
                    content=text
                )
                for pnum, text in pages_text
            ]
            StandardContent.objects.bulk_create(content_objects)

            # 如果企标缺失发布日期或实施日期，自动用提取到的日期填充并更新
            updated_fields = []
            if extracted_publish_date and (not standard.publish_date or force):
                standard.publish_date = extracted_publish_date
                updated_fields.append('publish_date')
            if extracted_implement_date and (not standard.implement_date or force):
                standard.implement_date = extracted_implement_date
                updated_fields.append('implement_date')

            if updated_fields:
                standard.save(update_fields=updated_fields)
                # 精准失效搜索缓存，不影响其他业务缓存
                from standards.models import _invalidate_search_cache
                try:
                    _invalidate_search_cache()
                except Exception:
                    pass

        return f"Successfully parsed {len(pages_text)} pages for Standard {standard.standard_no}."
    except Exception as e:
        raise self.retry(exc=e, countdown=5, max_retries=2)


@shared_task(bind=False, name='standards.auto_scan_missing_dates')
def auto_scan_missing_dates_task():
    """
    定时任务：自动检测发布时间缺失的企标并触发 PDF 扫描提取

    运行时机：
      - Celery Beat 每 30 分钟自动调度
      - 后台管理员也可通过 Django shell 手动触发

    处理逻辑：
      1. 查询所有 publish_date 为空的企标记录
      2. 过滤出在磁盘/共享盘上存在对应 PDF 文件的记录
      3. 对每个匹配记录，异步触发 parse_standard_pdf_task 重新扫描首页
    """
    import os
    import logging
    from django.conf import settings
    from standards.models import Standard

    logger = logging.getLogger('standards')
    shared_root = getattr(settings, 'SHARED_DISK_ROOT', r'Y:\磁盘阵列\标准文件下载\企标下载')

    # --- 查询缺失发布时间的企业标准（有 pdf_file 或 disk_filename 之一即可） ---
    from django.db.models import Q
    candidates = Standard.objects.filter(
        type='enterprise',
        publish_date__isnull=True
    ).filter(
        Q(pdf_file__isnull=False) | Q(disk_filename__isnull=False)
    ).exclude(
        pdf_file='', disk_filename=''
    ).values('id', 'standard_no', 'pdf_file', 'disk_filename')

    dispatched = 0
    skipped = 0

    for std in candidates:
        file_path = None
        std_id = std['id']
        std_no = std['standard_no']
        disk_fn = (std['disk_filename'] or '').replace('\\', '/')
        pdf_fn = ''
        if std['pdf_file']:
            try:
                # pdf_file 是 FieldFile，values() 拿到的是字符串
                pdf_fn = str(std['pdf_file']).replace('\\', '/')
            except Exception:
                pass

        # 优先 disk_filename
        if disk_fn:
            p = os.path.join(shared_root, disk_fn)
            if os.path.exists(p):
                file_path = p

        # 降级 pdf_file
        if not file_path and pdf_fn:
            for base in [shared_root, str(settings.MEDIA_ROOT)]:
                p = os.path.join(base, pdf_fn)
                if os.path.exists(p):
                    file_path = p
                    break
            if not file_path and pdf_fn.startswith('media/'):
                p = os.path.join(str(settings.MEDIA_ROOT), pdf_fn[len('media/'):])
                if os.path.exists(p):
                    file_path = p

        if file_path:
            # 异步触发 PDF 解析（包含日期提取逻辑）
            parse_standard_pdf_task.delay(std_id)
            dispatched += 1
            logger.info(f'[auto_scan] Dispatched PDF scan for [{std_no}] (id={std_id})')
        else:
            skipped += 1

    summary = (
        f'[auto_scan_missing_dates] Done: dispatched={dispatched}, '
        f'no_pdf_skipped={skipped}'
    )
    logger.info(summary)
    return summary


@shared_task(bind=False, name='standards.force_reparse_all_dates_task')
def force_reparse_all_dates_task():
    """
    全量重解析所有存在 PDF 文件的企标的发布日期和实施日期。
    """
    import os
    import logging
    from django.conf import settings
    from django.db.models import Q
    from standards.models import Standard

    logger = logging.getLogger('standards')
    shared_root = getattr(settings, 'SHARED_DISK_ROOT', r'Y:\磁盘阵列\标准文件下载\企标下载')

    # 查询所有存在 PDF 文件的企业标准
    candidates = Standard.objects.filter(
        type='enterprise'
    ).filter(
        Q(pdf_file__isnull=False) | Q(disk_filename__isnull=False)
    ).exclude(
        pdf_file='', disk_filename=''
    ).values('id', 'standard_no', 'pdf_file', 'disk_filename')

    dispatched = 0
    skipped = 0

    for std in candidates:
        file_path = None
        std_id = std['id']
        std_no = std['standard_no']
        disk_fn = (std['disk_filename'] or '').replace('\\', '/')
        pdf_fn = ''
        if std['pdf_file']:
            try:
                # pdf_file 是 FieldFile，values() 拿到的是字符串
                pdf_fn = str(std['pdf_file']).replace('\\', '/')
            except Exception:
                pass

        # 优先 disk_filename
        if disk_fn:
            p = os.path.join(shared_root, disk_fn)
            if os.path.exists(p):
                file_path = p

        # 降级 pdf_file
        if not file_path and pdf_fn:
            for base in [shared_root, str(settings.MEDIA_ROOT)]:
                p = os.path.join(base, pdf_fn)
                if os.path.exists(p):
                    file_path = p
                    break
            if not file_path and pdf_fn.startswith('media/'):
                p = os.path.join(str(settings.MEDIA_ROOT), pdf_fn[len('media/'):])
                if os.path.exists(p):
                    file_path = p

        if file_path:
            # 异步触发 PDF 解析，force=True 覆盖现有日期
            parse_standard_pdf_task.delay(std_id, force=True)
            dispatched += 1
            logger.info(f'[force_reparse] Dispatched PDF scan for [{std_no}] (id={std_id})')
        else:
            skipped += 1

    summary = (
        f'[force_reparse_all_dates_task] Done: dispatched={dispatched}, '
        f'no_pdf_skipped={skipped}'
    )
    logger.info(summary)
    return summary
