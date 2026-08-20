from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken
from companies.models import Lead, FollowUp, Attachment, Company

User = get_user_model()

class LeadAPITests(APITestCase):
    def setUp(self):
        # Create a test user
        self.user = User.objects.create_user(
            username='admin_test',
            password='password123',
            is_staff=True,
            is_superuser=True
        )
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        
        # Create a test company
        self.company = Company.objects.create(
            name="测试企业",
            credit_code="91110000MA00000000",
            status="active"
        )
        
        # Create a test lead
        self.lead = Lead.objects.create(
            source="phone",
            req_type="general_inquiry",
            status="pending",
            contact_name="小张",
            contact_phone="13800000000",
            enterprise=self.company,
            assignee=self.user.username
        )

    def test_lead_list_and_detail(self):
        url = reverse('admin-lead-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['contact_name'], '小张')

        detail_url = reverse('admin-lead-detail', kwargs={'pk': self.lead.id})
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['contact_name'], '小张')

    def test_lead_create_with_files(self):
        url = reverse('admin-lead-list')
        file1 = SimpleUploadedFile("test_doc.pdf", b"pdf content", content_type="application/pdf")
        file2 = SimpleUploadedFile("test_img.png", b"png content", content_type="image/png")
        
        data = {
            'source': 'wechat',
            'req_type': 'business_cooperation',
            'status': 'pending',
            'contact_name': '李经理',
            'contact_phone': '13900000000',
            'enterprise': self.company.id,
            'files': [file1, file2]
        }
        
        response = self.client.post(url, data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify Lead is created and attachments are linked
        new_lead = Lead.objects.get(contact_name='李经理')
        self.assertEqual(new_lead.attachments.count(), 2)
        filenames = [att.filename for att in new_lead.attachments.all()]
        self.assertIn("test_doc.pdf", filenames)
        self.assertIn("test_img.png", filenames)

    def test_status_change_creates_log(self):
        url = reverse('admin-lead-detail', kwargs={'pk': self.lead.id})
        # Change status from pending to following
        response = self.client.patch(url, {'status': 'following'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify system log follow-up is created
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, 'following')
        
        followups = FollowUp.objects.filter(lead=self.lead)
        self.assertEqual(followups.count(), 1)
        self.assertIn("[系统日志] 负责人将线索状态变更为：跟进中", followups.first().content)

    def test_add_followup_and_attachments(self):
        url = reverse('admin-lead-followup', kwargs={'pk': self.lead.id})
        file_obj = SimpleUploadedFile("contract_draft.docx", b"word doc content", content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        
        data = {
            'content': '今天进行了电话初访，客户很有意向。',
            'files': [file_obj]
        }
        
        response = self.client.post(url, data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify followup was created
        self.assertEqual(self.lead.followups.count(), 1)
        self.assertEqual(self.lead.followups.first().content, '今天进行了电话初访，客户很有意向。')
        
        # Verify attachment was created
        self.assertEqual(self.lead.attachments.count(), 1)
        self.assertEqual(self.lead.attachments.first().filename, 'contract_draft.docx')

        # Test deleting the attachment
        attachment = self.lead.attachments.first()
        delete_url = reverse('admin-lead-delete-attachment', kwargs={'pk': self.lead.id})
        delete_response = self.client.post(delete_url, {'attachment_id': attachment.id}, format='json')
        self.assertEqual(delete_response.status_code, status.HTTP_200_OK)
        self.assertEqual(Attachment.objects.filter(lead=self.lead).count(), 0)

        # Test deleting the attachment using the new RESTful DELETE API
        new_att = Attachment.objects.create(
            lead=self.lead,
            filename='test_delete_rest.txt',
            size=100
        )
        self.assertEqual(Attachment.objects.filter(lead=self.lead).count(), 1)
        
        rest_delete_url = reverse('admin-lead-attachment-detail', kwargs={'pk': new_att.id})
        rest_delete_response = self.client.delete(rest_delete_url)
        self.assertEqual(rest_delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Attachment.objects.filter(lead=self.lead).count(), 0)

    def test_lead_export(self):
        url = reverse('admin-lead-export')
        # GET export
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        
        # POST export (advanced selection)
        data = {
            'export_scope': 'selected',
            'ids': [self.lead.id],
            'selected_fields': ['contact_name', 'contact_phone', 'status']
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    def test_lead_export_performance_and_query_count(self):
        # Bulk create 500 mock leads to simulate real load
        leads = [
            Lead(
                source='phone',
                req_type='general_inquiry',
                status='pending',
                contact_name=f'联系人_{i}',
                contact_phone=f'1380000{i:04d}',
                enterprise=self.company,
                assignee=self.user.username
            ) for i in range(500)
        ]
        Lead.objects.bulk_create(leads)
        
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        import time
        
        url = reverse('admin-lead-export')
        
        # Capture queries and measure duration
        with CaptureQueriesContext(connection) as ctx:
            start_time = time.time()
            response = self.client.post(url, {
                'export_scope': 'query',
                'selected_fields': ['contact_name', 'contact_phone', 'status', 'assignee', 'enterprise']
            }, format='json')
            duration = time.time() - start_time

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify execution is extremely fast (under 1.0 second under normal conditions, limit set to 2.0 to avoid CI flakiness)
        self.assertLess(duration, 2.0)
        
        # Confirm N+1 query issue is prevented (query count should be small, typically < 6 with select_related and prefetch_related disabled)
        self.assertLess(len(ctx.captured_queries), 8)

    def test_company_quick_create(self):
        url = reverse('admin-company-quick-create')
        
        # 1. Create with only name (credit_code should be auto-generated starting with TEMP_)
        data = {'name': '快捷测试新企业'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], '快捷测试新企业')
        self.assertTrue(response.data['credit_code'].startswith('TEMP_'))
        
        # 2. Create with existing name (should return existing company)
        response2 = self.client.post(url, data, format='json')
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertEqual(response2.data['id'], response.data['id'])
        
        # 3. Create with name and credit_code
        data3 = {'name': '快捷另一个企业', 'credit_code': '91110000MA88888888'}
        response3 = self.client.post(url, data3, format='json')
        self.assertEqual(response3.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response3.data['name'], '快捷另一个企业')
        self.assertEqual(response3.data['credit_code'], '91110000MA88888888')
        
        # 4. Create with existing credit_code (should return existing company)
        data4 = {'name': '随便名字', 'credit_code': '91110000MA88888888'}
        response4 = self.client.post(url, data4, format='json')
        self.assertEqual(response4.status_code, status.HTTP_200_OK)
        self.assertEqual(response4.data['id'], response3.data['id'])


class OwnershipCategoryTests(APITestCase):
    databases = '__all__'

    def setUp(self):
        self.user = User.objects.create_user(
            username='admin_owner',
            password='password123',
            is_staff=True,
            is_superuser=True
        )
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

        from companies.models import CompanyCategory
        self.main_cat = CompanyCategory.objects.create(
            code='state_owned',
            name='国有企业',
            category_type='main',
            badge_color='blue',
            sort_order=10,
            definition='国有企业主分类'
        )
        self.sub_cat = CompanyCategory.objects.create(
            code='central_soe',
            name='央企',
            category_type='sub',
            parent=self.main_cat,
            badge_color='blue',
            sort_order=11,
            definition='国务院国资委履行出资人职责的企业'
        )

        self.company = Company.objects.create(
            name="中国石油天然气集团有限公司",
            credit_code="91110000MA11111111",
            status="active",
            company_type="有限责任公司(国有独资)"
        )

    def test_category_dict_api(self):
        url = reverse('dict-categories')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 2)

    def test_ownership_tag_service_rules(self):
        from companies.ownership_service import OwnershipTagService
        tags = OwnershipTagService.predict_and_assign_by_rules(self.company)
        self.assertTrue(self.company.ownership_categories.filter(code='state_owned').exists())

    def test_company_batch_tag(self):
        url = reverse('admin-company-batch-tag')
        data = {
            'company_ids': [self.company.id],
            'category_ids': [self.sub_cat.id],
            'action': 'add'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(self.company.ownership_categories.filter(code='central_soe').exists())
        self.assertTrue(self.company.ownership_categories.filter(code='state_owned').exists())

    def test_company_filter_by_category(self):
        self.company.ownership_categories.add(self.main_cat, self.sub_cat)
        url = reverse('admin-company-list')
        response = self.client.get(url, {'category_code': 'state_owned'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['ownership_categories'][0]['code'], 'state_owned')

    def test_company_sync_ownership_endpoint(self):
        url = reverse('admin-company-sync-ownership', kwargs={'pk': self.company.id})
        response = self.client.post(url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(len(response.data['tags']) > 0)

    def test_funnel_classification_all_tiers(self):
        from companies.ownership_service import OwnershipTagService

        # 1. 确定性民营企业
        res_private = OwnershipTagService.funnel_classify("北京某某科技有限公司", "有限责任公司(自然人投资或控股)")
        self.assertEqual(res_private['tier'], 1)
        self.assertIn('private', res_private['tag_codes'])

        # 2. 确定性外资企业
        res_foreign = OwnershipTagService.funnel_classify("某某(中国)投资有限公司", "有限责任公司(中外合资)")
        self.assertEqual(res_foreign['tier'], 1)
        self.assertIn('foreign_invested', res_foreign['tag_codes'])

        # 3. 央企白名单
        res_central = OwnershipTagService.funnel_classify("中国石油天然气股份有限公司吉林分公司", "分公司")
        self.assertEqual(res_central['tier'], 1)
        self.assertIn('state_owned', res_central['tag_codes'])

        # 4. Tier 2 存疑国资/城投企业 (之前抛出 NameError kw 的代码分支)
        res_ambiguous = OwnershipTagService.funnel_classify("某某市城市建设投资控股集团有限公司", "有限责任公司")
        self.assertEqual(res_ambiguous['tier'], 2)
        self.assertTrue(res_ambiguous['is_ambiguous'])
        self.assertIn('投资控股', res_ambiguous['ambiguity_reason'])




