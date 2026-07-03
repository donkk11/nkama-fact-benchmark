from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class EvidenceResult:
    id: str
    name: str
    category: str
    status: str
    evidence: list[dict[str, Any]] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "status": self.status,
            "evidence": self.evidence,
            "limitations": self.limitations,
        }


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


def _prefixes(raw: Any) -> list[list[str]]:
    if not raw:
        return []
    return [item for item in raw if isinstance(item, list) and all(isinstance(part, str) for part in item)]


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


def _no_forbidden_claims(check: dict[str, Any]) -> EvidenceResult:
    text = str(check.get("text", ""))
    forbidden = [str(item) for item in check.get("forbidden", [])]
    found = [item for item in forbidden if item.lower() in text.lower()]
    return EvidenceResult(
        str(check.get("id", "no_forbidden_claims")),
        str(check.get("name", "No forbidden unverified claims")),
        "claim",
        "pass" if not found else "fail",
        evidence=[{"kind": "forbidden_claim_scan", "forbidden": forbidden, "found": found}],
        limitations=[] if not found else [f"Found forbidden/unverified claim markers: {', '.join(found)}"],
    )


def _command(root: Path, check: dict[str, Any], *, allow_commands: bool, allowed_prefixes: list[list[str]]) -> EvidenceResult:
    command = check.get("command", [])
    if not isinstance(command, list) or not command or not all(isinstance(part, str) for part in command):
        return EvidenceResult(str(check.get("id", "command")), str(check.get("name", "Command check")), "terminal", "blocked", limitations=["Command must be a non-empty list of strings."])
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


def verify_manifest(manifest_path: str | Path, *, allow_commands: bool = False) -> dict[str, Any]:
    manifest_file = Path(manifest_path).expanduser().resolve()
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    root = Path(str(manifest.get("root", manifest_file.parent))).expanduser().resolve()
    allowed_prefixes = _prefixes(manifest.get("allowed_command_prefixes", []))
    rows: list[dict[str, Any]] = []
    for check in manifest.get("checks", []):
        kind = str(check.get("type", check.get("kind", "")))
        if kind == "file_exists":
            result = _file_exists(root, check)
        elif kind == "file_contains":
            result = _file_contains(root, check)
        elif kind == "no_forbidden_claims":
            result = _no_forbidden_claims(check)
        elif kind in {"command", "command_exit_zero"}:
            result = _command(root, check, allow_commands=allow_commands, allowed_prefixes=allowed_prefixes)
        else:
            result = EvidenceResult(str(check.get("id", "unknown")), str(check.get("name", "Unknown check")), "unknown", "blocked", limitations=[f"Unsupported check type: {kind}"])
        rows.append(result.to_dict())
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
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify an AI output evidence manifest.")
    parser.add_argument("manifest", help="Path to evidence_manifest.json")
    parser.add_argument("--allow-commands", action="store_true", help="Allow reviewed command checks from the manifest.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    print(json.dumps(verify_manifest(args.manifest, allow_commands=args.allow_commands), indent=2))


if __name__ == "__main__":
    main()
