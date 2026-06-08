/**
 * ecosystem.config.js — PM2 进程管理配置
 *
 * 用法：
 *   pm2 start ecosystem.config.js          # 首次启动所有进程
 *   pm2 reload ecosystem.config.js         # 热重载（零停机）
 *   pm2 stop ecosystem.config.js           # 停止所有进程
 *
 * Worker 数公式：CPU核数 × 2 + 1
 *   2核服务器 → workers: 5
 *   4核服务器 → workers: 9
 *   8核服务器 → workers: 17
 *
 * 请根据实际 nproc 输出修改 --workers 参数。
 */

// ─── 路径配置（Conda 环境）───────────────────────────────────────────
const CONDA_ENV  = '/home/zkbz01/anaconda3/envs/qb_system/bin';
const GUNICORN   = `${CONDA_ENV}/gunicorn`;
const CELERY     = `${CONDA_ENV}/celery`;

// 绝对路径，避免 PM2 因 CWD 变化找不到项目
const BACKEND_CWD = '/home/zkbz01/emis_v2/xiangmu/emis/backend';

module.exports = {
  apps: [
    // ─── Django API 服务（Gunicorn 多 Worker）────────────────────────
    {
      name: 'emis-backend',
      script: GUNICORN,
      args: [
        'config.wsgi:application',
        '--workers', '5',           // ← nproc 输出核数 × 2 + 1，2核填5，4核填9
        '--worker-class', 'gthread',
        '--threads', '4',           // 每 worker 4 线程 → 5×4=20 并发
        '--timeout', '120',
        '--bind', '0.0.0.0:8000',
        '--access-logfile', '-',
        '--error-logfile', '-',
      ].join(' '),
      cwd: BACKEND_CWD,
      interpreter: 'none',          // 可执行文件直接运行，不需要 Python 解释器包装
      env: {
        DJANGO_SETTINGS_MODULE: 'config.settings',
        SERVER_GATEWAY_INTERFACE: 'wsgi',   // 触发 AppConfig.ready() 缓存预热
        PYTHONUNBUFFERED: '1',
        PATH: `${CONDA_ENV}:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin`,
      },
      watch: false,
      max_memory_restart: '512M',
      restart_delay: 3000,
    },

    // ─── Celery Worker（异步任务：批量导入、PDF解析、短信）─────────────
    {
      name: 'emis-celery-worker',
      script: CELERY,
      args: '-A config worker -Q emis --concurrency=4 --loglevel=info',
      cwd: BACKEND_CWD,
      interpreter: 'none',
      env: {
        DJANGO_SETTINGS_MODULE: 'config.settings',
        PYTHONUNBUFFERED: '1',
        PATH: `${CONDA_ENV}:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin`,
      },
      watch: false,
      max_memory_restart: '512M',
      restart_delay: 5000,
    },

    // ─── Celery Beat（定时任务调度：PDF扫描、缓存预热）──────────────────
    {
      name: 'emis-celery-beat',
      script: CELERY,
      args: '-A config beat --loglevel=info',   // 使用 settings.CELERY_BEAT_SCHEDULE
      cwd: BACKEND_CWD,
      interpreter: 'none',
      env: {
        DJANGO_SETTINGS_MODULE: 'config.settings',
        PYTHONUNBUFFERED: '1',
        PATH: `${CONDA_ENV}:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin`,
      },
      watch: false,
      instances: 1,                 // Beat 只能单实例！
      restart_delay: 5000,
    },
  ],
};
