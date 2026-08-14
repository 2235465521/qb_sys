"""
companies.ownership_service — 企业所有制标签与分类智能识别服务

功能：
1. 企查查（QCC）股权穿透与实际控制人/企业性质 API 接入与精准打标
2. 本地智能特征规则引擎（兜底/离线批量初始化）
3. 分类标签映射与关联维护
"""

import re
import time
import hashlib
import logging
import requests
from django.conf import settings
from companies.models import Company, CompanyCategory

logger = logging.getLogger(__name__)


class OwnershipTagService:
    """企业所有制标签分析与打标服务"""

    @classmethod
    def get_category_cache(cls):
        """获取所有分类对象字典缓存"""
        cats = CompanyCategory.objects.select_related('parent').all()
        return {cat.code: cat for cat in cats}

    @classmethod
    def call_qcc_api(cls, company_name: str, credit_code: str = ''):
        """
        调用企查查（QCC）开放平台 API 获取企业精准画像与股权/实际控制人信息
        
        标准接口：企查查企业工商及股权穿透/企业类型高级接口
        """
        app_key = getattr(settings, 'QCC_APP_KEY', None)
        secret_key = getattr(settings, 'QCC_SECRET_KEY', None)

        if not app_key or not secret_key:
            logger.info("未配置 QCC_APP_KEY / QCC_SECRET_KEY，切换为本地高精度规则引擎分析。")
            return None

        # 企查查标准签名生成算法
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
                else:
                    logger.warning(f"QCC API 响应异常: {res_json.get('Message')}")
        except Exception as e:
            logger.error(f"请求 QCC API 失败: {str(e)}")

        return None

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

    @classmethod
    def parse_and_assign_qcc_data(cls, company: Company, qcc_result: dict) -> list:
        """
        根据企查查 API 返回的深度结构（含股权控制人、工商类型、国资背景标识等）精准打标
        """
        tag_codes = set()
        econ_kind = qcc_result.get('EconKind', '') or company.company_type or ''
        actual_controller = qcc_result.get('ActualController', {})
        controller_name = ''
        if isinstance(actual_controller, dict):
            controller_name = actual_controller.get('Name', '')
        elif isinstance(actual_controller, str):
            controller_name = actual_controller

        is_state_owned = qcc_result.get('IsStateOwned', False)
        belong_org = qcc_result.get('BelongOrg', '')

        # 1. 央企与各级国资判定
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

        # 2. 工商所有制类型判定
        if '国有独资' in econ_kind:
            tag_codes.add('state_solely_funded')
            tag_codes.add('state_owned')
        elif '国有全资' in econ_kind:
            tag_codes.add('state_wholly_owned')
            tag_codes.add('state_owned')
        elif '国有控股' in econ_kind or is_state_owned:
            tag_codes.add('state_controlled')
            tag_codes.add('state_owned')

        # 3. 港澳台投资企业
        if any(kw in econ_kind for kw in ['港、澳、台', '港澳台', '台港澳']):
            tag_codes.add('hmt_invested')
            if '合资' in econ_kind:
                tag_codes.add('hmt_joint_venture')
            elif '合作' in econ_kind:
                tag_codes.add('hmt_cooperative')
            elif '独资' in econ_kind:
                tag_codes.add('hmt_wholly_owned')
            elif '股份有限公司' in econ_kind:
                tag_codes.add('hmt_limited_by_shares')
            else:
                tag_codes.add('hmt_other')

        # 4. 外商投资企业
        elif any(kw in econ_kind for kw in ['外商投资', '中外合资', '外资', '外国']):
            tag_codes.add('foreign_invested')
            if '中外合资' in econ_kind or '合资经营' in econ_kind:
                tag_codes.add('foreign_joint_venture')
            elif '中外合作' in econ_kind or '合作经营' in econ_kind:
                tag_codes.add('foreign_cooperative')
            elif '独资' in econ_kind:
                tag_codes.add('foreign_wholly_owned')
            elif '股份有限公司' in econ_kind:
                tag_codes.add('foreign_limited_by_shares')
            else:
                tag_codes.add('foreign_other')

        # 5. 民营企业
        if not tag_codes:
            if any(kw in econ_kind for kw in ['私营', '自然人', '个人独资', '合伙企业', '有限责任公司(自然人投资或控股)']):
                tag_codes.add('private')
                tag_codes.add('private_general')

        return cls.apply_tags_to_company(company, list(tag_codes))

    @classmethod
    def predict_and_assign_by_rules(cls, company: Company) -> list:
        """
        基于多维文本特征的高精度规则打标引擎（离线/无 API 场景下的高保真推断）
        """
        tag_codes = set()
        name = company.name or ''
        company_type = company.company_type or ''

        # ── 1. 国有企业判定 ────────────────────────
        is_state = False

        # 央企与骨干国企特征库
        central_soe_patterns = [
            '中国石油', '中国石化', '国家电网', '南方电网', '中国华能', '中国大唐', '中国华电',
            '国家能源', '国家电投', '中国三峡', '中国电信', '中国联通', '中国移动', '中国电子',
            '中国一汽', '东风汽车', '中国宝武', '中国铝业', '中国中车', '中国船舶', '中国通号',
            '中国铁建', '中国中铁', '中国交建', '中国电建', '中国能建', '中国建筑', '中国航天',
            '中国航空', '中核', '中国核工业', '中粮集团', '招商局', '华润', '中国保利', '中钢集团'
        ]

        if any(name.startswith(p) or f"{p}集团" in name for p in central_soe_patterns):
            if '分公司' in name or '子公司' in name or '有限责任公司' in name:
                tag_codes.add('central_soe_sub')
            else:
                tag_codes.add('central_soe')
            is_state = True

        # 省属/市属国资特征
        if re.search(r'(省|市|自治区|直辖市)(国资|国有资产|投资控股|能源集团|交投集团|建投集团|水务集团|城投|文旅集团)', name):
            if any(p in name for p in ['省', '自治区']):
                tag_codes.add('provincial_soe')
            elif any(c in name for c in ['市', '地级']):
                tag_codes.add('municipal_soe')
            elif any(d in name for d in ['区', '县']):
                tag_codes.add('county_soe')
            else:
                tag_codes.add('state_controlled')
            is_state = True

        # 工商类型判定
        if '国有独资' in company_type:
            tag_codes.add('state_solely_funded')
            is_state = True
        elif '国有全资' in company_type:
            tag_codes.add('state_wholly_owned')
            is_state = True
        elif '国有控股' in company_type:
            tag_codes.add('state_controlled')
            is_state = True
        elif '国有' in company_type:
            tag_codes.add('state_controlled')
            is_state = True

        if is_state:
            tag_codes.add('state_owned')

        # ── 2. 港澳台投资企业判定 ──────────────────
        if any(kw in company_type for kw in ['港、澳、台', '港澳台', '台港澳']) or any(kw in name for kw in ['(台港澳', '（台港澳', '(港澳台', '（港澳台']):
            tag_codes.add('hmt_invested')
            if '合资' in company_type:
                tag_codes.add('hmt_joint_venture')
            elif '合作' in company_type:
                tag_codes.add('hmt_cooperative')
            elif '独资' in company_type:
                tag_codes.add('hmt_wholly_owned')
            elif '股份有限公司' in company_type:
                tag_codes.add('hmt_limited_by_shares')
            else:
                tag_codes.add('hmt_other')

        # ── 3. 外商投资企业判定 ────────────────────
        elif any(kw in company_type for kw in ['外商投资', '中外合资', '外资', '外国']) or any(kw in name for kw in ['(外商投资', '（外商投资', '(中外合资', '（中外合资']):
            tag_codes.add('foreign_invested')
            if '合资' in company_type or '中外合资' in name:
                tag_codes.add('foreign_joint_venture')
            elif '合作' in company_type or '中外合作' in name:
                tag_codes.add('foreign_cooperative')
            elif '独资' in company_type or '外资独资' in name:
                tag_codes.add('foreign_wholly_owned')
            elif '股份有限公司' in company_type:
                tag_codes.add('foreign_limited_by_shares')
            else:
                tag_codes.add('foreign_other')

        # ── 4. 民营企业判定 ────────────────────────
        if not tag_codes:
            tag_codes.add('private')
            tag_codes.add('private_general')

        return cls.apply_tags_to_company(company, list(tag_codes))
