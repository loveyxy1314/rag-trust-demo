import json

from src.dataset import apply_poison, build_dataset, load_facts, select_poison_facts


def mini_facts(n=6):
    return [
        {
            "id": f"{i:02d}",
            "topic": "process",
            "source": "man_pages",
            "statement": f"事实{i}的正确陈述。",
            "wrong": f"事实{i}的错误陈述",
            "question": f"问题{i}是什么？",
            "answer_terms": ["正确", str(i)],
            "marker": f"事实{i}的错误陈述",
        }
        for i in range(n)
    ]


def test_build_dataset_sizes_and_truth_fields():
    cfg = {"dataset": {"n_queries": 3}}
    facts = mini_facts()
    bundle = build_dataset(facts, cfg)

    assert len(bundle["docs"]) == 6 * 8
    assert len(bundle["poison"]) == 6 * 4
    assert len(bundle["queries"]) == 3
    for doc in bundle["docs"]:
        assert doc["label"] == "benign"
        assert "attack_type" in doc
    for doc in bundle["poison"]:
        assert doc["label"] == "malicious"
        assert doc["attack_type"] in {"prompt_injection", "false_fact"}


def test_apply_poison_preserves_doc_ids():
    facts = mini_facts()
    bundle = build_dataset(facts, {"dataset": {"n_queries": 3}})
    corpus, modified = apply_poison(bundle["docs"], bundle["poison"], facts, bundle["query_facts"], 0.10)

    assert len(corpus) == 48
    assert len(modified) == 4  # 10% of 48 -> 5 rounded, but poison comes in groups of 4 per fact
    replaced = [d for d in corpus if d["doc_id"] in set(modified)]
    assert len(replaced) == len(modified)
    assert all(d["label"] == "malicious" for d in replaced)
    original_ids = {d["doc_id"] for d in bundle["docs"]}
    assert set(modified) <= original_ids


def test_poison_selection_starts_with_query_facts():
    facts = mini_facts(10)
    selected = select_poison_facts(facts, ["02", "04"], 8)
    assert selected[0] == "02"
    assert selected[1] == "04"
    assert len(selected) == 2  # four documents each


def test_dataset_is_deterministic(tmp_path):
    facts = mini_facts()
    cfg = {"dataset": {"n_queries": 3}}
    first = build_dataset(facts, cfg)
    second = build_dataset(facts, cfg)
    assert first["meta"]["doc_sha256"] == second["meta"]["doc_sha256"]
    assert first["meta"]["queries_sha256"] == second["meta"]["queries_sha256"]
    assert json.dumps(first["meta"], sort_keys=True) == json.dumps(second["meta"], sort_keys=True)
