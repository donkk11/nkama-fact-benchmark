from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .evidence_cache import EvidenceCache, compute_cache_key


# category -> how the evidence was actually obtained. Derived, not stored per
# check, so this stays honest even as new check types are added — see the
# nkama:bridge design discussion for why a flat "tier" number was rejected in
# favor of orthogonal, plainly-labeled dimensions like this one.
_VERIFICATION_METHOD_BY_CATEGORY = {
    "file": "static",       # a file was read; nothing was executed
    "media": "probe",       # a real tool (ffprobe/ffmpeg) inspected an artifact
    "terminal": "subprocess",  # a real command from the manifest was executed
}


@dataclass
class EvidenceResult:
    id: str
    name: str
    category: str
    status: str
    evidence: list[dict[str, Any]] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    # Set later, only when a bridge run's independent verifier reports a
    # structured per-check finding for this exact check id — "not_requested"
    # is the honest default for every check run without a second model.
    independent_review: str = "not_requested"
    independent_review_note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "status": self.status,
            "verification_method": _VERIFICATION_METHOD_BY_CATEGORY.get(self.category, "unknown"),
            "evidence_scope": "local_harness",
            "independent_review": self.independent_review,
            "evidence": self.evidence,
            "limitations": self.limitations,
        }
        if self.independent_review_note:
            result["independent_review_note"] = self.independent_review_note
        return result


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _short_text(value: str, limit: int = 900) -> str:
    text = value.strip()
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_path(root: Path, raw_path: str) -> tuple[Path | None, str | None]:
    candidate = Path(raw_path).expanduser()
    candidate = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None, f"Path escapes evidence root: {raw_path}"
    return candidate, None


def _file_evidence(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "kind": "file",
        "path": str(path),
        "size_bytes": stat.st_size,
        "modified_epoch": int(stat.st_mtime),
        "sha256": _sha256(path),
    }


def _allowed(command: list[str], prefixes: list[list[str]]) -> bool:
    return any(command[: len(prefix)] == prefix for prefix in prefixes if prefix)


def _normalize_shell_words(raw: Any, *, label: str) -> tuple[list[str] | None, str | None]:
    if isinstance(raw, list) and raw and all(isinstance(part, str) for part in raw):
        return raw, None
    if isinstance(raw, str) and raw.strip():
        try:
            parts = shlex.split(raw)
        except ValueError as exc:
            return None, f"{label} could not be parsed safely: {exc}"
        if parts:
            return parts, None
    return None, f"{label} must be a non-empty list of strings or a safely split string."


def _prefixes(raw: Any) -> list[list[str]]:
    if not raw:
        return []
    prefixes: list[list[str]] = []
    for item in raw:
        prefix, _error = _normalize_shell_words(item, label="Allowed command prefix")
        if not prefix:
            continue
        if prefix[-1] == "*":
            prefix = prefix[:-1]
        if prefix:
            prefixes.append(prefix)
    return prefixes


def _file_exists(root: Path, check: dict[str, Any]) -> EvidenceResult:
    raw = str(check.get("path", ""))
    path, error = _safe_path(root, raw)
    if error or path is None:
        return EvidenceResult(str(check.get("id", "file_exists")), str(check.get("name", raw)), "file", "blocked", limitations=[error or "Invalid path."])
    if not path.exists():
        return EvidenceResult(str(check.get("id", raw)), str(check.get("name", f"File exists: {raw}")), "file", "fail", evidence=[{"kind": "file_probe", "path": str(path), "exists": False}], limitations=[f"Missing file: {path}"])
    return EvidenceResult(str(check.get("id", raw)), str(check.get("name", f"File exists: {raw}")), "file", "pass", evidence=[_file_evidence(path)])


def _file_contains(root: Path, check: dict[str, Any]) -> EvidenceResult:
    raw = str(check.get("path", ""))
    needle = str(check.get("text", ""))
    # Real bug, found by an adversarial audit: an omitted/empty "text" field
    # made "" in file_text always True, so a malformed check silently passed
    # instead of being blocked. A file_contains check with nothing to look
    # for cannot have checked anything.
    if not needle:
        return EvidenceResult(str(check.get("id", "file_contains")), str(check.get("name", raw)), "file", "blocked", limitations=["file_contains check has no (or empty) \"text\" field to search for."])
    path, error = _safe_path(root, raw)
    if error or path is None:
        return EvidenceResult(str(check.get("id", "file_contains")), str(check.get("name", raw)), "file", "blocked", limitations=[error or "Invalid path."])
    try:
        text = path.read_text(encoding=str(check.get("encoding", "utf-8")))
    except FileNotFoundError:
        return EvidenceResult(str(check.get("id", raw)), str(check.get("name", f"File contains: {raw}")), "file", "fail", evidence=[{"kind": "file_probe", "path": str(path), "exists": False}], limitations=[f"Missing file: {path}"])
    matched = needle in text
    return EvidenceResult(
        str(check.get("id", raw)),
        str(check.get("name", f"File contains: {raw}")),
        "file",
        "pass" if matched else "fail",
        evidence=[_file_evidence(path), {"kind": "content_match", "matched": matched, "text": _short_text(needle, 160)}],
        limitations=[] if matched else [f"Expected text was not found in {path}"],
    )


def _file_not_contains(root: Path, check: dict[str, Any]) -> EvidenceResult:
    """Inverse of file_contains: passes only when the given text is ABSENT
    from the file. Exists so a manifest can assert a placeholder/marker
    string has been replaced with real content, not just that some string
    is present (which a stale placeholder can satisfy just as easily as
    real work — see the starter-template self-pass this closes)."""
    raw = str(check.get("path", ""))
    needle = str(check.get("text", ""))
    if not needle:
        return EvidenceResult(str(check.get("id", "file_not_contains")), str(check.get("name", raw)), "file", "blocked", limitations=["file_not_contains check has no (or empty) \"text\" field to search for."])
    path, error = _safe_path(root, raw)
    if error or path is None:
        return EvidenceResult(str(check.get("id", "file_not_contains")), str(check.get("name", raw)), "file", "blocked", limitations=[error or "Invalid path."])
    try:
        text = path.read_text(encoding=str(check.get("encoding", "utf-8")))
    except FileNotFoundError:
        return EvidenceResult(str(check.get("id", raw)), str(check.get("name", f"File does not contain: {raw}")), "file", "fail", evidence=[{"kind": "file_probe", "path": str(path), "exists": False}], limitations=[f"Missing file: {path}"])
    matched = needle in text
    return EvidenceResult(
        str(check.get("id", raw)),
        str(check.get("name", f"File does not contain: {raw}")),
        "file",
        "fail" if matched else "pass",
        evidence=[_file_evidence(path), {"kind": "content_absence_check", "found": matched, "text": _short_text(needle, 160)}],
        limitations=[] if not matched else [f"Forbidden/placeholder text was still found in {path}"],
    )


def _no_forbidden_claims(check: dict[str, Any]) -> EvidenceResult:
    text = str(check.get("text", ""))
    forbidden = [str(item) for item in check.get("forbidden", [])]
    # Real bug, found by an adversarial audit: an empty "forbidden" list made
    # found=[] trivially, so a malformed check silently passed instead of
    # being blocked.
    if not forbidden:
        return EvidenceResult(str(check.get("id", "no_forbidden_claims")), str(check.get("name", "No forbidden unverified claims")), "claim", "blocked", limitations=["no_forbidden_claims check has no (or empty) \"forbidden\" list to scan for."])
    found = [item for item in forbidden if item.lower() in text.lower()]
    return EvidenceResult(
        str(check.get("id", "no_forbidden_claims")),
        str(check.get("name", "No forbidden unverified claims")),
        "claim",
        "pass" if not found else "fail",
        evidence=[{"kind": "forbidden_claim_scan", "forbidden": forbidden, "found": found}],
        limitations=[] if not found else [f"Found forbidden/unverified claim markers: {', '.join(found)}"],
    )


def _ffprobe_duration(path: Path) -> float | None:
    try:
        completed = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, timeout=30, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    try:
        return float(completed.stdout.strip())
    except ValueError:
        return None


def _media_duration_matches(root: Path, check: dict[str, Any]) -> EvidenceResult:
    """Real ffprobe duration check — a media file actually has the claimed length."""
    raw = str(check.get("path", ""))
    check_id = str(check.get("id", "media_duration_matches"))
    name = str(check.get("name", f"Media duration matches: {raw}"))
    path, error = _safe_path(root, raw)
    if error or path is None:
        return EvidenceResult(check_id, name, "media", "blocked", limitations=[error or "Invalid path."])
    if not path.exists():
        return EvidenceResult(check_id, name, "media", "fail", evidence=[{"kind": "file_probe", "path": str(path), "exists": False}], limitations=[f"Missing file: {path}"])
    duration = _ffprobe_duration(path)
    if duration is None:
        return EvidenceResult(check_id, name, "media", "blocked", limitations=["ffprobe unavailable or could not read duration — install ffmpeg/ffprobe."])
    expected = float(check.get("expected_seconds", 0))
    tolerance = float(check.get("tolerance_seconds", 0.5))
    passed = abs(duration - expected) <= tolerance
    return EvidenceResult(
        check_id, name, "media", "pass" if passed else "fail",
        evidence=[{"kind": "ffprobe_duration", "path": str(path), "measured_seconds": duration, "expected_seconds": expected, "tolerance_seconds": tolerance}],
        limitations=[] if passed else [f"Measured duration {duration:.3f}s outside {expected}s ± {tolerance}s"],
    )


def _media_not_silent(root: Path, check: dict[str, Any]) -> EvidenceResult:
    """Real ffmpeg silencedetect check — an audio/video track isn't mostly/entirely silent."""
    raw = str(check.get("path", ""))
    check_id = str(check.get("id", "media_not_silent"))
    name = str(check.get("name", f"Media not silent: {raw}"))
    path, error = _safe_path(root, raw)
    if error or path is None:
        return EvidenceResult(check_id, name, "media", "blocked", limitations=[error or "Invalid path."])
    if not path.exists():
        return EvidenceResult(check_id, name, "media", "fail", evidence=[{"kind": "file_probe", "path": str(path), "exists": False}], limitations=[f"Missing file: {path}"])
    duration = _ffprobe_duration(path)
    if duration is None or duration <= 0:
        return EvidenceResult(check_id, name, "media", "blocked", limitations=["ffprobe unavailable or zero/invalid duration."])
    noise_db = check.get("noise_db", "-35dB")
    min_gap = float(check.get("min_silence_seconds", 1.0))
    try:
        completed = subprocess.run(
            ["ffmpeg", "-i", str(path), "-af", f"silencedetect=noise={noise_db}:d={min_gap}", "-f", "null", "-"],
            capture_output=True, text=True, timeout=60, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return EvidenceResult(check_id, name, "media", "blocked", limitations=[f"Could not run ffmpeg: {exc}"])
    if completed.returncode != 0:
        return EvidenceResult(check_id, name, "media", "blocked", evidence=[{"kind": "ffmpeg_silencedetect", "path": str(path), "exit_code": completed.returncode, "stderr_excerpt": _short_text(completed.stderr, 300)}], limitations=[f"ffmpeg exited {completed.returncode} — cannot trust silence measurement (this used to silently read as 'not silent')."])
    total_silence = 0.0
    for line in completed.stderr.splitlines():
        if "silence_duration:" in line:
            try:
                total_silence += float(line.rsplit("silence_duration:", 1)[1].strip())
            except ValueError:
                continue
    silence_ratio = total_silence / duration
    max_ratio = float(check.get("max_silence_ratio", 0.5))
    passed = silence_ratio <= max_ratio
    return EvidenceResult(
        check_id, name, "media", "pass" if passed else "fail",
        evidence=[{"kind": "ffmpeg_silencedetect", "path": str(path), "duration_seconds": duration, "total_silence_seconds": round(total_silence, 3), "silence_ratio": round(silence_ratio, 4), "max_silence_ratio": max_ratio}],
        limitations=[] if passed else [f"Silence ratio {silence_ratio:.1%} exceeds max {max_ratio:.1%} — media may be broken/empty."],
    )


def _video_frame_extractable(root: Path, check: dict[str, Any]) -> EvidenceResult:
    """Real ffmpeg frame extraction — a video actually has real (non-empty) visual content at a timestamp."""
    raw = str(check.get("path", ""))
    check_id = str(check.get("id", "video_frame_extractable"))
    name = str(check.get("name", f"Frame extractable: {raw}"))
    path, error = _safe_path(root, raw)
    if error or path is None:
        return EvidenceResult(check_id, name, "media", "blocked", limitations=[error or "Invalid path."])
    if not path.exists():
        return EvidenceResult(check_id, name, "media", "fail", evidence=[{"kind": "file_probe", "path": str(path), "exists": False}], limitations=[f"Missing file: {path}"])
    timestamp = float(check.get("timestamp_seconds", 0))
    min_bytes = int(check.get("min_bytes", 1000))
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = Path(tmpdir) / "frame.png"
        try:
            completed = subprocess.run(
                ["ffmpeg", "-y", "-ss", str(timestamp), "-i", str(path), "-frames:v", "1", str(out_path)],
                capture_output=True, text=True, timeout=30, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return EvidenceResult(check_id, name, "media", "blocked", limitations=[f"Could not run ffmpeg: {exc}"])
        if completed.returncode != 0 or not out_path.exists():
            return EvidenceResult(check_id, name, "media", "fail", evidence=[{"kind": "ffmpeg_extract", "path": str(path), "timestamp_seconds": timestamp, "extracted": False}], limitations=[f"Frame extraction failed at {timestamp}s: {_short_text(completed.stderr, 300)}"])
        size = out_path.stat().st_size
    passed = size >= min_bytes
    return EvidenceResult(
        check_id, name, "media", "pass" if passed else "fail",
        evidence=[{"kind": "ffmpeg_extract", "path": str(path), "timestamp_seconds": timestamp, "extracted": True, "frame_bytes": size, "min_bytes": min_bytes}],
        limitations=[] if passed else [f"Extracted frame only {size} bytes (< {min_bytes}) — likely blank/black/corrupt."],
    )


def _command(root: Path, check: dict[str, Any], *, allow_commands: bool, allowed_prefixes: list[list[str]]) -> EvidenceResult:
    command, command_error = _normalize_shell_words(check.get("command", []), label="Command")
    if command_error or command is None:
        return EvidenceResult(str(check.get("id", "command")), str(check.get("name", "Command check")), "terminal", "blocked", limitations=[command_error or "Invalid command."])
    if not allow_commands:
        return EvidenceResult(str(check.get("id", "command")), str(check.get("name", "Command check")), "terminal", "blocked", evidence=[{"kind": "command_policy", "command": command, "allowed": False}], limitations=["Command execution is disabled. Rerun with --allow-commands after reviewing the manifest."])
    if not _allowed(command, allowed_prefixes):
        return EvidenceResult(str(check.get("id", "command")), str(check.get("name", "Command check")), "terminal", "blocked", evidence=[{"kind": "command_policy", "command": command, "allowed_prefixes": allowed_prefixes}], limitations=["Command does not match any allowed prefix."])
    try:
        completed = subprocess.run(command, cwd=str(root), text=True, capture_output=True, timeout=int(check.get("timeout_seconds", 30)), check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return EvidenceResult(str(check.get("id", "command")), str(check.get("name", "Command check")), "terminal", "blocked", limitations=[f"Could not run command: {exc}"])
    expected = int(check.get("expected_exit_code", 0))
    passed = completed.returncode == expected
    return EvidenceResult(
        str(check.get("id", "command")),
        str(check.get("name", "Command check")),
        "terminal",
        "pass" if passed else "fail",
        evidence=[{"kind": "subprocess", "command": command, "cwd": str(root), "exit_code": completed.returncode, "stdout_excerpt": _short_text(completed.stdout), "stderr_excerpt": _short_text(completed.stderr)}],
        limitations=[] if passed else [f"Expected exit code {expected}, got {completed.returncode}."],
    )


def _default_identity(kind: str, check: dict[str, Any]) -> tuple[str, str]:
    """The same (id, name) defaults the real check function would use when the
    manifest doesn't specify one, for the check kinds that are cacheable. Kept
    as its own function, called from both the fresh path (via the check
    functions themselves) and the cache-hit path, so the two can never quietly
    diverge — see the CACHEABLE_* sets in evidence_cache.py for which kinds
    this needs to cover."""
    if kind == "file_exists":
        raw = str(check.get("path", ""))
        return raw, f"File exists: {raw}"
    if kind == "file_contains":
        raw = str(check.get("path", ""))
        return raw, f"File contains: {raw}"
    if kind == "file_not_contains":
        raw = str(check.get("path", ""))
        return raw, f"File does not contain: {raw}"
    if kind in {"command", "command_exit_zero"}:
        return "command", "Command check"
    return "unknown", "Unknown check"


def verify_manifest(manifest_path: str | Path, *, allow_commands: bool = False, reuse_cache: bool = False) -> dict[str, Any]:
    manifest_file = Path(manifest_path).expanduser().resolve()
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    root = Path(str(manifest.get("root", manifest_file.parent))).expanduser().resolve()
    allowed_prefixes = _prefixes(manifest.get("allowed_command_prefixes", []))
    cache = EvidenceCache(root) if reuse_cache else None
    rows: list[dict[str, Any]] = []
    for check in manifest.get("checks", []):
        kind = str(check.get("type", check.get("kind", "")))
        cache_key = (
            compute_cache_key(check, root, command_caching_allowed=allow_commands, allowed_prefixes=allowed_prefixes)
            if cache is not None
            else None
        )
        cached_result = cache.get(cache_key) if cache is not None and cache_key is not None else None
        if cached_result is not None:
            row = dict(cached_result)
            # The cache key does not include id/name (two checks that verify the
            # same underlying fact should be able to share the cached work even
            # if they're labeled differently). But that means a cached row's
            # stored id/name belongs to whichever check first populated this
            # key — always overwrite them with the CURRENT check's identity,
            # using the exact same default each check function would itself
            # use for a fresh run, so a cache hit is never distinguishable by
            # its id/name defaults from a fresh check.
            default_id, default_name = _default_identity(kind, check)
            row["id"] = str(check.get("id", default_id))
            row["name"] = str(check.get("name", default_name))
            row["from_cache"] = True
            rows.append(row)
            continue
        if kind == "file_exists":
            result = _file_exists(root, check)
        elif kind == "file_contains":
            result = _file_contains(root, check)
        elif kind == "file_not_contains":
            result = _file_not_contains(root, check)
        elif kind == "no_forbidden_claims":
            result = _no_forbidden_claims(check)
        elif kind in {"command", "command_exit_zero"}:
            result = _command(root, check, allow_commands=allow_commands, allowed_prefixes=allowed_prefixes)
        elif kind == "media_duration_matches":
            result = _media_duration_matches(root, check)
        elif kind == "media_not_silent":
            result = _media_not_silent(root, check)
        elif kind == "video_frame_extractable":
            result = _video_frame_extractable(root, check)
        else:
            result = EvidenceResult(str(check.get("id", "unknown")), str(check.get("name", "Unknown check")), "unknown", "blocked", limitations=[f"Unsupported check type: {kind}"])
        result_dict = result.to_dict()
        result_dict["from_cache"] = False
        result_dict["verified_at"] = utc_now()
        if cache is not None and cache_key is not None:
            cache.set(cache_key, result_dict)
        rows.append(result_dict)
    report = {
        "schema_version": 1,
        "run_id": f"evidence_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}",
        "generated_at": utc_now(),
        "manifest": str(manifest_file),
        "principle": "fact_verified_only",
        "summary": {
            "checks_run": len(rows),
            "pass": sum(1 for item in rows if item["status"] == "pass"),
            "fail": sum(1 for item in rows if item["status"] == "fail"),
            "blocked": sum(1 for item in rows if item["status"] == "blocked"),
        },
        "checks": rows,
    }
    report["summary"]["passed_all_unblocked"] = report["summary"]["fail"] == 0
    # Real bug, found by an adversarial audit and confirmed live before this
    # fix: a manifest with zero checks previously returned clean_pass=true —
    # certifying the absence of evidence as a clean pass. checks_run > 0 is
    # now required; nothing checked can never mean nothing wrong.
    report["summary"]["clean_pass"] = (
        report["summary"]["checks_run"] > 0
        and report["summary"]["fail"] == 0
        and report["summary"]["blocked"] == 0
    )
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify an AI output evidence manifest.")
    parser.add_argument("manifest", help="Path to evidence_manifest.json")
    parser.add_argument("--allow-commands", action="store_true", help="Allow reviewed command checks from the manifest.")
    parser.add_argument(
        "--reuse-cache",
        action="store_true",
        help=(
            "Reuse a prior real check result when nothing it depends on has changed "
            "(content-hash keyed, off by default). Reused rows are marked "
            "from_cache: true. Blocked results and command checks with no declared "
            "input_paths are never cached."
        ),
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    report = verify_manifest(args.manifest, allow_commands=args.allow_commands, reuse_cache=args.reuse_cache)
    print(json.dumps(report, indent=2))
    # Real bug, found by an adversarial audit: this exited 0 unconditionally,
    # so a CI pipeline piping this straight into a gate never actually gated
    # on anything — a manifest full of real failures still exited clean.
    raise SystemExit(0 if report["summary"].get("clean_pass") else 1)


if __name__ == "__main__":
    main()
