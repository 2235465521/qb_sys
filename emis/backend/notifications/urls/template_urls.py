"""
notifications.urls.template_urls — 短信模板路由（后台）
"""

from django.urls import path
from notifications.views import SmsTemplateListCreateView, SmsTemplateDetailView

urlpatterns = [
    path('', SmsTemplateListCreateView.as_view(), name='sms-template-list'),
    path('<int:pk>/', SmsTemplateDetailView.as_view(), name='sms-template-detail'),
]
