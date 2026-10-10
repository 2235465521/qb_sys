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
