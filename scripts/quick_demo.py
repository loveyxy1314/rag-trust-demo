#!/usr/bin/env python3
"""Zero-GPU interactive/CLI end-to-end demo for rag-trust-demo.

Runs locally in < 3 seconds using the real repository modules (dataset, integrity,
provenance, offline retriever, and controlled RAG pipeline with a deterministic
extractive responder) for fast offline walkthroughs of a real query from retrieval ->
integrity -> provenance -> quarantine/allow -> audited output without downloading
multi-GB model weights.

Usage:
    python scripts/quick_demo.py
    python scripts/quick_demo.py --question "fork() 调用后父进程和子进程分别返回什么？" --ratio 0.20 --scene post_ingestion
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from src import dataset as dataset_mod  # noqa: E402
from src import integrity as integrity_mod  # noqa: E402
from src import rag_pipeline  # noqa: E402
from src.retriever import TfidfRetriever  # noqa: E402
from src.utils import read_jsonl  # noqa: E402


class PurePythonBigramRetriever:
    """Zero-dependency char-bigram cosine fallback when scikit-learn is not installed."""

    backend = "pure-python-char-bigram"

    def __init__(self):
        self.docs: list[dict] = []
        self.vecs: list[collections.Counter] = []
        self.norms: list[float] = []

    @staticmethod
    def _vec(text: str) -> tuple[collections.Counter, float]:
        s = "".join(text.lower().split())
        grams = [s[i : i + 2] for i in range(max(0, len(s) - 1))] or ([s] if s else [])
        c = collections.Counter(grams)
        norm = math.sqrt(sum(v * v for v in c.values())) or 1.0
        return c, norm

    def index(self, documents: list[dict]) -> None:
        self.docs = list(documents)
        self.vecs, self.norms = [], []
        for d in self.docs:
            c, n = self._vec(d["text"])
            self.vecs.append(c)
            self.norms.append(n)

    def search(self, question: str, top_k: int = 5) -> list[tuple[dict, float]]:
        qv, qn = self._vec(question)
        scored = []
        for d, dv, dn in zip(self.docs, self.vecs, self.norms):
            dot = sum(v * dv.get(k, 0) for k, v in qv.items())
            scored.append((d, dot / (qn * dn)))
        scored.sort(key=lambda x: -x[1])
        return scored[:top_k]


def build_offline_retriever(documents: list[dict]):
    try:
        ret = TfidfRetriever()
        ret.index(documents)
        return ret
    except ImportError:
        ret = PurePythonBigramRetriever()
        ret.index(documents)
        return ret


class LocalExtractiveLLM:
    """Deterministic offline responder for zero-GPU walkthroughs (not used in formal GPU runs)."""

    def generate(self, messages: list[dict], max_new_tokens: int = 96, temperature: float = 0.0):
        user_text = messages[-1]["content"]
        lines = [ln.strip() for ln in user_text.splitlines() if ln.strip().startswith("[")]
        if not lines:
            return "证据不足", {"offline_demo": True}
        top_line = lines[0]
        return f"（离线演示模式-基于首条放行证据）{top_line}", {"offline_demo": True}


class OfflineRuleSemanticStub:
    """Transparent offline placeholder when GPU Qwen2.5-1.5B is unavailable."""

    def detect(self, doc: dict) -> dict:
        return {
            "decision": "allow",
            "risk_score": 0.05,
            "risk_category": "offline_skipped",
            "reason": "离线快速演示未加载 GPU 1.5B 语义模型；完整性与来源规则已真实执行",
            "elapsed_s": 0.0,
            "cache_hit": False,
            "parse_failures": 0,
            "final_parse_failure": False,
            "injection_label": None,
            "fact_label": None,
        }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Zero-GPU end-to-end walkthrough of rag-trust-demo.")
    p.add_argument("--question", default="fork() 成功时，父进程和子进程分别得到什么返回值？", help="Linux technical query")
    p.add_argument("--scene", choices=["post_ingestion", "pre_ingestion"], default="post_ingestion")
    p.add_argument("--ratio", type=float, default=0.20, help="Poisoning ratio (0.0, 0.05, 0.10, 0.20)")
    p.add_argument("--group", choices=["baseline", "integrity", "combined"], default="combined")
    p.add_argument("--json", action="store_true", help="Print full JSON audit record")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    cfg = yaml.safe_load((ROOT / "configs/config.yaml").read_text(encoding="utf-8"))
    clean_docs = read_jsonl(ROOT / "data/dataset/corpus.jsonl")
    poison_pool = read_jsonl(ROOT / "data/dataset/poison.jsonl")
    queries = read_jsonl(ROOT / "data/dataset/queries.jsonl")

    # Match an existing frozen query when possible, otherwise build an ad-hoc query object
    matched = next((q for q in queries if args.question.strip() in q["question"] or q["question"] in args.question.strip()), None)
    query = matched or {
        "query_id": "demo-custom",
        "fact_id": "custom",
        "question": args.question.strip(),
        "expected_terms": [],
        "wrong_terms": [],
        "attack_markers": ["RAG_POISON_999"],
    }

    facts_data = json.loads((ROOT / "data/facts.json").read_text(encoding="utf-8"))
    facts = facts_data["facts"] if isinstance(facts_data, dict) else facts_data
    query_facts = [q["fact_id"] for q in queries]
    active_corpus, _ = dataset_mod.apply_poison(clean_docs, poison_pool, facts, query_facts, args.ratio)
    manifest = integrity_mod.build_manifest(clean_docs if args.scene == "post_ingestion" else active_corpus)
    retriever = build_offline_retriever(active_corpus)

    record = rag_pipeline.run_query(
        query=query,
        corpus=active_corpus,
        group=args.group,
        manifest=manifest,
        retriever=retriever,
        detector=OfflineRuleSemanticStub(),
        llm=LocalExtractiveLLM(),
        cfg=cfg,
        meta={"scene": args.scene, "poisoning_ratio": args.ratio},
    )

    if args.json:
        print(json.dumps(record, ensure_ascii=False, indent=2))
        return 0

    print("=" * 72)
    print(f"RAG 可信增强本地快速演示 | 场景: {args.scene} | 投毒比例: {args.ratio:.0%} | 防护组: {args.group}")
    print("=" * 72)
    print(f"输入问题: {record['question']}")
    print(f"检索 Top-{len(record['audits'])} 文档审计明细:")
    for idx, a in enumerate(record["audits"], 1):
        prov = a["provenance"]["status"] if isinstance(a["provenance"], dict) else a["provenance"]
        eval_lbl = a["evaluation_only"]["label"]
        atk = a["evaluation_only"]["attack_type"] or "none"
        print(
            f"  [{idx}] {a['doc_id']:<22} | score={a['retrieval_score']:.3f} "
            f"| integrity={a['integrity']:<14} | provenance={prov:<16} "
            f"| decision={a['decision']:<10} | (离线真值: {eval_lbl}/{atk})"
        )
    print("-" * 72)
    print(f"放行进入上下文 ({record['context_count']} 条): {record['accepted_ids']}")
    print(f"系统输出: {record['answer']}")
    print(f"耗时统计: total={record['total_s']*1000:.1f} ms (retrieval={record['retrieval_s']*1000:.1f} ms, "
          f"integrity={record['integrity_s']*1000:.2f} ms, provenance={record['provenance_s']*1000:.2f} ms)")
    print(f"说明: 本命令使用离线检索（{retriever.backend}）与离线演示响应器，未加载 GPU 1.5B 语义模型；"
          "完整 GPU 推理与 768/612 条实测结果见 docs/EVALUATION_REPORT.md。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
