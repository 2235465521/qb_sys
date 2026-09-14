# 2. 豆包大模型连接器采用一站式聚合查询接口

Date: 2026-09-10

## Status

Accepted

## Context

企标管理系统（EMIS）需要对接字节跳动豆包电脑端「技能·连接器」，使用户在大模型对话中可自然语言提问“某公司名下有哪些标准”。
传统 RESTful 规范通常将企业与标准分为两级独立资源（`/companies?keyword=xxx` 和 `/companies/{id}/standards`），要求客户端进行两阶段级联调用。

然而在 LLM Function Calling 场景下：
1. 分步调用会导致大模型发起两次往返网络请求（2x RTT），对话延迟增加。
2. 大模型在两轮 Tool Call 之间可能丢失上下文或错误提取企业 ID。
3. 企业名下的企标数量可能较多，全量输出会耗尽 LLM Context 限制（Token 溢出）。

## Decision

我们决定为豆包连接器设计专属的**一站式聚合接口**（`/api/open/doubao/company-standards`）：

1. **单轮检索聚合**：接口接收 `company_name` 关键词，服务端内部自动完成企业模糊匹配与关联标准查询，一次性返回企业核心主体信息与标准列表。
2. **Token 与数量截断控制**：默认返回前 20 条最新标准（支持通过 `limit` 调整，上限 50），并在响应顶层返回标准总数 `total_standards`，引导大模型按需向用户总结或提示查看完整数据。
3. **多公司匹配消歧**：当搜索关键词匹配到多家实体企业时，优先聚合首位企业标准，并在附加字段 `related_companies` 中返回其他候选企业名称，方便大模型向用户追问确认。

## Consequences

### Positive
- **大模型响应极速**：单轮 Tool Call 完成业务目标，交互延时降低 50% 以上。
- **Token 消耗可控**：精确过滤大模型不需要的复杂冗余字段。
- **降低大模型调用出错率**：消除了“先拿 ID 再查下级”的依赖断裂风险。

### Negative / Trade-offs
- 接口与经典 REST 资源规范略有解耦，属于专门面向 Agent 工具层定制的胶水层接口（BFF / Agent Facade）。
