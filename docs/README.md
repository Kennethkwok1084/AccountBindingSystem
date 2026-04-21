# 文档导航

本目录以 [完整深度研究报告](./deep-research-report.md) 为总源文档，并补充一组更适合开发、联调、部署和验收的拆分文档。

## 阅读顺序

1. [需求基线与业务规则](./product-requirements.md)
2. [系统架构设计](./system-architecture.md)
3. [数据模型与 API 约定](./data-model-and-api.md)
4. [工程澄清与风险清单](./engineering-clarifications.md)
5. [部署、运维与测试](./deployment-testing.md)
6. [备份恢复演练记录](./backup-restore-drill.md)
7. [上线前检查清单](./go-live-checklist.md)
8. [完整深度研究报告](./deep-research-report.md)

## 文档分工

| 文档 | 适用对象 | 主要内容 |
|---|---|---|
| `product-requirements.md` | 产品、后端、前端、测试 | 背景、范围、固定业务规则、核心流程、验收标准 |
| `system-architecture.md` | 后端、前端、架构设计 | 技术栈、模块边界、路由建议、并发与调度原则 |
| `data-model-and-api.md` | 后端、数据库、联调 | 核心数据模型、表职责、关键约束、API 契约、Excel 契约 |
| `engineering-clarifications.md` | 技术负责人、后端、测试 | 高风险设计点、推荐口径、并发测试重点 |
| `deployment-testing.md` | 运维、测试、实施 | 部署拓扑、安全基线、备份恢复、测试计划、实施里程碑 |
| `backup-restore-drill.md` | 运维、实施、验收 | PostgreSQL 恢复演练记录模板与当前口径 |
| `go-live-checklist.md` | 项目负责人、测试、运维 | 上线前核对项、责任归属、签收记录 |
| `deep-research-report.md` | 项目负责人、架构师 | 全量论证、DDL 草案、接口示例、实施细节、背景依据 |

## 使用建议

- 方案评审时，优先看 `product-requirements.md` 和 `system-architecture.md`。
- 后端建模和接口开发时，优先看 `data-model-and-api.md`，DDL 与完整示例再回查总报告。
- 开发前做方案收口时，优先看 `engineering-clarifications.md`，先把高风险语义对齐。
- 部署、试运行、上线前检查时，优先看 `deployment-testing.md`。
- 备份恢复演练和上线签收时，配合 `backup-restore-drill.md` 与 `go-live-checklist.md` 一起使用。
- 总报告保留为细节总库，拆分文档优先承担日常协作和执行沟通。
