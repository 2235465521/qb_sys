from django.core.management.base import BaseCommand
from companies.models import CompanyCategory


class Command(BaseCommand):
    help = '初始化企业所有制分类与标签体系字典（包含国企、民企、外资、港澳台、事业单位与科研高校、社会组织、国家机关等）'

    def handle(self, *args, **options):
        # 1. 主分类 (Main Categories)
        main_categories_data = [
            {
                'code': 'state_owned',
                'name': '国有企业',
                'category_type': 'main',
                'badge_color': 'blue',
                'sort_order': 10,
                'definition': '指企业全部资产归国家所有，并按《中华人民共和国企业法人登记管理条例》规定登记注册的非公司制的经济组织，以及国有独资、国有控股和国有实际控制的企业。'
            },
            {
                'code': 'private',
                'name': '民营企业',
                'category_type': 'main',
                'badge_color': 'green',
                'sort_order': 20,
                'definition': '指民间私有资本投资、民间私人进行经营且由民间所有人享受收益、承担风险的经济实体。'
            },
            {
                'code': 'hmt_invested',
                'name': '港澳台投资企业',
                'category_type': 'main',
                'badge_color': 'purple',
                'sort_order': 30,
                'definition': '指港澳台地区投资者依照中华人民共和国法律及有关法规在内地投资设立的企业。'
            },
            {
                'code': 'foreign_invested',
                'name': '外商投资企业',
                'category_type': 'main',
                'badge_color': 'orange',
                'sort_order': 40,
                'definition': '指外国企业、外国人或其他经济组织依照中国法律法规在中国境内设立的投资企业。'
            },
            {
                'code': 'public_institution',
                'name': '事业单位与科研高校',
                'category_type': 'main',
                'badge_color': 'gold',
                'sort_order': 50,
                'definition': '指国家为了社会公益目的，由国家机关举办或者其他组织利用国有资产举办的社会服务组织，包括公立高等院校、科研院所、检验检测机构、公立医院等。'
            },
            {
                'code': 'social_organization',
                'name': '社会团体与行业组织',
                'category_type': 'main',
                'badge_color': 'magenta',
                'sort_order': 60,
                'definition': '指中国公民或单位自愿组成，为实现会员共同意愿，按照其章程开展活动的非营利性社会组织，包括行业协会、学会、联合会、商会、促进会、基金会等。'
            },
            {
                'code': 'government_agency',
                'name': '国家机关与政务机构',
                'category_type': 'main',
                'badge_color': 'red',
                'sort_order': 70,
                'definition': '指行使国家行政职权、管理国家行政事务的各级人民政府及其所属各工作部门或各类管理委员会。'
            },
        ]

        main_cat_map = {}
        for item in main_categories_data:
            cat, created = CompanyCategory.objects.update_or_create(
                code=item['code'],
                defaults={
                    'name': item['name'],
                    'category_type': item['category_type'],
                    'badge_color': item['badge_color'],
                    'sort_order': item['sort_order'],
                    'definition': item['definition'],
                    'parent': None,
                    'is_active': True,
                }
            )
            main_cat_map[item['code']] = cat
            status_text = '创建' if created else '更新'
            self.stdout.write(f"[{status_text}] 主大类: {cat.name} ({cat.code})")

        # 2. 小类标签 (Subcategories)
        sub_categories_data = [
            # ── 国有企业子类 ────────────────────────
            {
                'parent_code': 'state_owned',
                'code': 'central_soe',
                'name': '央企',
                'badge_color': 'blue',
                'sort_order': 11,
                'definition': '指国务院授权国有资产监督管理委员会履行出资人职责的企业。'
            },
            {
                'parent_code': 'state_owned',
                'code': 'central_soe_sub',
                'name': '央企子公司',
                'badge_color': 'blue',
                'sort_order': 12,
                'definition': '指央企对外投资控股形成的各级子公司，包含国有资产监督管理委员会披露的央企旗下的子公司或成员和股权穿透计算而得的企业。'
            },
            {
                'parent_code': 'state_owned',
                'code': 'provincial_soe',
                'name': '省属国企',
                'badge_color': 'geekblue',
                'sort_order': 13,
                'definition': '指各省或各直辖市国有资产监督管理委员会披露的省属监管企业以及直接出资控股的企业。'
            },
            {
                'parent_code': 'state_owned',
                'code': 'municipal_soe',
                'name': '市属国企',
                'badge_color': 'cyan',
                'sort_order': 14,
                'definition': '指各地级市国有资产监督管理委员会所披露的市属监管企业以及直接出资控股的企业。'
            },
            {
                'parent_code': 'state_owned',
                'code': 'county_soe',
                'name': '县（区）属国企',
                'badge_color': 'cyan',
                'sort_order': 15,
                'definition': '各县或区级政府/国资机构履行出资人职责或直接出资控股的企业。'
            },
            {
                'parent_code': 'state_owned',
                'code': 'state_wholly_owned',
                'name': '国有全资企业',
                'badge_color': 'blue',
                'sort_order': 16,
                'definition': '指政府部门、机构、事业单位、国有独资企业单独或共同出资，直接或间接合计持股为100%的企业。'
            },
            {
                'parent_code': 'state_owned',
                'code': 'state_solely_funded',
                'name': '国有独资企业',
                'badge_color': 'blue',
                'sort_order': 17,
                'definition': '指国家单独出资、由国务院或者地方人民政府授权本级人民政府国有资产监督管理机构履行出资人职责的企业。'
            },
            {
                'parent_code': 'state_owned',
                'code': 'state_controlled',
                'name': '国有控股企业',
                'badge_color': 'geekblue',
                'sort_order': 18,
                'definition': '是指在企业的全部资本中，国家资本（股本）所占比例大于50%的企业，且为第一大股东。'
            },
            {
                'parent_code': 'state_owned',
                'code': 'state_actual_controlled',
                'name': '国有实际控制企业',
                'badge_color': 'geekblue',
                'sort_order': 19,
                'definition': '指在企业的全部资本中，国家资本（股本）所占比例未超过50%，但为第一大股东，并且通过股东协议、公司章程、董事会决议或者其他协议安排能够对其实际支配的企业。'
            },

            # ── 民营企业子类 ────────────────────────
            {
                'parent_code': 'private',
                'code': 'private_general',
                'name': '民营企业',
                'badge_color': 'green',
                'sort_order': 21,
                'definition': '是指民间私有资本投资、民间私人进行经营且由民间所有人享受收益、承担风险的经济实体。'
            },

            # ── 港澳台投资企业子类 ──────────────────
            {
                'parent_code': 'hmt_invested',
                'code': 'hmt_joint_venture',
                'name': '港澳台合资经营企业',
                'badge_color': 'purple',
                'sort_order': 31,
                'definition': '指港澳台地区投资者与内地企业依照《中华人民共和国中外合资经营企业法》及有关法律的规定，按合同规定的比例投资设立、分享利润和分担风险的企业。'
            },
            {
                'parent_code': 'hmt_invested',
                'code': 'hmt_cooperative',
                'name': '港澳台合作经营企业',
                'badge_color': 'purple',
                'sort_order': 32,
                'definition': '指港澳台地区投资者与内地企业依照《中华人民共和国中外合作经营企业法》及有关法律的规定，依照合作合同的约定进行投资或提供条件设立、分配利润和分担风险的企业。'
            },
            {
                'parent_code': 'hmt_invested',
                'code': 'hmt_wholly_owned',
                'name': '港澳台独资企业',
                'badge_color': 'purple',
                'sort_order': 33,
                'definition': '指依照《中华人民共和国外资企业法》及有关法律的规定，在内地由港澳台地区投资者全额投资设立的企业。'
            },
            {
                'parent_code': 'hmt_invested',
                'code': 'hmt_limited_by_shares',
                'name': '港澳台投资股份有限公司',
                'badge_color': 'purple',
                'sort_order': 34,
                'definition': '指根据国家有关规定，经外经贸部依法批准设立，其中港、澳、台商的股本占公司注册资本的比例达25%以上的股份有限公司。'
            },
            {
                'parent_code': 'hmt_invested',
                'code': 'hmt_other',
                'name': '其他港澳台投资企业',
                'badge_color': 'purple',
                'sort_order': 35,
                'definition': '指在中国境内参照有关规定依法设立的港、澳、台商投资合伙企业及其他组织等。'
            },

            # ── 外商投资企业子类 ────────────────────
            {
                'parent_code': 'foreign_invested',
                'code': 'foreign_joint_venture',
                'name': '中外合资经营企业',
                'badge_color': 'orange',
                'sort_order': 41,
                'definition': '指中国合营者与外国合营者依照中国法律的规定，在中国境内共同投资、共同经营、并按投资比例分享利润、分担风险及亏损的企业。'
            },
            {
                'parent_code': 'foreign_invested',
                'code': 'foreign_cooperative',
                'name': '中外合作经营企业',
                'badge_color': 'orange',
                'sort_order': 42,
                'definition': '指外国企业或外国人与中国内地企业依照《中华人民共和国中外合作经营企业法》及有关法律的规定，依照合作合同的约定进行投资或提供条件设立、分配利润和分担风险的企业。'
            },
            {
                'parent_code': 'foreign_invested',
                'code': 'foreign_wholly_owned',
                'name': '外资企业（独资）',
                'badge_color': 'orange',
                'sort_order': 43,
                'definition': '指依照《中华人民共和国外资企业法》等有关法律在中国境内设立的全部资本由外国投资者投资的企业。'
            },
            {
                'parent_code': 'foreign_invested',
                'code': 'foreign_limited_by_shares',
                'name': '外商投资股份有限公司',
                'badge_color': 'orange',
                'sort_order': 44,
                'definition': '指根据国家有关规定，经外经贸部依法批准设立，其中外资的股本占公司注册资本的比例达25%以上的股份有限公司。'
            },
            {
                'parent_code': 'foreign_invested',
                'code': 'foreign_other',
                'name': '其他外商投资企业',
                'badge_color': 'orange',
                'sort_order': 45,
                'definition': '指外商投资合伙企业和其他未区分的外商投资企业。'
            },

            # ── 事业单位与科研高校子类 ──────────────
            {
                'parent_code': 'public_institution',
                'code': 'higher_education',
                'name': '高等院校',
                'badge_color': 'gold',
                'sort_order': 51,
                'definition': '指教育部及各省市教育行政主管部门审批设立的大学、学院、高等职业技术学校等公立或非营利性高等学府。'
            },
            {
                'parent_code': 'public_institution',
                'code': 'research_institute',
                'name': '科研院所',
                'badge_color': 'volcano',
                'sort_order': 52,
                'definition': '指中国科学院、中国工程院、国家各部委及地方所属的科学技术研究院、研究所、标准化/计量/检验检测等专业科研技术机构。'
            },
            {
                'parent_code': 'public_institution',
                'code': 'public_organization',
                'name': '事业单位/公共机构',
                'badge_color': 'gold',
                'sort_order': 53,
                'definition': '指国家为了社会公益目的，由国家机关举办或者其他组织利用国有资产举办的从事教育、文化、卫生、监测等社会公益服务的各级各类事业单位。'
            },

            # ── 社会团体与行业组织子类 ──────────────
            {
                'parent_code': 'social_organization',
                'code': 'industry_association',
                'name': '行业协会/学会',
                'badge_color': 'magenta',
                'sort_order': 61,
                'definition': '由企业、事业单位或专业技术人员组成的全国性或地方性行业协会、学会、联合会、商会或研究会等非营利性社会组织。'
            },

            # ── 国家机关与政务机构子类 ──────────────
            {
                'parent_code': 'government_agency',
                'code': 'government_agency_sub',
                'name': '行政机关/管委会',
                'badge_color': 'red',
                'sort_order': 71,
                'definition': '指行使国家行政职权、管理国家行政事务的各级人民政府及其所属各工作部门或园区管理委员会。'
            },
        ]

        for item in sub_categories_data:
            parent_cat = main_cat_map.get(item['parent_code'])
            cat, created = CompanyCategory.objects.update_or_create(
                code=item['code'],
                defaults={
                    'name': item['name'],
                    'category_type': 'sub',
                    'badge_color': item['badge_color'],
                    'sort_order': item['sort_order'],
                    'definition': item['definition'],
                    'parent': parent_cat,
                    'is_active': True,
                }
            )
            status_text = '创建' if created else '更新'
            self.stdout.write(f"  [{status_text}] 小类标签: {cat.name} ({cat.code}) -> 所属: {parent_cat.name}")

        self.stdout.write(self.style.SUCCESS("成功初始化全体系分类与标签（含企事业单位、高校、科研院所、社会组织）！"))
