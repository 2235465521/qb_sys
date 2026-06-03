from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
import datetime

from .models import UsageLog
from .middleware import get_action_desc, get_client_ip

AdminUser = get_user_model()

class UsageLogModelTestCase(TestCase):
    def setUp(self):
        self.user = AdminUser.objects.create_user(
            username='test_auditor', 
            password='testpassword',
            real_name='审计测试员',
            role='admin'
        )

    def test_log_creation(self):
        log = UsageLog.objects.create(
            user=self.user,
            username=self.user.username,
            real_name=self.user.real_name,
            ip_address='127.0.0.1',
            path='/api/client/standards/5/download/',
            method='GET',
            action='前台下载企标PDF',
            status_code=200,
            duration=0.045
        )
        self.assertEqual(UsageLog.objects.count(), 1)
        self.assertEqual(log.username, 'test_auditor')
        self.assertFalse(log.is_warning)


class UsageLogViewsTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = AdminUser.objects.create_superuser(
            username='admin_boss', 
            password='superpassword',
            real_name='老板'
        )
        self.client.force_authenticate(user=self.admin)
        
        # Create some dummy logs
        UsageLog.objects.create(
            user=self.admin,
            username=self.admin.username,
            real_name=self.admin.real_name,
            ip_address='127.0.0.1',
            path='/api/client/standards/',
            method='GET',
            action='前台查询企标列表',
            status_code=200,
            duration=0.05
        )
        UsageLog.objects.create(
            username='Anonymous',
            real_name='未登录用户',
            ip_address='192.168.1.100',
            path='/api/auth/login/',
            method='POST',
            action='用户登录',
            status_code=200,
            duration=0.12
        )

    def test_summary_view(self):
        url = reverse('admin-statistics-summary')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.data
        self.assertEqual(data['total_hits'], 2) # Note: middleware logs client request, so the test request itself to /api/admin/statistics/summary/ is NOT logged because we filtered it out! But wait, let's see. We had 2 dummy logs in setup.
        # Oh, in the test run, did middleware run? In rest_framework APIClient, middleware might run. Let's see how many logs we have.
        # It should be at least 2.
        self.assertGreaterEqual(data['total_hits'], 2)
        self.assertEqual(data['today_hits'], data['total_hits'])

    def test_charts_view(self):
        url = reverse('admin-statistics-charts')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('trend', response.data)
        self.assertIn('top_users', response.data)
        self.assertIn('hourly_distribution', response.data)

    def test_logs_list_view(self):
        url = reverse('admin-statistics-logs')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('results', response.data)
        self.assertGreaterEqual(len(response.data['results']), 2)
