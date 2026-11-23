"""Stage 1: environment check -> docs/environment_report.md"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def sh(cmd: str) -> str:
    try:
        out = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return (out.stdout + out.stderr).strip()
    except Exception as exc:
        return f"<error: {exc}>"


def collect(load_model: bool) -> dict:
    info = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "cwd": os.getcwd(),
        "cpu_count": os.cpu_count(),
        "cpu_model": sh("lscpu | grep -m1 'Model name' | cut -d: -f2").strip(),
        "memory": sh("free -h | head -2"),
        "disk_home": sh("df -h ~ | tail -1"),
        "rocm_version_file": sh("cat /opt/rocm/.info/version 2>/dev/null || echo n/a"),
        "rocm_smi": sh("rocm-smi --showproductname 2>&1 | head -20"),
        "packages": {},
    }
    try:
        import torch

        info["torch"] = torch.__version__
        info["torch_hip"] = torch.version.hip
        info["cuda_available"] = torch.cuda.is_available()
        info["gpu_count"] = torch.cuda.device_count()
        if torch.cuda.is_available():
            info["gpu_name"] = torch.cuda.get_device_name(0)
            props = torch.cuda.get_device_properties(0)
            info["gpu_total_memory_gb"] = round(props.total_memory / 1e9, 2)
            x = torch.ones((64, 64), device="cuda")
            info["gpu_matmul_ok"] = float((x @ x)[0, 0].item())
        info["backend"] = "ROCm" if getattr(torch.version, "hip", None) else "CUDA/CPU"
    except Exception as exc:
        info["torch_error"] = str(exc)
    for module in ["transformers", "accelerate", "pytest", "yaml", "pandas", "sklearn", "matplotlib", "huggingface_hub"]:
        try:
            mod = __import__(module)
            info["packages"][module] = getattr(mod, "__version__", "unknown")
        except Exception:
            info["packages"][module] = None
    info["hf_cache"] = sh("du -sh ~/.cache/huggingface 2>/dev/null || echo none")
    info["hf_models_cached"] = sh("ls ~/.cache/huggingface/hub 2>/dev/null | head -20")
    if load_model:
        from src.llm import LocalLLM

        cfg = json.loads((ROOT / "configs" / "model_check.json").read_text()) if (ROOT / "configs" / "model_check.json").exists() else {}
        model_id = cfg.get("model", "Qwen/Qwen2.5-1.5B-Instruct")
        info["model_check"] = {"model": model_id}
        llm = LocalLLM(model_id)
        info["model_check"].update(llm.memory_report, load_seconds=round(llm.load_seconds, 2))
        info["model_check"]["smoke_answer"], info["model_check"]["smoke_seconds"] = llm.generate(
            [{"role": "user", "content": "只回复 OK。"}], max_new_tokens=4
        )
    return info


def to_markdown(info: dict) -> str:
    lines = [
        "# 环境检查报告",
        "",
        f"- 检查时间：{__import__('time').strftime('%Y-%m-%d %H:%M:%S %z')}",
        f"- Python：{info['python']}",
        f"- 平台：{info['platform']}",
        f"- CPU：{info.get('cpu_model', '')} / {info['cpu_count']} 核",
        f"- 内存：{info['memory'].replace(chr(10), ' | ')}",
        f"- 磁盘：{info['disk_home']}",
        f"- PyTorch：{info.get('torch', '不可用')}",
        f"- torch.version.hip：{info.get('torch_hip')}",
        f"- torch.cuda.is_available()：{info.get('cuda_available')}",
        f"- GPU：{info.get('gpu_name', '无')}，显存 {info.get('gpu_total_memory_gb', 'n/a')} GB",
        f"- 后端判定：{info.get('backend')}",
        f"- GPU 矩阵乘测试：{info.get('gpu_matmul_ok')}",
        f"- ROCm SMI：{info['rocm_smi'].splitlines()[2] if len(info['rocm_smi'].splitlines()) > 2 else info['rocm_smi']}",
        "",
        "## 依赖",
        "",
        "| 包 | 版本 |",
        "| --- | --- |",
    ]
    for name, version in info["packages"].items():
        lines.append(f"| {name} | {version} |")
    lines += ["", "## 模型缓存", "", f"- 缓存大小：{info['hf_cache']}", f"- 已缓存模型：{info['hf_models_cached'].replace(chr(10), ', ')}", ""]
    if "model_check" in info:
        mc = info["model_check"]
        lines += [
            "## 最小模型推理测试",
            "",
            f"- 模型：{mc['model']}",
            f"- 精度：{mc.get('dtype')}，设备：{mc.get('device')}",
            f"- 加载耗时：{mc.get('load_seconds')} s",
            f"- 显存占用：{mc.get('allocated_mb')} MB（峰值 {mc.get('max_allocated_mb')} MB）",
            f"- 冒烟回答：{mc.get('smoke_answer')!r}，耗时 {mc.get('smoke_seconds'):.3f} s",
            "",
        ]
    lines += [
        "## 结论与限制",
        "",
        "- 仅当 `torch.version.hip` 非空且 GPU 名称来自 `rocm-smi` 时，才把本实验描述为 ROCm/AMD GPU 实验。",
        "- PyTorch 的 ROCm 后端复用 `torch.cuda` 接口，因此 `torch.cuda.is_available()` 不能单独用来判断 NVIDIA CUDA。",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--load-model", action="store_true")
    args = parser.parse_args()
    info = collect(args.load_model)
    docs = ROOT / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "environment.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    (docs / "environment_report.md").write_text(to_markdown(info), encoding="utf-8")
    print(json.dumps(info, ensure_ascii=False, indent=2)[:2000])


if __name__ == "__main__":
    main()
