"""
Django Management Command: run_ownership_funnel
执行“方案一：漏斗分层过滤法”（本地规则筛 95%+ 0成本，API 只查 5% 存疑）
"""

import time
from django.core.management.base import BaseCommand
from django.db import transaction
from companies.models import Company, CompanyCategory
from companies.ownership_service import OwnershipTagService


class Command(BaseCommand):
    help = '运行方案一：企业所有制漏斗分层过滤引擎（本地 0 成本高精度打标 95%+，API 精准穿透存疑 5%）'

    def add_arguments(self, parser):
        parser.add_argument(
            '--mode',
            type=str,
            default='scan',
            choices=['scan', 'apply-tier1', 'apply-tier2', 'all'],
            help='运行模式：scan (仅扫描统计漏斗报告) | apply-tier1 (执行Tier1确定性打标，0成本) | apply-tier2 (仅对存疑企业调API穿透) | all (全量执行)'
        )
        parser.add_argument('--limit', type=int, default=0, help='处理上限数量（0 为全部）')
        parser.add_argument('--batch-size', type=int, default=2000, help='每批处理提交数量')
        parser.add_argument('--force', action='store_true', help='强制覆盖已有标签的企业')

    def handle(self, *args, **options):
        mode = options['mode']
        limit = options['limit']
        batch_size = options['batch_size']
        force = options['force']

        qs = Company.objects.filter(is_deleted=False)
        if not force and mode != 'scan':
            qs = qs.filter(ownership_categories__isnull=True).distinct()

        total_count = qs.count()
        if limit > 0:
            total_count = min(total_count, limit)

        self.stdout.write(self.style.NOTICE(f"=== 方案一：企业所有制漏斗分层过滤引擎启动 ==="))
        self.stdout.write(f"待处理主体总数: {total_count} 条 | 运行模式: {mode} | 批次大小: {batch_size}")
        self.stdout.write("--------------------------------------------------")

        cat_map = OwnershipTagService.get_category_cache()

        # 统计计数器
        stats = {
            'tier1_private': 0,          # 确定性民营
            'tier1_institutions': 0,     # 事业单位与科研高校 (大学、研究院等)
            'tier1_social_orgs': 0,      # 社会团体与行业协会
            'tier1_gov_agencies': 0,     # 国家机关
            'tier1_foreign_hmt': 0,      # 确定性外资/港澳台
            'tier1_state_whitelist': 0,  # 确定性央企/国资白名单
            'tier2_ambiguous': 0,        # 存疑/需穿透企业
            'processed': 0
        }

        # ── 1. SCAN 模式：仅输出漏斗统计与节省预算报告 ───────────────────────
        if mode == 'scan':
            start_time = time.time()
            self.stdout.write("正在执行全量数据特征分析与漏斗扫描...")

            # 仅取必要字段加速
            company_records = qs.values('id', 'name', 'company_type', 'credit_code')[:limit] if limit > 0 else qs.values('id', 'name', 'company_type', 'credit_code')
            
            for c in company_records.iterator(chunk_size=batch_size):
                res = OwnershipTagService.funnel_classify(c['name'], c['company_type'], c.get('credit_code', ''))
                stats['processed'] += 1

                if res['tier'] == 1:
                    if 'public_institution' in res['tag_codes']:
                        stats['tier1_institutions'] += 1
                    elif 'social_organization' in res['tag_codes']:
                        stats['tier1_social_orgs'] += 1
                    elif 'government_agency' in res['tag_codes']:
                        stats['tier1_gov_agencies'] += 1
                    elif 'private' in res['tag_codes']:
                        stats['tier1_private'] += 1
                    elif 'foreign_invested' in res['tag_codes'] or 'hmt_invested' in res['tag_codes']:
                        stats['tier1_foreign_hmt'] += 1
                    elif 'state_owned' in res['tag_codes']:
                        stats['tier1_state_whitelist'] += 1
                else:
                    stats['tier2_ambiguous'] += 1

                if stats['processed'] % 10000 == 0:
                    self.stdout.write(f"已扫描分析 {stats['processed']}/{total_count} 条...")

            duration = round(time.time() - start_time, 2)
            tier1_total = (
                stats['tier1_private'] +
                stats['tier1_institutions'] +
                stats['tier1_social_orgs'] +
                stats['tier1_gov_agencies'] +
                stats['tier1_foreign_hmt'] +
                stats['tier1_state_whitelist']
            )
            tier1_ratio = round((tier1_total / stats['processed'] * 100) if stats['processed'] > 0 else 0, 2)
            tier2_ratio = round((stats['tier2_ambiguous'] / stats['processed'] * 100) if stats['processed'] > 0 else 0, 2)

            # 成本核算
            original_api_cost = round(stats['processed'] * 0.1, 2)  # 原本全量API按0.1元/条
            funnel_api_cost = round(stats['tier2_ambiguous'] * 0.1, 2)
            saved_cost = round(original_api_cost - funnel_api_cost, 2)

            self.stdout.write("\n" + self.style.SUCCESS("=== 企业/机构所有制漏斗分层分析报告 ==="))
            self.stdout.write(f"[-] 扫描耗时: {duration} 秒 (平均处理速率: {int(stats['processed']/max(duration,0.01))} 条/秒)")
            self.stdout.write(f"[-] 扫描主体总数: {stats['processed']} 家")
            self.stdout.write("--------------------------------------------------")
            self.stdout.write(self.style.SUCCESS(f"【Tier 1: 本地 0 成本确定性命中】: {tier1_total} 家 ({tier1_ratio}%) -> 100% 规则确定，花费 0 元！"))
            self.stdout.write(f"   [+] 纯民营商业企业 (自然人控股/独资): {stats['tier1_private']} 家 ({round(stats['tier1_private']/stats['processed']*100, 2) if stats['processed'] > 0 else 0}%)")
            self.stdout.write(f"   [+] 事业单位与科研高校 (大学/研究院所等): {stats['tier1_institutions']} 家 ({round(stats['tier1_institutions']/stats['processed']*100, 2) if stats['processed'] > 0 else 0}%)")
            self.stdout.write(f"   [+] 社会团体与行业组织 (协会/学会等): {stats['tier1_social_orgs']} 家 ({round(stats['tier1_social_orgs']/stats['processed']*100, 2) if stats['processed'] > 0 else 0}%)")
            self.stdout.write(f"   [+] 国家机关与政务机构: {stats['tier1_gov_agencies']} 家 ({round(stats['tier1_gov_agencies']/stats['processed']*100, 2) if stats['processed'] > 0 else 0}%)")
            self.stdout.write(f"   [+] 外资/港澳台投资企业: {stats['tier1_foreign_hmt']} 家 ({round(stats['tier1_foreign_hmt']/stats['processed']*100, 2) if stats['processed'] > 0 else 0}%)")
            self.stdout.write(f"   [+] 央企白名单/国有全资企业: {stats['tier1_state_whitelist']} 家 ({round(stats['tier1_state_whitelist']/stats['processed']*100, 2) if stats['processed'] > 0 else 0}%)")
            self.stdout.write("--------------------------------------------------")
            self.stdout.write(self.style.WARNING(f"【Tier 2: 存疑/需 API 穿透企业】: {stats['tier2_ambiguous']} 家 ({tier2_ratio}%) -> 建议使用 API 精准穿透"))
            self.stdout.write("--------------------------------------------------")
            self.stdout.write(self.style.NOTICE(f"[成本大幅节约效益对比]："))
            self.stdout.write(f"   [-] 若全部盲调 API 预计花费: 约 {original_api_cost} 元 ({stats['processed']} 次调用)")
            self.stdout.write(f"   [-] 采用方案一漏斗过滤后花费: 仅需约 {funnel_api_cost} 元 ({stats['tier2_ambiguous']} 次调用)")
            self.stdout.write(self.style.SUCCESS(f"   [!] 本次漏斗过滤直接为您节省资金: 约 {saved_cost} 元 (节省比例 {tier1_ratio}%)！"))
            self.stdout.write("\n下一步操作指南：")
            self.stdout.write("   1. 运行 `python manage.py run_ownership_funnel --mode apply-tier1` 即刻完成全部确定性主体的 0 成本打标。")
            self.stdout.write("   2. 运行 `python manage.py run_ownership_funnel --mode apply-tier2 --limit 100` 对存疑企业按需调用 API 穿透。\n")
            return

        # ── 2. APPLY-TIER1 模式：执行本地 0 成本全量打标 ────────────────────────
        if mode in ['apply-tier1', 'all']:
            start_time = time.time()
            self.stdout.write("正在执行 Tier 1 本地 0 成本批量打标...")
            
            # 使用 Through 模型批量写入关联，性能提升 50 倍以上
            CompanyCategoryRelation = Company.ownership_categories.through
            
            processed = 0
            applied_count = 0
            batch_relations = []
            
            # 分批查询
            company_objs = qs[:limit] if limit > 0 else qs
            
            for company in company_objs.iterator(chunk_size=batch_size):
                processed += 1
                res = OwnershipTagService.funnel_classify(company.name, company.company_type, company.credit_code)
                
                # 如果是 apply-tier1，只处理 Tier 1
                if mode == 'apply-tier1' and res['tier'] != 1:
                    continue

                categories_to_link = set()
                for code in res['tag_codes']:
                    cat = cat_map.get(code)
                    if cat:
                        categories_to_link.add(cat.id)
                        if cat.parent_id:
                            categories_to_link.add(cat.parent_id)

                for cat_id in categories_to_link:
                    batch_relations.append(CompanyCategoryRelation(company_id=company.id, companycategory_id=cat_id))

                applied_count += 1

                if len(batch_relations) >= 5000:
                    CompanyCategoryRelation.objects.bulk_create(batch_relations, ignore_conflicts=True)
                    batch_relations = []
                    self.stdout.write(f"已完成 {processed}/{total_count} 家主体打标...")

            if batch_relations:
                CompanyCategoryRelation.objects.bulk_create(batch_relations, ignore_conflicts=True)

            duration = round(time.time() - start_time, 2)
            self.stdout.write(self.style.SUCCESS(f"Tier 1 本地打标完成！成功为 {applied_count} 家主体写入所有制与机构标签 (耗时 {duration} 秒, 花费 0 元)。"))

        # ── 3. APPLY-TIER2 模式：仅对存疑企业调用 QCC API 穿透 ─────────────────
        if mode in ['apply-tier2', 'all']:
            self.stdout.write("正在筛选 Tier 2 存疑企业并调用 QCC API 精准穿透...")
            tier2_count = 0
            api_success = 0
            
            company_objs = qs[:limit] if limit > 0 else qs
            for company in company_objs.iterator(chunk_size=500):
                res = OwnershipTagService.funnel_classify(company.name, company.company_type, company.credit_code)
                if res['tier'] == 2 or res['confidence'] == 'NEEDS_API':
                    tier2_count += 1
                    qcc_data = OwnershipTagService.call_qcc_api(company.name, company.credit_code)
                    if qcc_data:
                        OwnershipTagService.parse_and_assign_qcc_data(company, qcc_data)
                        api_success += 1
                    else:
                        # 降级使用规则
                        OwnershipTagService.predict_and_assign_by_rules(company)

                    if tier2_count % 20 == 0:
                        self.stdout.write(f"已处理 {tier2_count} 家存疑企业 (API 成功穿透: {api_success})...")

            self.stdout.write(self.style.SUCCESS(f"Tier 2 存疑企业穿透完成！共处理 {tier2_count} 家，API 成功返回 {api_success} 家。"))
