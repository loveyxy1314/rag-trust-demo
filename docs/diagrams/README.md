# 架构图与流程图说明（draw.io 原文件 + 矢量 SVG）

本目录包含本项目的全部架构图与流程图。所有图表均按学术制图规范设计，提供 **`.drawio` 原生可编辑文件** 与 **真文本矢量 `.svg` 预览图**（二者由同一结构定义生成，确保内容完全一致）。

## 图表清单

| 编号 | 文件名 | 图表类型 | 核心展示内容 |
| --- | --- | --- | --- |
| 图 1 | [`fig1_system_architecture.drawio`](fig1_system_architecture.drawio) / [`.svg`](fig1_system_architecture.svg) | 系统总体架构图 | 模块 A–F 离线基线构建、在线三层筛查（完整性 + 来源 + 双分支语义检测）、受控生成与 `evaluation_only` 评价隔离红线 |
| 图 2 | [`fig2_defense_decision_flow.drawio`](fig2_defense_decision_flow.drawio) / [`.svg`](fig2_defense_decision_flow.svg) | 防护决策流程图 | 组合防护顺序拦截逻辑、检测缓存键控、Qwen2.5-1.5B 双分支短 JSON 调用与冻结阈值（0.70 / 0.40）处置分支 |
| 图 3 | [`fig3_threat_model_scenes.drawio`](fig3_threat_model_scenes.drawio) / [`.svg`](fig3_threat_model_scenes.svg) | 威胁模型对照图 | 恒定 400 文档同 ID 替换假设、I1/I2 注入与 F1/F2 错误事实载荷，以及 `post_ingestion` 与 `pre_ingestion` 两类场景的可观测性对比 |
| 图 4 | [`fig4_experiment_evolution_flow.drawio`](fig4_experiment_evolution_flow.drawio) / [`.svg`](fig4_experiment_evolution_flow.svg) | 实验演进闭环图 | 从正式轮（768 条）→ 证据粒度消融（388 条）→ API 压力测试与 GPT-6 复核（224 条）→ 语义门控 v1 失败止损（153 条）→ BGE 重排+标记（612 条）的完整迭代链 |

## 配色与视觉规范

配色采用学术论文 Science 风格色板（单图主色不超过 5 种，兼顾色盲可读性）：

- **蓝色 `#4E79A7`**（浅底 `#EBF2F7`）：输入、检索与数据处理步骤
- **橙色 `#F28E2B`**（浅底 `#FEF3E6`，加粗边框）：核心防御算法与消融实验模块
- **绿色 `#59A14F`**（浅底 `#EDF6EC`）：可信基线存储、放行输出与冻结决策
- **黄色 `#EDC948`**（浅底 `#FDF9E7`）：条件分支与阈值决策菱形节点
- **红色 `#E15759`**（浅底 `#FDECEC`）：攻击载荷、隔离拦截与负面失败止损
- **红色虚线 `#CC3311`**：评价真值隔离边界（`evaluation_only`）与评测口径约束

## 编辑与矢量导出方法

1. **在 draw.io 中二次编辑**：使用 [diagrams.net](https://app.diagrams.net/) 网页版、draw.io 桌面端或 VS Code `Draw.io Integration` 插件直接打开任意 `.drawio` 文件，所有中文标签与节点均可自由拖动和修改。
2. **重新自动生成**：运行 `python scripts/generate_diagrams.py` 可一键重新生成全部 `.drawio` 与 `.svg` 文件，并自动执行 XML 结构与前景框体无重叠校验。
3. **矢量 PDF / SVG 导出说明**：在 draw.io 中选择 `文件 -> 导出为 -> PDF`（勾选“裁剪”且不勾选“转为曲线”），或直接使用本目录的 `.svg` 矢量图嵌入 Word / LaTeX，即可保持图内文字清晰、可选中与无损缩放。
