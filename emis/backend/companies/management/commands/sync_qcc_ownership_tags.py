from django.core.management.base import BaseCommand
from companies.models import Company
from companies.ownership_service import OwnershipTagService


class Command(BaseCommand):
    help = '通过企查查（QCC）API 或智能规则引擎为存量企业批量打上所有制与小类属性标签'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=0, help='处理企业数量上限（0 表示全部）')
        parser.add_argument('--force', action='store_true', help='强制覆盖已有标签')
        parser.add_argument('--use-qcc', action='store_true', help='强制启用企查查 API 进行联网穿透')

    def handle(self, *args, **options):
        limit = options['limit']
        force = options['force']
        use_qcc = options['use_qcc']

        qs = Company.objects.filter(is_deleted=False)
        if not force:
            # 默认只给尚未打标签的企业打标
            qs = qs.filter(ownership_categories__isnull=True).distinct()

        total = qs.count()
        if limit > 0:
            qs = qs[:limit]
            total = limit

        self.stdout.write(f"开始为 {total} 家企业执行所有制分类打标...")

        count = 0
        for company in qs:
            tags_applied = []
            if use_qcc:
                qcc_data = OwnershipTagService.call_qcc_api(company.name, company.credit_code)
                if qcc_data:
                    tags_applied = OwnershipTagService.parse_and_assign_qcc_data(company, qcc_data)
            
            if not tags_applied:
                # 兜底使用高精度规则分析
                tags_applied = OwnershipTagService.predict_and_assign_by_rules(company)

            count += 1
            if count % 50 == 0 or count == total:
                self.stdout.write(f"已处理 {count}/{total} 家企业... [{company.name} -> {','.join(tags_applied)}]")

        self.stdout.write(self.style.SUCCESS(f"打标完成！共为 {count} 家企业成功赋予所有制标签。"))
