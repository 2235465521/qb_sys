import io
import openpyxl
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

User = get_user_model()

class SniffExcelRegressionTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user, _ = User.objects.get_or_create(username='diag_user', defaults={'is_active': True})
        self.client.force_authenticate(user=self.user)

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["标准编号", "标准名称"])
        ws.append(["Q/TEST 001-2023", "测试产品标准"])
        buf = io.BytesIO()
        wb.save(buf)
        self.xlsx_bytes = buf.getvalue()

    def test_sniff_with_wrong_content_type_rejected_cleanly(self):
        """
        验证当客户端未发送 multipart/form-data（例如误传 application/json）时，
        后端通过 parser_classes 明确拒绝 (415 Unsupported Media Type)，不再崩溃解码
        """
        response = self.client.post(
            '/api/client/standards/sniff-excel/',
            data=b'{}',
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 415)

    def test_sniff_with_multipart_format_success(self):
        """
        验证标准 multipart/form-data 上传 .xlsx 正常解析返回 200 与列映射
        """
        file = SimpleUploadedFile(
            "test.xlsx",
            self.xlsx_bytes,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response = self.client.post(
            '/api/client/standards/sniff-excel/',
            data={'file': file},
            format='multipart'
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('headers', response.data)
        self.assertEqual(response.data['suggested_std_no_col'], 'A')
        self.assertEqual(response.data['suggested_title_col'], 'B')
        self.assertEqual(response.data['total_rows'], 1)

    def test_sniff_empty_file_rejected(self):
        """
        验证上传空文件或未带 file 字段时友好返回 400
        """
        response = self.client.post(
            '/api/client/standards/sniff-excel/',
            data={},
            format='multipart'
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data.get('error'), '请上传 Excel 文件')

    def test_list_match_preview_with_multipart_file_upload(self):
        """
        验证第二阶段 ListMatchPreviewView 通过 multipart 上传 Excel 文件能正常返回分析预览
        """
        file = SimpleUploadedFile(
            "test.xlsx",
            self.xlsx_bytes,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response = self.client.post(
            '/api/client/standards/list-match-preview/',
            data={
                'file': file,
                'std_no_col_idx': 0,
                'title_col_idx': 1,
                'header_row_idx': 0
            },
            format='multipart'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['total_input'], 1)
        self.assertIn('details', response.data)

    def test_false_positive_pdf_prevention(self):
        """
        验证当数据库记录中 disk_filename 指向磁盘不存在的路径时，
        check_standard_has_pdf 严谨返回 False，杜绝假阳性标记
        """
        from standards.models import Standard
        from standards.services_list_match import check_standard_has_pdf

        std = Standard(
            standard_no="Q/FAKE 001-2024",
            title="不存在物理文件的测试标准",
            type="enterprise",
            disk_filename="fake/path/does_not_exist_9999.pdf"
        )
        self.assertFalse(check_standard_has_pdf(std))

    def test_title_fallback_with_english_prefix(self):
        """
        验证当输入以英文前缀命名的标准标题（如 LED平板灯）且未带有效标准号时，
        第二层降级策略能够准确命中该标准，不发生误判漏检
        """
        from standards.models import Standard
        from standards.services_list_match import match_single_item

        std = Standard.objects.create(
            standard_no="Q/LED 001-2023",
            title="LED平板灯技术要求",
            type="enterprise",
            status="active"
        )

        candidate, mode = match_single_item(raw_no="LED平板灯技术要求", raw_title="LED平板灯技术要求")
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.id, std.id)
        self.assertEqual(mode, 'title_fallback')

    def test_export_manifest_endpoint_and_filename(self):
        """
        验证交付回执清单导出端点返回正确的 Content-Disposition 标头
        """
        response = self.client.post(
            '/api/client/standards/export-match-manifest/',
            data={
                'details': [
                    {
                        'index': 1,
                        'input_no': 'Q/TEST 001-2023',
                        'input_title': '测试标准',
                        'status_text': '标准号精确命中',
                        'matched_no': 'Q/TEST 001-2023',
                        'matched_title': '测试标准',
                        'company_name': '测试企业',
                        'status_label': '现行',
                        'publish_date': '2023-01-01',
                        'has_pdf': True
                    }
                ]
            },
            format='json'
        )
        import urllib.parse
        self.assertEqual(response.status_code, 200)
        self.assertIn('Content-Disposition', response.headers)
        self.assertIn('企标匹配交付回执清单.xlsx', urllib.parse.unquote(response.headers['Content-Disposition']))
