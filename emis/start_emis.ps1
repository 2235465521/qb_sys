# EMIS (企业管理信息系统) 一键启动脚本

Write-Host "🚀 正在启动 EMIS 系统..." -ForegroundColor Cyan

# 1. 检查 Redis (Celery 依赖)
Write-Host "检查 Redis 服务..." -ForegroundColor Yellow
# 假设 Redis 已安装并在默认端口运行，若未运行请手动启动

$WorkDir = $PSScriptRoot
if (-not $WorkDir) {
    $WorkDir = Get-Location
}

# 2. 启动 Django 后端
Start-Process powershell -WorkingDirectory "$WorkDir\backend" -ArgumentList "-NoExit", "-Command", "python manage.py runserver 0.0.0.0:8000"

# 3. 启动 Celery Worker
Start-Process powershell -WorkingDirectory "$WorkDir\backend" -ArgumentList "-NoExit", "-Command", "celery -A config worker --loglevel=info -P eventlet"

# 4. 启动 Vite 前端
Start-Process powershell -WorkingDirectory "$WorkDir\frontend" -ArgumentList "-NoExit", "-Command", "npm run dev"

Write-Host "✅ 所有服务已尝试启动！" -ForegroundColor Green
Write-Host "   - 后端 API: http://127.0.0.1:8000"
Write-Host "   - 前端页面: http://127.0.0.1:5173"
Write-Host "   - Celery 日志请查看弹出窗口"
