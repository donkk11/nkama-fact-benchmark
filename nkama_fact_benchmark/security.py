from __future__ import annotations

import argparse
import json
import re
import tarfile
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPECTED_ENTRY_POINTS = {
    "nkama-evidence-layer",
    "nkama-fact-benchmark",
    "nkama-prompt-filter",
    "nkama-truth-filter",
}

PUBLIC_TOP_LEVEL_FILES = {
    "LICENSE",
    "MANIFEST.in",
    "PKG-INFO",
    "README_PYPI.md",
    "pyproject.toml",
    "setup.cfg",
}

PRIVATE_TEXT_PATTERNS = {
    "home_path": re.compile(r"/Users/[A-Za-z0-9._-]+"),
    "documents_path": re.compile(r"Documents/[A-Za-z0-9._/-]+"),
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "pypi_token": re.compile(r"pypi-[A-Za-z0-9_-]+"),
    "credential_assignment": re.compile(
        "("
        + "|".join(
            [
                "UV" + "_PUBLISH" + "_TOKEN",
                "API" + "_KEY",
                "SECRET",
                "PASSWORD",
            ]
        )
        + r")\s*[:=]\s*['\"]?[^\s'\"]+",
        re.IGNORECASE,
    ),
}


@dataclass
class AuditFinding:
    id: str
    status: str
    evidence: dict[str, Any] = field(default_factory=dict)
    limitation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status,
            "evidence": self.evidence,
            "limitation": self.limitation,
        }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_archive(path: Path) -> tuple[list[str], dict[str, str]]:
    names: list[str] = []
    text_files: dict[str, str] = {}
    if path.suffix == ".whl" or path.suffix == ".zip":
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            for name in names:
                try:
                    text_files[name] = archive.read(name).decode("utf-8", "ignore")
                except KeyError:
                    continue
    elif path.name.endswith(".tar.gz") or path.suffix in {".tgz", ".tar"}:
        with tarfile.open(path) as archive:
            names = archive.getnames()
            for member in archive.getmembers():
                if not member.isfile():
                    continue
                handle = archive.extractfile(member)
                if handle is not None:
                    text_files[member.name] = handle.read().decode("utf-8", "ignore")
    else:
        raise ValueError(f"Unsupported artifact type: {path}")
    return names, text_files


def _entry_points_from_text_files(text_files: dict[str, str]) -> set[str]:
    entry_text = ""
    for name, text in text_files.items():
        if name.endswith("entry_points.txt"):
            entry_text = text
            break
    found: set[str] = set()
    in_console = False
    for raw_line in entry_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            in_console = line == "[console_scripts]"
            continue
        if in_console and "=" in line:
            found.add(line.split("=", 1)[0].strip())
    return found


def _public_release_path_allowed(name: str) -> bool:
    parts = Path(name).parts
    if not parts:
        return False
    if len(parts) == 1 and parts[0].startswith("nkama_fact_benchmark-"):
        return True
    if parts[0].startswith("nkama_fact_benchmark-") and parts[-1] in PUBLIC_TOP_LEVEL_FILES:
        return True
    if parts[0].startswith("nkama_fact_benchmark-") and parts[0].endswith(".dist-info"):
        return True
    if parts[0].startswith("nkama_fact_benchmark-") and len(parts) >= 2:
        return parts[1] in {"nkama_fact_benchmark", "nkama_fact_benchmark.egg-info"}
    if parts[0] == "nkama_fact_benchmark":
        return True
    return False


def audit_artifact(path: str | Path) -> dict[str, Any]:
    artifact = Path(path).expanduser().resolve()
    names, text_files = _read_archive(artifact)
    findings: list[AuditFinding] = []

    forbidden_paths = [name for name in names if not _public_release_path_allowed(name)]
    findings.append(
        AuditFinding(
            id="no_internal_paths",
            status="pass" if not forbidden_paths else "fail",
            evidence={"forbidden_paths": forbidden_paths[:20], "count": len(forbidden_paths)},
            limitation="" if not forbidden_paths else "Artifact contains internal/private path names.",
        )
    )

    text_hits = []
    for name, text in text_files.items():
        for label, pattern in PRIVATE_TEXT_PATTERNS.items():
            matches = sorted(set(pattern.findall(text)))
            if matches:
                text_hits.append({"file": name, "pattern": label, "matches": matches[:5]})
    findings.append(
        AuditFinding(
            id="no_private_text",
            status="pass" if not text_hits else "fail",
            evidence={"hits": text_hits[:20], "count": len(text_hits)},
            limitation="" if not text_hits else "Artifact contains private/internal text markers.",
        )
    )

    entry_points = _entry_points_from_text_files(text_files)
    missing = sorted(EXPECTED_ENTRY_POINTS - entry_points)
    unexpected = sorted(entry_points - EXPECTED_ENTRY_POINTS)
    findings.append(
        AuditFinding(
            id="public_entry_points_exact",
            status="pass" if not missing and not unexpected else "fail",
            evidence={"entry_points": sorted(entry_points), "missing": missing, "unexpected": unexpected},
            limitation="" if not missing and not unexpected else "Entry points are not exactly the public command set.",
        )
    )

    requires = []
    for name, text in text_files.items():
        if name.endswith("METADATA") or name.endswith("PKG-INFO"):
            requires.extend([line for line in text.splitlines() if line.startswith("Requires-Dist:")])
    findings.append(
        AuditFinding(
            id="no_runtime_dependencies",
            status="pass" if not requires else "fail",
            evidence={"requires_dist": requires},
            limitation="" if not requires else "Public package has runtime dependencies.",
        )
    )

    rows = [finding.to_dict() for finding in findings]
    return {
        "artifact": str(artifact),
        "status": "pass" if all(row["status"] == "pass" for row in rows) else "fail",
        "file_count": len(names),
        "findings": rows,
    }


def audit_artifacts(paths: list[str | Path]) -> dict[str, Any]:
    artifacts = [audit_artifact(path) for path in paths]
    return {
        "schema_version": 1,
        "generated_at": utc_now(),
        "principle": "public_safe_release_only",
        "summary": {
            "artifacts": len(artifacts),
            "pass": sum(1 for item in artifacts if item["status"] == "pass"),
            "fail": sum(1 for item in artifacts if item["status"] == "fail"),
        },
        "artifacts": artifacts,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit public release artifacts before publishing.")
    parser.add_argument("artifacts", nargs="+", help="Wheel/source artifacts to audit.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    report = audit_artifacts(args.artifacts)
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["summary"]["fail"] == 0 else 1)


if __name__ == "__main__":
    main()
