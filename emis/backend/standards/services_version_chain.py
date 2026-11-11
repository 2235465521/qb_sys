"""
standards.services_version_chain — 标准版本链（all_chain / part_chain）补全与校验服务

核心规则：
1. 仅从 standard_no 解析主体与版本年份，不修改数据库中的 standard_no、id 或其他业务字段。
2. all_chain：同组全部记录 ID，按标准年份从新到旧排列；组内每条记录写入相同数组。
3. part_chain：[当前记录ID, 紧邻的更旧版本ID]；最旧版本或单条记录填 [自身ID]。
4. 异常拦截：编号缺失/无法解析年份、格式异常、同组同年份重复、企业归属不明确、
   年份字段冲突或组内存在疑似异常兄弟记录时，暂停更新该组并保留原有字段。
5. 事务保障：每组更新在独立事务中执行，仅更新与原值不同的记录，并保存修改前后审计日志以支持回滚。
"""

from __future__ import annotations

import datetime
import difflib
import json
import os
import re
import threading
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Optional

from django.conf import settings
from django.db import transaction
from django.db.models import Q

from standards.models import Standard

_chain_sync_local = threading.local()


@contextmanager
def suppress_version_chain_signals():
    """在批量导入或内部回写期间临时屏蔽信号触发，防止重复全组计算或递归。"""
    depth = getattr(_chain_sync_local, 'suppress_depth', 0)
    _chain_sync_local.suppress_depth = depth + 1
    try:
        yield
    finally:
        _chain_sync_local.suppress_depth = max(0, getattr(_chain_sync_local, 'suppress_depth', 1) - 1)


def is_version_chain_signals_suppressed() -> bool:
    return getattr(_chain_sync_local, 'suppress_depth', 0) > 0

MIN_VALID_YEAR = 1949
DASH_CHARS_PATTERN = re.compile(r'[—–－―−]')
MULTI_SPACE_PATTERN = re.compile(r'\s+')
TRAILING_YEAR_PATTERN = re.compile(r'^(.*?)\s*(-+)\s*(\d{4})\s*$')
DOUBLE_YEAR_SUFFIX_PATTERN = re.compile(r'-(?:19|20)\d{2}$')
EMBEDDED_YEAR_SPACE_PATTERN = re.compile(r'[-/](?:19|20)\d{2}\s+')
DOUBLE_Q_PREFIX_PATTERN = re.compile(r'^(?:Q/)+Q/', re.IGNORECASE)
ENTERPRISE_PREFIX_PATTERN = re.compile(r'^(?:[\u4e00-\u9fff]?Q)/', re.IGNORECASE)
COMPANY_SPLIT_PATTERN = re.compile(r'[、,，;；/]+')
COMPANY_PAREN_PATTERN = re.compile(r'[()（）\s]+')


def get_max_valid_year() -> int:
    """允许的最大合法标准年份（当前年份 + 2）。"""
    return datetime.date.today().year + 2


def full_to_half(text: str) -> str:
    """将全角字符（含全角空格）转换为半角字符，不改变汉字和标点语义。"""
    chars = []
    for ch in text:
        code = ord(ch)
        if code == 12288:
            code = 32
        elif 65281 <= code <= 65374:
            code -= 65248
        chars.append(chr(code))
    return ''.join(chars)


def normalize_standard_text(text: str) -> str:
    """对标准编号做只读规范化：全角转半角、统一连接符和斜杠、压缩空格。"""
    if not text:
        return ''
    s = full_to_half(str(text)).strip()
    s = DASH_CHARS_PATTERN.sub('-', s)
    s = s.replace('／', '/')
    s = MULTI_SPACE_PATTERN.sub(' ', s)
    return s


def normalize_body_key(body: str) -> str:
    """将标准编号主体归一化为用于精准分组的紧凑键（保留类别/斜杠/点号/前导零/连字符）。"""
    norm = normalize_standard_text(body)
    return MULTI_SPACE_PATTERN.sub('', norm).upper()


def _extract_suspected_compact_body(raw_body: str, error_code: str) -> Optional[str]:
    """针对可识别的格式缺陷（如重复年份后缀、重复 Q/ 前缀），提取疑似主体键以保护同组完整性。"""
    candidate = normalize_standard_text(raw_body)
    if error_code == 'DOUBLE_YEAR_SUFFIX':
        candidate = DOUBLE_YEAR_SUFFIX_PATTERN.sub('', candidate).strip()
    if DOUBLE_Q_PREFIX_PATTERN.match(candidate):
        candidate = re.sub(r'^(?:Q/)+', 'Q/', candidate, flags=re.IGNORECASE)
    if '//' in candidate:
        candidate = re.sub(r'/+', '/', candidate)
    compact = normalize_body_key(candidate)
    return compact or None


@dataclass(frozen=True, slots=True)
class ParsedStandardNo:
    raw: str
    normalized_body: Optional[str]
    compact_body: Optional[str]
    year: Optional[int]
    suspected_compact_body: Optional[str] = None
    error_code: Optional[str] = None
    error_detail: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        return self.error_code is None and self.compact_body is not None and self.year is not None


def parse_standard_no(raw_standard_no: Optional[str], max_year: Optional[int] = None) -> ParsedStandardNo:
    """
    从原始 standard_no 解析标准编号主体与版本年份。
    不合法或不可靠的格式返回 error_code 与原因，绝不盲目截取末尾四位数字。
    """
    raw = '' if raw_standard_no is None else str(raw_standard_no)
    norm = normalize_standard_text(raw)
    if not norm:
        return ParsedStandardNo(
            raw=raw,
            normalized_body=None,
            compact_body=None,
            year=None,
            error_code='EMPTY_STANDARD_NO',
            error_detail='标准编号为空',
        )

    match = TRAILING_YEAR_PATTERN.match(norm)
    if not match:
        return ParsedStandardNo(
            raw=raw,
            normalized_body=None,
            compact_body=None,
            year=None,
            error_code='NO_TRAILING_YEAR',
            error_detail='标准编号末尾缺少“分隔符+4位年份”，无法可靠识别版本年份',
        )

    body_raw = match.group(1).strip()
    year = int(match.group(3))
    upper_year = max_year if max_year is not None else get_max_valid_year()

    if not (MIN_VALID_YEAR <= year <= upper_year):
        return ParsedStandardNo(
            raw=raw,
            normalized_body=None,
            compact_body=None,
            year=None,
            error_code='YEAR_OUT_OF_RANGE',
            error_detail=f'末尾数字 {year} 超出合法标准年份范围 ({MIN_VALID_YEAR}~{upper_year})',
        )

    if not body_raw:
        return ParsedStandardNo(
            raw=raw,
            normalized_body=None,
            compact_body=None,
            year=None,
            error_code='EMPTY_BODY',
            error_detail='去除年份后标准编号主体为空',
        )

    if DOUBLE_YEAR_SUFFIX_PATTERN.search(body_raw):
        suspected = _extract_suspected_compact_body(body_raw, 'DOUBLE_YEAR_SUFFIX')
        return ParsedStandardNo(
            raw=raw,
            normalized_body=None,
            compact_body=None,
            year=None,
            suspected_compact_body=suspected,
            error_code='DOUBLE_YEAR_SUFFIX',
            error_detail=f'标准编号存在疑似重复年份后缀: {raw}',
        )

    if EMBEDDED_YEAR_SPACE_PATTERN.search(body_raw):
        return ParsedStandardNo(
            raw=raw,
            normalized_body=None,
            compact_body=None,
            year=None,
            error_code='EMBEDDED_TITLE_OR_YEAR',
            error_detail=f'标准编号主体中混入年份与描述文本: {raw}',
        )

    if body_raw[-1] in '.,/:-':
        return ParsedStandardNo(
            raw=raw,
            normalized_body=None,
            compact_body=None,
            year=None,
            error_code='TRAILING_PUNCTUATION_IN_BODY',
            error_detail=f'标准编号主体末尾含非法标点符号: {raw}',
        )

    if '//' in body_raw or DOUBLE_Q_PREFIX_PATTERN.match(body_raw):
        suspected = _extract_suspected_compact_body(body_raw, 'MALFORMED_PREFIX')
        return ParsedStandardNo(
            raw=raw,
            normalized_body=None,
            compact_body=None,
            year=None,
            suspected_compact_body=suspected,
            error_code='MALFORMED_PREFIX',
            error_detail=f'标准编号前缀格式异常（包含重复斜杠或重复 Q/）: {raw}',
        )

    compact_body = normalize_body_key(body_raw)
    return ParsedStandardNo(
        raw=raw,
        normalized_body=body_raw,
        compact_body=compact_body,
        year=year,
    )


def _split_company_units(company_name: Optional[str]) -> list[str]:
    """拆分联合起草企业名称并归一化，用于识别同号跨企业 ID 的归属歧义。"""
    if not company_name:
        return []
    parts = []
    for seg in COMPANY_SPLIT_PATTERN.split(full_to_half(company_name)):
        cleaned = COMPANY_PAREN_PATTERN.sub('', seg).strip()
        if cleaned:
            parts.append(cleaned)
    return parts


def _are_companies_ambiguous(name_a: Optional[str], name_b: Optional[str]) -> bool:
    """
    判断两个关联企业名是否可能指向同一主体或联合发布主体：
    1. 联合名称中包含完全相同的企业成员；
    2. 两个名称高度相似（如错别字“碧诚”vs“碧城”、更名“飞华环保”vs“飞华环保器材”）。
    """
    units_a = _split_company_units(name_a)
    units_b = _split_company_units(name_b)
    if not units_a or not units_b:
        return False

    for ua in units_a:
        for ub in units_b:
            if ua == ub:
                return True
            if min(len(ua), len(ub)) >= 5:
                ratio = difflib.SequenceMatcher(None, ua, ub).ratio()
                if ratio >= 0.85:
                    return True
    return False


def _is_enterprise_record(std_type: str, compact_body: str) -> bool:
    return std_type == 'enterprise' or bool(ENTERPRISE_PREFIX_PATTERN.match(compact_body))


def _is_strict_int_list(value) -> bool:
    return type(value) is list and all(type(item) is int for item in value)


@dataclass(slots=True)
class StandardRow:
    id: int
    standard_no: str
    type: str
    company_id: Optional[int]
    company_name: Optional[str]
    publish_date: Optional[datetime.date]
    all_chain: object
    part_chain: object
    title: str = ''
    explicit_year: Optional[int] = None


@dataclass(slots=True)
class PlannedChange:
    id: int
    standard_no: str
    group_key: str
    group_label: str
    year: Optional[int]
    company_id: Optional[int]
    company_name: Optional[str]
    old_all_chain: object
    new_all_chain: list[int]
    old_part_chain: object
    new_part_chain: list[int]
    change_type: str = 'chain'


@dataclass(slots=True)
class AnomalyRecord:
    id: int
    standard_no: str
    group_key: Optional[str]
    group_label: Optional[str]
    company_id: Optional[int]
    company_name: Optional[str]
    reason_code: str
    reason_detail: str


@dataclass
class VersionChainRunResult:
    mode: str
    scope: str
    total_scanned: int = 0
    total_groups: int = 0
    valid_groups: int = 0
    paused_groups_count: int = 0
    unchanged_count: int = 0
    planned_changes_count: int = 0
    applied_count: int = 0
    anomalies_count: int = 0
    missing_ids: list[int] = field(default_factory=list)
    changes: list[PlannedChange] = field(default_factory=list)
    anomalies: list[AnomalyRecord] = field(default_factory=list)
    report_files: dict[str, str] = field(default_factory=dict)

    def to_audit_dict(self) -> dict:
        return {
            'generated_at': datetime.datetime.now().isoformat(timespec='seconds'),
            'mode': self.mode,
            'scope': self.scope,
            'stats': {
                'total_scanned': self.total_scanned,
                'total_groups': self.total_groups,
                'valid_groups': self.valid_groups,
                'paused_groups_count': self.paused_groups_count,
                'unchanged_count': self.unchanged_count,
                'planned_changes_count': self.planned_changes_count,
                'applied_count': self.applied_count,
                'anomalies_count': self.anomalies_count,
                'missing_ids': self.missing_ids,
            },
            'changes': [asdict(c) for c in self.changes],
            'anomalies': [asdict(a) for a in self.anomalies],
        }


_ROW_FIELDS = (
    'id',
    'standard_no',
    'type',
    'company_id',
    'company__name',
    'publish_date',
    'all_chain',
    'part_chain',
)


def _rows_from_values_qs(qs, chunk_size: int = 10000) -> list[StandardRow]:
    return [
        StandardRow(
            id=row[0],
            standard_no=row[1],
            type=row[2],
            company_id=row[3],
            company_name=row[4],
            publish_date=row[5],
            all_chain=row[6],
            part_chain=row[7],
        )
        for row in qs.iterator(chunk_size=chunk_size)
    ]


def _fetch_all_rows(chunk_size: int = 10000) -> list[StandardRow]:
    qs = Standard.objects.select_related('company').order_by('id').values_list(*_ROW_FIELDS)
    return _rows_from_values_qs(qs, chunk_size=chunk_size)


def _half_to_full_ascii(text: str) -> str:
    chars = []
    for ch in text:
        code = ord(ch)
        if ch == ' ':
            chars.append('\u3000')
        elif 33 <= code <= 126:
            chars.append(chr(code + 65248))
        else:
            chars.append(ch)
    return ''.join(chars)


def _build_body_prefixes(compact_body: str) -> set[str]:
    """为单个 compact_body 生成用于命中索引的前缀变体（含空格、全角及重复 Q/ 畸形前缀）。"""
    prefixes: set[str] = set()
    if not compact_body:
        return prefixes

    if '/' in compact_body:
        head, tail = compact_body.split('/', 1)
        m_alpha = re.match(r'^([A-Za-z]{2,4})', tail)
        if m_alpha:
            anchor = m_alpha.group(1)
            anchors = {anchor}
        elif tail and tail[0].isalpha():
            anchors = {f'{tail[0]} ', f'{tail[0]}-', tail[:2]}
        else:
            anchors = {tail[:3]}

        base_variants: set[str] = set()
        for anc in anchors:
            if not anc:
                continue
            base_variants.update({
                f'{head}/{anc}',
                f'{head}/ {anc}',
                f'{head}//{anc}',
                f'{head}／{anc}',
            })
            if head.upper() == 'Q':
                base_variants.add(f'Q/Q/{anc}')
        if len(tail) >= 2:
            base_variants.add(f'{head}/{tail[0]} {tail[1:2]}')
        if len(tail) >= 3:
            base_variants.add(f'{head}/{tail[:2]} {tail[2:3]}')
    else:
        anchor = compact_body[:4]
        base_variants = {anchor}

    for v in base_variants:
        if v:
            prefixes.add(v)
            prefixes.add(_half_to_full_ascii(v))
    return prefixes


def _fetch_rows_for_scope(
    *,
    target_bodies: Optional[Iterable[str]] = None,
    target_ids: Optional[Iterable[int]] = None,
    extra_bodies: Optional[Iterable[str]] = None,
) -> list[StandardRow]:
    """
    智能按作用域拉取候选行：
    - 全量模式：流式拉取全表最小列集合；
    - 局部模式（≤30 个标准主体）：利用 standard_no / clean_id / company_id 索引范围查询，毫秒级返回。
    """
    if target_bodies is None and target_ids is None and extra_bodies is None:
        return _fetch_all_rows()

    norm_bodies: set[str] = set()
    if target_bodies:
        norm_bodies.update(normalize_body_key(b) for b in target_bodies if b)
    if extra_bodies:
        norm_bodies.update(normalize_body_key(b) for b in extra_bodies if b)

    seed_rows: list[StandardRow] = []
    seed_company_ids: set[int] = set()
    if target_ids is not None:
        id_list = [int(i) for i in target_ids]
        if id_list:
            seed_qs = Standard.objects.select_related('company').filter(id__in=id_list).values_list(*_ROW_FIELDS)
            seed_rows = _rows_from_values_qs(seed_qs, chunk_size=2000)
            for r in seed_rows:
                if r.company_id is not None:
                    seed_company_ids.add(r.company_id)
            norm_bodies.update(extract_affected_bodies(r.standard_no for r in seed_rows))

    if not norm_bodies:
        return seed_rows

    if len(norm_bodies) > 30:
        return _fetch_all_rows()

    q_filter = Q()
    if seed_company_ids:
        q_filter |= Q(company_id__in=seed_company_ids)
    if target_ids is not None:
        q_filter |= Q(id__in=[int(i) for i in target_ids])

    prefixes: set[str] = set()
    for body in norm_bodies:
        prefixes.update(_build_body_prefixes(body))

    for p in prefixes:
        q_filter |= Q(standard_no__istartswith=p) | Q(clean_id__istartswith=p)

    qs = Standard.objects.select_related('company').filter(q_filter).order_by('id').values_list(*_ROW_FIELDS)
    return _rows_from_values_qs(qs, chunk_size=5000)


def _format_group_key(std_type: str, compact_body: str, company_id: Optional[int]) -> str:
    return f'{std_type}|{compact_body}|{company_id if company_id is not None else "NONE"}'


def _format_group_label(std_type: str, compact_body: str, company_id: Optional[int], company_name: Optional[str]) -> str:
    if company_id is not None:
        return f'{compact_body} (type={std_type}, company_id={company_id}, {company_name or ""})'
    return f'{compact_body} (type={std_type})'


def _verify_chain_invariants(all_chain: list[int], part_chain: list[int], record_id: int) -> None:
    if len(all_chain) != len(set(all_chain)):
        raise ValueError(f'all_chain contains duplicate IDs for record {record_id}: {all_chain}')
    if len(part_chain) != len(set(part_chain)):
        raise ValueError(f'part_chain contains duplicate IDs for record {record_id}: {part_chain}')
    if record_id not in all_chain:
        raise ValueError(f'record {record_id} missing from its own all_chain: {all_chain}')
    if not part_chain or part_chain[0] != record_id:
        raise ValueError(f'part_chain must start with self id {record_id}: {part_chain}')


def _plan_fallback_self_if_empty(
    r: StandardRow,
    *,
    group_key: str,
    group_label: str,
    year: Optional[int],
    result: VersionChainRunResult,
    grouped_changes: list[tuple[str, list[PlannedChange]]],
) -> None:
    """
    若记录未找到有效版本组或存在异常暂停且当前 all_chain 为空，
    则默认在 all_chain 中填入自身 ID；若已有非空 all_chain，则严格保留原值。
    """
    if _is_strict_int_list(r.all_chain) and len(r.all_chain) > 0:
        result.unchanged_count += 1
        return

    kept_part = r.part_chain if _is_strict_int_list(r.part_chain) else []
    change = PlannedChange(
        id=r.id,
        standard_no=r.standard_no,
        group_key=group_key,
        group_label=group_label,
        year=year,
        company_id=r.company_id,
        company_name=r.company_name,
        old_all_chain=r.all_chain,
        new_all_chain=[r.id],
        old_part_chain=r.part_chain,
        new_part_chain=list(kept_part),
        change_type='fallback_self',
    )
    result.changes.append(change)
    grouped_changes.append((group_key, [change]))


def compute_version_chains(
    rows: list[StandardRow],
    *,
    target_bodies: Optional[Iterable[str]] = None,
    target_ids: Optional[Iterable[int]] = None,
    extra_bodies: Optional[Iterable[str]] = None,
) -> tuple[list[tuple[str, list[PlannedChange]]], VersionChainRunResult]:
    """
    纯计算函数：基于全量候选记录构建分组、检测异常、计算版本链并过滤作用域。
    返回 (grouped_changes, result)，其中 grouped_changes 按组打包以便按组事务更新。
    """
    norm_target_bodies = {normalize_body_key(b) for b in target_bodies if b} if target_bodies else None
    norm_extra_bodies = {normalize_body_key(b) for b in extra_bodies if b} if extra_bodies else None
    target_id_set = {int(i) for i in target_ids} if target_ids is not None else None

    if target_id_set is not None and norm_target_bodies is not None:
        scope_desc = f'bodies={sorted(norm_target_bodies)},ids={sorted(target_id_set)}'
    elif target_id_set is not None and norm_extra_bodies is not None:
        scope_desc = f'ids={sorted(target_id_set)},extra_bodies={sorted(norm_extra_bodies)}'
    elif target_id_set is not None:
        scope_desc = f'ids={sorted(target_id_set)}'
    elif norm_target_bodies is not None:
        scope_desc = f'bodies={sorted(norm_target_bodies)}'
    elif norm_extra_bodies is not None:
        scope_desc = f'extra_bodies={sorted(norm_extra_bodies)}'
    else:
        scope_desc = 'all'

    result = VersionChainRunResult(mode='dry_run', scope=scope_desc, total_scanned=len(rows))

    row_by_id = {r.id: r for r in rows}
    if target_id_set is not None:
        result.missing_ids = sorted(i for i in target_id_set if i not in row_by_id)

    parsed_map: dict[int, ParsedStandardNo] = {}
    suspected_malformed_bodies: dict[tuple[str, str, Optional[int]], list[StandardRow]] = defaultdict(list)
    suspected_malformed_any_company: dict[tuple[str, str], list[StandardRow]] = defaultdict(list)

    for r in rows:
        parsed = parse_standard_no(r.standard_no)
        parsed_map[r.id] = parsed
        if not parsed.is_valid and parsed.suspected_compact_body:
            suspected_malformed_bodies[(r.type, parsed.suspected_compact_body, r.company_id)].append(r)
            suspected_malformed_any_company[(r.type, parsed.suspected_compact_body)].append(r)

    # 若按 ID 过滤，先扩展到目标 ID 所在标准编号主体（及疑似主体）
    expanded_bodies: Optional[set[str]] = None
    if target_id_set is not None:
        expanded_bodies = set()
        for tid in target_id_set:
            row = row_by_id.get(tid)
            if not row:
                continue
            p = parsed_map[tid]
            if p.compact_body:
                expanded_bodies.add(p.compact_body)
            elif p.suspected_compact_body:
                expanded_bodies.add(p.suspected_compact_body)

    has_any_filter = (
        norm_target_bodies is not None
        or target_id_set is not None
        or norm_extra_bodies is not None
    )

    unattributed_bodies: dict[tuple[str, str], list[StandardRow]] = defaultdict(list)
    by_type_body: dict[tuple[str, str], list[tuple[StandardRow, ParsedStandardNo]]] = defaultdict(list)
    grouped_changes: list[tuple[str, list[PlannedChange]]] = []

    for r in rows:
        parsed = parsed_map[r.id]
        if not parsed.is_valid:
            in_scope = False
            if not has_any_filter:
                in_scope = True
            else:
                if target_id_set is not None and r.id in target_id_set:
                    in_scope = True
                if norm_target_bodies is not None and parsed.suspected_compact_body in norm_target_bodies:
                    in_scope = True
                if expanded_bodies is not None and parsed.suspected_compact_body in expanded_bodies:
                    in_scope = True
                if norm_extra_bodies is not None and parsed.suspected_compact_body in norm_extra_bodies:
                    in_scope = True

            if in_scope:
                result.anomalies.append(
                    AnomalyRecord(
                        id=r.id,
                        standard_no=r.standard_no,
                        group_key=None,
                        group_label=parsed.suspected_compact_body,
                        company_id=r.company_id,
                        company_name=r.company_name,
                        reason_code=parsed.error_code or 'PARSE_ERROR',
                        reason_detail=parsed.error_detail or '标准编号解析失败',
                    )
                )
                _plan_fallback_self_if_empty(
                    r,
                    group_key=f'FALLBACK|{r.id}',
                    group_label=parsed.suspected_compact_body or f'UNPARSEABLE#{r.id}',
                    year=None,
                    result=result,
                    grouped_changes=grouped_changes,
                )
            continue

        assert parsed.compact_body is not None
        if _is_enterprise_record(r.type, parsed.compact_body) and r.company_id is None:
            unattributed_bodies[(r.type, parsed.compact_body)].append(r)
        by_type_body[(r.type, parsed.compact_body)].append((r, parsed))

    # 构建分组并检查跨企业归属歧义
    groups: dict[tuple[str, str, Optional[int]], list[tuple[StandardRow, ParsedStandardNo]]] = defaultdict(list)
    ambiguous_company_ids_by_body: dict[tuple[str, str], set[Optional[int]]] = defaultdict(set)

    for (std_type, compact_body), items in by_type_body.items():
        if _is_enterprise_record(std_type, compact_body):
            # 检测同号不同 company_id 之间的名称重叠/疑似更名歧义
            company_map: dict[Optional[int], Optional[str]] = {}
            for r, _ in items:
                if r.company_id is not None:
                    company_map[r.company_id] = r.company_name
            comp_items = list(company_map.items())
            for idx_a in range(len(comp_items)):
                cid_a, cname_a = comp_items[idx_a]
                for idx_b in range(idx_a + 1, len(comp_items)):
                    cid_b, cname_b = comp_items[idx_b]
                    if _are_companies_ambiguous(cname_a, cname_b):
                        ambiguous_company_ids_by_body[(std_type, compact_body)].add(cid_a)
                        ambiguous_company_ids_by_body[(std_type, compact_body)].add(cid_b)

            for r, p in items:
                groups[(std_type, compact_body, r.company_id)].append((r, p))
        else:
            for r, p in items:
                groups[(std_type, compact_body, None)].append((r, p))

    for group_tuple in sorted(groups.keys(), key=lambda x: (x[0], x[1], x[2] if x[2] is not None else -1)):
        std_type, compact_body, group_company_id = group_tuple
        items = groups[group_tuple]

        # 作用域过滤：必须整组参与计算
        if has_any_filter:
            matched_group = False
            if norm_target_bodies is not None and compact_body in norm_target_bodies:
                matched_group = True
            if norm_extra_bodies is not None and compact_body in norm_extra_bodies:
                matched_group = True
            if target_id_set is not None and any(r.id in target_id_set for r, _ in items):
                matched_group = True
            if not matched_group:
                continue

        result.total_groups += 1
        gkey = _format_group_key(std_type, compact_body, group_company_id)
        sample_company_name = next((r.company_name for r, _ in items if r.company_name), None)
        glabel = _format_group_label(std_type, compact_body, group_company_id, sample_company_name)

        def _pause_group_with_fallback(reason_code: str, reason_detail: str):
            result.paused_groups_count += 1
            for r, p in items:
                result.anomalies.append(
                    AnomalyRecord(
                        id=r.id,
                        standard_no=r.standard_no,
                        group_key=gkey,
                        group_label=glabel,
                        company_id=r.company_id,
                        company_name=r.company_name,
                        reason_code=reason_code,
                        reason_detail=reason_detail,
                    )
                )
                _plan_fallback_self_if_empty(
                    r,
                    group_key=f'FALLBACK|{gkey}|{r.id}',
                    group_label=glabel,
                    year=p.year,
                    result=result,
                    grouped_changes=grouped_changes,
                )

        # 1. 检查企业标准缺少企业归属
        if _is_enterprise_record(std_type, compact_body) and group_company_id is None:
            _pause_group_with_fallback(
                'MISSING_COMPANY_ATTRIBUTION',
                '企业标准缺少关联企业归属（company_id 为空），无法确认归属',
            )
            continue

        # 2. 若同编号主体下存在未归属的企业记录，暂停受影响组
        if (std_type, compact_body) in unattributed_bodies:
            _pause_group_with_fallback(
                'GROUP_CONTAINS_UNATTRIBUTED_RECORD',
                '同编号主体下存在缺少企业归属的记录，为保证链条完整暂停更新该组',
            )
            continue

        # 3. 检查同号跨企业 ID 的归属歧义（如主企业 vs 联合起草/疑似更名）
        if group_company_id in ambiguous_company_ids_by_body.get((std_type, compact_body), set()):
            _pause_group_with_fallback(
                'AMBIGUOUS_COMPANY_ATTRIBUTION',
                '同编号主体存在主/联合企业重叠或高度相似企业名称，企业归属不明确，暂停自动合并与更新',
            )
            continue

        # 4. 检查组内是否存在疑难格式异常兄弟记录（如 Q/JSB JS012-2014-2014 与 Q/JSB JS012-2016）
        malformed_siblings = (
            suspected_malformed_bodies.get((std_type, compact_body, group_company_id), [])
            if _is_enterprise_record(std_type, compact_body)
            else suspected_malformed_any_company.get((std_type, compact_body), [])
        )
        if malformed_siblings:
            sibling_desc = ', '.join(f'{s.id}:{s.standard_no}' for s in malformed_siblings)
            _pause_group_with_fallback(
                'GROUP_CONTAINS_MALFORMED_RECORD',
                f'同组存在格式异常记录 [{sibling_desc}]，为避免生成缺失版本的链条暂停更新该组',
            )
            continue

        # 5. 检查显式年份字段 / publish_date 严重倒挂冲突
        conflict_msgs = []
        for r, p in items:
            assert p.year is not None
            if r.explicit_year is not None and r.explicit_year != p.year:
                conflict_msgs.append(f'记录 {r.id} 编号年份 {p.year} 与年份字段 {r.explicit_year} 冲突')
            elif r.publish_date is not None and r.publish_date.year < p.year - 1:
                conflict_msgs.append(
                    f'记录 {r.id} 发布日期 {r.publish_date} 早于编号年份 {p.year} 两年以上'
                )

        if conflict_msgs:
            detail = '；'.join(conflict_msgs)
            _pause_group_with_fallback(
                'YEAR_FIELD_CONFLICT',
                f'年份字段冲突，暂停更新该组：{detail}',
            )
            continue

        # 6. 检查同组同年份重复记录
        year_buckets: dict[int, list[StandardRow]] = defaultdict(list)
        for r, p in items:
            assert p.year is not None
            year_buckets[p.year].append(r)

        dup_years = sorted(y for y, bucket in year_buckets.items() if len(bucket) > 1)
        if dup_years:
            dup_desc = '；'.join(
                f'{y}年存在ID {[x.id for x in sorted(year_buckets[y], key=lambda k: k.id)]}'
                for y in dup_years
            )
            _pause_group_with_fallback(
                'DUPLICATE_YEAR_IN_GROUP',
                f'同分组同年份存在多条记录（{dup_desc}），禁止按ID或时间强行排序，暂停更新该组',
            )
            continue

        # 7. 计算版本链（严格按标准年份从新到旧排序）
        result.valid_groups += 1
        sorted_items = sorted(items, key=lambda pair: (-(pair[1].year or 0), pair[0].id))
        all_ids = [r.id for r, _ in sorted_items]

        group_planned: list[PlannedChange] = []
        for idx, (r, p) in enumerate(sorted_items):
            assert p.year is not None
            new_all_chain = list(all_ids)
            new_part_chain = [r.id, sorted_items[idx + 1][0].id] if idx + 1 < len(sorted_items) else [r.id]
            _verify_chain_invariants(new_all_chain, new_part_chain, r.id)

            all_same = _is_strict_int_list(r.all_chain) and r.all_chain == new_all_chain
            part_same = _is_strict_int_list(r.part_chain) and r.part_chain == new_part_chain
            if all_same and part_same:
                result.unchanged_count += 1
                continue

            change = PlannedChange(
                id=r.id,
                standard_no=r.standard_no,
                group_key=gkey,
                group_label=glabel,
                year=p.year,
                company_id=r.company_id,
                company_name=r.company_name,
                old_all_chain=r.all_chain,
                new_all_chain=new_all_chain,
                old_part_chain=r.part_chain,
                new_part_chain=new_part_chain,
            )
            group_planned.append(change)
            result.changes.append(change)

        if group_planned:
            grouped_changes.append((gkey, group_planned))

    result.planned_changes_count = len(result.changes)
    result.anomalies_count = len(result.anomalies)
    return grouped_changes, result


def _save_reports(result: VersionChainRunResult, report_dir: str | Path) -> dict[str, str]:
    """流式写入 JSON 审计/回滚文件与 Markdown 报告，支持 70 万级大规模数据低内存输出。"""
    out_dir = Path(report_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    prefix = f'version_chain_{result.mode}_{ts}'

    json_path = out_dir / f'{prefix}.audit.json'
    md_path = out_dir / f'{prefix}.report.md'
    now_iso = datetime.datetime.now().isoformat(timespec='seconds')
    now_human = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    stats_dict = {
        'total_scanned': result.total_scanned,
        'total_groups': result.total_groups,
        'valid_groups': result.valid_groups,
        'paused_groups_count': result.paused_groups_count,
        'unchanged_count': result.unchanged_count,
        'planned_changes_count': result.planned_changes_count,
        'applied_count': result.applied_count,
        'anomalies_count': result.anomalies_count,
        'missing_ids': result.missing_ids,
    }

    with json_path.open('w', encoding='utf-8') as f:
        f.write('{\n')
        f.write(f'  "generated_at": {json.dumps(now_iso)},\n')
        f.write(f'  "mode": {json.dumps(result.mode)},\n')
        f.write(f'  "scope": {json.dumps(result.scope, ensure_ascii=False)},\n')
        f.write(f'  "stats": {json.dumps(stats_dict, ensure_ascii=False)},\n')
        f.write('  "changes": [\n')
        total_c = len(result.changes)
        for idx, c in enumerate(result.changes):
            comma = ',' if idx + 1 < total_c else ''
            f.write('    ' + json.dumps(asdict(c), ensure_ascii=False) + comma + '\n')
        f.write('  ],\n')
        f.write('  "anomalies": [\n')
        total_a = len(result.anomalies)
        for idx, a in enumerate(result.anomalies):
            comma = ',' if idx + 1 < total_a else ''
            f.write('    ' + json.dumps(asdict(a), ensure_ascii=False) + comma + '\n')
        f.write('  ]\n')
        f.write('}\n')

    max_md_changes = 10000
    with md_path.open('w', encoding='utf-8') as f:
        f.write(f'# 标准版本链处理报告 ({result.mode})\n\n')
        f.write(f'- 生成时间: {now_human}\n')
        f.write(f'- 运行模式: `{result.mode}`\n')
        f.write(f'- 处理范围: `{result.scope}`\n')
        f.write(f'- 扫描记录总数: {result.total_scanned}\n')
        f.write(f'- 纳入范围分组数: {result.total_groups}（有效组 {result.valid_groups}，异常暂停组 {result.paused_groups_count}）\n')
        f.write(f'- 待更新/已更新记录数: {result.planned_changes_count}（实际写入 {result.applied_count}）\n')
        f.write(f'- 无需变更记录数: {result.unchanged_count}\n')
        f.write(f'- 异常/跳过记录数: {result.anomalies_count}\n')
        if result.missing_ids:
            f.write(f'- 未找到的指定 ID: {result.missing_ids}\n')

        f.write('\n## 一、变更明细\n\n')
        if result.changes:
            if len(result.changes) > max_md_changes:
                f.write(f'> 变更共 {len(result.changes)} 条，为保证报告可读性本表仅展示前 {max_md_changes} 条，完整全量明细请查看同目录 `.audit.json` 文件。\n\n')
            f.write('| 变更类型 | 分组依据 | 记录 ID | 标准编号 | 年份 | 原 all_chain | 新 all_chain | 原 part_chain | 新 part_chain |\n')
            f.write('|---|---|---|---|---|---|---|---|---|\n')
            for c in result.changes[:max_md_changes]:
                ctype = '默认兜底自身ID' if c.change_type == 'fallback_self' else '版本链计算'
                year_str = str(c.year) if c.year is not None else '-'
                f.write(
                    f'| {ctype} | {c.group_label} | {c.id} | `{c.standard_no}` | {year_str} | '
                    f'`{json.dumps(c.old_all_chain, ensure_ascii=False)}` | '
                    f'`{json.dumps(c.new_all_chain, separators=(",", ":"))}` | '
                    f'`{json.dumps(c.old_part_chain, ensure_ascii=False)}` | '
                    f'`{json.dumps(c.new_part_chain, separators=(",", ":"))}` |\n'
                )
        else:
            f.write('无需要变更的记录。\n')

        f.write('\n## 二、异常与跳过清单\n\n')
        if result.anomalies:
            f.write('| 分组依据 | 记录 ID | 标准编号 | 关联企业 | 异常代码 | 跳过原因 |\n')
            f.write('|---|---|---|---|---|---|\n')
            for a in result.anomalies:
                comp = f'{a.company_id or ""} {a.company_name or ""}'.strip() or '-'
                f.write(
                    f'| {a.group_label or "-"} | {a.id} | `{a.standard_no}` | {comp} | '
                    f'`{a.reason_code}` | {a.reason_detail} |\n'
                )
        else:
            f.write('无异常记录。\n')

    return {'audit_json': str(json_path), 'report_md': str(md_path)}


def _pack_whole_groups_into_batches(
    grouped_changes: list[tuple[str, list[PlannedChange]]],
    max_records_per_batch: int,
) -> list[list[PlannedChange]]:
    """
    将分组打包为不超过 max_records_per_batch 条记录的批次，绝不将同一分组拆分到不同事务中。
    """
    limit = max(1, max_records_per_batch)
    batches: list[list[PlannedChange]] = []
    current_batch: list[PlannedChange] = []

    for _gkey, group_changes in grouped_changes:
        if current_batch and len(current_batch) + len(group_changes) > limit:
            batches.append(current_batch)
            current_batch = []
        current_batch.extend(group_changes)

    if current_batch:
        batches.append(current_batch)
    return batches


def run_version_chain_completion(
    *,
    execute: bool = False,
    target_bodies: Optional[Iterable[str]] = None,
    target_ids: Optional[Iterable[int]] = None,
    extra_bodies: Optional[Iterable[str]] = None,
    batch_size: int = 1000,
    report_dir: Optional[str | Path] = None,
    save_report: bool = True,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> VersionChainRunResult:
    """
    执行标准版本链补全（默认仅试运行预览，execute=True 时按整组打包在事务内批量写入数据库）。
    """
    rows = _fetch_rows_for_scope(
        target_bodies=target_bodies,
        target_ids=target_ids,
        extra_bodies=extra_bodies,
    )
    grouped_changes, result = compute_version_chains(
        rows,
        target_bodies=target_bodies,
        target_ids=target_ids,
        extra_bodies=extra_bodies,
    )
    result.mode = 'execute' if execute else 'dry_run'

    if execute and grouped_changes:
        batches = _pack_whole_groups_into_batches(grouped_changes, batch_size)
        total_records = result.planned_changes_count
        total_batches = len(batches)
        applied = 0

        with suppress_version_chain_signals():
            for batch_idx, batch_changes in enumerate(batches, start=1):
                ids = [c.id for c in batch_changes]
                change_by_id = {c.id: c for c in batch_changes}
                with transaction.atomic():
                    objs = list(
                        Standard.objects.select_for_update()
                        .only('id', 'all_chain', 'part_chain')
                        .filter(id__in=ids)
                    )
                    if len(objs) != len(ids):
                        found = {o.id for o in objs}
                        raise RuntimeError(f'组内记录缺失，回滚更新: missing={set(ids) - found}')
                    for obj in objs:
                        ch = change_by_id[obj.id]
                        obj.all_chain = ch.new_all_chain
                        obj.part_chain = ch.new_part_chain
                    Standard.objects.bulk_update(objs, ['all_chain', 'part_chain'], batch_size=max(1, batch_size))
                applied += len(objs)

                if progress_callback:
                    progress_callback(
                        f'批次 {batch_idx}/{total_batches}，累计更新 {applied}/{total_records} 条记录'
                    )

        result.applied_count = applied

    if save_report:
        default_dir = Path(settings.BASE_DIR) / 'reports' / 'version_chains'
        result.report_files = _save_reports(result, report_dir or default_dir)

    return result


def extract_affected_bodies(standard_nos: Iterable[Optional[str]]) -> set[str]:
    """从一组标准编号中提取受影响的标准主体键（含疑难畸形编号的疑似主体）。"""
    bodies: set[str] = set()
    for sno in standard_nos:
        parsed = parse_standard_no(sno)
        if parsed.compact_body:
            bodies.add(parsed.compact_body)
        elif parsed.suspected_compact_body:
            bodies.add(parsed.suspected_compact_body)
    return bodies


def sync_version_chains_for_targets(
    *,
    target_ids: Optional[Iterable[int]] = None,
    extra_bodies: Optional[Iterable[str]] = None,
) -> Optional[VersionChainRunResult]:
    """
    自动同步指定记录及其所在完整版本链分组（用于信号实时更新与批量导入后置对齐）。
    """
    id_list = [int(i) for i in target_ids if i is not None] if target_ids is not None else []
    body_list = [b for b in extra_bodies if b] if extra_bodies is not None else []
    if not id_list and not body_list:
        return None
    return run_version_chain_completion(
        execute=True,
        target_ids=id_list or None,
        extra_bodies=body_list or None,
        save_report=False,
    )


def sync_version_chains_for_standards(standards: Iterable[Standard]) -> Optional[VersionChainRunResult]:
    """针对批量创建/更新后的 Standard 对象集合，一次性自动同步其所在全部分组的版本链。"""
    std_list = list(standards)
    if not std_list:
        return None
    ids = [s.id for s in std_list if getattr(s, 'id', None)]
    bodies = extract_affected_bodies(getattr(s, 'standard_no', None) for s in std_list)
    return sync_version_chains_for_targets(target_ids=ids or None, extra_bodies=bodies or None)


def rollback_from_audit_file(
    audit_json_path: str | Path,
    *,
    execute: bool = False,
    batch_size: int = 1000,
) -> dict:
    """
    根据保存的审计 JSON 文件中的 old_all_chain / old_part_chain 回滚数据库记录。
    按整组打包在事务内批量回滚，绝不拆分同组记录。
    """
    path = Path(audit_json_path)
    with path.open('r', encoding='utf-8') as f:
        payload = json.load(f)

    changes = payload.get('changes', [])
    by_group: dict[str, list[dict]] = defaultdict(list)
    for item in changes:
        by_group[item['group_key']].append(item)

    restored_count = 0
    if execute and by_group:
        limit = max(1, batch_size)
        batches: list[list[dict]] = []
        cur: list[dict] = []
        for items in by_group.values():
            if cur and len(cur) + len(items) > limit:
                batches.append(cur)
                cur = []
            cur.extend(items)
        if cur:
            batches.append(cur)

        with suppress_version_chain_signals():
            for batch_items in batches:
                ids = [int(i['id']) for i in batch_items]
                by_id = {int(i['id']): i for i in batch_items}
                with transaction.atomic():
                    objs = list(
                        Standard.objects.select_for_update()
                        .only('id', 'all_chain', 'part_chain')
                        .filter(id__in=ids)
                    )
                    for obj in objs:
                        rec = by_id[obj.id]
                        obj.all_chain = rec['old_all_chain'] if rec['old_all_chain'] is not None else []
                        obj.part_chain = rec['old_part_chain'] if rec['old_part_chain'] is not None else []
                    Standard.objects.bulk_update(objs, ['all_chain', 'part_chain'], batch_size=limit)
                    restored_count += len(objs)

    return {
        'mode': 'execute' if execute else 'dry_run',
        'audit_file': str(path),
        'groups_count': len(by_group),
        'records_in_audit': len(changes),
        'restored_count': restored_count,
    }
