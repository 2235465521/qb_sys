/**
 * ecosystem.config.js — PM2 进程管理配置
 *
 * 用法：
 *   pm2 start ecosystem.config.js          # 启动所有进程
 *   pm2 reload ecosystem.config.js         # 热重载（零停机）
 *   pm2 stop ecosystem.config.js           # 停止所有进程
 *
 * Worker 数公式：CPU核数 × 2 + 1
 *   2核服务器 → workers: 5
 *   4核服务器 → workers: 9
 *   8核服务器 → workers: 17
 *
 * 请根据实际服务器 CPU 核数修改 --workers 参数。
 */

const VENV_PYTHON = '/home/zkbz01/emis_v2/venv/bin/python';  // ← 根据实际虚拟环境路径修改
const BACKEND_CWD = './emis/backend';

module.exports = {
  apps: [
    // ─── Django API 服务（Gunicorn 多 Worker）───────────────────────
    {
      name: 'emis-backend',
      script: 'gunicorn',
      args: [
        'config.wsgi:application',
        '--workers', '5',          // ← 根据 CPU 核数调整（公式：核数×2+1）
        '--worker-class', 'gthread',
        '--threads', '4',          // 每 worker 4 线程 → 5×4=20 并发
        '--timeout', '120',        // 请求超时 120s（批量导入已改为异步，不影响）
        '--bind', '0.0.0.0:8000',
        '--access-logfile', '-',
        '--error-logfile', '-',
      ].join(' '),
      cwd: BACKEND_CWD,
      interpreter: VENV_PYTHON,
      env: {
        DJANGO_SETTINGS_MODULE: 'config.settings',
        SERVER_GATEWAY_INTERFACE: 'wsgi',   // 让 AppConfig.ready() 触发预热
        PYTHONUNBUFFERED: '1',
      },
      watch: false,
      max_memory_restart: '512M',
      restart_delay: 3000,
    },

    // ─── Celery Worker（异步任务：批量导入、PDF解析、短信）──────────
    {
      name: 'emis-celery-worker',
      script: 'celery',
      args: '-A config worker -Q emis --concurrency=4 --loglevel=info',
      cwd: BACKEND_CWD,
      interpreter: VENV_PYTHON,
      env: {
        DJANGO_SETTINGS_MODULE: 'config.settings',
        PYTHONUNBUFFERED: '1',
      },
      watch: false,
      max_memory_restart: '512M',
      restart_delay: 5000,
    },

    // ─── Celery Beat（定时任务调度：PDF扫描、缓存预热）────────────────
    {
      name: 'emis-celery-beat',
      script: 'celery',
      args: '-A config beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler',
      cwd: BACKEND_CWD,
      interpreter: VENV_PYTHON,
      env: {
        DJANGO_SETTINGS_MODULE: 'config.settings',
        PYTHONUNBUFFERED: '1',
      },
      watch: false,
      // Beat 只能单实例运行！不要设置 instances > 1
      instances: 1,
      restart_delay: 5000,
    },
  ],
};
