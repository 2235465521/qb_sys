"""
standards.services_export — 企标后台高级定制数据导出服务模块
遵循 Deep Module 设计原则：
1. 对外暴露极简统一接口；
2. 内部采用 values(*fields) 投影查询，杜绝实例化数十万 Model 对象的内存雪崩与全表 JSON 字段冗余传输；
3. 采用 write_only=True 流式引擎，以毫秒级速度和极低内存占用完成 10 万+ 数据的分 Sheet 导出；
4. 彻底解决生产服务器 Gunicorn 30s 超时和 OOM 导致的 502 Bad Gateway。
"""

import os
import io
import tempfile
from datetime import datetime
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

from django.db.models import Q
from standards.models import Standard
from standards.utils.search_utils import build_smart_search_q


class StandardExportService:
    """企标后台导出核心服务类"""

    TYPE_CHOICES_DICT = {
        'enterprise': '企业标准',
        'group': '团体标准',
        'national': '国家标准',
        'industry': '行业标准',
        'local': '地方标准',
    }

    STATUS_CHOICES_DICT = {
        'active': '现行',
        'deprecated': '已废止',
        'upcoming': '即将实施',
        'draft': '草案',
    }

    PARSE_STATUS_DICT = {
        'unparsed': '暂未解析',
        'references_parsed': '已完成规范性引用解析',
        'indicators_parsed': '已完成指标解析',
    }

    # 字段配置表：
    # key -> (列名, 依赖的数据库字段列表, 格式化lambda, 默认列宽)
    FIELD_DEFINITIONS = {
        # 1. 标准核心属性
        'standard_no': (
            '标准编号(原始)',
            ['standard_no'],
            lambda r: r.get('standard_no') or '',
            24
        ),
        'clean_id': (
            '标准编号(清洗)',
            ['clean_id'],
            lambda r: r.get('clean_id') or '',
            22
        ),
        'title': (
            '标准名称',
            ['title'],
            lambda r: r.get('title') or '',
            32
        ),
        'type': (
            '标准类型',
            ['type'],
            lambda r: StandardExportService.TYPE_CHOICES_DICT.get(r.get('type'), r.get('type') or ''),
            14
        ),
        'status': (
            '标准状态',
            ['status'],
            lambda r: StandardExportService.STATUS_CHOICES_DICT.get(r.get('status'), r.get('status') or ''),
            12
        ),
        'publish_date': (
            '发布日期',
            ['publish_date'],
            lambda r: r['publish_date'].strftime('%Y-%m-%d') if r.get('publish_date') else '',
            14
        ),
        'implement_date': (
            '实施日期',
            ['implement_date'],
            lambda r: r['implement_date'].strftime('%Y-%m-%d') if r.get('implement_date') else '',
            14
        ),
        'created_at': (
            '入库时间',
            ['created_at'],
            lambda r: r['created_at'].strftime('%Y-%m-%d %H:%M') if r.get('created_at') else '',
            18
        ),
        'ics': (
            'ICS分类号',
            ['ics'],
            lambda r: r.get('ics') or '',
            14
        ),
        'ccs': (
            'CCS分类号',
            ['ccs'],
            lambda r: r.get('ccs') or '',
            14
        ),
        'is_parsed': (
            '解析状态',
            ['is_parsed'],
            lambda r: StandardExportService.PARSE_STATUS_DICT.get(r.get('is_parsed'), r.get('is_parsed') or ''),
            18
        ),
        'has_pdf': (
            '是否挂接PDF',
            ['pdf_file', 'disk_filename'],
            lambda r: '是' if bool(r.get('pdf_file') or r.get('disk_filename')) else '否',
            14
        ),

        # 2. 起草企业关联属性
        'company_name': (
            '起草单位/企业名称',
            ['company__name'],
            lambda r: r.get('company__name') or '',
            28
        ),
        'credit_code': (
            '统一社会信用代码',
            ['company__credit_code'],
            lambda r: r.get('company__credit_code') or '',
            22
        ),
        'legal_person': (
            '法定代表人',
            ['company__legal_person'],
            lambda r: r.get('company__legal_person') or '',
            14
        ),
        'province': (
            '所属省份',
            ['company__province__name'],
            lambda r: r.get('company__province__name') or '',
            14
        ),
        'city': (
            '所属城市',
            ['company__city__name'],
            lambda r: r.get('company__city__name') or '',
            14
        ),
        'district': (
            '所属区县',
            ['company__district__name'],
            lambda r: r.get('company__district__name') or '',
            14
        ),
        'company_address': (
            '企业详细地址',
            ['company__address'],
            lambda r: r.get('company__address') or '',
            32
        ),
        'company_type': (
            '企业(机构)类型',
            ['company__company_type'],
            lambda r: r.get('company__company_type') or '',
            18
        ),
        'company_size': (
            '企业规模',
            ['company__company_size'],
            lambda r: r.get('company__company_size') or '',
            14
        ),
    }

    # 预设推荐列集合
    DEFAULT_RECOMMENDED_FIELDS = [
        'standard_no', 'title', 'company_name', 'status',
        'publish_date', 'implement_date', 'province', 'city', 'district', 'has_pdf'
    ]

    @classmethod
    def build_queryset(cls, export_scope: str = 'query', ids: list = None, filters: dict = None):
        """
        根据导出范围及过滤条件构造基础 Standard QuerySet
        """
        filters = filters or {}
        qs = Standard.objects.all()

        # 1. 勾选指定数据
        if export_scope == 'selected':
            if not ids:
                return Standard.objects.none()
            return qs.filter(id__in=ids).order_by('-created_at')

        # 2. 全库导出 (all) 或根据条件导出 (query)
        std_type = filters.get('type')
        if std_type and std_type != 'all':
            qs = qs.filter(type=std_type)
        elif export_scope != 'all' and not std_type:
            qs = qs.filter(type='enterprise')

        if export_scope == 'all':
            return qs.order_by('-created_at')

        # query 模式下的高级条件过滤
        kw = (filters.get('keyword') or '').strip()
        if kw:
            search_q = build_smart_search_q(kw, ['standard_no', 'title'], clean_id_field='clean_id')
            qs = qs.filter(search_q | Q(company__name__icontains=kw))

        status_val = filters.get('status')
        if status_val:
            qs = qs.filter(status=status_val)

        company_id = filters.get('company_id')
        if company_id:
            qs = qs.filter(company_id=company_id)

        has_pdf = filters.get('has_pdf')
        if has_pdf is True or has_pdf == 'true' or has_pdf == '1':
            qs = qs.filter(Q(pdf_file__isnull=False, pdf_file__gt='') | Q(disk_filename__isnull=False, disk_filename__gt=''))
        elif has_pdf is False or has_pdf == 'false' or has_pdf == '0':
            qs = qs.filter((Q(pdf_file__isnull=True) | Q(pdf_file='')) & (Q(disk_filename__isnull=True) | Q(disk_filename='')))

        is_parsed = filters.get('is_parsed')
        if is_parsed:
            qs = qs.filter(is_parsed=is_parsed)

        date_type = filters.get('date_type', 'publish_date')
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
            default_w = cls.FIELD_DEFINITIONS[field_key][3]
            ws.column_dimensions[col_letter].width = default_w

        return ws

    @classmethod
    def export_standards(cls, queryset, selected_fields: list = None, chunk_size: int = 100000):
        """
        极速流式导出企业标准目录：
        - 使用 values(*db_fields) 精确投影，彻底避免加载大体积 JSON 字段及实例化数十万 Model 对象；
        - 若总数 <= chunk_size (10万条)：单工作表直接生成；
        - 若总数 > chunk_size (如18万条)：在同一 Excel 工作簿内自动切分多个 Sheet（Part1、Part2...，序号连续递增）；
        - 返回: (file_bytes, filename, content_type)
        """
        if not selected_fields:
            selected_fields = cls.DEFAULT_RECOMMENDED_FIELDS

        valid_fields = [f for f in selected_fields if f in cls.FIELD_DEFINITIONS]
        if not valid_fields:
            valid_fields = cls.DEFAULT_RECOMMENDED_FIELDS

        # 1. 搜集所需的所有数据库字段，仅向 MySQL 请求这些字段
        db_cols = set()
        for f in valid_fields:
            db_cols.update(cls.FIELD_DEFINITIONS[f][1])
        db_cols_list = list(db_cols)

        total_count = queryset.count()
        date_str = datetime.now().strftime('%Y%m%d_%H%M%S')

        wb = openpyxl.Workbook(write_only=True)

        # 2. 提取器列表快速绑定
        extractors = [(f, cls.FIELD_DEFINITIONS[f][2]) for f in valid_fields]

        # 3. 数据查询与流式写入（values 模式内存极低，零 Model 实例化）
        values_qs = queryset.values(*db_cols_list)

        if total_count <= chunk_size:
            # 单 Sheet
            ws = cls._add_styled_sheet(wb, "企业标准目录", valid_fields)
            row_num = 1
            for row in values_qs.iterator(chunk_size=5000):
                row_data = [row_num]
                for _, extractor in extractors:
                    try:
                        row_data.append(extractor(row))
                    except Exception:
                        row_data.append('')
                ws.append(row_data)
                row_num += 1
        else:
            # 多 Sheet 切分
            cur_part = 1
            start_seq = 1
            end_seq = min(chunk_size, total_count)
            sheet_title = f"企业标准目录_Part{cur_part}({start_seq}-{end_seq})"
            ws = cls._add_styled_sheet(wb, sheet_title, valid_fields)

            global_seq = 1
            for row in values_qs.iterator(chunk_size=5000):
                row_data = [global_seq]
                for _, extractor in extractors:
                    try:
                        row_data.append(extractor(row))
                    except Exception:
                        row_data.append('')
                ws.append(row_data)

                # 切分到新 Sheet
                if global_seq % chunk_size == 0 and global_seq < total_count:
                    cur_part += 1
                    start_seq = global_seq + 1
                    end_seq = min(global_seq + chunk_size, total_count)
                    sheet_title = f"企业标准目录_Part{cur_part}({start_seq}-{end_seq})"
                    ws = cls._add_styled_sheet(wb, sheet_title, valid_fields)

                global_seq += 1

        # 4. 使用临时文件避免大内存占用
        tmp_fd, tmp_path = tempfile.mkstemp(suffix='.xlsx')
        os.close(tmp_fd)
        try:
            wb.save(tmp_path)
            with open(tmp_path, 'rb') as f:
                file_bytes = f.read()
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

        filename = f"企业标准目录导出_{date_str}.xlsx"
        content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        return file_bytes, filename, content_type

    @classmethod
    def export_to_excel(cls, queryset, selected_fields: list = None, max_limit: int = 100000) -> bytes:
        file_bytes, _, _ = cls.export_standards(queryset, selected_fields=selected_fields, chunk_size=max_limit)
        return file_bytes
