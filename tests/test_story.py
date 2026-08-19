"""Regression coverage for the Nkama Voice (story.py).

Guards the multi-line 'Answer:' truncation bug found and fixed 2026-07-23:
the hook must capture the full paragraph, not just its first line.
"""
from __future__ import annotations

import json
from pathlib import Path

from nkama_fact_benchmark.story import build_story


def _write_run(tmp_path: Path, *, answer_text: str, checks: list[dict]) -> Path:
    ai_output = tmp_path / "ai_output"
    ai_output.mkdir(parents=True)
    (ai_output / "ANSWER.md").write_text(answer_text, encoding="utf-8")
    manifest = {"schema_version": 1, "checks": checks}
    manifest_path = ai_output / "evidence_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path


def test_hook_captures_full_multiline_answer_paragraph(tmp_path):
    answer = (
        "Answer: This sentence deliberately wraps across two physical\n"
        "lines before the paragraph ends.\n\n"
        "Second paragraph should not be included.\n"
    )
    manifest_path = _write_run(
        tmp_path,
        answer_text=answer,
        checks=[{"id": "a", "name": "A", "type": "file_exists", "path": "ANSWER.md"}],
    )
    story = build_story(manifest_path)
    assert "wraps across two physical lines before the paragraph ends." in story
    assert "Second paragraph" not in story


def test_clean_pass_story_has_no_failure_section(tmp_path):
    manifest_path = _write_run(
        tmp_path,
        answer_text="Answer: All good.\n",
        checks=[{"id": "a", "name": "A", "type": "file_exists", "path": "ANSWER.md"}],
    )
    story = build_story(manifest_path)
    assert "clean_pass" in story
    assert "What didn't hold up" not in story


def test_failed_check_is_disclosed_not_hidden(tmp_path):
    manifest_path = _write_run(
        tmp_path,
        answer_text="Answer: One check will fail on purpose.\n",
        checks=[
            {"id": "a", "name": "Real file", "type": "file_exists", "path": "ANSWER.md"},
            {"id": "b", "name": "Missing file", "type": "file_exists", "path": "NOPE.md"},
        ],
    )
    story = build_story(manifest_path)
    assert "What didn't hold up" in story
    assert "Missing file" in story
    assert "not clean" in story


def test_round_drama_is_extracted_over_flat_answer(tmp_path):
    answer = (
        "# issue#9 — real fix\n\n"
        "Answer: Implemented the fix end to end.\n\n"
        "Evidence: Independent verifier: Round 1 caught a real crash on empty input. "
        "Round 2: verified fixed and 12 tests pass.\n"
    )
    manifest_path = _write_run(
        tmp_path,
        answer_text=answer,
        checks=[{"id": "a", "name": "A", "type": "file_exists", "path": "ANSWER.md"}],
    )
    story = build_story(manifest_path)
    assert "didn't take this on faith" in story
    assert "caught a real crash on empty input" in story
    assert "verified fixed and 12 tests pass" in story
    assert "*issue#9 — real fix*" in story  # eyebrow from the H1 title


def test_paths_and_branch_asides_stripped_from_fallback_hook(tmp_path):
    answer = (
        "Answer: Implemented the fix end to end in the working clone at "
        "`/Users/someone/very/long/absolute/path/repo` (branch `fix/thing`), "
        "returning exit 2 with a clear message.\n"
    )
    manifest_path = _write_run(
        tmp_path,
        answer_text=answer,
        checks=[{"id": "a", "name": "A", "type": "file_exists", "path": "ANSWER.md"}],
    )
    story = build_story(manifest_path)
    headline = story.splitlines()[0]
    assert "/Users/" not in headline
    assert "branch" not in headline
    assert "returning exit 2 with a clear message" in headline
