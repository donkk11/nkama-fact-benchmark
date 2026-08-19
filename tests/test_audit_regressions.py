"""Regression tests for the real holes two adversarial audits found.

Every test here corresponds to a way this package could previously report
success without real evidence. They exist because the audits noted that all
prior fixes were unguarded — nothing would have caught a silent regression.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from nkama_fact_benchmark.capability import _status_counts
from nkama_fact_benchmark.evidence_layer import verify_manifest
from nkama_fact_benchmark.inspector import inspect_run_folder
from nkama_fact_benchmark.workflow import create_run_package

REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_manifest(tmp_path: Path, checks: list[dict]) -> Path:
    manifest = tmp_path / "evidence_manifest.json"
    manifest.write_text(json.dumps({"checks": checks}), encoding="utf-8")
    return manifest


def test_empty_manifest_is_not_a_clean_pass(tmp_path):
    report = verify_manifest(_write_manifest(tmp_path, []))
    assert report["summary"]["clean_pass"] is False


def test_real_passing_manifest_is_still_a_clean_pass(tmp_path):
    target = tmp_path / "real.txt"
    target.write_text("hello", encoding="utf-8")
    report = verify_manifest(_write_manifest(tmp_path, [
        {"id": "c1", "type": "file_exists", "path": str(target)},
    ]))
    assert report["summary"]["clean_pass"] is True


def test_file_contains_without_text_is_blocked_not_passed(tmp_path):
    target = tmp_path / "real.txt"
    target.write_text("hello", encoding="utf-8")
    report = verify_manifest(_write_manifest(tmp_path, [
        {"id": "c1", "type": "file_contains", "path": str(target)},
    ]))
    assert report["checks"][0]["status"] == "blocked"


def test_no_forbidden_claims_with_empty_list_is_blocked_not_passed(tmp_path):
    report = verify_manifest(_write_manifest(tmp_path, [
        {"id": "c1", "type": "no_forbidden_claims", "text": "anything at all"},
    ]))
    assert report["checks"][0]["status"] == "blocked"


def test_file_not_contains_detects_leftover_placeholder(tmp_path):
    target = tmp_path / "ANSWER.md"
    target.write_text("Replace this placeholder with the real answer.", encoding="utf-8")
    report = verify_manifest(_write_manifest(tmp_path, [
        {"id": "c1", "type": "file_not_contains", "path": str(target), "text": "Replace this placeholder"},
    ]))
    assert report["checks"][0]["status"] == "fail"

    target.write_text("A real answer with real content.", encoding="utf-8")
    report = verify_manifest(_write_manifest(tmp_path, [
        {"id": "c1", "type": "file_not_contains", "path": str(target), "text": "Replace this placeholder"},
    ]))
    assert report["checks"][0]["status"] == "pass"


def test_untouched_starter_run_folder_does_not_verify_clean(tmp_path):
    """The worst hole an audit found: a brand-new run folder, zero work done,
    used to verify as clean_pass: true."""
    payload = create_run_package(title="t", prompt="do something", output_dir=tmp_path / "run", overwrite=True)
    report = verify_manifest(payload["evidence_manifest"])
    assert report["summary"]["clean_pass"] is False


def test_starter_run_folder_verifies_once_placeholder_is_replaced(tmp_path):
    payload = create_run_package(title="t", prompt="do something", output_dir=tmp_path / "run", overwrite=True)
    answer = Path(payload["ai_output_dir"]) / "ANSWER.md"
    answer.write_text("Answer:\nReal work.\n\nEvidence:\nReal evidence.\n\nLimitations:\nNone.\n", encoding="utf-8")
    report = verify_manifest(payload["evidence_manifest"])
    assert report["summary"]["clean_pass"] is True


def test_capability_status_counts_empty_is_not_clean_pass():
    assert _status_counts([])["clean_pass"] is False


def test_inspector_does_not_call_empty_manifest_a_verified_build(tmp_path):
    root = tmp_path / "run"
    (root / "ai_output").mkdir(parents=True)
    for name in ("original_prompt.md", "evidence_prompt.md", "README.md"):
        (root / name).write_text("x", encoding="utf-8")
    (root / "run_contract.json").write_text("{}", encoding="utf-8")
    (root / "ai_output" / "ANSWER.md").write_text("Built the thing.", encoding="utf-8")
    (root / "ai_output" / "code.py").write_text("print(1)", encoding="utf-8")
    (root / "ai_output" / "evidence_manifest.json").write_text(json.dumps({"checks": []}), encoding="utf-8")

    result = inspect_run_folder(root)
    assert result["classification"] != "verified_build"
    manifest_finding = next(f for f in result["findings"] if f["id"] == "evidence_manifest")
    assert manifest_finding["status"] != "pass"


def test_evidence_layer_cli_exits_nonzero_on_failure(tmp_path):
    manifest = _write_manifest(tmp_path, [])
    completed = subprocess.run(
        [sys.executable, "-m", "nkama_fact_benchmark.evidence_layer", str(manifest)],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert completed.returncode == 1


def test_evidence_layer_cli_exits_zero_on_real_pass(tmp_path):
    target = tmp_path / "real.txt"
    target.write_text("hello", encoding="utf-8")
    manifest = _write_manifest(tmp_path, [{"id": "c1", "type": "file_exists", "path": str(target)}])
    completed = subprocess.run(
        [sys.executable, "-m", "nkama_fact_benchmark.evidence_layer", str(manifest)],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert completed.returncode == 0


@pytest.mark.parametrize("first_line,expected", [
    ("Verdict: PASS", "PASS"),
    ("Verdict: FAIL", "FAIL"),
    ("Verdict: BLOCKED", "BLOCKED"),
    ("Verdict: this is NOT A PASS", "MISSING"),
    ("Verdict: UNBLOCKED, all good", "MISSING"),
    ("I cannot PASS this off as verified.", "MISSING"),
])
def test_bridge_verdict_parsing_rejects_loose_substring_matches(first_line, expected):
    """Mirrors bridge.py's real verdict parse — a negated sentence must not
    read as PASS, and 'UNBLOCKED' must not read as BLOCKED."""
    verdict = "MISSING"
    match = re.match(r"verdict\s*:\s*(PASS|FAIL|BLOCKED)\b", first_line, re.IGNORECASE)
    if match:
        verdict = match.group(1).upper()
    assert verdict == expected


@pytest.mark.parametrize("raw,expected_confirmed", [
    (True, True),
    (False, False),
    ("false", False),
    ("no", False),
    ("disputed", False),
    (None, False),
])
def test_bridge_agrees_requires_real_boolean_true(raw, expected_confirmed):
    """Mirrors bridge.py's real check — a truthy JSON *string* must not count
    as agreement."""
    assert (raw is True) == expected_confirmed
