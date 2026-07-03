from __future__ import annotations

import argparse
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .evidence_layer import verify_manifest
from .prompt_filter import wrap_prompt


CONTRACT_FILE = "truth_contract.json"
RUN_LOG_FILE = "TRUTH_FILTER_RUNS.jsonl"
COMPARISON_JSON = "TRUTH_FILTER_COMPARISON.json"
COMPARISON_MD = "TRUTH_FILTER_COMPARISON.md"
DEFAULT_SUBMISSIONS = ["codex", "claude", "chatgpt", "gemini", "local_model"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip().lower()).strip("-")
    return slug or f"truth-task-{uuid.uuid4().hex[:8]}"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def init_contract(
    *,
    name: str,
    output_dir: str | Path,
    prompt: str = "",
    submissions: list[str] | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    output_path = Path(output_dir).expanduser().resolve()
    if output_path.exists() and any(output_path.iterdir()) and not overwrite:
        raise FileExistsError(f"Output directory is not empty: {output_path}")
    output_path.mkdir(parents=True, exist_ok=True)
    submissions = submissions or list(DEFAULT_SUBMISSIONS)
    task_prompt = prompt or "Complete the task and include an evidence_manifest.json that verifies your output."
    (output_path / "prompt.md").write_text(wrap_prompt(task_prompt), encoding="utf-8")
    records = []
    for item in submissions:
        name_slug = slugify(item)
        subdir = output_path / "submissions" / name_slug
        subdir.mkdir(parents=True, exist_ok=True)
        (subdir / "PUT_FILES_HERE.md").write_text(
            "# Submission Folder\n\nPut this AI's generated files here, including `evidence_manifest.json` when possible.\n",
            encoding="utf-8",
        )
        records.append({"name": name_slug, "path": str(subdir.relative_to(output_path))})
    contract = {
        "schema_version": 1,
        "name": name,
        "created_at": utc_now(),
        "prompt": "prompt.md",
        "submissions": records,
        "runner": "evidence_manifest",
        "safety": {
            "default_external_model_calls": "not_run",
            "default_command_execution": "blocked_until_allow_commands",
            "blocked_evidence_counts_as_success": False,
        },
    }
    _write_json(output_path / CONTRACT_FILE, contract)
    return contract


def load_contract(contract_dir: str | Path) -> dict[str, Any]:
    root = Path(contract_dir).expanduser().resolve()
    contract_path = root / CONTRACT_FILE
    if not contract_path.exists():
        raise FileNotFoundError(f"Missing {CONTRACT_FILE}: {contract_path}")
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["_contract_dir"] = str(root)
    return contract


def _submission_path(contract: dict[str, Any], submission: dict[str, Any]) -> Path:
    root = Path(str(contract["_contract_dir"]))
    raw = Path(str(submission["path"]))
    return raw if raw.is_absolute() else (root / raw).resolve()


def run_submission(contract: dict[str, Any], submission: dict[str, Any], *, allow_commands: bool = False) -> dict[str, Any]:
    path = _submission_path(contract, submission)
    name = str(submission.get("name", path.name))
    manifest = path / "evidence_manifest.json"
    if not path.exists():
        return {"name": name, "path": str(path), "status": "blocked", "summary": {}, "limitations": ["Submission directory does not exist."]}
    if not manifest.exists():
        return {"name": name, "path": str(path), "status": "blocked", "summary": {}, "limitations": ["Missing evidence_manifest.json."]}
    report = verify_manifest(manifest, allow_commands=allow_commands)
    summary = report["summary"]
    status = "pass" if summary["fail"] == 0 and summary["blocked"] == 0 else "fail"
    return {
        "name": name,
        "path": str(path),
        "status": status,
        "summary": summary,
        "limitations": [] if status == "pass" else ["Evidence manifest has failed or blocked checks."],
    }


def render_comparison(report: dict[str, Any]) -> str:
    lines = [
        "# Nkama Truth Filter Comparison",
        "",
        f"Run ID: `{report['run_id']}`",
        f"Generated: {report['generated_at']}",
        "",
        "| Submission | Status | Summary | Limitation |",
        "|---|---:|---|---|",
    ]
    for result in report["results"]:
        summary = result.get("summary", {})
        bits = [f"{key}={summary[key]}" for key in ["pass", "fail", "blocked"] if key in summary]
        lines.append(
            f"| {result['name']} | {result['status'].upper()} | {', '.join(bits)} | {'; '.join(result.get('limitations', []))} |"
        )
    lines.extend(["", "Blocked evidence is not treated as success.", ""])
    return "\n".join(lines)


def run_contract(contract_dir: str | Path, *, submission_names: list[str] | None = None, allow_commands: bool = False) -> dict[str, Any]:
    root = Path(contract_dir).expanduser().resolve()
    contract = load_contract(root)
    selected = set(submission_names or [])
    submissions = [
        item
        for item in contract.get("submissions", [])
        if isinstance(item, dict) and (not selected or str(item.get("name")) in selected)
    ]
    results = [run_submission(contract, item, allow_commands=allow_commands) for item in submissions]
    report = {
        "schema_version": 1,
        "run_id": f"truth_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}",
        "generated_at": utc_now(),
        "contract_path": str(root / CONTRACT_FILE),
        "summary": {
            "submissions": len(results),
            "pass": sum(1 for item in results if item["status"] == "pass"),
            "fail": sum(1 for item in results if item["status"] == "fail"),
            "blocked": sum(1 for item in results if item["status"] == "blocked"),
        },
        "results": results,
    }
    _write_json(root / COMPARISON_JSON, report)
    (root / COMPARISON_MD).write_text(render_comparison(report), encoding="utf-8")
    with (root / RUN_LOG_FILE).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"run_id": report["run_id"], "generated_at": report["generated_at"], "summary": report["summary"]}) + "\n")
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create and run evidence-gated AI task contracts.")
    sub = parser.add_subparsers(dest="command")
    init = sub.add_parser("init", help="Create a truth-filter task contract.")
    init.add_argument("name")
    init.add_argument("--prompt", default="")
    init.add_argument("--output", help="Output directory. Defaults to a slug of the task name.")
    init.add_argument("--submissions", default=",".join(DEFAULT_SUBMISSIONS))
    init.add_argument("--overwrite", action="store_true")
    run = sub.add_parser("run", help="Run evidence checks for submissions.")
    run.add_argument("contract_dir")
    run.add_argument("--submission", action="append", default=[])
    run.add_argument("--allow-commands", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "init":
        output = args.output or slugify(args.name)
        submissions = [slugify(item) for item in args.submissions.split(",") if item.strip()]
        contract = init_contract(name=args.name, output_dir=output, prompt=args.prompt, submissions=submissions, overwrite=args.overwrite)
        print(json.dumps({"contract": str(Path(output).expanduser().resolve() / CONTRACT_FILE), "submissions": contract["submissions"]}, indent=2))
        return
    if args.command == "run":
        report = run_contract(args.contract_dir, submission_names=args.submission, allow_commands=args.allow_commands)
        root = Path(args.contract_dir).expanduser().resolve()
        print(json.dumps({"summary": report["summary"], "json_output": str(root / COMPARISON_JSON), "markdown_output": str(root / COMPARISON_MD)}, indent=2))
        return
    build_parser().print_help()


if __name__ == "__main__":
    main()
