from src.integrity import build_manifest, tamper_detection_rate, verify
from src.utils import sha256_text


def test_manifest_and_verification():
    original = [{"doc_id": "d1", "text": "fork() 子进程返回 0"}]
    manifest = build_manifest(original)
    assert manifest["d1"] == sha256_text("fork() 子进程返回 0")

    assert verify(original[0], manifest)["status"] == "integrity_pass"

    tampered = [{"doc_id": "d1", "text": "fork() 父进程返回 0"}]
    assert verify(tampered[0], manifest)["status"] == "integrity_fail"

    unknown = [{"doc_id": "d2", "text": "任意内容"}]
    assert verify(unknown[0], manifest)["status"] == "baseline_missing"


def test_tamper_detection_rate():
    reports = {"d1": {"status": "integrity_fail"}, "d2": {"status": "integrity_pass"}}
    assert tamper_detection_rate(["d1", "d2"], reports) == 0.5
    assert tamper_detection_rate([], reports) is None
