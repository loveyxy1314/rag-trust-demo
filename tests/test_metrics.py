from src.metrics import detection_metrics, summarize


def row(label, decision, parse_failure=False, attack_type="none"):
    return {
        "label_eval": label,
        "attack_type_eval": attack_type,
        "decision": decision,
        "parse_failure": parse_failure,
    }


def test_parse_failure_rate_is_count_over_total_not_initialised_to_total():
    rows = [
        row("malicious", "quarantine", parse_failure=False, attack_type="prompt_injection"),
        row("benign", "allow", parse_failure=True),
        row("benign", "allow", parse_failure=False),
        row("benign", "review", parse_failure=False),
    ]
    metrics = detection_metrics(rows)
    assert metrics["json_parse_failure_rate"] == 0.25
    assert metrics["tp"] == 1
    assert metrics["fp"] == 1
    assert metrics["precision"] == 0.5
    assert metrics["recall"] == 1.0


def test_all_parses_succeed_gives_zero_rate():
    metrics = detection_metrics([row("benign", "allow"), row("malicious", "quarantine")])
    assert metrics["json_parse_failure_rate"] == 0.0


def record(group, retrieved, accepted, success):
    return {
        "query_id": f"q-{group}-{len(retrieved)}-{len(accepted)}-{success}",
        "group": group,
        "scene": "pre_ingestion",
        "poisoning_ratio": 0.2,
        "answer": "x",
        "attack_success": success,
        "malicious_retrieved": retrieved,
        "malicious_accepted": accepted,
        "context_texts": {},
        "total_s": 0.3,
        "detection_s": 0.0,
        "generation_s": 0.2,
        "answer_correct": not success,
        "context_count": len(accepted),
    }


def test_asr_denominators_distinguish_attacked_from_exposed():
    recs = [
        # retrieved but filtered out: counts towards attacked, not exposed
        record("g1", ["m1"], [], False),
        # exposed and successful: counts in both numerators
        record("g1", ["m2"], ["m2"], True),
        # exposed but unsuccessful: only in exposed denominator
        record("g1", ["m3"], ["m3"], False),
        # attacked with nothing exposed: exposed ASR must be undefined
        record("g2", ["m4"], [], False),
    ]
    rows, _ = summarize(recs)
    g1 = next(r for r in rows if r["group"] == "g1")
    g2 = next(r for r in rows if r["group"] == "g2")
    assert (g1["attacked_queries"], g1["exposed_queries"]) == (3, 2)
    assert round(g1["asr_on_attacked"], 4) == 0.3333
    assert g1["asr_on_exposed"] == 0.5
    assert round(g1["exposure_rate"], 4) == 0.6667
    assert g2["attacked_queries"] == 1
    assert g2["asr_on_attacked"] == 0.0
    assert g2["asr_on_exposed"] is None
    assert g2["exposure_rate"] == 0.0
