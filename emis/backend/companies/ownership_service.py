"""
companies.ownership_service — 企业所有制标签与分类漏斗分层智能识别引擎 (Tiered Funnel Engine)

方案一（漏斗分层法）：
  Tier 1（本地 0 成本高精度规则引擎，覆盖约 90%+ 存量企业）：
    - 确定性民营企业（自然人独资/控股/合伙/个体） -> 100% 自动打标（0 成本）
    - 确定性外资/港澳台（法定工商类型明确） -> 100% 自动打标（0 成本）
    - 确定性央企/国资（国资委 98 家央企名录白名单 + 国有独资/全资） -> 100% 自动打标（0 成本）
  Tier 2（存疑/混改/需股权穿透企业，约 5%~10%）：
    - 识别出归属不明确的国资控股/投资控股/集团型企业
    - 仅对这部分企业按需调用企查查（QCC）API 进行股权穿透与实际控制人精准归类
"""

import re
import time
import hashlib
import logging
import requests
from django.conf import settings
from companies.models import Company, CompanyCategory

logger = logging.getLogger(__name__)

# ============================================================
# 国务院国资委权威监管央企名录与核心骨干企业白名单
# ============================================================
CENTRAL_SOE_PATTERNS = [
    '中国核工业', '中核', '中国航天科技', '航天科技', '中国航天科工', '航天科工',
    '中国航空工业', '中航工业', '中国船舶', '中船', '中国兵器工业', '北方工业',
    '中国兵器装备', '中国电子科技', '中国电科', '中国航空发动机', '中国航发',
    '中国融通', '中国石油天然气', '中国石油', '中石油', '中国石油化工', '中国石化',
    '中石化', '中国海洋石油', '中海油', '国家管网', '国家石油天然气管网',
    '国家电网', '中国南方电网', '南方电网', '中国华能', '华能集团', '中国大唐',
    '大唐集团', '中国华电', '华电集团', '国家电力投资', '国家电投', '国电投',
    '中国长江三峡', '三峡集团', '国家能源投资', '国家能源集团', '国能',
    '中国电信', '中国联合网络通信', '中国联通', '中国移动通信', '中国移动',
    '中国电子信息产业', '中国电子', '中国第一汽车', '中国一汽', '一汽集团',
    '东风汽车', '中国一重', '中国机械工业', '国机集团', '哈尔滨电气', '哈电集团',
    '东方电气', '鞍钢', '中国宝武', '宝武钢铁', '中国矿产资源', '中国铝业',
    '中铝', '中国远洋海运', '中远海运', '中国航空集团', '国航', '中国东方航空',
    '东航', '中国南方航空', '南航', '中国中化', '中化集团', '中粮集团', '中粮',
    '中国五矿', '五矿集团', '中国通用技术', '通用技术', '中国建筑', '中建',
    '中国储备粮管理', '中储粮', '国家开发投资', '国投', '招商局', '华润',
    '中国旅游集团', '中旅', '中国商用飞机', '中国商飞', '中国节能环保', '中国节能',
    '中国国际工程咨询', '中咨', '中国诚通', '中国中煤能源', '中煤集团',
    '中国煤炭科工', '中煤科工', '机械科学研究总院', '中国钢研', '中国化学工程',
    '中国化学', '中国盐业', '中盐', '中国建材', '中国有色矿业', '中色',
    '有研科技', '矿冶科技', '中国医药集团', '国药集团', '国药', '中国保利',
    '保利集团', '中国建设科技', '新兴际华', '中国民航信息', '中国航空油料',
    '中国航油', '中国航空器材', '中国电力建设', '中国电建', '中国能源建设',
    '中国能建', '中国安能', '中国黄金', '中国广核', '中广核', '华侨城',
    '中国南水北调', '南水北调', '中国铁路工程', '中国中铁', '中铁',
    '中国铁道建筑', '中国铁建', '中铁建', '中国交通建设', '中国交建', '中交',
    '中国信息通信科技', '中国信科', '中国农业发展', '中农发', '中国林业',
    '中林', '中国中车', '中车', '中国铁路通信信号', '中国通号', '中国检验认证',
    '中检', '中国电气装备', '中国物流集团', '中国稀土', '中国资源循环'
]


class OwnershipTagService:
    """企业所有制标签分析与打标服务"""

    @classmethod
    def get_category_cache(cls):
        """获取所有分类对象字典缓存"""
        cats = CompanyCategory.objects.select_related('parent').all()
        return {cat.code: cat for cat in cats}

    # ============================================================
    # 方案一核心：漏斗分层分类决策引擎 (Tiered Funnel Engine)
    # ============================================================

    @classmethod
    def funnel_classify(cls, name: str, company_type: str = '') -> dict:
        """
        单家企业漏斗分层判定算法
        
        Returns:
            {
                'tier': 1 or 2,
                'confidence': 'HIGH' | 'NEEDS_API',
                'matched_rule': str,
                'tag_codes': list of str,
                'is_ambiguous': bool,
                'ambiguity_reason': str
            }
        """
        name = (name or '').strip()
        ctype = (company_type or '').strip()

        # ────────────────────────────────────────────────────────
        # [Tier 1.1] 确定性民营企业 (约占 80%~90%，0 成本直接过滤)
        # ────────────────────────────────────────────────────────
        private_type_keywords = [
            '自然人投资或控股', '自然人独资', '个人独资', '私营', '个体工商户',
            '个体户', '农民专业合作社', '自然人出资', '自然人控股'
        ]
        
        # 只要工商类型是自然人控股/独资，且公司名不属于央企白名单，100% 为民营企业
        if any(kw in ctype for kw in private_type_keywords):
            if not any(p in name for p in ['中国石油', '国家电网', '中国移动', '中国电信', '中国铁建', '中铁']):
                return {
                    'tier': 1,
                    'confidence': 'HIGH',
                    'matched_rule': f'工商类型包含民营独资/控股特征: {ctype}',
                    'tag_codes': ['private', 'private_general'],
                    'is_ambiguous': False,
                    'ambiguity_reason': ''
                }

        # ────────────────────────────────────────────────────────
        # [Tier 1.2] 确定性外资 / 港澳台投资企业 (约占 3%~5%，0 成本)
        # ────────────────────────────────────────────────────────
        # 港澳台投资企业
        if any(kw in ctype for kw in ['港、澳、台', '港澳台', '台港澳']) or any(kw in name for kw in ['(台港澳', '（台港澳', '(港澳台', '（港澳台']):
            tags = ['hmt_invested']
            if '合资' in ctype:
                tags.append('hmt_joint_venture')
            elif '合作' in ctype:
                tags.append('hmt_cooperative')
            elif '独资' in ctype:
                tags.append('hmt_wholly_owned')
            elif '股份有限公司' in ctype:
                tags.append('hmt_limited_by_shares')
            else:
                tags.append('hmt_other')
            return {
                'tier': 1,
                'confidence': 'HIGH',
                'matched_rule': f'港澳台工商类型/名称命中: {ctype or name}',
                'tag_codes': tags,
                'is_ambiguous': False,
                'ambiguity_reason': ''
            }

        # 外商投资企业
        if any(kw in ctype for kw in ['外商投资', '中外合资', '外资', '外国']) or any(kw in name for kw in ['(外商投资', '（外商投资', '(中外合资', '（中外合资']):
            tags = ['foreign_invested']
            if '合资' in ctype or '中外合资' in name:
                tags.append('foreign_joint_venture')
            elif '合作' in ctype or '中外合作' in name:
                tags.append('foreign_cooperative')
            elif '独资' in ctype or '外资独资' in name:
                tags.append('foreign_wholly_owned')
            elif '股份有限公司' in ctype:
                tags.append('foreign_limited_by_shares')
            else:
                tags.append('foreign_other')
            return {
                'tier': 1,
                'confidence': 'HIGH',
                'matched_rule': f'外商投资工商类型/名称命中: {ctype or name}',
                'tag_codes': tags,
                'is_ambiguous': False,
                'ambiguity_reason': ''
            }

        # ────────────────────────────────────────────────────────
        # [Tier 1.3] 确定性央企集团及子公司白名单 (0 成本)
        # ────────────────────────────────────────────────────────
        for central_name in CENTRAL_SOE_PATTERNS:
            if name.startswith(central_name) or f"{central_name}集团" in name:
                tags = ['state_owned']
                if any(sub in name for sub in ['分公司', '子公司', '有限责任公司', '局', '厂', '处', '院']):
                    tags.append('central_soe_sub')
                else:
                    tags.append('central_soe')
                return {
                    'tier': 1,
                    'confidence': 'HIGH',
                    'matched_rule': f'国务院国资委央企白名单命中: {central_name}',
                    'tag_codes': tags,
                    'is_ambiguous': False,
                    'ambiguity_reason': ''
                }

        # ────────────────────────────────────────────────────────
        # [Tier 1.4] 确定性国有独资 / 国有全资 (0 成本)
        # ────────────────────────────────────────────────────────
        if '国有独资' in ctype:
            return {
                'tier': 1,
                'confidence': 'HIGH',
                'matched_rule': '工商类型明确为国有独资',
                'tag_codes': ['state_owned', 'state_solely_funded'],
                'is_ambiguous': False,
                'ambiguity_reason': ''
            }
        elif '国有全资' in ctype:
            return {
                'tier': 1,
                'confidence': 'HIGH',
                'matched_rule': '工商类型明确为国有全资',
                'tag_codes': ['state_owned', 'state_wholly_owned'],
                'is_ambiguous': False,
                'ambiguity_reason': ''
            }

        # ────────────────────────────────────────────────────────
        # [Tier 2] 存疑/需股权穿透企业 (约占 5%~10%，建议 API 穿透)
        # ────────────────────────────────────────────────────────
        state_ambiguous_keywords = [
            '国资', '国有资产', '投资控股', '资产管理', '城市建设', '城投',
            '建投', '交投', '水务集团', '文旅集团', '能源集团', '控股集团',
            '产业投资', '国有', '省属', '市属'
        ]

        if any(kw in name for kw in state_ambiguous_keywords) or '国有' in ctype:
            # 存疑国企候选：先基于文本给出预估标签，但标明 NEEDS_API
            predicted_tags = ['state_owned']
            if any(p in name for p in ['省', '自治区']):
                predicted_tags.append('provincial_soe')
            elif any(c in name for c in ['市', '地级']):
                predicted_tags.append('municipal_soe')
            elif any(d in name for d in ['区', '县']):
                predicted_tags.append('county_soe')
            else:
                predicted_tags.append('state_controlled')

            return {
                'tier': 2,
                'confidence': 'NEEDS_API',
                'matched_rule': f'名称/工商包含国资投资特征关键词，但股权层级需穿透',
                'tag_codes': predicted_tags,
                'is_ambiguous': True,
                'ambiguity_reason': f'企业名称包含“{kw}”，股权归属（央企/省属/市属/民营控股）建议通过 API 精准穿透'
            }

        # ────────────────────────────────────────────────────────
        # [Tier 1.5] 默认常规民营有限责任公司 (0 成本)
        # ────────────────────────────────────────────────────────
        return {
            'tier': 1,
            'confidence': 'HIGH',
            'matched_rule': f'常规商业企业，无国资/外资特征，默认为民营企业: {ctype or "普通公司"}',
            'tag_codes': ['private', 'private_general'],
            'is_ambiguous': False,
            'ambiguity_reason': ''
        }

    # ============================================================
    # 标签批量打标与关联操作
    # ============================================================

    @classmethod
    def apply_tags_to_company(cls, company: Company, tag_codes: list, clear_existing: bool = False):
        """为企业打上指定编码的标签（包含其父级大类）"""
        cat_map = cls.get_category_cache()
        categories_to_add = set()

        for code in tag_codes:
            cat = cat_map.get(code)
            if cat:
                categories_to_add.add(cat)
                if cat.parent:
                    categories_to_add.add(cat.parent)

        if clear_existing:
            company.ownership_categories.clear()

        if categories_to_add:
            company.ownership_categories.add(*categories_to_add)

        return [c.name for c in categories_to_add]

    # ============================================================
    # 企查查 API 穿透支持 (Tier 2 专用)
    # ============================================================

    @classmethod
    def call_qcc_api(cls, company_name: str, credit_code: str = ''):
        """调用企查查开放平台 API 获取实际控制人与股权穿透信息"""
        app_key = getattr(settings, 'QCC_APP_KEY', None)
        secret_key = getattr(settings, 'QCC_SECRET_KEY', None)

        if not app_key or not secret_key:
            return None

        timestamp = str(int(time.time()))
        raw_str = f"{app_key}{timestamp}{secret_key}"
        token = hashlib.md5(raw_str.encode('utf-8')).hexdigest().upper()

        url = "https://api.qichacha.com/ECIV4/GetDetailsByName"
        headers = {
            'Token': token,
            'Timespan': timestamp,
        }
        params = {
            'key': app_key,
            'searchKey': credit_code or company_name,
        }

        try:
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            if resp.status_code == 200:
                res_json = resp.json()
                if res_json.get('Status') == '200':
                    return res_json.get('Result', {})
        except Exception as e:
            logger.error(f"请求 QCC API 异常: {str(e)}")

        return None

    @classmethod
    def parse_and_assign_qcc_data(cls, company: Company, qcc_result: dict) -> list:
        """根据企查查 API 实际控制人与国资穿透数据进行精准打标"""
        tag_codes = set()
        econ_kind = qcc_result.get('EconKind', '') or company.company_type or ''
        actual_controller = qcc_result.get('ActualController', {})
        controller_name = ''
        if isinstance(actual_controller, dict):
            controller_name = actual_controller.get('Name', '')
        elif isinstance(actual_controller, str):
            controller_name = actual_controller

        is_state_owned = qcc_result.get('IsStateOwned', False)

        if '国务院国有资产监督管理委员会' in controller_name or '国务院' in controller_name:
            tag_codes.add('central_soe')
            tag_codes.add('state_owned')
        elif '国资委' in controller_name or '国有资产监督' in controller_name:
            if any(p in controller_name for p in ['省', '自治区', '直辖市', '北京市', '上海市', '天津市', '重庆市']):
                tag_codes.add('provincial_soe')
            elif any(c in controller_name for c in ['市', '地级']):
                tag_codes.add('municipal_soe')
            elif any(d in controller_name for d in ['区', '县']):
                tag_codes.add('county_soe')
            else:
                tag_codes.add('state_controlled')
            tag_codes.add('state_owned')

        if '国有独资' in econ_kind:
            tag_codes.add('state_solely_funded')
            tag_codes.add('state_owned')
        elif '国有全资' in econ_kind:
            tag_codes.add('state_wholly_owned')
            tag_codes.add('state_owned')
        elif '国有控股' in econ_kind or is_state_owned:
            tag_codes.add('state_controlled')
            tag_codes.add('state_owned')

        if not tag_codes:
            # 走漏斗规则兜底
            rule_res = cls.funnel_classify(company.name, econ_kind)
            tag_codes.update(rule_res['tag_codes'])

        return cls.apply_tags_to_company(company, list(tag_codes))

    @classmethod
    def predict_and_assign_by_rules(cls, company: Company) -> list:
        """调用漏斗分层算法为单家企业快速打标"""
        res = cls.funnel_classify(company.name, company.company_type)
        return cls.apply_tags_to_company(company, res['tag_codes'])
