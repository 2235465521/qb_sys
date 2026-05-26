"""
EMIS 企业管理信息系统 - Django 主配置
技术栈: Django 6.x + DRF + MySQL + Celery + Redis
"""

from pathlib import Path
from decouple import config
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY', default='emis-insecure-dev-key')

DEBUG = config('DEBUG', default=True, cast=bool)

ALLOWED_HOSTS = ['*']

# ============================================================
# 已安装 App
# ============================================================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # 第三方
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',

    # 业务 App
    'users',
    'companies',
    'standards',
    'notifications',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# ============================================================
# 数据库 - MySQL 8.x
# ============================================================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': config('DB_NAME', default='emis_db'),
        'USER': config('DB_USER', default='root'),
        'PASSWORD': config('DB_PASSWORD', default=''),
        'HOST': config('DB_HOST', default='127.0.0.1'),
        'PORT': config('DB_PORT', default='3306'),
        'OPTIONS': {
            'charset': 'utf8mb4',
        },
    }
}

# ============================================================
# Django REST Framework
# ============================================================
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
}

# ============================================================
# JWT 配置
# ============================================================
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=8),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# ============================================================
# CORS 跨域
# ============================================================
CORS_ALLOW_ALL_ORIGINS = DEBUG  # 开发环境允许所有来源
CORS_ALLOWED_ORIGINS = [
    'http://localhost:5173',  # React Vite 开发服务器
    'http://127.0.0.1:5173',
]

# ============================================================
# Redis 自动探测与双模降级机制
# ============================================================
import redis
from urllib.parse import urlparse

REDIS_URL = config('REDIS_URL', default='redis://127.0.0.1:6379/0')

try:
    parsed_url = urlparse(REDIS_URL)
    redis_host = parsed_url.hostname or '127.0.0.1'
    redis_port = parsed_url.port or 6379
except Exception:
    redis_host = '127.0.0.1'
    redis_port = 6379

try:
    # 尝试连接 Redis（连接超时 1.0 秒，Ping 存活测试）
    r = redis.Redis(host=redis_host, port=redis_port, socket_connect_timeout=1.0)
    r.ping()
    REDIS_AVAILABLE = True
except Exception:
    REDIS_AVAILABLE = False

# ============================================================
# Celery 配置
# ============================================================
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TIMEZONE = 'Asia/Shanghai'
CELERY_BEAT_SCHEDULE = {}

if REDIS_AVAILABLE:
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL
    CELERY_TASK_ALWAYS_EAGER = False
else:
    # Redis 离线时切换为同步执行模式，防止进程阻塞挂起
    CELERY_BROKER_URL = 'memory://'
    CELERY_RESULT_BACKEND = None
    CELERY_TASK_ALWAYS_EAGER = True

# ============================================================
# 文件存储 - 严格按技术栈文档规范
# ============================================================
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# ============================================================
# 缓存配置 - 具备本地文件系统跨进程缓存与 Redis 缓存双模切换
# ============================================================
if REDIS_AVAILABLE:
    try:
        import django_redis
        CACHES = {
            'default': {
                'BACKEND': 'django_redis.cache.RedisCache',
                'LOCATION': config('REDIS_URL', default='redis://127.0.0.1:6379/1'),
                'OPTIONS': {
                    'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                }
            }
        }
    except ImportError:
        CACHES = {
            'default': {
                'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
                'LOCATION': str(MEDIA_ROOT / 'django_cache'),
            }
        }
else:
    # Redis 离线时使用本地文件缓存以支持 Web 端与后台进程间的数据通信
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
            'LOCATION': str(MEDIA_ROOT / 'django_cache'),
        }
    }


# ============================================================
# 自定义用户模型
# ============================================================
AUTH_USER_MODEL = 'users.AdminUser'

# ============================================================
# 国际化
# ============================================================
LANGUAGE_CODE = 'zh-hans'
TIME_ZONE = 'Asia/Shanghai'
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ============================================================
# 共享磁盘物理路径配置（适配 Windows 局域网磁盘映射）
# ============================================================
SHARED_DISK_ROOT = r"Y:\磁盘阵列\标准文件下载\企标下载"
