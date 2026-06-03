import time
import re
import logging
from django.utils.timezone import now
from django.core.cache import cache
from rest_framework_simplejwt.authentication import JWTAuthentication
from .models import UsageLog

logger = logging.getLogger(__name__)

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def get_action_desc(method, path):
    """根据请求方法和路径映射友好的中文描述"""
    # 账号认证与基本信息
    if '/api/auth/login' in path:
        return '用户登录'
    elif '/api/auth/register' in path:
        return '新用户注册'
    elif '/api/auth/user' in path:
        return '获取用户信息'
    elif '/api/auth/refresh' in path:
        return '刷新认证Token'

    # 前台客户端业务
    elif '/api/client/search/companies/' in path:
        if 'export' in path:
            return '前台导出企业数据'
        return '前台检索企业'
    elif '/api/client/search/leads/' in path:
        return '前台提交营销线索'
    elif '/api/client/standards/' in path:
        if 'download' in path:
            return '前台下载企标PDF'
        elif 'preview' in path:
            return '前台预览企标PDF'
        return '前台查询企标列表'
    elif '/api/client/analysis/trends/' in path:
        return '查询趋势分析图表'
    elif '/api/client/analysis/' in path:
        return '解析企标规范性引用'
    elif '/api/client/members/' in path:
        return '前台会员中心查询'
    elif '/api/client/notifications/' in path:
        return '前台查询通知任务'

    # 后台管理业务
    elif '/api/admin/companies/' in path:
        if method == 'GET':
            return '后台查询企业列表'
        elif method == 'POST':
            return '后台创建企业'
        elif method in ('PUT', 'PATCH'):
            return '后台更新企业'
        elif method == 'DELETE':
            return '后台删除企业'
    elif '/api/admin/standards/' in path:
        if 'import' in path or 'upload' in path:
            return '后台导入企标规范'
        elif method == 'GET':
            return '后台查询企标列表'
        elif method == 'POST':
            return '后台创建企标'
        elif method in ('PUT', 'PATCH'):
            return '后台修改企标'
        elif method == 'DELETE':
            return '后台删除企标'
    elif '/api/admin/references/' in path:
        return '后台查询标准引用日志'
    elif '/api/admin/leads/' in path:
        return '后台管理营销线索'
    elif '/api/admin/members/' in path:
        if method == 'GET':
            return '后台查询会员列表'
        elif method == 'POST':
            return '后台新增会员档案'
        elif method in ('PUT', 'PATCH'):
            return '后台修改会员档案'
        elif method == 'DELETE':
            return '后台删除会员档案'
    elif '/api/admin/sms-templates/' in path:
        return '数据配置：短信模板管理'
    elif '/api/admin/dict/' in path:
        return '数据配置：数据字典管理'
    elif '/api/admin/users/' in path:
        if method == 'GET':
            return '后台查询系统用户'
        elif method == 'POST':
            return '后台新建系统用户'
        elif method in ('PUT', 'PATCH'):
            return '后台更新系统用户'
        elif method == 'DELETE':
            return '后台删除系统用户'
    elif '/api/admin/statistics/' in path:
        return '查看系统使用记录与统计'

    return f"API操作: {method} {path}"


class UsageLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 仅拦截 API 请求
        if not request.path.startswith('/api/'):
            return self.get_response(request)

        # 过滤掉统计请求自身的日志记录，防止刷屏
        if '/api/admin/statistics/' in request.path:
            return self.get_response(request)

        # 记录请求起始时间
        start_time = time.time()
        
        # 执行请求，获取响应
        response = self.get_response(request)
        
        # 计算耗时
        duration = round(time.time() - start_time, 3)
        
        try:
            self.log_request(request, response, duration)
        except Exception as e:
            logger.error(f"UsageLogMiddleware 记录日志失败: {e}", exc_info=True)
            
        return response

    def log_request(self, request, response, duration):
        # 1. 尝试获取认证用户
        user = None
        if hasattr(request, 'user') and request.user.is_authenticated:
            user = request.user
        else:
            # 备用方案：手动解析 Bearer Token，以便在 Exception 或早期生命周期中抓到用户
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                try:
                    token = auth_header.split(' ')[1]
                    jwt_auth = JWTAuthentication()
                    validated_token = jwt_auth.get_validated_token(token)
                    user = jwt_auth.get_user(validated_token)
                except Exception:
                    pass

        # 2. 提取 IP 地址
        ip_address = get_client_ip(request)

        # 3. 提取检索关键词（GET 参数）
        keyword = request.GET.get('keyword') or request.GET.get('query') or ''
        
        # 4. 提取目标对象 ID (例如标准 ID 或企业 ID)
        target_id = ''
        # 匹配 /api/client/standards/123/download/ 或 /api/admin/companies/123/ 这种路径中的数字 ID
        id_match = re.search(r'/api/(?:client|admin)/(?:standards|companies|members)/(\d+)/', request.path)
        if id_match:
            target_id = id_match.group(1)

        # 5. 生成操作汉化描述
        action = get_action_desc(request.method, request.path)

        # 6. 防爬虫与异常下载预警检测 (针对预览与下载)
        is_warning = False
        is_download_action = 'download' in request.path or 'export' in request.path
        if is_download_action and response.status_code == 200:
            user_key = user.username if user else ip_address
            cache_key = f"usage_download_count_{user_key}"
            
            # 获取过去10分钟内的下载次数
            download_count = cache.get(cache_key, 0) + 1
            cache.set(cache_key, download_count, 600)  # 10分钟有效期
            
            # 若10分钟内下载/导出次数超过 15 次，触发异常警报
            if download_count > 15:
                is_warning = True

        # 7. 写入数据库
        UsageLog.objects.create(
            user=user,
            username=user.username if user else 'Anonymous',
            real_name=user.real_name if user else '未登录用户',
            ip_address=ip_address,
            path=request.path[:255],
            method=request.method,
            action=action,
            keyword=keyword[:255],
            target_id=target_id,
            status_code=response.status_code,
            duration=duration,
            is_warning=is_warning
        )
