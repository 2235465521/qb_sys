import re
import jieba
from django.db.models import Q, Case, When, Value, IntegerField

def normalize_search_keyword(keyword: str) -> str:
    """
    对用户输入的搜索关键词进行极致的容错规范化。
    """
    if not keyword:
        return ""

    # 1. 全角转半角 (包括空格、英文、数字、符号)
    def full_to_half(text):
        inside_code = []
        for char in text:
            code = ord(char)
            if code == 12288:
                code = 32
            elif 65281 <= code <= 65374:
                code -= 65248
            inside_code.append(chr(code))
        return ''.join(inside_code)

    normalized = full_to_half(keyword)

    # 2. 标点归一化
    normalized = re.sub(r'[—–－]', '-', normalized)
    normalized = normalized.replace('，', ',').replace('。', '.')
    normalized = normalized.replace('（', '(').replace('）', ')')
    normalized = normalized.replace('【', '[').replace('】', ']')
    normalized = normalized.replace('／', '/')

    # 3. 标准号常见拼写错误修复 (不区分大小写)
    normalized = normalized.upper()
    
    def fix_standard_prefix(match):
        prefix = match.group(1)
        if len(prefix) >= 2 and prefix.endswith('T') and '/' not in prefix:
            return prefix[:-1] + '/T ' + match.group(2)
        return match.group(0)

    normalized = re.sub(r'\b([A-Z]+T)[\s\-]*(\d+)', fix_standard_prefix, normalized)

    # 4. 空格压缩
    normalized = re.sub(r'\s+', ' ', normalized).strip()

    return normalized


# ============================================================
# 品类知识库与智能扩展规则
# ============================================================

CATEGORY_EXPANSION_RULES = [
    {
        'id': 'tea',
        'triggers': {'茶叶', '茶类', '茶制品', '茶饮品', '饮用茶', '茶叶类'},
        'include_terms': [
            '茶叶', '绿茶', '红茶', '乌龙茶', '白茶', '黑茶', '黄茶', '普洱茶',
            '代用茶', '调味茶', '袋泡茶', '花茶', '紧压茶', '抹茶', '茶饮料',
            '养生茶', '凉茶', '奶茶', '速溶茶', '茶粉', '茶浓缩液', '茶制代烟', '茶'
        ],
        'exclude_terms': [
            '茶几', '茶具', '茶壶', '茶杯', '茶盘', '茶台', '茶桌', '茶椅', '茶柜',
            '茶洗', '茶垫', '茶夹', '茶则', '茶海', '茶宠', '茶船', '茶刀',
            '茶油', '山茶油', '油茶', '茶籽', '茶树精油', '茶粕', '茶皂素', '茶多酚饲料',
            '山茶花', '油茶树'
        ],
        'company_include_terms': ['茶业', '茶叶', '茶厂', '茶行']
    },
    {
        'id': 'liquor',
        'triggers': {'酒类', '酒品', '饮用酒', '酒制品', '酒饮料'},
        'include_terms': [
            '白酒', '啤酒', '黄酒', '葡萄酒', '配制酒', '露酒', '米酒', '果酒',
            '青稞酒', '药酒', '清酒', '白兰地', '威士忌', '伏特加', '朗姆酒', '酒'
        ],
        'exclude_terms': [
            '酒精', '医用酒精', '消毒酒精', '工业酒精', '酒石酸', '酒糟饲料', '酒曲',
            '酿酒设备', '酒柜', '酒具', '醒酒器', '开瓶器', '酒架'
        ],
        'company_include_terms': ['酒业', '酒厂', '酿酒']
    },
    {
        'id': 'edible_oil',
        'triggers': {'食用油', '植物油', '食用植物油', '粮油', '食用油脂'},
        'include_terms': [
            '食用油', '植物油', '菜籽油', '大豆油', '花生油', '玉米油', '葵花籽油',
            '芝麻油', '香油', '茶油', '山茶油', '橄榄油', '亚麻籽油', '调和油',
            '米糠油', '核桃油', '棉籽油', '棕榈油', '食用猪油', '牛油'
        ],
        'exclude_terms': [
            '机油', '润滑油', '柴油', '汽油', '工业用油', '变压器油', '导热油',
            '防锈油', '精油', '基础油', '压榨机', '滤油机', '储油罐'
        ],
        'company_include_terms': ['油脂', '粮油']
    },
    {
        'id': 'fertilizer',
        'triggers': {'肥料', '化肥', '农肥'},
        'include_terms': [
            '肥料', '水溶肥', '水溶肥料', '有机肥', '有机肥料', '复合肥', '复混肥料',
            '复合肥料', '叶面肥', '叶面肥料', '微生物肥料', '菌肥', '生物有机肥',
            '掺混肥料', '氮肥', '磷肥', '钾肥', '缓控释肥料', '土壤调理剂'
        ],
        'exclude_terms': ['施肥机', '造粒机', '肥料包装', '造粒'],
        'company_include_terms': ['肥料', '化肥']
    },
    {
        'id': 'pesticide',
        'triggers': {'农药', '植保品'},
        'include_terms': [
            '农药', '杀虫剂', '除草剂', '杀菌剂', '杀螨剂', '植物生长调节剂',
            '悬浮剂', '乳油', '水剂', '可湿性粉剂', '微乳剂', '水分散粒剂'
        ],
        'exclude_terms': ['喷雾器', '施药机', '农药残留检测'],
        'company_include_terms': ['农药', '植保']
    },
    {
        'id': 'beverage',
        'triggers': {'饮料', '饮品'},
        'include_terms': [
            '饮料', '果汁', '果蔬汁', '碳酸饮料', '茶饮料', '凉茶', '植物饮料',
            '固体饮料', '能量饮料', '蛋白饮料', '风味饮料', '饮用水', '矿泉水',
            '苏打水', '乳酸菌饮料', '奶茶饮料'
        ],
        'exclude_terms': ['饮料机械', '灌装机', '饮料瓶', '售货机'],
        'company_include_terms': ['饮料', '饮品']
    },
    {
        'id': 'dairy',
        'triggers': {'乳制品', '奶制品', '乳品'},
        'include_terms': [
            '牛奶', '酸奶', '鲜奶', '发酵乳', '调制乳', '灭菌乳', '巴氏杀菌乳',
            '奶粉', '炼乳', '奶油', '黄油', '奶酪', '干酪', '乳清粉', '乳制品'
        ],
        'exclude_terms': ['挤奶机', '奶瓶', '储奶罐'],
        'company_include_terms': ['乳业', '奶业', '乳制品']
    },
    {
        'id': 'condiment',
        'triggers': {'调味品', '调料', '佐料'},
        'include_terms': [
            '调味品', '酱油', '食醋', '醋', '味精', '鸡精', '料酒', '调味酱',
            '番茄酱', '辣椒酱', '火锅底料', '复合调味料', '香辛料', '食用盐'
        ],
        'exclude_terms': ['调料盒', '调味瓶', '包装机'],
        'company_include_terms': ['调味品', '调味']
    },
    {
        'id': 'furniture',
        'triggers': {'家具', '办公家具', '民用家具'},
        'include_terms': [
            '家具', '床', '沙发', '桌', '椅', '几', '茶几', '衣柜', '书柜',
            '储物柜', '橱柜', '办公桌', '升降桌'
        ],
        'exclude_terms': ['家具五金', '家具漆', '木工胶'],
        'company_include_terms': ['家具', '家居']
    }
]

def find_matched_category_rule(token: str):
    """匹配 token 是否对应品类规则"""
    if not token:
        return None
    token_clean = token.strip()
    for rule in CATEGORY_EXPANSION_RULES:
        if token_clean in rule['triggers'] or token_clean == rule['id']:
            return rule
    return None


# 停用通用词，分词时忽略
STOP_WORDS = {
    '的', '和', '与', '及', '等', '之', '用', '为', '由', '向',
    '标准', '规范', '技术', '要求', '规程', '指南', '通则', '产品',
    '企业标准', '企标', '系列', '部分', '通用'
}

def extract_core_keywords(token: str) -> list:
    """提取实词核心词根"""
    if not token:
        return []
    words = jieba.lcut(token)
    cleaned = [w.strip() for w in words if len(w.strip()) > 1 and w.strip() not in STOP_WORDS]
    return cleaned


def build_smart_search_q(keyword: str, search_fields: list, clean_id_field: str = None) -> Q:
    """
    智能分词与品类扩展模糊搜索：
    1. 规范化用户的输入；
    2. 按空格切分为多个 token；
    3. 若 token 命中品类词典（如“茶叶”）：
       - 正向扩展匹配同义词及所有子品类词（绿茶、红茶、代用茶、调味茶、茶饮料等）；
       - 结合起草单位名称进行涉茶企业关联识别；
       - 负向严格剔除跨品类干扰项（如茶几、茶具、茶油等）；
    4. 若 token 为未命中的普通词语：
       - 进行字面容错与 clean_id 匹配；
       - 若长度大于等于3，支持 jieba 分词后核心实词 AND 召回；
    5. 各 token 之间保持 AND 约束。
    """
    if not keyword:
        return Q()

    normalized = normalize_search_keyword(keyword)
    if not normalized:
        return Q()

    tokens = normalized.split()
    final_q = Q()

    from standards.services import generate_clean_id

    for token in tokens:
        token_q = Q()
        cat_rule = find_matched_category_rule(token)

        if cat_rule:
            # 命中品类规则，执行品类正向扩展与负向噪音剔除
            cat_pos_q = Q()
            for inc in cat_rule['include_terms']:
                cat_pos_q |= Q(title__icontains=inc)
            
            # 起草单位关联匹配
            company_terms = cat_rule.get('company_include_terms', [])
            for c_term in company_terms:
                cat_pos_q |= Q(company__name__icontains=c_term)

            # 跨品类噪音剔除
            cat_neg_q = Q()
            for exc in cat_rule['exclude_terms']:
                cat_neg_q |= Q(title__icontains=exc)

            token_q = cat_pos_q & ~cat_neg_q
        else:
            # 普通词：字面匹配 + 标准号 clean_id 匹配
            literal_q = Q()
            for field in search_fields:
                literal_q |= Q(**{f"{field}__icontains": token})

            if clean_id_field:
                clean_token = generate_clean_id(token)
                if clean_token:
                    literal_q |= Q(**{f"{clean_id_field}__icontains": clean_token})

            # 支持核心实词分词容错（当字面未连续时依然能命中，如"灵芝固体饮料"）
            sub_words = extract_core_keywords(token)
            if len(sub_words) > 1:
                sub_q = Q()
                for sw in sub_words:
                    sub_q &= Q(title__icontains=sw)
                literal_q |= sub_q

            token_q = literal_q

        final_q &= token_q

    return final_q


def build_relevance_annotation(keyword: str):
    """
    构建相关性打分表达式，供模糊检索结果优先排序：
    - 完整字面包含原始搜索词：得 100 分
    - 标题包含核心触发词：得 60 分
    - 标题包含品类扩展词：得 30 分
    - 起草单位命中：得 10 分
    """
    if not keyword:
        return Value(0, output_field=IntegerField())

    normalized = normalize_search_keyword(keyword)
    cat_rule = find_matched_category_rule(normalized)

    whens = [
        When(title__icontains=keyword, then=Value(100)),
        When(standard_no__icontains=keyword, then=Value(90)),
    ]

    if cat_rule:
        for t in cat_rule['triggers']:
            whens.append(When(title__icontains=t, then=Value(80)))
        # 常见细分品类优先赋分
        for inc in cat_rule['include_terms'][:10]:
            whens.append(When(title__icontains=inc, then=Value(50)))
        whens.append(When(title__icontains=cat_rule['include_terms'][-1], then=Value(30)))
        for c_term in cat_rule.get('company_include_terms', []):
            whens.append(When(company__name__icontains=c_term, then=Value(15)))
    else:
        sub_words = extract_core_keywords(normalized)
        if len(sub_words) > 1:
            all_sub = Q()
            for sw in sub_words:
                all_sub &= Q(title__icontains=sw)
            whens.append(When(all_sub, then=Value(40)))

    return Case(*whens, default=Value(0), output_field=IntegerField())
