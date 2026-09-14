from django.test import TestCase
from django.conf import settings
from rest_framework.test import APIClient
from rest_framework import status
from companies.models import Company, Province, City
from standards.models import Standard
import datetime

class DoubaoConnectorAPITestCase(TestCase):
    databases = '__all__'

    def setUp(self):
        self.client = APIClient()
        self.api_key = getattr(settings, 'DOUBAO_API_KEY', 'emis_doubao_secret_key_2026')

        # 创建基础省市字典
        self.province = Province.objects.create(code='440000', name='广东省')
        self.city = City.objects.create(province=self.province, code='440300', name='深圳市')

        # 创建主测试企业（标准较多）
        self.company_main = Company.objects.create(
            name="深圳市测试科技有限公司",
            credit_code="91440300MA5TEST01",
            legal_person="张三",
            province=self.province,
            city=self.city,
            standards_count=2
        )

        # 创建同名子公司/关联公司（用于测试消歧）
        self.company_sub = Company.objects.create(
            name="深圳市测试科技软件有限公司",
            credit_code="91440300MA5TEST02",
            legal_person="李四",
            province=self.province,
            city=self.city,
            standards_count=0
        )

        # 创建该企业名下的企标与团标
        self.std_ent = Standard.objects.create(
            standard_no="Q/TEST 001-2024",
            clean_id="Q/TEST 001-2024",
            title="智能设备数据传输规范",
            type="enterprise",
            status="active",
            company=self.company_main,
            publish_date=datetime.date(2024, 1, 15),
            implement_date=datetime.date(2024, 2, 1),
            disk_filename="test/std01.pdf"
        )

        self.std_grp = Standard.objects.create(
            standard_no="T/TEST 002-2023",
            clean_id="T/TEST 002-2023",
            title="物联网终端能耗评级要求",
            type="group",
            status="deprecated",
            company=self.company_main,
            publish_date=datetime.date(2023, 5, 10),
            implement_date=datetime.date(2023, 6, 1)
        )

    def test_schema_endpoint(self):
        """测试 Schema 接口可正常匿名访问并返回 OpenAPI 规范"""
        res = self.client.get('/api/open/doubao/schema/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertEqual(data.get('openapi'), '3.0.0')
        self.assertIn('/api/open/doubao/company-standards/', data.get('paths', {}))

    def test_auth_failure_when_missing_or_wrong_key(self):
        """测试未携带或携带错误 API Key 时的 401 拦截"""
        # 1. 没有任何 key
        res = self.client.get('/api/open/doubao/company-standards/?company_name=测试科技')
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

        # 2. 错误的 key
        res = self.client.get(
            '/api/open/doubao/company-standards/?company_name=测试科技',
            HTTP_AUTHORIZATION="Bearer wrong_token_123"
        )
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_bad_request_without_company_name(self):
        """测试携带正确 key 但缺少 company_name 时返回 400"""
        res = self.client.get(
            '/api/open/doubao/company-standards/',
            HTTP_AUTHORIZATION=f"Bearer {self.api_key}"
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_successful_query_with_disambiguation(self):
        """测试正常查询、智能主匹配及消歧候选列表"""
        res = self.client.get(
            '/api/open/doubao/company-standards/?company_name=测试科技',
            HTTP_AUTHORIZATION=f"Bearer {self.api_key}"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertTrue(data['matched'])

        # 验证主匹配企业（优先标准总数多的）
        self.assertEqual(data['company']['name'], "深圳市测试科技有限公司")
        self.assertEqual(data['company']['credit_code'], "91440300MA5TEST01")
        self.assertEqual(data['total_standards'], 2)
        self.assertEqual(len(data['standards']), 2)

        # 验证返回的标准信息
        std_nos = [s['standard_no'] for s in data['standards']]
        self.assertIn("Q/TEST 001-2024", std_nos)
        self.assertIn("T/TEST 002-2023", std_nos)

        # 验证下载链接生成（有物理文件路径时应有 download_url）
        std_01 = next(s for s in data['standards'] if s['standard_no'] == "Q/TEST 001-2024")
        self.assertTrue(std_01['has_pdf'])
        self.assertIn("/api/open/doubao/download/", std_01['download_url'])

        # 验证候选企业消歧列表
        self.assertEqual(len(data['candidate_companies']), 1)
        self.assertEqual(data['candidate_companies'][0]['name'], "深圳市测试科技软件有限公司")

    def test_filter_by_standard_type_and_status(self):
        """测试按标准类型和状态过滤"""
        # 仅查询现行的企标
        res = self.client.get(
            '/api/open/doubao/company-standards/?company_name=测试科技&standard_type=enterprise&status=active',
            HTTP_AUTHORIZATION=f"Bearer {self.api_key}"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertEqual(data['total_standards'], 1)
        self.assertEqual(data['standards'][0]['standard_no'], "Q/TEST 001-2024")

    def test_download_auth(self):
        """测试下载接口鉴权"""
        # 错误 key -> 401
        res = self.client.get(f"/api/open/doubao/download/{self.std_ent.id}/?key=wrong_key")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_federated_search_shanghai_institute(self):
        """测试跨库联邦检索上海市质量监督检验技术研究院"""
        res = self.client.get(
            '/api/open/doubao/company-standards/?company_name=上海市质量监督检验技术研究院',
            HTTP_AUTHORIZATION=f"Bearer {self.api_key}"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertTrue(data['matched'])
        self.assertIn("上海市质量监督检验技术研究院", data['company']['name'])
        self.assertEqual(data['company']['credit_code'], "123100007895625792")
        self.assertEqual(data['company']['legal_person'], "王虎")
        self.assertGreaterEqual(data['total_standards'], 700)
        self.assertGreater(len(data['standards']), 0)

    def test_federated_search_byd(self):
        """测试跨库联邦检索比亚迪"""
        res = self.client.get(
            '/api/open/doubao/company-standards/?company_name=比亚迪',
            HTTP_AUTHORIZATION=f"Bearer {self.api_key}"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertTrue(data['matched'])
        self.assertGreaterEqual(data['total_standards'], 500)
