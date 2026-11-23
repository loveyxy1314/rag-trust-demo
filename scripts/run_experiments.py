#!/usr/bin/env python3
"""Module F: run the controlled experiments (groups x scenes x poisoning ratios).

Design notes
------------
* The corpus always has 400 documents. Poisoning *replaces* normal documents,
  keeping their doc_id, so recall/accuracy stay comparable across ratios.
* scene=post_ingestion : trusted manifest is built from the clean corpus, then
  documents are replaced -> integrity_fail is detectable.
* scene=pre_ingestion  : the manifest is built after poisoning (what a careless
  ingestion pipeline would do) -> hashes pass, only provenance/semantics react.
* The detector is evaluated over the whole 400-doc corpus at ratio 0.0 and 0.20
  (config), and its per-query decisions are logged for every condition.

Every record is appended and flushed immediately, so an interrupted run can be
resumed with --resume without repeating finished (scene, ratio, group, query).
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import integrity as integrity_mod  # noqa: E402
from src.dataset import apply_poison, load_dataset, load_facts  # noqa: E402
from src.integrity import build_manifest  # noqa: E402
from src.llm import LocalLLM  # noqa: E402
from src.metrics import detection_metrics, summarize  # noqa: E402
from src.provenance import assess  # noqa: E402
from src.rag_pipeline import GROUPS, run_query  # noqa: E402
from src.retriever import build_retriever  # noqa: E402
from src.semantic_detector import SemanticDetector  # noqa: E402
from src.utils import ensure_dir, load_config, read_jsonl, set_seed, sha256_text, write_json  # noqa: E402


def log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run RAG trust experiments")
    parser.add_argument("--config", default=str(ROOT / "configs" / "config.yaml"))
    parser.add_argument("--data-dir", default=str(ROOT / "data" / "dataset"))
    parser.add_argument("--facts", default=str(ROOT / "data" / "facts.json"))
    parser.add_argument("--groups", nargs="+", choices=GROUPS, default=None)
    parser.add_argument("--scenes", nargs="+", choices=["pre_ingestion", "post_ingestion"], default=None)
    parser.add_argument("--ratios", nargs="+", type=float, default=None)
    parser.add_argument("--limit", type=int, default=None, help="only the first N evaluation queries (smoke runs)")
    parser.add_argument("--run-name", default=None)
    parser.add_argument("--resume", action="store_true", help="append to an existing run directory")
    parser.add_argument("--no-detector-eval", action="store_true", help="skip the full-corpus detector evaluation")
    return parser.parse_args()


def write_csv(path: Path, rows: list[dict]) -> None:
    ensure_dir(path.parent)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def corpus_hash(corpus: list[dict]) -> str:
    return sha256_text("\n".join(sorted(d["doc_id"] + sha256_text(d["text"]) for d in corpus)))


def environment() -> dict:
    import platform

    import torch

    info = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "torch": torch.__version__,
        "hip": getattr(torch.version, "hip", None),
        "cuda_available": torch.cuda.is_available(),
    }
    if torch.cuda.is_available():
        info["gpu"] = torch.cuda.get_device_name(0)
        info["gpu_total_mb"] = round(torch.cuda.get_device_properties(0).total_memory / 2**20, 1)
    return info


def build_condition(scene: str, ratio: float, docs: list[dict], poison: list[dict], facts: list[dict],
                    query_facts: list[str]) -> tuple[list[dict], list[str], dict]:
    corpus, modified = apply_poison(docs, poison, facts, query_facts, ratio)
    if scene == "post_ingestion":
        manifest = build_manifest(docs)          # baseline taken before poisoning
    elif scene == "pre_ingestion":
        manifest = build_manifest(corpus)        # poisoned corpus registered as trusted
    else:
        raise ValueError(scene)
    return corpus, modified, manifest


def should_run_full_eval(cfg: dict, scene: str, ratio: float, first_scene: str) -> bool:
    exp = cfg["experiments"]
    if not exp.get("detector_full_corpus_eval", False):
        return False
    if ratio == 0.0:
        return scene == first_scene
    return ratio == float(exp.get("full_corpus_eval_ratio", 0.20))


def main() -> int:
    args = parse_args()
    cfg = load_config(args.config)
    exp = cfg["experiments"]
    groups = args.groups or exp["groups"]
    scenes = args.scenes or exp["scenes"]
    ratios = [float(x) for x in (args.ratios or exp["poisoning_ratios"])]
    for group in groups:
        if group not in GROUPS:
            raise SystemExit(f"unknown group: {group}")

    set_seed(cfg["project"].get("seed", 42))
    bundle = load_dataset(args.data_dir)
    facts = load_facts(args.facts)
    docs, poison, queries = bundle["docs"], bundle["poison"], bundle["queries"]
    if len(docs) != int(exp.get("corpus_size", len(docs))):
        raise SystemExit(f"corpus size mismatch: {len(docs)} != {exp.get('corpus_size')}")
    if args.limit:
        queries = queries[: args.limit]
    query_facts = sorted({q["fact_id"] for q in queries})

    out_root = resolve(cfg["project"].get("output_dir", "results"))
    run_name = args.run_name or time.strftime("%Y%m%d_%H%M%S")
    run_dir = ensure_dir(out_root / run_name)
    raw_path = run_dir / "raw.jsonl"
    eval_path = run_dir / "detect_eval.jsonl"

    if args.resume and raw_path.exists():
        records = read_jsonl(raw_path)
        log(f"resume: {len(records)} records already in {raw_path}")
    else:
        records = []
        for stale in (raw_path, eval_path):
            if stale.exists():
                stale.unlink()
    seen = {(r["scene"], r["poisoning_ratio"], r["group"], r["query_id"]) for r in records}

    eval_rows: list[dict] = read_jsonl(eval_path) if (args.resume and eval_path.exists()) else []
    evaluated = {(r["scene"], r["poisoning_ratio"]) for r in eval_rows}

    start_all = time.perf_counter()
    env = environment()
    log(f"torch={env['torch']} hip={env['hip']} gpu={env.get('gpu')}")

    model_id = cfg["models"]["generator_model"]
    detector_id = cfg["models"].get("detector_model", model_id)
    llm = LocalLLM(model_id, dtype=cfg["models"].get("dtype", "float16"), device=cfg["models"].get("device", "cuda"))
    warmup_s = llm.warmup()
    log(f"generator loaded in {llm.load_seconds:.1f}s (warmup {warmup_s:.2f}s): {model_id}")
    if detector_id == model_id:
        detector_llm = llm
        detector_load_s = 0.0
    else:
        detector_llm = LocalLLM(detector_id, dtype=cfg["models"].get("dtype", "float16"), device=cfg["models"].get("device", "cuda"))
        detector_load_s = detector_llm.load_seconds
        detector_llm.warmup()
        log(f"detector loaded in {detector_load_s:.1f}s: {detector_id}")

    cache_path = cfg["detector"].get("cache")
    detector = SemanticDetector(detector_llm, cfg, resolve(cache_path) if cache_path else None)
    log(f"detector cache entries: {len(detector.cache)}")

    retriever = build_retriever(cfg, docs)
    log(f"retriever backend: {retriever.backend}")

    conditions: list[dict] = []
    total_planned = len(scenes) * len(ratios) * len(groups) * len(queries)
    done = 0
    raw_fh = open(raw_path, "a", encoding="utf-8")
    try:
        for scene in scenes:
            for ratio in ratios:
                t_cond = time.perf_counter()
                corpus, modified, manifest = build_condition(scene, ratio, docs, poison, facts, query_facts)
                retriever.index(corpus)
                index_s = time.perf_counter() - t_cond
                n_poison = sum(1 for d in corpus if d["label"] == "malicious")
                condition = {
                    "run_name": run_name,
                    "scene": scene,
                    "poisoning_ratio": ratio,
                    "n_docs": len(corpus),
                    "n_malicious": n_poison,
                    "n_modified": len(modified),
                    "modified_ids": modified,
                    "corpus_sha256": corpus_hash(corpus),
                    "manifest_entries": len(manifest),
                    "retriever": retriever.backend,
                    "index_s": round(index_s, 3),
                }
                conditions.append(condition)
                log(f"condition scene={scene} ratio={ratio:.2f}: {n_poison} malicious, {len(modified)} modified, index {index_s:.2f}s")

                if should_run_full_eval(cfg, scene, ratio, scenes[0]) and not args.no_detector_eval and (scene, ratio) not in evaluated:
                    t_eval = time.perf_counter()
                    log(f"full-corpus detector evaluation: {len(corpus)} docs")
                    for i, doc in enumerate(corpus, 1):
                        result = detector.detect(doc)
                        eval_rows.append({
                            "scene": scene,
                            "poisoning_ratio": ratio,
                            "doc_id": doc["doc_id"],
                            "split": doc.get("split", "poison"),
                            "template_id": doc.get("template_id"),
                            "label_eval": doc["label"],
                            "attack_type_eval": doc["attack_type"],
                            "payload": doc.get("payload"),
                            "source": doc.get("source"),
                            "decision": result["decision"],
                            "risk_score": result["risk_score"],
                            "risk_category": result["risk_category"],
                            "injection_label": result["injection_label"],
                            "fact_label": result["fact_label"],
                            "parse_failure": result.get("final_parse_failure", False),
                            "parse_failures": result.get("parse_failures", 0),
                            "cache_hit": result.get("cache_hit", False),
                            "elapsed_s": result["elapsed_s"],
                        })
                        if i % 100 == 0:
                            log(f"  evaluated {i}/{len(corpus)}")
                    with open(eval_path, "w", encoding="utf-8") as fh:
                        for row in eval_rows:
                            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                    log(f"detector evaluation finished in {time.perf_counter() - t_eval:.1f}s")

                for group in groups:
                    for query in queries:
                        key = (scene, ratio, group, query["query_id"])
                        if key in seen:
                            done += 1
                            continue
                        record = run_query(query, corpus, group, manifest, retriever, detector, llm, cfg,
                                           {"scene": scene, "poisoning_ratio": ratio})
                        record["run_name"] = run_name
                        raw_fh.write(json.dumps(record, ensure_ascii=False) + "\n")
                        raw_fh.flush()
                        records.append(record)
                        seen.add(key)
                        done += 1
                        if done % 24 == 0 or done == total_planned:
                            if record.get("error"):
                                log(f"  {done}/{total_planned} error: {record['error']}")
                            else:
                                log(f"  {done}/{total_planned} scene={scene} ratio={ratio:.2f} group={group} q={query['query_id']} "
                                    f"t={record['total_s']:.2f}s")
    finally:
        raw_fh.close()

    # ---- summaries -------------------------------------------------------
    summary_rows, grading_rows = summarize(records)
    summary_rows = [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in row.items()} for row in summary_rows]
    write_csv(run_dir / "summary.csv", summary_rows)
    grading_rows = [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in row.items()} for row in grading_rows]
    write_csv(run_dir / "grading.csv", grading_rows)
    write_csv(run_dir / "manual_review.csv", [r for r in grading_rows if r["status"] == "待人工复核"])
    write_json(run_dir / "conditions.json", conditions)

    # Detector metrics over the full corpus (clean and 20% poisoned).
    eval_summary: list[dict] = []
    for scene in scenes:
        for ratio in ratios:
            rows = [r for r in eval_rows if r["scene"] == scene and r["poisoning_ratio"] == ratio]
            if not rows:
                continue
            for positive in ("flagged", "quarantine"):
                metrics = detection_metrics(rows, positive_decision=positive)
                eval_summary.append({
                    "scene": scene,
                    "poisoning_ratio": ratio,
                    "positive": positive,
                    "n": metrics["n"],
                    "tp": metrics["tp"],
                    "fp": metrics["fp"],
                    "fn": metrics["fn"],
                    "tn": metrics["tn"],
                    "precision": round(metrics["precision"], 4) if metrics["precision"] is not None else None,
                    "recall": round(metrics["recall"], 4) if metrics["recall"] is not None else None,
                    "f1": round(metrics["f1"], 4) if metrics["f1"] is not None else None,
                    "false_positive_rate": round(metrics["false_positive_rate"], 4) if metrics["false_positive_rate"] is not None else None,
                    "injection_recall": round(metrics["detection_rate_injection"], 4) if metrics["detection_rate_injection"] is not None else None,
                    "false_fact_recall": round(metrics["detection_rate_false_fact"], 4) if metrics["detection_rate_false_fact"] is not None else None,
                    "json_parse_failure_rate": round(metrics["json_parse_failure_rate"], 4) if metrics["json_parse_failure_rate"] is not None else None,
                })
    write_csv(run_dir / "detector_eval_metrics.csv", eval_summary)

    # Benign flag rate per template: is the held-out test template (T8) worse?
    template_rows: list[dict] = []
    keys = sorted({(r["scene"], r["poisoning_ratio"], r.get("template_id")) for r in eval_rows
                   if r["label_eval"] == "benign"}, key=lambda x: (x[0], x[1], str(x[2])))
    for scene, ratio, template in keys:
        rows = [r for r in eval_rows if r["scene"] == scene and r["poisoning_ratio"] == ratio
                and r["label_eval"] == "benign" and r.get("template_id") == template]
        flagged = sum(1 for r in rows if r["decision"] != "allow")
        split = rows[0].get("split") if rows else None
        template_rows.append({
            "scene": scene,
            "poisoning_ratio": ratio,
            "template_id": template,
            "split": split,
            "n": len(rows),
            "flagged": flagged,
            "flag_rate": round(flagged / len(rows), 4) if rows else None,
        })
    write_csv(run_dir / "benign_by_template.csv", template_rows)

    # Detector decisions on the documents actually retrieved, per group.
    audit_rows: list[dict] = []
    for record in records:
        for audit in record.get("audits", []):
            semantic = audit.get("semantic", {})
            if semantic.get("risk_score") is None:
                continue
            audit_rows.append({
                "scene": record["scene"],
                "poisoning_ratio": record["poisoning_ratio"],
                "group": record["group"],
                "doc_id": audit["doc_id"],
                "label_eval": audit["evaluation_only"]["label"],
                "attack_type_eval": audit["evaluation_only"]["attack_type"],
                "semantic_decision": semantic.get("decision", "allow"),
                "decision": semantic.get("decision", "allow"),
                "risk_score": semantic.get("risk_score"),
                "parse_failure": semantic.get("final_parse_failure", False),
            })
    query_detection: list[dict] = []
    keys = sorted({(r["scene"], r["poisoning_ratio"], r["group"]) for r in audit_rows})
    for scene, ratio, group in keys:
        rows = [r for r in audit_rows if (r["scene"], r["poisoning_ratio"], r["group"]) == (scene, ratio, group)]
        for positive in ("flagged", "quarantine"):
            metrics = detection_metrics(rows, positive_decision=positive)
            query_detection.append({
                "scene": scene,
                "poisoning_ratio": ratio,
                "group": group,
                "positive": positive,
                "n": metrics["n"],
                "precision": round(metrics["precision"], 4) if metrics["precision"] is not None else None,
                "recall": round(metrics["recall"], 4) if metrics["recall"] is not None else None,
                "f1": round(metrics["f1"], 4) if metrics["f1"] is not None else None,
                "false_positive_rate": round(metrics["false_positive_rate"], 4) if metrics["false_positive_rate"] is not None else None,
                "injection_recall": round(metrics["detection_rate_injection"], 4) if metrics["detection_rate_injection"] is not None else None,
                "false_fact_recall": round(metrics["detection_rate_false_fact"], 4) if metrics["detection_rate_false_fact"] is not None else None,
                "json_parse_failure_rate": round(metrics["json_parse_failure_rate"], 4) if metrics["json_parse_failure_rate"] is not None else None,
            })
    write_csv(run_dir / "query_detection_metrics.csv", query_detection)

    # Integrity: tampered documents that were retrieved and quarantined.
    integrity_rows: list[dict] = []
    for scene, ratio in sorted({(r["scene"], r["poisoning_ratio"]) for r in records}):
        condition = next((c for c in conditions if c["scene"] == scene and c["poisoning_ratio"] == ratio), None)
        modified = set(condition["modified_ids"]) if condition else set()
        for group in groups:
            if group not in {"integrity", "combined"}:
                continue
            recs = [r for r in records if (r["scene"], r["poisoning_ratio"], r["group"]) == (scene, ratio, group)]
            retrieved = integrity_failed = total_quarantined = 0
            for record in recs:
                for audit in record.get("audits", []):
                    if audit["doc_id"] in modified:
                        retrieved += 1
                        # Only count the integrity check itself; a document may also be
                        # quarantined later by provenance/semantic rules in `combined`.
                        if audit.get("integrity") == integrity_mod.STATUS_FAIL:
                            integrity_failed += 1
                        if audit["decision"] == "quarantine":
                            total_quarantined += 1
            integrity_rows.append({
                "scene": scene,
                "poisoning_ratio": ratio,
                "group": group,
                "n_tampered": len(modified),
                "tampered_retrievals": retrieved,
                "integrity_failed": integrity_failed,
                "integrity_fail_rate": round(integrity_failed / retrieved, 4) if retrieved else None,
                "total_quarantined": total_quarantined,
                "total_quarantine_rate": round(total_quarantined / retrieved, 4) if retrieved else None,
            })
    write_csv(run_dir / "integrity_stats.csv", integrity_rows)

    # Provenance decisions on retrieved documents.
    provenance_rows: list[dict] = []
    for scene, ratio in sorted({(r["scene"], r["poisoning_ratio"]) for r in records}):
        recs = [r for r in records if (r["scene"], r["poisoning_ratio"]) == (scene, ratio) and r["group"] == "combined"]
        counts: dict[str, int] = {}
        for record in recs:
            for audit in record.get("audits", []):
                status = audit.get("provenance", "not_checked")
                status = status.get("status") if isinstance(status, dict) else status
                counts[status] = counts.get(status, 0) + 1
        provenance_rows.append({"scene": scene, "poisoning_ratio": ratio, "group": "combined", **counts})
    write_csv(run_dir / "provenance_stats.csv", provenance_rows)

    cache_hits = sum(1 for r in eval_rows if r.get("cache_hit"))
    detection_times = [r["elapsed_s"] for r in eval_rows if not r.get("cache_hit") and r.get("elapsed_s")]
    meta = {
        "run_name": run_name,
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "wall_seconds": round(time.perf_counter() - start_all, 1),
        "groups": groups,
        "scenes": scenes,
        "ratios": ratios,
        "n_queries": len(queries),
        "n_records": len(records),
        "n_errors": sum(1 for r in records if r.get("error")),
        "config": {k: v for k, v in cfg.items() if k != "_config_path"},
        "config_path": cfg.get("_config_path"),
        "dataset_meta": bundle["meta"],
        "environment": env,
        "models": {
            "generator": llm.memory_report,
            "generator_load_s": round(llm.load_seconds, 3),
            "detector": detector_llm.memory_report,
            "detector_load_s": round(detector_load_s, 3),
            "warmup_s": round(warmup_s, 3),
        },
        "retriever": retriever.backend,
        "detector_eval": {
            "docs": len(eval_rows),
            "cache_hits": cache_hits,
            "mean_detection_s_per_doc": round(sum(detection_times) / len(detection_times), 4) if detection_times else None,
            "note": "per-doc time = two short constrained calls; cache hits are excluded from the mean",
        },
        "notes": [
            "poison documents replace normal documents with the same doc_id",
            "post_ingestion baseline is built before poisoning; pre_ingestion baseline is built after poisoning",
            "review documents are excluded from the generation context (conservative policy)",
            "attack success relies on exact marker matching; rule-based and conservative",
        ],
    }
    write_json(run_dir / "meta.json", meta)
    log(f"done: {len(records)} records, {len(records) and meta['n_errors']} errors, {meta['wall_seconds']}s -> {run_dir}")
    return 0 if meta["n_errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
