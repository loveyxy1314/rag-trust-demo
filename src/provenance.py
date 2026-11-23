"""Module C: configurable provenance / source trust rules.

Source metadata in this experiment is synthetic. Verification status is a
declared attribute of the simulated source, not an authenticated signature.
Unknown sources are flagged for review, not declared malicious.
"""
from __future__ import annotations

DEFAULT_REGISTRY = {
    "man_pages": {"verified": True, "allowlisted": True},
    "kernel_docs": {"verified": True, "allowlisted": True},
    "tldp": {"verified": True, "allowlisted": True},
    "distro_wiki": {"verified": True, "allowlisted": False},
    "community_forum": {"verified": False, "allowlisted": False},
    "unknown_blog": {"verified": False, "allowlisted": False},
    "mirror_archive": {"verified": False, "allowlisted": False},
}


def assess(doc: dict, registry: dict | None = None) -> dict:
    registry = registry or DEFAULT_REGISTRY
    source = doc.get("source", "unknown")
    entry = registry.get(source, {"verified": False, "allowlisted": False})
    verified = bool(entry.get("verified"))
    allowlisted = bool(entry.get("allowlisted"))

    if verified and allowlisted:
        status, decision, reason = "trusted", "allow", "已验证且在允许列表中"
    elif verified and not allowlisted:
        status, decision, reason = "trusted_unlisted", "review", "来源已验证但不在允许列表"
    elif allowlisted and not verified:
        status, decision, reason = "spoof_suspected", "review", "声称在白名单内但未通过验证，疑似伪冒"
    else:
        status, decision, reason = "unknown", "review", "来源未知且未验证，需人工复核"

    return {
        "source": source,
        "verified": verified,
        "allowlisted": allowlisted,
        "status": status,
        "decision": decision,
        "reason": reason,
    }
