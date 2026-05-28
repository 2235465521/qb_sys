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

## 二、 PM2 进程配置与开机自启（断电自动恢复）

为了方便统一管理服务器上的多个项目，并实现服务器断电/重启后的自动恢复运行，本项目使用 **PM2** 进程管理器进行统一维护。

### 1. 配置文件管理 (`/home/zkbz01/ecosystem.config.js`)
在服务器用户的家目录下统一配置所有运行的项目：
```javascript
module.exports = {
  apps: [
    // 1. 原有的 gate-frontend 前端服务
    {
      name: "gate-frontend",
      script: "npm",
      args: "run preview",
      cwd: "/home/zkbz01/gate_sys",
      autorestart: true,
      watch: false,
      env: {
        NODE_ENV: "production"
      }
    },
    // 2. 原有的 frpc 内网穿透客户端
    {
      name: "frpc",
      script: "./frpc",
      args: "-c frpc.toml",
      cwd: "/home/zkbz01/frp_0.57.0_linux_amd64",
      autorestart: true,
      watch: false
    },
    // 3. EMIS 企标系统 后端 Gunicorn 服务
    {
      name: "emis-backend",
      script: "/home/zkbz01/anaconda3/envs/qb_system/bin/gunicorn",
      args: "config.wsgi:application --bind 0.0.0.0:8003 --workers 4",
      cwd: "/home/zkbz01/emis_v2/xiangmu/emis/backend",
      interpreter: "none",
      autorestart: true,
      watch: false,
      env: {
        NODE_ENV: "production"
      }
    },
    // 4. EMIS 企标系统 Celery 异步任务队列
    {
      name: "emis-celery",
      script: "/home/zkbz01/anaconda3/envs/qb_system/bin/celery",
      args: "-A config worker -l info -c 4 --logfile celery.log",
      cwd: "/home/zkbz01/emis_v2/xiangmu/emis/backend",
      interpreter: "none",
      autorestart: true,
      watch: false
    }
  ]
};
```

### 2. 首次部署与自启动设置步骤
1. **安装 PM2**：
   ```bash
   sudo npm install -g pm2
   ```
2. **清理冲突进程**：
   在交由 PM2 接管前，确保之前手动后台运行的进程已被关闭（释放端口）：
   ```bash
   sudo pkill -f gunicorn
   sudo pkill -f celery
   fuser -k 5176/tcp 2>/dev/null
   killall frpc 2>/dev/null
   ```
3. **启动所有服务**：
   ```bash
   pm2 start /home/zkbz01/ecosystem.config.js
   ```
4. **开启 PM2 系统级开机自启**：
   ```bash
   # 保存当前的运行列表（告诉 PM2 开机默认运行哪些进程）
   pm2 save
   
   # 生成系统开机自启服务
   pm2 startup
   # 注意：运行后终端最下方会生成一行以 `sudo env PATH=...` 开头的系统命令，请复制并执行该命令完成开机自启的注册。
   ```

### 3. Nginx 开机自启动配置
网页能够正常打开的前提是 Nginx 反向代理正常运行。在系统重启后，Nginx 也需要自动启动：
```bash
# 启动并设置开机自启
sudo systemctl start nginx
sudo systemctl enable nginx
```

---

## 三、 升级部署标准流程（使用 PM2 后）

引入 **PM2** 进程管理后，您**不再需要**手动使用 `pkill` 去杀死进程或用 `nohup/--daemon` 去后台启动。PM2 会自动帮我们托管、重启并输出日志，升级流程极度简化。

### 1. 更新前端代码（EMIS 系统）
如果更新了 EMIS 的前端代码，只需要打包生成静态资源，Nginx 会自动读取最新文件，**无需重启任何服务**：
```bash
# 进入前端目录
cd ~/emis_v2/xiangmu/emis/frontend

# 拉取最新前端代码
git pull

# 构建静态资源（dist 目录会自动更新）
npm run build
```

### 2. 更新后端代码（EMIS 系统）
```bash
# 进入后端目录
cd ~/emis_v2/xiangmu/emis/backend

# 拉取最新后端代码
git pull

# 激活项目的虚拟环境，用于处理可能的依赖变化或数据库变动
conda activate qb_system

# [可选] 如果代码里新增了第三方依赖包，安装它们
pip install -r requirements.txt

# [可选] 如果修改了数据库模型，执行迁移
python manage.py migrate
```

### 3. 使用 PM2 一键重启服务载入新代码
由于 Python 代码在内存中运行，后端和 Celery 在拉取代码后必须重启才能生效。现在您只需执行：
```bash
# 一键重启后端和异步任务，PM2 会安全重启它们
pm2 restart emis-backend emis-celery

# 如果您连同 gate-frontend 也有更新，可以重启所有托管服务：
# pm2 restart all
```

---

## 四、 避坑指南 (Troubleshooting)

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
