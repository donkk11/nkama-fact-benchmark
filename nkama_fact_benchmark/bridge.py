"""One-command bridge: two terminal agents, one contract, no MCP.

The user picks which agent builds and which one verifies. Nkama prepares the
evidence contract, the builder works under scoped permissions, the verifier
independently re-runs the evidence layer and signs a verdict, and the harness
re-verifies everything itself. Nobody grades their own homework.

    uvx nkama-fact-benchmark bridge "MY TASK" \\
      --builder claude --verifier codex --allow-external-model
"""

from __future__ import annotations

import argparse
import glob
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .agent import (
    _agent_model_prompt,
    _build_tool_policy,
    _short_text,
    create_agent_package,
    render_agent_protocol,
    run_agent_model,
)
from .evidence_layer import verify_manifest

AGENTS = ("claude", "codex")
CODEX_APP_GLOB = "/Applications/Codex*.app/Contents/Resources/codex"
DEFAULT_ALLOWED_COMMANDS = ["python3 *", "uvx *"]
VERDICT_FILE = "VERIFIER_VERDICT.md"
CHECKS_FILE = "VERIFIER_CHECKS.json"
BRIDGE_REPORT = "BRIDGE_REPORT.json"


def find_agent_cli(name: str) -> str | None:
    """Locate a provider CLI: PATH first, then known app-bundle locations."""
    binary = shutil.which(name)
    if binary:
        return binary
    if name == "codex":
        hits = sorted(glob.glob(CODEX_APP_GLOB))
        if hits:
            return hits[-1]
    return None


def _verifier_prompt(name: str, manifest: str, run_dir: str) -> str:
    return (
        "You are the independent verifier in an Nkama bridge run. Another AI "
        "agent built the contents of ai_output/ and reported its own results. "
        "Do NOT trust that report.\n\n"
        "Independently run this exact command and read the JSON summary:\n"
        f"uvx --no-cache --from nkama-fact-benchmark nkama-evidence-layer {manifest} --allow-commands\n\n"
        "Also read ai_output/ANSWER.md and compare its claims to the summary "
        "you personally observed.\n\n"
        f"Then write {VERDICT_FILE} in {run_dir} containing: a first line "
        "'Verdict: PASS' or 'Verdict: FAIL' or 'Verdict: BLOCKED'; the exact "
        "evidence summary JSON you observed; any discrepancies between the "
        "builder's claims and your observation; and the closing signature "
        f"'Verified by {name}'.\n\n"
        f"Also write {CHECKS_FILE} in {run_dir} — a JSON object with one entry "
        "per check id from the manifest you just ran, each recording whether "
        "you personally agree that check's real result matches what you "
        "observed:\n"
        '{"per_check": [{"id": "<check id from the manifest>", "agrees": true|false, '
        '"note": "required and specific if agrees is false — say exactly what you '
        'observed instead"}]}\n\n'
        "One entry per check id in the manifest, no more, no fewer. This file "
        "is what lets a human tell 'the verifier agreed with everything' apart "
        "from 'the verifier only checked the overall shape' — do not skip it "
        "and do not copy the builder's own per-check verdicts without "
        "independently confirming each one yourself.\n\n"
        "If you cannot run the command (missing tool, no network, denied "
        "permission), the verdict is BLOCKED - never guess and never copy the "
        "builder's numbers."
    )


def _run_codex(binary: str, prompt: str, run_dir: str, sandbox: str, timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(
        [binary, "exec", "--sandbox", sandbox, "--cd", run_dir, prompt],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _run_claude_verifier(binary: str, model: str, prompt: str, run_dir: str, timeout: int) -> subprocess.CompletedProcess:
    command = [
        binary, "--print", "--model", model, "--no-session-persistence",
        "--tools", "Read,Edit,Write,Bash",
        "--allowedTools", "Read", "Edit", "Write", "Bash(uvx *)",
        "--add-dir", run_dir, "--permission-mode", "auto", prompt,
    ]
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False, cwd=run_dir)


def _write_bridge_report(result: dict[str, Any], run_dir: str) -> None:
    (Path(run_dir) / BRIDGE_REPORT).write_text(json.dumps(result, indent=2), encoding="utf-8")


def _finish_after_bad_builder(
    result: dict[str, Any],
    *,
    payload: dict[str, Any],
    harness_summary: dict[str, Any],
    status: str,
) -> dict[str, Any]:
    run_dir = payload["output_dir"]
    result["status"] = "blocked" if status == "blocked" else "fail"
    result["verifier"].update(status="not_run", verdict="NOT_RUN")
    result["harness_reverification"] = harness_summary
    result["run_dir"] = run_dir
    result["evidence_manifest"] = payload["evidence_manifest"]
    result["answer"] = str(Path(run_dir) / "ai_output" / "ANSWER.md")
    result["limitations"].append(
        "Builder did not complete successfully; independent verifier was not allowed to convert a blocked/failed build into a pass."
    )
    _write_bridge_report(result, run_dir)
    return result


def run_bridge(
    *,
    task: str,
    builder: str = "claude",
    verifier: str | None = None,
    builder_model: str = "claude-sonnet-4-6",
    verifier_model: str = "claude-sonnet-4-6",
    max_budget_usd: str = "2",
    timeout_seconds: int = 300,
    output_dir: str | Path | None = None,
    allow_external_model: bool = False,
    allowed_commands: list[str] | None = None,
    codex_sandbox_build: str = "workspace-write",
    codex_sandbox_verify: str = "danger-full-access",
    title: str = "Nkama Bridge Run",
    overwrite: bool = False,
) -> dict[str, Any]:
    if builder not in AGENTS:
        raise ValueError(f"builder must be one of {AGENTS}")
    verifier = verifier or ("codex" if builder == "claude" else "claude")
    if verifier not in AGENTS:
        raise ValueError(f"verifier must be one of {AGENTS}")
    if verifier == builder:
        raise ValueError("builder and verifier must be different agents - nobody grades their own homework")
    allowed_commands = allowed_commands or list(DEFAULT_ALLOWED_COMMANDS)

    detected = {name: find_agent_cli(name) for name in (builder, verifier)}
    missing = [name for name, path in detected.items() if not path]

    result: dict[str, Any] = {
        "schema_version": 1,
        "status": "blocked",
        "builder": {"agent": builder, "cli": detected.get(builder)},
        "verifier": {"agent": verifier, "cli": detected.get(verifier)},
        "limitations": [],
    }
    if missing:
        result["limitations"].append(
            f"Missing provider CLI(s): {', '.join(missing)}. Install/authenticate them, then rerun."
        )
        return result
    if not allow_external_model:
        result["limitations"].append(
            "External model calls are disabled. Rerun with --allow-external-model after reviewing the task."
        )
        return result

    # ---- build phase --------------------------------------------------------
    if builder == "claude":
        build = run_agent_model(
            task=task,
            output_dir=output_dir,
            model=builder_model,
            max_budget_usd=max_budget_usd,
            allow_external_model=True,
            allow_claude_tools=True,
            allowed_commands=allowed_commands,
            timeout_seconds=timeout_seconds,
            title=title,
            overwrite=overwrite,
        )
        payload = build["agent"]
        # agent-run verifies without command execution, so command checks read
        # "blocked" at this stage; grade the builder on the full verification.
        build_summary = verify_manifest(payload["evidence_manifest"], allow_commands=True)["summary"]
        build_status = build.get("status", "blocked")
        model_run = build.get("model_run", {})
        # run_agent_model computes its status without executing command checks,
        # so a strong manifest (command_exit_zero) always reads "fail" there.
        # Grade the builder on the full re-verification (clean_pass runs the
        # commands); fall back to build_status only to label genuine failures.
        result["builder"].update(
            status="pass" if build_summary.get("clean_pass") else build_status,
            model=builder_model,
            evidence_summary=build_summary,
            model_run_status=model_run.get("status"),
            provider_metadata=model_run.get("provider_metadata"),
        )
        if result["builder"]["status"] != "pass":
            return _finish_after_bad_builder(
                result,
                payload=payload,
                harness_summary=build_summary,
                status=result["builder"]["status"],
            )
    else:  # codex builds
        payload = create_agent_package(task=task, output_dir=output_dir, title=title, overwrite=overwrite)
        tool_policy = {
            "tool_mode": "codex_scoped_tools",
            "allowed_directories": [payload["output_dir"]],
            "allowed_commands": list(allowed_commands),
            "allowed_external_model": allow_external_model,
            "allowed_browser_mcp_tools": "none",
            "budget_cap": max_budget_usd or "not set",
            "claude_tools": "none",
            "claude_allowed_tools": [],
            "permission_mode": codex_sandbox_build,
        }
        Path(payload["agent_protocol"]).write_text(render_agent_protocol(payload, tool_policy), encoding="utf-8")
        prompt = _agent_model_prompt(payload, tool_policy)
        try:
            completed = _run_codex(detected[builder], prompt, payload["output_dir"], codex_sandbox_build, timeout_seconds)
            build_summary = verify_manifest(payload["evidence_manifest"], allow_commands=True)["summary"]
            result["builder"].update(
                status="pass" if build_summary.get("clean_pass") else "fail",
                model="codex", exit_code=completed.returncode,
                evidence_summary=build_summary, stdout_excerpt=_short_text(completed.stdout or "", 600),
            )
            if completed.returncode != 0 and result["builder"]["status"] == "pass":
                result["builder"]["status"] = "fail"
        except subprocess.TimeoutExpired:
            try:
                build_summary = verify_manifest(payload["evidence_manifest"], allow_commands=True)["summary"]
            except Exception as exc:  # noqa: BLE001 - report verifier failure as evidence limitation.
                build_summary = {"error": str(exc)}
            result["builder"].update(status="blocked", model="codex", evidence_summary=build_summary)
            result["limitations"].append(f"Codex build phase exceeded {timeout_seconds}s timeout.")
            return _finish_after_bad_builder(
                result,
                payload=payload,
                harness_summary=build_summary,
                status="blocked",
            )
        if result["builder"]["status"] != "pass":
            return _finish_after_bad_builder(
                result,
                payload=payload,
                harness_summary=build_summary,
                status=result["builder"]["status"],
            )

    run_dir = payload["output_dir"]
    manifest = payload["evidence_manifest"]

    # ---- verify phase (the other agent, independently) ----------------------
    prompt = _verifier_prompt(verifier.capitalize(), manifest, run_dir)
    try:
        if verifier == "codex":
            completed = _run_codex(detected[verifier], prompt, run_dir, codex_sandbox_verify, timeout_seconds)
        else:
            completed = _run_claude_verifier(detected[verifier], verifier_model, prompt, run_dir, timeout_seconds)
        result["verifier"].update(exit_code=completed.returncode,
                                  stdout_excerpt=_short_text(completed.stdout or "", 600))
    except subprocess.TimeoutExpired:
        result["verifier"].update(status="blocked")
        result["limitations"].append(f"Verifier phase exceeded {timeout_seconds}s timeout.")

    verdict_path = Path(run_dir) / VERDICT_FILE
    verdict_text = verdict_path.read_text(encoding="utf-8") if verdict_path.exists() else ""
    first_line = verdict_text.splitlines()[0].strip() if verdict_text else ""
    # Real bug, found by an adversarial audit: a loose substring search let a
    # negated sentence ("this is NOT A PASS") parse as PASS, and "UNBLOCKED"
    # parse as BLOCKED. The prompt tells the verifier to write the literal
    # "Verdict: PASS/FAIL/BLOCKED" as the first line — require that exact
    # shape instead of scanning for the word anywhere in the line.
    verdict = "MISSING"
    match = re.match(r"verdict\s*:\s*(PASS|FAIL|BLOCKED)\b", first_line, re.IGNORECASE)
    if match:
        verdict = match.group(1).upper()
    result["verifier"].update(verdict=verdict, verdict_file=str(verdict_path) if verdict_text else None)

    # ---- harness re-verification (trust nobody, including the verifier) -----
    harness_full = verify_manifest(manifest, allow_commands=True)
    harness = harness_full["summary"]
    result["harness_reverification"] = harness

    # ---- merge the verifier's structured per-check findings, if it wrote them ----
    # Real, not assumed: a first-line "Verdict: PASS" can't tell a human whether
    # the verifier actually re-checked every claim or only the overall shape.
    # This is the fix for that — see nkama:bridge design notes.
    checks_path = Path(run_dir) / CHECKS_FILE
    per_check_review: dict[str, dict[str, Any]] = {}
    if checks_path.exists():
        try:
            parsed = json.loads(checks_path.read_text(encoding="utf-8"))
            for entry in parsed.get("per_check", []):
                cid = str(entry.get("id", ""))
                if not cid:
                    continue
                # Real bug, found by an adversarial audit: `if agrees` used
                # Python truthiness, so a verifier writing the JSON string
                # "false" (truthy, since it's a non-empty string) read as
                # confirmed. Require the literal JSON boolean true.
                agrees = entry.get("agrees") is True
                per_check_review[cid] = {
                    "independent_review": "confirmed" if agrees else "disputed",
                    "independent_review_note": entry.get("note") if not agrees else None,
                }
        except (json.JSONDecodeError, TypeError, AttributeError) as exc:
            result["limitations"].append(f"{CHECKS_FILE} existed but could not be parsed: {exc}")
    else:
        result["limitations"].append(
            f"Verifier did not write {CHECKS_FILE} — per-check independent_review "
            "stays 'not_requested' on every check; only the overall verdict is cross-verified."
        )

    reviewed_checks = []
    for check in harness_full.get("checks", []):
        check = dict(check)
        review = per_check_review.get(check.get("id", ""))
        if review:
            check["independent_review"] = review["independent_review"]
            if review["independent_review_note"]:
                check["independent_review_note"] = review["independent_review_note"]
        reviewed_checks.append(check)
    result["checks"] = reviewed_checks
    result["per_check_review_count"] = len(per_check_review)
    real_check_ids = {str(c.get("id", "")) for c in harness_full.get("checks", [])}
    total_checks = len(real_check_ids)
    # Real gaps, found across two rounds of adversarial audit — three separate
    # ways "review_complete" could be faked before this:
    #   1. Only reviewing 1 of N checks (fixed first round: count >= total).
    #   2. Reviewing every real check but marking every one "agrees: false" —
    #      count-based completeness didn't care whether reviews agreed.
    #   3. Padding VERIFIER_CHECKS.json with fake/unknown ids to inflate the
    #      count without covering the real checks at all.
    # Fixed properly now: every real check id must be present AND confirmed —
    # coverage is checked by id intersection, not by count.
    matched_ids = real_check_ids & per_check_review.keys()
    all_matched_confirmed = all(
        per_check_review[cid]["independent_review"] == "confirmed" for cid in matched_ids
    )
    review_complete = (
        total_checks == 0
        or (matched_ids == real_check_ids and all_matched_confirmed)
    )

    if (
        result["builder"].get("status") == "pass"
        and harness.get("clean_pass")
        and verdict == "PASS"
        and review_complete
    ):
        result["status"] = "pass"
    elif verdict == "PASS" and not review_complete:
        result["status"] = "fail"
        # Real bug, found by an adversarial audit: this always blamed an
        # incomplete count, even when every real check WAS reviewed but one
        # or more came back disputed — a different failure than "didn't
        # review enough". Diagnose the actual cause instead of guessing.
        if matched_ids != real_check_ids:
            result["limitations"].append(
                f"Verifier wrote 'Verdict: PASS' but only reviewed "
                f"{len(matched_ids)}/{total_checks} real checks individually "
                f"in {CHECKS_FILE} — an incomplete review is not a pass."
            )
        else:
            disputed_ids = sorted(
                cid for cid in matched_ids if per_check_review[cid]["independent_review"] != "confirmed"
            )
            result["limitations"].append(
                f"Verifier wrote 'Verdict: PASS' but disputed {len(disputed_ids)}/{total_checks} "
                f"checks individually in {CHECKS_FILE} ({', '.join(disputed_ids)}) — an overall "
                "PASS cannot override a disputed individual check."
            )
    elif verdict == "BLOCKED" or not verdict_text:
        result["status"] = "blocked"
        result["limitations"].append(
            "Verifier could not (or did not) independently confirm the evidence. Blocked is not success."
        )
    else:
        result["status"] = "fail"

    result["run_dir"] = run_dir
    result["evidence_manifest"] = manifest
    result["answer"] = str(Path(run_dir) / "ai_output" / "ANSWER.md")
    _write_bridge_report(result, run_dir)
    return result


def run_cli(args: argparse.Namespace) -> None:
    task = args.task or (Path(args.file).read_text(encoding="utf-8") if args.file else "")
    if not task.strip():
        raise SystemExit("Provide a task (positional argument or --file).")
    result = run_bridge(
        task=task,
        builder=args.builder,
        verifier=args.verifier,
        builder_model=args.model,
        verifier_model=args.verifier_model,
        max_budget_usd=args.max_budget_usd,
        timeout_seconds=args.timeout_seconds,
        output_dir=args.output,
        allow_external_model=args.allow_external_model,
        allowed_commands=args.allow_command or None,
        title=args.title,
        overwrite=args.overwrite,
    )
    if args.json:
        print(json.dumps(result, indent=2))
        return
    print("Nkama bridge run complete.")
    print(f"Status: {result['status']}")
    print(f"Builder: {result['builder'].get('agent')} -> {result['builder'].get('status')}")
    print(f"Verifier: {result['verifier'].get('agent')} -> verdict {result['verifier'].get('verdict', 'n/a')}")
    if result.get("harness_reverification") is not None:
        print(f"Harness re-verification: {result['harness_reverification']}")
    if result.get("run_dir"):
        print(f"Run folder: {result['run_dir']}")
    for limitation in result.get("limitations", []):
        print(f"Limitation: {limitation}")
