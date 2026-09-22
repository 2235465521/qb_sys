"""
companies.services_association — 社会组织/行业协会名单批量查标与合并导出深度服务模块
遵守 Codebase Design 架构原则：
  - 极小接口表面积 (Small Interface)
  - 深度实现隐藏复杂跨库查询 (Deep Module)
  - 避免 N+1 数据库访问，一次性批处理
"""

import io
import re
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from django.db import connections
from django.utils import timezone
from companies.models import Company
from standards.models import Standard


class AssociationBatchService:
    """
    社团与协会批量查标与合并导出服务
    """

    @classmethod
    def parse_excel_association_names(cls, file_content: bytes) -> list:
        """
        智能解析上传的 Excel 文件，提取社团/协会名称列表。
        
        自动策略：
          1. 搜索表头含有 ['社团', '协会', '单位', '机构', '组织', '名称', '企业'] 的列
          2. 若未匹配到显著表头，根据首列是否为“序号”/数字判断：若是则提取第2列，否则提取第1列
          3. 自动去除空白行与首尾空格，按原始出现顺序去重
        """
        wb = openpyxl.load_workbook(io.BytesIO(file_content), data_only=True)
        sheet = wb.active
        if not sheet:
            return []

        rows = list(sheet.iter_rows(values_only=True))
        if not rows:
            return []

        # 查找表头
        target_col_idx = None
        start_row_idx = 0

        header_keywords = ['社团名称', '协会名称', '社团组织名称', '社会组织名称', '单位名称', '机构名称', '名称', '社团', '协会']
        
        # 扫描前 5 行寻找表头
        for r_idx in range(min(5, len(rows))):
            row = rows[r_idx]
            for c_idx, cell in enumerate(row):
                if cell and any(k in str(cell).strip() for k in header_keywords):
                    target_col_idx = c_idx
                    start_row_idx = r_idx + 1
                    break
            if target_col_idx is not None:
                break

        # 如果未找到表头关键词，进行启发式推断
        if target_col_idx is None:
            first_row = rows[0]
            first_val = str(first_row[0] or '').strip()
            # 如果第一列是 '序号' 或数字编号，且有第二列，则默认使用第二列
            if (first_val in ['序号', '编号', 'id', 'ID'] or first_val.isdigit()) and len(first_row) > 1:
                target_col_idx = 1
                start_row_idx = 1
            else:
                target_col_idx = 0
                start_row_idx = 1 if ('名' in first_val or '称' in first_val) else 0

        extracted_names = []
        seen = set()

        for r_idx in range(start_row_idx, len(rows)):
            row = rows[r_idx]
            if len(row) > target_col_idx:
                raw_val = row[target_col_idx]
                if raw_val is not None:
                    name_str = str(raw_val).strip()
                    # 过滤纯数字、无效标点、表头文字残留
                    if name_str and name_str not in ['社团名称', '协会名称', '序号', '单位名称'] and not name_str.isdigit():
                        if name_str not in seen:
                            seen.add(name_str)
                            extracted_names.append(name_str)

        return extracted_names

    @classmethod
    def batch_query_associations(cls, names: list) -> dict:
        """
        批量穿透检索所有输入的社会团体/行业协会的标准资产。
        
        执行流程（3 次批处理 SQL）：
          1. 批量检索 compare_conp.ent_std_maker 与 EMIS Company 表获取信用代码与法人工商信息；
          2. 批量检索 mydate.unit_dict 获取 stsc 关联的 unit_id；
          3. 批量联查 mydate.view_std_full 获取全部去重标准清单，并合并本地企标库；
          4. 内存聚合分组，生成各协会标准分类统计（团标/国标/地标/行标/企标）。
        """
        clean_names = []
        seen = set()
        for n in names:
            s = str(n or '').strip()
            if s and s not in seen:
                seen.add(s)
                clean_names.append(s)

        if not clean_names:
            return {
                'total_input': 0,
                'matched_count': 0,
                'total_standards_count': 0,
                'items': []
            }

        # ── 步骤 1：批量工商与主体对齐 ────────────────────────────
        ent_map = {}
        try:
            with connections['compare_conp'].cursor() as cur:
                placeholders = ', '.join(['%s'] * len(clean_names))
                cur.execute(f"""
                    SELECT 
                        company_name, 
                        unified_social_credit_code, 
                        legal_representative, 
                        province, 
                        city, 
                        district, 
                        enterprise_type
                    FROM ent_std_maker
                    WHERE company_name IN ({placeholders})
                """, clean_names)
                for r in cur.fetchall():
                    ent_map[r[0]] = {
                        'credit_code': r[1] or '',
                        'legal_person': r[2] or '-',
                        'province': r[3] or '',
                        'city': r[4] or '',
                        'district': r[5] or '',
                        'enterprise_type': r[6] or '社会团体'
                    }
        except Exception as e:
            pass

        # 结合本地 Company 表
        local_companies = Company.objects.filter(name__in=clean_names)
        local_company_map = {c.name: c for c in local_companies}
        for c_name, comp in local_company_map.items():
            if c_name not in ent_map:
                ent_map[c_name] = {
                    'credit_code': comp.credit_code or '',
                    'legal_person': comp.legal_person or '-',
                    'province': comp.province.name if comp.province else '',
                    'city': comp.city.name if comp.city else '',
                    'district': comp.district.name if comp.district else '',
                    'enterprise_type': '社会团体'
                }

        # ── 步骤 2：批量检索 stsc_db 的 unit_dict ──────────────
        unit_map = {}  # { unit_name: [unit_ids...] }
        uid_to_name = {}  # { unit_id: unit_name }

        try:
            with connections['stsc_db'].cursor() as cur:
                placeholders = ', '.join(['%s'] * len(clean_names))
                cur.execute(f"""
                    SELECT unit_id, unit_name, credit_code
                    FROM unit_dict
                    WHERE unit_name IN ({placeholders})
                """, clean_names)
                for uid, uname, ccode in cur.fetchall():
                    unit_map.setdefault(uname, []).append(uid)
                    uid_to_name[uid] = uname
                    if ccode and uname in ent_map and not ent_map[uname].get('credit_code'):
                        ent_map[uname]['credit_code'] = ccode
                    elif ccode and uname not in ent_map:
                        ent_map[uname] = {
                            'credit_code': ccode,
                            'legal_person': '-',
                            'province': '-',
                            'city': '-',
                            'district': '-',
                            'enterprise_type': '社会团体'
                        }
        except Exception as e:
            pass

        all_uids = list(uid_to_name.keys())

        # ── 步骤 3：批量检索联邦标准 ──────────────────────────────
        fed_standards_by_unit = {}  # { unit_name: [std_dicts...] }

        if all_uids:
            try:
                with connections['stsc_db'].cursor() as cur:
                    uid_placeholders = ', '.join(['%s'] * len(all_uids))
                    cur.execute(f"""
                        SELECT 
                            u.unit_name,
                            v.std_id, 
                            v.std_chinesename, 
                            v.std_type, 
                            v.release_date, 
                            v.implement_date, 
                            v.ex_state as status, 
                            h.draft_unit as drafter,
                            r.rank_order
                        FROM unit_dict u
                        JOIN std_unit_relation r ON u.unit_id = r.unit_id
                        JOIN view_std_full v ON r.base_id = v.id
                        LEFT JOIN std_extend_h h ON v.id = h.base_id
                        WHERE u.unit_id IN ({uid_placeholders})
                        ORDER BY v.release_date DESC
                    """, all_uids)
                    for row in cur.fetchall():
                        uname, sid, stitle, stype, rdate, idate, status_val, drafter, rank = row
                        fed_standards_by_unit.setdefault(uname, []).append({
                            'standard_no': sid or '',
                            'title': stitle or '无标题',
                            'type_raw': stype or '',
                            'release_date': str(rdate) if rdate else '-',
                            'implement_date': str(idate) if idate else '-',
                            'status_raw': status_val,
                            'drafter': drafter or '',
                            'rank': rank
                        })
            except Exception as e:
                pass

        # ── 步骤 4：本地企标检索 ──────────────────────────────────
        local_stds_by_company = {}
        if local_companies:
            local_stds = Standard.objects.filter(company__in=local_companies)
            for ls in local_stds:
                c_name = ls.company.name
                local_stds_by_company.setdefault(c_name, []).append({
                    'standard_no': ls.standard_no or '',
                    'title': ls.title or '无标题',
                    'type_raw': 'enterprise',
                    'release_date': ls.publish_date.strftime('%Y-%m-%d') if ls.publish_date else '-',
                    'implement_date': ls.implement_date.strftime('%Y-%m-%d') if ls.implement_date else '-',
                    'status_raw': 1 if ls.status == 'active' else 0,
                    'drafter': '主起草单位',
                    'rank': 1,
                    'is_local': True
                })

        # ── 步骤 5：汇总聚合每个协会的标准资产 ────────────────────
        status_map = {0: '废止', 1: '现行', 2: '即将实施'}

        result_items = []
        grand_total_standards = 0
        matched_associations = 0

        for idx, name in enumerate(clean_names, 1):
            ent = ent_map.get(name, {})
            uids = unit_map.get(name, [])
            fed_list = fed_standards_by_unit.get(name, [])
            loc_list = local_stds_by_company.get(name, [])

            is_matched = bool(ent.get('credit_code') or uids or loc_list)
            if is_matched:
                matched_associations += 1

            # 去重标准列表（按标准号大写去重）
            seen_std_nos = set()
            unified_standards = []

            # 优先加入本地企标
            for ls in loc_list:
                s_no = (ls['standard_no'] or '').strip().upper()
                if s_no and s_no not in seen_std_nos:
                    seen_std_nos.add(s_no)
                    unified_standards.append({
                        'standard_no': ls['standard_no'],
                        'title': ls['title'],
                        'type_display': '企业标准',
                        'drafter_display': ls['drafter'],
                        'status': '现行' if ls['status_raw'] == 1 else '废止',
                        'release_date': ls['release_date'],
                        'implement_date': ls['implement_date'],
                        'is_local': True
                    })

            # 加入联邦库标准
            for fs in fed_list:
                s_no = (fs['standard_no'] or '').strip().upper()
                if not s_no or s_no in seen_std_nos:
                    continue
                seen_std_nos.add(s_no)

                # 推导标准类别
                t_raw = (fs['type_raw'] or '').upper()
                if s_no.startswith('GB') or 'GB' in t_raw or '国标' in t_raw:
                    t_disp = '国家标准'
                elif (s_no.startswith('TB') or s_no.startswith('T/') or s_no.startswith('T ') or
                      '团标' in t_raw or '团体' in t_raw):
                    t_disp = '团体标准'
                elif s_no.startswith('DB') or '地标' in t_raw or '地方' in t_raw:
                    t_disp = '地方标准'
                else:
                    t_disp = '行业标准'

                # 推导起草身份
                rank = fs.get('rank')
                drafter_text = fs.get('drafter')
                if rank:
                    rank_disp = f"第{rank}名"
                elif drafter_text:
                    parts = drafter_text.replace(';', ',').replace('，', ',').split(',')
                    rank_disp = " / ".join([p.strip() for p in parts[:2] if p.strip()])
                else:
                    rank_disp = '-'

                unified_standards.append({
                    'standard_no': fs['standard_no'],
                    'title': fs['title'],
                    'type_display': t_disp,
                    'drafter_display': rank_disp,
                    'status': status_map.get(fs['status_raw'], '现行'),
                    'release_date': fs['release_date'],
                    'implement_date': fs['implement_date'],
                    'is_local': False
                })

            # 各分类统计
            group_count = sum(1 for s in unified_standards if s['type_display'] == '团体标准')
            national_count = sum(1 for s in unified_standards if s['type_display'] == '国家标准')
            local_count = sum(1 for s in unified_standards if s['type_display'] == '地方标准')
            industry_count = sum(1 for s in unified_standards if s['type_display'] == '行业标准')
            enterprise_count = sum(1 for s in unified_standards if s['type_display'] == '企业标准')
            std_total = len(unified_standards)
            grand_total_standards += std_total

            addr_parts = [ent.get('province', ''), ent.get('city', ''), ent.get('district', '')]
            addr_str = "".join([p for p in addr_parts if p and p != '-'])

            result_items.append({
                'index': idx,
                'input_name': name,
                'matched_name': name,
                'credit_code': ent.get('credit_code') or '-',
                'legal_person': ent.get('legal_person') or '-',
                'area': addr_str or '-',
                'agency_type': ent.get('enterprise_type') or '社会团体',
                'status': 'matched' if is_matched else 'not_found',
                'standard_total': std_total,
                'group_count': group_count,
                'national_count': national_count,
                'local_count': local_count,
                'industry_count': industry_count,
                'enterprise_count': enterprise_count,
                'standards': unified_standards
            })

        return {
            'total_input': len(clean_names),
            'matched_count': matched_associations,
            'total_standards_count': grand_total_standards,
            'items': result_items
        }

    @classmethod
    def export_associations_merged_excel(cls, names: list) -> tuple:
        """
        生成单文件双 Sheet 的专业格式化 Excel 报表：
          - Sheet 1: 【社团组织与标准资产总览】
          - Sheet 2: 【各协会标准目录明细全集】
        
        Returns:
            (excel_bytes: bytes, filename: str)
        """
        summary_res = cls.batch_query_associations(names)
        items = summary_res.get('items', [])

        wb = openpyxl.Workbook()
        
        # ── 样式与字体定义 ─────────────────────────────────────────
        teal_fill = PatternFill(start_color="0D9488", end_color="0D9488", fill_type="solid")
        zebra_fill = PatternFill(start_color="F9FAFB", end_color="F9FAFB", fill_type="solid")
        title_font = Font(name="Microsoft YaHei", size=15, bold=True, color="111827")
        subtitle_font = Font(name="Microsoft YaHei", size=9, italic=True, color="6B7280")
        header_font = Font(name="Microsoft YaHei", size=11, bold=True, color="FFFFFF")
        data_font = Font(name="Microsoft YaHei", size=10, color="1F2937")
        bold_data_font = Font(name="Microsoft YaHei", size=10, bold=True, color="0D9488")
        
        thin_border = Border(
            left=Side(style='thin', color='E5E7EB'),
            right=Side(style='thin', color='E5E7EB'),
            top=Side(style='thin', color='E5E7EB'),
            bottom=Side(style='thin', color='E5E7EB')
        )
        center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
        left_align = Alignment(horizontal="left", vertical="center", wrap_text=True)
        right_align = Alignment(horizontal="right", vertical="center", wrap_text=True)

        now_str = timezone.now().strftime("%Y-%m-%d %H:%M:%S")

        # ============================================================
        # Sheet 1: 【社团组织与标准资产总览】
        # ============================================================
        ws1 = wb.active
        ws1.title = "社团标准资产概览"
        ws1.views.sheetView[0].showGridLines = True

        # 标题行
        ws1.merge_cells("A1:M1")
        c_title1 = ws1["A1"]
        c_title1.value = "社会团体/行业协会标准资产汇总统计表"
        c_title1.font = title_font
        c_title1.alignment = center_align
        ws1.row_dimensions[1].height = 36

        # 副标题行
        ws1.merge_cells("A2:M2")
        c_sub1 = ws1["A2"]
        c_sub1.value = f"生成时间: {now_str}  |  涉及社会组织共 {summary_res['total_input']} 家  |  匹配命中 {summary_res['matched_count']} 家  |  累计覆盖标准资产共 {summary_res['total_standards_count']} 项"
        c_sub1.font = subtitle_font
        c_sub1.alignment = center_align
        ws1.row_dimensions[2].height = 20

        # 表头
        headers1 = [
            "序号", "社团组织名称", "统一社会信用代码", "法定代表人", "所属省市区",
            "组织类型", "团体标准数", "国家标准数", "行业标准数", "地方标准数", "企业标准数", "标准总数", "匹配状态"
        ]
        ws1.row_dimensions[3].height = 28

        for col_idx, h_text in enumerate(headers1, 1):
            cell = ws1.cell(row=3, column=col_idx, value=h_text)
            cell.font = header_font
            cell.fill = teal_fill
            cell.alignment = center_align
            cell.border = thin_border

        # 数据行
        for r_idx, item in enumerate(items, 4):
            status_text = '已建档/已收录' if item['status'] == 'matched' else '库中暂无基础工商'
            row_vals = [
                item['index'],
                item['input_name'],
                item['credit_code'],
                item['legal_person'],
                item['area'],
                item['agency_type'],
                item['group_count'],
                item['national_count'],
                item['industry_count'],
                item['local_count'],
                item['enterprise_count'],
                item['standard_total'],
                status_text
            ]
            ws1.row_dimensions[r_idx].height = 22
            is_even = (r_idx % 2 == 0)

            for col_idx, val in enumerate(row_vals, 1):
                cell = ws1.cell(row=r_idx, column=col_idx, value=val)
                cell.border = thin_border
                cell.font = bold_data_font if col_idx == 12 and val > 0 else data_font
                if is_even:
                    cell.fill = zebra_fill

                if col_idx in [1, 3, 7, 8, 9, 10, 11, 12, 13]:
                    cell.alignment = center_align
                elif col_idx in [2, 4, 5, 6]:
                    cell.alignment = left_align

        # 冻结前三行
        ws1.freeze_panes = "A4"

        # ============================================================
        # Sheet 2: 【各协会标准目录明细大清单】
        # ============================================================
        ws2 = wb.create_sheet(title="各协会标准目录明细全集")
        ws2.views.sheetView[0].showGridLines = True

        # 标题行
        ws2.merge_cells("A1:J1")
        c_title2 = ws2["A1"]
        c_title2.value = "社会团体/行业协会标准目录明细大清单"
        c_title2.font = title_font
        c_title2.alignment = center_align
        ws2.row_dimensions[1].height = 36

        # 副标题行
        ws2.merge_cells("A2:J2")
        c_sub2 = ws2["A2"]
        c_sub2.value = f"生成时间: {now_str}  |  涵盖各社会组织名下全部标准目录  |  明细清单共 {summary_res['total_standards_count']} 条记录"
        c_sub2.font = subtitle_font
        c_sub2.alignment = center_align
        ws2.row_dimensions[2].height = 20

        # 表头
        headers2 = [
            "序号", "归属社团组织名称", "统一社会信用代码", "标准编号", "标准中文名称",
            "标准类别", "起草单位排名 / 身份", "标准状态", "发布日期", "实施日期"
        ]
        ws2.row_dimensions[3].height = 28

        for col_idx, h_text in enumerate(headers2, 1):
            cell = ws2.cell(row=3, column=col_idx, value=h_text)
            cell.font = header_font
            cell.fill = teal_fill
            cell.alignment = center_align
            cell.border = thin_border

        # 展平写入所有明细
        detail_row_idx = 4
        std_global_index = 1

        for item in items:
            assoc_name = item['input_name']
            credit_code = item['credit_code']
            stds = item.get('standards', [])

            if not stds:
                continue

            for s in stds:
                ws2.row_dimensions[detail_row_idx].height = 22
                is_even = (detail_row_idx % 2 == 0)
                row_vals = [
                    std_global_index,
                    assoc_name,
                    credit_code,
                    s['standard_no'],
                    s['title'],
                    s['type_display'],
                    s['drafter_display'],
                    s['status'],
                    s['release_date'],
                    s['implement_date']
                ]

                for col_idx, val in enumerate(row_vals, 1):
                    cell = ws2.cell(row=detail_row_idx, column=col_idx, value=val)
                    cell.border = thin_border
                    cell.font = data_font
                    if is_even:
                        cell.fill = zebra_fill

                    if col_idx in [1, 3, 6, 7, 8, 9, 10]:
                        cell.alignment = center_align
                    elif col_idx in [2, 4, 5]:
                        cell.alignment = left_align

                std_global_index += 1
                detail_row_idx += 1

        # 冻结前三行
        ws2.freeze_panes = "A4"

        # ── 自动计算两张 Sheet 的列宽 ──────────────────────────────
        for ws in [ws1, ws2]:
            for col in ws.columns:
                max_len = 0
                col_letter = get_column_letter(col[0].column)
                for cell in col[2:]:  # 从第 3 行表头及以下开始计算
                    if cell.value:
                        val_str = str(cell.value)
                        # 中文字符算 2 字符宽，英文/数字算 1 字符宽
                        c_len = sum(2 if ord(char) > 127 else 1 for char in val_str)
                        if c_len > max_len:
                            max_len = c_len
                ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        filename = f"社团协会标准资产汇总及明细目录_{timezone.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return buffer.getvalue(), filename
