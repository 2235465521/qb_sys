"""
standards App — 标准信息模型

包含：
  Standard          — 企标/团标/国标主表
  NormativeReference — 规范性引用记录（模块二解析结果）
"""

from django.db import models
from companies.models import Company


def pdf_upload_path(instance, filename):
    """
    按技术栈文档规范：PDF 强制按日期分层存储
    路径格式: pdfs/YYYY/MM/DD/原始文件名
    例如: pdfs/2026/05/15/xQ_T_123-2026.pdf
    """
    from django.utils import timezone
    today = timezone.now().date()
    return f'pdfs/{today.strftime("%Y/%m/%d")}/{filename}'


class Standard(models.Model):
    """
    标准信息（企标/团标/国标统一存储）

    ⚠️ 关键规则：
    - standard_no: 原样存储，保留特殊前缀（如"新Q"、"DBY"）
    - clean_id: 清洗后的标准号，用于检索去重，但必须严格区分前缀
      例如: "新Q/T 123-2026" 和 "Q/T 123-2026" 的 clean_id 必须不同
    """

    TYPE_CHOICES = [
        ('enterprise', '企业标准'),  # 企标
        ('group', '团体标准'),        # 团标
        ('national', '国家标准'),    # 国标（被引用统计对象）
        ('industry', '行业标准'),    # 行标
        ('local', '地方标准'),       # 地标
    ]

    STATUS_CHOICES = [
        ('active', '现行'),
        ('deprecated', '废止'),
        ('upcoming', '即将实施'),
        ('draft', '草案'),
    ]


    # ── 标准号字段（核心）──────────────────────────────────
    standard_no = models.CharField(
        '标准号（原始）', max_length=200, db_index=True,
        help_text='保留原始标准号，包含特殊前缀如"新Q/T"、"DBY"等，禁止清洗'
    )
    clean_id = models.CharField(
        '标准号（标准化）', max_length=200, db_index=True,
        help_text='用于检索的标准化标准号，前缀必须严格保留以区分不同标准体系'
    )

    type = models.CharField('标准类型', max_length=20, choices=TYPE_CHOICES, default='enterprise')
    title = models.CharField('标准名称', max_length=500, blank=True)

    ics = models.CharField(
        'ICS分类号', max_length=100, blank=True, null=True, db_index=True,
        help_text='国际标准分类号，如 35.240.50'
    )
    ccs = models.CharField(
        'CCS分类号', max_length=100, blank=True, null=True, db_index=True,
        help_text='中国标准文献分类号，如 L70'
    )

    # 关联企业（国标无企业）
    company = models.ForeignKey(
        Company, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='standards', verbose_name='关联企业'
    )

    # ── 文件存储（技术栈文档规范：按日期分层）────────────
    pdf_file = models.FileField(
        '标准文件（PDF/Word）',
        upload_to=pdf_upload_path,
        max_length=500,
        null=True, blank=True
    )

    # ── 磁盘阵列文件相对路径 ──────────────────────────────
    # 存储相对于 SHARED_DISK_ROOT 的路径，例如：整合/Q_QJSB_JS022-2016_xxx.pdf
    # 文件本体永远在磁盘阵列，不进项目 media 目录
    disk_filename = models.CharField(
        '磁盘阵列文件路径',
        max_length=500,
        blank=True
    )

    # ── 解析状态（模块二）────────────────────────────────
    PARSE_STATUS_CHOICES = [
        ('unparsed', '暂未解析'),
        ('references_parsed', '已完成规范性引用解析'),
        ('indicators_parsed', '已完成指标解析'),
    ]

    is_parsed = models.CharField(
        '解析状态',
        max_length=50,
        choices=PARSE_STATUS_CHOICES,
        default='unparsed',
        db_index=True,
        help_text='标准解析状态'
    )


    # ── 国标引用统计（模块二热度排行）────────────────────
    citation_count = models.PositiveIntegerField(
        '被引用次数', default=0, db_index=True,
        help_text='仅对国标有效，每次被企标规范性引用时 +1'
    )

    # ── 全生命周期链条（溯源）────────────────────────────
    # ⚠️ 关键规则：溯源统计严格以 all_chain 为主，忽略 part_chain
    all_chain = models.JSONField(
        '全生命周期链条', default=list, blank=True,
        help_text='JSON 数组，存储该标准在全生命周期中所有相关标准 ID'
    )
    part_chain = models.JSONField(
        '部分链条（仅辅助）', default=list, blank=True,
        help_text='参考字段，统计时不使用，仅作展示辅助'
    )

    status = models.CharField('标准状态', max_length=20, choices=STATUS_CHOICES, default='active')

    publish_date = models.DateField('发布日期', null=True, blank=True)
    implement_date = models.DateField('实施日期', null=True, blank=True)

    created_at = models.DateTimeField('入库时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'standards_standard'
        verbose_name = '标准'
        verbose_name_plural = '标准列表'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['type', 'is_parsed'], name='idx_type_parsed'),
            models.Index(fields=['citation_count'], name='idx_citation'),
        ]

    def __str__(self):
        return self.standard_no

    def increment_citation(self):
        """
        国标被引用次数 +1（原子操作）
        ⚠️ 溯源逻辑：严格绑定 all_chain，不使用 part_chain
        """
        from django.db.models import F
        Standard.objects.filter(pk=self.pk).update(citation_count=F('citation_count') + 1)


class NormativeReference(models.Model):
    """
    规范性引用记录（模块二 Excel 解析结果）

    当内部同事上传企标的"规范性引用 Excel"时，
    系统解析后在此表记录：哪个企标引用了哪个国标
    """

    # 被解析的企标
    source_standard = models.ForeignKey(
        Standard, on_delete=models.CASCADE,
        related_name='normative_references',
        verbose_name='来源企标'
    )

    # 被引用的国标（冗余存储标准号方便检索，FK 可为空处理未入库国标）
    cited_standard_no = models.CharField('被引用标准号', max_length=200, db_index=True)
    latest_standard_no = models.CharField('最新标准号', max_length=200, db_index=True, blank=True, default='')
    cited_standard = models.ForeignKey(
        Standard, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='cited_by',
        verbose_name='被引用标准（关联）'
    )

    created_at = models.DateTimeField('记录时间', auto_now_add=True)

    class Meta:
        db_table = 'standards_normative_reference'
        verbose_name = '规范性引用'
        verbose_name_plural = '规范性引用列表'
        # 防止重复引用记录
        unique_together = [('source_standard', 'cited_standard_no')]

    def __str__(self):
        return f'{self.source_standard.standard_no} → {self.cited_standard_no}'


class StandardContent(models.Model):
    """
    企业标准 PDF 页面全文文本内容
    """
    standard = models.ForeignKey(
        Standard,
        on_delete=models.CASCADE,
        related_name='contents',
        verbose_name='关联标准'
    )
    page_number = models.PositiveIntegerField('页码')
    content = models.TextField('页面内容', blank=True)

    class Meta:
        db_table = 'standards_standard_content'
        verbose_name = '标准内容'
        verbose_name_plural = '标准内容列表'
        unique_together = [('standard', 'page_number')]
        ordering = ['page_number']

    def __str__(self):
        return f'{self.standard.standard_no} - P.{self.page_number}'


from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache


import logging
logger = logging.getLogger(__name__)


def _invalidate_search_cache():
    """
    精准清除与搜索/统计相关的缓存 key，
    包含企业搜索缓存与联邦标准摘要缓存。
    """
    try:
        # django-redis 支持通配符删除
        cache.delete_pattern("company_search:*")
        cache.delete_pattern("company_federated_standards_summary:*")
        cache.delete_pattern("company_federated_standards:*")
    except (AttributeError, Exception) as e:
        logger.warning(f"Cache pattern invalidation fallback: {e}")
        cache.delete("company_search:default")
    cache.delete("dashboard:stats")


def update_company_standards_count(company):
    if not company:
        return
    try:
        # 1. 本地企标/团标数量
        local_count = company.standards.filter(type__in=['enterprise', 'group']).count()
        # 2. 联邦库精准去重统计数量（通过 FederatedStandardService 深度模块）
        from companies.services import FederatedStandardService
        fed_summary = FederatedStandardService.get_company_standards_summary(company, scope='expanded')
        federated_count = fed_summary.get('total_standards', 0)

        company.standards_count = max(local_count, federated_count)
        company.save(update_fields=['standards_count'])
    except Exception as e:
        logger.error(f"Error in update_company_standards_count for company {company.id}: {e}")


@receiver(post_save, sender=Standard)
def standard_post_save(sender, instance, created, **kwargs):
    """
    当企标记录保存时，精准清除搜索缓存并异步触发 PDF 解析任务，同时更新企业标准总数
    """
    try:
        _invalidate_search_cache()
    except Exception:
        pass

    if instance.company:
        try:
            update_company_standards_count(instance.company)
        except Exception:
            pass

    # 仅企标才需要全文解析，国标等一般不需要
    if instance.type != 'enterprise':
        return

    if instance.pdf_file or instance.disk_filename:
        # 异步调用 Celery 任务解析 PDF
        from standards.tasks import parse_standard_pdf_task
        parse_standard_pdf_task.delay(instance.id)


@receiver(post_delete, sender=Standard)
def standard_post_delete(sender, instance, **kwargs):
    """
    当企标记录删除时，精准清除搜索缓存，并更新企业标准总数
    """
    try:
        _invalidate_search_cache()
    except Exception:
        pass

    if instance.company:
        try:
            update_company_standards_count(instance.company)
        except Exception:
            pass


