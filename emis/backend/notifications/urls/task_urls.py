"""
notifications.urls.task_urls — 短信任务路由（模块三）
"""

from django.urls import path
from notifications.views import SmsTaskListCreateView, SmsTaskDetailView

urlpatterns = [
    path('tasks/', SmsTaskListCreateView.as_view(), name='sms-task-list'),
    path('tasks/<int:pk>/', SmsTaskDetailView.as_view(), name='sms-task-detail'),
]
