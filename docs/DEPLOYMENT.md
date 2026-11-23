# 部署与复现说明

本文档说明如何在 **无 GPU 本地环境（5–15 分钟跑通）** 与 **AMD GPU / ROCm 云端环境（完整复现推理）** 两种场景下部署并验证 `rag-trust-demo`。

## 一、环境要求

| 场景 | 硬件与系统 | Python | 核心依赖 | 预计耗时 |
| --- | --- | --- | --- | --- |
| 本地快速验证与离线审计 | 任意 Windows / Linux / macOS（仅 CPU） | 3.10–3.12 | `PyYAML`, `numpy`, `pandas`, `scikit-learn`, `matplotlib`, `pytest` | 安装 + 验证 < 5 分钟 |
| 完整 GPU 实验复现 | AMD Radeon AI PRO R9700（34.21 GB 显存）或同类 ≥8 GB 显存 GPU | 3.12 | 预装 ROCm PyTorch（**切勿用 pip 覆盖**）+ `requirements.txt` | 正式轮约 6 分钟（347.5 s） |

## 二、本地 CPU 快速安装与验证（无 GPU 快速复现）

```bash
# 1. 克隆仓库并进入项目目录
git clone <repository-url>
cd rag-trust-demo

# 2. 创建虚拟环境并安装核心依赖
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Linux / macOS:
# source .venv/bin/activate

pip install -r requirements.txt
```

安装完成后，按顺序运行以下四条零 GPU 命令即可在陌生环境中验证全部核心功能、单元测试、审计重算与哈希一致性：

```bash
# (1) 运行 64 项自动化回归测试（约 1-2 秒）
python -m pytest -q

# (2) 运行零 GPU 端到端真实查询演示（展示入库后篡改拦截与审计输出）
python scripts/quick_demo.py --question "fork() 在父进程和子进程中分别返回什么？" --scene post_ingestion --ratio 0.20 --group combined

# (3) 独立审计正式轮 768 条原始记录，并从 raw.jsonl 重新聚合汇总表与 5 张矢量图
python scripts/audit_formal_20261027.py
python scripts/analyze_results.py --input results/formal_20261027 --output results/formal_20261027/summary.csv --figures docs/figures

# (4) 核验重排消融 612 条记录的补充复核映射、算术与 SHA-256 哈希
python verify_rerank_review.py
```

## 三、完整 AMD GPU / ROCm 云端复现记录

本项目的正式轮与后续消融实验均在 **AUP Learning Cloud**（`tpe.aupcloud.io`）上完成，原始环境核验信息如下：

| 项目 | 实测记录 |
| --- | --- |
| 操作系统 | Linux-7.0.0-28-generic-x86_64-with-glibc2.39 |
| CPU / 内存 / 磁盘 | AMD Ryzen Threadripper PRO 9975WX（64 核）/ 251 GiB / 11 TiB |
| GPU 与显存 | AMD Radeon AI PRO R9700（34.21 GB） |
| 深度学习后端 | PyTorch `2.9.1+rocm7.13.0`（`torch.version.hip = 7.13.99004-3309c6114a`） |
| 推理模型 | `Qwen/Qwen2.5-1.5B-Instruct`（FP16，加载 3.3–3.6 s，显存约 3.1 GB） |
| 向量检索模型 | `BAAI/bge-small-zh-v1.5`（FP32；无 GPU 时代码自动回退 TF-IDF） |
| 相关性重排模型（消融轮） | `BAAI/bge-reranker-v2-m3`（固定快照 `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`，FP16，峰值分配约 1.14 GiB） |

> **ROCm 环境重要提示**：PyTorch 的 ROCm 后端复用 `torch.cuda` 接口，因此仅检查 `torch.cuda.is_available()` 不能区分 NVIDIA CUDA 与 AMD ROCm。必须同时核验 `torch.version.hip` 非空且 `rocm-smi` 识别到 AMD GPU。请勿使用 `pip install torch` 覆盖镜像预装的 ROCm PyTorch。

### 云端完整实验复现命令

```bash
# 1. 环境与 GPU 模型加载核验
python scripts/check_environment.py --load-model

# 2. 重新生成固定种子（seed=42）数据集（400 正常 + 200 投毒 + 24 问题）
python scripts/generate_dataset.py

# 3. 冒烟运行（仅跑 2 题验证全链路）
python scripts/run_experiments.py --limit 2 --run-name smoke

# 4. 正式四组 × 两场景 × 四比例实验（768 条查询，支持中断续跑）
python scripts/run_experiments.py --groups baseline integrity llm_detector combined
# 如中断可续跑：
# python scripts/run_experiments.py --resume --run-name <run_name>

# 5. 从原始记录重算全部指标、表格与图表
python scripts/analyze_results.py --input results/ --output results/summary.csv
```

## 四、常见问题排查

1. **离线环境无法连接 Hugging Face**：`scripts/quick_demo.py`、`pytest`、`analyze_results.py`、`audit_formal_20261027.py` 与 `verify_rerank_review.py` 均完全离线运行，不需要联网下载模型权重。
2. **Windows 终端中文乱码**：在 PowerShell 中先执行 `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8` 或 `chcp 65001`。
3. **重算 `audit_formal_20261027.py` 生成的临时目录**：该脚本默认把派生审计表写入 `results/review_20261027/`（已被 `.gitignore` 忽略），不会覆盖或修改原始实验产物。
