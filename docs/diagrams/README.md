# 架构图与流程图说明（draw.io 原文件 + 矢量 SVG）

本目录包含本项目的 4 组学术论文风格架构图与流程图，均提供 **`.drawio` 原生可编辑文件** 与 **真文本矢量 `.svg` 预览图**。

## 图表清单

| 编号 | 文件名 | 图表类型 | 核心展示内容 |
| --- | --- | --- | --- |
| 图 1 | [`fig1_system_architecture.drawio`](fig1_system_architecture.drawio) / [`.svg`](fig1_system_architecture.svg) | 系统总体架构图 | 离线基线与索引、在线三层筛查与受控生成、审计重算与 `evaluation_only` 评价隔离边界（模块 A–F） |
| 图 2 | [`fig2_defense_decision_flow.drawio`](fig2_defense_decision_flow.drawio) / [`.svg`](fig2_defense_decision_flow.svg) | 防护决策流程图 | 组合防护顺序短路逻辑、检测缓存键控、Qwen2.5-1.5B 双分支短 JSON 调用与冻结阈值（0.70 / 0.40）分支 |
| 图 3 | [`fig3_threat_model_scenes.drawio`](fig3_threat_model_scenes.drawio) / [`.svg`](fig3_threat_model_scenes.svg) | 威胁模型对照图 | 恒定 400 文档同 ID 替换、提示注入与错误事实载荷，以及 `post_ingestion` 与 `pre_ingestion` 两类场景对比 |
| 图 4 | [`fig4_experiment_evolution_flow.drawio`](fig4_experiment_evolution_flow.drawio) / [`.svg`](fig4_experiment_evolution_flow.svg) | 实验演进闭环图 | 五阶段受控实验、合法引用误伤与语义门控 v1 负面止损、重排补评及最终工程冻结决策 |

## 视觉规范

采用克制的学术论文三色体系（适配黑白打印与色盲阅读，图内不内嵌演示型大标题）：

- **中性白/浅灰（`#FFFFFF` / `#F8F9FA`，深灰线 `#343A40`）**：常规数据与工程组件、虚线分组泳道
- **低饱和学术灰蓝（`#EEF3F8`，边框 `#2C5282`）**：核心防御模块、受控生成与冻结方案
- **低饱和暗红（`#FDF2F2`，边框 `#9B2C2C`）**：攻击载荷、拦截排除、负面止损及 `evaluation_only` 虚线隔离边界

## 编辑与导出方法

1. **在 draw.io 中微调**：使用 [diagrams.net](https://app.diagrams.net/)、draw.io 桌面端或 VS Code `Draw.io Integration` 插件直接打开任意 `.drawio` 文件进行编辑。
2. **命令行重新生成**：运行 `python scripts/generate_diagrams.py` 可一键重建全部 `.drawio` 与 `.svg` 文件，并自动执行 XML 结构与前景框体零重叠校验。
3. **矢量 PDF / SVG 导出**：在 draw.io 中选择 `文件 -> 导出为 -> PDF`（勾选“裁剪”且不勾选“转为曲线”），或直接使用本目录的 `.svg` 矢量图嵌入 Word / LaTeX，即可保持图内文字清晰、可选中与无损缩放。
