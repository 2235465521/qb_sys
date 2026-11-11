# 标准版本链（`all_chain` / `part_chain`）补全程序配置与运行说明

## 1. 数据库配置与字段核查

程序复用 Django 主配置（[settings.py](file:///E:/企标管理系统_企标记录/emis/backend/config/settings.py) 与 `emis/backend/.env` 中的 `default` MySQL 连接 `emis_db`）及 [`Standard`](file:///E:/企标管理系统_企标记录/emis/backend/standards/models.py#L24-L158) 模型。

已核查 `standards_standard` 实际字段类型：
- `id`: `bigint`（自增主键，对应 Python `int`）
- `standard_no`: `varchar(200)`（原始标准号，程序只读不改）
- `type`: `varchar(20)`（当前库内 1,987 条记录均为 `enterprise`）
- `company_id`: `bigint`（关联 `companies_company.id`，当前库内均非空）
- `publish_date`: `date`（发布/公开日期，非编号版本年份）
- `all_chain`: `json`（JSON 数组，存储 `list[int]`）
- `part_chain`: `json`（JSON 数组，存储 `list[int]`）

---

## 2. 程序结构与自动更新机制

- 核心服务：[services_version_chain.py](file:///E:/企标管理系统_企标记录/emis/backend/standards/services_version_chain.py)
  - [`parse_standard_no`](file:///E:/企标管理系统_企标记录/emis/backend/standards/services_version_chain.py#L115-L204)：只读解析标准编号主体与版本年份（支持全角转半角、等效连字符 `—`/`–`/`－`/`--` 归一化、合法年份范围 `1949 ~ 当前年+2`），保留标准类别、`GB` 与 `GB/T`、`.`、`-` 及前导零。
  - [`compute_version_chains`](file:///E:/企标管理系统_企标记录/emis/backend/standards/services_version_chain.py#L365-L600)：全量分组、跨企业歧义/缺失检查、格式异常与同年份重复拦截、按标准年份从新到旧排序并计算 `all_chain` 与 `part_chain`；对找不到有效版本链或无替代版本的记录，若原 `all_chain` 为空则默认填入 `[自身ID]`（已有非空链条则严格保留原值）。
  - [`run_version_chain_completion`](file:///E:/企标管理系统_企标记录/emis/backend/standards/services_version_chain.py#L810-L866)：默认试运行；传入 `execute=True` 时按分组独立事务 `transaction.atomic()` 调用 `bulk_update(..., ['all_chain', 'part_chain'])` 仅更新发生变化的链条字段，并生成审计 JSON 与 Markdown 报告。
  - [`sync_version_chains_for_targets`](file:///E:/企标管理系统_企标记录/emis/backend/standards/services_version_chain.py#L879-L895) / [`sync_version_chains_for_standards`](file:///E:/企标管理系统_企标记录/emis/backend/standards/services_version_chain.py#L898-L905)：供单条信号与批量导入后置调用的自动对齐入口。
  - [`rollback_from_audit_file`](file:///E:/企标管理系统_企标记录/emis/backend/standards/services_version_chain.py#L908-L945)：依据审计 JSON 中的 `old_all_chain` / `old_part_chain` 按组事务回滚。
- 自动更新接入点：
  1. **实时信号联动**（[models.py](file:///E:/企标管理系统_企标记录/emis/backend/standards/models.py#L266-L360)）：`Standard` 新增、修改（`standard_no` / `type` / `company` / `publish_date`）及删除时，通过 `pre_save` / `post_save` / `post_delete` 自动刷新原分组与新分组的完整版本链。
  2. **批量导入后置对齐**（[services.py](file:///E:/企标管理系统_企标记录/emis/backend/standards/services.py)、[tasks.py](file:///E:/企标管理系统_企标记录/emis/backend/standards/tasks.py#L420-L660)、[import_excel_standards.py](file:///E:/企标管理系统_企标记录/emis/backend/scripts/import_excel_standards.py)）：Excel 批量导入（含 `bulk_create` 与异步任务）完成后自动整批刷新本批次涉及分组的版本链。
  3. **定时兜底任务**（[tasks.py](file:///E:/企标管理系统_企标记录/emis/backend/standards/tasks.py#L1269-L1283) & [settings.py](file:///E:/企标管理系统_企标记录/emis/backend/config/settings.py#L184-L205)）：Celery Beat 每 30 分钟自动执行 `standards.auto_sync_version_chains`，兜底对齐绕过 ORM 直接写入数据库的记录。
- 管理命令：[rebuild_version_chains.py](file:///E:/企标管理系统_企标记录/emis/backend/standards/management/commands/rebuild_version_chains.py)
- 自动化测试：[tests_version_chain.py](file:///E:/企标管理系统_企标记录/emis/backend/standards/tests_version_chain.py)

---

## 3. 运行方式

以下命令均在 `E:\企标管理系统_企标记录\emis\backend` 目录下执行：

### 3.1 试运行（默认不写数据库）

```powershell
python manage.py rebuild_version_chains --dry-run
```

输出控制台摘要，并在 `emis/backend/reports/version_chains/` 下生成：
- `version_chain_dry_run_<timestamp>.audit.json`（变更前后值备份与异常清单）
- `version_chain_dry_run_<timestamp>.report.md`（分组依据、记录 ID、标准编号、修改前后链条与跳过原因明细表）

### 3.2 指定范围运行

按标准编号主体处理（会先在全表扫描匹配该主体的所有格式变体）：

```powershell
# 试运行预览
python manage.py rebuild_version_chains --body "Q/FASC 001"

# 正式写入指定主体
python manage.py rebuild_version_chains --body "Q/FASC 001" --execute
```

按指定记录 ID 处理（自动扩展查询其所在完整分组，禁止仅用局部 ID 建链）：

```powershell
# 试运行预览
python manage.py rebuild_version_chains --ids 2879

# 正式写入指定 ID 所在分组
python manage.py rebuild_version_chains --ids 234,12234 --execute
```

### 3.3 全量正式写入（需显式参数触发）

```powershell
python manage.py rebuild_version_chains --execute --all --batch-size 200
```

> 安全保护：若只传 `--execute` 而未传 `--all`、`--body` 或 `--ids`，命令会直接拒绝执行，防止误写全表。

### 3.4 回滚本次更新

```powershell
# 先预览回滚影响
python manage.py rebuild_version_chains --rollback reports/version_chains/version_chain_execute_YYYYMMDD_HHMMSS.audit.json

# 确认后实际回滚
python manage.py rebuild_version_chains --rollback reports/version_chains/version_chain_execute_YYYYMMDD_HHMMSS.audit.json --execute
```

---

## 4. 异常代码说明

| 异常代码 | 说明 |
|---|---|
| `EMPTY_STANDARD_NO` / `EMPTY_BODY` | 标准编号为空或去除年份后主体为空 |
| `NO_TRAILING_YEAR` | 末尾缺少“分隔符+4位年份”（如 `未知企标号`、`Q/16`、`Q/hsjj-003`） |
| `YEAR_OUT_OF_RANGE` | 末尾4位数字超出合法年份范围（如 `Q/YNY-8051`） |
| `DOUBLE_YEAR_SUFFIX` | 主体末尾存在重复年份后缀（如 `Q/JSB JS012-2014-2014`） |
| `EMBEDDED_TITLE_OR_YEAR` | 编号中混入年份与中文标题文本（如 `Q/T11944-2012 中空玻璃 -2012`） |
| `TRAILING_PUNCTUATION_IN_BODY` | 主体末尾含非法标点（如 `Q/HHJC .-2024`） |
| `MALFORMED_PREFIX` | 重复 `Q/` 或 `//` 前缀（如 `Q/Q/FQCJ 003-2023`、`Q//KLJ-006-2023`） |
| `MISSING_COMPANY_ATTRIBUTION` / `GROUP_CONTAINS_UNATTRIBUTED_RECORD` | 企业标准缺少 `company_id`，或同号下存在未归属记录 |
| `AMBIGUOUS_COMPANY_ATTRIBUTION` | 同编号跨不同 `company_id` 存在主企业/联合起草重叠或疑似更名 |
| `GROUP_CONTAINS_MALFORMED_RECORD` | 同组存在疑似格式异常兄弟记录，为保证链条完整暂停更新整组 |
| `YEAR_FIELD_CONFLICT` | 显式年份字段冲突，或 `publish_date` 早于编号年份两年以上 |
| `DUPLICATE_YEAR_IN_GROUP` | 同分组同年份存在多条不同 ID 记录，暂停更新整组 |
