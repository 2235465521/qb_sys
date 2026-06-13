import re
from django.db.models import Q

def normalize_search_keyword(keyword: str) -> str:
    """
    对用户输入的搜索关键词进行极致的容错规范化。
    """
    if not keyword:
        return ""

    # 1. 全角转半角 (包括空格、英文、数字、符号)
    # 全角字符unicode编码从65281~65374 （十六进制 0xFF01 ~ 0xFF5E）
    # 半角字符unicode编码从33~126 （十六进制 0x21 ~ 0x7E）
    # 特例：全角空格 12288（0x3000） -> 半角空格 32（0x20）
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
    # 破折号统一为半角连字符
    normalized = re.sub(r'[—–－]', '-', normalized)
    # 中文逗号、句号替换
    normalized = normalized.replace('，', ',').replace('。', '.')
    # 括号替换（保险起见，即使全角转半角没覆盖全）
    normalized = normalized.replace('（', '(').replace('）', ')')
    normalized = normalized.replace('【', '[').replace('】', ']')
    normalized = normalized.replace('／', '/')

    # 3. 标准号常见拼写错误修复 (不区分大小写)
    # 例如：gbt 123 -> GB/T 123, jbt -> JB/T, dbt -> DB/T
    # 先统一转大写方便处理
    normalized = normalized.upper()
    
    def fix_standard_prefix(match):
        prefix = match.group(1)
        # 如果长度大于等于2且以T结尾，并且前面没有斜杠
        if len(prefix) >= 2 and prefix.endswith('T') and '/' not in prefix:
            return prefix[:-1] + '/T ' + match.group(2)
        return match.group(0)

    # 正则：匹配纯字母结尾带T的，后跟可选空格、可选短横线，后跟数字
    # 例如 GBT123, GBT 123, GBT-123
    normalized = re.sub(r'\b([A-Z]+T)[\s\-]*(\d+)', fix_standard_prefix, normalized)

    # 4. 空格压缩
    # 把首尾空格去掉，把连续多个空格压缩为一个空格
    normalized = re.sub(r'\s+', ' ', normalized).strip()

    return normalized


def build_smart_search_q(keyword: str, search_fields: list, clean_id_field: str = None) -> Q:
    """
    智能分词搜索：
    1. 规范化用户的输入
    2. 按空格切分为多个 token
    3. 对于每个 token，它必须匹配 search_fields 中的任意一个（OR）
    4. 所有的 tokens 必须全部匹配（AND）

    :param keyword: 用户的原始搜索词
    :param search_fields: 要进行 icontains 查询的字段列表 (例如 ['title', 'standard_no'])
    :param clean_id_field: (可选) 如果传入，会对该字段应用 generate_clean_id(token) 进行匹配
    :return: 组装好的 Django Q 对象
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
        for field in search_fields:
            token_q |= Q(**{f"{field}__icontains": token})
            
        if clean_id_field:
            # 对于标准号特殊处理，使用去除了空格的 clean_id 容错匹配
            clean_token = generate_clean_id(token)
            if clean_token:
                token_q |= Q(**{f"{clean_id_field}__icontains": clean_token})
                
        final_q &= token_q

    return final_q
