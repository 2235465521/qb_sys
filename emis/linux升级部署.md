# 企标管理系统 (EMIS) Linux 升级部署实战指南

> 👨‍💻 **文档说明**：本文档由拥有 10 年架构及运维经验的专家编写，旨在为 EMIS 系统在 Linux 环境下的日常升级、部署与排错提供标准作业程序 (SOP)。后续排查问题或进行版本迭代时，请优先以此文档为准。

## 一、 部署前置条件

1. **操作系统与权限**：
   - 建议在 Ubuntu/CentOS 等主流 Linux 系统上操作。
   - 基础操作使用普通用户（如 `zkbz01`）即可。
   - **关键操作**（如杀掉 `root` 遗留进程）必须具备 `sudo` 权限。

2. **核心目录与变量**：
   - 项目根目录：`~/emis_v2/xiangmu/emis/`
   - 后端目录：`~/emis_v2/xiangmu/emis/backend/`
   - 前端目录：`~/emis_v2/xiangmu/emis/frontend/`
   - 共享物理磁盘阵列（挂载点）：`/mnt/std_bk/磁盘阵列/标准文件下载/企标下载`

---

## 二、 升级部署标准流程

### 1. 更新前端代码并打包
```bash
# 进入前端工程目录
cd ~/emis_v2/xiangmu/emis/frontend

# 拉取最新代码
git pull

# 构建生产环境静态资源 (输出至 dist 目录，由后端或 Nginx 接管)
npm run build
```

### 2. 清理旧版后台进程（重点防御僵尸进程）
> ⚠️ **警告**：如果系统曾经以 `root` 权限运行过服务，普通用户的 `pkill` 将会提示 `Operation not permitted` 并失效。必须使用 `sudo` 彻底清理，防止新老代码同时运行争抢任务。

```bash
# 使用管理员权限彻底杀掉所有 Gunicorn 进程，释放 8003 端口
sudo pkill -f gunicorn

# 使用管理员权限彻底杀掉所有 Celery 异步任务进程，防止抢单
sudo pkill -f celery
```

### 3. 更新后端代码并重启服务
```bash
# 进入后端工程目录
cd ~/emis_v2/xiangmu/emis/backend

# 拉取最新代码
git pull

# 启动 Gunicorn Web 服务（绑定 8003 端口，4 个 worker，后台守护运行）
gunicorn config.wsgi:application --bind 0.0.0.0:8003 --workers 4 --daemon

# 启动 Celery 异步任务队列（后台运行，日志输出到 celery.log）
celery -A config worker -l info -c 4 -D --logfile celery.log
```

---

## 三、 避坑指南 (Troubleshooting)

在过往的实际部署与维护中，我们遇到过以下典型故障。若遇到类似现象，请直接对号入座排查：

### 1. 故障现象：“有时候打包/扫盘能成功，有时候一直卡死在 10%”
* **原因分析**：这是典型的“双轨运行”血案。由于早期用 `root` 启动了进程，导致普通用户的 `pkill` 清理失败。此时 8003 端口被老版本霸占，而 Celery 却因为允许启动多个 worker 而变成了两拨人马（新老并存）。当新 Celery 抢到任务时，处理秒成功；当老 Celery 抢到任务时，依然触发旧 Bug 导致卡死。
* **解决方案**：严格执行 `sudo pkill -f gunicorn` 和 `sudo pkill -f celery`，确保系统内没有任何残留的幽灵进程后再启动全新代码。

### 2. 故障现象：打包下载下来的 ZIP 文件是 `0KB`
* **原因分析**：这通常是因为 Nginx 配置的 `X-Accel-Redirect` (Sendfile) 转发路径与 Django 实际生成的物理路径存在不匹配，或者是文件权限问题导致 Nginx 进程无法读取临时生成的 Zip 包（例如 Django 以 root 身份生成了只有 root 可读的 0600 权限文件）。
* **解决方案**：检查 Nginx 配置文件中对于 `/media/` 路由的物理映射；确保 `MEDIA_ROOT` 目录及其下的文件具有足够的公共读权限。

### 3. 故障现象：网页突然报 `503 Service Temporarily Unavailable`
* **原因分析**：说明前端请求成功打到了 Nginx，但 Nginx 转发给后端的 8003 端口时无人响应。通常是因为 Gunicorn 进程挂掉了，或者 Gunicorn 因为语法错误、端口冲突等原因重启失败，没有成功拉起。
* **解决方案**：使用前台启动命令（去掉 `--daemon` 守护参数）观察报错信息：`gunicorn config.wsgi:application --bind 0.0.0.0:8003`，修复报错后再转后台运行。

### 4. 故障现象：在服务器上执行 `git pull` 时卡死、无响应
* **原因分析**：通常是因为 SSH 密钥失效、Github 服务器暂时阻断，或当前用户缺乏该目录的读写权限导致线程阻塞。
* **解决方案**：
  - 按 `Ctrl + C` 中断命令。
  - 检查网络及鉴权：`ssh -T git@github.com`。
  - 若提示 `.git` 目录权限问题，可使用 `sudo chown -R $USER:$USER .git` 修复所有权。

### 5. 故障现象：扫盘找不到 `/mnt/std_bk/...` 里的 PDF 文件，下载按钮始终灰色
* **原因分析**：代码中可能将磁盘路径硬编码为了 Windows 环境特有的 `Y:\磁盘阵列...`，或者在读取 `.env` 配置失败时 Fallback 到了该地址。另外，前端页面以前可能写死只读取 `disk_filename`，而没有校验新的 `pdf_file` 字段。
* **解决方案**：已在最新代码的 `settings.py` 中增加了针对 Linux 和 Windows 系统的环境自适应判断。拉取最新代码并重启 Gunicorn 即可生效。
