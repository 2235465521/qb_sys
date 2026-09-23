"""
standards.services_export — 企标后台高级定制数据导出服务模块
遵循 Deep Module 设计原则：对外暴露极简接口，内部封装过滤、级联预加载及 Excel 样式渲染。
"""

import io
from datetime import datetime
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from django.db.models import Q
from standards.models import Standard
from standards.utils.search_utils import build_smart_search_q


class StandardExportService:
    """企标后台导出核心服务类"""

    # 完整字段映射表：key -> (导出列名, 提取函数, 推荐默认列宽)
    FIELD_DEFINITIONS = {
        # 1. 标准核心属性
        'standard_no': ('标准编号(原始)', lambda s: s.standard_no or '', 24),
        'clean_id': ('标准编号(清洗)', lambda s: s.clean_id or '', 22),
        'title': ('标准名称', lambda s: s.title or '', 32),
        'type': ('标准类型', lambda s: s.get_type_display() if hasattr(s, 'get_type_display') else s.type or '', 14),
        'status': ('标准状态', lambda s: s.get_status_display() if hasattr(s, 'get_status_display') else s.status or '', 12),
        'publish_date': ('发布日期', lambda s: s.publish_date.strftime('%Y-%m-%d') if s.publish_date else '', 14),
        'implement_date': ('实施日期', lambda s: s.implement_date.strftime('%Y-%m-%d') if s.implement_date else '', 14),
        'created_at': ('入库时间', lambda s: s.created_at.strftime('%Y-%m-%d %H:%M') if s.created_at else '', 18),
        'ics': ('ICS分类号', lambda s: s.ics or '', 14),
        'ccs': ('CCS分类号', lambda s: s.ccs or '', 14),
        'is_parsed': ('解析状态', lambda s: s.get_is_parsed_display() if hasattr(s, 'get_is_parsed_display') else s.is_parsed or '', 18),
        'has_pdf': ('是否挂接PDF', lambda s: '是' if bool(s.pdf_file or s.disk_filename) else '否', 14),

        # 2. 起草企业关联属性
        'company_name': ('起草单位/企业名称', lambda s: s.company.name if s.company else '', 28),
        'credit_code': ('统一社会信用代码', lambda s: s.company.credit_code if s.company else '', 22),
        'legal_person': ('法定代表人', lambda s: s.company.legal_person if s.company else '', 14),
        'province': ('所属省份', lambda s: s.company.province.name if (s.company and s.company.province) else '', 14),
        'city': ('所属城市', lambda s: s.company.city.name if (s.company and s.company.city) else '', 14),
        'district': ('所属区县', lambda s: s.company.district.name if (s.company and s.company.district) else '', 14),
        'company_address': ('企业详细地址', lambda s: s.company.address if s.company else '', 32),
        'company_type': ('企业(机构)类型', lambda s: s.company.company_type if s.company else '', 18),
        'company_size': ('企业规模', lambda s: s.company.company_size if s.company else '', 14),
    }

    # 预设推荐列集合
    DEFAULT_RECOMMENDED_FIELDS = [
        'standard_no', 'title', 'company_name', 'status',
        'publish_date', 'implement_date', 'province', 'city', 'district', 'has_pdf'
    ]

    @classmethod
    def build_queryset(cls, export_scope: str = 'query', ids: list = None, filters: dict = None):
        """
        根据导出范围及过滤条件构造高优化的 Standard QuerySet
        """
        filters = filters or {}
        qs = Standard.objects.all().select_related(
            'company',
            'company__province',
            'company__city',
            'company__district'
        )

        # 1. 勾选指定数据
        if export_scope == 'selected':
            if not ids:
                return Standard.objects.none()
            return qs.filter(id__in=ids).order_by('-created_at')

        # 2. 全库导出 (all) 或根据条件导出 (query)
        # 标准类型（默认为 enterprise 企标，支持 all）
        std_type = filters.get('type')
        if std_type and std_type != 'all':
            qs = qs.filter(type=std_type)
        elif export_scope != 'all' and not std_type:
            # 默认后台以企业标准为主
            qs = qs.filter(type='enterprise')

        if export_scope == 'all':
            # 全部导出模式，仅受类型控制或基础过滤
            return qs.order_by('-created_at')

        # query 模式下的高级条件过滤
        # 关键词检索 (标准编号、标准名称、或者所属企业)
        kw = (filters.get('keyword') or '').strip()
        if kw:
            search_q = build_smart_search_q(kw, ['standard_no', 'title'], clean_id_field='clean_id')
            # 同时支持搜索企业名称
            qs = qs.filter(search_q | Q(company__name__icontains=kw))

        # 标准状态
        status_val = filters.get('status')
        if status_val:
            qs = qs.filter(status=status_val)

        # 关联企业 ID
        company_id = filters.get('company_id')
        if company_id:
            qs = qs.filter(company_id=company_id)

        # 是否已挂接 PDF 文件
        has_pdf = filters.get('has_pdf')
        if has_pdf is True or has_pdf == 'true' or has_pdf == '1':
            qs = qs.filter(Q(pdf_file__isnull=False, pdf_file__gt='') | Q(disk_filename__isnull=False, disk_filename__gt=''))
        elif has_pdf is False or has_pdf == 'false' or has_pdf == '0':
            qs = qs.filter((Q(pdf_file__isnull=True) | Q(pdf_file='')) & (Q(disk_filename__isnull=True) | Q(disk_filename='')))

        # 解析状态
        is_parsed = filters.get('is_parsed')
        if is_parsed:
            qs = qs.filter(is_parsed=is_parsed)

        # 日期范围过滤 (发布日期或实施日期)
        date_type = filters.get('date_type', 'publish_date')  # 'publish_date' | 'implement_date'
        start_date = filters.get('start_date')
        end_date = filters.get('end_date')

        date_field = 'publish_date' if date_type == 'publish_date' else 'implement_date'
        if start_date:
            try:
                s_dt = datetime.strptime(start_date.split('T')[0], '%Y-%m-%d').date()
                qs = qs.filter(**{f'{date_field}__gte': s_dt})
            except Exception:
                pass
        if end_date:
            try:
                e_dt = datetime.strptime(end_date.split('T')[0], '%Y-%m-%d').date()
                qs = qs.filter(**{f'{date_field}__lte': e_dt})
            except Exception:
                pass

        # 省市区筛选（若前端有传）
        prov_id = filters.get('province_id')
        if prov_id:
            qs = qs.filter(company__province_id=prov_id)
        city_id = filters.get('city_id')
        if city_id:
            qs = qs.filter(company__city_id=city_id)
        district_id = filters.get('district_id')
        if district_id:
            qs = qs.filter(company__district_id=district_id)

        return qs.order_by('-created_at')

    @classmethod
    def _add_styled_sheet(cls, wb, sheet_title, valid_fields):
        """在 write_only 工作簿中创建带有统一样式表头和自适应列宽的工作表"""
        from openpyxl.cell import WriteOnlyCell

        ws = wb.create_sheet(title=sheet_title[:31])

        header_fill = PatternFill(start_color='1F4E79', end_color='1F4E79', fill_type='solid')
        header_font = Font(name='微软雅黑', size=11, bold=True, color='FFFFFF')
        header_align = Alignment(horizontal='center', vertical='center', wrap_text=True)

        headers = ['序号'] + [cls.FIELD_DEFINITIONS[f][0] for f in valid_fields]
        header_cells = []
        for h_text in headers:
            cell = WriteOnlyCell(ws, value=h_text)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = header_align
            header_cells.append(cell)
        ws.append(header_cells)

        ws.column_dimensions['A'].width = 8
        for col_idx, field_key in enumerate(valid_fields, 2):
            col_letter = get_column_letter(col_idx)
            default_w = cls.FIELD_DEFINITIONS[field_key][2]
            ws.column_dimensions[col_letter].width = default_w

        return ws

    @classmethod
    def export_standards(cls, queryset, selected_fields: list = None, chunk_size: int = 100000):
        """
        导出企业标准目录：
        - 若总数 <= chunk_size (默认10万条)：生成单 Sheet 的 Excel 字节流；
        - 若总数 > chunk_size (例如18万条)：在同一个 Excel 内切分多个工作表 Sheet（每卷 10 万条，序号连续递增）；
        始终输出标准 .xlsx 格式，彻底避开非 HTTPS 站点下载 .zip 时触发的 Chrome 安全拦截。
        返回元组: (file_bytes, filename, content_type)
        """
        from datetime import datetime

        if not selected_fields:
            selected_fields = cls.DEFAULT_RECOMMENDED_FIELDS

        valid_fields = [f for f in selected_fields if f in cls.FIELD_DEFINITIONS]
        if not valid_fields:
            valid_fields = cls.DEFAULT_RECOMMENDED_FIELDS

        total_count = queryset.count()
        date_str = datetime.now().strftime('%Y%m%d_%H%M%S')

        wb = openpyxl.Workbook(write_only=True)

        # 情况 1: 数据量 <= chunk_size (10万条)
        if total_count <= chunk_size:
            ws = cls._add_styled_sheet(wb, "企业标准目录", valid_fields)
            row_num = 1
            for standard in queryset.iterator(chunk_size=2000):
                row_data = [row_num]
                for field_key in valid_fields:
                    extractor = cls.FIELD_DEFINITIONS[field_key][1]
                    try:
                        val = extractor(standard)
                    except Exception:
                        val = ''
                    row_data.append(val)
                ws.append(row_data)
                row_num += 1
        else:
            # 情况 2: 数据量 > chunk_size (如 18 万条)，在同一工作簿内切分多个 Sheet
            cur_part = 1
            start_seq = 1
            end_seq = min(chunk_size, total_count)
            sheet_title = f"企业标准目录_Part{cur_part}({start_seq}-{end_seq})"
            ws = cls._add_styled_sheet(wb, sheet_title, valid_fields)

            global_seq = 1
            for standard in queryset.iterator(chunk_size=2000):
                row_data = [global_seq]
                for field_key in valid_fields:
                    extractor = cls.FIELD_DEFINITIONS[field_key][1]
                    try:
                        val = extractor(standard)
                    except Exception:
                        val = ''
                    row_data.append(val)
                ws.append(row_data)

                # 达到本 Sheet 10 万条且后面还有数据，开启新 Sheet
                if global_seq % chunk_size == 0 and global_seq < total_count:
                    cur_part += 1
                    start_seq = global_seq + 1
                    end_seq = min(global_seq + chunk_size, total_count)
                    sheet_title = f"企业标准目录_Part{cur_part}({start_seq}-{end_seq})"
                    ws = cls._add_styled_sheet(wb, sheet_title, valid_fields)

                global_seq += 1

        output = io.BytesIO()
        wb.save(output)
        filename = f"企业标准目录导出_{date_str}.xlsx"
        content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        return output.getvalue(), filename, content_type

    # 兼容历史别名
    @classmethod
    def export_to_excel(cls, queryset, selected_fields: list = None, max_limit: int = 100000) -> bytes:
        data_bytes, _, _ = cls.export_standards(queryset, selected_fields=selected_fields, chunk_size=max_limit)
        return data_bytes
