"""
standards.services — 标准业务逻辑层

功能：
  - 特殊标准号 clean_id 生成（严格区分前缀）
  - 规范性引用 Excel 解析（模块二）
  - 国标引用热度统计
  - ZIP 打包异步任务
"""

import re
import io
import zipfile
import openpyxl
from django.db import transaction
from django.db.models import F, Q

from .models import Standard, NormativeReference


# ============================================================
# 特殊标准号处理
# ⚠️ 关键规则：严格保留省份简称前缀和少数民族语言代码
# ============================================================

# 已知特殊前缀模式（少数民族语言代码、省份简称等）
# 必须放在通用前缀匹配之前
SPECIAL_PREFIX_PATTERNS = [
    # 少数民族语言代码：如 DBY（彝文）、DBZ（藏文）等
    r'^(DB[A-Z]{1,2})',
    # 省份简称+标准类型：如 新Q/T、藏DB、蒙Q/T
    r'^([新藏蒙琼黔陕甘皖滇闽鄂赣豫湘苏浙粤川吉辽冀津沪京渝宁桂内][A-Z])',
    # 带斜杠的特殊编号
    r'^([A-Z]{2,4}/[A-Z])',
]

def generate_clean_id(standard_no: str) -> str:
    """
    生成标准化 clean_id，用于检索和去重。

    ⚠️ 核心规则：
    1. 保留所有特殊前缀（"新Q"、"DBY"等）
    2. 不同前缀 = 不同标准，绝不合并
    3. 仅移除多余空格，统一大写

    Args:
        standard_no: 原始标准号（如 "新Q/T 123-2026"、"DBY/T 001-2025"）

    Returns:
        标准化 clean_id（如 "新Q/T123-2026"、"DBY/T001-2025"）
    """
    if not standard_no:
        return ''

    # 去除首尾空格，统一大写字母部分
    clean = standard_no.strip()

    # 移除内部多余空格（但保留前缀中的汉字）
    # 只移除数字/字母之间的空格（版本号前的空格）
    clean = re.sub(r'(?<=[A-Z0-9])\s+(?=[0-9])', '', clean)

    # 统一连字符
    clean = re.sub(r'[—–]', '-', clean)

    return clean


def validate_standard_no(standard_no: str) -> bool:
    """
    验证标准号格式是否合法。
    接受所有已知前缀（包含特殊前缀），不能因校验丢失数据。
    """
    if not standard_no or len(standard_no.strip()) < 2:
        return False
    # 只要不是空值，都接受（宽松校验，不能丢数据）
    return True


# ============================================================
# 规范性引用 Excel 解析（模块二核心）
# ============================================================

CITATION_EXCEL_REQUIRED_COLS = ['企标号', '被引用标准号']


def parse_normative_reference_excel(file_obj) -> dict:
    """
    解析规范性引用 Excel 文件（支持原 2 列格式与新 10 列批量批次格式）
    """
    import pandas as pd
    import uuid
    from django.db import transaction
    from django.db.models import F
    from companies.models import Company
    from standards.models import Standard, NormativeReference

    result = {
        'parsed_standards': 0, 
        'citations_added': 0, 
        'companies_created': 0, 
        'standards_created': 0,
        'pdf_aligned_count': 0,
        'errors': []
    }

    try:
        df = pd.read_excel(file_obj)
    except Exception as e:
        result['errors'].append(f'文件解析失败: {str(e)}')
        return result

    if df.empty:
        result['errors'].append('文件内容为空')
        return result

    # 1. 检测是否是 10 列批次导入格式 (通过包含的核心列 '企标号', '公司名称', '企标中引用的标准号')
    if '企标号' in df.columns and '公司名称' in df.columns and '企标中引用的标准号' in df.columns:
        with transaction.atomic():
            for idx, row in df.iterrows():
                row_idx = idx + 2  # Excel 行号 1-indexed (加上表头)
                
                company_name = str(row['公司名称']).strip() if pd.notna(row['公司名称']) else ''
                std_no = str(row['企标号']).strip() if pd.notna(row['企标号']) else ''
                std_name = str(row['企标名']).strip() if '企标名' in df.columns and pd.notna(row['企标名']) else ''
                
                # 匹配被引用标准号（优先完整标准号，其次中引标准号）
                cited_no = None
                if '发布时引用的完整标准号' in df.columns and pd.notna(row['发布时引用的完整标准号']):
                    cited_no = str(row['发布时引用的完整标准号']).strip()
                elif pd.notna(row['企标中引用的标准号']):
                    cited_no = str(row['企标中引用的标准号']).strip()

                latest_no = ''
                if '最新标准号' in df.columns and pd.notna(row['最新标准号']):
                    latest_no = str(row['最新标准号']).strip()
                else:
                    latest_no = cited_no or ''
                    
                if not company_name or not std_no or not cited_no:
                    continue
                    
                try:
                    # 1. 自动对齐/建档企业
                    company, created_co = Company.objects.get_or_create(
                        name=company_name,
                        defaults={
                            'credit_code': f'TEMP_{uuid.uuid4().hex[:14].upper()}',
                            'status': 'active'
                        }
                    )
                    if created_co:
                        result['companies_created'] += 1
                        
                    # 2. 自动对齐/建档企标
                    clean_id = generate_clean_id(std_no)
                    standard, created_std = Standard.objects.get_or_create(
                        standard_no=std_no,
                        defaults={
                            'clean_id': clean_id,
                            'title': std_name or '批量入库标准',
                            'company': company,
                            'type': 'enterprise',
                            'is_parsed': True
                        }
                    )
                    if created_std:
                        result['standards_created'] += 1
                    else:
                        if not standard.is_parsed:
                            standard.is_parsed = True
                            standard.save(update_fields=['is_parsed'])
                            result['parsed_standards'] += 1
                            
                    # 3. 关联或建档被引用的国标（统计引用热度）
                    cited_std = Standard.objects.filter(standard_no=cited_no, type='national').first()
                    
                    # 4. 创建规范性引用关系记录
                    ref, created_ref = NormativeReference.objects.get_or_create(
                        source_standard=standard,
                        cited_standard_no=cited_no,
                        defaults={
                            'cited_standard': cited_std,
                            'latest_standard_no': latest_no
                        }
                    )
                    if not created_ref and latest_no and ref.latest_standard_no != latest_no:
                        ref.latest_standard_no = latest_no
                        ref.save(update_fields=['latest_standard_no'])

                    if created_ref:
                        result['citations_added'] += 1
                        # 累加国标引用热度计数
                        if cited_std:
                            Standard.objects.filter(pk=cited_std.pk).update(citation_count=F('citation_count') + 1)
                            
                except Exception as e:
                    result['errors'].append(f"第 {row_idx} 行解析失败: {str(e)}")
                    
        # 5. 后置自动扫盘匹配一次 PDF 相对路径
        try:
            scan_res = scan_and_align_pdf_assets()
            result['pdf_aligned_count'] = scan_res.get('matched_count', 0)
        except Exception as scan_err:
            result['errors'].append(f"关联扫盘对齐 PDF 失败: {str(scan_err)}")
            
        return result

    else:
        # 2. 原来的 2 列格式兼容导入
        parsed_standard_nos = set()
        citation_pairs = []  # [(企标号, 被引用标准号), ...]
        
        for idx, row in df.iterrows():
            row_idx = idx + 2
            if len(row) < 2:
                continue
            source_no = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ''
            cited_no = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ''
            
            if not source_no:
                continue
            parsed_standard_nos.add(source_no)
            if cited_no:
                citation_pairs.append((source_no, cited_no))

        with transaction.atomic():
            updated = Standard.objects.filter(
                standard_no__in=parsed_standard_nos,
                type='enterprise'
            ).update(is_parsed=True)
            result['parsed_standards'] = updated

            if updated < len(parsed_standard_nos):
                not_found = parsed_standard_nos - set(
                    Standard.objects.filter(
                        standard_no__in=parsed_standard_nos
                    ).values_list('standard_no', flat=True)
                )
                for no in not_found:
                    result['errors'].append(f'企标未找到: {no}（可能未入库）')

            source_map = {
                s.standard_no: s
                for s in Standard.objects.filter(standard_no__in=parsed_standard_nos)
            }

            cited_nos = {cited_no for _, cited_no in citation_pairs}
            cited_map = {
                s.standard_no: s
                for s in Standard.objects.filter(
                    standard_no__in=cited_nos,
                    type='national'
                )
            }

            citation_count_delta = {}

            for source_no, cited_no in citation_pairs:
                source = source_map.get(source_no)
                if not source:
                    continue

                cited = cited_map.get(cited_no)

                try:
                    ref, created_ref = NormativeReference.objects.get_or_create(
                        source_standard=source,
                        cited_standard_no=cited_no,
                        defaults={
                            'cited_standard': cited,
                            'latest_standard_no': cited_no
                        }
                    )
                    if created_ref:
                        result['citations_added'] += 1
                        if cited:
                            citation_count_delta[cited.standard_no] = citation_count_delta.get(cited.standard_no, 0) + 1
                except Exception as e:
                    result['errors'].append(f'引用记录创建失败 {source_no}→{cited_no}: {str(e)}')

            for cited_no, delta in citation_count_delta.items():
                Standard.objects.filter(standard_no=cited_no, type='national').update(
                    citation_count=F('citation_count') + delta
                )

        # 5. 后置自动扫盘匹配一次 PDF 相对路径
        try:
            scan_res = scan_and_align_pdf_assets()
            result['pdf_aligned_count'] = scan_res.get('matched_count', 0)
        except Exception as scan_err:
            result['errors'].append(f"关联扫盘对齐 PDF 失败: {str(scan_err)}")

        return result


def get_citation_ranking(limit: int = 20):
    """
    获取国标引用热度排行榜（基于被引用的“发布时引用的完整标准号”进行累加统计，并关联展示“最新标准号”）
    """
    from django.db.models import Count, Max
    from standards.models import NormativeReference

    ranking = (
        NormativeReference.objects
        .values('cited_standard_no')
        .annotate(
            citation_count=Count('id'),
            latest_no=Max('latest_standard_no')
        )
        .order_by('-citation_count')[:limit]
    )

    results = []
    for idx, item in enumerate(ranking):
        cited_no = item['cited_standard_no']
        latest_no = item['latest_no'] or cited_no
        results.append({
            'id': idx + 1,
            'standard_no': cited_no,      # 发布时引用的完整标准号
            'title': latest_no,           # 最新标准号（替代原“标准名称”列显示）
            'citation_count': item['citation_count']
        })
    return results


# ============================================================
# 共享磁盘文件对齐与扫盘服务
# ============================================================

def normalize_string(s: str) -> str:
    """
    去除所有非字母数字字符并转为小写，用于模糊匹配标准号与文件名
    """
    if not s:
        return ""
    if s.lower().endswith('.pdf'):
        s = s[:-4]
    return re.sub(r'[^a-zA-Z0-9]', '', s).lower()


def scan_and_align_pdf_assets() -> dict:
    """
    自动遍历 Y:\磁盘阵列\标准文件下载\企标下载\整合\ 目录下的平铺 PDF 文件，
    对库内缺失 pdf_file 相对路径的企标进行多维子串模糊匹配对齐。
    """
    import os
    from django.conf import settings
    
    shared_root = getattr(settings, 'SHARED_DISK_ROOT', r"Y:\磁盘阵列\标准文件下载\企标下载")
    target_dir = os.path.join(shared_root, "整合")
    
    if not os.path.exists(target_dir):
        return {"success": False, "matched_count": 0, "error": f"物理磁盘路径不存在: {target_dir}"}
        
    # 1. 扫描整合目录下所有的 pdf 文件并建立归一化映射
    try:
        disk_files = [f for f in os.listdir(target_dir) if f.lower().endswith('.pdf')]
    except Exception as e:
        return {"success": False, "matched_count": 0, "error": f"读取磁盘目录失败: {str(e)}"}
        
    normalized_file_map = {normalize_string(f): f for f in disk_files}
    
    # 2. 查询缺失文件或物理路径失效的企标进行对齐
    all_standards = Standard.objects.filter(type='enterprise')
    unlinked_standards = []
    
    for std in all_standards:
        if not std.pdf_file or not std.pdf_file.name:
            unlinked_standards.append(std)
            continue
            
        # 检查物理文件是否真实存在于本地或共享盘中
        rel_path = std.pdf_file.name
        
        # 本地 media 路径
        local_exists = os.path.exists(os.path.join(settings.MEDIA_ROOT, rel_path))
        # 共享磁盘路径
        shared_exists = os.path.exists(os.path.join(shared_root, rel_path))
        
        # 兜底清理 media/ 前缀检查
        if not shared_exists and rel_path.startswith('media/'):
            clean_path = rel_path.replace('media/', '', 1)
            local_exists = local_exists or os.path.exists(os.path.join(settings.MEDIA_ROOT, clean_path))
            
        if not local_exists and not shared_exists:
            # 物理文件缺失，需要扫盘重新匹配对齐
            unlinked_standards.append(std)
    
    matched_count = 0
    for std in unlinked_standards:
        std_norm = normalize_string(std.standard_no)
        matched_filename = None
        
        # 2a. 精确匹配
        if std_norm in normalized_file_map:
            matched_filename = normalized_file_map[std_norm]
        else:
            # 2b. 模糊包含匹配
            for file_norm, filename in normalized_file_map.items():
                if std_norm in file_norm or file_norm in std_norm:
                    matched_filename = filename
                    break
                    
        if matched_filename:
            std.pdf_file = f"整合/{matched_filename}"
            std.save(update_fields=['pdf_file'])
            matched_count += 1
            
    return {"success": True, "matched_count": matched_count}


# ============================================================
# ZIP 打包服务（Celery 异步任务辅助）
# ============================================================

def create_zip_from_standards(standard_ids: list, include_excel: bool = False) -> bytes:
    """
    将指定标准的 PDF 文件打包成 ZIP，并可选地生成企业与标准地域对应关系的 Excel 清单。

    由 Celery 任务调用（异步执行），
    优先使用 disk_filename 字段（共享磁盘阵列），完全移除对 pdf_file.path 的依赖。
    文件存在才加入 ZIP，不存在则跳过并记录日志。
    """
    import os
    import logging
    import pandas as pd
    from django.conf import settings

    logger = logging.getLogger('standards.services')
    standards = Standard.objects.select_related('company', 'company__province', 'company__city').filter(id__in=standard_ids)
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


# ============================================================
# Excel 批量导入企标（按照爬取 Excel 表头与核心业务逻辑）
# ============================================================

def import_standards_from_excel(file_obj) -> dict:
    """
    从爬取的 Excel 文件批量导入企标和企业信息（高度融合核心业务与 LBS 定位）

    适合 crawled Excel 表头格式，并自动对齐去重、物理路径分层与直辖市二级结构兼容。
    """
    import pandas as pd
    from django.utils import timezone
    from companies.models import Company, Province, City, District
    
    result = {
        'success': 0,
        'skipped': 0,
        'companies_created': 0,
        'companies_updated': 0,
        'errors': []
    }
    
    try:
        df = pd.read_excel(file_obj)
    except Exception as e:
        result['errors'].append(f'文件解析失败: {str(e)}')
        return result
        
    today_str = timezone.now().strftime("%Y/%m/%d")
    
    standards_to_create = []
    companies_created_count = 0
    companies_updated_count = 0
    skipped_duplicates_count = 0
    
    with transaction.atomic():
        for idx, row in df.iterrows():
            credit_code = str(row.get('统一社会信用代码', '')).strip()
            company_name = str(row.get('起草单位/企业名称', '')).strip()
            
            if not credit_code or credit_code == 'nan' or not company_name or company_name == 'nan':
                continue
                
            # --- 步骤 A: 级联匹配省市区外键 ---
            province = None
            city = None
            district = None
            
            geo_str = str(row.get('行政区划', '')).strip()
            if geo_str and geo_str != 'nan' and '-' in geo_str:
                geo_parts = geo_str.split('-')
                if len(geo_parts) >= 1:
                    province = Province.objects.filter(name__icontains=geo_parts[0].replace("省", "")).first()
                
                # 处理直辖市两级行政区划 (如北京市-海淀区)
                if len(geo_parts) == 2 and province:
                    city = City.objects.filter(name__in=["市辖区", province.name.replace("市", "")], province=province).first()
                    if not city:
                        city = City.objects.filter(province=province).first()
                    if city:
                        district = District.objects.filter(name__icontains=geo_parts[1], city=city).first()
                else:
                    # 标准三级区划结构 (如安徽省-安庆市-桐城市)
                    if len(geo_parts) >= 2 and province:
                        city = City.objects.filter(name__icontains=geo_parts[1].replace("市", ""), province=province).first()
                    if len(geo_parts) >= 3 and city:
                        district = District.objects.filter(name__icontains=geo_parts[2], city=city).first()
            
            # --- 步骤 B: 根据大字典自动获取 LBS 中心经纬度 ---
            company_lat = None
            company_lng = None
            if district and district.latitude and district.longitude:
                company_lat = district.latitude
                company_lng = district.longitude
            elif city and city.latitude and city.longitude:
                company_lat = city.latitude
                company_lng = city.longitude

            # --- 步骤 C: 新建或安全更新企业信息（按照信用代码去重） ---
            legal_person = str(row.get('法定代表人', '')).strip()
            if not legal_person or legal_person == 'nan':
                legal_person = ''
                
            address = str(row.get('注册地址', '')).strip()
            if not address or address == 'nan':
                address = ''

            company, created = Company.objects.get_or_create(
                credit_code=credit_code,
                defaults={
                    'name': company_name,
                    'legal_person': legal_person,
                    'address': address,
                    'province': province,
                    'city': city,
                    'district': district,
                    'latitude': company_lat,
                    'longitude': company_lng,
                    'status': 'active'
                }
            )
            
            if created:
                companies_created_count += 1
            else:
                updated = False
                if not company.latitude and company_lat:
                    company.latitude = company_lat
                    company.longitude = company_lng
                    updated = True
                if not company.district and district:
                    company.province = province
                    company.city = city
                    company.district = district
                    updated = True
                if updated:
                    company.save()
                    companies_updated_count += 1
            
            # --- 步骤 D: 拼装标准记录并建立外键绑定 ---
            standard_no = str(row.get('标准编号', '')).strip()
            standard_title = str(row.get('标准名称', '')).strip()
            if standard_title.startswith('《') and standard_title.endswith('》'):
                standard_title = standard_title[1:-1].strip()
            
            if not standard_no or standard_no == 'nan':
                continue
                
            clean_id = generate_clean_id(standard_no)
            
            if Standard.objects.filter(clean_id=clean_id).exists():
                skipped_duplicates_count += 1
                continue
                
            publish_date = None
            pub_date_val = row.get('公开时间')
            if pd.notnull(pub_date_val):
                try:
                    publish_date = pd.to_datetime(pub_date_val).date()
                except:
                    pass
            
            status_str = str(row.get('标准状态', ''))
            standard_status = 'active'
            if '废止' in status_str:
                standard_status = 'deprecated'
            elif '草案' in status_str:
                standard_status = 'draft'

            pdf_filename = str(row.get('PDF文件名', '')).strip()
            pdf_db_path = f"pdfs/{today_str}/{pdf_filename}" if pdf_filename and pdf_filename != 'nan' else ''
            
            new_standard = Standard(
                standard_no=standard_no,
                clean_id=clean_id,
                type='enterprise',
                title=standard_title if standard_title != 'nan' else '',
                company=company,
                pdf_file=pdf_db_path,
                publish_date=publish_date,
                status=standard_status
            )
            standards_to_create.append(new_standard)
            
        if standards_to_create:
            Standard.objects.bulk_create(standards_to_create, batch_size=1000)
            
    # 自动进行 Y:\ 磁盘扫盘匹配对齐，补全 relative_path (pdf_file)
    try:
        scan_res = scan_and_align_pdf_assets()
        result['pdf_aligned_count'] = scan_res.get('matched_count', 0)
    except Exception:
        pass
            
    result['success'] = len(standards_to_create)
    result['skipped'] = skipped_duplicates_count
    result['companies_created'] = companies_created_count
    result['companies_updated'] = companies_updated_count
    return result
