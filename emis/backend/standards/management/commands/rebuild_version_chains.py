"""
Django 管理命令：standards_standard 表标准版本链（all_chain / part_chain）补全与回滚。

示例：
  # 1. 全量试运行（仅预览与生成报告，不写数据库）
  python manage.py rebuild_version_chains --dry-run

  # 2. 按标准编号主体试运行 / 正式更新
  python manage.py rebuild_version_chains --body "Q/SYJT 003"
  python manage.py rebuild_version_chains --body "Q/SYJT 003" --execute

  # 3. 按指定记录 ID 所在完整分组处理
  python manage.py rebuild_version_chains --ids 234
  python manage.py rebuild_version_chains --ids 234 --execute

  # 4. 全量正式更新（必须显式传 --execute --all）
  python manage.py rebuild_version_chains --execute --all --batch-size 200

  # 5. 根据审计文件回滚
  python manage.py rebuild_version_chains --rollback reports/version_chains/xxx.audit.json --execute
"""

import json
from django.core.management.base import BaseCommand, CommandError

from standards.services_version_chain import (
    rollback_from_audit_file,
    run_version_chain_completion,
)


def _parse_id_tokens(raw_tokens: list[str] | None) -> list[int] | None:
    if not raw_tokens:
        return None
    ids: list[int] = []
    for token in raw_tokens:
        for part in str(token).split(','):
            part = part.strip()
            if not part:
                continue
            try:
                ids.append(int(part))
            except ValueError as exc:
                raise CommandError(f'无效的记录 ID: {part!r}') from exc
    return ids or None


def _parse_body_tokens(raw_tokens: list[str] | None) -> list[str] | None:
    if not raw_tokens:
        return None
    bodies: list[str] = []
    for token in raw_tokens:
        for part in str(token).split(','):
            part = part.strip()
            if part:
                bodies.append(part)
    return bodies or None


class Command(BaseCommand):
    help = '计算并按需更新 standards_standard 表的 all_chain 和 part_chain 版本链字段（默认试运行）'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='试运行模式（默认）：仅计算并输出变更预览和异常清单，不写数据库',
        )
        parser.add_argument(
            '--execute',
            action='store_true',
            help='正式写入数据库模式；未指定 --body/--ids 时必须同时指定 --all',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            dest='run_all',
            help='允许在 --execute 模式下执行全量更新',
        )
        parser.add_argument(
            '--body',
            action='append',
            dest='bodies',
            help='按标准编号主体处理（可多次传入或用逗号分隔），例如 --body "Q/SYJT 003"',
        )
        parser.add_argument(
            '--ids',
            action='append',
            dest='id_tokens',
            help='按指定记录 ID 所在完整分组处理（可多次传入或用逗号分隔），例如 --ids 234',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=200,
            help='正式写入时每批处理的分组数量并输出进度（默认 200）',
        )
        parser.add_argument(
            '--report-dir',
            type=str,
            default=None,
            help='审计 JSON 与 Markdown 报告输出目录（默认 backend/reports/version_chains）',
        )
        parser.add_argument(
            '--no-report',
            action='store_true',
            help='不将审计 JSON 与 Markdown 报告写入磁盘',
        )
        parser.add_argument(
            '--preview-limit',
            type=int,
            default=30,
            help='控制台最多展示多少条变更预览与异常详情（默认 30）',
        )
        parser.add_argument(
            '--rollback',
            type=str,
            default=None,
            help='指定审计 JSON 文件路径，将受影响记录回滚至修改前的值（需配合 --execute 实际写入）',
        )

    def handle(self, *args, **options):
        if options['dry_run'] and options['execute']:
            raise CommandError('--dry-run 与 --execute 不能同时指定')

        execute = bool(options['execute'])
        rollback_path = options['rollback']

        if rollback_path:
            summary = rollback_from_audit_file(rollback_path, execute=execute)
            self.stdout.write(self.style.SUCCESS('=== 版本链回滚结果 ==='))
            self.stdout.write(json.dumps(summary, ensure_ascii=False, indent=2))
            return

        target_bodies = _parse_body_tokens(options['bodies'])
        target_ids = _parse_id_tokens(options['id_tokens'])

        if execute and not options['run_all'] and not target_bodies and not target_ids:
            raise CommandError(
                '全量正式写入数据库必须显式传入 --execute --all；'
                '若只需处理局部范围请传 --body 或 --ids；若只需预览请使用 --dry-run。'
            )

        def on_progress(msg: str):
            self.stdout.write(f'[进度] {msg}')

        result = run_version_chain_completion(
            execute=execute,
            target_bodies=target_bodies,
            target_ids=target_ids,
            batch_size=options['batch_size'],
            report_dir=options['report_dir'],
            save_report=not options['no_report'],
            progress_callback=on_progress,
        )

        mode_label = '正式写入 (execute)' if execute else '试运行 (dry-run)'
        self.stdout.write(self.style.SUCCESS(f'=== 标准版本链处理完成 [{mode_label}] ==='))
        self.stdout.write(f'处理范围: {result.scope}')
        self.stdout.write(f'扫描总记录数: {result.total_scanned}')
        self.stdout.write(
            f'范围内分组数: {result.total_groups} '
            f'(有效组: {result.valid_groups}, 异常暂停组: {result.paused_groups_count})'
        )
        self.stdout.write(f'计划变更记录数: {result.planned_changes_count}')
        self.stdout.write(f'实际写入记录数: {result.applied_count}')
        self.stdout.write(f'无需变更记录数: {result.unchanged_count}')
        self.stdout.write(f'异常/跳过记录数: {result.anomalies_count}')
        if result.missing_ids:
            self.stdout.write(self.style.WARNING(f'未找到的指定 ID: {result.missing_ids}'))

        limit = max(0, options['preview_limit'])
        if result.changes and limit > 0:
            self.stdout.write('\n--- 变更预览 ---')
            for ch in result.changes[:limit]:
                self.stdout.write(
                    f'  [ID={ch.id}] {ch.standard_no} | 组={ch.group_label} | '
                    f'all: {ch.old_all_chain} -> {ch.new_all_chain} | '
                    f'part: {ch.old_part_chain} -> {ch.new_part_chain}'
                )
            if len(result.changes) > limit:
                self.stdout.write(f'  ... 其余 {len(result.changes) - limit} 条详见报告文件')

        if result.anomalies and limit > 0:
            self.stdout.write('\n--- 异常与跳过清单 ---')
            for an in result.anomalies[:limit]:
                self.stdout.write(
                    f'  [ID={an.id}] {an.standard_no} | [{an.reason_code}] {an.reason_detail}'
                )
            if len(result.anomalies) > limit:
                self.stdout.write(f'  ... 其余 {len(result.anomalies) - limit} 条详见报告文件')

        if result.report_files:
            self.stdout.write('\n--- 输出文件 ---')
            for k, path in result.report_files.items():
                self.stdout.write(f'  {k}: {path}')
