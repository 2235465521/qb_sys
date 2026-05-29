"""
companies App — 企业信息模型

包含：
  Province / City / District  — 三级行政区划字典
  Company                     — 企业主表
"""

from django.db import models
from django.conf import settings


# ============================================================
# 行政区划字典（三级联动）
# ============================================================

class Province(models.Model):
    """省级行政区"""
    code = models.CharField('区划代码', max_length=10, unique=True)
    name = models.CharField('省份名称', max_length=20)
    latitude = models.DecimalField('纬度', max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField('经度', max_digits=10, decimal_places=7, null=True, blank=True)

    class Meta:
        db_table = 'dict_province'
        verbose_name = '省份'
        ordering = ['code']

    def __str__(self):
        return self.name


class City(models.Model):
    """市级行政区"""
    province = models.ForeignKey(Province, on_delete=models.CASCADE, related_name='cities')
    code = models.CharField('区划代码', max_length=10, unique=True)
    name = models.CharField('城市名称', max_length=30)
    latitude = models.DecimalField('纬度', max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField('经度', max_digits=10, decimal_places=7, null=True, blank=True)

    class Meta:
        db_table = 'dict_city'
        verbose_name = '城市'
        ordering = ['code']

    def __str__(self):
        return self.name


class District(models.Model):
    """县/区级行政区"""
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='districts')
    code = models.CharField('区划代码', max_length=10, unique=True)
    name = models.CharField('区县名称', max_length=30)
    latitude = models.DecimalField('纬度', max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField('经度', max_digits=10, decimal_places=7, null=True, blank=True)

    class Meta:
        db_table = 'dict_district'
        verbose_name = '区县'
        ordering = ['code']

    def __str__(self):
        return self.name


# ============================================================
# 企业信息主表
# ============================================================

class Company(models.Model):
    """企业信息"""

    STATUS_CHOICES = [
        ('active', '正常'),
        ('disabled', '禁用'),
    ]

    name = models.CharField('企业名称', max_length=200, db_index=True)
    credit_code = models.CharField('统一社会信用代码', max_length=25, unique=True)
    legal_person = models.CharField('法人', max_length=50, blank=True)

    # 行政区划（存储名称方便显示，外键方便联动）
    province = models.ForeignKey(
        Province, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='companies', verbose_name='省份'
    )
    city = models.ForeignKey(
        City, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='companies', verbose_name='城市'
    )
    district = models.ForeignKey(
        District, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='companies', verbose_name='区县'
    )

    # LBS 坐标（用于空间检索）
    latitude = models.DecimalField(
        '纬度', max_digits=10, decimal_places=7,
        null=True, blank=True, db_index=True
    )
    longitude = models.DecimalField(
        '经度', max_digits=10, decimal_places=7,
        null=True, blank=True, db_index=True
    )

    contact = models.CharField('联系方式', max_length=100, blank=True)
    address = models.CharField('详细地址', max_length=500, blank=True)

    # ── 模块二新增 16 个企业库扩展字段 ────────────────────────
    established_date = models.DateField('成立日期', null=True, blank=True, help_text='企业或机构的成立日期')
    registered_address = models.CharField('注册地址', max_length=500, blank=True, help_text='企业营业执照上的注册地址')
    registered_zipcode = models.CharField('注册地址邮编', max_length=20, blank=True, help_text='注册地址对应的邮政编码')
    valid_mobile = models.CharField('有效手机号', max_length=50, blank=True, help_text='主要联系手机号码，用于接收重要推送或通知')
    more_phones = models.CharField('更多电话', max_length=200, blank=True, help_text='其他备用联系电话')
    email = models.EmailField('邮箱', blank=True, help_text='企业的官方或联系邮箱')
    company_type = models.CharField('企业(机构)类型', max_length=100, blank=True, help_text='例如：有限责任公司、股份有限公司等')
    registration_no = models.CharField('注册号', max_length=100, blank=True, help_text='工商注册号')
    organization_code = models.CharField('组织机构代码', max_length=100, blank=True, help_text='组织机构代码证编号')
    industry_category = models.CharField('国标行业门类', max_length=100, blank=True, help_text='国标行业分类门类名称或代码')
    industry_major = models.CharField('国标行业大类', max_length=100, blank=True, help_text='国标行业分类大类')
    industry_middle = models.CharField('国标行业中类', max_length=100, blank=True, help_text='国标行业分类中类')
    industry_minor = models.CharField('国标行业小类', max_length=100, blank=True, help_text='国标行业分类小类')
    company_size = models.CharField('企业规模', max_length=50, blank=True, help_text='例如：大型、中型、小型、微型')
    english_name = models.CharField('英文名', max_length=200, blank=True, help_text='企业英文名称')
    former_names = models.CharField('曾用名', max_length=500, blank=True, help_text='企业历史曾用名')

    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='active')
    is_deleted = models.BooleanField('是否软删除', default=False, db_index=True)

    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'companies_company'
        verbose_name = '企业'
        verbose_name_plural = '企业列表'
        ordering = ['-created_at']
        indexes = [
            # 联合索引：省市查询优化
            models.Index(fields=['province', 'city', 'district'], name='idx_region'),
            # 联合索引：有效企业查询
            models.Index(fields=['is_deleted', 'status'], name='idx_status'),
        ]

    def __str__(self):
        return self.name

    def get_full_region(self):
        """返回完整行政区划字符串"""
        parts = []
        if self.province:
            parts.append(self.province.name)
        if self.city:
            parts.append(self.city.name)
        if self.district:
            parts.append(self.district.name)
        return ''.join(parts)


class Lead(models.Model):
    """
    Lead 线索模型
    升级旧版的 B2B CompanyLead 模型，用于管理全生命周期客户商机
    """
    DEFAULT_SOURCE_CHOICES = [
        ('wechat', '视频号/公众号'),
        ('phone', '电话咨询'),
        ('visit', '线下拜访'),
        ('other', '其他渠道'),
    ]

    DEFAULT_REQ_TYPE_CHOICES = [
        ('data_correction', '数据纠错'),
        ('business_cooperation', '业务合作'),
        ('general_inquiry', '常规咨询'),
    ]

    DEFAULT_STATUS_CHOICES = [
        ('pending', '待处理'),
        ('following', '跟进中'),
        ('solved', '已解决/已成单'),
        ('closed', '无效关闭'),
    ]

    source = models.CharField(
        '来源', 
        max_length=50, 
        default='other'
    )
    req_type = models.CharField(
        '诉求类型', 
        max_length=50, 
        default='general_inquiry'
    )
    status = models.CharField(
        '跟进状态', 
        max_length=50, 
        default='pending'
    )
    
    # 负责人现在存储为字符串，以支持非系统注册用户作为指派负责人
    assignee = models.CharField(
        '负责人',
        max_length=100,
        blank=True,
        null=True
    )
    
    # 关联企业库主表（非强制必选，常规咨询在成单前可先置空）
    enterprise = models.ForeignKey(
        'Company',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='leads',
        verbose_name='关联企业'
    )

    # 基础客户人脉字段
    contact_name = models.CharField('联系人姓名', max_length=100, blank=True)
    contact_phone = models.CharField('联系电话', max_length=100, blank=True)
    contact_wechat = models.CharField('联系微信', max_length=100, blank=True)

    created_at = models.DateTimeField('建立时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'companies_lead'  # 保持与原表名一致，方便平滑接管与迁移
        verbose_name = 'CRM客户线索'
        verbose_name_plural = 'CRM客户线索'
        ordering = ['-created_at']

    def get_source_display(self):
        return self._get_option_label('source', self.source)

    def get_req_type_display(self):
        return self._get_option_label('req_type', self.req_type)

    def get_status_display(self):
        return self._get_option_label('status', self.status)

    def _get_option_label(self, option_type, value):
        if not value:
            return ''
        try:
            opt = LeadOption.objects.filter(option_type=option_type, value=value, is_active=True).first()
            if opt:
                return opt.name
        except Exception:
            pass
        # Fallback to hardcoded defaults
        defaults = {
            'source': dict(self.DEFAULT_SOURCE_CHOICES),
            'req_type': dict(self.DEFAULT_REQ_TYPE_CHOICES),
            'status': dict(self.DEFAULT_STATUS_CHOICES),
        }
        return defaults.get(option_type, {}).get(value, value)

    def __str__(self):
        return f"{self.contact_name or '未知人'} - {self.get_status_display()}"


class FollowUp(models.Model):
    """
    FollowUp 跟进记录模型
    支持一条线索追加多条跟进动态时间轴
    """
    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE,
        related_name='followups',
        verbose_name='关联线索'
    )
    content = models.TextField('跟进内容')
    created_at = models.DateTimeField('跟进时间', auto_now_add=True)
    
    # 执行跟进的系统用户
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='followup_records',
        verbose_name='跟进人'
    )

    class Meta:
        db_table = 'companies_lead_followup'
        verbose_name = '线索跟进记录'
        verbose_name_plural = '线索跟进记录'
        ordering = ['created_at']  # 时间轴顺序列出

    def __str__(self):
        return f"{self.lead.contact_name} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"


class Attachment(models.Model):
    """
    Attachment 附件模型
    用于保存纠错凭证、合规授权书、合同草稿等存证文件
    """
    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE,
        related_name='attachments',
        verbose_name='关联线索'
    )
    # 文件物理上传路径限定，强制隔离命名空间
    file = models.FileField('附件文件', upload_to='leads/attachments/')
    filename = models.CharField('原始文件名', max_length=255)
    size = models.PositiveIntegerField('文件大小(Bytes)', default=0)
    created_at = models.DateTimeField('上传时间', auto_now_add=True)

    class Meta:
        db_table = 'companies_lead_attachment'
        verbose_name = '线索附件'
        verbose_name_plural = '线索附件'
        ordering = ['-created_at']

    def __str__(self):
        return self.filename


class LeadOption(models.Model):
    OPTION_TYPES = [
        ('req_type', '诉求类型'),
        ('source', '渠道来源'),
        ('status', '跟进状态'),
        ('assignee', '负责人'),
    ]
    option_type = models.CharField('配置项类型', max_length=20, choices=OPTION_TYPES)
    name = models.CharField('配置项名称/值', max_length=100)
    value = models.CharField('对应键值(英文码/名称值)', max_length=100)
    is_active = models.BooleanField('是否启用', default=True)
    sort_order = models.IntegerField('排序', default=0)

    class Meta:
        db_table = 'companies_lead_option'
        verbose_name = '线索自定义配置项'
        verbose_name_plural = '线索自定义配置项'
        unique_together = ('option_type', 'value')
        ordering = ['option_type', 'sort_order', 'name']

    def __str__(self):
        return f"{self.get_option_type_display()} - {self.name} ({self.value})"

