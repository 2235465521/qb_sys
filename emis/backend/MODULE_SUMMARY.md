# 后端模块开发总结 (Backend Summary)

## 1. 企业与标准管理模块 (Companies & Standards)
- **核心逻辑**: 实现了“胖 Model”架构，在 `services.py` 中封装了业务逻辑。
- **数据结构**: 
    - `Company`: 支持经纬度存储及行政区划关联。
    - `Standard`: 支持企标与国标区分，具备 `is_parsed` 状态位。
- **LBS 检索**: 实现了基于 `ST_Distance_Sphere` 的空间地理位置查询。
- **引用解析**: 实现了 Excel 解析引擎，支持 `all_chain` 溯源统计国家标准引用频次。

## 2. 异步任务模块 (Celery & Redis)
- **ZIP 打包**: 实现了标准文件多选打包下载任务。
- **短信发送**: 实现了短信模板变量渲染与异步群发。

## 3. 字典系统 (Dictionary)
- **行政区划**: 实现了省、市、区三级数据的预置与 API 检索。
