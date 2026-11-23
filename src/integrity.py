"""Module B: SHA-256 trusted baseline manifest and integrity verification.

Limitation (documented in the report): a matching hash only proves the bytes are
identical to the baseline. It does NOT prove the content is true, nor that the
source is authentic.
"""
from __future__ import annotations

from .utils import sha256_text

STATUS_PASS = "integrity_pass"
STATUS_FAIL = "integrity_fail"
STATUS_MISSING = "baseline_missing"


def build_manifest(documents: list[dict]) -> dict:
    """doc_id -> sha256(text). Labels and other metadata are deliberately excluded."""
    return {doc["doc_id"]: sha256_text(doc["text"]) for doc in documents}


def verify(doc: dict, manifest: dict) -> dict:
    expected = manifest.get(doc["doc_id"])
    if expected is None:
        return {"status": STATUS_MISSING, "expected": None, "actual": sha256_text(doc["text"])}
    actual = sha256_text(doc["text"])
    status = STATUS_PASS if actual == expected else STATUS_FAIL
    return {"status": status, "expected": expected, "actual": actual}


def tamper_detection_rate(modified_ids: list[str], reports: dict) -> float | None:
    if not modified_ids:
        return None
    flagged = sum(1 for doc_id in modified_ids if reports.get(doc_id, {}).get("status") == STATUS_FAIL)
    return flagged / len(modified_ids)
