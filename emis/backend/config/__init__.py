# 确保 Celery app 在 Django 启动时自动加载
from .celery import app as celery_app

__all__ = ('celery_app',)
