"""
Celery 异步任务定义

tasks/
  - pack_standards_zip  — 标准文件打包（模块一）
  - send_sms_task       — 短信批量发送（模块三）
"""

from celery import shared_task
from django.utils import timezone


# ============================================================
# 模块一：ZIP 打包任务
# ============================================================

@shared_task(bind=True, name='standards.pack_zip')
def pack_standards_zip(self, standard_ids: list, download_token: str, include_excel: bool = False):
    """
    异步打包选中标准文件为 ZIP

    Args:
        standard_ids:   要打包的标准 ID 列表
        download_token: 唯一下载令牌（用于前端轮询 + 后台存储结果）
        include_excel:  是否生成包含企业地域信息的 Excel 清单
    """
    from django.core.cache import cache
    from standards.services import create_zip_from_standards
    import os
    import tempfile

    try:
        # 更新进度
        cache.set(f'zip_task_{download_token}', {'status': 'running', 'progress': 0}, timeout=3600)

        zip_bytes = create_zip_from_standards(standard_ids, include_excel=include_excel)

        # 将 ZIP 写入临时文件（供 Nginx X-Accel-Redirect 使用）
        from django.conf import settings
        temp_dir = settings.MEDIA_ROOT / 'temp_zips'
        temp_dir.mkdir(parents=True, exist_ok=True)
        zip_path = temp_dir / f'{download_token}.zip'

        with open(zip_path, 'wb') as f:
            f.write(zip_bytes)

        # 更新任务状态，使用安全 API 包装器下载
        cache.set(f'zip_task_{download_token}', {
            'status': 'done',
            'download_url': f'/api/client/standards/pack/download/?token={download_token}',
            'file_size': len(zip_bytes),
        }, timeout=3600)

    except Exception as exc:
        cache.set(f'zip_task_{download_token}', {
            'status': 'failed',
            'error': str(exc),
        }, timeout=3600)
        raise self.retry(exc=exc, countdown=5, max_retries=2)


# ============================================================
# 模块三：短信批量发送任务
# ============================================================

@shared_task(bind=True, name='notifications.send_sms')
def send_sms_task(self, task_id: int):
    """
    异步批量发送短信

    从 SmsTask 读取配置 → 查询目标会员 → 逐条发送 → 写入日志

    Args:
        task_id: SmsTask 的数据库 ID
    """
    from notifications.models import SmsTask, SmsLog
    from users.models import Member

    try:
        task = SmsTask.objects.get(id=task_id)
    except SmsTask.DoesNotExist:
        return

    # 标记为执行中
    task.status = 'running'
    task.started_at = timezone.now()
    task.save(update_fields=['status', 'started_at'])

    # 查询目标会员
    if task.target_group == 'all_active':
        members = Member.objects.filter(status='active')
    elif task.target_group == 'specific_company':
        members = Member.objects.filter(
            status='active', company__icontains=task.target_company
        )
    else:
        members = Member.objects.filter(status='active')

    task.total_count = members.count()
    task.save(update_fields=['total_count'])

    sent = 0
    failed = 0

    for member in members.iterator():
        try:
            # 渲染短信内容
            content = task.template.render(member)

            # TODO: 调用真实短信服务商 API
            # 当前为模拟发送，集成后替换此处
            _mock_send_sms(member.phone, content)

            SmsLog.objects.create(
                task=task,
                member=member,
                phone=member.phone,
                content=content,
                status='success',
            )
            sent += 1

        except Exception as e:
            SmsLog.objects.create(
                task=task,
                member=member,
                phone=member.phone,
                content='',
                status='failed',
                error_message=str(e),
            )
            failed += 1

    # 完成任务
    task.status = 'done' if failed == 0 else 'partial'
    task.sent_count = sent
    task.failed_count = failed
    task.finished_at = timezone.now()
    task.save(update_fields=['status', 'sent_count', 'failed_count', 'finished_at'])


def _mock_send_sms(phone: str, content: str):
    """
    模拟短信发送（开发阶段占位）
    实际部署时替换为阿里云短信 SDK / 腾讯云短信 SDK
    """
    import logging
    logging.getLogger('emis.sms').info(f'[MOCK SMS] → {phone}: {content[:30]}...')


# ============================================================
# 模块四：磁盘文件对齐任务
# ============================================================

@shared_task(bind=True, name='standards.align_disk_files_task')
def align_disk_files_task(self):
    """
    扫描磁盘阵列并与数据库clean_id对齐，更新到 disk_filename 字段，并在缓存中维护执行状态
    """
    import os
    from django.core.cache import cache
    from django.utils import timezone
    from standards.models import Standard

    # 1. 写入运行状态
    cache.set('scan_pdf_sync_task', {
        'status': 'running',
        'started_at': timezone.now().strftime("%Y-%m-%d %H:%M:%S")
    }, timeout=3600)

    try:
        target_dir = "/mnt/std_bk/磁盘阵列/标准文件下载/企标下载/整合"
        
        if not os.path.exists(target_dir):
            err_msg = f"找不到目标磁盘阵列路径: {target_dir}"
            cache.set('scan_pdf_sync_task', {'status': 'failed', 'error': err_msg}, timeout=3600)
            return {"success": False, "matched_count": 0, "error": err_msg}

        try:
            disk_files = [f for f in os.listdir(target_dir) if f.lower().endswith('.pdf')]
        except Exception as e:
            err_msg = f"读取目录失败: {str(e)}"
            cache.set('scan_pdf_sync_task', {'status': 'failed', 'error': err_msg}, timeout=3600)
            return {"success": False, "matched_count": 0, "error": err_msg}

        def normalize(s):
            return "".join(c for c in s if c.isalnum()).lower() if s else ""

        file_norms = [(f, normalize(f)) for f in disk_files]
        standards = Standard.objects.all()
        success_count = 0

        for std in standards:
            if not std.clean_id:
                continue
            
            clean_norm = normalize(std.clean_id)
            if not clean_norm:
                continue
            
            matched_file = None
            for filename, fnorm in file_norms:
                if clean_norm in fnorm:
                    matched_file = filename
                    break
            
            if matched_file:
                relative_path = f"整合/{matched_file}"
                if std.pdf_file.name != relative_path:
                    std.pdf_file.name = relative_path
                    std.save(update_fields=['pdf_file'])
                success_count += 1

        # 2. 写入成功结果
        cache.set('scan_pdf_sync_task', {
            'status': 'done',
            'matched_count': success_count,
            'finished_at': timezone.now().strftime("%Y-%m-%d %H:%M:%S")
        }, timeout=3600)

        return {"success": True, "matched_count": success_count}

    except Exception as e:
        cache.set('scan_pdf_sync_task', {
            'status': 'failed',
            'error': str(e)
        }, timeout=3600)
        raise self.retry(exc=e, countdown=5, max_retries=2)


