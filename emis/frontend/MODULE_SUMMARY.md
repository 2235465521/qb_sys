# 前端模块开发总结 (Frontend Summary)

## 1. 架构规范
- **技术栈**: React 18 + Vite + Ant Design 5 + React Query。
- **类型安全**: 强制执行 `import type` 规范，解决 Vite 类型解析白屏问题。
- **状态管理**: 采用 React Query 封装业务 Hook（`useCompanyData`, `useDictData` 等），实现数据缓存。

## 2. 界面实现
- **后台管理 (Admin)**: 
    - 企业列表 CRUD、Excel 导入/导出。
    - 行政区划三级联动选择器。
    - 短信模板管理。
- **前台应用 (Client)**:
    - 搜企搜标：集成 LBS 坐标检索与距离展示。
    - 引用统计：Excel 上传解析面板与国标热度排行榜。
    - 会员中心：会员采集与任务触发。

## 3. 视觉设计
- **登录页**: 采用溢彩渐变 + 玻璃拟态设计。
- **布局**: 主侧边栏响应式布局。
