import datetime
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from companies.models import Company
from standards.models import Standard
from standards.services_version_chain import (
    StandardRow,
    compute_version_chains,
    parse_standard_no,
    rollback_from_audit_file,
    run_version_chain_completion,
    suppress_version_chain_signals,
    sync_version_chains_for_standards,
)


class VersionChainParserTests(TestCase):
    def test_valid_formats_and_normalization(self):
        p1 = parse_standard_no('Q/SYJT 003-2024')
        self.assertTrue(p1.is_valid)
        self.assertEqual(p1.compact_body, 'Q/SYJT003')
        self.assertEqual(p1.year, 2024)

        p2 = parse_standard_no('  Ｑ／ＳＹＪＴ　００３—２０２６ ')
        self.assertTrue(p2.is_valid)
        self.assertEqual(p2.compact_body, 'Q/SYJT003')
        self.assertEqual(p2.year, 2026)

        p3 = parse_standard_no('Q/2022-2016')
        self.assertTrue(p3.is_valid)
        self.assertEqual(p3.compact_body, 'Q/2022')
        self.assertEqual(p3.year, 2016)

        p4 = parse_standard_no('新Q/BD 005-2026')
        self.assertTrue(p4.is_valid)
        self.assertEqual(p4.compact_body, '新Q/BD005')
        self.assertEqual(p4.year, 2026)

    def test_invalid_formats_rejected(self):
        invalid_cases = [
            ('', 'EMPTY_STANDARD_NO'),
            ('   ', 'EMPTY_STANDARD_NO'),
            ('未知企标号', 'NO_TRAILING_YEAR'),
            ('Q/16', 'NO_TRAILING_YEAR'),
            ('Q/hsjj-003', 'NO_TRAILING_YEAR'),
            ('Q/YNY-8051', 'YEAR_OUT_OF_RANGE'),
            ('Q/JSB JS012-2014-2014', 'DOUBLE_YEAR_SUFFIX'),
            ('Q/T11944-2012 中空玻璃 -2012', 'EMBEDDED_TITLE_OR_YEAR'),
            ('Q/HHJC .-2024', 'TRAILING_PUNCTUATION_IN_BODY'),
            ('Q/Q/FQCJ 003-2023', 'MALFORMED_PREFIX'),
            ('Q//KLJ-006-2023', 'MALFORMED_PREFIX'),
        ]
        for raw, expected_code in invalid_cases:
            parsed = parse_standard_no(raw)
            self.assertFalse(parsed.is_valid, f'Expected invalid for {raw!r}')
            self.assertEqual(parsed.error_code, expected_code, f'Unexpected code for {raw!r}')


class VersionChainServiceAndCommandTests(TestCase):
    def setUp(self):
        self.comp_a = Company.objects.create(
            name='测试实业有限公司',
            credit_code='91330000000000001A',
            status='active',
        )
        self.comp_b = Company.objects.create(
            name='另一家独立科技有限公司',
            credit_code='91330000000000002B',
            status='active',
        )

    def _create_std(self, *, pk=None, standard_no, std_type='enterprise', company=None, title='测试标准', publish_date=None, all_chain=None, part_chain=None):
        kwargs = {
            'standard_no': standard_no,
            'clean_id': standard_no,
            'type': std_type,
            'title': title,
            'company': company,
            'publish_date': publish_date,
            'all_chain': all_chain if all_chain is not None else [],
            'part_chain': part_chain if part_chain is not None else [],
            'status': 'active',
        }
        if pk is not None:
            kwargs['id'] = pk
        with suppress_version_chain_signals():
            return Standard.objects.create(**kwargs)

    def test_required_example_exact_match_and_idempotency(self):
        """验证题目指定 3 条示例的精确结果，以及不修改 standard_no、重复运行幂等。"""
        self._create_std(pk=234, standard_no='Q/SYJT 003-2024', company=self.comp_a, publish_date=datetime.date(2025, 1, 10))
        self._create_std(pk=12234, standard_no='Q/SYJT 003-2026', company=self.comp_a, publish_date=datetime.date(2026, 2, 1))
        self._create_std(pk=2234, standard_no='Q/SYJT 003-2017', company=self.comp_a, publish_date=datetime.date(2020, 6, 1))

        # 试运行不得写入数据库
        with tempfile.TemporaryDirectory() as tmpdir:
            dry_res = run_version_chain_completion(execute=False, report_dir=tmpdir)
            self.assertEqual(dry_res.planned_changes_count, 3)
            self.assertEqual(dry_res.applied_count, 0)
            self.assertTrue(Path(dry_res.report_files['audit_json']).exists())
            self.assertTrue(Path(dry_res.report_files['report_md']).exists())

            for pk in (234, 12234, 2234):
                obj = Standard.objects.get(pk=pk)
                self.assertEqual(obj.all_chain, [])
                self.assertEqual(obj.part_chain, [])

            # 正式写入
            exec_res = run_version_chain_completion(execute=True, report_dir=tmpdir)
            self.assertEqual(exec_res.applied_count, 3)

            s_12234 = Standard.objects.get(pk=12234)
            s_234 = Standard.objects.get(pk=234)
            s_2234 = Standard.objects.get(pk=2234)

            self.assertEqual(s_12234.all_chain, [12234, 234, 2234])
            self.assertEqual(s_12234.part_chain, [12234, 234])

            self.assertEqual(s_234.all_chain, [12234, 234, 2234])
            self.assertEqual(s_234.part_chain, [234, 2234])

            self.assertEqual(s_2234.all_chain, [12234, 234, 2234])
            self.assertEqual(s_2234.part_chain, [2234])

            # 原始 standard_no 未被修改
            self.assertEqual(s_234.standard_no, 'Q/SYJT 003-2024')
            self.assertEqual(s_12234.standard_no, 'Q/SYJT 003-2026')
            self.assertEqual(s_2234.standard_no, 'Q/SYJT 003-2017')

            # 幂等性：再次执行零变更
            second_res = run_version_chain_completion(execute=True, report_dir=tmpdir)
            self.assertEqual(second_res.planned_changes_count, 0)
            self.assertEqual(second_res.applied_count, 0)
            self.assertEqual(second_res.unchanged_count, 3)

    def test_single_record_and_insert_higher_and_intermediate_versions(self):
        """验证单条记录、新增更高年份以及新增中间年份版本后的链条更新。"""
        self._create_std(pk=501, standard_no='Q/SINGLE 001-2022', company=self.comp_a)
        run_version_chain_completion(execute=True, save_report=False)

        s501 = Standard.objects.get(pk=501)
        self.assertEqual(s501.all_chain, [501])
        self.assertEqual(s501.part_chain, [501])

        # 新增更高年份（ID 更小，检验不按 ID 排序）
        self._create_std(pk=102, standard_no='Q/SINGLE 001-2026', company=self.comp_a)
        run_version_chain_completion(execute=True, save_report=False)

        s102 = Standard.objects.get(pk=102)
        s501.refresh_from_db()
        self.assertEqual(s102.all_chain, [102, 501])
        self.assertEqual(s102.part_chain, [102, 501])
        self.assertEqual(s501.all_chain, [102, 501])
        self.assertEqual(s501.part_chain, [501])

        # 新增中间年份 2024（验证受影响的 part_chain 正确更新）
        self._create_std(pk=900, standard_no='Q/SINGLE 001-2024', company=self.comp_a)
        res = run_version_chain_completion(execute=True, save_report=False)
        self.assertEqual(res.applied_count, 3)

        s102.refresh_from_db()
        s900 = Standard.objects.get(pk=900)
        s501.refresh_from_db()
        self.assertEqual(s102.all_chain, [102, 900, 501])
        self.assertEqual(s102.part_chain, [102, 900])
        self.assertEqual(s900.all_chain, [102, 900, 501])
        self.assertEqual(s900.part_chain, [900, 501])
        self.assertEqual(s501.all_chain, [102, 900, 501])
        self.assertEqual(s501.part_chain, [501])

    def test_no_false_merges_and_format_equivalence(self):
        """验证 GB vs GB/T、003.1 vs 003.2、003 vs 3、新Q vs Q、同名不同号不混组；等价全角/横杠/空格可合并。"""
        # 国标与分部分
        gb = self._create_std(pk=10, standard_no='GB 100-2020', std_type='national', title='通用名称')
        gbt = self._create_std(pk=11, standard_no='GB/T 100-2021', std_type='national', title='通用名称')
        p1 = self._create_std(pk=12, standard_no='Q/SYJT 003.1-2020', company=self.comp_a, title='第一部分')
        p2 = self._create_std(pk=13, standard_no='Q/SYJT 003.2-2021', company=self.comp_a, title='第二部分')
        z3 = self._create_std(pk=14, standard_no='Q/SYJT 003-2020', company=self.comp_a, title='产品标准')
        s3 = self._create_std(pk=15, standard_no='Q/SYJT 3-2021', company=self.comp_a, title='产品标准')
        xq = self._create_std(pk=16, standard_no='新Q/BD 005-2026', company=self.comp_a, title='同名称测试')
        nq = self._create_std(pk=17, standard_no='Q/BD 005-2025', company=self.comp_a, title='同名称测试')

        # 全角/长破折号/空格差异应正常归入同一组，但保留原始 standard_no
        eq1 = self._create_std(pk=20, standard_no='Q/NTXJ 001-2024', company=self.comp_a)
        eq2 = self._create_std(pk=21, standard_no='Ｑ／ＮＴＸＪ００１—２０２０', company=self.comp_a)

        run_version_chain_completion(execute=True, save_report=False)

        for obj in (gb, gbt, p1, p2, z3, s3, xq, nq):
            obj.refresh_from_db()
            self.assertEqual(obj.all_chain, [obj.id])
            self.assertEqual(obj.part_chain, [obj.id])

        eq1.refresh_from_db()
        eq2.refresh_from_db()
        self.assertEqual(eq1.all_chain, [20, 21])
        self.assertEqual(eq1.part_chain, [20, 21])
        self.assertEqual(eq2.all_chain, [20, 21])
        self.assertEqual(eq2.part_chain, [21])
        self.assertEqual(eq2.standard_no, 'Ｑ／ＮＴＸＪ００１—２０２０')

    def test_anomaly_interceptions_preserve_existing_chains(self):
        """验证同年份重复、编号缺失、格式异常、企业归属缺失、跨企业歧义及年份冲突均拦截且保留原值。"""
        # 1. 同组同年份重复 -> 整组（含另一正常年份）均暂停更新并保留原值
        d1 = self._create_std(pk=1001, standard_no='Q/DUP 001-2024', company=self.comp_a, all_chain=[999], part_chain=[999])
        d2 = self._create_std(pk=1002, standard_no='Q/DUP 001—2024', company=self.comp_a)
        d3 = self._create_std(pk=1003, standard_no='Q/DUP 001-2020', company=self.comp_a, all_chain=[888], part_chain=[888])

        # 2. 格式异常与缺失
        bad_empty = self._create_std(pk=1004, standard_no='   ', company=self.comp_a, all_chain=[111])
        bad_8051 = self._create_std(pk=1005, standard_no='Q/YNY-8051', company=self.comp_a)
        bad_double_y = self._create_std(pk=1006, standard_no='Q/JSB JS012-2014-2014', company=self.comp_a)
        sib_double_y = self._create_std(pk=1007, standard_no='Q/JSB JS012-2016', company=self.comp_a, all_chain=[777])

        # 3. 企业归属缺失
        no_comp = self._create_std(pk=1008, standard_no='Q/NOCOMP 001-2023', company=None)

        # 4. 同号不同独立企业（应分别独立建链，不混组、不拦截）
        sep_a = self._create_std(pk=1009, standard_no='Q/SAME 001-2024', company=self.comp_a, title='石灰石粉')
        sep_b = self._create_std(pk=1010, standard_no='Q/SAME 001-2023', company=self.comp_b, title='宠物项圈')

        # 5. 同号疑似联合/更名企业（归属不明确 -> 暂停更新）
        comp_joint = Company.objects.create(
            name='测试实业有限公司、合作研究院',
            credit_code='91330000000000003C',
            status='active',
        )
        amb_1 = self._create_std(pk=1011, standard_no='Q/AMB 001-2024', company=self.comp_a)
        amb_2 = self._create_std(pk=1012, standard_no='Q/AMB 001-2023', company=comp_joint)

        # 6. publish_date 早于编号年份 2 年以上 -> 冲突暂停
        pub_conflict = self._create_std(
            pk=1013,
            standard_no='Q/CONF 001-2025',
            company=self.comp_a,
            publish_date=datetime.date(2020, 1, 1),
        )

        res = run_version_chain_completion(execute=True, save_report=False)
        # 2 条正常分隔记录 + 7 条原 all_chain 为空的异常/无法解析记录均兜底填入自身 ID
        self.assertEqual(res.applied_count, 9)

        # 原已有非空链条字段保持不变；原为空的默认填入自身 ID，part_chain 保持空
        d1.refresh_from_db()
        d2.refresh_from_db()
        d3.refresh_from_db()
        self.assertEqual(d1.all_chain, [999])
        self.assertEqual(d2.all_chain, [1002])
        self.assertEqual(d2.part_chain, [])
        self.assertEqual(d3.all_chain, [888])

        bad_empty.refresh_from_db()
        self.assertEqual(bad_empty.all_chain, [111])
        sib_double_y.refresh_from_db()
        self.assertEqual(sib_double_y.all_chain, [777])

        for fallback_std in (bad_8051, bad_double_y, no_comp, amb_1, amb_2, pub_conflict):
            fallback_std.refresh_from_db()
            self.assertEqual(fallback_std.all_chain, [fallback_std.id])
            self.assertEqual(fallback_std.part_chain, [])

        sep_a.refresh_from_db()
        sep_b.refresh_from_db()
        self.assertEqual(sep_a.all_chain, [1009])
        self.assertEqual(sep_b.all_chain, [1010])

        codes = {a.id: a.reason_code for a in res.anomalies}
        self.assertEqual(codes[1001], 'DUPLICATE_YEAR_IN_GROUP')
        self.assertEqual(codes[1003], 'DUPLICATE_YEAR_IN_GROUP')
        self.assertEqual(codes[1004], 'EMPTY_STANDARD_NO')
        self.assertEqual(codes[1005], 'YEAR_OUT_OF_RANGE')
        self.assertEqual(codes[1006], 'DOUBLE_YEAR_SUFFIX')
        self.assertEqual(codes[1007], 'GROUP_CONTAINS_MALFORMED_RECORD')
        self.assertEqual(codes[1008], 'MISSING_COMPANY_ATTRIBUTION')
        self.assertEqual(codes[1011], 'AMBIGUOUS_COMPANY_ATTRIBUTION')
        self.assertEqual(codes[1012], 'AMBIGUOUS_COMPANY_ATTRIBUTION')
        self.assertEqual(codes[1013], 'YEAR_FIELD_CONFLICT')

    def test_scope_by_single_id_and_by_body(self):
        """验证指定单条 ID 时必须查询所在完整分组，不能仅用局部记录建链。"""
        self._create_std(pk=234, standard_no='Q/SYJT 003-2024', company=self.comp_a)
        self._create_std(pk=12234, standard_no='Q/SYJT 003-2026', company=self.comp_a)
        self._create_std(pk=2234, standard_no='Q/SYJT 003-2017', company=self.comp_a)
        other = self._create_std(pk=9999, standard_no='Q/OTHER 001-2025', company=self.comp_a)

        # 通过管理命令仅传 --ids 234
        call_command('rebuild_version_chains', '--ids', '234', '--execute', '--no-report')

        for pk in (12234, 234, 2234):
            obj = Standard.objects.get(pk=pk)
            self.assertEqual(obj.all_chain, [12234, 234, 2234])

        self.assertEqual(Standard.objects.get(pk=12234).part_chain, [12234, 234])
        self.assertEqual(Standard.objects.get(pk=234).part_chain, [234, 2234])
        self.assertEqual(Standard.objects.get(pk=2234).part_chain, [2234])

        # 作用域外记录不受影响
        other.refresh_from_db()
        self.assertEqual(other.all_chain, [])

        # 通过 --body 更新另一分组
        call_command('rebuild_version_chains', '--body', 'Q/OTHER 001', '--execute', '--no-report')
        other.refresh_from_db()
        self.assertEqual(other.all_chain, [9999])
        self.assertEqual(other.part_chain, [9999])

    def test_execute_requires_all_or_scope_and_rollback_works(self):
        """验证全量执行保护开关、事务原子性以及审计文件回滚。"""
        with self.assertRaises(CommandError):
            call_command('rebuild_version_chains', '--execute', '--no-report')

        self._create_std(pk=301, standard_no='Q/RB 001-2025', company=self.comp_a, all_chain=[1], part_chain=[1])
        self._create_std(pk=302, standard_no='Q/RB 001-2020', company=self.comp_a)

        with tempfile.TemporaryDirectory() as tmpdir:
            res = run_version_chain_completion(execute=True, report_dir=tmpdir)
            self.assertEqual(res.applied_count, 2)
            self.assertEqual(Standard.objects.get(pk=301).all_chain, [301, 302])
            self.assertEqual(Standard.objects.get(pk=302).all_chain, [301, 302])

            audit_path = res.report_files['audit_json']
            rb_dry = rollback_from_audit_file(audit_path, execute=False)
            self.assertEqual(rb_dry['restored_count'], 0)
            self.assertEqual(Standard.objects.get(pk=301).all_chain, [301, 302])

            rb_exec = rollback_from_audit_file(audit_path, execute=True)
            self.assertEqual(rb_exec['restored_count'], 2)
            self.assertEqual(Standard.objects.get(pk=301).all_chain, [1])
            self.assertEqual(Standard.objects.get(pk=301).part_chain, [1])
            self.assertEqual(Standard.objects.get(pk=302).all_chain, [])
            self.assertEqual(Standard.objects.get(pk=302).part_chain, [])

    def test_transaction_atomicity_on_group_failure(self):
        """验证单组更新发生异常时整组回滚，不会出现部分记录更新。"""
        self._create_std(pk=401, standard_no='Q/TX 001-2025', company=self.comp_a)
        self._create_std(pk=402, standard_no='Q/TX 001-2020', company=self.comp_a)

        with patch.object(Standard.objects, 'bulk_update', side_effect=RuntimeError('simulated db failure')):
            with self.assertRaises(RuntimeError):
                run_version_chain_completion(execute=True, save_report=False)

        self.assertEqual(Standard.objects.get(pk=401).all_chain, [])
        self.assertEqual(Standard.objects.get(pk=402).all_chain, [])

    def test_explicit_year_field_conflict_detected(self):
        """验证若传入显式年份字段且与标准编号年份不一致，拦截该组。"""
        rows = [
            StandardRow(
                id=1,
                standard_no='Q/EX 001-2024',
                type='enterprise',
                title='测试',
                company_id=1,
                company_name='测试公司',
                publish_date=None,
                all_chain=[],
                part_chain=[],
                explicit_year=2023,
            )
        ]
        grouped, res = compute_version_chains(rows)
        self.assertEqual(len(grouped), 1)
        self.assertEqual(res.anomalies_count, 1)
        self.assertEqual(res.anomalies[0].reason_code, 'YEAR_FIELD_CONFLICT')
        self.assertEqual(res.planned_changes_count, 1)
        self.assertEqual(res.changes[0].change_type, 'fallback_self')
        self.assertEqual(res.changes[0].new_all_chain, [1])


class VersionChainAutoSyncTests(TestCase):
    """验证新增、修改、删除、批量导入与定时兜底任务下的自动版本链更新。"""

    def setUp(self):
        self.comp_a = Company.objects.create(
            name='自动同步测试企业A',
            credit_code='91330000000000091A',
            status='active',
        )

    def test_realtime_create_update_delete_auto_sync(self):
        # 1. 新增第一条企标，自动填入自身 ID
        s_2024 = Standard.objects.create(
            id=2001,
            standard_no='Q/AUTO 001-2024',
            clean_id='Q/AUTO001-2024',
            type='enterprise',
            company=self.comp_a,
            status='active',
        )
        self.assertEqual(s_2024.all_chain, [2001])
        self.assertEqual(s_2024.part_chain, [2001])

        # 2. 新增更高年份版本，整组自动联动刷新
        s_2026 = Standard.objects.create(
            id=2002,
            standard_no='Q/AUTO 001-2026',
            clean_id='Q/AUTO001-2026',
            type='enterprise',
            company=self.comp_a,
            status='active',
        )
        s_2024.refresh_from_db()
        self.assertEqual(s_2026.all_chain, [2002, 2001])
        self.assertEqual(s_2026.part_chain, [2002, 2001])
        self.assertEqual(s_2024.all_chain, [2002, 2001])
        self.assertEqual(s_2024.part_chain, [2001])

        # 3. 新增无法解析年份的企标，默认在 all_chain 填入自身 ID
        s_bad = Standard.objects.create(
            id=2003,
            standard_no='未知企标号',
            clean_id='未知企标号',
            type='enterprise',
            company=self.comp_a,
            status='active',
        )
        self.assertEqual(s_bad.all_chain, [2003])

        # 4. 修改标准编号主体，原分组与新分组均自动更新
        s_2024.standard_no = 'Q/AUTO 002-2024'
        s_2024.save()
        s_2026.refresh_from_db()
        s_2024.refresh_from_db()
        self.assertEqual(s_2026.all_chain, [2002])
        self.assertEqual(s_2026.part_chain, [2002])
        self.assertEqual(s_2024.all_chain, [2001])
        self.assertEqual(s_2024.part_chain, [2001])

        # 5. 再添加 2025 版到 Q/AUTO 002 并随后删除，验证删除后自动回退为单条链
        s_2025 = Standard.objects.create(
            id=2004,
            standard_no='Q/AUTO 002-2025',
            clean_id='Q/AUTO002-2025',
            type='enterprise',
            company=self.comp_a,
            status='active',
        )
        s_2024.refresh_from_db()
        self.assertEqual(s_2024.all_chain, [2004, 2001])
        self.assertEqual(s_2025.part_chain, [2004, 2001])

        s_2025.delete()
        s_2024.refresh_from_db()
        self.assertEqual(s_2024.all_chain, [2001])
        self.assertEqual(s_2024.part_chain, [2001])

    def test_bulk_create_and_scheduled_task_auto_sync(self):
        from standards.tasks import auto_sync_version_chains_task

        objs = [
            Standard(
                id=3001,
                standard_no='Q/BULK 001-2020',
                clean_id='Q/BULK001-2020',
                type='enterprise',
                company=self.comp_a,
                status='active',
            ),
            Standard(
                id=3002,
                standard_no='Q/BULK 001-2025',
                clean_id='Q/BULK001-2025',
                type='enterprise',
                company=self.comp_a,
                status='active',
            ),
            Standard(
                id=3003,
                standard_no='Q/NOLINK',
                clean_id='Q/NOLINK',
                type='enterprise',
                company=self.comp_a,
                status='active',
            ),
        ]
        Standard.objects.bulk_create(objs)
        sync_version_chains_for_standards(objs)

        self.assertEqual(Standard.objects.get(pk=3001).all_chain, [3002, 3001])
        self.assertEqual(Standard.objects.get(pk=3001).part_chain, [3001])
        self.assertEqual(Standard.objects.get(pk=3002).all_chain, [3002, 3001])
        self.assertEqual(Standard.objects.get(pk=3002).part_chain, [3002, 3001])
        self.assertEqual(Standard.objects.get(pk=3003).all_chain, [3003])

        # 模拟绕过信号直接写入空 all_chain，由定时兜底任务自动修复
        Standard.objects.bulk_create([
            Standard(
                id=3004,
                standard_no='Q/BULK 001-2026',
                clean_id='Q/BULK001-2026',
                type='enterprise',
                company=self.comp_a,
                status='active',
            )
        ])
        task_res = auto_sync_version_chains_task()
        self.assertGreaterEqual(task_res['applied_count'], 3)
        self.assertEqual(Standard.objects.get(pk=3004).all_chain, [3004, 3002, 3001])
        self.assertEqual(Standard.objects.get(pk=3004).part_chain, [3004, 3002])
        self.assertEqual(Standard.objects.get(pk=3002).all_chain, [3004, 3002, 3001])
        self.assertEqual(Standard.objects.get(pk=3001).all_chain, [3004, 3002, 3001])
