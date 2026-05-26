# EMIS 双系统架构重构与登录跳转 Bug 修复文档

## 1. 核心 Bug 修复：点击模块回跳 Login 页
### 问题根源
- **401 未授权拦截**: 之前前端使用的是 Mock Token，而后端 Django 开启了 JWT 严格认证。每当组件（如字典选择器）发起 API 请求时，后端返回 401，触发了 `api/client.ts` 中的拦截器：`window.location.href = '/login'`。
- **Token 注入失效**: 原有的 Axios 拦截器在注入 `Authorization` 头时，部分情况下由于对象赋值方式（`.Authorization` vs `['Authorization']`）在浏览器端失效。

### 修复方案
1. **后端真实认证**: 在 `users.urls.auth_urls` 中启用了真正的 JWT 登录接口 `/api/auth/login/`。
2. **账号初始化**: 强制在数据库中初始化了超级管理员账号（`admin` / `admin123`），确保身份校验真实有效。
3. **拦截器加固**: 优化了 `src/api/client.ts`，采用更稳定的 `config.headers['Authorization']` 注入方式，并在登录页成功后同时存储 `access` 和 `refresh` 令牌。

---

## 2. 双系统架构重构 (Dual-System)
### 设计方案
- **逻辑隔离**: 弃用通用的 `MainLayout`，拆分为 `ClientLayout`（前台应用门户）与 `AdminLayout`（管理后台系统）。
- **路由分流**: 
    - `/client/*`: 对应前台业务，拥有浅色调主题和业务侧边栏。
    - `/admin/*`: 对应后台管理，拥有深色调主题和管理侧边栏。
- **路径规范**: 后台路径严格锁定为 `/admin`，前台路径锁定为 `/client`。

### 系统切换逻辑
- 用户登录后根据权限（或手动选择）进入对应的系统。
- 两个系统在视觉、导航、功能上完全独立，互不干扰。

---

## 3. 待执行操作
- [x] 重写 `LoginPage` 调用真实接口。
- [x] 创建 `ClientLayout` 与 `AdminLayout` 布局组件。
- [x] 更新 `router/index.tsx` 实现分流。
- [x] 物理清理 Vite 缓存并重启。

---

## 4. 后续权限细化修复 (细粒度路由守护)
- [x] **后端接口拉取**: 新增 `/api/auth/me/` 获取登录用户的 `role`、`real_name` 和 `username`。
- [x] **前端缓存封装**: 基于 React Query 封装了 `useAuth.ts`，缓存并获取用户信息，避免重复多余网络请求。
- [x] **路由守卫拦截**: 新增 `src/components/ProtectedRoute.tsx` 守卫组件，在渲染前完成 token 与 admin 权限校验。
- [x] **前后台双向穿梭**:
    - 在前台 `ClientLayout` 检测到管理员身份，Header 会优雅地提供 **"进入管理后台"** 快捷按钮。
    - 在后台 `AdminLayout` 头部，提供 **"返回前台门户"** 快捷按钮。
- [x] **智能登录分流**: `LoginPage` 登录成功后智能根据管理员权限与会员身份进行分流跳转，极大提升体验。
