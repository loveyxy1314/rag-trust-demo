#!/usr/bin/env python3
"""Module F (analysis): metrics, markdown tables and figures.

Usage
-----
python scripts/analyze_results.py --input results/ --output results/summary.csv

If --input points at the results root, the newest run directory containing
raw.jsonl is used. All numbers are recomputed from raw records; nothing is
hard-coded.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from src.metrics import summarize  # noqa: E402
from src.utils import ensure_dir, read_jsonl, write_json  # noqa: E402

GROUPS = ["baseline", "integrity", "llm_detector", "combined"]
SCENES = ["pre_ingestion", "post_ingestion"]

# Science-style colorblind-friendly academic palette
SCIENCE_COLORS = ["#4E79A7", "#F28E2B", "#59A14F", "#E15759", "#76B7B2"]
plt.rcParams["axes.prop_cycle"] = plt.cycler(color=SCIENCE_COLORS)
plt.rcParams["svg.fonttype"] = "none"  # keep true selectable text in exported SVG


def _save_figure(fig, out: Path) -> None:
    fig.savefig(out, dpi=300, bbox_inches="tight")
    fig.savefig(out.with_suffix(".svg"), bbox_inches="tight")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(ROOT / "results"))
    parser.add_argument("--output", default=None, help="path of summary.csv")
    parser.add_argument("--figures", default=None, help="figure directory")
    return parser.parse_args()


def find_run(path: Path) -> Path:
    path = path.resolve()
    if (path / "raw.jsonl").exists():
        return path
    candidates = [p for p in path.iterdir() if p.is_dir() and (p / "raw.jsonl").exists()]
    if not candidates:
        raise SystemExit(f"no run directory with raw.jsonl under {path}")
    return max(candidates, key=lambda p: (p / "raw.jsonl").stat().st_mtime)


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def fmt(value, digits: int = 3) -> str:
    if value is None or value == "":
        return "—"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number != number:  # NaN
        return "—"
    return f"{number:.{digits}f}"


def write_csv(path: Path, rows: list[dict]) -> None:
    ensure_dir(path.parent)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def markdown_table(rows: list[dict], columns: list[tuple[str, str]]) -> str:
    if not rows:
        return "_（无数据）_\n"
    head = "| " + " | ".join(label for _, label in columns) + " |\n"
    sep = "| " + " | ".join("---" for _ in columns) + " |\n"
    body = ""
    for row in rows:
        body += "| " + " | ".join(str(row.get(key, "")) for key, _ in columns) + " |\n"
    return head + sep + body


def plot_asr(summary: list[dict], ratios: list[float], out: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), sharey=True)
    width = 0.8 / len(GROUPS)
    positions = list(range(len(ratios)))
    for ax, scene in zip(axes, SCENES):
        for i, group in enumerate(GROUPS):
            xs, ys = [], []
            for p, ratio in zip(positions, ratios):
                row = next((r for r in summary if r["scene"] == scene and r["poisoning_ratio"] == ratio and r["group"] == group), None)
                if row and row.get("asr_on_attacked") is not None:
                    xs.append(p + (i - 1.5) * width)
                    ys.append(float(row["asr_on_attacked"]))
            if xs:
                bars = ax.bar(xs, ys, width=width, label=group)
                for bar, value in zip(bars, ys):
                    ax.text(bar.get_x() + bar.get_width() / 2, value + 0.012, f"{value:.2f}",
                            ha="center", va="bottom", fontsize=6, rotation=90)
        ax.set_xticks(positions)
        ax.set_xticklabels([f"{r:.2f}" for r in ratios])
        ax.set_title(f"ASR on attacked queries ({scene})")
        ax.set_xlabel("poisoning ratio")
        ax.set_ylim(0, 1.08)
        ax.grid(axis="y", alpha=0.3)
    axes[0].set_ylabel("attack success rate")
    axes[0].legend(fontsize=8)
    fig.tight_layout()
    _save_figure(fig, out)
    plt.close(fig)


def plot_accuracy(summary: list[dict], ratios: list[float], out: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), sharey=True)
    width = 0.8 / len(GROUPS)
    positions = list(range(len(ratios)))
    for ax, scene in zip(axes, SCENES):
        for i, group in enumerate(GROUPS):
            xs, ys = [], []
            for p, ratio in zip(positions, ratios):
                row = next((r for r in summary if r["scene"] == scene and r["poisoning_ratio"] == ratio and r["group"] == group), None)
                if row and row.get("answer_accuracy") is not None:
                    xs.append(p + (i - 1.5) * width)
                    ys.append(float(row["answer_accuracy"]))
            if xs:
                bars = ax.bar(xs, ys, width=width, label=group)
                for bar, value in zip(bars, ys):
                    ax.text(bar.get_x() + bar.get_width() / 2, value + 0.012, f"{value:.2f}",
                            ha="center", va="bottom", fontsize=6, rotation=90)
        ax.set_xticks(positions)
        ax.set_xticklabels([f"{r:.2f}" for r in ratios])
        ax.set_title(f"Rule-based answer accuracy ({scene})")
        ax.set_xlabel("poisoning ratio")
        ax.set_ylim(0, 1.08)
        ax.grid(axis="y", alpha=0.3)
    axes[0].set_ylabel("accuracy")
    axes[0].legend(fontsize=8)
    fig.tight_layout()
    _save_figure(fig, out)
    plt.close(fig)


def plot_detection(rows: list[dict], out: Path) -> None:
    flagged = [r for r in rows if str(r["positive"]) == "flagged"]
    if not flagged:
        return
    poisoned = [r for r in flagged if str(r.get("recall", "")) not in ("", "None", "nan")]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    if poisoned:
        labels = [f"{r['scene']} @ {fmt(r['poisoning_ratio'], 2)}" for r in poisoned]
        metrics = [("precision", "Precision"), ("recall", "Recall"), ("f1", "F1")]
        width = 0.8 / len(metrics)
        positions = list(range(len(poisoned)))
        for i, (key, label) in enumerate(metrics):
            values = [float(r[key]) for r in poisoned]
            xs = [p + (i - 1.5) * width for p in positions]
            axes[0].bar(xs, values, width=width, label=label)
        axes[0].set_xticks(positions)
        axes[0].set_xticklabels(labels, rotation=12, fontsize=8)
        axes[0].set_ylim(0, 1.05)
        axes[0].set_title("Detector P/R/F1 at 20% poisoning")
        axes[0].grid(axis="y", alpha=0.3)
        axes[0].legend(fontsize=8, ncol=3)

    labels = [f"{r['scene']} @ {fmt(r['poisoning_ratio'], 2)}" for r in flagged]
    values = [float(r["false_positive_rate"]) if r.get("false_positive_rate") not in (None, "") else 0.0 for r in flagged]
    xs = list(range(len(flagged)))
    bars = axes[1].bar(xs, values, width=0.55, color="#E15759")
    for bar, value in zip(bars, values):
        axes[1].text(bar.get_x() + bar.get_width() / 2, value + 0.0008, f"{value:.4f}",
                     ha="center", va="bottom", fontsize=7, rotation=90)
    axes[1].set_xticks(xs)
    axes[1].set_xticklabels(labels, rotation=12, fontsize=8)
    axes[1].set_ylim(0, max(values) * 1.35 if max(values) else 0.01)
    axes[1].set_title("False positive rate (benign documents)")
    axes[1].grid(axis="y", alpha=0.3)
    fig.suptitle("Semantic detector on the full corpus (review+quarantine = flagged)", fontsize=10)
    fig.tight_layout()
    _save_figure(fig, out)
    plt.close(fig)


def plot_latency(summary: list[dict], out: Path, scene: str = "post_ingestion", ratio: float = 0.20) -> None:
    rows = [r for r in summary if r["scene"] == scene and r["poisoning_ratio"] == ratio]
    if not rows:
        return
    rows = sorted(rows, key=lambda r: GROUPS.index(r["group"]))
    labels = [r["group"] for r in rows]
    means = [float(r["total_s_mean"]) for r in rows]
    p95 = [float(r["total_s_p95"]) for r in rows]
    xs = list(range(len(rows)))
    fig, ax = plt.subplots(figsize=(7.5, 4))
    bars1 = ax.bar([x - 0.2 for x in xs], means, width=0.4, label="mean")
    bars2 = ax.bar([x + 0.2 for x in xs], p95, width=0.4, label="P95")
    for bars, values in ((bars1, means), (bars2, p95)):
        for bar, value in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, value + 0.012, f"{value:.2f}",
                    ha="center", va="bottom", fontsize=7)
    ax.set_xticks(xs)
    ax.set_xticklabels(labels)
    ax.set_ylabel("seconds / query")
    ax.set_ylim(0, max(p95) * 1.15)
    ax.set_title(f"End-to-end latency ({scene}, ratio {ratio:.2f})")
    ax.grid(axis="y", alpha=0.3)
    ax.legend()
    fig.tight_layout()
    _save_figure(fig, out)
    plt.close(fig)


def plot_affected(summary: list[dict], out: Path, scene: str = "post_ingestion", ratios: tuple[float, ...] = (0.0, 0.2)) -> None:
    panels = []
    for ratio in ratios:
        rows = [r for r in summary if r["scene"] == scene and r["poisoning_ratio"] == ratio]
        if rows:
            panels.append((ratio, sorted(rows, key=lambda r: GROUPS.index(r["group"]))))
    if not panels:
        return
    top = max(int(r["normal_quarantined"]) + int(r["normal_reviewed"]) for _, rows in panels for r in rows)
    fig, axes = plt.subplots(1, len(panels), figsize=(5.6 * len(panels), 4), sharey=True, squeeze=False)
    axes = axes[0]
    for ax, (ratio, rows) in zip(axes, panels):
        labels = [r["group"] for r in rows]
        quarantined = [int(r["normal_quarantined"]) for r in rows]
        reviewed = [int(r["normal_reviewed"]) for r in rows]
        xs = list(range(len(rows)))
        ax.bar(xs, quarantined, label="normal quarantined")
        ax.bar(xs, reviewed, bottom=quarantined, label="normal sent to review")
        for x, q, r in zip(xs, quarantined, reviewed):
            ax.text(x, q + r + 0.2, f"q={q}, r={r}", ha="center", va="bottom", fontsize=8)
        ax.set_xticks(xs)
        ax.set_xticklabels(labels)
        ax.set_title("Clean corpus" if ratio == 0 else f"{ratio:.0%} poisoning")
        ax.set_ylim(0, max(top * 1.4, 1))
        ax.grid(axis="y", alpha=0.3)
    axes[0].set_ylabel("retrieved benign documents affected")
    axes[-1].legend(loc="upper left")
    fig.suptitle(f"Benign documents blocked by each group ({scene})")
    fig.tight_layout()
    _save_figure(fig, out)
    plt.close(fig)


def main() -> int:
    args = parse_args()
    run_dir = find_run(Path(args.input))
    records = read_jsonl(run_dir / "raw.jsonl")
    if not records:
        raise SystemExit("raw.jsonl is empty")
    summary_rows, grading_rows = summarize(records)
    ratios = sorted({float(r["poisoning_ratio"]) for r in summary_rows})
    scenes = [s for s in SCENES if any(r["scene"] == s for r in summary_rows)]

    output = Path(args.output) if args.output else run_dir / "summary.csv"
    ensure_dir(output.parent)
    rounded_summary = [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in row.items()} for row in summary_rows]
    write_csv(output, rounded_summary)
    write_csv(run_dir / "grading.csv",
              [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in row.items()} for row in grading_rows])
    write_csv(run_dir / "manual_review.csv", [r for r in grading_rows if r["status"] == "待人工复核"])

    fig_dir = ensure_dir(Path(args.figures) if args.figures else run_dir / "figures")
    plot_asr(summary_rows, ratios, fig_dir / "fig_asr.png")
    plot_accuracy(summary_rows, ratios, fig_dir / "fig_accuracy.png")
    plot_latency(summary_rows, fig_dir / "fig_latency.png")
    plot_affected(summary_rows, fig_dir / "fig_normal_affected.png")
    detector_rows = read_csv(run_dir / "detector_eval_metrics.csv")
    plot_detection(detector_rows, fig_dir / "fig_detector.png")

    # ---- markdown tables -------------------------------------------------
    table = []
    for scene in scenes:
        for ratio in ratios:
            for group in GROUPS:
                row = next((r for r in summary_rows if r["scene"] == scene and r["poisoning_ratio"] == ratio and r["group"] == group), None)
                if not row:
                    continue
                table.append({
                    "scene": scene,
                    "ratio": f"{ratio:.2f}",
                    "group": group,
                    "n": row["n_queries"],
                    "attacked": row["attacked_queries"],
                    "exposed": row["exposed_queries"],
                    "exposure": fmt(row["exposure_rate"]),
                    "asr_exposed": fmt(row["asr_on_exposed"]),
                    "asr_attacked": fmt(row["asr_on_attacked"]),
                    "accuracy": fmt(row["answer_accuracy"]),
                    "evidence": fmt(row["evidence_support_rate"]),
                    "normal_quar": row["normal_quarantined"],
                    "normal_rev": row["normal_reviewed"],
                    "errors": row["errors"],
                    "mean_s": fmt(row["total_s_mean"], 2),
                    "p95_s": fmt(row["total_s_p95"], 2),
                })
    try:
        run_display = run_dir.relative_to(ROOT).as_posix()
    except ValueError:
        run_display = run_dir.name
    try:
        output_display = output.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        output_display = output.name
    md = ["# 实验结果表（由 analyze_results.py 自动生成）\n",
          f"运行目录：`{run_display}`；记录数：{len(records)}；问题数：{len({r['query_id'] for r in records})}。\n",
          "## 1. 分组总表\n",
          markdown_table(table, [
              ("scene", "场景"), ("ratio", "投毒比例"), ("group", "组别"), ("n", "问题数"),
              ("attacked", "检索含恶意的问题数"), ("exposed", "恶意进入上下文的问题数"), ("exposure", "暴露率"),
              ("asr_exposed", "ASR(暴露问题)"), ("asr_attacked", "ASR(被攻击问题)"),
              ("accuracy", "回答正确率"), ("evidence", "证据支持率"), ("normal_quar", "正常文档误隔离"),
              ("normal_rev", "正常文档送复核"), ("errors", "错误"), ("mean_s", "均值秒"), ("p95_s", "P95秒")])]

    det_rows = read_csv(run_dir / "detector_eval_metrics.csv")
    det_md = [{
        "scene": r["scene"], "ratio": f"{float(r['poisoning_ratio']):.2f}", "positive": r["positive"],
        "n": r["n"], "precision": fmt(r["precision"]), "recall": fmt(r["recall"]), "f1": fmt(r["f1"]),
        "fpr": fmt(r["false_positive_rate"]), "inj": fmt(r["injection_recall"]),
        "fact": fmt(r["false_fact_recall"]), "parse_fail": fmt(r["json_parse_failure_rate"]),
    } for r in det_rows]
    md += ["\n## 2. 检测器全语料评价\n",
           markdown_table(det_md, [("scene", "场景"), ("ratio", "比例"), ("positive", "判正口径"), ("n", "文档数"),
                                   ("precision", "P"), ("recall", "R"), ("f1", "F1"), ("fpr", "FPR"),
                                   ("inj", "注入召回"), ("fact", "错误事实召回"), ("parse_fail", "解析失败率")])]

    integrity_rows = read_csv(run_dir / "integrity_stats.csv")
    md += ["\n## 3. 完整性校验（按哈希判定统计，不把来源/语义隔离算作完整性命中）\n",
           markdown_table([{k: (fmt(v) if k.endswith("rate") else v) for k, v in r.items()} for r in integrity_rows],
                          [("scene", "场景"), ("poisoning_ratio", "比例"), ("group", "组别"), ("n_tampered", "篡改文档数"),
                           ("tampered_retrievals", "被检索次数"), ("integrity_failed", "哈希判失败"),
                           ("integrity_fail_rate", "完整性检出率"), ("total_quarantined", "最终隔离"),
                           ("total_quarantine_rate", "最终隔离率")])]

    template_rows = read_csv(run_dir / "benign_by_template.csv")
    template_scene = template_rows[0]["scene"] if template_rows else None
    template_rows = [r for r in template_rows if r["scene"] == template_scene]
    md += ["\n## 3b. 语义检测对正常文档的误报率（按模板，模板切分见数据集说明）\n",
           markdown_table([{k: (fmt(v) if k == "flag_rate" else v) for k, v in r.items()} for r in template_rows],
                          [("poisoning_ratio", "比例"), ("template_id", "模板"), ("split", "划分"), ("n", "文档数"),
                           ("flagged", "被复核/隔离"), ("flag_rate", "误报率")])]

    query_det = read_csv(run_dir / "query_detection_metrics.csv")
    md += ["\n## 4. 检索文档上的语义检测（按组）\n",
           markdown_table([{k: (fmt(v) if k in {"precision", "recall", "f1", "false_positive_rate", "injection_recall", "false_fact_recall", "json_parse_failure_rate"} else v)
                            for k, v in r.items()} for r in query_det],
                          [("scene", "场景"), ("poisoning_ratio", "比例"), ("group", "组别"), ("positive", "判正口径"),
                           ("n", "文档数"), ("precision", "P"), ("recall", "R"), ("f1", "F1"),
                           ("false_positive_rate", "FPR"), ("injection_recall", "注入召回"), ("false_fact_recall", "事实召回")])]

    # ---- automatic observations (numbers only) ---------------------------
    observations = []
    for scene in scenes:
        for ratio in ratios:
            base = next((r for r in summary_rows if r["scene"] == scene and r["poisoning_ratio"] == ratio and r["group"] == "baseline"), None)
            comb = next((r for r in summary_rows if r["scene"] == scene and r["poisoning_ratio"] == ratio and r["group"] == "combined"), None)
            if base and comb:
                observations.append(
                    f"- {scene} @ {ratio:.2f}: baseline ASR(被攻击)={fmt(base['asr_on_attacked'])}，ASR(暴露)={fmt(base['asr_on_exposed'])}；"
                    f"combined ASR(被攻击)={fmt(comb['asr_on_attacked'])}，ASR(暴露)={fmt(comb['asr_on_exposed'])}，"
                    f"暴露率={fmt(comb['exposure_rate'])}；"
                    f"正常文档误隔离 {base['normal_quarantined']} → {comb['normal_quarantined']}，"
                    f"平均时延 {fmt(base['total_s_mean'], 2)}s → {fmt(comb['total_s_mean'], 2)}s。"
                )
    if det_rows:
        for row in det_rows:
            if str(row["positive"]) == "flagged":
                observations.append(
                    f"- 检测器（{row['scene']} @ {float(row['poisoning_ratio']):.2f}）：P={fmt(row['precision'])}，R={fmt(row['recall'])}，"
                    f"F1={fmt(row['f1'])}，FPR={fmt(row['false_positive_rate'])}，解析失败率={fmt(row['json_parse_failure_rate'])}。"
                )
    md += ["\n## 5. 关键数值（自动摘录，不含结论性推断）\n", "\n".join(observations) + "\n"]
    (run_dir / "tables.md").write_text("\n".join(md), encoding="utf-8")

    analysis = {
        "run_dir": run_display,
        "n_records": len(records),
        "figures": sorted(p.name for p in fig_dir.glob("*.png")),
        "summary_csv": output_display,
        "observations": observations,
    }
    write_json(run_dir / "analysis.json", analysis)
    print(f"summary -> {output}")
    print(f"figures -> {fig_dir}")
    print(f"tables  -> {run_dir / 'tables.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
