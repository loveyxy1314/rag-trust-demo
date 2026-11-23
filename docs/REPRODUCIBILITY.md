# 跨环境复现指南与独立验证记录

本文档提供在无 GPU 的普通 CPU 环境下快速验证本项目的标准步骤，并用于记录独立环境下的复现结果。

## 一、离线复现步骤（约 5 分钟，无需 GPU）

1. 在干净的虚拟环境中拉取代码并安装依赖：
   ```bash
   git clone <repository-url>
   cd rag-trust-demo
   python -m venv .venv
   # Windows PowerShell: .venv\Scripts\Activate.ps1
   # Linux / macOS:      source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. 依次运行以下四条验证命令：
   - **单元测试**：`python -m pytest -q`（预期：`64 passed`）
   - **端到端离线演示**：`python scripts/quick_demo.py --scene post_ingestion --ratio 0.20 --group combined`（预期：展示 `integrity_fail -> quarantine`、`trusted_unlisted -> review` 与 `allow` 放行输出）
   - **正式轮只读审计**：`python scripts/audit_formal_20261027.py`（预期：`records: 768`、`errors: 0`、数据集与产物哈希一致）
   - **重排复核哈希校验**：`python verify_rerank_review.py`（预期：`Verified: 44 unique source-cited reviews, 73 mapped answers, 612 covered records...`）

## 二、独立环境验证记录

| 验证环境 | 验证日期 | 操作系统与硬件 | Python 版本 | 耗时 | `pytest` | `quick_demo.py` | 审计与哈希校验 | 备注 |
| --- | --- | --- | --- | --- | :---: | :---: | :---: | --- |
| 开发环境基准 | 2026-11-23 | Windows (x64, CPU) | 3.13 / 3.12 | < 1 min | 64 passed | Pass (2.6 ms) | Pass | 本地全量验证通过 |
| 独立复现环境 1 | — | — | — | — | — | — | — | 外部环境复现后更新 |
