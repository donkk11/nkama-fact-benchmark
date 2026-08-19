"""Real coverage for the content-addressed evidence cache.

Every test here proves a specific trust guarantee, not just "it runs":
cache hits are marked, misses on content change are real misses, blocked
results are never cached, command checks with no declared inputs are never
cached, a cached command result cannot leak past the --allow-commands
policy gate, and the cache store lives outside the evidence root so the
thing being verified cannot forge its own cache entries.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from nkama_fact_benchmark.evidence_layer import verify_manifest


@pytest.fixture(autouse=True)
def _isolated_cache_home(tmp_path_factory, monkeypatch):
    """Every test gets its own cache location — never touch the real ~/.cache,
    and never nest it inside a test's own tmp_path (several tests use tmp_path
    itself as the evidence root, and the whole point is that the cache must
    live somewhere the evidence root can't reach)."""
    monkeypatch.setenv("NKAMA_CACHE_HOME", str(tmp_path_factory.mktemp("cache_home")))


def _write_manifest(root: Path, checks: list[dict]) -> Path:
    manifest = {
        "schema_version": 1,
        "root": str(root),
        "allowed_command_prefixes": ["python3 *"],
        "checks": checks,
    }
    manifest_path = root / "evidence_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path


def test_file_check_cache_hit_is_marked_from_cache(tmp_path):
    target = tmp_path / "answer.md"
    target.write_text("Answer: real content.", encoding="utf-8")
    manifest_path = _write_manifest(
        tmp_path, [{"type": "file_exists", "id": "a", "path": "answer.md"}]
    )

    first = verify_manifest(manifest_path, reuse_cache=True)
    assert first["checks"][0]["status"] == "pass"
    assert first["checks"][0]["from_cache"] is False
    assert first["checks"][0]["verified_at"]

    second = verify_manifest(manifest_path, reuse_cache=True)
    assert second["checks"][0]["status"] == "pass"
    assert second["checks"][0]["from_cache"] is True
    assert second["checks"][0]["verified_at"] == first["checks"][0]["verified_at"]


def test_file_content_change_invalidates_the_cache(tmp_path):
    target = tmp_path / "answer.md"
    target.write_text("Answer: version one.", encoding="utf-8")
    manifest_path = _write_manifest(
        tmp_path,
        [{"type": "file_contains", "id": "a", "path": "answer.md", "text": "version one"}],
    )

    first = verify_manifest(manifest_path, reuse_cache=True)
    assert first["checks"][0]["status"] == "pass"

    target.write_text("Answer: version two.", encoding="utf-8")
    second = verify_manifest(manifest_path, reuse_cache=True)
    assert second["checks"][0]["from_cache"] is False  # real re-check, real new answer
    assert second["checks"][0]["status"] == "fail"


def test_reuse_cache_defaults_off(tmp_path):
    target = tmp_path / "answer.md"
    target.write_text("Answer: real content.", encoding="utf-8")
    manifest_path = _write_manifest(
        tmp_path, [{"type": "file_exists", "id": "a", "path": "answer.md"}]
    )

    verify_manifest(manifest_path, reuse_cache=True)  # populate the cache
    without_flag = verify_manifest(manifest_path)  # reuse_cache defaults False
    assert without_flag["checks"][0]["from_cache"] is False


def test_blocked_result_is_never_cached(tmp_path):
    manifest_path = _write_manifest(
        tmp_path, [{"type": "file_exists", "id": "a", "path": "../outside.md"}]
    )

    first = verify_manifest(manifest_path, reuse_cache=True)
    assert first["checks"][0]["status"] == "blocked"

    second = verify_manifest(manifest_path, reuse_cache=True)
    assert second["checks"][0]["from_cache"] is False  # never came from cache


def test_command_check_without_input_paths_is_never_cached(tmp_path):
    manifest_path = _write_manifest(
        tmp_path,
        [{
            "type": "command_exit_zero",
            "id": "a",
            "command": ["python3", "-c", "print(1)"],
        }],
    )

    first = verify_manifest(manifest_path, allow_commands=True, reuse_cache=True)
    assert first["checks"][0]["status"] == "pass"
    assert first["checks"][0]["from_cache"] is False

    second = verify_manifest(manifest_path, allow_commands=True, reuse_cache=True)
    assert second["checks"][0]["from_cache"] is False  # never eligible, never cached


def test_command_check_with_declared_inputs_caches_and_invalidates(tmp_path):
    script = tmp_path / "check.py"
    script.write_text("print('ok')", encoding="utf-8")
    manifest_path = _write_manifest(
        tmp_path,
        [{
            "type": "command_exit_zero",
            "id": "a",
            "command": ["python3", "check.py"],
            "input_paths": ["check.py"],
        }],
    )

    first = verify_manifest(manifest_path, allow_commands=True, reuse_cache=True)
    assert first["checks"][0]["from_cache"] is False

    second = verify_manifest(manifest_path, allow_commands=True, reuse_cache=True)
    assert second["checks"][0]["from_cache"] is True

    script.write_text("print('changed')", encoding="utf-8")
    third = verify_manifest(manifest_path, allow_commands=True, reuse_cache=True)
    assert third["checks"][0]["from_cache"] is False  # real input changed, real re-run


def test_cached_command_result_cannot_leak_past_allow_commands_gate(tmp_path):
    """Round-1 finding (Codex): a cached pass must never bypass command policy."""
    script = tmp_path / "check.py"
    script.write_text("print('ok')", encoding="utf-8")
    manifest_path = _write_manifest(
        tmp_path,
        [{
            "type": "command_exit_zero",
            "id": "a",
            "command": ["python3", "check.py"],
            "input_paths": ["check.py"],
        }],
    )

    verify_manifest(manifest_path, allow_commands=True, reuse_cache=True)  # cache a real pass
    blocked_run = verify_manifest(manifest_path, allow_commands=False, reuse_cache=True)
    assert blocked_run["checks"][0]["from_cache"] is False
    assert blocked_run["checks"][0]["status"] == "blocked"


def test_cache_key_changes_with_timeout_seconds(tmp_path):
    """Round-1 finding (Codex): timeout_seconds must be part of the cache key."""
    script = tmp_path / "check.py"
    script.write_text("print('ok')", encoding="utf-8")
    manifest_path = _write_manifest(
        tmp_path,
        [{
            "type": "command_exit_zero",
            "id": "a",
            "command": ["python3", "check.py"],
            "input_paths": ["check.py"],
            "timeout_seconds": 5,
        }],
    )
    verify_manifest(manifest_path, allow_commands=True, reuse_cache=True)

    manifest_path = _write_manifest(
        tmp_path,
        [{
            "type": "command_exit_zero",
            "id": "a",
            "command": ["python3", "check.py"],
            "input_paths": ["check.py"],
            "timeout_seconds": 60,
        }],
    )
    changed_timeout = verify_manifest(manifest_path, allow_commands=True, reuse_cache=True)
    assert changed_timeout["checks"][0]["from_cache"] is False


def test_cache_store_lives_outside_evidence_root(tmp_path):
    """Round-1 finding (Codex): the evidence root must not contain the cache,
    since the root is often the thing being verified and could forge entries."""
    target = tmp_path / "answer.md"
    target.write_text("Answer: real content.", encoding="utf-8")
    manifest_path = _write_manifest(
        tmp_path, [{"type": "file_exists", "id": "a", "path": "answer.md"}]
    )
    verify_manifest(manifest_path, reuse_cache=True)

    root_contents_before = set(p.name for p in tmp_path.iterdir())
    assert ".nkama_cache" not in root_contents_before
    assert not any("cache" in name.lower() for name in root_contents_before)


def test_cache_hit_uses_current_checks_id_and_name_not_the_cached_ones(tmp_path):
    """Round-2 finding (Codex): two checks sharing a cache key (same type/path/
    text/encoding, different id/name) must not misattribute evidence — the
    report row must always carry the CURRENT check's identity."""
    target = tmp_path / "answer.md"
    target.write_text("Answer: real content.", encoding="utf-8")
    manifest_path = _write_manifest(
        tmp_path,
        [{"type": "file_exists", "id": "check-one", "name": "First reason", "path": "answer.md"}],
    )
    verify_manifest(manifest_path, reuse_cache=True)

    manifest_path = _write_manifest(
        tmp_path,
        [{"type": "file_exists", "id": "check-two", "name": "Second reason", "path": "answer.md"}],
    )
    second = verify_manifest(manifest_path, reuse_cache=True)
    assert second["checks"][0]["from_cache"] is True  # same underlying fact, real reuse
    assert second["checks"][0]["id"] == "check-two"  # but the CURRENT check's identity
    assert second["checks"][0]["name"] == "Second reason"


def test_cache_home_override_pointing_inside_root_is_rejected(tmp_path, monkeypatch):
    """Round-2 finding (Codex): NKAMA_CACHE_HOME must not be honored if it
    resolves inside the evidence root — that would restore the exact forgery
    boundary the external-cache design exists to remove."""
    fake_home = tmp_path.parent / "fake_home_for_default_fallback"
    fake_home.mkdir(exist_ok=True)
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    monkeypatch.setenv("NKAMA_CACHE_HOME", str(tmp_path / "inside_root_cache"))

    from nkama_fact_benchmark.evidence_cache import EvidenceCache

    cache = EvidenceCache(tmp_path)
    assert not str(cache.path).startswith(str(tmp_path.resolve()))
    assert str(cache.path).startswith(str(fake_home.resolve()))


def test_cache_hit_default_identity_matches_a_fresh_checks_default(tmp_path):
    """Round-3 finding (Codex): when the CURRENT check omits id/name, a cache
    hit must compute the same default a fresh run would — not fall back to
    the cache key or to whatever the first check's name happened to be."""
    target = tmp_path / "answer.md"
    target.write_text("Answer: real content.", encoding="utf-8")

    manifest_path = _write_manifest(
        tmp_path,
        [{"type": "file_exists", "id": "explicit-id", "name": "Explicit name", "path": "answer.md"}],
    )
    verify_manifest(manifest_path, reuse_cache=True)  # populate the cache

    manifest_path = _write_manifest(
        tmp_path, [{"type": "file_exists", "path": "answer.md"}]  # no id/name at all
    )
    fresh_no_cache = verify_manifest(manifest_path)  # reuse_cache off: real fresh defaults
    cached_no_cache = verify_manifest(manifest_path, reuse_cache=True)  # hits the cache

    assert cached_no_cache["checks"][0]["from_cache"] is True
    assert cached_no_cache["checks"][0]["id"] == fresh_no_cache["checks"][0]["id"] == "answer.md"
    assert (
        cached_no_cache["checks"][0]["name"]
        == fresh_no_cache["checks"][0]["name"]
        == "File exists: answer.md"
    )


def test_cache_disabled_when_even_default_home_resolves_inside_root(tmp_path, monkeypatch):
    """Round-3 finding (Codex): if the DEFAULT cache home also resolves inside
    the evidence root (e.g. root is an ancestor of the user's home dir), the
    cache must disable itself for that run rather than silently write inside
    the root anyway."""
    monkeypatch.delenv("NKAMA_CACHE_HOME", raising=False)
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    from nkama_fact_benchmark.evidence_cache import EvidenceCache

    # root is an ancestor of fake_home, so the default cache home is inside root.
    cache = EvidenceCache(tmp_path)
    assert cache.path is None
    assert cache.get("anything") is None
    cache.set("anything", {"status": "pass"})  # must not raise, must not write
    assert not (tmp_path / "home" / ".cache").exists()


def test_malformed_cache_file_degrades_to_miss_not_crash(tmp_path, monkeypatch):
    """Round-4 finding (Codex): a valid-JSON-but-wrong-shape cache file (e.g.
    a list instead of a dict) must be treated as an empty cache, not crash."""
    cache_home = tmp_path.parent / "malformed_cache_home"
    cache_home.mkdir(exist_ok=True)
    monkeypatch.setenv("NKAMA_CACHE_HOME", str(cache_home))

    from nkama_fact_benchmark.evidence_cache import EvidenceCache

    # Pre-seed a malformed cache file at the exact path EvidenceCache will use.
    probe = EvidenceCache(tmp_path)
    probe.path.parent.mkdir(parents=True, exist_ok=True)
    probe.path.write_text("[]", encoding="utf-8")

    target = tmp_path / "answer.md"
    target.write_text("Answer: real content.", encoding="utf-8")
    manifest_path = _write_manifest(
        tmp_path, [{"type": "file_exists", "id": "a", "path": "answer.md"}]
    )
    result = verify_manifest(manifest_path, reuse_cache=True)  # must not raise
    assert result["checks"][0]["status"] == "pass"
    assert result["checks"][0]["from_cache"] is False


def test_unwritable_cache_home_degrades_to_no_persistence_not_crash(tmp_path, monkeypatch):
    """Round-4 finding (Codex): if the cache home can't actually be written to
    (e.g. a regular file sits where a directory is needed), verification must
    still complete — only future-run caching is lost, silently."""
    blocking_file = tmp_path.parent / "not_a_directory_cache_home"
    blocking_file.write_text("not a directory", encoding="utf-8")
    monkeypatch.setenv("NKAMA_CACHE_HOME", str(blocking_file))

    target = tmp_path / "answer.md"
    target.write_text("Answer: real content.", encoding="utf-8")
    manifest_path = _write_manifest(
        tmp_path, [{"type": "file_exists", "id": "a", "path": "answer.md"}]
    )
    result = verify_manifest(manifest_path, reuse_cache=True)  # must not raise
    assert result["checks"][0]["status"] == "pass"
    assert result["checks"][0]["from_cache"] is False


def test_unreadable_cache_directory_degrades_to_miss_not_crash(tmp_path, monkeypatch):
    """Round-5 finding (Codex): a cache directory that raises on exists()/
    read (e.g. permission denied) must degrade to an empty cache, not crash
    EvidenceCache construction."""
    cache_home = tmp_path.parent / "unreadable_cache_home"
    cache_home.mkdir(exist_ok=True)
    monkeypatch.setenv("NKAMA_CACHE_HOME", str(cache_home))
    cache_home.chmod(0o000)
    try:
        target = tmp_path / "answer.md"
        target.write_text("Answer: real content.", encoding="utf-8")
        manifest_path = _write_manifest(
            tmp_path, [{"type": "file_exists", "id": "a", "path": "answer.md"}]
        )
        result = verify_manifest(manifest_path, reuse_cache=True)  # must not raise
        assert result["checks"][0]["status"] == "pass"
    finally:
        cache_home.chmod(0o755)  # restore so pytest can clean up tmp_path


def test_forged_cache_entry_in_evidence_root_has_no_effect(tmp_path):
    """A hand-planted fake cache file inside the evidence root (what an
    untrustworthy builder could try) must be inert — the cache never reads
    from inside the root."""
    target = tmp_path / "answer.md"
    target.write_text("Answer: real content.", encoding="utf-8")
    manifest_path = _write_manifest(
        tmp_path, [{"type": "file_exists", "id": "a", "path": "answer.md"}]
    )

    forged_dir = tmp_path / ".nkama_cache"
    forged_dir.mkdir()
    (forged_dir / "evidence_cache.json").write_text(
        json.dumps({"forged-key": {"cached_at_epoch": 9999999999, "result": {"status": "pass"}}}),
        encoding="utf-8",
    )

    result = verify_manifest(manifest_path, reuse_cache=True)
    assert result["checks"][0]["from_cache"] is False
    assert result["checks"][0]["status"] == "pass"  # real result, not the forged one
