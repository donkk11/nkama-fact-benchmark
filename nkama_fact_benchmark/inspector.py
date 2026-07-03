from __future__ import annotations

import argparse
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .evidence_layer import verify_manifest


EXPECTED_ROOT_FILES = (
    "original_prompt.md",
    "evidence_prompt.md",
    "run_contract.json",
    "README.md",
)
EXPECTED_AGENT_FILES = ("AGENT_PROTOCOL.md",)
EXPECTED_AI_OUTPUT_FILES = ("ANSWER.md", "evidence_manifest.json")

CODE_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".html",
    ".css",
    ".java",
    ".kt",
    ".swift",
    ".rs",
    ".go",
    ".c",
    ".cpp",
    ".cs",
    ".sh",
}
DOCUMENT_EXTENSIONS = {".md", ".txt", ".pdf", ".docx", ".pptx", ".xlsx", ".csv", ".json"}
RICH_DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".pptx", ".xlsx"}
DESIGN_HINTS = (
    "architecture",
    "data schema",
    "schema",
    "daily prompt",
    "monthly prompt",
    "risk",
    "test case",
    "recommended",
    "design",
)
CLAIM_PATTERNS = (
    r"\btests? passed\b",
    r"\ball checks passed\b",
    r"\bverified\b",
    r"\bfully working\b",
    r"\bproduction ready\b",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_text(path: Path, limit: int = 200_000) -> str:
    try:
        return path.read_text(encoding="utf-8")[:limit]
    except (OSError, UnicodeDecodeError):
        return ""


def _json_or_none(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _relative(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _file_info(root: Path, path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": _relative(root, path),
        "size_bytes": stat.st_size,
        "extension": path.suffix.lower(),
    }


def _walk_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.name != ".DS_Store" and not path.name.startswith(".~lock.")
    )


def _manifest_path(root: Path) -> Path:
    ai_manifest = root / "ai_output" / "evidence_manifest.json"
    if ai_manifest.exists():
        return ai_manifest
    return root / "evidence_manifest.json"


def _manifest_types(manifest: dict[str, Any] | None) -> list[str]:
    if not manifest:
        return []
    return [str(check.get("type", check.get("kind", ""))) for check in manifest.get("checks", []) if isinstance(check, dict)]


def _evidence_depth(manifest_types: list[str], evidence_summary: dict[str, Any] | None) -> str:
    if not evidence_summary:
        return "none"
    if evidence_summary.get("checks_run", 0) == 0:
        return "none"
    if any(kind in {"command", "command_exit_zero"} for kind in manifest_types):
        return "strong" if evidence_summary.get("blocked", 0) == 0 and evidence_summary.get("fail", 0) == 0 else "command_blocked"
    if any(kind in {"file_contains", "no_forbidden_claims"} for kind in manifest_types):
        return "shallow"
    return "presence_only"


def _answer_claims_verification(answer_text: str) -> bool:
    return any(re.search(pattern, answer_text, flags=re.IGNORECASE) for pattern in CLAIM_PATTERNS)


def _looks_like_placeholder(answer_text: str) -> bool:
    lowered = answer_text.lower()
    return "ai answer placeholder" in lowered or "replace this file" in lowered or "evidence: pending" in lowered


def _looks_like_design(answer_text: str, output_files: list[Path]) -> bool:
    text = answer_text.lower()
    hint_count = sum(1 for hint in DESIGN_HINTS if hint in text)
    has_schema = any(path.name == "schema.json" for path in output_files)
    has_test_cases = any("test" in path.name.lower() for path in output_files)
    return hint_count >= 2 or (has_schema and has_test_cases)


def _classify(
    *,
    target_exists: bool,
    missing_required: list[str],
    answer_text: str,
    output_files: list[Path],
    evidence_summary: dict[str, Any] | None,
    evidence_depth: str,
    manifest_exists: bool,
    code_files: list[Path],
    rich_documents: list[Path],
    design_like: bool,
) -> str:
    if not target_exists:
        return "blocked"
    if not manifest_exists:
        return "fake_evidence" if _answer_claims_verification(answer_text) else "incomplete"
    if missing_required or _looks_like_placeholder(answer_text):
        return "incomplete"
    if evidence_summary:
        if evidence_summary.get("fail", 0) > 0:
            return "failed_evidence"
        if evidence_summary.get("blocked", 0) > 0:
            return "blocked"
    if _answer_claims_verification(answer_text) and evidence_depth in {"none", "presence_only"}:
        return "fake_evidence"
    if code_files and evidence_depth == "strong":
        return "verified_build"
    if code_files:
        return "working_code_unverified"
    if rich_documents and evidence_summary and evidence_summary.get("fail", 0) == 0 and evidence_summary.get("blocked", 0) == 0:
        return "working_document"
    if design_like:
        return "design_only"
    if output_files and evidence_summary and evidence_summary.get("fail", 0) == 0 and evidence_summary.get("blocked", 0) == 0:
        return "verified_files_shallow"
    return "incomplete"


def inspect_run_folder(target: str | Path, *, allow_commands: bool = False) -> dict[str, Any]:
    root = Path(target).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        return {
            "schema_version": 1,
            "run_id": f"inspect_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}",
            "generated_at": utc_now(),
            "target": str(root),
            "principle": "fact_verified_only",
            "classification": "blocked",
            "summary": {"status": "blocked", "reason": "Target folder does not exist or is not a directory."},
            "findings": [],
            "limitations": ["Cannot inspect a missing or non-directory target."],
        }

    ai_output = root / "ai_output"
    manifest_file = _manifest_path(root)
    answer_file = ai_output / "ANSWER.md" if ai_output.exists() else root / "ANSWER.md"
    all_files = _walk_files(root)
    output_files = _walk_files(ai_output) if ai_output.exists() else []
    generated_output_files = [
        path for path in output_files if path.name not in {"ANSWER.md", "evidence_manifest.json"} and path.name != ".DS_Store"
    ]
    answer_text = _read_text(answer_file) if answer_file.exists() else ""
    manifest = _json_or_none(manifest_file) if manifest_file.exists() else None
    manifest_types = _manifest_types(manifest)
    evidence_report: dict[str, Any] | None = None
    evidence_summary: dict[str, Any] | None = None
    evidence_error = ""
    if manifest_file.exists() and manifest is not None:
        try:
            evidence_report = verify_manifest(manifest_file, allow_commands=allow_commands)
            evidence_summary = evidence_report["summary"]
        except Exception as exc:  # pragma: no cover - defensive reporting path
            evidence_error = str(exc)

    expected = list(EXPECTED_ROOT_FILES) + [f"ai_output/{name}" for name in EXPECTED_AI_OUTPUT_FILES]
    missing_required = [name for name in EXPECTED_ROOT_FILES if not (root / name).exists()]
    if not ai_output.exists():
        missing_required.append("ai_output/")
    else:
        missing_required.extend(f"ai_output/{name}" for name in EXPECTED_AI_OUTPUT_FILES if not (ai_output / name).exists())

    code_files = [path for path in generated_output_files if path.suffix.lower() in CODE_EXTENSIONS]
    document_files = [path for path in generated_output_files if path.suffix.lower() in DOCUMENT_EXTENSIONS]
    rich_documents = [path for path in generated_output_files if path.suffix.lower() in RICH_DOCUMENT_EXTENSIONS]
    design_like = _looks_like_design(answer_text, generated_output_files)
    depth = _evidence_depth(manifest_types, evidence_summary)
    classification = _classify(
        target_exists=True,
        missing_required=missing_required,
        answer_text=answer_text,
        output_files=generated_output_files,
        evidence_summary=evidence_summary,
        evidence_depth=depth,
        manifest_exists=manifest_file.exists() and manifest is not None,
        code_files=code_files,
        rich_documents=rich_documents,
        design_like=design_like,
    )

    findings = [
        {
            "id": "standard_structure",
            "status": "pass" if not missing_required else "fail",
            "evidence": {"expected": expected, "missing": missing_required},
        },
        {
            "id": "output_inventory",
            "status": "pass" if generated_output_files else "warn",
            "evidence": {
                "total_files": len(all_files),
                "generated_output_files": [_file_info(root, path) for path in generated_output_files],
                "code_files": [_relative(root, path) for path in code_files],
                "document_files": [_relative(root, path) for path in document_files],
            },
        },
        {
            "id": "evidence_manifest",
            "status": "pass"
            if evidence_summary and evidence_summary.get("fail", 0) == 0 and evidence_summary.get("blocked", 0) == 0
            else "blocked"
            if evidence_error or not manifest_file.exists() or manifest is None
            else "fail",
            "evidence": {
                "path": _relative(root, manifest_file),
                "exists": manifest_file.exists(),
                "valid_json": manifest is not None,
                "check_types": manifest_types,
                "summary": evidence_summary,
                "depth": depth,
                "error": evidence_error,
            },
        },
        {
            "id": "answer_claims",
            "status": "warn" if _answer_claims_verification(answer_text) and depth in {"none", "presence_only"} else "pass",
            "evidence": {
                "answer_exists": answer_file.exists(),
                "placeholder": _looks_like_placeholder(answer_text),
                "verification_claim_detected": _answer_claims_verification(answer_text),
            },
        },
    ]
    limitations: list[str] = []
    if depth in {"presence_only", "shallow"}:
        limitations.append("Evidence checks are shallow; they prove file presence or phrases, not full task correctness.")
    if classification == "design_only":
        limitations.append("This output is useful design/planning material, not a running application or automated system.")
    if classification == "working_code_unverified":
        limitations.append("Code-like files exist, but no passing command/test evidence proves they run.")
    if evidence_error:
        limitations.append(f"Evidence manifest could not be verified: {evidence_error}")

    return {
        "schema_version": 1,
        "run_id": f"inspect_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}",
        "generated_at": utc_now(),
        "target": str(root),
        "principle": "fact_verified_only",
        "classification": classification,
        "summary": {
            "status": "pass" if classification in {"design_only", "working_document", "verified_build", "verified_files_shallow"} else classification,
            "evidence_depth": depth,
            "output_files": len(generated_output_files),
            "code_files": len(code_files),
            "document_files": len(document_files),
            "missing_required": len(missing_required),
        },
        "structure": {
            "root_files": [_relative(root, path) for path in all_files if path.parent == root],
            "ai_output_files": [_relative(root, path) for path in output_files],
            "agent_protocol_present": any((root / name).exists() for name in EXPECTED_AGENT_FILES),
        },
        "evidence_report": evidence_report,
        "findings": findings,
        "limitations": limitations,
        "next_steps": _next_steps(classification, missing_required=missing_required, generated_output_files=generated_output_files),
    }


def _next_steps(classification: str, *, missing_required: list[str] | None = None, generated_output_files: list[Path] | None = None) -> list[str]:
    missing_required = missing_required or []
    generated_output_files = generated_output_files or []
    if classification == "design_only":
        return [
            "Decide whether the design should become code, a document, a spreadsheet, or an app.",
            "Add task-specific evidence checks before calling it verified.",
            "If building code, add command checks for tests and run nkama-evidence-layer with --allow-commands after review.",
        ]
    if classification == "working_code_unverified":
        return [
            "Add command checks that run the app tests or smoke checks.",
            "Rerun nkama-evidence-layer with --allow-commands after reviewing allowed_command_prefixes.",
        ]
    if classification == "incomplete":
        if missing_required:
            return ["Create the missing required files or rerun nkama-fact-benchmark run/start/agent."]
        if not generated_output_files:
            return [
                "This is only a prepared starter folder; no real AI output files have been added yet.",
                "Paste evidence_prompt.md into the AI, put the generated work in ai_output/, update evidence_manifest.json, then rerun inspect.",
            ]
        return ["Finish the AI output, update evidence_manifest.json, then rerun inspect."]
    if classification == "fake_evidence":
        return ["Remove unsupported success claims or add real manifest checks that prove them."]
    if classification == "verified_build":
        return ["Review the generated output manually for product quality, not just technical evidence."]
    if classification == "verified_files_shallow":
        return [
            "Treat this as verified file evidence, not proof of full product correctness.",
            "For sandbox capability tests, run the same command inside each AI environment you want to compare.",
            "Add command checks when you need stronger proof than file presence and phrase matches.",
        ]
    return ["Fix failed or blocked checks, then rerun inspect."]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect a Nkama run folder and classify what the AI actually produced.")
    parser.add_argument("folder", help="Path to a Nkama run folder.")
    parser.add_argument("--allow-commands", action="store_true", help="Allow reviewed command checks while verifying the manifest.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    print(json.dumps(inspect_run_folder(args.folder, allow_commands=args.allow_commands), indent=2))


if __name__ == "__main__":
    main()
