from django.db import models
from django.conf import settings

class UsageLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='usage_logs',
        verbose_name='操作用户'
    )
    username = models.CharField('用户名', max_length=150, blank=True)
    real_name = models.CharField('真实姓名', max_length=150, blank=True)
    ip_address = models.CharField('IP地址', max_length=45, blank=True)
    path = models.CharField('请求路径', max_length=255)
    method = models.CharField('请求方式', max_length=10)
    action = models.CharField('操作描述', max_length=100)
    keyword = models.CharField('检索词', max_length=255, blank=True, db_index=True)
    target_id = models.CharField('目标ID', max_length=100, blank=True, db_index=True)
    status_code = models.IntegerField('状态码')
    duration = models.FloatField('耗时(秒)')
    is_warning = models.BooleanField('是否异常下载/越权警报', default=False, db_index=True)
    created_at = models.DateTimeField('操作时间', auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'statistics_usage_log'
        ordering = ['-created_at']
        verbose_name = '使用日志'
        verbose_name_plural = '使用日志'
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['username']),
            models.Index(fields=['action']),
            models.Index(fields=['is_warning']),
        ]

    def __str__(self):
        return f"{self.username or 'Anonymous'} - {self.action} - {self.created_at}"
