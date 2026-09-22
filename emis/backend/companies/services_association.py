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
    def _build_candidate_name_variants(cls, name: str) -> list:
        """
        为输入的社团/协会名称生成智能别名候选集：
          - 规范化标点（去除末尾句号、顿号、空格）
          - 全半角括号互换
          - 泛化词互转（“行业协会” <-> “协会”）
        """
        raw = str(name or '').strip().rstrip('。，,. ；;')
        variants = {raw}
        raw_half = raw.replace('（', '(').replace('）', ')')
        raw_full = raw.replace('(', '（').replace(')', '）')
        variants.add(raw_half)
        variants.add(raw_full)

        for v in list(variants):
            if '行业协会' in v:
                variants.add(v.replace('行业协会', '协会'))
            elif '协会' in v:
                variants.add(v.replace('协会', '行业协会'))

        return [v for v in variants if v]

    @classmethod
    def batch_query_associations(cls, names: list) -> dict:
        """
        深度批量穿透检索输入的社会团体/行业协会的标准资产。
        
        多源深度聚合策略：
          1. 智能别名衍生：自动处理全半角括号、“协会”与“行业协会”互转、末尾标点清洗；
          2. 权威工商对齐：批量从 compare_conp.ent_std_maker 与 EMIS Company 表获取官方信用代码与法人；
          3. 团标发布全景关联 (std_tb_detail)：批量从 std_tb_detail 的 tb_asso / Issu_auth / unit_name 捕获协会自主发布的团体标准；
          4. 标准起草人关联 (unit_dict -> std_unit_relation)：通过名称别名和统一社会信用代码反查 unit_dict，批量提取起草的国标、行标、地标与团标；
          5. 本地企标库合并：关联 EMIS 本地 Standard 表；
          6. 全局去重与结构化分类统计。
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

        # ── 步骤 0：生成所有名称的智能别名候选字典 ──────────────
        name_to_variants = {}
        all_variants_set = set()
        for name in clean_names:
            vars_list = cls._build_candidate_name_variants(name)
            name_to_variants[name] = vars_list
            all_variants_set.update(vars_list)
        all_variants = list(all_variants_set)

        # ── 步骤 1：批量工商与主体对齐 ────────────────────────────
        ent_map = {}
        chunk_size = 300
        try:
            with connections['compare_conp'].cursor() as cur:
                for i in range(0, len(all_variants), chunk_size):
                    chunk = all_variants[i:i + chunk_size]
                    placeholders = ', '.join(['%s'] * len(chunk))
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
                    """, chunk)
                    for r in cur.fetchall():
                        ent_map[r[0]] = {
                            'matched_name': r[0],
                            'credit_code': r[1] or '',
                            'legal_person': r[2] or '-',
                            'province': r[3] or '',
                            'city': r[4] or '',
                            'district': r[5] or '',
                            'enterprise_type': r[6] or '社会团体'
                        }
        except Exception:
            pass

        # 结合本地 Company 表
        try:
            local_companies = Company.objects.filter(name__in=all_variants)
            for comp in local_companies:
                c_name = comp.name
                if c_name not in ent_map or not ent_map[c_name].get('credit_code'):
                    ent_map[c_name] = {
                        'matched_name': c_name,
                        'credit_code': comp.credit_code or '',
                        'legal_person': comp.legal_person or '-',
                        'province': comp.province.name if comp.province else '',
                        'city': comp.city.name if comp.city else '',
                        'district': comp.district.name if comp.district else '',
                        'enterprise_type': '社会团体'
                    }
        except Exception:
            pass

        # 收集所有已匹配的信用代码用于反向穿透
        all_matched_credits = list({ent_map[k]['credit_code'] for k in ent_map if ent_map[k].get('credit_code')})

        # ── 步骤 2：多维度批量检索 unit_dict 获取 unit_id ─────────
        unit_map = {}  # { variant_name: [unit_ids...] }
        credit_to_uids = {}  # { credit_code: [unit_ids...] }
        all_uids_set = set()

        try:
            with connections['stsc_db'].cursor() as cur:
                # 2.1 按机构名称别名查 unit_dict
                for i in range(0, len(all_variants), chunk_size):
                    chunk = all_variants[i:i + chunk_size]
                    placeholders = ', '.join(['%s'] * len(chunk))
                    cur.execute(f"""
                        SELECT unit_id, unit_name, credit_code
                        FROM unit_dict
                        WHERE unit_name IN ({placeholders})
                    """, chunk)
                    for uid, uname, ccode in cur.fetchall():
                        unit_map.setdefault(uname, []).append(uid)
                        all_uids_set.add(uid)
                        if ccode and uname not in ent_map:
                            ent_map[uname] = {
                                'matched_name': uname,
                                'credit_code': ccode,
                                'legal_person': '-',
                                'province': '',
                                'city': '',
                                'district': '',
                                'enterprise_type': '社会团体'
                            }
        except Exception:
            pass

        # 2.2 按统一社会信用代码反查 unit_dict（穿透分会与别名）
        if all_matched_credits:
            for db_alias in ['stsc_db', 'stsc_standard_database']:
                try:
                    with connections[db_alias].cursor() as cur:
                        for i in range(0, len(all_matched_credits), chunk_size):
                            chunk = all_matched_credits[i:i + chunk_size]
                            placeholders = ', '.join(['%s'] * len(chunk))
                            cur.execute(f"""
                                SELECT unit_id, unit_name, credit_code
                                FROM unit_dict
                                WHERE credit_code IN ({placeholders})
                            """, chunk)
                            for uid, uname, ccode in cur.fetchall():
                                if ccode:
                                    credit_to_uids.setdefault(ccode, []).append(uid)
                                    all_uids_set.add(uid)
                except Exception:
                    pass

        # ── 步骤 3：核心增强 — 批量检索 std_tb_detail (团体标准发布协会) ──
        tb_published_stds = {}  # { variant_name: [std_dicts...] }

        try:
            with connections['stsc_db'].cursor() as cur:
                tb_chunk_size = 100
                for i in range(0, len(all_variants), tb_chunk_size):
                    chunk = all_variants[i:i + tb_chunk_size]
                    placeholders = ', '.join(['%s'] * len(chunk))
                    cur.execute(f"""
                        SELECT 
                            t.tb_asso, t.Issu_auth, t.unit_name,
                            v.std_id, v.std_chinesename, v.std_type, v.release_date, v.implement_date, v.ex_state,
                            t.drafter
                        FROM std_tb_detail t
                        JOIN view_std_full v ON t.base_id = v.id
                        WHERE t.tb_asso IN ({placeholders}) 
                           OR t.Issu_auth IN ({placeholders}) 
                           OR t.unit_name IN ({placeholders})
                    """, chunk * 3)
                    for r in cur.fetchall():
                        asso, issu, uname, sid, stitle, stype, rdate, idate, status_val, drafter = r
                        matched_key = asso if asso in chunk else (issu if issu in chunk else uname)
                        tb_published_stds.setdefault(matched_key, []).append({
                            'standard_no': sid or '',
                            'title': stitle or '无标题',
                            'type_display': '团体标准',
                            'release_date': str(rdate) if rdate else '-',
                            'implement_date': str(idate) if idate else '-',
                            'status_raw': status_val,
                            'drafter_display': '主要发布协会',
                            'rank': 1,
                            'is_local': False,
                            'source': 'tb_published'
                        })
        except Exception:
            pass

        # ── 步骤 4：批量检索 std_unit_relation (起草人关联) ──────────
        all_uids = list(all_uids_set)
        unit_rel_stds = {}  # { unit_id: [std_dicts...] }

        if all_uids:
            try:
                with connections['stsc_db'].cursor() as cur:
                    for i in range(0, len(all_uids), chunk_size):
                        chunk = all_uids[i:i + chunk_size]
                        placeholders = ', '.join(['%s'] * len(chunk))
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
                            WHERE r.unit_id IN ({placeholders})
                            ORDER BY v.release_date DESC
                        """, chunk)
                        for row in cur.fetchall():
                            uid, sid, stitle, stype, rdate, idate, status_val, drafter, rank = row
                            
                            # 推导标准类别
                            s_no = (sid or '').strip().upper()
                            t_raw = (stype or '').upper()
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
                            if rank:
                                rank_disp = f"第{rank}名"
                            elif drafter:
                                parts = drafter.replace(';', ',').replace('，', ',').split(',')
                                rank_disp = " / ".join([p.strip() for p in parts[:2] if p.strip()])
                            else:
                                rank_disp = '-'

                            unit_rel_stds.setdefault(uid, []).append({
                                'standard_no': sid or '',
                                'title': stitle or '无标题',
                                'type_display': t_disp,
                                'release_date': str(rdate) if rdate else '-',
                                'implement_date': str(idate) if idate else '-',
                                'status_raw': status_val,
                                'drafter_display': rank_disp,
                                'rank': rank or 99,
                                'is_local': False,
                                'source': 'unit_drafted'
                            })
            except Exception:
                pass

        # ── 步骤 5：本地企标检索 ──────────────────────────────────
        local_stds_by_name = {}
        try:
            local_stds = Standard.objects.filter(company__name__in=all_variants).select_related('company')
            for ls in local_stds:
                c_name = ls.company.name
                local_stds_by_name.setdefault(c_name, []).append({
                    'standard_no': ls.standard_no or '',
                    'title': ls.title or '无标题',
                    'type_display': '企业标准',
                    'release_date': ls.publish_date.strftime('%Y-%m-%d') if ls.publish_date else '-',
                    'implement_date': ls.implement_date.strftime('%Y-%m-%d') if ls.implement_date else '-',
                    'status_raw': 1 if ls.status == 'active' else 0,
                    'drafter_display': '主起草单位',
                    'rank': 1,
                    'is_local': True,
                    'source': 'local'
                })
        except Exception:
            pass

        # ── 步骤 6：多源汇总聚合与全局去重 ────────────────────────
        status_map = {0: '废止', 1: '现行', 2: '即将实施'}

        result_items = []
        grand_total_standards = 0
        matched_associations = 0

        for idx, name in enumerate(clean_names, 1):
            vars_list = name_to_variants.get(name, [name])

            # 6.1 查找最佳工商档案（优先原名，再别名）
            ent = {}
            for v in vars_list:
                if v in ent_map and ent_map[v].get('credit_code'):
                    ent = ent_map[v]
                    break
            if not ent:
                for v in vars_list:
                    if v in ent_map:
                        ent = ent_map[v]
                        break

            credit_code = ent.get('credit_code', '')
            matched_official_name = ent.get('matched_name') or name

            # 6.2 汇集该协会关联的所有 unit_id（来自名称别名及统一代码）
            associated_uids = set()
            for v in vars_list:
                for uid in unit_map.get(v, []):
                    associated_uids.add(uid)
            if credit_code:
                for uid in credit_to_uids.get(credit_code, []):
                    associated_uids.add(uid)

            # 6.3 汇集所有来源标准并去重
            seen_std_nos = set()
            unified_standards = []

            # 优先 1：本地企标
            for v in vars_list:
                for s in local_stds_by_name.get(v, []):
                    s_no = (s['standard_no'] or '').strip().upper()
                    if s_no and s_no not in seen_std_nos:
                        seen_std_nos.add(s_no)
                        unified_standards.append({
                            **s,
                            'status': '现行' if s['status_raw'] == 1 else '废止'
                        })

            # 优先 2：自主发布的团体标准 (std_tb_detail)
            for v in vars_list:
                for s in tb_published_stds.get(v, []):
                    s_no = (s['standard_no'] or '').strip().upper()
                    if s_no and s_no not in seen_std_nos:
                        seen_std_nos.add(s_no)
                        unified_standards.append({
                            **s,
                            'status': status_map.get(s['status_raw'], '现行')
                        })

            # 优先 3：起草的标准 (std_unit_relation)
            for uid in associated_uids:
                for s in unit_rel_stds.get(uid, []):
                    s_no = (s['standard_no'] or '').strip().upper()
                    if s_no and s_no not in seen_std_nos:
                        seen_std_nos.add(s_no)
                        unified_standards.append({
                            **s,
                            'status': status_map.get(s['status_raw'], '现行')
                        })

            std_total = len(unified_standards)
            is_matched = bool(credit_code or associated_uids or std_total > 0)
            if is_matched:
                matched_associations += 1
            grand_total_standards += std_total

            # 分类统计
            group_count = sum(1 for s in unified_standards if s['type_display'] == '团体标准')
            national_count = sum(1 for s in unified_standards if s['type_display'] == '国家标准')
            local_count = sum(1 for s in unified_standards if s['type_display'] == '地方标准')
            industry_count = sum(1 for s in unified_standards if s['type_display'] == '行业标准')
            enterprise_count = sum(1 for s in unified_standards if s['type_display'] == '企业标准')

            addr_parts = [ent.get('province', ''), ent.get('city', ''), ent.get('district', '')]
            addr_str = "".join([p for p in addr_parts if p and p != '-'])

            result_items.append({
                'index': idx,
                'input_name': name,
                'matched_name': matched_official_name,
                'credit_code': credit_code or '-',
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
