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
from companies.models import Company, Province, City, District
from companies.services import search_companies, FederatedStandardService
from companies.services_association import AssociationBatchService


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

    # 解析 export_content 参数（支持列表 ['enterprise', 'enterprise_standard', 'other_standard', 'tb_association'] 或字符串 'both'/'all' 等）
    if isinstance(export_content, list):
        content_set = set(export_content)
    elif export_content == 'both':
        content_set = {'enterprise', 'enterprise_standard'}
    elif export_content == 'all':
        content_set = {'enterprise', 'enterprise_standard', 'other_standard', 'tb_association'}
    elif export_content == 'enterprise_only':
        content_set = {'enterprise'}
    elif export_content == 'standard_only':
        content_set = {'enterprise_standard'}
    elif export_content == 'other_standard_only':
        content_set = {'other_standard'}
    elif export_content == 'tb_association_only':
        content_set = {'tb_association'}
    else:
        content_set = {'enterprise', 'enterprise_standard', 'other_standard'}

    if not company_list and 'tb_association' not in content_set:
        raise ValueError("按当前过滤条件未检索到任何匹配的企业记录")

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

    # 5. 准备国行地团标目录数据（全局去重并归合选定起草单位）
    other_standard_rows = []
    if 'other_standard' in content_set:
        comp_ids = [c.id for c in company_list]
        other_items_map = {}

        # a. 名下直接关联的非企标标准 (国/行/地/团)
        direct_stds = Standard.objects.select_related('company').filter(
            company_id__in=comp_ids,
            type__in=['national', 'industry', 'local', 'group']
        )
        for std in direct_stds:
            s_no = (std.standard_no or '').strip()
            if not s_no:
                continue
            comp_name = std.company.name if std.company else ''
            if s_no not in other_items_map:
                other_items_map[s_no] = {
                    's_no': s_no,
                    'std': std,
                    'industry_category': std.company.industry_category if std.company else '',
                    'companies': [],
                    'ranks': [],
                    'fed_info': None
                }
            if comp_name and comp_name not in other_items_map[s_no]['companies']:
                other_items_map[s_no]['companies'].append(comp_name)

        # b. 穿透 stsc_db 检索选定企业真正参与起草的非企标标准 (国/行/地/团)
        for company in company_list:
            try:
                summary_data = FederatedStandardService.get_company_standards_summary(company)
                fed_stds = summary_data.get('standards', [])
                for fed in fed_stds:
                    s_no = (fed.get('standard_no') or '').strip()
                    if not s_no:
                        continue
                    if s_no not in other_items_map:
                        other_items_map[s_no] = {
                            's_no': s_no,
                            'std': None,
                            'industry_category': company.industry_category or '',
                            'companies': [],
                            'ranks': [],
                            'fed_info': fed
                        }
                    comp_name = company.name
                    if comp_name and comp_name not in other_items_map[s_no]['companies']:
                        other_items_map[s_no]['companies'].append(comp_name)
                    rank_order = fed.get('rank_order')
                    if rank_order and not any(r[0] == comp_name for r in other_items_map[s_no]['ranks']):
                        other_items_map[s_no]['ranks'].append((comp_name, rank_order))
            except Exception as fed_err:
                logger.error(f"Failed to query STSC standards for company {company.name}: {fed_err}")

        other_items = list(other_items_map.values())

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

            # 起草单位：只提取选定导出目标中检索/归属的企业名称，避免列出全部几十家无关单位
            matched_companies = item.get('companies') or []
            if matched_companies:
                drafters_disp = ", ".join(matched_companies)
            else:
                drafters_raw = fed_info.get('drafters') or d_info.get('drafter') or ''
                if isinstance(drafters_raw, list):
                    drafters_disp = ", ".join(drafters_raw[:2]) if drafters_raw else '-'
                elif isinstance(drafters_raw, str) and drafters_raw.strip():
                    drafters_disp = drafters_raw.strip()
                else:
                    drafters_disp = '-'

            # 起草单位排名名次
            ranks = item.get('ranks') or []
            if ranks:
                rank_disp = ", ".join([f"第{r}名" for c, r in ranks])
            elif fed_info.get('rank_order'):
                rank_disp = f"第{fed_info.get('rank_order')}名"
            elif d_info.get('rank_order'):
                rank_disp = f"第{d_info.get('rank_order')}名"
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

    # 6. 准备社会组织全景标准资产目录与明细 (tb_association)
    tb_asso_rows = []
    tb_detail_rows = []
    if 'tb_association' in content_set:
        prov_id = base_filters.get('province_id') or advanced_filters.get('province_id')
        city_id = base_filters.get('city_id') or advanced_filters.get('city_id')
        district_id = base_filters.get('district_id') or advanced_filters.get('district_id')
        kw = (base_filters.get('q') or base_filters.get('keyword') or '').strip()
        reg_level = advanced_filters.get('reg_level') or base_filters.get('reg_level')
        reg_authority = (advanced_filters.get('reg_authority') or base_filters.get('reg_authority') or '').strip()

        # 角色与类型过滤配置 (可单选/多选)
        association_roles = advanced_filters.get('association_roles')
        if not association_roles or not isinstance(association_roles, list):
            association_roles = ['publisher_group', 'drafter_group', 'drafter_national']
        roles_set = set(association_roles)
        include_zero_standard = bool(advanced_filters.get('include_zero_standard_associations', False))

        prov_name = ''
        city_name = ''
        district_name = ''
        if prov_id:
            try:
                p_obj = Province.objects.filter(id=prov_id).first()
                if p_obj:
                    prov_name = p_obj.name.strip()
            except Exception:
                pass
        if city_id:
            try:
                c_obj = City.objects.filter(id=city_id).first()
                if c_obj:
                    city_name = c_obj.name.strip()
            except Exception:
                pass
        if district_id:
            try:
                d_obj = District.objects.filter(id=district_id).first()
                if d_obj:
                    district_name = d_obj.name.strip()
            except Exception:
                pass

        p_kw = prov_name.replace('省', '').replace('市', '').replace('自治区', '').replace('壮族', '').replace('回族', '').replace('维吾尔', '') if prov_name else ''
        c_kw = city_name.replace('市', '').replace('地区', '').replace('州', '') if city_name else ''
        d_kw = district_name.replace('市', '').replace('区', '').replace('县', '').replace('旗', '') if district_name else ''

        # ── 步骤 6.1：收集目标社会组织候选池 ────────────────────────────
        asso_pool = {}

        if export_scope == 'selected' and company_list:
            # 勾选模式：直接以勾选的主体作为候选
            for co in company_list:
                cname = (co.name or '').strip()
                if cname:
                    asso_pool[cname] = {
                        'name': cname,
                        'regi_no': (co.credit_code or '').strip(),
                        'legal_rep': '',
                        'charge_person': '',
                        'issu_auth': '',
                        'address': '',
                        'province': co.province.name if co.province else prov_name,
                        'city': co.city.name if co.city else city_name,
                        'district': co.district.name if co.district else district_name,
                        'standards': [],
                        'seen_std_ids': set()
                    }
        else:
            # 过滤模式：从 compare_conp.ent_std_maker 检索该地域社会组织底册
            try:
                with connections['compare_conp'].cursor() as cur:
                    ent_where = ["(enterprise_type LIKE %s OR company_name LIKE %s OR company_name LIKE %s OR company_name LIKE %s)"]
                    ent_params = ['%社会团体%', '%协会%', '%学会%', '%商会%']
                    if p_kw:
                        ent_where.append("(province LIKE %s OR company_name LIKE %s)")
                        ent_params.extend([f"%{p_kw}%", f"%{p_kw}%"])
                    if c_kw:
                        ent_where.append("(city LIKE %s OR company_name LIKE %s)")
                        ent_params.extend([f"%{c_kw}%", f"%{c_kw}%"])
                    if d_kw:
                        ent_where.append("(district LIKE %s OR company_name LIKE %s)")
                        ent_params.extend([f"%{d_kw}%", f"%{d_kw}%"])
                    if kw:
                        ent_where.append("(company_name LIKE %s OR unified_social_credit_code LIKE %s)")
                        ent_params.extend([f"%{kw}%", f"%{kw}%"])

                    sql_ent = f"""
                        SELECT company_name, unified_social_credit_code, legal_representative, province, city, district
                        FROM ent_std_maker
                        WHERE {' AND '.join(ent_where)}
                        LIMIT 50000
                    """
                    cur.execute(sql_ent, ent_params)
                    for r_cname, r_code, r_lrep, r_pr, r_ci, r_dist in cur.fetchall():
                        name_clean = (r_cname or '').strip()
                        if name_clean and name_clean not in asso_pool:
                            asso_pool[name_clean] = {
                                'name': name_clean,
                                'regi_no': (r_code or '').strip(),
                                'legal_rep': (r_lrep or '').strip(),
                                'charge_person': '',
                                'issu_auth': '',
                                'address': '',
                                'province': (r_pr or '').strip() or prov_name,
                                'city': (r_ci or '').strip() or city_name,
                                'district': (r_dist or '').strip() or district_name,
                                'standards': [],
                                'seen_std_ids': set()
                            }
            except Exception as e:
                logger.warning(f"Query ent_std_maker for regional associations error: {e}")

        # ── 步骤 6.2：补充/对齐已发团标数据（主发布单位） ─────────────────────────
        status_map = {1: '现行', 0: '废止', 2: '即将实施'}
        batch_size = 300

        try:
            with connections['stsc_db'].cursor() as cur:
                if export_scope == 'selected':
                    selected_names = list(asso_pool.keys())
                    for i in range(0, len(selected_names), batch_size):
                        chunk = selected_names[i:i + batch_size]
                        ph = ', '.join(['%s'] * len(chunk))
                        sql_tb = f"""
                            SELECT 
                                t.tb_asso, t.regi_no, t.Issu_auth, t.charge_person, t.address,
                                v.std_id, v.std_chinesename, v.release_date, v.implement_date, v.ex_state
                            FROM std_tb_detail t
                            JOIN view_std_full v ON t.base_id = v.id
                            WHERE t.tb_asso IN ({ph})
                            ORDER BY t.tb_asso, v.release_date DESC
                        """
                        cur.execute(sql_tb, chunk)
                        for r_asso, r_regi, r_issu, r_cp, r_addr, sid, stitle, rdate, idate, ex_st in cur.fetchall():
                            a_name = (r_asso or '').strip()
                            if not a_name or a_name not in asso_pool:
                                continue
                            g = asso_pool[a_name]
                            if not g['regi_no'] and r_regi:
                                g['regi_no'] = r_regi.strip()
                            if not g['charge_person'] and r_cp:
                                g['charge_person'] = r_cp.strip()
                            if not g['issu_auth'] and r_issu:
                                g['issu_auth'] = r_issu.strip()
                            if not g['address'] and r_addr:
                                g['address'] = r_addr.strip()

                            if 'publisher_group' in roles_set:
                                sid_clean = (sid or '').strip()
                                if sid_clean and sid_clean not in g['seen_std_ids']:
                                    g['seen_std_ids'].add(sid_clean)
                                    g['standards'].append({
                                        'std_id': sid_clean,
                                        'title': stitle or '无标题',
                                        'type_display': '团体标准',
                                        'role_display': '主发布单位',
                                        'drafter_display': '主要发布协会',
                                        'rank': 1,
                                        'status': status_map.get(ex_st, '现行'),
                                        'release_date': str(rdate) if rdate else '-',
                                        'implement_date': str(idate) if idate else '-'
                                    })
                else:
                    tb_where = []
                    tb_params = []
                    if p_kw:
                        tb_where.append("(t.tb_asso LIKE %s OR t.address LIKE %s OR t.Issu_auth LIKE %s)")
                        tb_params.extend([f"%{p_kw}%", f"%{p_kw}%", f"%{p_kw}%"])
                    if c_kw:
                        tb_where.append("(t.tb_asso LIKE %s OR t.address LIKE %s OR t.Issu_auth LIKE %s)")
                        tb_params.extend([f"%{c_kw}%", f"%{c_kw}%", f"%{c_kw}%"])
                    if d_kw:
                        tb_where.append("(t.Issu_auth LIKE %s OR t.address LIKE %s OR t.tb_asso LIKE %s)")
                        tb_params.extend([f"%{d_kw}%", f"%{d_kw}%", f"%{d_kw}%"])
                    if kw:
                        tb_where.append("(t.tb_asso LIKE %s OR t.regi_no LIKE %s OR v.std_id LIKE %s OR v.std_chinesename LIKE %s)")
                        tb_params.extend([f"%{kw}%", f"%{kw}%", f"%{kw}%", f"%{kw}%"])

                    if reg_level == 'ministry':
                        tb_where.append("(t.Issu_auth LIKE %s)")
                        tb_params.append('%民政部%')
                    elif reg_level == 'province':
                        tb_where.append("(t.Issu_auth LIKE %s)")
                        tb_params.append('%民政厅%')
                    elif reg_level == 'city':
                        tb_where.append("(t.Issu_auth LIKE %s AND t.Issu_auth NOT LIKE %s AND t.Issu_auth NOT LIKE %s)")
                        tb_params.extend(['%市民政局%', '%区%', '%县%'])
                    elif reg_level == 'district':
                        tb_where.append("(t.Issu_auth LIKE %s OR t.Issu_auth LIKE %s OR t.Issu_auth LIKE %s OR t.Issu_auth LIKE %s)")
                        tb_params.extend(['%区%民政局%', '%县%民政局%', '%区民政局%', '%县民政局%'])

                    if reg_authority:
                        tb_where.append("(t.Issu_auth LIKE %s)")
                        tb_params.append(f"%{reg_authority}%")

                    where_clause = ("WHERE " + " AND ".join(tb_where)) if tb_where else ""
                    sql_tb = f"""
                        SELECT 
                            t.tb_asso, t.regi_no, t.Issu_auth, t.charge_person, t.address,
                            v.std_id, v.std_chinesename, v.release_date, v.implement_date, v.ex_state
                        FROM std_tb_detail t
                        JOIN view_std_full v ON t.base_id = v.id
                        {where_clause}
                        ORDER BY t.tb_asso, v.release_date DESC
                        LIMIT 50000
                    """
                    cur.execute(sql_tb, tb_params)
                    for r_asso, r_regi, r_issu, r_cp, r_addr, sid, stitle, rdate, idate, ex_st in cur.fetchall():
                        a_name = (r_asso or '').strip()
                        if not a_name:
                            continue
                        if a_name not in asso_pool:
                            asso_pool[a_name] = {
                                'name': a_name,
                                'regi_no': (r_regi or '').strip(),
                                'legal_rep': '',
                                'charge_person': (r_cp or '').strip(),
                                'issu_auth': (r_issu or '').strip(),
                                'address': (r_addr or '').strip(),
                                'province': prov_name,
                                'city': city_name,
                                'district': district_name,
                                'standards': [],
                                'seen_std_ids': set()
                            }
                        else:
                            g = asso_pool[a_name]
                            if not g['regi_no'] and r_regi:
                                g['regi_no'] = r_regi.strip()
                            if not g['charge_person'] and r_cp:
                                g['charge_person'] = r_cp.strip()
                            if not g['issu_auth'] and r_issu:
                                g['issu_auth'] = r_issu.strip()
                            if not g['address'] and r_addr:
                                g['address'] = r_addr.strip()

                        # 如果启用了主发布团标 (publisher_group)，存入标准明细
                        if 'publisher_group' in roles_set:
                            sid_clean = (sid or '').strip()
                            g = asso_pool[a_name]
                            if sid_clean and sid_clean not in g['seen_std_ids']:
                                g['seen_std_ids'].add(sid_clean)
                                g['standards'].append({
                                    'std_id': sid_clean,
                                    'title': stitle or '无标题',
                                    'type_display': '团体标准',
                                    'role_display': '主发布单位',
                                    'drafter_display': '主要发布协会',
                                    'rank': 1,
                                    'status': status_map.get(ex_st, '现行'),
                                    'release_date': str(rdate) if rdate else '-',
                                    'implement_date': str(idate) if idate else '-'
                                })
        except Exception as e:
            logger.error(f"Query std_tb_detail for associations error: {e}")

        # ── 步骤 6.3：反查 compare_conp 对齐官方信用代码与法定代表人 ────────────────
        all_pool_names = list(asso_pool.keys())
        if all_pool_names:
            try:
                with connections['compare_conp'].cursor() as cur:
                    for i in range(0, len(all_pool_names), batch_size):
                        chunk = all_pool_names[i:i + batch_size]
                        ph = ', '.join(['%s'] * len(chunk))
                        cur.execute(f"""
                            SELECT company_name, unified_social_credit_code, legal_representative, province, city, district
                            FROM ent_std_maker
                            WHERE company_name IN ({ph})
                        """, chunk)
                        for cname, ccode, lrep, pr, ci, dist in cur.fetchall():
                            if cname in asso_pool:
                                g = asso_pool[cname]
                                if not g['regi_no'] and ccode:
                                    g['regi_no'] = ccode.strip()
                                lrep_clean = (lrep or '').strip()
                                if lrep_clean and lrep_clean != '-':
                                    g['legal_rep'] = lrep_clean
                                if pr and (not g['province'] or g['province'] == '-'):
                                    g['province'] = pr.strip()
                                if ci and (not g['city'] or g['city'] == '-'):
                                    g['city'] = ci.strip()
                                if dist and (not g['district'] or g['district'] == '-'):
                                    g['district'] = dist.strip()
            except Exception as e:
                logger.warning(f"Failed to align official legal_rep: {e}")

        # ── 步骤 6.4：检索参编起草标准 (团标/国标/行标/地标) ─────────────────────────
        drafter_roles = roles_set & {'drafter_group', 'drafter_national', 'drafter_industry_local'}
        if drafter_roles and all_pool_names:
            try:
                unit_to_assos = {}
                with connections['stsc_db'].cursor() as cur:
                    for i in range(0, len(all_pool_names), batch_size):
                        chunk = all_pool_names[i:i + batch_size]
                        ph = ', '.join(['%s'] * len(chunk))
                        cur.execute(f"""
                            SELECT unit_id, unit_name, full_company_name
                            FROM unit_dict
                            WHERE unit_name IN ({ph}) OR full_company_name IN ({ph})
                        """, chunk * 2)
                        for uid, uname, fname in cur.fetchall():
                            if not uid:
                                continue
                            if uname and uname in asso_pool:
                                unit_to_assos.setdefault(uid, set()).add(uname)
                            if fname and fname in asso_pool:
                                unit_to_assos.setdefault(uid, set()).add(fname)

                    all_uids = list(unit_to_assos.keys())
                    for i in range(0, len(all_uids), batch_size):
                        u_chunk = all_uids[i:i + batch_size]
                        u_ph = ', '.join(['%s'] * len(u_chunk))
                        cur.execute(f"""
                            SELECT 
                                r.unit_id,
                                v.std_id, 
                                v.std_chinesename, 
                                v.std_type, 
                                v.release_date, 
                                v.implement_date, 
                                v.ex_state, 
                                h.draft_unit, 
                                r.rank_order
                            FROM std_unit_relation r
                            JOIN view_std_full v ON r.base_id = v.id
                            LEFT JOIN std_extend_h h ON v.id = h.base_id
                            WHERE r.unit_id IN ({u_ph})
                            ORDER BY v.release_date DESC
                        """, u_chunk)
                        for uid, sid, stitle, stype, rdate, idate, ex_st, drafter, rank in cur.fetchall():
                            sid_clean = (sid or '').strip()
                            if not sid_clean:
                                continue
                            s_no = sid_clean.upper()
                            t_raw = (stype or '').upper()

                            if s_no.startswith('GB') or 'GB' in t_raw or '国标' in t_raw:
                                t_disp = '国家标准'
                                r_key = 'drafter_national'
                            elif s_no.startswith('T/') or s_no.startswith('TB') or '团标' in t_raw or '团体' in t_raw:
                                t_disp = '团体标准'
                                r_key = 'drafter_group'
                            elif s_no.startswith('DB') or '地标' in t_raw or '地方' in t_raw:
                                t_disp = '地方标准'
                                r_key = 'drafter_industry_local'
                            else:
                                t_disp = '行业标准'
                                r_key = 'drafter_industry_local'

                            if r_key not in drafter_roles:
                                continue

                            if rank:
                                rank_disp = f"第{rank}名"
                            elif drafter:
                                parts = drafter.replace(';', ',').replace('，', ',').split(',')
                                rank_disp = " / ".join([p.strip() for p in parts[:2] if p.strip()])
                            else:
                                rank_disp = '参编单位'

                            for a_name in unit_to_assos.get(uid, []):
                                g = asso_pool[a_name]
                                if sid_clean not in g['seen_std_ids']:
                                    g['seen_std_ids'].add(sid_clean)
                                    g['standards'].append({
                                        'std_id': sid_clean,
                                        'title': stitle or '无标题',
                                        'type_display': t_disp,
                                        'role_display': '参编单位',
                                        'drafter_display': rank_disp,
                                        'rank': rank or 99,
                                        'status': status_map.get(ex_st, '现行'),
                                        'release_date': str(rdate) if rdate else '-',
                                        'implement_date': str(idate) if idate else '-'
                                    })
            except Exception as e:
                logger.error(f"Query drafted standards for associations error: {e}")

        # ── 步骤 6.5：构建 Sheet 1 与 Sheet 2 报表数据 ───────────────────────
        sorted_assos = sorted(asso_pool.values(), key=lambda x: len(x['standards']), reverse=True)

        if not include_zero_standard:
            sorted_assos = [g for g in sorted_assos if len(g['standards']) > 0]

        detail_idx = 1
        for idx, g in enumerate(sorted_assos, 1):
            stds = g['standards']
            total_stds = len(stds)
            pub_group_cnt = sum(1 for s in stds if s['role_display'] == '主发布单位')
            draft_group_cnt = sum(1 for s in stds if s['role_display'] == '参编单位' and s['type_display'] == '团体标准')
            draft_national_cnt = sum(1 for s in stds if s['type_display'] == '国家标准')
            draft_other_cnt = sum(1 for s in stds if s['type_display'] in ('行业标准', '地方标准'))
            active_cnt = sum(1 for s in stds if s['status'] == '现行')

            valid_dates = [s['release_date'] for s in stds if s['release_date'] and s['release_date'] != '-']
            earliest_date = min(valid_dates) if valid_dates else '-'
            latest_date = max(valid_dates) if valid_dates else '-'

            lrep = g.get('legal_rep') or ''
            cp = g.get('charge_person') or ''
            if lrep and cp and lrep != cp:
                person_disp = f"{lrep} (申报负责人: {cp})"
            elif lrep:
                person_disp = lrep
            elif cp:
                person_disp = cp
            else:
                person_disp = '-'

            tb_asso_rows.append({
                '序号': idx,
                '协会名称': g['name'],
                '统一社会信用代码': g['regi_no'] or '-',
                '法定代表人/负责人': person_disp,
                '所属省份': g['province'] or '-',
                '所属城市': g['city'] or '-',
                '所属区县': g['district'] or '-',
                '登记/主管机关': g['issu_auth'] or '-',
                '办公/注册详细地址': g['address'] or '-',
                '主发布团标数': pub_group_cnt,
                '参编团标数': draft_group_cnt,
                '参编国标数': draft_national_cnt,
                '参编行/地标数': draft_other_cnt,
                '符合条件标准总计': total_stds,
                '现行标准数': active_cnt,
                '首次发布日期': earliest_date,
                '最近发布日期': latest_date,
            })

            for s in stds:
                tb_detail_rows.append({
                    '序号': detail_idx,
                    '归属社会组织名称': g['name'],
                    '统一社会信用代码': g['regi_no'] or '-',
                    '标准编号': s['std_id'],
                    '标准中文名称': s['title'],
                    '标准类别': s['type_display'],
                    '参与角色/身份': s['role_display'],
                    '署名排名/起草单位': s['drafter_display'],
                    '标准状态': s['status'],
                    '发布日期': s['release_date'],
                    '实施日期': s['implement_date'],
                })
                detail_idx += 1

    if not company_list and not tb_asso_rows:
        raise ValueError("按当前过滤条件未检索到任何匹配的企业或社会团体记录")

    # 7. 文件写出
    exports_dir = os.path.join(settings.MEDIA_ROOT, 'exports')
    os.makedirs(exports_dir, exist_ok=True)

    file_prefix = f"advanced_export_{uuid_str}"

    co_cols = ['企业名称', '统一信用代码', '省份', '城市', '区县', '曾用名', '企业(机构)类型', '企业规模', '登记状态']
    std_cols = ['标准号', '标准名称', '企业名称', '标准状态', '标准类型', '制修订', '发布日期', '实施日期', 'ICS', 'CCS', '国民经济分类']
    other_std_cols = ['标准号', '标准名称', '标准状态', '标准类型', '制修订', '发布日期', '实施日期', 'ICS', 'ICS中文名称', 'CCS', 'CCS中文名称', '起草单位', '起草单位排名名次', '国民经济分类']
    asso_cols = [
        '序号', '协会名称', '统一社会信用代码', '法定代表人/负责人',
        '所属省份', '所属城市', '所属区县', '登记/主管机关', '办公/注册详细地址',
        '主发布团标数', '参编团标数', '参编国标数', '参编行/地标数',
        '符合条件标准总计', '现行标准数', '首次发布日期', '最近发布日期'
    ]
    detail_cols = [
        '序号', '归属社会组织名称', '统一社会信用代码', '标准编号', '标准中文名称',
        '标准类别', '参与角色/身份', '署名排名/起草单位', '标准状态', '发布日期', '实施日期'
    ]

    sheet_asso_name = '社会组织及标准资产概览'
    sheet_detail_name = '社会组织标准明细全清单'

    if file_format == 'separate_zip':
        zip_filename = f"{file_prefix}.zip"
        zip_filepath = os.path.join(exports_dir, zip_filename)

        written_any = False
        with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zf:
            if 'enterprise' in content_set and company_rows:
                df_co = pd.DataFrame(company_rows, columns=co_cols)
                co_buf = io.BytesIO()
                df_co.to_excel(co_buf, index=False, sheet_name='企业目录', engine='openpyxl')
                zf.writestr('1_企业目录.xlsx', co_buf.getvalue())
                written_any = True

            if 'enterprise_standard' in content_set and standard_rows:
                df_std = pd.DataFrame(standard_rows, columns=std_cols)
                std_buf = io.BytesIO()
                df_std.to_excel(std_buf, index=False, sheet_name='企标目录', engine='openpyxl')
                zf.writestr('2_企标目录.xlsx', std_buf.getvalue())
                written_any = True

            if 'other_standard' in content_set and other_standard_rows:
                df_other = pd.DataFrame(other_standard_rows, columns=other_std_cols)
                other_buf = io.BytesIO()
                df_other.to_excel(other_buf, index=False, sheet_name='国行地团标目录', engine='openpyxl')
                zf.writestr('3_国行地团标目录.xlsx', other_buf.getvalue())
                written_any = True

            if 'tb_association' in content_set and tb_asso_rows:
                df_asso = pd.DataFrame(tb_asso_rows, columns=asso_cols)
                asso_buf = io.BytesIO()
                df_asso.to_excel(asso_buf, index=False, sheet_name=sheet_asso_name, engine='openpyxl')
                zf.writestr(f'4_{sheet_asso_name}.xlsx', asso_buf.getvalue())

                df_detail = pd.DataFrame(tb_detail_rows, columns=detail_cols)
                detail_buf = io.BytesIO()
                df_detail.to_excel(detail_buf, index=False, sheet_name=sheet_detail_name, engine='openpyxl')
                zf.writestr(f'5_{sheet_detail_name}.xlsx', detail_buf.getvalue())
                written_any = True

            if not written_any:
                empty_df = pd.DataFrame([{'提示': '当前筛选条件下未检索到任何符合条件的记录'}])
                buf = io.BytesIO()
                empty_df.to_excel(buf, index=False, sheet_name='无匹配数据', engine='openpyxl')
                zf.writestr('无匹配数据.xlsx', buf.getvalue())

        return f"exports/{zip_filename}"
    else:
        excel_filename = f"{file_prefix}.xlsx"
        excel_filepath = os.path.join(exports_dir, excel_filename)

        written_any = False
        with pd.ExcelWriter(excel_filepath, engine='openpyxl') as writer:
            if 'enterprise' in content_set and company_rows:
                df_co = pd.DataFrame(company_rows, columns=co_cols)
                df_co.to_excel(writer, sheet_name='企业目录', index=False)
                written_any = True
            if 'enterprise_standard' in content_set and standard_rows:
                df_std = pd.DataFrame(standard_rows, columns=std_cols)
                df_std.to_excel(writer, sheet_name='企标目录', index=False)
                written_any = True
            if 'other_standard' in content_set and other_standard_rows:
                df_other = pd.DataFrame(other_standard_rows, columns=other_std_cols)
                df_other.to_excel(writer, sheet_name='国行地团标目录', index=False)
                written_any = True
            if 'tb_association' in content_set and tb_asso_rows:
                df_asso = pd.DataFrame(tb_asso_rows, columns=asso_cols)
                df_asso.to_excel(writer, sheet_name=sheet_asso_name, index=False)
                df_detail = pd.DataFrame(tb_detail_rows, columns=detail_cols)
                df_detail.to_excel(writer, sheet_name=sheet_detail_name, index=False)
                written_any = True

            if not written_any:
                empty_df = pd.DataFrame([{'提示': '当前筛选条件下未检索到任何符合条件的记录'}])
                empty_df.to_excel(writer, sheet_name='无匹配数据', index=False)

        return f"exports/{excel_filename}"




