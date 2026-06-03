from rest_framework import serializers
from .models import UsageLog

class UsageLogSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S")
    user_role_display = serializers.SerializerMethodField()

    class Meta:
        model = UsageLog
        fields = [
            'id', 'user', 'username', 'real_name', 'user_role_display',
            'ip_address', 'path', 'method', 'action', 'keyword',
            'target_id', 'status_code', 'duration', 'is_warning', 'created_at'
        ]

    def get_user_role_display(self, obj):
        if obj.user:
            return obj.user.get_role_display()
        return "外部访客"
