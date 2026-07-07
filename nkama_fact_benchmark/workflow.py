from __future__ import annotations

import argparse
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .prompt_filter import analyze_prompt, wrap_prompt


RUN_CONTRACT_JSON = "run_contract.json"
ORIGINAL_PROMPT_MD = "original_prompt.md"
EVIDENCE_PROMPT_MD = "evidence_prompt.md"
PROMPT_ANALYSIS_JSON = "prompt_analysis.json"
RUN_README_MD = "README.md"
AI_OUTPUT_DIR = "ai_output"
MANIFEST_TEMPLATE = "evidence_manifest.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip().lower()).strip("-_.")
    return slug or f"nkama-run-{uuid.uuid4().hex[:8]}"


def _read_prompt(args: argparse.Namespace) -> str:
    if args.file:
        return Path(args.file).expanduser().read_text(encoding="utf-8")
    if args.prompt:
        return args.prompt
    raise SystemExit("Provide a prompt argument or --file path.")


def _read_prompt_interactive(args: argparse.Namespace) -> str:
    if args.file or args.prompt:
        return _read_prompt(args)
    print("What do you want your AI to build, answer, or verify?")
    print("Type the prompt, then press Enter. For multiple lines, keep typing and finish with an empty line.")
    lines: list[str] = []
    first = input("> ").strip()
    if not first:
        raise SystemExit("No prompt entered.")
    lines.append(first)
    while True:
        try:
            line = input("| ")
        except EOFError:
            break
        if not line.strip():
            break
        lines.append(line)
    return "\n".join(lines)


def _default_output_dir(prompt: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return Path(f"nkama_run_{stamp}_{slugify(prompt)[:40]}")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _manifest_template() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "allowed_command_prefixes": [],
        "checks": [
            {
                "id": "answer_file_exists",
                "name": "Answer file exists",
                "type": "file_exists",
                "path": "ANSWER.md",
            },
            {
                "id": "answer_mentions_evidence",
                "name": "Answer mentions evidence",
                "type": "file_contains",
                "path": "ANSWER.md",
                "text": "Evidence:",
            },
            {
                "id": "answer_mentions_limitations",
                "name": "Answer mentions limitations",
                "type": "file_contains",
                "path": "ANSWER.md",
                "text": "Limitations:",
            },
        ],
        "_instructions": [
            "This is a starter manifest. Replace or extend these checks to match the files the AI actually generated.",
            "Command checks are blocked by default and require nkama-evidence-layer --allow-commands plus explicit allowed_command_prefixes.",
            "Use argv-style executable checks, for example: allowed_command_prefixes [[\"python3\"]] and command [\"python3\", \"test_project.py\"].",
            "Do not edit a blocked or failed report into a pass. Fix the evidence or keep the limitation visible.",
        ],
    }


def _readme(*, title: str, output_path: Path) -> str:
    manifest = f"{AI_OUTPUT_DIR}/{MANIFEST_TEMPLATE}"
    return (
        "# Nkama Fact Benchmark Run\n\n"
        f"Title: {title}\n\n"
        "This folder is a public-safe evidence-gated AI task package. It does not call an AI model by itself. "
        "It prepares the prompt, expected output folder, starter evidence manifest, and verification commands.\n\n"
        "## Files\n\n"
        "- `original_prompt.md` - the user's original task.\n"
        "- `evidence_prompt.md` - paste this into the AI assistant you want to test.\n"
        "- `prompt_analysis.json` - machine-readable prompt readiness checks.\n"
        "- `run_contract.json` - machine-readable run metadata and safety rules.\n"
        "- `ai_output/ANSWER.md` - the AI answer or generated-output summary.\n"
        f"- `{manifest}` - starter manifest for verifying the AI output.\n\n"
        "## Next Steps\n\n"
        "1. Paste `evidence_prompt.md` into the AI assistant.\n"
        f"2. Put the AI's generated files in `{AI_OUTPUT_DIR}/`.\n"
        f"3. Update `{manifest}` so it checks the actual files and tests.\n"
        "4. Verify the output:\n\n"
        "```bash\n"
        f"uvx --from nkama-fact-benchmark nkama-evidence-layer {output_path / manifest}\n"
        "```\n\n"
        "If the manifest contains reviewed command checks, run:\n\n"
        "```bash\n"
        f"uvx --from nkama-fact-benchmark nkama-evidence-layer {output_path / manifest} --allow-commands\n"
        "```\n\n"
        "Blocked evidence is not success. Fix the output, update the manifest, and rerun verification.\n"
        "Use `nkama-fact-benchmark inspect .` from this folder when you want a plain-language classification of what the AI actually produced.\n"
    )


def create_run_package(
    *,
    prompt: str,
    output_dir: str | Path | None = None,
    title: str = "Nkama AI Run",
    mode: str = "strict",
    overwrite: bool = False,
) -> dict[str, Any]:
    output_path = Path(output_dir).expanduser().resolve() if output_dir else _default_output_dir(prompt).resolve()
    if output_path.exists() and any(output_path.iterdir()) and not overwrite:
        raise FileExistsError(f"Output directory is not empty: {output_path}")
    output_path.mkdir(parents=True, exist_ok=True)
    ai_output = output_path / AI_OUTPUT_DIR
    ai_output.mkdir(exist_ok=True)

    analysis = analyze_prompt(prompt)
    run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"
    contract = {
        "schema_version": 1,
        "run_id": run_id,
        "title": title,
        "created_at": utc_now(),
        "principle": "fact_verified_only",
        "status": "prepared",
        "prompt_files": {
            "original": ORIGINAL_PROMPT_MD,
            "evidence_wrapped": EVIDENCE_PROMPT_MD,
            "analysis": PROMPT_ANALYSIS_JSON,
        },
        "output": {
            "directory": AI_OUTPUT_DIR,
            "evidence_manifest": f"{AI_OUTPUT_DIR}/{MANIFEST_TEMPLATE}",
        },
        "safety": {
            "external_model_calls": "not_run_by_public_default",
            "command_execution": "not_run_without_explicit_allow_commands",
            "blocked_evidence_counts_as_success": False,
            "private_files_read_by_default": False,
            "first_run_builds": False,
            "protocol_state_file": "NKAMA_SESSION_STATE.md when sandbox file storage is available",
        },
        "next_commands": {
            "verify_files_only": f"uvx --from nkama-fact-benchmark nkama-evidence-layer {AI_OUTPUT_DIR}/{MANIFEST_TEMPLATE}",
            "verify_with_reviewed_commands": f"uvx --from nkama-fact-benchmark nkama-evidence-layer {AI_OUTPUT_DIR}/{MANIFEST_TEMPLATE} --allow-commands",
        },
    }

    (output_path / ORIGINAL_PROMPT_MD).write_text(prompt.strip() + "\n", encoding="utf-8")
    (output_path / EVIDENCE_PROMPT_MD).write_text(wrap_prompt(prompt, mode=mode), encoding="utf-8")
    _write_json(output_path / PROMPT_ANALYSIS_JSON, analysis)
    _write_json(output_path / RUN_CONTRACT_JSON, contract)
    _write_json(ai_output / MANIFEST_TEMPLATE, _manifest_template())
    (ai_output / "ANSWER.md").write_text(
        "Answer:\n"
        "PENDING. Replace this placeholder with the AI assistant's answer or generated-output summary.\n\n"
        "Evidence:\n"
        "Pending. Add file, command, source, screenshot, or manifest evidence after work is actually performed.\n\n"
        "Limitations:\n"
        "No task output has been generated yet.\n\n"
        "Files changed or created:\n"
        "- `ANSWER.md` placeholder\n"
        "- `evidence_manifest.json` starter manifest\n\n"
        "Tests or checks run:\n"
        "None yet.\n",
        encoding="utf-8",
    )
    (output_path / RUN_README_MD).write_text(_readme(title=title, output_path=output_path), encoding="utf-8")

    return {
        "schema_version": 1,
        "title": title,
        "run_id": run_id,
        "output_dir": str(output_path),
        "status": "prepared",
        "readiness": analysis["readiness"],
        "original_prompt": str(output_path / ORIGINAL_PROMPT_MD),
        "evidence_prompt": str(output_path / EVIDENCE_PROMPT_MD),
        "prompt_analysis": str(output_path / PROMPT_ANALYSIS_JSON),
        "run_contract": str(output_path / RUN_CONTRACT_JSON),
        "ai_output_dir": str(ai_output),
        "evidence_manifest": str(ai_output / MANIFEST_TEMPLATE),
        "verification_command": f"uvx --from nkama-fact-benchmark nkama-evidence-layer {ai_output / MANIFEST_TEMPLATE}",
        "next_step": "Paste evidence_prompt.md into an AI assistant, place outputs in ai_output/, then verify the evidence manifest.",
    }


def render_start_message(payload: dict[str, Any]) -> str:
    return (
        "\nNkama Fact Benchmark started a verified AI workflow.\n\n"
        f"Run folder: {payload['output_dir']}\n"
        f"Prompt for your AI: {payload['evidence_prompt']}\n"
        f"AI output folder: {payload['ai_output_dir']}\n"
        f"Evidence manifest: {payload['evidence_manifest']}\n\n"
        "What to do next:\n"
        "1. Open `evidence_prompt.md` and paste it into the AI you want to use.\n"
        "2. Put the AI's answer or generated files into `ai_output/`.\n"
        "3. Update `ai_output/evidence_manifest.json` so it checks the real output.\n"
        "4. Run the verifier:\n\n"
        f"{payload['verification_command']}\n\n"
        "5. Inspect the finished folder:\n\n"
        f"uvx nkama-fact-benchmark inspect {payload['output_dir']}\n\n"
        "If evidence is missing, the result should be BLOCKED, not guessed as true.\n"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare a public-safe evidence-gated AI run folder.")
    parser.add_argument("prompt", nargs="?", help="Prompt text to prepare.")
    parser.add_argument("--file", help="Read prompt text from a file.")
    parser.add_argument("--output", help="Output directory. Defaults to a timestamped nkama_run_* folder.")
    parser.add_argument("--title", default="Nkama AI Run")
    parser.add_argument("--mode", choices=["strict", "compact"], default="strict")
    parser.add_argument("--overwrite", action="store_true")
    return parser


def _output_dir_for_start(args: argparse.Namespace, prompt: str) -> str | Path | None:
    if args.output:
        return args.output
    if args.prompt or args.file:
        return None
    default = _default_output_dir(prompt)
    response = input(f"Output folder [{default}]: ").strip()
    return response or default


def run_cli(args: argparse.Namespace, *, interactive: bool = False) -> dict[str, Any]:
    prompt = _read_prompt_interactive(args) if interactive else _read_prompt(args)
    output_dir = _output_dir_for_start(args, prompt) if interactive else args.output
    payload = create_run_package(
        prompt=prompt,
        output_dir=output_dir,
        title=args.title,
        mode=args.mode,
        overwrite=args.overwrite,
    )
    if interactive and not getattr(args, "json", False):
        print(render_start_message(payload))
    else:
        print(json.dumps(payload, indent=2))
    return payload


def main() -> None:
    run_cli(build_parser().parse_args())


if __name__ == "__main__":
    main()
