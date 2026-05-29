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
            assignee=self.user
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
                assignee=self.user
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


