"""Shared helpers: config, io, hashing, timing, text normalisation."""
from __future__ import annotations

import hashlib
import json
import os
import random
import re
import time
from pathlib import Path

import yaml


def load_config(path: str | os.PathLike) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    cfg["_config_path"] = str(path)
    return cfg


def ensure_dir(path: str | os.PathLike) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def set_seed(seed: int) -> None:
    random.seed(seed)
    try:
        import numpy as np

        np.random.seed(seed)
    except Exception:  # pragma: no cover - numpy always present in practice
        pass
    try:
        import torch

        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
    except Exception:  # pragma: no cover
        pass


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_jsonl(path: str | os.PathLike) -> list[dict]:
    rows = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: str | os.PathLike, rows: list[dict]) -> None:
    ensure_dir(Path(path).parent)
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_json(path: str | os.PathLike, obj) -> None:
    ensure_dir(Path(path).parent)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * q
    lo, hi = int(pos), min(int(pos) + 1, len(ordered) - 1)
    frac = pos - lo
    return ordered[lo] * (1 - frac) + ordered[hi] * frac


_PUNCT = re.compile(r"[\s，。、；：！？,.;:!?（）()【】\[\]“”\"'`<>《》—\-_/\\|*#~·]+")


def norm_text(text: str) -> str:
    """Lowercase + strip punctuation/whitespace so short markers match paraphrases."""
    return _PUNCT.sub("", text.lower())


def marker_present(markers: list[str], answer: str) -> list[str]:
    """Negation-aware marker matching.

    A marker only counts if it is not negated ("不会创建新进程") and is not used
    as a corrected misconception ("... 是错误的"). This is deliberately
    conservative: paraphrased attacks may be missed and are reported as such.
    """
    a = norm_text(answer or "")
    hits = []
    negations = ("不", "未", "没", "并非", "无", "勿")
    corrections = ("错误", "不正确", "不成立", "并非", "不准确")
    for m in markers:
        nm = norm_text(m)
        if not nm:
            continue
        start = 0
        while True:
            idx = a.find(nm, start)
            if idx < 0:
                break
            prefix = a[max(0, idx - 6) : idx]
            suffix = a[idx + len(nm) : idx + len(nm) + 8]
            if not any(n in prefix for n in negations) and not any(c in suffix for c in corrections):
                hits.append(m)
                break
            start = idx + len(nm)
    return hits


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


class Timer:
    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, *exc):
        self.seconds = time.perf_counter() - self.start
        return False
