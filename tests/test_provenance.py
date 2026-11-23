from src.provenance import assess


def test_verified_allowlisted_source_is_allowed():
    result = assess({"source": "man_pages"})
    assert result["status"] == "trusted"
    assert result["decision"] == "allow"


def test_verified_but_unlisted_source_goes_to_review():
    result = assess({"source": "distro_wiki"})
    assert result["status"] == "trusted_unlisted"
    assert result["decision"] == "review"


def test_unknown_source_is_reviewed_not_declared_malicious():
    result = assess({"source": "random_blog"})
    assert result["status"] == "unknown"
    assert result["decision"] == "review"


def test_spoofed_allowlist_is_flagged():
    registry = {"man_pages": {"verified": False, "allowlisted": True}}
    result = assess({"source": "man_pages"}, registry)
    assert result["status"] == "spoof_suspected"
    assert result["decision"] == "review"
