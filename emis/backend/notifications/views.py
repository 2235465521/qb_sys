"""
notifications — 视图、序列化器
"""

from rest_framework import generics, serializers, status, permissions
from rest_framework.response import Response
from .models import SmsTemplate, SmsTask


class SmsTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SmsTemplate
        fields = ['id', 'name', 'content', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class SmsTaskSerializer(serializers.ModelSerializer):
    template_name = serializers.CharField(source='template.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = SmsTask
        fields = [
            'id', 'template', 'template_name', 'target_group', 'target_company',
            'celery_task_id', 'scheduled_time', 'started_at', 'finished_at',
            'status', 'status_display', 'total_count', 'sent_count', 'failed_count',
            'created_by', 'created_at',
        ]
        read_only_fields = ['id', 'celery_task_id', 'started_at', 'finished_at',
                            'status', 'total_count', 'sent_count', 'failed_count', 'created_at']


class SmsTemplateListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SmsTemplateSerializer
    queryset = SmsTemplate.objects.all()


class SmsTemplateDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SmsTemplateSerializer
    queryset = SmsTemplate.objects.all()


class SmsTaskListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SmsTaskSerializer
    queryset = SmsTask.objects.select_related('template').all()

    def perform_create(self, serializer):
        """创建任务后立即提交 Celery 异步执行"""
        task_obj = serializer.save(
            created_by=str(self.request.user),
            status='pending',
        )
        from standards.tasks import send_sms_task
        celery_result = send_sms_task.delay(task_id=task_obj.id)
        task_obj.celery_task_id = celery_result.id
        task_obj.save(update_fields=['celery_task_id'])


class SmsTaskDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SmsTaskSerializer
    queryset = SmsTask.objects.select_related('template').all()
