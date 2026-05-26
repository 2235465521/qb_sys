"""
users App — 用户/会员模型

包含：
  AdminUser  — 后台管理员（继承 AbstractBaseUser）
  Member     — 前台会员档案
"""

from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin


class AdminUserManager(BaseUserManager):
    def create_user(self, username, password=None, **extra_fields):
        if not username:
            raise ValueError('管理员用户名不能为空')
        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'superadmin')
        return self.create_user(username, password, **extra_fields)


class AdminUser(AbstractBaseUser, PermissionsMixin):
    """后台管理员账号"""

    ROLE_CHOICES = [
        ('superadmin', '超级管理员'),
        ('admin', '普通管理员'),
        ('operator', '操作员'),  # 可上传解析 Excel 的内部同事
        ('client', '普通客户'),    # 外部自主注册客户
    ]

    username = models.CharField('用户名', max_length=50, unique=True)
    real_name = models.CharField('真实姓名', max_length=50, blank=True)
    role = models.CharField('角色', max_length=20, choices=ROLE_CHOICES, default='admin')
    is_active = models.BooleanField('是否启用', default=True)
    is_staff = models.BooleanField('是否可进入 Django Admin', default=False)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    objects = AdminUserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = []

    class Meta:
        db_table = 'users_admin'
        verbose_name = '管理员'
        verbose_name_plural = '管理员列表'

    def __str__(self):
        return f'{self.username} ({self.get_role_display()})'


class Member(models.Model):
    """前台会员档案"""

    STATUS_CHOICES = [
        ('active', '正常'),
        ('frozen', '冻结'),
        ('expired', '过期'),
    ]

    name = models.CharField('姓名', max_length=50)
    company = models.CharField('所属单位', max_length=200, blank=True, null=True)
    phone = models.CharField('手机号', max_length=20, db_index=True)
    status = models.CharField('会员状态', max_length=20, choices=STATUS_CHOICES, default='active')
    notes = models.TextField('备注', blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'users_member'
        verbose_name = '会员'
        verbose_name_plural = '会员列表'
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class OrganizationCategory(models.Model):
    """组织机构分类定义表 (支持用户自定义新增分类模块，如公司、协会、办事处等)"""
    name = models.CharField('分类名称', max_length=50, unique=True)
    code = models.CharField('分类编码', max_length=50, unique=True)
    is_system = models.BooleanField('是否系统默认', default=False)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        db_table = 'users_org_category'
        verbose_name = '组织机构分类'
        verbose_name_plural = '组织机构分类列表'
        ordering = ['created_at']

    def __str__(self):
        return self.name


class MemberOrgRole(models.Model):
    """会员-组织职务关联表 (支持一人身兼多职)"""
    member = models.ForeignKey(Member, related_name='roles', on_delete=models.CASCADE, verbose_name='会员')
    category = models.ForeignKey(OrganizationCategory, on_delete=models.PROTECT, verbose_name='所属分类')
    org_name = models.CharField('机构/单位名称', max_length=200)
    position = models.CharField('担任职务', max_length=100)
    joined_at = models.DateTimeField('加入时间', auto_now_add=True)

    class Meta:
        db_table = 'users_member_org_role'
        verbose_name = '会员任职角色'
        verbose_name_plural = '会员任职角色列表'
        ordering = ['joined_at']

    def __str__(self):
        return f'{self.member.name} - {self.org_name}({self.position})'
