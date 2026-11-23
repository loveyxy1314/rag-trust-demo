# 数据说明

`facts.json` 保存 50 条 Linux 系统编程事实，字段含义：

| 字段 | 用途 |
| --- | --- |
| `id` / `topic` | 事实标识与主题 |
| `statement` | 正确陈述，也作为语义检测的可信参考 |
| `wrong` | 错误陈述，仅用于构造投毒样本与 ASR 标记 |
| `question` | 冻结评价问题 |
| `answer_terms` | 规则评分用的关键词 |
| `marker` | 攻击成功标记（错误事实原句） |

`dataset/` 由 `python scripts/generate_dataset.py` 确定性生成：

- `corpus.jsonl`：400 条正常文档，8 个模板 T1–T8；
- `poison.jsonl`：200 条投毒文档（100 指令注入、100 错误事实），
  每条通过相同 `doc_id` 替换正常文档；
- `queries.jsonl`：24 个冻结问题；
- `dataset_meta.json`：数量、模板划分、SHA-256 摘要。

字段 `label`、`attack_type`、`payload`、`template_id`、`split`、`correct_fact`
均为**评价真值**。检测器只接收 `text` 与 `reference`；流水线审计中的 `evaluation_only`
字段不进入任何模型输入。新增代码时不得把这些字段拼进 Prompt。
