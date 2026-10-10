"""
standards.services_list_match — 外部清单智能降级匹配与打包服务层

功能：
  1. Excel 表头智能嗅探与行提取
  2. 标准号优先 + 标准名称降级两阶段匹配
  3. 歧义多重版本择优收敛（有效PDF优先 -> 现行active优先 -> 最新发布日期倒序）
  4. 审计与对账清单 Excel 生成
  5. 规范重命名 ZIP 压缩打包
"""

import io
import os
import re
import zipfile
import logging
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from django.conf import settings
from django.db.models import Q, Case, When, Value, IntegerField

from standards.models import Standard
from standards.services import generate_clean_id

logger = logging.getLogger('standards.services_list_match')

MAX_LIST_MATCH_LIMIT = 500


def clean_standard_code(code: str) -> str:
    """清洗标准号字符串，去除全角符号、多余空格"""
    if not code:
        return ''
    s = str(code).strip()
    s = s.replace('／', '/').replace('—', '-').replace('–', '-')
    s = re.sub(r'\s+', ' ', s)
    return s


def sanitize_filename(name: str) -> str:
    """清洗文件名中的 Windows 非法字符"""
    if not name:
        return ''
    s = str(name).strip()
    s = re.sub(r'[\\/*?:"<>|\r\n\t]', '_', s)
    return s[:150]


try:
    import xlrd
except ImportError:
    xlrd = None


def _is_xls_bytes(file_bytes: bytes) -> bool:
    """检查是否为老版本 .xls (Compound File Binary Format / OLE2)"""
    return file_bytes.startswith(b'\xd0\xcf\x11\xe0')


def sniff_excel_structure(file_bytes: bytes):
    """
    智能嗅探 Excel 文件的表头与列结构。
    支持 .xlsx 与 .xls 双格式。
    扫描前 5 行，正则匹配标准编号列与标准名称列。
    """
    sheet_names = []
    rows = []
    total_data_rows = 0

    if _is_xls_bytes(file_bytes):
        if not xlrd:
            raise ValueError("当前服务缺少 xlrd 库支持，无法解析 .xls 文件，请转换为 .xlsx 后重试")
        try:
            wb = xlrd.open_workbook(file_contents=file_bytes)
            sheet_names = wb.sheet_names()
            if not sheet_names:
                raise ValueError("Excel 文件中没有有效的工作表 (Sheet)")
            sheet = wb.sheet_by_name(sheet_names[0])
            for r_idx in range(min(15, sheet.nrows)):
                row_vals = []
                for c_idx in range(sheet.ncols):
                    val = sheet.cell_value(r_idx, c_idx)
                    if isinstance(val, float) and val.is_integer():
                        val = int(val)
                    row_vals.append(str(val).strip() if val is not None else '')
                rows.append(row_vals)
            # 计算总数据行数
            total_raw_rows = sheet.nrows
        except Exception as e:
            raise ValueError(f"解析 .xls 文件失败: {str(e)}")
    else:
        # 默认尝试 openpyxl 解析 .xlsx
        try:
            wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
            sheet_names = wb.sheetnames
            if not sheet_names:
                raise ValueError("Excel 文件中没有有效的工作表 (Sheet)")
            sheet = wb[sheet_names[0]]
            for idx, row in enumerate(sheet.iter_rows(values_only=True)):
                if idx >= 15:
                    break
                rows.append([str(c).strip() if c is not None else '' for c in row])
            wb.close()

            wb2 = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
            sheet2 = wb2[sheet_names[0]]
            total_raw_rows = sheet2.max_row or 0
            wb2.close()
        except Exception as e:
            # 若 openpyxl 解析失败且可能为 xls，尝试 xlrd 兜底
            if xlrd:
                try:
                    wb = xlrd.open_workbook(file_contents=file_bytes)
                    sheet_names = wb.sheet_names()
                    sheet = wb.sheet_by_name(sheet_names[0])
                    for r_idx in range(min(15, sheet.nrows)):
                        row_vals = []
                        for c_idx in range(sheet.ncols):
                            val = sheet.cell_value(r_idx, c_idx)
                            if isinstance(val, float) and val.is_integer():
                                val = int(val)
                            row_vals.append(str(val).strip() if val is not None else '')
                        rows.append(row_vals)
                    total_raw_rows = sheet.nrows
                except Exception:
                    raise ValueError(f"解析 Excel 失败（请确保文件为有效 .xlsx 或 .xls 格式）: {str(e)}")
            else:
                raise ValueError(f"解析 Excel 失败（请确保文件为有效 .xlsx 格式）: {str(e)}")

    if not rows:
        raise ValueError("Excel 表格为空")

    # 寻找最佳表头行（前 5 行中非空单元格最多且包含特征词的一行）
    header_row_idx = 0
    std_no_regex = re.compile(r'(标准.*号|企标.*号|编号|代码|备案号|std.*no|code)', re.I)
    title_regex = re.compile(r'(标准.*名称|企标.*名称|品名|产品.*名称|中文.*名称|名称|title|name)', re.I)

    best_score = -1
    for r_idx, row in enumerate(rows[:5]):
        score = 0
        for cell in row:
            if std_no_regex.search(cell):
                score += 10
            if title_regex.search(cell):
                score += 10
            if cell:
                score += 1
        if score > best_score:
            best_score = score
            header_row_idx = r_idx

    header_cells = rows[header_row_idx]
    headers = []
    suggested_std_no_col = ''
    suggested_title_col = ''

    for c_idx, cell in enumerate(header_cells):
        col_letter = get_column_letter(c_idx + 1)
        label = cell if cell else f"列 {col_letter}"
        display_name = f"{col_letter}列: {label}"
        headers.append({
            'index': c_idx,
            'letter': col_letter,
            'label': label,
            'display': display_name
        })

        if not suggested_std_no_col and std_no_regex.search(cell):
            suggested_std_no_col = col_letter
        elif not suggested_title_col and title_regex.search(cell):
            suggested_title_col = col_letter

    total_data_rows = max(0, total_raw_rows - (header_row_idx + 1))

    return {
        'sheet_names': sheet_names,
        'current_sheet': sheet_names[0],
        'header_row_index': header_row_idx,
        'headers': headers,
        'suggested_std_no_col': suggested_std_no_col,
        'suggested_title_col': suggested_title_col,
        'total_rows': total_data_rows
    }


def extract_items_from_excel(file_bytes: bytes, sheet_name=None, std_no_col_idx=None, title_col_idx=None, header_row_idx=0):
    """
    根据用户选定或自动识别的列索引提取标准数据项，支持 .xlsx 与 .xls
    """
    items = []

    if _is_xls_bytes(file_bytes) or (xlrd and not file_bytes.startswith(b'PK')):
        if not xlrd:
            raise ValueError("当前服务缺少 xlrd 库支持，无法读取 .xls 文件")
        wb = xlrd.open_workbook(file_contents=file_bytes)
        sheet = wb.sheet_by_name(sheet_name) if sheet_name and sheet_name in wb.sheet_names() else wb.sheet_by_index(0)

        for r_idx in range(sheet.nrows):
            if r_idx <= header_row_idx:
                continue
            if len(items) >= MAX_LIST_MATCH_LIMIT:
                break

            val_no = ''
            val_title = ''
            if std_no_col_idx is not None and 0 <= std_no_col_idx < sheet.ncols:
                cell_val = sheet.cell_value(r_idx, std_no_col_idx)
                if isinstance(cell_val, float) and cell_val.is_integer():
                    cell_val = int(cell_val)
                val_no = str(cell_val).strip() if cell_val is not None else ''

            if title_col_idx is not None and 0 <= title_col_idx < sheet.ncols:
                cell_val = sheet.cell_value(r_idx, title_col_idx)
                if isinstance(cell_val, float) and cell_val.is_integer():
                    cell_val = int(cell_val)
                val_title = str(cell_val).strip() if cell_val is not None else ''

            if val_no or val_title:
                items.append({
                    'raw_no': val_no,
                    'raw_title': val_title
                })
        return items

    # 默认使用 openpyxl 解析 .xlsx
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    sheet = wb[sheet_name] if sheet_name and sheet_name in wb.sheetnames else wb.active

    for r_idx, row in enumerate(sheet.iter_rows(values_only=True)):
        if r_idx <= header_row_idx:
            continue
        if len(items) >= MAX_LIST_MATCH_LIMIT:
            break

        val_no = ''
        val_title = ''
        if std_no_col_idx is not None and 0 <= std_no_col_idx < len(row):
            cell_val = row[std_no_col_idx]
            val_no = str(cell_val).strip() if cell_val is not None else ''

        if title_col_idx is not None and 0 <= title_col_idx < len(row):
            cell_val = row[title_col_idx]
            val_title = str(cell_val).strip() if cell_val is not None else ''

        # 过滤完全为空的无效行
        if val_no or val_title:
            items.append({
                'raw_no': val_no,
                'raw_title': val_title
            })

    wb.close()
    return items


def pick_best_candidate(qs):
    """
    消歧策略：
    1. 有有效 PDF 优先
    2. 现行有效（status='active'）优先
    3. 最新发布日期倒序
    """
    annotated = qs.annotate(
        has_file_flag=Case(
            When(Q(pdf_file__isnull=False) & ~Q(pdf_file=''), then=Value(1)),
            When(Q(disk_filename__isnull=False) & ~Q(disk_filename=''), then=Value(1)),
            default=Value(0),
            output_field=IntegerField()
        ),
        is_active_flag=Case(
            When(status='active', then=Value(1)),
            default=Value(0),
            output_field=IntegerField()
        )
    ).order_by('-has_file_flag', '-is_active_flag', '-publish_date')

    return annotated.first()


def check_standard_has_pdf(std: Standard) -> bool:
    """真实核验标准是否有物理 PDF 文件"""
    shared_root = getattr(settings, 'SHARED_DISK_ROOT', r"Y:\磁盘阵列\标准文件下载\企标下载")

    if std.disk_filename:
        norm_disk = std.disk_filename.replace('\\', '/')
        if os.path.exists(os.path.join(shared_root, norm_disk)):
            return True

    if std.pdf_file and std.pdf_file.name:
        rel = std.pdf_file.name.replace('\\', '/')
        if os.path.exists(os.path.join(shared_root, rel)):
            return True
        if os.path.exists(os.path.join(settings.MEDIA_ROOT, rel)):
            return True
        if rel.startswith('media/'):
            clean_rel = rel.replace('media/', '', 1)
            if os.path.exists(os.path.join(settings.MEDIA_ROOT, clean_rel)):
                return True

    # 兜底：数据库非空标记
    if std.disk_filename or (std.pdf_file and std.pdf_file.name):
        return True

    return False


def match_single_item(raw_no: str, raw_title: str):
    """
    逐行标准双层降级匹配算法：
    1. 优先标准号匹配（clean_id 严格前缀与原始编号）
    2. 若未命中或标准号为空，降级至标准名称匹配
    3. 同名多重匹配消歧收敛
    """
    cleaned_no = clean_standard_code(raw_no)
    cleaned_title = str(raw_title).strip() if raw_title else ''

    candidate = None
    match_mode = 'not_found'

    # 第一层：标准号匹配
    if cleaned_no:
        clean_id_val = generate_clean_id(cleaned_no)
        # 精确或标准化 clean_id
        qs = Standard.objects.select_related('company').filter(type='enterprise').filter(
            Q(clean_id__iexact=clean_id_val) |
            Q(standard_no__iexact=cleaned_no) |
            Q(standard_no__iexact=clean_id_val)
        )
        if qs.exists():
            candidate = pick_best_candidate(qs)
            match_mode = 'std_no_exact'
        else:
            # 容错：去空格匹配
            no_compact = cleaned_no.replace(' ', '')
            qs2 = Standard.objects.select_related('company').filter(type='enterprise').filter(
                Q(clean_id__iexact=no_compact) | Q(standard_no__iexact=no_compact)
            )
            if qs2.exists():
                candidate = pick_best_candidate(qs2)
                match_mode = 'std_no_exact'

    # 第二层：名称降级匹配
    if not candidate and cleaned_title:
        qs_title = Standard.objects.select_related('company').filter(type='enterprise').filter(
            Q(title__iexact=cleaned_title)
        )
        if qs_title.exists():
            candidate = pick_best_candidate(qs_title)
            match_mode = 'title_fallback'
        else:
            # 去除首尾特殊标点符号后再试
            stripped_title = re.sub(r'^[《\(（]|[\)）》]$', '', cleaned_title)
            if stripped_title and stripped_title != cleaned_title:
                qs_title2 = Standard.objects.select_related('company').filter(type='enterprise', title__iexact=stripped_title)
                if qs_title2.exists():
                    candidate = pick_best_candidate(qs_title2)
                    match_mode = 'title_fallback'

    return candidate, match_mode


def match_items_batch(raw_items: list):
    """
    批量匹配主入口
    """
    truncated_items = raw_items[:MAX_LIST_MATCH_LIMIT]
    details = []
    matched_count = 0
    available_file_count = 0
    missing_file_count = 0
    not_found_count = 0

    for idx, item in enumerate(truncated_items):
        raw_no = item.get('raw_no', '')
        raw_title = item.get('raw_title', '')

        candidate, mode = match_single_item(raw_no, raw_title)

        if candidate:
            matched_count += 1
            has_pdf = check_standard_has_pdf(candidate)
            if has_pdf:
                available_file_count += 1
                status_code = mode  # 'std_no_exact' or 'title_fallback'
                status_text = '标准号精确命中' if mode == 'std_no_exact' else '标准名称降级命中'
            else:
                missing_file_count += 1
                status_code = 'matched_no_file'
                status_text = '命中但暂无PDF附件'

            company_name = candidate.company.name if candidate.company else '未知起草单位'
            details.append({
                'index': idx + 1,
                'input_no': raw_no,
                'input_title': raw_title,
                'status_code': status_code,
                'status_text': status_text,
                'standard_id': candidate.id,
                'matched_no': candidate.standard_no,
                'matched_title': candidate.title,
                'company_name': company_name,
                'publish_date': str(candidate.publish_date) if hasattr(candidate, 'publish_date') and candidate.publish_date else '-',
                'status_label': candidate.get_status_display() if hasattr(candidate, 'get_status_display') else candidate.status,
                'has_pdf': has_pdf
            })
        else:
            not_found_count += 1
            details.append({
                'index': idx + 1,
                'input_no': raw_no,
                'input_title': raw_title,
                'status_code': 'not_found',
                'status_text': '未收录该标准',
                'standard_id': None,
                'matched_no': '-',
                'matched_title': '-',
                'company_name': '-',
                'publish_date': '-',
                'status_label': '-',
                'has_pdf': False
            })

    return {
        'total_input': len(truncated_items),
        'matched_count': matched_count,
        'available_file_count': available_file_count,
        'missing_file_count': missing_file_count,
        'not_found_count': not_found_count,
        'details': details
    }


def generate_manifest_excel_bytes(details: list) -> bytes:
    """
    根据匹配明细生成格式典雅的 Excel 对账清单
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "企标匹配与下载对账清单"

    # 表头样式
    header_fill = PatternFill(start_color="00838F", end_color="00838F", fill_type="solid")
    header_font = Font(name="Microsoft YaHei", size=11, bold=True, color="FFFFFF")
    data_font = Font(name="Microsoft YaHei", size=10)
    center_align = Alignment(horizontal="center", vertical="center")
    left_align = Alignment(horizontal="left", vertical="center")

    thin_border = Border(
        left=Side(style='thin', color='E0E0E0'),
        right=Side(style='thin', color='E0E0E0'),
        top=Side(style='thin', color='E0E0E0'),
        bottom=Side(style='thin', color='E0E0E0')
    )

    headers = [
        "序号", "原始输入标准号", "原始输入标准名称", "匹配判定结果",
        "命中的标准编号", "命中的标准名称", "起草单位", "标准状态",
        "发布日期", "PDF文件归档状态"
    ]

    ws.append(headers)
    ws.row_dimensions[1].height = 28

    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_align

    # 填充数据行
    for r_idx, item in enumerate(details, start=2):
        has_pdf_str = "已打包/可下载" if item.get('has_pdf') else "缺电子档/未打包"
        row_vals = [
            item.get('index', r_idx - 1),
            item.get('input_no', ''),
            item.get('input_title', ''),
            item.get('status_text', ''),
            item.get('matched_no', ''),
            item.get('matched_title', ''),
            item.get('company_name', ''),
            item.get('status_label', ''),
            item.get('publish_date', ''),
            has_pdf_str
        ]
        ws.append(row_vals)
        ws.row_dimensions[r_idx].height = 22

        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=r_idx, column=col_idx)
            cell.font = data_font
            cell.border = thin_border
            if col_idx in [1, 4, 8, 9, 10]:
                cell.alignment = center_align
            else:
                cell.alignment = left_align

            # 特殊标记状态颜色
            if col_idx == 4:
                status_code = item.get('status_code')
                if status_code in ['std_no_exact', 'title_fallback']:
                    cell.font = Font(name="Microsoft YaHei", size=10, color="00796B", bold=True)
                elif status_code == 'matched_no_file':
                    cell.font = Font(name="Microsoft YaHei", size=10, color="E65100", bold=True)
                else:
                    cell.font = Font(name="Microsoft YaHei", size=10, color="D32F2F")

    # 自动列宽
    col_widths = [8, 22, 30, 20, 24, 32, 28, 12, 14, 18]
    for idx, width in enumerate(col_widths, start=1):
        ws.column_dimensions[get_column_letter(idx)].width = width

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def create_zip_from_list_matched(standard_ids: list, manifest_data: list = None) -> bytes:
    """
    打包已匹配的标准 PDF 文件，并规整化命名，自动嵌入审计 Excel 清单
    """
    standards = Standard.objects.select_related('company').filter(id__in=standard_ids)
    shared_root = getattr(settings, 'SHARED_DISK_ROOT', r"Y:\磁盘阵列\标准文件下载\企标下载")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for std in standards:
            file_path = None

            # 优先从共享磁盘获取
            if std.disk_filename:
                norm_disk = std.disk_filename.replace('\\', '/')
                disk_path = os.path.join(shared_root, norm_disk)
                if os.path.exists(disk_path):
                    file_path = disk_path

            # 降级使用 pdf_file
            if not file_path and std.pdf_file and std.pdf_file.name:
                rel = std.pdf_file.name.replace('\\', '/')
                disk_path = os.path.join(shared_root, rel)
                media_path = os.path.join(settings.MEDIA_ROOT, rel)
                if os.path.exists(disk_path):
                    file_path = disk_path
                elif os.path.exists(media_path):
                    file_path = media_path
                elif rel.startswith('media/'):
                    clean_rel = rel.replace('media/', '', 1)
                    alt_media = os.path.join(settings.MEDIA_ROOT, clean_rel)
                    if os.path.exists(alt_media):
                        file_path = alt_media

            if file_path:
                clean_no = sanitize_filename(std.standard_no)
                clean_tit = sanitize_filename(std.title)
                arcname = f"[{clean_no}] {clean_tit}.pdf" if clean_tit else f"[{clean_no}].pdf"
                try:
                    zf.write(file_path, arcname=arcname)
                except Exception as e:
                    logger.warning(f"清单打包写入单文件失败: std_id={std.id}, error={str(e)}")

        # 注入清单 Excel
        if manifest_data:
            try:
                manifest_bytes = generate_manifest_excel_bytes(manifest_data)
                zf.writestr('企标打包清单与对账明细.xlsx', manifest_bytes)
            except Exception as e:
                logger.error(f"注入清单 Excel 异常: {str(e)}")

    return buffer.getvalue()
