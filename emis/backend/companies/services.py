"""
companies.services — 企业业务逻辑层

按"胖 Model / 瘦 View"原则，复杂逻辑不写在 views.py 中。

功能：
  - 多维检索（行政/LBS/关键词）
  - Excel 批量导入（含查重校验）
  - Excel 导出
"""

import math
import io
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from django.db import transaction, IntegrityError
from django.db.models import Q

from .models import Company, Province, City, District


# ============================================================
# LBS 空间检索（MySQL ST_Distance_Sphere）
# ============================================================

def search_companies_by_lbs(center_lat: float, center_lng: float, radius_km: float):
    """
    基于经纬度和半径（km）检索范围内的企业。

    使用 MySQL 8.x 内置 ST_Distance_Sphere 函数，
    不依赖 PostGIS，返回在圆形范围内的企业 QuerySet。

    Args:
        center_lat: 中心点纬度
        center_lng: 中心点经度
        radius_km:  搜索半径（公里）

    Returns:
        带距离注解的 Company QuerySet
    """
    from django.db.models.expressions import RawSQL
    from django.db.models import FloatField

    radius_meters = radius_km * 1000

    # MySQL 8.x: ST_Distance_Sphere(POINT(lng, lat), POINT(center_lng, center_lat))
    distance_expr = RawSQL(
        "ST_Distance_Sphere(POINT(%s, %s), POINT(longitude, latitude))",
        (center_lng, center_lat),
        output_field=FloatField()
    )

    return (
        Company.objects
        .filter(is_deleted=False, status='active')
        .exclude(latitude__isnull=True)
        .exclude(longitude__isnull=True)
        .annotate(distance_meters=distance_expr)
        .filter(distance_meters__lte=radius_meters)
        .order_by('distance_meters')
    )


# ============================================================
# 多维综合检索
# ============================================================

def search_companies(
    keyword: str = '',
    province_id: int = None,
    city_id: int = None,
    district_id: int = None,
    center_lat: float = None,
    center_lng: float = None,
    radius_km: float = None,
    ics: str = '',
    ccs: str = '',
    standard_logic: str = 'OR',
    status: str = 'active',
):
    """
    多维度企业与标准级联检索（支持任意组合条件）

    支持：
      1. 行政区划级联 (Province -> City -> District)
      2. 经纬度 LBS 范围筛选 (lat, lng, radius_km) 并能与其他条件 AND 联动
      3. 企业名称/信用代码关键词匹配
      4. 企业标准 ICS / CCS 分类筛选 (支持 OR / AND 逻辑)
    """
    qs = Company.objects.filter(is_deleted=False)

    if status:
        qs = qs.filter(status=status)

    # 1. 行政区划筛选（三级级联 AND 逻辑）
    if district_id:
        qs = qs.filter(district_id=district_id)
    elif city_id:
        qs = qs.filter(city_id=city_id)
    elif province_id:
        qs = qs.filter(province_id=province_id)

    # 2. 关键词搜索（企业名称模糊匹配）
    if keyword:
        qs = qs.filter(
            Q(name__icontains=keyword) | Q(credit_code__icontains=keyword)
        )

    # 3. 标准分类 ICS/CCS 筛选 (支持 AND / OR 逻辑)
    if ics or ccs:
        from standards.models import Standard
        
        if standard_logic == 'AND' and ics and ccs:
            # 必须同时具备符合 ICS 的标准以及符合 CCS 的标准
            matching_ics = Standard.objects.filter(ics__icontains=ics).values_list('company_id', flat=True)
            matching_ccs = Standard.objects.filter(ccs__icontains=ccs).values_list('company_id', flat=True)
            matching_companies = set(matching_ics) & set(matching_ccs)
            qs = qs.filter(id__in=matching_companies)
        else:
            # OR 逻辑或单项查询
            std_q = Q()
            if ics and ccs:
                std_q = Q(ics__icontains=ics) | Q(ccs__icontains=ccs)
            elif ics:
                std_q = Q(ics__icontains=ics)
            elif ccs:
                std_q = Q(ccs__icontains=ccs)
            
            matching_companies = Standard.objects.filter(std_q).values_list('company_id', flat=True)
            qs = qs.filter(id__in=matching_companies)

    # 4. LBS 范围筛选 (支持与其他条件 AND 级联联动)
    if center_lat is not None and center_lng is not None and radius_km:
        from django.db.models.expressions import RawSQL
        from django.db.models import FloatField

        radius_meters = radius_km * 1000
        distance_expr = RawSQL(
            "ST_Distance_Sphere(POINT(%s, %s), POINT(longitude, latitude))",
            (center_lng, center_lat),
            output_field=FloatField()
        )
        qs = (
            qs.exclude(latitude__isnull=True)
            .exclude(longitude__isnull=True)
            .annotate(distance_meters=distance_expr)
            .filter(distance_meters__lte=radius_meters)
            .order_by('distance_meters')
        )

    # 5. 统计企业名下的企标与团标数量（防 N+1 查询高性能设计）
    from django.db.models import Count
    qs = qs.annotate(
        standards_count=Count(
            'standards',
            filter=Q(standards__type__in=['enterprise', 'group'])
        )
    )

    return qs.select_related('province', 'city', 'district')


# ============================================================
# Excel 批量导入
# ============================================================

IMPORT_TEMPLATE_HEADERS = [
    '企业名称*', '统一社会信用代码*', '法人', '省份', '城市', '区县',
    '纬度', '经度', '联系方式', '详细地址'
]


def generate_import_template() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = '企业导入模板'
    header_fill = PatternFill(start_color='1F4E79', end_color='1F4E79', fill_type='solid')
    header_font = Font(color='FFFFFF', bold=True)
    header_align = Alignment(horizontal='center', vertical='center')
    for col, header in enumerate(IMPORT_TEMPLATE_HEADERS, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = header_align
        ws.column_dimensions[cell.column_letter].width = 20
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()

def import_companies_from_excel(file_obj) -> dict:
    """
    从 Excel 文件批量导入企业信息

    Args:
        file_obj: 上传的文件对象

    Returns:
        {
          'success': int,       # 成功导入数量
          'skipped': int,       # 跳过（已存在）数量
          'errors': list[str],  # 错误列表（行号 + 原因）
        }
    """
    result = {'success': 0, 'skipped': 0, 'errors': []}

    try:
        wb = openpyxl.load_workbook(file_obj)
        ws = wb.active
    except Exception as e:
        result['errors'].append(f'文件解析失败: {str(e)}')
        return result

    
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        result['errors'].append('文件为空')
        return result

    headers = [str(c).strip() if c else '' for c in rows[0]]
    col_map = {'name': -1, 'credit_code': -1, 'legal_person': -1, 'province': -1, 'city': -1, 'district': -1, 'region_full': -1, 'latitude': -1, 'longitude': -1, 'contact': -1, 'address': -1}

    for i, h in enumerate(headers):
        if h in ['企业名称*', '企业名称', '起草单位/企业名称']:
            col_map['name'] = i
        elif h in ['统一社会信用代码*', '统一社会信用代码']:
            col_map['credit_code'] = i
        elif h in ['法人', '法定代表人']:
            col_map['legal_person'] = i
        elif h in ['省份']:
            col_map['province'] = i
        elif h in ['城市']:
            col_map['city'] = i
        elif h in ['区县']:
            col_map['district'] = i
        elif h in ['行政区划']:
            col_map['region_full'] = i
        elif h in ['纬度']:
            col_map['latitude'] = i
        elif h in ['经度']:
            col_map['longitude'] = i
        elif h in ['联系方式']:
            col_map['contact'] = i
        elif h in ['详细地址', '注册地址']:
            col_map['address'] = i

    # Fallback to default indices if no headers matched at all (assume template format but without header row, or just rely on col_map)
    if all(v == -1 for v in col_map.values()):
        col_map = {'name': 0, 'credit_code': 1, 'legal_person': 2, 'province': 3, 'city': 4, 'district': 5, 'latitude': 6, 'longitude': 7, 'contact': 8, 'address': 9, 'region_full': -1}

    data_rows = rows[1:]

    for row_idx, row in enumerate(data_rows, start=2):
        if not any(row):  # 跳过空行
            continue

        try:
            def get_val(key):
                idx = col_map.get(key, -1)
                if idx != -1 and idx < len(row):
                    val = row[idx]
                    return str(val).strip() if val else ''
                return ''

            name = get_val('name')
            credit_code = get_val('credit_code')

            if not name:
                result['errors'].append(f'第{row_idx}行: 企业名称不能为空')
                continue
            if not credit_code:
                result['errors'].append(f'第{row_idx}行: 统一社会信用代码不能为空')
                continue

            if Company.objects.filter(credit_code=credit_code).exists():
                result['skipped'] += 1
                continue

            province = city = district = None
            
            # Handle region_full first
            region_full = get_val('region_full')
            if region_full and region_full != 'nan' and '-' in region_full:
                geo_parts = region_full.split('-')
                if len(geo_parts) >= 1:
                    province = Province.objects.filter(name__icontains=geo_parts[0].replace('省', '')).first()
                if len(geo_parts) == 2 and province:
                    city = City.objects.filter(name__in=['市辖区', province.name.replace('市', '')], province=province).first()
                    if not city:
                        city = City.objects.filter(province=province).first()
                    if city:
                        district = District.objects.filter(name__icontains=geo_parts[1], city=city).first()
                else:
                    if len(geo_parts) >= 2 and province:
                        city = City.objects.filter(name__icontains=geo_parts[1].replace('市', ''), province=province).first()
                    if len(geo_parts) >= 3 and city:
                        district = District.objects.filter(name__icontains=geo_parts[2], city=city).first()
            
            # If region_full didn\'t yield results or wasn\'t present, try individual columns
            if not province:
                province_name = get_val('province')
                if province_name:
                    province = Province.objects.filter(name__icontains=province_name).first()
            if not city and province:
                city_name = get_val('city')
                if city_name:
                    city = City.objects.filter(name__icontains=city_name, province=province).first()
            if not district and city:
                district_name = get_val('district')
                if district_name:
                    district = District.objects.filter(name__icontains=district_name, city=city).first()

            latitude = None
            longitude = None
            try:
                lat_str = get_val('latitude')
                if lat_str: latitude = float(lat_str)
                lng_str = get_val('longitude')
                if lng_str: longitude = float(lng_str)
            except (ValueError, TypeError):
                result['errors'].append(f'第{row_idx}行: 经纬度格式有误，已跳过坐标')
            
            # 如果Excel中没有提供经纬度，则根据大字典(省市区)自动填入中心点经纬度，实现零成本落位
            if latitude is None and longitude is None:
                if district and district.latitude and district.longitude:
                    latitude = district.latitude
                    longitude = district.longitude
                elif city and city.latitude and city.longitude:
                    latitude = city.latitude
                    longitude = city.longitude

            with transaction.atomic():
                Company.objects.create(
                    name=name,
                    credit_code=credit_code,
                    legal_person=get_val('legal_person'),
                    province=province,
                    city=city,
                    district=district,
                    latitude=latitude,
                    longitude=longitude,
                    contact=get_val('contact'),
                    address=get_val('address'),
                )
            result['success'] += 1

        except IntegrityError:
            result['skipped'] += 1
        except Exception as e:
            result['errors'].append(f'第{row_idx}行: {str(e)}')

    return result

    # 跳过表头行
    data_rows = rows[1:]

    for row_idx, row in enumerate(data_rows, start=2):
        if not any(row):  # 跳过空行
            continue

        try:
            name = str(row[0]).strip() if row[0] else ''
            credit_code = str(row[1]).strip() if row[1] else ''

            if not name:
                result['errors'].append(f'第{row_idx}行: 企业名称不能为空')
                continue
            if not credit_code:
                result['errors'].append(f'第{row_idx}行: 统一社会信用代码不能为空')
                continue

            # 查重：信用代码唯一
            if Company.objects.filter(credit_code=credit_code).exists():
                result['skipped'] += 1
                continue

            # 解析行政区划（通过名称查找，允许为空）
            province = city = district = None
            province_name = str(row[3]).strip() if len(row) > 3 and row[3] else ''
            city_name = str(row[4]).strip() if len(row) > 4 and row[4] else ''
            district_name = str(row[5]).strip() if len(row) > 5 and row[5] else ''

            if province_name:
                province = Province.objects.filter(name__icontains=province_name).first()
            if city_name and province:
                city = City.objects.filter(name__icontains=city_name, province=province).first()
            if district_name and city:
                district = District.objects.filter(name__icontains=district_name, city=city).first()

            # 解析经纬度
            latitude = None
            longitude = None
            try:
                if len(row) > 6 and row[6]:
                    latitude = float(row[6])
                if len(row) > 7 and row[7]:
                    longitude = float(row[7])
            except (ValueError, TypeError):
                result['errors'].append(f'第{row_idx}行: 经纬度格式有误，已跳过坐标')

            with transaction.atomic():
                Company.objects.create(
                    name=name,
                    credit_code=credit_code,
                    legal_person=str(row[2]).strip() if len(row) > 2 and row[2] else '',
                    province=province,
                    city=city,
                    district=district,
                    latitude=latitude,
                    longitude=longitude,
                    contact=str(row[8]).strip() if len(row) > 8 and row[8] else '',
                    address=str(row[9]).strip() if len(row) > 9 and row[9] else '',
                )
            result['success'] += 1

        except IntegrityError:
            result['skipped'] += 1
        except Exception as e:
            result['errors'].append(f'第{row_idx}行: {str(e)}')

    return result


def export_companies_to_excel(queryset) -> bytes:
    """
    将企业 QuerySet 导出为 Excel 二进制数据

    Returns:
        Excel 文件的 bytes 对象
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = '企业信息'

    # 表头样式
    header_fill = PatternFill(start_color='1F4E79', end_color='1F4E79', fill_type='solid')
    header_font = Font(color='FFFFFF', bold=True)
    header_align = Alignment(horizontal='center', vertical='center')

    headers = ['企业名称', '统一社会信用代码', '法人', '省份', '城市', '区县',
               '纬度', '经度', '联系方式', '详细地址', '状态', '入库时间']

    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = header_align

    # 数据行
    for row_idx, company in enumerate(queryset, 2):
        ws.cell(row=row_idx, column=1, value=company.name)
        ws.cell(row=row_idx, column=2, value=company.credit_code)
        ws.cell(row=row_idx, column=3, value=company.legal_person)
        ws.cell(row=row_idx, column=4, value=company.province.name if company.province else '')
        ws.cell(row=row_idx, column=5, value=company.city.name if company.city else '')
        ws.cell(row=row_idx, column=6, value=company.district.name if company.district else '')
        ws.cell(row=row_idx, column=7, value=float(company.latitude) if company.latitude else '')
        ws.cell(row=row_idx, column=8, value=float(company.longitude) if company.longitude else '')
        ws.cell(row=row_idx, column=9, value=company.contact)
        ws.cell(row=row_idx, column=10, value=company.address)
        ws.cell(row=row_idx, column=11, value=company.get_status_display())
        ws.cell(row=row_idx, column=12, value=company.created_at.strftime('%Y-%m-%d'))

    # 自动列宽
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 40)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


def export_companies_to_excel_advanced(queryset, fields=None, include_standards=False) -> bytes:
    """
    高级企业导出服务，支持前端传递列名数组动态选择列，并支持带出企业关联的所有标准目录。
    """
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    import io

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "企业高级定制导出"

    # 表头样式
    header_fill = PatternFill(start_color='1F4E79', end_color='1F4E79', fill_type='solid')
    header_font = Font(color='FFFFFF', bold=True)
    header_align = Alignment(horizontal='center', vertical='center', wrap_text=True)

    # 完整字段到导出列与数据的映射表
    FIELD_MAPPING = {
        'name': ('企业名称', lambda c: c.name),
        'credit_code': ('统一社会信用代码', lambda c: c.credit_code),
        'legal_person': ('法人', lambda c: c.legal_person),
        'province': ('省份', lambda c: c.province.name if c.province else ''),
        'city': ('城市', lambda c: c.city.name if c.city else ''),
        'district': ('区县', lambda c: c.district.name if c.district else ''),
        'latitude': ('纬度', lambda c: float(c.latitude) if c.latitude else ''),
        'longitude': ('经度', lambda c: float(c.longitude) if c.longitude else ''),
        'contact': ('联系方式', lambda c: c.contact),
        'address': ('详细地址', lambda c: c.address),
        'status': ('状态', lambda c: c.get_status_display()),
        'created_at': ('入库时间', lambda c: c.created_at.strftime('%Y-%m-%d') if c.created_at else ''),
        # 16 个新增字段
        'established_date': ('成立日期', lambda c: c.established_date.strftime('%Y-%m-%d') if c.established_date else ''),
        'registered_address': ('注册地址', lambda c: c.registered_address),
        'registered_zipcode': ('注册地址邮编', lambda c: c.registered_zipcode),
        'valid_mobile': ('有效手机号', lambda c: c.valid_mobile),
        'more_phones': ('更多电话', lambda c: c.more_phones),
        'email': ('邮箱', lambda c: c.email),
        'company_type': ('企业(机构)类型', lambda c: c.company_type),
        'registration_no': ('注册号', lambda c: c.registration_no),
        'organization_code': ('组织机构代码', lambda c: c.organization_code),
        'industry_category': ('国标行业门类', lambda c: c.industry_category),
        'industry_major': ('国标行业大类', lambda c: c.industry_major),
        'industry_middle': ('国标行业中类', lambda c: c.industry_middle),
        'industry_minor': ('国标行业小类', lambda c: c.industry_minor),
        'company_size': ('企业规模', lambda c: c.company_size),
        'english_name': ('英文名', lambda c: c.english_name),
        'former_names': ('曾用名', lambda c: c.former_names),
    }

    # 默认导出所有字段
    if not fields or len(fields) == 0:
        fields = list(FIELD_MAPPING.keys())

    # 筛选匹配的字段
    headers = []
    active_fields = []
    for f in fields:
        if f in FIELD_MAPPING:
            headers.append(FIELD_MAPPING[f][0])
            active_fields.append(f)

    # 追加关联标准目录表头
    if include_standards:
        headers.append('关联标准目录')

    # 写入表头
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = header_align

    # 级联预加载关联的标准，优化 N+1 问题
    if include_standards:
        queryset = queryset.prefetch_related('standards')

    # 写入数据行
    for row_idx, company in enumerate(queryset, 2):
        for col_idx, field_code in enumerate(active_fields, 1):
            val = FIELD_MAPPING[field_code][1](company)
            ws.cell(row=row_idx, column=col_idx, value=val)

        if include_standards:
            # 获取所有关联标准目录列表并拼接
            standards = company.standards.all()
            standards_text = ""
            if standards.exists():
                standards_text = "\n".join([
                    f"{s.standard_no} 《{s.title or '未命名'}》 [{s.get_type_display()}]"
                    for s in standards
                ])
            cell = ws.cell(row=row_idx, column=len(headers), value=standards_text)
            cell.alignment = Alignment(wrap_text=True, vertical='top')

    # 自动列宽（对多行换行的标准目录只取最宽的单行线，防止列宽过宽影响观感）
    for col in ws.columns:
        max_len = 0
        for cell in col:
            val_str = str(cell.value or '')
            lines = val_str.split('\n')
            for line in lines:
                # 兼容中文字符宽度计算
                # 简单估算：一个中文字符宽度相当于1.7个西文字符
                import unicodedata
                line_len = 0
                for char in line:
                    if unicodedata.east_asian_width(char) in ('F', 'W', 'A'):
                        line_len += 2
                    else:
                        line_len += 1
                max_len = max(max_len, line_len)
        ws.column_dimensions[col[0].column_letter].width = min(max(max_len + 4, 12), 60)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


def export_leads_to_excel_advanced(queryset, fields=None) -> bytes:
    """
    高级线索导出服务，支持前端传递列名数组动态选择列。
    """
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    import io

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "线索数据导出"

    # 表头样式
    header_fill = PatternFill(start_color='1F4E79', end_color='1F4E79', fill_type='solid')
    header_font = Font(color='FFFFFF', bold=True)
    header_align = Alignment(horizontal='center', vertical='center', wrap_text=True)

    # 完整字段到导出列与数据的映射表
    FIELD_MAPPING = {
        'source': ('来源', lambda c: c.get_source_display()),
        'req_type': ('诉求类型', lambda c: c.get_req_type_display()),
        'status': ('跟进状态', lambda c: c.get_status_display()),
        'assignee': ('负责人', lambda c: c.assignee.username if c.assignee else ''),
        'enterprise': ('关联企业', lambda c: c.enterprise.name if c.enterprise else ''),
        'contact_name': ('联系人姓名', lambda c: c.contact_name),
        'contact_phone': ('联系电话', lambda c: c.contact_phone),
        'contact_wechat': ('联系微信', lambda c: c.contact_wechat),
        'created_at': ('建立时间', lambda c: c.created_at.strftime('%Y-%m-%d %H:%M') if c.created_at else ''),
        'updated_at': ('更新时间', lambda c: c.updated_at.strftime('%Y-%m-%d %H:%M') if c.updated_at else ''),
    }

    # 默认导出所有字段
    if not fields or len(fields) == 0:
        fields = list(FIELD_MAPPING.keys())

    # 筛选匹配 of target fields
    headers = []
    active_fields = []
    for f in fields:
        if f in FIELD_MAPPING:
            headers.append(FIELD_MAPPING[f][0])
            active_fields.append(f)

    # 写入表头
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = header_align

    # 写入数据行
    for row_idx, lead in enumerate(queryset, 2):
        for col_idx, field_code in enumerate(active_fields, 1):
            val = FIELD_MAPPING[field_code][1](lead)
            ws.cell(row=row_idx, column=col_idx, value=val)

    # 自动列宽
    for col in ws.columns:
        max_len = 0
        for cell in col:
            val_str = str(cell.value or '')
            lines = val_str.split('\n')
            for line in lines:
                import unicodedata
                line_len = 0
                for char in line:
                    if unicodedata.east_asian_width(char) in ('F', 'W', 'A'):
                        line_len += 2
                    else:
                        line_len += 1
                max_len = max(max_len, line_len)
        ws.column_dimensions[col[0].column_letter].width = min(max(max_len + 4, 12), 60)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()

