import os
import io
import zipfile
import logging
import pandas as pd
from django.conf import settings
from django.db import connections
from django.db.models import Q
from standards.models import Standard
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
