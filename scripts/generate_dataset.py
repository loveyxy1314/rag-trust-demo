"""Stage 2: generate the synthetic knowledge base (400 benign docs + 200 poison + 24 queries)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.dataset import build_dataset, load_facts, save_dataset  # noqa: E402
from src.utils import load_config, set_seed  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(ROOT / "configs" / "config.yaml"))
    parser.add_argument("--out", default=str(ROOT / "data" / "dataset"))
    parser.add_argument("--facts", default=str(ROOT / "data" / "facts.json"))
    args = parser.parse_args()
    cfg = load_config(args.config)
    set_seed(cfg["project"]["seed"])
    facts = load_facts(args.facts)
    expected = cfg["dataset"]["n_facts"]
    if len(facts) != expected:
        raise SystemExit(f"facts.json has {len(facts)} facts, config expects {expected}")
    bundle = build_dataset(facts, cfg)
    meta = save_dataset(bundle, args.out)
    print("dataset written to", args.out)
    print(json_dumps(meta))


def json_dumps(obj) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
