import os
import io
import re
import zipfile
import logging

import pandas as pd
from django.conf import settings
from django.db import connections
from django.db.models import Q
from standards.models import Standard
from standards.services import generate_clean_id
from companies.models import Company
from companies.services import search_companies, FederatedStandardService


logger = logging.getLogger('standards.archive_helpers')

def create_zip_from_standards(standard_ids: list, include_excel: bool = False) -> bytes:
    """
    将指定标准的 PDF 文件打包成 ZIP，并可选地生成企业与标准地域对应关系的 Excel 清单。
    优先使用 disk_filename 字段（共享磁盘阵列），完全移除对 pdf_file.path 的依赖。
    """
    # 分离本地企标 ID (int) 与联邦标准 ID (str, 以 fed_ 开头)
    local_ids = []
    federated_stds = []
    for sid in standard_ids:
        if isinstance(sid, str) and sid.startswith('fed_'):
            federated_stds.append(sid[4:])  # 剥离 fed_ 前缀，得到真实标准号
        else:
            try:
                local_ids.append(int(sid))
            except (ValueError, TypeError):
                pass

    standards = Standard.objects.select_related('company', 'company__province', 'company__city').filter(id__in=local_ids)
    shared_root = getattr(settings, 'SHARED_DISK_ROOT', r"Y:\磁盘阵列\标准文件下载\企标下载")

    buffer = io.BytesIO()
    added_count = 0
    skipped_count = 0
    excel_data = []

    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for std in standards:
            file_path = None

            # 优先使用 disk_filename
            if std.disk_filename:
                # 兼容 Windows 导入的含有反斜杠 \ 的旧路径，在 Linux 环境下转换为正斜杠 /
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

            # 如果文件存在，加入 ZIP
            if file_path:
                arcname = f'{std.standard_no.replace("/", "_")}.pdf'
                try:
                    zf.write(file_path, arcname=arcname)
                    added_count += 1
                    
                    if include_excel:
                        company_name = std.company.name if std.company else ''
                        province_name = std.company.province.name if std.company and std.company.province else ''
                        city_name = std.company.city.name if std.company and std.company.city else ''
                        excel_data.append({
                            '标准编号': std.standard_no,
                            '标准名称': std.title,
                            '企业名称': company_name,
                            '所属省份': province_name,
                            '所属城市': city_name
                        })
                except Exception as e:
                    logger.warning(f"写入 ZIP 失败 - 标准 ID: {std.id}, 路径: {file_path}, 错误: {str(e)}")
                    skipped_count += 1
            else:
                logger.warning(f"文件不存在或缺失 disk_filename - 标准 ID: {std.id}, 标准号: {std.standard_no}")
                skipped_count += 1

        # 处理联邦标准
        if federated_stds:
            try:
                with connections['stsc_db'].cursor() as cursor:
                    cursor.execute("SET NAMES utf8mb4;")
                    # 获取联邦标准的路径与基本信息
                    format_strings = ','.join(['%s'] * len(federated_stds))
                    query = f"""
                        SELECT v.std_id, v.std_chinesename, f.file_path, h.draft_unit
                        FROM view_std_full v
                        LEFT JOIN std_filepath f ON v.id = f.base_id
                        LEFT JOIN std_extend_h h ON v.id = h.base_id
                        WHERE v.std_id IN ({format_strings})
                    """
                    cursor.execute(query, tuple(federated_stds))
                    for row in cursor.fetchall():
                        std_no = row[0]
                        title = row[1]
                        file_path_rel = row[2]
                        draft_unit = row[3]

                        if file_path_rel:
                            # 联邦标准的 file_path 是相对路径，且与共享盘在同一大目录下
                            # 但需要向上一级目录再拼接。根据 settings，通常直接用父目录拼接。
                            base_dir = os.path.dirname(shared_root.rstrip('/\\'))
                            norm_path = file_path_rel.replace('/', os.sep).replace('\\', os.sep)
                            full_path = os.path.join(base_dir, norm_path)
                            
                            if os.path.exists(full_path):
                                arcname = f'{std_no.replace("/", "_")}.pdf'
                                try:
                                    zf.write(full_path, arcname=arcname)
                                    added_count += 1
                                    
                                    if include_excel:
                                        excel_data.append({
                                            '标准编号': std_no,
                                            '标准名称': title,
                                            '企业名称': draft_unit or '未知起草单位',
                                            '所属省份': '联邦国行标',
                                            '所属城市': '-'
                                        })
                                except Exception as e:
                                    logger.warning(f"写入联邦标准 ZIP 失败 - {std_no}: {str(e)}")
                                    skipped_count += 1
                            else:
                                skipped_count += 1
                        else:
                            skipped_count += 1
            except Exception as e:
                logger.error(f"处理联邦标准打包时发生异常: {str(e)}")

        # 如果需要，并且有成功打包的数据，生成并写入 Excel
        if include_excel and excel_data:
            try:
                df = pd.DataFrame(excel_data)
                excel_buffer = io.BytesIO()
                df.to_excel(excel_buffer, index=False, engine='openpyxl')
                excel_buffer.seek(0)
                zf.writestr('下载清单与企业地域映射表.xlsx', excel_buffer.read())
                logger.info("已生成并写入 Excel 映射清单。")
            except Exception as e:
                logger.error(f"生成 Excel 清单失败: {str(e)}")

    logger.info(f"ZIP 打包完成 - 总数: {len(standard_ids)}, 成功: {added_count}, 跳过: {skipped_count}")
    buffer.seek(0)
    return buffer.getvalue()

def pack_enterprises_to_zip(enterprise_ids: list = None, filters: dict = None, export_all: bool = False, uuid_str: str = "") -> str:
    """
    打包选中企业或检索条件名下的所有 PDF 企标文件。
    最大限制 200 家企业。
    目录结构：企业名称/标准号_标准名称.pdf
    """
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


def infer_company_type(name: str, raw_type: str = "") -> str:

    """
    已知企业名称或原始类型，智能判定企业(机构)类型
    """
    if raw_type and raw_type.strip():
        return raw_type.strip()
    if not name:
        return '其他'
    name = name.strip()
    if any(k in name for k in ['协会', '学会', '研究会', '商会', '促进会', '基金会', '联盟']):
        return '社会团体'
    if any(k in name for k in ['学校', '大学', '学院', '医院', '中心', '站', '研究所', '研究院', '托育中心', '幼托']):
        return '事业单位'
    if any(k in name for k in ['经营部', '商行', '个体', '理发店', '餐馆', '小吃店', '加工厂', '水产店', '食品店']):
        return '个体工商户'
    if '合作社' in name:
        return '农民专业合作社(联合社)'
    if '股份有限公司' in name:
        return '股份有限公司'
    if '有限责任公司' in name or '有限公司' in name:
        return '有限责任公司'
    if '合伙企业' in name:
        return '有限合伙'
    if any(k in name for k in ['局', '厅', '委', '办', '人民政府', '支队', '大队', '委员会']):
        return '机关单位'
    return '其他'


def detect_std_type_display(std_no: str, raw_type: str = "") -> str:
    """
    根据标准号前缀和原始类型推导标准分类（团体标准、地方标准、国家标准、行业标准）
    """
    s = (std_no or "").strip().upper()
    r = (raw_type or "").upper()
    if '团体' in r or s.startswith('T/') or s.startswith('T '):
        return '团体标准'
    if '地方' in r or s.startswith('DB'):
        return '地方标准'
    if '国家' in r or s.startswith('GB') or s.startswith('GH') or s.startswith('JJG'):
        return '国家标准'
    if '行业' in r or '/' in s:
        return '行业标准'
    return '国家标准'


def norm_std_super_key(s: str) -> str:
    """
    清洗标准号为强匹配 Key（移除 /T、/t、空格、破折号、点、标点符号等）
    如: 'GB 5296.6-2004' -> 'GB529662004'
        'GB/T 5296.6-2004' -> 'GB529662004'
        'JB/T 8250.5—1995' -> 'JBT825051995'
    """
    if not s:
        return ""
    s_clean = re.sub(r'/T', '', str(s), flags=re.IGNORECASE)
    return re.sub(r'[^A-Z0-9]', '', s_clean.upper())


def norm_std_prefix_key(s: str) -> str:
    """
    提取标准主体编号（不含年份与子部分），用于无部分/无年份模糊兜底匹配
    如: 'GB/T 4897-2003' -> 'GB4897'
        'GB/T 4897.1-2003' -> 'GB4897'
    """
    if not s:
        return ""
    s_clean = re.sub(r'/T', '', str(s), flags=re.IGNORECASE).upper()
    m = re.search(r'([A-Z]+)\s*[\/]?\s*([0-9]+)', s_clean)
    if m:
        return f"{m.group(1)}{m.group(2)}"
    return ""


def fetch_ics_ccs_name_maps(ics_code_list: list, ccs_code_list: list) -> tuple:
    """
    批量查询 stsc_db 的 std_ics_dict 与 std_ccs_dict，返回 {code: category_name} 映射字典
    """
    ics_tokens = set()
    for raw in ics_code_list:
        if not raw or raw in ('-', ''):
            continue
        parts = re.split(r'[,;；/|\s]+', str(raw))
        for p in parts:
            p_clean = p.strip()
            if p_clean and p_clean != '-':
                ics_tokens.add(p_clean)

    ccs_tokens = set()
    for raw in ccs_code_list:
        if not raw or raw in ('-', ''):
            continue
        parts = re.split(r'[,;；/|\s]+', str(raw))
        for p in parts:
            p_clean = p.strip()
            if p_clean and p_clean != '-':
                ccs_tokens.add(p_clean)

    ics_map = {}
    ccs_map = {}

    if not ics_tokens and not ccs_tokens:
        return ics_map, ccs_map

    try:
        with connections['stsc_db'].cursor() as cursor:
            cursor.execute("SET NAMES utf8mb4;")

            if ics_tokens:
                ics_list = list(ics_tokens)
                chunk_size = 500
                for i in range(0, len(ics_list), chunk_size):
                    chunk = ics_list[i:i + chunk_size]
                    in_clause = ",".join(["%s"] * len(chunk))
                    cursor.execute(f"SELECT ics_code, category_name FROM std_ics_dict WHERE ics_code IN ({in_clause})", chunk)
                    for code, name in cursor.fetchall():
                        if code and name:
                            ics_map[code.strip()] = name.strip()

            if ccs_tokens:
                ccs_list = list(ccs_tokens)
                chunk_size = 500
                for i in range(0, len(ccs_list), chunk_size):
                    chunk = ccs_list[i:i + chunk_size]
                    in_clause = ",".join(["%s"] * len(chunk))
                    cursor.execute(f"SELECT ccs_code, category_name FROM std_ccs_dict WHERE ccs_code IN ({in_clause})", chunk)
                    for code, name in cursor.fetchall():
                        if code and name:
                            ccs_map[code.strip()] = name.strip()
    except Exception as exc:
        logger.warning(f"获取 ICS/CCS 字典名称映射失败: {exc}")

    return ics_map, ccs_map


def format_codes_and_names(raw_code_str: str, name_map: dict) -> tuple:
    """
    清洗并规范化 ICS 或 CCS 代码与中文名称：
    将原始分类号字符串拆分为多个独立代码，用 ';' 分隔重组编号与对应的中文名称。
    Returns: (formatted_codes_str, formatted_names_str)
    """
    if not raw_code_str or str(raw_code_str).strip() in ('-', ''):
        return '-', '-'

    parts = re.split(r'[,;；/|\s]+', str(raw_code_str))
    valid_codes = []
    valid_names = []

    for p in parts:
        code = p.strip()
        if not code or code == '-':
            continue
        if code not in valid_codes:
            valid_codes.append(code)
            zh_name = name_map.get(code) or '-'
            valid_names.append(zh_name)

    if not valid_codes:
        return '-', '-'

    code_str = "; ".join(valid_codes)
    name_str = "; ".join(valid_names)
    return code_str, name_str


def fetch_std_details_map(std_nos: list) -> dict:
    """
    多级高容错检索：从本地 Standard 表和穿透 stsc_db 获取标准的标题、状态、类型、ICS、CCS、发布/实施日期及起草单位。
    支持国标 (std_gb_detail)、行标 (std_hb_detail)、地标 (std_db_detail)、团标 (std_tb_detail) 明细表联合查询。
    自动处理 /T 缺失、半全角符号差异、无子部分号/年份变更等场景。
    """
    if not std_nos:
        return {}

    details_map = {}
    from standards.services import generate_clean_id

    # 映射池：普通 clean_id、super_key、prefix_key
    clean_to_raw = {}
    super_to_raw = {}
    prefix_to_raw = {}

    for no in std_nos:
        clean = generate_clean_id(no)
        clean_to_raw[clean] = no
        s_key = norm_std_super_key(no)
        if s_key:
            super_to_raw[s_key] = no
        p_key = norm_std_prefix_key(no)
        if p_key:
            prefix_to_raw.setdefault(p_key, []).append(no)

    # 1. 查询本地 Standard 表
    local_stds = Standard.objects.select_related('company').filter(
        Q(standard_no__in=std_nos) | Q(clean_id__in=list(clean_to_raw.keys()))
    )
    for std in local_stds:
        no = std.standard_no
        item_info = {
            'title': std.title or '-',
            'status': std.get_status_display() or '现行',
            'type': std.get_type_display() if (std.type and std.type != 'enterprise') else detect_std_type_display(no),
            'ics': std.ics or '-',
            'ccs': std.ccs or '-',
            'release_date': std.publish_date.strftime('%Y-%m-%d') if std.publish_date else '-',
            'implement_date': std.implement_date.strftime('%Y-%m-%d') if std.implement_date else '-',
            'drafter': std.company.name if std.company else '-',
        }
        details_map[no] = item_info
        if std.clean_id:
            details_map[std.clean_id] = item_info
        if std.clean_id in clean_to_raw:
            details_map[clean_to_raw[std.clean_id]] = item_info

    # 2. 查漏：穿透到 stsc_db 的 std_base 与各明细表 (补充不存在或 ICS/CCS 为空的记录)
    missing_nos = []
    for no in std_nos:
        d = details_map.get(no) or details_map.get(generate_clean_id(no)) or details_map.get(norm_std_super_key(no))
        if not d or d.get('ics') in ('-', '', None) or d.get('ccs') in ('-', '', None):
            missing_nos.append(no)

    if missing_nos:
        try:
            with connections['stsc_db'].cursor() as cursor:
                cursor.execute("SET NAMES utf8mb4;")

                # =========================================================
                # 阶段 1: 极速阶段 —— 建立 std_id_norm 精准 B-Tree 索引 IN 查询 (覆盖 95%+ 正规格式)
                # =========================================================
                norm_map = {}  # norm_str -> original_no
                for no in missing_nos:
                    n_str = re.sub(r'[/ \-\s]', '', no).upper()
                    if n_str:
                        norm_map[n_str] = no

                norm_keys = list(norm_map.keys())
                chunk_size = 500
                for i in range(0, len(norm_keys), chunk_size):
                    chunk_keys = norm_keys[i:i + chunk_size]
                    in_clause = ",".join(["%s"] * len(chunk_keys))

                    sql = f"""
                        SELECT b.std_id, b.std_id_norm, b.std_chinesename, b.ex_state, b.std_type,
                               COALESCE(gb.ics, hb.ics, db.ics, tb.ics) AS ics,
                               COALESCE(gb.ccs, hb.ccs, db.ccs, tb.ccs) AS ccs,
                               b.release_date, b.implement_date,
                               COALESCE(h.draft_unit, gb.drafter, hb.drafter, tb.drafter) AS drafter
                        FROM std_base b
                        LEFT JOIN std_gb_detail gb ON b.id = gb.base_id
                        LEFT JOIN std_hb_detail hb ON b.id = hb.base_id
                        LEFT JOIN std_db_detail db ON b.id = db.base_id
                        LEFT JOIN std_tb_detail tb ON b.id = tb.base_id
                        LEFT JOIN std_extend_h h ON b.id = h.base_id
                        WHERE b.std_id_norm IN ({in_clause})
                    """
                    cursor.execute(sql, chunk_keys)
                    for row in cursor.fetchall():
                        s_id = row[0]
                        s_norm = row[1]
                        title = row[2] or '-'
                        st_code = row[3]
                        ex_state = '即将实施' if st_code == 2 else ('废止' if st_code == 0 else '现行')
                        raw_type = row[4] or ''
                        type_disp = detect_std_type_display(s_id, raw_type)
                        ics = row[5] or '-'
                        ccs = row[6] or '-'
                        rel_date = row[7].strftime('%Y-%m-%d') if row[7] else '-'
                        imp_date = row[8].strftime('%Y-%m-%d') if row[8] else '-'
                        drafter_str = row[9] or '-'

                        item_dict = {
                            'title': title,
                            'status': ex_state,
                            'type': type_disp,
                            'ics': ics,
                            'ccs': ccs,
                            'release_date': rel_date,
                            'implement_date': imp_date,
                            'drafter': drafter_str,
                        }

                        clean_ver = generate_clean_id(s_id)
                        s_key = norm_std_super_key(s_id)
                        p_key = norm_std_prefix_key(s_id)

                        details_map[s_id] = item_dict
                        details_map[clean_ver] = item_dict
                        if s_norm:
                            details_map[s_norm] = item_dict
                        if s_key:
                            details_map[s_key] = item_dict
                        if p_key and p_key not in details_map:
                            details_map[p_key] = item_dict

                        raw_no = norm_map.get(s_norm) or clean_to_raw.get(clean_ver) or super_to_raw.get(s_key)
                        if raw_no:
                            details_map[raw_no] = item_dict

                # =========================================================
                # 阶段 2: 降级保底阶段 —— 对仅剩未命中的极少数非标格式发起模糊扫描 (覆盖 5% 非标格式)
                # =========================================================
                still_missing_nos = [
                    no for no in missing_nos
                    if not details_map.get(no) or details_map.get(no, {}).get('ics') in ('-', '', None)
                ]

                if still_missing_nos:
                    digit_tokens = set()
                    for no in still_missing_nos:
                        nums = re.findall(r'\d+', no)
                        if nums:
                            digit_tokens.add(nums[0])

                    if digit_tokens:
                        token_list = list(digit_tokens)
                        for i in range(0, len(token_list), 100):
                            chunk = token_list[i:i + 100]
                            where_clauses = " OR ".join(["b.std_id LIKE %s"] * len(chunk))
                            params = [f"%{t}%" for t in chunk]

                            sql = f"""
                                SELECT b.std_id, b.std_chinesename, b.ex_state, b.std_type,
                                       COALESCE(gb.ics, hb.ics, db.ics, tb.ics) AS ics,
                                       COALESCE(gb.ccs, hb.ccs, db.ccs, tb.ccs) AS ccs,
                                       b.release_date, b.implement_date,
                                       COALESCE(h.draft_unit, gb.drafter, hb.drafter, tb.drafter) AS drafter
                                FROM std_base b
                                LEFT JOIN std_gb_detail gb ON b.id = gb.base_id
                                LEFT JOIN std_hb_detail hb ON b.id = hb.base_id
                                LEFT JOIN std_db_detail db ON b.id = db.base_id
                                LEFT JOIN std_tb_detail tb ON b.id = tb.base_id
                                LEFT JOIN std_extend_h h ON b.id = h.base_id
                                WHERE {where_clauses}
                            """
                            cursor.execute(sql, params)
                            for row in cursor.fetchall():
                                s_id = row[0]
                                title = row[1] or '-'
                                st_code = row[2]
                                ex_state = '即将实施' if st_code == 2 else ('废止' if st_code == 0 else '现行')
                                raw_type = row[3] or ''
                                type_disp = detect_std_type_display(s_id, raw_type)
                                ics = row[4] or '-'
                                ccs = row[5] or '-'
                                rel_date = row[6].strftime('%Y-%m-%d') if row[6] else '-'
                                imp_date = row[7].strftime('%Y-%m-%d') if row[7] else '-'
                                drafter_str = row[8] or '-'

                                item_dict = {
                                    'title': title,
                                    'status': ex_state,
                                    'type': type_disp,
                                    'ics': ics,
                                    'ccs': ccs,
                                    'release_date': rel_date,
                                    'implement_date': imp_date,
                                    'drafter': drafter_str,
                                }

                                clean_ver = generate_clean_id(s_id)
                                s_key = norm_std_super_key(s_id)
                                p_key = norm_std_prefix_key(s_id)

                                details_map[s_id] = item_dict
                                details_map[clean_ver] = item_dict
                                if s_key:
                                    details_map[s_key] = item_dict
                                if p_key and p_key not in details_map:
                                    details_map[p_key] = item_dict

                                raw_no = clean_to_raw.get(clean_ver) or super_to_raw.get(s_key)
                                if raw_no:
                                    details_map[raw_no] = item_dict

        except Exception as exc:
            logger.warning(f"从 stsc_db 补全标准信息失败: {exc}")

    return details_map





def generate_advanced_export_file(
    enterprise_ids: list = None,
    base_filters: dict = None,
    advanced_filters: dict = None,
    export_scope: str = 'filtered',
    export_content: str = 'both',
    file_format: str = 'single_excel',
    uuid_str: str = ""
) -> str:
    """
    高级导出底层引擎函数：
    根据筛选项导出 企业目录 与 去重企标目录，并写出为单 Excel(多Sheet) 或 ZIP(双Excel)。
    """
    base_filters = base_filters or {}
    advanced_filters = advanced_filters or {}

    # 1. 过滤企业列表
    if export_scope == 'selected' and enterprise_ids:
        qs = Company.objects.select_related('province', 'city', 'district').filter(id__in=enterprise_ids)
    else:
        # 复用 search_companies 服务以确保完全对齐前端搜索状态
        from companies.services import search_companies
        qs = search_companies(
            keyword=base_filters.get('q') or base_filters.get('keyword') or base_filters.get('query'),
            province_id=base_filters.get('province_id') or base_filters.get('province'),
            city_id=base_filters.get('city_id') or base_filters.get('city'),
            district_id=base_filters.get('district_id') or base_filters.get('district'),
            status=base_filters.get('status'),
            ics=base_filters.get('ics'),
            ccs=base_filters.get('ccs'),
            standard_logic=base_filters.get('standard_logic', 'OR'),
            center_lat=base_filters.get('center_lat') or base_filters.get('lat'),
            center_lng=base_filters.get('center_lng') or base_filters.get('lng'),
            radius_km=base_filters.get('radius_km')
        ).select_related('province', 'city', 'district')

    # 上限保护：先拉取查询结果，由于需要推断机构类型，我们将对结果进行内存过滤
    company_list = list(qs[:100000])

    # 2. 高级过滤：企业(机构)类型包含/排除模式 (在内存中根据 infer_company_type 过滤)
    agency_type_mode = advanced_filters.get('agency_type_mode', 'include')
    agency_types = advanced_filters.get('agency_types', [])
    if agency_types and isinstance(agency_types, list):
        filtered_list = []
        for co in company_list:
            inferred = infer_company_type(co.name, co.company_type)
            match = any((atype in inferred or inferred in atype) for atype in agency_types if atype)
            
            if agency_type_mode == 'exclude':
                if not match:
                    filtered_list.append(co)
            else:
                if match:
                    filtered_list.append(co)
        company_list = filtered_list

    if not company_list:
        raise ValueError("按当前过滤条件未检索到任何匹配的企业记录")

    # 解析 export_content 参数（支持列表 ['enterprise', 'enterprise_standard', 'other_standard'] 或字符串 'both'/'all' 等）
    if isinstance(export_content, list):
        content_set = set(export_content)
    elif export_content == 'both':
        content_set = {'enterprise', 'enterprise_standard'}
    elif export_content == 'all':
        content_set = {'enterprise', 'enterprise_standard', 'other_standard'}
    elif export_content == 'enterprise_only':
        content_set = {'enterprise'}
    elif export_content == 'standard_only':
        content_set = {'enterprise_standard'}
    elif export_content == 'other_standard_only':
        content_set = {'other_standard'}
    else:
        content_set = {'enterprise', 'enterprise_standard', 'other_standard'}

    # 3. 准备企业目录数据
    company_rows = []
    if 'enterprise' in content_set:
        for co in company_list:
            p_name = co.province.name if co.province else ''
            c_name = co.city.name if co.city else ''
            d_name = co.district.name if co.district else ''

            company_rows.append({
                '企业名称': co.name,
                '统一信用代码': co.credit_code,
                '省份': p_name,
                '城市': c_name,
                '区县': d_name,
                '曾用名': co.former_names or '',
                '企业(机构)类型': infer_company_type(co.name, co.company_type),
                '企业规模': co.company_size or '',
                '登记状态': '存续' if co.status == 'active' else '禁用',
            })

    # 4. 准备企标目录数据（全局去重）
    standard_rows = []
    if 'enterprise_standard' in content_set:
        comp_ids = [c.id for c in company_list]
        stds = Standard.objects.select_related('company').filter(
            company_id__in=comp_ids,
            type='enterprise'
        )

        seen_nos = set()
        for std in stds:
            s_no = (std.standard_no or '').strip()
            if not s_no or s_no in seen_nos:
                continue
            seen_nos.add(s_no)
            company_name = std.company.name if std.company else ''
            pub_date = std.publish_date.strftime('%Y-%m-%d') if std.publish_date else '-'
            imp_date = std.implement_date.strftime('%Y-%m-%d') if std.implement_date else '-'
            standard_rows.append({
                '标准号': s_no,
                '标准名称': std.title or '',
                '企业名称': company_name,
                '标准状态': std.get_status_display() or '现行',
                '标准类型': std.get_type_display() or '企业标准',
                '制修订': '制定',
                '发布日期': pub_date,
                '实施日期': imp_date,
                'ICS': std.ics or '',
                'CCS': std.ccs or '',
                '国民经济分类': std.company.industry_category if std.company else '',
            })

    # 5. 准备国行地团标目录数据（全局去重）
    other_standard_rows = []
    if 'other_standard' in content_set:
        comp_ids = [c.id for c in company_list]
        seen_nos = set()
        other_items = []

        # a. 名下直接关联的非企标标准 (国/行/地/团)
        direct_stds = Standard.objects.select_related('company').filter(
            company_id__in=comp_ids,
            type__in=['national', 'industry', 'local', 'group']
        )
        for std in direct_stds:
            s_no = (std.standard_no or '').strip()
            if not s_no or s_no in seen_nos:
                continue
            seen_nos.add(s_no)
            other_items.append({
                's_no': s_no,
                'std': std,
                'industry_category': std.company.industry_category if std.company else ''
            })

        # b. 穿透 stsc_db 检索选定企业真正参与起草的非企标标准 (国/行/地/团)
        for company in company_list:
            try:
                summary_data = FederatedStandardService.get_company_standards_summary(company)
                fed_stds = summary_data.get('standards', [])
                for fed in fed_stds:
                    s_no = (fed.get('standard_no') or '').strip()
                    if not s_no or s_no in seen_nos:
                        continue
                    seen_nos.add(s_no)
                    other_items.append({
                        's_no': s_no,
                        'std': None,
                        'fed_info': fed,
                        'industry_category': company.industry_category or ''
                    })
            except Exception as fed_err:
                logger.error(f"Failed to query STSC standards for company {company.name}: {fed_err}")

        # 批量从 stsc_db / 本地 Standard 表抓取补全标题、状态、类型、ICS、CCS、日期与起草单位
        nos_to_fetch = [item['s_no'] for item in other_items]
        details_map = fetch_std_details_map(nos_to_fetch)

        all_ics_raw = []
        all_ccs_raw = []

        for item in other_items:
            s_no = item['s_no']
            std = item['std']
            fed_info = item.get('fed_info') or {}
            clean_ver = generate_clean_id(s_no)
            s_key = norm_std_super_key(s_no)
            p_key = norm_std_prefix_key(s_no)

            d_info = (details_map.get(s_no) or
                      details_map.get(clean_ver) or
                      details_map.get(s_key) or
                      details_map.get(p_key) or {})

            raw_ics = d_info.get('ics') or fed_info.get('ics') or (std.ics if std else '')
            raw_ccs = d_info.get('ccs') or fed_info.get('ccs') or (std.ccs if std else '')
            item['d_info'] = d_info
            item['raw_ics'] = raw_ics
            item['raw_ccs'] = raw_ccs

            if raw_ics:
                all_ics_raw.append(raw_ics)
            if raw_ccs:
                all_ccs_raw.append(raw_ccs)

        ics_map, ccs_map = fetch_ics_ccs_name_maps(all_ics_raw, all_ccs_raw)

        for item in other_items:
            s_no = item['s_no']
            std = item['std']
            fed_info = item.get('fed_info') or {}
            d_info = item.get('d_info') or {}

            raw_title = d_info.get('title') or fed_info.get('title') or (std.title if std else '')
            title = raw_title if (raw_title and raw_title != '-') else '-'

            status = d_info.get('status') or fed_info.get('status') or (std.get_status_display() if std else '现行')
            stype = d_info.get('type') or fed_info.get('type') or (std.get_type_display() if (std and std.type != 'enterprise') else detect_std_type_display(s_no))

            ics, ics_zh = format_codes_and_names(item.get('raw_ics'), ics_map)
            ccs, ccs_zh = format_codes_and_names(item.get('raw_ccs'), ccs_map)

            pub_date = (std.publish_date.strftime('%Y-%m-%d') if std and std.publish_date else None) or d_info.get('release_date') or fed_info.get('release_date') or '-'
            imp_date = (std.implement_date.strftime('%Y-%m-%d') if std and std.implement_date else None) or d_info.get('implement_date') or fed_info.get('implement_date') or '-'

            drafters_raw = fed_info.get('drafters') or d_info.get('drafter') or ''
            if isinstance(drafters_raw, list):
                drafters_disp = ", ".join(drafters_raw) if drafters_raw else '-'
            elif isinstance(drafters_raw, str) and drafters_raw.strip():
                drafters_disp = drafters_raw.strip()
            else:
                drafters_disp = '-'

            rank_order = fed_info.get('rank_order') or d_info.get('rank_order')
            if rank_order:
                rank_disp = f"第{rank_order}名"
            else:
                rank_disp = '-'

            other_standard_rows.append({
                '标准号': s_no,
                '标准名称': title,
                '标准状态': status,
                '标准类型': stype,
                '制修订': '制定',
                '发布日期': pub_date,
                '实施日期': imp_date,
                'ICS': ics,
                'ICS中文名称': ics_zh,
                'CCS': ccs,
                'CCS中文名称': ccs_zh,
                '起草单位': drafters_disp,
                '起草单位排名名次': rank_disp,
                '国民经济分类': item['industry_category'],
            })

    # 6. 文件写出
    exports_dir = os.path.join(settings.MEDIA_ROOT, 'exports')
    os.makedirs(exports_dir, exist_ok=True)

    file_prefix = f"advanced_export_{uuid_str}"

    co_cols = ['企业名称', '统一信用代码', '省份', '城市', '区县', '曾用名', '企业(机构)类型', '企业规模', '登记状态']
    std_cols = ['标准号', '标准名称', '企业名称', '标准状态', '标准类型', '制修订', '发布日期', '实施日期', 'ICS', 'CCS', '国民经济分类']
    other_std_cols = ['标准号', '标准名称', '标准状态', '标准类型', '制修订', '发布日期', '实施日期', 'ICS', 'ICS中文名称', 'CCS', 'CCS中文名称', '起草单位', '起草单位排名名次', '国民经济分类']

    if file_format == 'separate_zip':
        zip_filename = f"{file_prefix}.zip"
        zip_filepath = os.path.join(exports_dir, zip_filename)

        with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zf:
            if 'enterprise' in content_set:
                df_co = pd.DataFrame(company_rows, columns=co_cols)
                co_buf = io.BytesIO()
                df_co.to_excel(co_buf, index=False, sheet_name='企业目录', engine='openpyxl')
                zf.writestr('1_企业目录.xlsx', co_buf.getvalue())

            if 'enterprise_standard' in content_set:
                df_std = pd.DataFrame(standard_rows, columns=std_cols)
                std_buf = io.BytesIO()
                df_std.to_excel(std_buf, index=False, sheet_name='企标目录', engine='openpyxl')
                zf.writestr('2_企标目录.xlsx', std_buf.getvalue())

            if 'other_standard' in content_set:
                df_other = pd.DataFrame(other_standard_rows, columns=other_std_cols)
                other_buf = io.BytesIO()
                df_other.to_excel(other_buf, index=False, sheet_name='国行地团标目录', engine='openpyxl')
                zf.writestr('3_国行地团标目录.xlsx', other_buf.getvalue())

        return f"exports/{zip_filename}"
    else:
        excel_filename = f"{file_prefix}.xlsx"
        excel_filepath = os.path.join(exports_dir, excel_filename)

        with pd.ExcelWriter(excel_filepath, engine='openpyxl') as writer:
            if 'enterprise' in content_set:
                df_co = pd.DataFrame(company_rows, columns=co_cols)
                df_co.to_excel(writer, sheet_name='企业目录', index=False)
            if 'enterprise_standard' in content_set:
                df_std = pd.DataFrame(standard_rows, columns=std_cols)
                df_std.to_excel(writer, sheet_name='企标目录', index=False)
            if 'other_standard' in content_set:
                df_other = pd.DataFrame(other_standard_rows, columns=other_std_cols)
                df_other.to_excel(writer, sheet_name='国行地团标目录', index=False)

        return f"exports/{excel_filename}"




