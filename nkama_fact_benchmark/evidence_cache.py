"""Content-addressed reuse for evidence checks.

The core Nkama rule is unchanged by this module: a claim is not proof, a
checkable artifact is. This cache never lets a claim substitute for a check.
It only lets a check that was *already run for real* be reused, and only
when the cache key proves nothing relevant has changed since then.

A check is eligible for caching only if every input that could change its
outcome is explicitly declared and hashable:

- file_exists / file_contains: the single declared `path` is the input.
- command / command_exit_zero: only cacheable if the manifest author
  declares `input_paths` — the files the command actually depends on — AND
  the caller has `allow_commands=True` for this run (enforced by the caller
  in evidence_layer.py, not here). A command check with no declared inputs
  is never cached, on any run, full stop. Guessing at a command's real
  dependencies would silently defeat the entire point of Nkama, so this
  module refuses to guess. Note this is still an honesty-system limit: an
  incomplete `input_paths` declaration is not detectable from here. Treat
  command-check caching as trusting the manifest author, same as every
  other part of a manifest.
- media_* and no_forbidden_claims checks: not cacheable in this version.

A cache hit is never silent. Every reused result carries `from_cache: true`
and the original `verified_at` timestamp of the real run it came from, so a
report reader always knows whether a result was just re-observed or is a
fresh, live check.

Blocked results are never cached — a cached "I could not verify this" would
let a fixable blocker rot in the cache after it was fixed.

Trust boundary: the cache store deliberately does NOT live inside the
evidence root. The evidence root is frequently the *thing being verified* —
an AI's own ai_output/ folder — and that AI has full write access to its own
output. A cache file sitting inside that folder could simply be hand-written
with a forged "pass" entry, which would make the cache indistinguishable
from an unverified claim: exactly the failure mode Nkama exists to catch.
Instead the store lives under the verifier's own `~/.cache`, keyed by a hash
of the resolved root path, outside whatever sandbox a builder AI is given.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

CACHE_HOME_ENV = "NKAMA_CACHE_HOME"
DEFAULT_TTL_SECONDS = 86400  # 24h: cache keys already invalidate on content
# change; the TTL is a second, independent guard against silent tool/dependency
# drift that a file-content hash alone would never catch.

CACHEABLE_FILE_CHECKS = {"file_exists", "file_contains"}
CACHEABLE_COMMAND_CHECKS = {"command", "command_exit_zero"}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _resolve_under_root(root: Path, raw_path: str) -> Path | None:
    candidate = Path(raw_path).expanduser()
    candidate = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


def compute_cache_key(
    check: dict[str, Any],
    root: Path,
    *,
    command_caching_allowed: bool = False,
    allowed_prefixes: list[list[str]] | None = None,
) -> str | None:
    """Return a stable cache key for `check`, or None if it isn't cacheable.

    None means "never cache this, on any run" — not "cache miss". Callers
    must treat None as ineligible, not as a reason to fall back to guessing.

    `command_caching_allowed` must mirror the caller's real `allow_commands`
    policy for this run — a command check is never cacheable when the run
    itself is not permitted to execute commands, otherwise a cached pass
    from an earlier, permitted run could leak into a run where command
    execution is supposed to be blocked entirely.
    """
    kind = str(check.get("type", check.get("kind", "")))

    if kind in CACHEABLE_FILE_CHECKS:
        candidate = _resolve_under_root(root, str(check.get("path", "")))
        if candidate is None or not candidate.is_file():
            return None
        parts = [
            "kind=" + kind,
            "path=" + str(check.get("path", "")),
            "text=" + str(check.get("text", "")),
            "encoding=" + str(check.get("encoding", "utf-8")),
            "file_sha256=" + _sha256_file(candidate),
        ]
        return _sha256_text("|".join(parts))

    if kind in CACHEABLE_COMMAND_CHECKS:
        if not command_caching_allowed:
            return None  # This run does not permit command execution at all.
        input_paths = check.get("input_paths")
        if not isinstance(input_paths, list) or not input_paths:
            return None  # No declared inputs: never cache. Do not guess.
        file_hashes: list[str] = []
        for raw_path in sorted(str(p) for p in input_paths):
            candidate = _resolve_under_root(root, raw_path)
            if candidate is None or not candidate.is_file():
                return None  # A declared input is missing/escapes root: not cacheable.
            file_hashes.append(f"{raw_path}={_sha256_file(candidate)}")
        policy_fingerprint = _sha256_text(
            json.dumps(sorted(allowed_prefixes or []), sort_keys=True)
        )
        parts = [
            "kind=" + kind,
            "command=" + json.dumps(check.get("command", []), sort_keys=True),
            "expected_exit_code=" + str(check.get("expected_exit_code", 0)),
            "timeout_seconds=" + str(check.get("timeout_seconds", 30)),
            "allowed_prefixes_fingerprint=" + policy_fingerprint,
            "inputs=" + "|".join(file_hashes),
        ]
        return _sha256_text("|".join(parts))

    return None


class EvidenceCache:
    """A local, transparent, content-addressed store of past check results.

    Stored at `~/.cache/nkama_fact_benchmark/evidence_cache/<root-hash>.json`
    (override with the NKAMA_CACHE_HOME env var) — deliberately outside the
    evidence root itself. See the module docstring for why: an evidence root
    is often the thing being verified, and it must not be a place the subject
    of the verification can plant a forged "pass".
    """

    def __init__(self, root: Path, *, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        self.root = root.resolve()
        self.ttl_seconds = ttl_seconds
        import os

        def _inside_root(candidate: Path) -> bool:
            try:
                candidate.relative_to(self.root)
                return True
            except ValueError:
                return False

        default_cache_home = (Path.home() / ".cache" / "nkama_fact_benchmark" / "evidence_cache").expanduser().resolve()
        configured = Path(os.environ.get(CACHE_HOME_ENV, default_cache_home)).expanduser().resolve()
        if _inside_root(configured):
            # The configured cache home resolves inside the evidence root — exactly
            # the forgery risk this whole design exists to avoid. Refuse the unsafe
            # override rather than honor it; fall back to the real default instead
            # of failing outright, since a missing/bad env var shouldn't block a run.
            configured = default_cache_home
        if _inside_root(configured):
            # Even the default resolves inside the root (e.g. the evidence root is
            # an ancestor of the user's home directory). There is no safe location
            # left to use — disable caching for this run entirely rather than write
            # somewhere a forged entry could reach. This is the cache-layer
            # equivalent of "blocked": refuse silently succeeding unsafely.
            self.path = None
            self._data = {}
            return
        root_hash = _sha256_text(str(self.root))
        self.path = configured / f"{root_hash}.json"
        self._data = {}
        try:
            exists = self.path.exists()
        except OSError:
            exists = False  # e.g. permission denied on a parent directory.
        if exists:
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                # Caching is a pure optimization — any unexpected shape (not
                # produced by this module, or corrupted) must degrade to "act
                # as if the cache were empty", never crash verification itself.
                self._data = loaded if isinstance(loaded, dict) else {}
            except (json.JSONDecodeError, OSError, UnicodeDecodeError):
                self._data = {}

    def get(self, cache_key: str) -> dict[str, Any] | None:
        if self.path is None:
            return None  # Caching disabled for this run (no safe cache location).
        entry = self._data.get(cache_key)
        if not isinstance(entry, dict):
            return None  # Malformed entry: treat as a miss, not a crash.
        cached_at = entry.get("cached_at_epoch", 0)
        if not isinstance(cached_at, (int, float)) or time.time() - cached_at > self.ttl_seconds:
            return None  # Expired (or unreadable timestamp): treat as a miss.
        result = entry.get("result")
        if not isinstance(result, dict):
            return None
        # The result was already stamped with its own verified_at at the moment
        # it was first computed (by the caller, before set() ran) — return it
        # unchanged rather than recomputing a second, slightly different time.
        return dict(result)

    def set(self, cache_key: str, result: dict[str, Any]) -> None:
        if self.path is None:
            return  # Caching disabled for this run (no safe cache location).
        if result.get("status") == "blocked":
            return  # Never cache a "could not verify" — it may become checkable later.
        self._data[cache_key] = {
            "cached_at_epoch": time.time(),
            "result": result,
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self._data, indent=2, sort_keys=True), encoding="utf-8")
        except OSError:
            # Cache home unusable (e.g. a file sits where a directory is
            # needed, permissions, disk full). This must never take down a
            # real verification run over a pure optimization — the result was
            # already returned to the caller from the fresh check; only the
            # persistence for a *future* run is lost here, silently.
            pass
