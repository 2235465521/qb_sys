import os
import io
import zipfile
import logging
import pandas as pd
from django.conf import settings
from django.db import connections
from django.db.models import Q
from standards.models import Standard, NormativeReference
from standards.services import generate_clean_id
from companies.models import Company
from companies.services import search_companies


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
                        FROM mydate.view_std_full v
                        LEFT JOIN mydate.std_filepath f ON v.id = f.base_id
                        LEFT JOIN mydate.std_extend_h h ON v.id = h.base_id
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


def fetch_std_details_map(std_nos: list) -> dict:
    """
    批量从本地 Standard 表和穿透 stsc_db 获取标准的标题、状态、类型、ICS、CCS。
    支持国标 (std_gb_detail)、行标 (std_hb_detail)、地标 (std_db_detail)、团标 (std_tb_detail) 明细表联合查询。
    """
    if not std_nos:
        return {}

    details_map = {}
    from standards.services import generate_clean_id
    clean_to_raw = {}
    for no in std_nos:
        clean = generate_clean_id(no)
        clean_to_raw[clean] = no

    # 1. 查询本地 Standard 表
    local_stds = Standard.objects.filter(
        Q(standard_no__in=std_nos) | Q(clean_id__in=list(clean_to_raw.keys()))
    )
    for std in local_stds:
        no = std.standard_no
        item_info = {
            'title': std.title or '',
            'status': std.get_status_display() or '现行',
            'type': std.get_type_display() if (std.type and std.type != 'enterprise') else detect_std_type_display(no),
            'ics': std.ics or '',
            'ccs': std.ccs or '',
        }
        details_map[no] = item_info
        if std.clean_id:
            details_map[std.clean_id] = item_info
        if std.clean_id in clean_to_raw:
            details_map[clean_to_raw[std.clean_id]] = item_info

    # 2. 查漏：若有未查到的标准号，穿透到 stsc_db 的 view_std_full 与各明细表
    missing_cleans = [c for c in clean_to_raw.keys() if (c not in details_map and clean_to_raw[c] not in details_map)]
    if missing_cleans:
        try:
            with connections['stsc_db'].cursor() as cursor:
                cursor.execute("SET NAMES utf8mb4;")
                chunk_size = 500
                for i in range(0, len(missing_cleans), chunk_size):
                    chunk = missing_cleans[i:i + chunk_size]
                    fmt = ','.join(['%s'] * len(chunk))
                    sql = f"""
                        SELECT v.std_id, v.std_chinesename, v.ex_state, v.std_type,
                               COALESCE(v.ics, gb.ics, hb.ics, db.ics, tb.ics) AS ics,
                               COALESCE(v.ccs, gb.ccs, hb.ccs, db.ccs, tb.ccs) AS ccs
                        FROM mydate.view_std_full v
                        LEFT JOIN mydate.std_gb_detail gb ON v.id = gb.base_id
                        LEFT JOIN mydate.std_hb_detail hb ON v.id = hb.base_id
                        LEFT JOIN mydate.std_db_detail db ON v.id = db.base_id
                        LEFT JOIN mydate.std_tb_detail tb ON v.id = tb.base_id
                        WHERE REPLACE(REPLACE(v.std_id, ' ', ''), '—', '-') IN ({fmt})
                    """
                    cursor.execute(sql, tuple(chunk))
                    for row in cursor.fetchall():
                        s_id = row[0]
                        title = row[1] or ''
                        st_code = row[2]

                        if st_code == 1:
                            ex_state = '现行'
                        elif st_code == 2:
                            ex_state = '即将实施'
                        elif st_code == 0:
                            ex_state = '废止'
                        else:
                            ex_state = '现行'

                        raw_type = row[3] or ''
                        type_disp = detect_std_type_display(s_id, raw_type)
                        ics = row[4] or ''
                        ccs = row[5] or ''

                        item_dict = {
                            'title': title,
                            'status': ex_state,
                            'type': type_disp,
                            'ics': ics,
                            'ccs': ccs,
                        }

                        clean_ver = generate_clean_id(s_id)
                        details_map[s_id] = item_dict
                        details_map[clean_ver] = item_dict

                        raw_no = clean_to_raw.get(clean_ver, s_id)
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
    qs = Company.objects.select_related('province', 'city', 'district').all()

    if export_scope == 'selected' and enterprise_ids:
        qs = qs.filter(id__in=enterprise_ids)
    else:
        # 应用基础过滤条件
        q = base_filters.get('q') or base_filters.get('query')
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(credit_code__icontains=q))

        province_id = base_filters.get('province_id') or base_filters.get('province')
        if province_id:
            qs = qs.filter(province_id=province_id)

        city_id = base_filters.get('city_id') or base_filters.get('city')
        if city_id:
            qs = qs.filter(city_id=city_id)

        district_id = base_filters.get('district_id') or base_filters.get('district')
        if district_id:
            qs = qs.filter(district_id=district_id)

        co_status = base_filters.get('status')
        if co_status:
            qs = qs.filter(status=co_status)

    # 2. 高级过滤：企业(机构)类型包含/排除模式
    agency_type_mode = advanced_filters.get('agency_type_mode', 'include')
    agency_types = advanced_filters.get('agency_types', [])
    if agency_types and isinstance(agency_types, list):
        agency_q = Q()
        for atype in agency_types:
            if atype:
                agency_q |= Q(company_type__icontains=atype)
        if agency_type_mode == 'exclude':
            qs = qs.exclude(agency_q)
        else:
            qs = qs.filter(agency_q)

    # 上限保护：10 万条数据
    company_list = list(qs[:100000])
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
            standard_rows.append({
                '标准号': s_no,
                '标准名称': std.title or '',
                '标准状态': std.get_status_display() or '现行',
                '标准类型': std.get_type_display() or '企业标准',
                '制修订': '制定',
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

        # b. 企标规范性引用的国/行/地/团标
        ent_stds = Standard.objects.filter(company_id__in=comp_ids, type='enterprise')
        refs = NormativeReference.objects.select_related('cited_standard', 'source_standard__company').filter(
            source_standard__in=ent_stds
        )
        for ref in refs:
            s_no = (ref.cited_standard_no or '').strip()
            if not s_no or s_no in seen_nos:
                continue
            seen_nos.add(s_no)
            other_items.append({
                's_no': s_no,
                'std': ref.cited_standard,
                'industry_category': ref.source_standard.company.industry_category if (ref.source_standard and ref.source_standard.company) else ''
            })

        # 批量从 stsc_db / 本地 Standard 表抓取补全标题、状态、类型、ICS、CCS
        nos_to_fetch = [item['s_no'] for item in other_items]
        details_map = fetch_std_details_map(nos_to_fetch)

        for item in other_items:
            s_no = item['s_no']
            std = item['std']
            clean_ver = generate_clean_id(s_no)
            d_info = details_map.get(s_no) or details_map.get(clean_ver) or {}



            title = d_info.get('title') or (std.title if std else '')
            status = d_info.get('status') or (std.get_status_display() if std else '现行')
            stype = d_info.get('type') or (std.get_type_display() if (std and std.type != 'enterprise') else detect_std_type_display(s_no))

            ics = d_info.get('ics') or (std.ics if std else '')
            ccs = d_info.get('ccs') or (std.ccs if std else '')

            other_standard_rows.append({
                '标准号': s_no,
                '标准名称': title,
                '标准状态': status,
                '标准类型': stype,
                '制修订': '制定',
                'ICS': ics,
                'CCS': ccs,
                '国民经济分类': item['industry_category'],
            })

    # 6. 文件写出
    exports_dir = os.path.join(settings.MEDIA_ROOT, 'exports')
    os.makedirs(exports_dir, exist_ok=True)

    file_prefix = f"advanced_export_{uuid_str}"

    co_cols = ['企业名称', '统一信用代码', '省份', '城市', '区县', '曾用名', '企业(机构)类型', '企业规模', '登记状态']
    std_cols = ['标准号', '标准名称', '标准状态', '标准类型', '制修订', 'ICS', 'CCS', '国民经济分类']

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
                df_other = pd.DataFrame(other_standard_rows, columns=std_cols)
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
                df_other = pd.DataFrame(other_standard_rows, columns=std_cols)
                df_other.to_excel(writer, sheet_name='国行地团标目录', index=False)

        return f"exports/{excel_filename}"




