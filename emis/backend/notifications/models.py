"""
notifications App — 短信通知模型

包含：
  SmsTemplate  — 短信模板（后台管理员配置）
  SmsTask      — 短信发送任务（含 Celery 异步状态跟踪）
  SmsLog       — 单条短信发送日志（含重试记录）
"""

from django.db import models
from users.models import Member


class SmsTemplate(models.Model):
    """
    短信模板

    模板内容支持变量替换，如：
    "尊敬的{name}，您好！您所在的{company}的会员资格即将到期..."
    """

    name = models.CharField('模板名称', max_length=100)
    content = models.TextField(
        '模板内容',
        help_text='支持变量: {name}=姓名, {company}=单位, {phone}=手机号'
    )
    is_active = models.BooleanField(
        '是否已审核可用', default=False,
        help_text='审核通过后方可被任务引用'
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'notifications_sms_template'
        verbose_name = '短信模板'
        verbose_name_plural = '短信模板列表'

    def __str__(self):
        return self.name

    def render(self, member: Member) -> str:
        """用会员信息渲染模板内容"""
        return self.content.format(
            name=member.name,
            company=member.company,
            phone=member.phone,
        )


class SmsTask(models.Model):
    """
    短信发送任务（每次触发一个任务）

    任务由 Celery Beat 在指定时间触发，
    或由管理员手动在前台创建立即执行。
    """

    STATUS_CHOICES = [
        ('pending', '待执行'),
        ('running', '执行中'),
        ('done', '已完成'),
        ('failed', '失败'),
        ('partial', '部分成功'),
    ]

    TARGET_GROUP_CHOICES = [
        ('all_active', '全部正常会员'),
        ('specific_company', '指定单位会员'),
        ('custom', '自定义手机号列表'),
    ]

    template = models.ForeignKey(
        SmsTemplate, on_delete=models.PROTECT,
        related_name='tasks', verbose_name='使用模板'
    )
    target_group = models.CharField(
        '目标群体', max_length=30,
        choices=TARGET_GROUP_CHOICES, default='all_active'
    )
    target_company = models.CharField(
        '指定单位（target_group=specific_company时填写）',
        max_length=200, blank=True
    )

    # Celery 任务 ID（用于查询异步任务状态）
    celery_task_id = models.CharField('Celery 任务ID', max_length=100, blank=True)

    scheduled_time = models.DateTimeField('计划执行时间', null=True, blank=True)
    started_at = models.DateTimeField('实际开始时间', null=True, blank=True)
    finished_at = models.DateTimeField('完成时间', null=True, blank=True)

    status = models.CharField('任务状态', max_length=20, choices=STATUS_CHOICES, default='pending')

    total_count = models.PositiveIntegerField('总发送目标数', default=0)
    sent_count = models.PositiveIntegerField('成功发送数', default=0)
    failed_count = models.PositiveIntegerField('失败数', default=0)

    created_by = models.CharField('创建人', max_length=50, blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        db_table = 'notifications_sms_task'
        verbose_name = '短信任务'
        verbose_name_plural = '短信任务列表'
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.get_status_display()}] {self.template.name} @ {self.scheduled_time}'


class SmsLog(models.Model):
    """
    单条短信发送日志（含重试记录）

    每个会员的每次发送都记录在此，
    失败记录包含错误信息，支持重试机制。
    """

    STATUS_CHOICES = [
        ('success', '成功'),
        ('failed', '失败'),
        ('retry', '重试中'),
    ]

    task = models.ForeignKey(
        SmsTask, on_delete=models.CASCADE,
        related_name='logs', verbose_name='所属任务'
    )
    member = models.ForeignKey(
        Member, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='sms_logs', verbose_name='目标会员'
    )
    phone = models.CharField('目标手机号', max_length=20)
    content = models.TextField('实际发送内容')

    status = models.CharField('发送状态', max_length=20, choices=STATUS_CHOICES)
    error_message = models.TextField('错误信息', blank=True)
    retry_count = models.PositiveSmallIntegerField('重试次数', default=0)

    sent_at = models.DateTimeField('发送时间', auto_now_add=True)

    class Meta:
        db_table = 'notifications_sms_log'
        verbose_name = '短信发送日志'
        verbose_name_plural = '短信发送日志'
        ordering = ['-sent_at']

    def __str__(self):
        return f'{self.phone} - {self.get_status_display()}'
