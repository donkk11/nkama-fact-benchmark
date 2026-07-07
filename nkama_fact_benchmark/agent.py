from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from pathlib import Path
from typing import Any

from .evidence_layer import verify_manifest
from .workflow import create_run_package


AGENT_PROTOCOL_MD = "AGENT_PROTOCOL.md"
MODEL_RUN_REPORT_JSON = "MODEL_RUN_REPORT.json"
DEFAULT_CLAUDE_MODEL = "sonnet"
DEFAULT_BROWSER_MCP_TOOLS = "none"
REQUIRED_PROVIDER_SECTIONS = (
    "Answer:",
    "Evidence:",
    "Limitations:",
)
FINAL_REPORT_SECTIONS = REQUIRED_PROVIDER_SECTIONS + (
    "Files changed or created:",
    "Tests or checks run:",
)


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _tool_policy_block(policy: dict[str, Any]) -> str:
    allowed_dirs = policy.get("allowed_directories") or []
    allowed_commands = policy.get("allowed_commands") or []
    return (
        "## Tool Permission Contract\n\n"
        "This mode may grant Claude/Codex tools.\n\n"
        f"- Tool mode: `{policy.get('tool_mode', 'text_only')}`\n"
        f"- Allowed directories: {', '.join(f'`{item}`' for item in allowed_dirs) if allowed_dirs else '`none`'}\n"
        f"- Allowed commands: {', '.join(f'`{item}`' for item in allowed_commands) if allowed_commands else '`none`'}\n"
        f"- Allowed external model: `{policy.get('allowed_external_model', False)}`\n"
        f"- Allowed browser/MCP tools: `{policy.get('allowed_browser_mcp_tools', DEFAULT_BROWSER_MCP_TOOLS)}`\n"
        f"- Budget cap: `{policy.get('budget_cap') or 'not set'}`\n"
        f"- Claude tools: `{policy.get('claude_tools') or 'none'}`\n"
        f"- Permission mode: `{policy.get('permission_mode') or 'not applicable'}`\n\n"
        "If the task requires anything outside this contract, stop and ask the user for that exact permission. "
        "Do not bypass permissions, do not simulate missing tools, and do not rewrite unavailable evidence into a pass.\n\n"
    )


def _read_task(args: argparse.Namespace) -> str:
    if args.file:
        return Path(args.file).expanduser().read_text(encoding="utf-8")
    return args.task or ""


def render_agent_protocol(payload: dict[str, Any] | None = None, tool_policy: dict[str, Any] | None = None) -> str:
    if payload:
        evidence_prompt = payload["evidence_prompt"]
        ai_output_dir = payload["ai_output_dir"]
        evidence_manifest = payload["evidence_manifest"]
        verifier = payload["verification_command"]
        task_state = (
            "A task workspace has already been prepared.\n\n"
            f"- Evidence prompt: `{evidence_prompt}`\n"
            f"- AI output folder: `{ai_output_dir}`\n"
            f"- Evidence manifest: `{evidence_manifest}`\n"
            f"- Verifier: `{verifier}`\n"
        )
    else:
        task_state = (
            "No task workspace has been prepared yet.\n\n"
            "Ask the user for the task, then run:\n\n"
            "```bash\n"
            "uvx nkama-fact-benchmark agent \"USER TASK HERE\" --output nkama_agent_run\n"
            "```\n"
        )

    policy = tool_policy or {
        "tool_mode": "text_only",
        "allowed_directories": [],
        "allowed_commands": [],
        "allowed_external_model": False,
        "allowed_browser_mcp_tools": DEFAULT_BROWSER_MCP_TOOLS,
        "budget_cap": "not set",
        "claude_tools": "",
        "permission_mode": None,
    }

    return (
        "# Nkama Fact Benchmark Agent Protocol\n\n"
        "You are an AI agent working under Nkama Fact Benchmark. Your goal is to complete the user's task while "
        "making the result verifiable. Do not treat this protocol as decoration; treat it as the working contract.\n\n"
        "## Current State\n\n"
        f"{task_state}\n\n"
        f"{_tool_policy_block(policy)}"
        "## Agent Rules\n\n"
        "1. If the user has not provided a task, ask for the task before building anything.\n"
        "2. Read `evidence_prompt.md` and use it as the task contract.\n"
        "3. Do not claim file access, code execution, browsing, database writes, screenshots, or tests unless actually performed.\n"
        "4. If a required fact, file, tool, or permission is unavailable, mark that item BLOCKED instead of pretending it passed.\n"
        "5. If private files, external model calls, shell commands, or network access are needed, ask the user for explicit permission first.\n"
        "6. Put generated answers, code, documents, or reports in `ai_output/`.\n"
        "7. Replace the placeholder `ai_output/ANSWER.md` with the real answer or a summary of generated files.\n"
        "8. Update `ai_output/evidence_manifest.json` so it checks the actual output files and tests.\n"
        "9. Run `nkama-evidence-layer` after updating the manifest. Use `--allow-commands` only for reviewed command checks.\n"
        "10. Final reports must separate Answer, Evidence, Limitations, Files changed or created, and Tests or checks run.\n\n"
        "## Session Memory\n\n"
        "If file storage is available, create or update `NKAMA_SESSION_STATE.md` in the task workspace. Keep it short and current:\n\n"
        "```text\n"
        "Protocol: Nkama Fact Benchmark active\n"
        "Task: ...\n"
        "Mode: design | build | inspect | compare\n"
        "Files created: ...\n"
        "Checks run: ...\n"
        "Open limitations: ...\n"
        "```\n\n"
        "If the conversation gets long, restate one short reminder that Nkama remains active. Do not clear this protocol unless the user explicitly asks you to deactivate or ignore Nkama state.\n\n"
        "## Verification Commands\n\n"
        "File-only verification:\n\n"
        "```bash\n"
        "uvx --from nkama-fact-benchmark nkama-evidence-layer ai_output/evidence_manifest.json\n"
        "```\n\n"
        "Reviewed command verification:\n\n"
        "```bash\n"
        "uvx --from nkama-fact-benchmark nkama-evidence-layer ai_output/evidence_manifest.json --allow-commands\n"
        "```\n\n"
        "## Evidence Manifest Command Schema\n\n"
        "Use argv-style command checks when you add executable proof. This is the canonical form:\n\n"
        "```json\n"
        "{\n"
        "  \"allowed_command_prefixes\": [[\"python3\"], [\"uvx\"]],\n"
        "  \"checks\": [\n"
        "    {\n"
        "      \"id\": \"unit_tests_pass\",\n"
        "      \"type\": \"command_exit_zero\",\n"
        "      \"command\": [\"python3\", \"test_example.py\"],\n"
        "      \"expected_exit_code\": 0\n"
        "    }\n"
        "  ]\n"
        "}\n"
        "```\n\n"
        "String commands may be split safely by newer Nkama versions, but argv lists are preferred because they avoid shell ambiguity.\n\n"
        "## Final Report Shape\n\n"
        "Answer:\n"
        "Evidence:\n"
        "Limitations:\n"
        "Files changed or created:\n"
        "Tests or checks run:\n\n"
        "Never rewrite a blocked or failed check into a pass. Fix the work, rerun the check, or report the limitation.\n"
    )


def create_agent_package(
    *,
    task: str,
    output_dir: str | Path | None = None,
    title: str = "Nkama Agent Run",
    mode: str = "strict",
    overwrite: bool = False,
) -> dict[str, Any]:
    payload = create_run_package(
        prompt=task,
        output_dir=output_dir,
        title=title,
        mode=mode,
        overwrite=overwrite,
    )
    protocol_path = Path(payload["output_dir"]) / AGENT_PROTOCOL_MD
    protocol_path.write_text(render_agent_protocol(payload), encoding="utf-8")
    payload["agent_protocol"] = str(protocol_path)
    payload["agent_next_step"] = "AI agent should read AGENT_PROTOCOL.md and evidence_prompt.md, build in ai_output/, then run nkama-evidence-layer."
    return payload


def _short_text(value: str, limit: int = 1200) -> str:
    text = value.strip()
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _build_tool_policy(
    *,
    payload: dict[str, Any],
    allow_external_model: bool,
    max_budget_usd: str | None,
    allow_claude_tools: bool = False,
    allowed_dirs: list[str] | None = None,
    allowed_commands: list[str] | None = None,
    allowed_browser_mcp_tools: str = DEFAULT_BROWSER_MCP_TOOLS,
    permission_mode: str | None = None,
) -> dict[str, Any]:
    command_patterns = list(allowed_commands or [])
    if allow_claude_tools:
        directories = _unique([payload["output_dir"], *(str(Path(item).expanduser().resolve()) for item in (allowed_dirs or []))])
        claude_tool_names = ["Read", "Edit"]
        allowed_tools = ["Read", "Edit"]
        if command_patterns:
            claude_tool_names.append("Bash")
            allowed_tools.extend(f"Bash({pattern})" for pattern in command_patterns)
        mode = permission_mode or "default"
        claude_tools = ",".join(claude_tool_names)
    else:
        directories = []
        allowed_tools = []
        mode = None
        claude_tools = ""
    return {
        "tool_mode": "claude_scoped_tools" if allow_claude_tools else "text_only",
        "allowed_directories": directories,
        "allowed_commands": command_patterns,
        "allowed_external_model": allow_external_model,
        "allowed_browser_mcp_tools": allowed_browser_mcp_tools,
        "budget_cap": max_budget_usd or "not set",
        "claude_tools": claude_tools,
        "claude_allowed_tools": allowed_tools,
        "permission_mode": mode,
    }


def _agent_model_prompt(payload: dict[str, Any], tool_policy: dict[str, Any]) -> str:
    protocol = Path(payload["agent_protocol"]).read_text(encoding="utf-8")
    evidence_prompt = Path(payload["evidence_prompt"]).read_text(encoding="utf-8")
    if tool_policy.get("tool_mode") == "text_only":
        tool_instructions = (
            "This run is text-only. You do not have filesystem, shell, browser, screenshot, or database tools.\n"
            "Do not ask to use tools. Do not print simulated tool calls. Do not say you will inspect files first.\n"
            "If the task can be answered from the prompt alone, answer it directly.\n"
            "If the task requires missing files, private data, current browsing, or execution, mark that part as BLOCKED in Limitations.\n"
            "Do not claim to have written files, run tests, browsed, or inspected attachments unless you actually did.\n"
        )
    else:
        tool_label = "Codex" if str(tool_policy.get("tool_mode", "")).startswith("codex") else "Claude"
        tool_instructions = (
            f"This run may provide scoped {tool_label} tools. Use only the tools and paths named in the Tool Permission Contract.\n"
            "If you need another directory, command, browser/MCP tool, credential, private file, or external service, stop and ask for that exact permission in Limitations.\n"
            "Do not bypass permissions. Do not use commands outside the allowed command patterns. Do not simulate tool results.\n"
            "When you create or edit files, put them inside the prepared task workspace unless the user explicitly allowed another directory.\n"
        )
    return (
        "You are being called by `nkama-fact-benchmark agent-run`.\n"
        "Follow the protocol and complete the task as a verifiable answer.\n"
        f"{tool_instructions}"
        "Return only the task answer and model-level evidence using exactly these headings:\n"
        "Answer:\n"
        "Evidence:\n"
        "Limitations:\n\n"
        "Do not include `Files changed or created` or `Tests or checks run`; the Nkama runner will add those sections after it writes files and verifies the manifest.\n\n"
        "=== AGENT PROTOCOL ===\n"
        f"{protocol}\n\n"
        "=== EVIDENCE PROMPT ===\n"
        f"{evidence_prompt}\n"
    )


def _claude_command(
    *,
    prompt: str,
    model: str,
    max_budget_usd: str | None,
    claude_command: str,
    tool_policy: dict[str, Any],
) -> list[str]:
    command = [
        claude_command,
        "--print",
        "--model",
        model,
        "--no-session-persistence",
        "--output-format",
        "json",
    ]
    if tool_policy.get("tool_mode") == "claude_scoped_tools":
        command.extend(["--tools", str(tool_policy.get("claude_tools") or "Read,Edit")])
        allowed_tools = [str(item) for item in tool_policy.get("claude_allowed_tools", []) if str(item)]
        if allowed_tools:
            command.extend(["--allowedTools", *allowed_tools])
        allowed_dirs = [str(item) for item in tool_policy.get("allowed_directories", []) if str(item)]
        if allowed_dirs:
            command.extend(["--add-dir", *allowed_dirs])
        permission_mode = tool_policy.get("permission_mode")
        if permission_mode:
            command.extend(["--permission-mode", str(permission_mode)])
    else:
        command.extend(["--tools", ""])
    if max_budget_usd:
        command.extend(["--max-budget-usd", max_budget_usd])
    command.append(prompt)
    return command


def _extract_provider_answer(stdout: str) -> tuple[str, dict[str, Any]]:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return stdout.strip(), {"kind": "plain_stdout"}
    if isinstance(payload, dict) and isinstance(payload.get("result"), str):
        metadata = {
            "kind": "claude_json",
            "type": payload.get("type"),
            "subtype": payload.get("subtype"),
            "is_error": payload.get("is_error"),
            "total_cost_usd": payload.get("total_cost_usd"),
            "stop_reason": payload.get("stop_reason"),
        }
        return payload["result"].strip(), metadata
    if isinstance(payload, dict):
        metadata = {
            "kind": "json_without_result",
            "type": payload.get("type"),
            "subtype": payload.get("subtype"),
            "is_error": payload.get("is_error"),
            "total_cost_usd": payload.get("total_cost_usd"),
            "stop_reason": payload.get("stop_reason"),
        }
        return json.dumps(payload, indent=2), metadata
    return json.dumps(payload, indent=2), {"kind": "json_without_result"}


def _looks_like_tool_request(text: str) -> bool:
    lowered = text.lower()
    explicit_tool_marker = "**tool:" in lowered or "\ntool:" in lowered or lowered.startswith("tool:")
    json_command_marker = '"command"' in lowered and '"description"' in lowered
    planning_to_inspect = "i'll check" in lowered or "i will check" in lowered or "before creating" in lowered
    return explicit_tool_marker or json_command_marker or planning_to_inspect


def _looks_like_permission_request(text: str) -> bool:
    lowered = text.lower()
    markers = (
        "need permission",
        "needs permission",
        "grant access",
        "permission denied",
        "not allowed",
        "i need access",
        "requires access",
        "cannot access",
        "no filesystem access",
        "no shell",
        "no browser",
    )
    return any(marker in lowered for marker in markers)


def _split_known_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    preface: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        matched = next((heading for heading in FINAL_REPORT_SECTIONS if stripped == heading or stripped.startswith(heading + " ")), None)
        if matched:
            current = matched
            rest = stripped[len(matched) :].strip()
            sections.setdefault(current, [])
            if rest:
                sections[current].append(rest)
            continue
        if current:
            sections.setdefault(current, []).append(line)
        elif stripped:
            preface.append(line)
    parsed = {heading: "\n".join(lines).strip() for heading, lines in sections.items()}
    if preface and "Answer:" not in parsed:
        parsed["Answer:"] = "\n".join(preface).strip()
    return parsed


def _answer_contract(answer: str, *, tool_policy: dict[str, Any] | None = None) -> dict[str, Any]:
    sections = _split_known_sections(answer)
    missing = [section for section in REQUIRED_PROVIDER_SECTIONS if not sections.get(section)]
    tool_request = _looks_like_tool_request(answer)
    permission_request = _looks_like_permission_request(answer)
    limitations = []
    if missing:
        limitations.append(f"Missing required provider sections: {', '.join(missing)}")
    if tool_request:
        limitations.append("Provider returned a tool-request or inspection-plan style response during a text-only run.")
    if permission_request and tool_policy and tool_policy.get("tool_mode") == "claude_scoped_tools":
        limitations.append("Provider appears to need additional permission outside the current tool contract.")
    return {
        "accepted": not limitations,
        "required_provider_sections": list(REQUIRED_PROVIDER_SECTIONS),
        "final_report_sections": list(FINAL_REPORT_SECTIONS),
        "missing_sections": missing,
        "tool_request_detected": tool_request,
        "permission_request_detected": permission_request,
        "limitations": limitations,
    }


def _rejected_answer_text(
    *,
    provider: str,
    completed_returncode: int,
    provider_metadata: dict[str, Any],
    answer: str,
    limitations: list[str],
) -> str:
    limitation_text = "\n".join(f"- {item}" for item in limitations) or "- Provider output did not satisfy the Nkama contract."
    return (
        "Answer:\n"
        "FAILED. The external model provider returned output, but Nkama Fact Benchmark rejected it because it did not satisfy the verifiable final-report contract.\n\n"
        "Evidence:\n"
        f"Provider `{provider}` was invoked and returned exit code {completed_returncode}.\n"
        f"Provider metadata: {json.dumps(provider_metadata, sort_keys=True)}\n"
        f"Raw provider answer excerpt: {_short_text(answer, 700)}\n\n"
        "Limitations:\n"
        f"{limitation_text}\n"
        "- The user's task answer was not accepted as verified output. Rerun after fixing the provider prompt, model behavior, or permissions.\n\n"
        "Files changed or created:\n"
        "ANSWER.md, MODEL_RUN_REPORT.json\n\n"
        "Tests or checks run:\n"
        "Provider subprocess attempted; Nkama answer contract checked; Nkama evidence manifest checked.\n"
    )


def _relative_to_output(payload: dict[str, Any], path: str | Path) -> str:
    output_root = Path(payload["output_dir"])
    candidate = Path(path)
    try:
        return str(candidate.relative_to(output_root))
    except ValueError:
        return str(candidate)


def _evidence_summary_line(evidence_summary: dict[str, Any] | None) -> str:
    if not evidence_summary:
        return "Evidence manifest verification: pending while composing final report."
    return (
        "Evidence manifest verification: "
        f"{evidence_summary.get('checks_run', 0)} checks, "
        f"{evidence_summary.get('pass', 0)} pass, "
        f"{evidence_summary.get('fail', 0)} fail, "
        f"{evidence_summary.get('blocked', 0)} blocked."
    )


def _suggested_permission_flags(
    *,
    allow_external_model: bool,
    allow_claude_tools: bool,
    max_budget_usd: str | None,
    timeout_seconds: int,
) -> list[str]:
    flags: list[str] = []
    if not allow_external_model:
        flags.append("--allow-external-model")
    if not allow_claude_tools:
        flags.append("--allow-claude-tools")
    if not max_budget_usd:
        flags.extend(["--max-budget-usd", "2.00"])
    flags.extend(["--timeout-seconds", str(max(timeout_seconds, 300))])
    return flags


def _permission_request(
    *,
    provider: str,
    model: str,
    reason: str,
    output_dir: str,
    allow_external_model: bool,
    allow_claude_tools: bool,
    max_budget_usd: str | None,
    timeout_seconds: int,
    provider_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = provider_metadata or {}
    reason_lower = " ".join(
        str(item).lower()
        for item in [
            reason,
            metadata.get("subtype"),
            metadata.get("stop_reason"),
            metadata.get("kind"),
        ]
        if item
    )
    requested: list[str] = []
    questions: list[str] = []
    if not allow_external_model or "external model calls are disabled" in reason_lower:
        requested.append("external_model_access")
        questions.append(f"Do you allow Nkama to call `{provider}` model `{model}` for this task?")
    if "no such file or directory" in reason_lower or "could not run provider command" in reason_lower:
        requested.append("provider_cli_available")
        questions.append(
            "Is the provider CLI installed and authenticated in this sandbox, or should the user run this command in a terminal where it is available?"
        )
    if "max_budget" in reason_lower or "budget" in reason_lower:
        requested.append("higher_budget_cap")
        questions.append("What maximum provider budget should be allowed for the rerun?")
    if "timeout" in reason_lower:
        requested.append("higher_timeout")
        questions.append("What timeout in seconds should be allowed for the rerun?")
    if not allow_claude_tools:
        requested.append("scoped_tool_access")
        questions.append("Should the provider receive scoped Read/Edit/Bash tools for the prepared output folder?")
    if not requested:
        requested.extend(["external_model_access", "budget_cap", "timeout_limit"])
        questions.append("Review the blocked reason, then choose whether to grant external model access, a budget cap, and a timeout.")
    flags = _suggested_permission_flags(
        allow_external_model=allow_external_model,
        allow_claude_tools=allow_claude_tools,
        max_budget_usd=max_budget_usd,
        timeout_seconds=timeout_seconds,
    )
    return {
        "status": "needs_user_permission",
        "blocked_reason": reason,
        "requested": _unique(requested),
        "questions": questions,
        "safe_defaults": {
            "max_budget_usd": max_budget_usd or "2.00",
            "timeout_seconds": max(timeout_seconds, 300),
            "output_dir": output_dir,
            "tools": "scoped Read/Edit/Bash only when --allow-claude-tools is set",
        },
        "suggested_flags": flags,
        "human_next_step": (
            "Ask the user to approve external model access, choose a budget cap, choose a timeout, "
            "and confirm the provider CLI is installed/authenticated. Then rerun agent-run with the suggested flags."
        ),
    }


def _permission_request_text(request: dict[str, Any]) -> str:
    questions = "\n".join(f"- {item}" for item in request.get("questions", []))
    flags = " ".join(shlex.quote(str(item)) for item in request.get("suggested_flags", []))
    safe_defaults = request.get("safe_defaults", {})
    return (
        "Permission request:\n"
        f"{questions}\n"
        f"- Suggested budget cap: `{safe_defaults.get('max_budget_usd')}`\n"
        f"- Suggested timeout: `{safe_defaults.get('timeout_seconds')}` seconds\n"
        f"- Suggested rerun flags: `{flags}`\n"
    )


def _compose_runner_answer(
    *,
    payload: dict[str, Any],
    provider: str,
    model: str,
    provider_answer: str,
    provider_metadata: dict[str, Any],
    exit_code: int,
    tool_policy: dict[str, Any],
    evidence_summary: dict[str, Any] | None = None,
) -> str:
    sections = _split_known_sections(provider_answer)
    task_answer = sections.get("Answer:", provider_answer.strip())
    model_evidence = sections.get("Evidence:", "The provider returned a text answer for the given task.")
    model_limitations = sections.get("Limitations:", "No model-level limitations were reported by the provider.")
    changed_files = [
        payload["original_prompt"],
        payload["evidence_prompt"],
        payload["prompt_analysis"],
        payload["run_contract"],
        payload["agent_protocol"],
        str(Path(payload["ai_output_dir"]) / "ANSWER.md"),
        payload["evidence_manifest"],
        str(Path(payload["output_dir"]) / MODEL_RUN_REPORT_JSON),
    ]
    changed_lines = "\n".join(f"- `{_relative_to_output(payload, item)}`" for item in changed_files)
    if tool_policy.get("tool_mode") == "claude_scoped_tools":
        runner_limitations = (
            "- The provider was run with scoped Claude tool access, not unlimited system access.\n"
            f"- Allowed directories: {', '.join(f'`{item}`' for item in tool_policy.get('allowed_directories', [])) or '`none`'}\n"
            f"- Allowed commands: {', '.join(f'`{item}`' for item in tool_policy.get('allowed_commands', [])) or '`none`'}\n"
            f"- Allowed browser/MCP tools: `{tool_policy.get('allowed_browser_mcp_tools', DEFAULT_BROWSER_MCP_TOOLS)}`\n"
            "- Anything outside the tool contract must be requested and reported as BLOCKED until granted.\n"
        )
    else:
        runner_limitations = (
            "- The provider was intentionally run in text-only mode with no filesystem, shell, browser, screenshot, or database tools.\n"
        )
    return (
        "Answer:\n"
        f"{task_answer}\n\n"
        "Evidence:\n"
        "Model-level evidence:\n"
        f"{model_evidence}\n\n"
        "Nkama runner evidence:\n"
        f"- Provider `{provider}` model `{model}` was invoked through a local CLI subprocess and returned exit code {exit_code}.\n"
        f"- Provider metadata: `{json.dumps(provider_metadata, sort_keys=True)}`\n"
        f"- Nkama runner wrote `ai_output/ANSWER.md` and `MODEL_RUN_REPORT.json`.\n"
        f"- {_evidence_summary_line(evidence_summary)}\n\n"
        "Limitations:\n"
        "Model-level limitations:\n"
        f"{model_limitations}\n\n"
        "Nkama runner limitations:\n"
        f"{runner_limitations}"
        "- The runner created files and verified the starter evidence manifest outside the provider model session.\n"
        "- The starter manifest proves basic output presence and evidence-section structure only; task-specific correctness is not deeply verified yet.\n\n"
        "Files changed or created:\n"
        f"{changed_lines}\n\n"
        "Tests or checks run:\n"
        "- Provider subprocess completed.\n"
        "- Nkama answer contract checked.\n"
        f"- {_evidence_summary_line(evidence_summary)}\n"
    )


def _blocked_report(
    payload: dict[str, Any],
    *,
    provider: str,
    reason: str,
    model: str = DEFAULT_CLAUDE_MODEL,
    allow_external_model: bool = False,
    allow_claude_tools: bool = False,
    max_budget_usd: str | None = None,
    timeout_seconds: int = 120,
    provider_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    permission_request = _permission_request(
        provider=provider,
        model=model,
        reason=reason,
        output_dir=payload["output_dir"],
        allow_external_model=allow_external_model,
        allow_claude_tools=allow_claude_tools,
        max_budget_usd=max_budget_usd,
        timeout_seconds=timeout_seconds,
        provider_metadata=provider_metadata,
    )
    report = {
        "schema_version": 1,
        "status": "blocked",
        "provider": provider,
        "model": model,
        "model_call": "not_run",
        "reason": reason,
        "permission_request": permission_request,
        "output_dir": payload["output_dir"],
        "answer": payload["ai_output_dir"] + "/ANSWER.md",
        "evidence_manifest": payload["evidence_manifest"],
    }
    _write_json(Path(payload["output_dir"]) / MODEL_RUN_REPORT_JSON, report)
    return report


def run_agent_model(
    *,
    task: str,
    output_dir: str | Path | None = None,
    provider: str = "claude",
    model: str = DEFAULT_CLAUDE_MODEL,
    max_budget_usd: str | None = None,
    claude_command: str = "claude",
    allow_external_model: bool = False,
    allow_claude_tools: bool = False,
    allowed_dirs: list[str] | None = None,
    allowed_commands: list[str] | None = None,
    allowed_browser_mcp_tools: str = DEFAULT_BROWSER_MCP_TOOLS,
    permission_mode: str | None = None,
    timeout_seconds: int = 120,
    title: str = "Nkama Agent Run",
    mode: str = "strict",
    overwrite: bool = False,
    command_runner: Any = subprocess.run,
) -> dict[str, Any]:
    payload = create_agent_package(task=task, output_dir=output_dir, title=title, mode=mode, overwrite=overwrite)
    tool_policy = _build_tool_policy(
        payload=payload,
        allow_external_model=allow_external_model,
        max_budget_usd=max_budget_usd,
        allow_claude_tools=allow_claude_tools,
        allowed_dirs=allowed_dirs,
        allowed_commands=allowed_commands,
        allowed_browser_mcp_tools=allowed_browser_mcp_tools,
        permission_mode=permission_mode,
    )
    protocol_path = Path(payload["agent_protocol"])
    protocol_path.write_text(render_agent_protocol(payload, tool_policy), encoding="utf-8")
    payload["tool_policy"] = tool_policy
    if not allow_external_model:
        report = _blocked_report(
            payload,
            provider=provider,
            reason="External model calls are disabled. Rerun with --allow-external-model after reviewing the task and data.",
            model=model,
            allow_external_model=allow_external_model,
            allow_claude_tools=allow_claude_tools,
            max_budget_usd=max_budget_usd,
            timeout_seconds=timeout_seconds,
        )
        return {"schema_version": 1, "status": "blocked", "agent": payload, "model_run": report}
    if provider != "claude":
        report = _blocked_report(
            payload,
            provider=provider,
            reason=f"Unsupported provider: {provider}",
            model=model,
            allow_external_model=allow_external_model,
            allow_claude_tools=allow_claude_tools,
            max_budget_usd=max_budget_usd,
            timeout_seconds=timeout_seconds,
        )
        return {"schema_version": 1, "status": "blocked", "agent": payload, "model_run": report}

    prompt = _agent_model_prompt(payload, tool_policy)
    command = _claude_command(
        prompt=prompt,
        model=model,
        max_budget_usd=max_budget_usd,
        claude_command=claude_command,
        tool_policy=tool_policy,
    )
    try:
        completed = command_runner(command, text=True, capture_output=True, timeout=timeout_seconds, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        report = _blocked_report(
            payload,
            provider=provider,
            reason=f"Could not run provider command: {exc}",
            model=model,
            allow_external_model=allow_external_model,
            allow_claude_tools=allow_claude_tools,
            max_budget_usd=max_budget_usd,
            timeout_seconds=timeout_seconds,
        )
        report["timeout_seconds"] = timeout_seconds
        _write_json(Path(payload["output_dir"]) / MODEL_RUN_REPORT_JSON, report)
        return {"schema_version": 1, "status": "blocked", "agent": payload, "model_run": report}

    answer, provider_metadata = _extract_provider_answer(completed.stdout or "")
    answer_path = Path(payload["ai_output_dir"]) / "ANSWER.md"
    provider_error = bool(provider_metadata.get("is_error"))
    provider_ok = completed.returncode == 0 and not provider_error and bool(answer)
    answer_contract = (
        _answer_contract(answer, tool_policy=tool_policy)
        if provider_ok
        else {"accepted": False, "limitations": ["Provider did not produce a successful answer."], "permission_request_detected": False}
    )
    if provider_ok:
        if answer_contract["accepted"]:
            answer_path.write_text(
                _compose_runner_answer(
                    payload=payload,
                    provider=provider,
                    model=model,
                    provider_answer=answer,
                    provider_metadata=provider_metadata,
                    exit_code=completed.returncode,
                    tool_policy=tool_policy,
                ),
                encoding="utf-8",
            )
        else:
            answer_path.write_text(
                _rejected_answer_text(
                    provider=provider,
                    completed_returncode=completed.returncode,
                    provider_metadata=provider_metadata,
                    answer=answer,
                    limitations=answer_contract["limitations"],
                ),
                encoding="utf-8",
            )
    else:
        blocked_reason = "Provider subprocess did not produce a verified task answer."
        permission_request = _permission_request(
            provider=provider,
            model=model,
            reason=blocked_reason,
            output_dir=payload["output_dir"],
            allow_external_model=allow_external_model,
            allow_claude_tools=allow_claude_tools,
            max_budget_usd=max_budget_usd,
            timeout_seconds=timeout_seconds,
            provider_metadata=provider_metadata,
        )
        answer_path.write_text(
            "Answer:\n"
            "BLOCKED. The external model provider did not produce a verified answer.\n\n"
            "Evidence:\n"
            f"Provider `{provider}` was invoked and returned exit code {completed.returncode}.\n"
            f"Provider metadata: {json.dumps(provider_metadata, sort_keys=True)}\n"
            f"Provider stdout excerpt: {_short_text(completed.stdout or '', 500)}\n\n"
            "Limitations:\n"
            "No task answer was generated by the provider. Fix provider authentication/configuration, then rerun.\n\n"
            f"{_permission_request_text(permission_request)}\n"
            "Files changed or created:\n"
            "ANSWER.md, MODEL_RUN_REPORT.json\n\n"
            "Tests or checks run:\n"
            "Provider subprocess attempted; Nkama evidence manifest checked.\n",
            encoding="utf-8",
        )

    evidence_report = verify_manifest(payload["evidence_manifest"])
    if provider_ok and answer_contract["accepted"]:
        answer_path.write_text(
            _compose_runner_answer(
                payload=payload,
                provider=provider,
                model=model,
                    provider_answer=answer,
                    provider_metadata=provider_metadata,
                    exit_code=completed.returncode,
                    tool_policy=tool_policy,
                    evidence_summary=evidence_report["summary"],
                ),
                encoding="utf-8",
            )
        evidence_report = verify_manifest(payload["evidence_manifest"])
    if not provider_ok:
        model_status = "blocked"
    elif answer_contract.get("permission_request_detected") and tool_policy.get("tool_mode") == "claude_scoped_tools":
        model_status = "blocked"
    elif not answer_contract["accepted"]:
        model_status = "fail"
    elif evidence_report["summary"]["fail"] == 0 and evidence_report["summary"]["blocked"] == 0:
        model_status = "pass"
    else:
        model_status = "fail"
    report = {
        "schema_version": 1,
        "status": model_status,
        "provider": provider,
        "model": model,
        "model_call": "run",
        "command": [part if index < len(command) - 1 else "<prompt omitted>" for index, part in enumerate(command)],
        "exit_code": completed.returncode,
        "timeout_seconds": timeout_seconds,
        "tool_policy": tool_policy,
        "provider_metadata": provider_metadata,
        "answer_contract": answer_contract,
        "stdout_excerpt": _short_text(completed.stdout or ""),
        "stderr_excerpt": _short_text(completed.stderr or ""),
        "answer": str(answer_path),
        "evidence_manifest": payload["evidence_manifest"],
        "evidence_summary": evidence_report["summary"],
        "permission_request": _permission_request(
            provider=provider,
            model=model,
            reason="Provider call was blocked/failed, failed the answer contract, or generated output did not satisfy the evidence manifest.",
            output_dir=payload["output_dir"],
            allow_external_model=allow_external_model,
            allow_claude_tools=allow_claude_tools,
            max_budget_usd=max_budget_usd,
            timeout_seconds=timeout_seconds,
            provider_metadata=provider_metadata,
        )
        if model_status != "pass"
        else None,
        "limitations": []
        if model_status == "pass"
        else answer_contract.get("limitations", [])
        + [
            "Provider call was blocked/failed, failed the answer contract, or generated output did not satisfy the evidence manifest.",
        ],
    }
    _write_json(Path(payload["output_dir"]) / MODEL_RUN_REPORT_JSON, report)
    return {"schema_version": 1, "status": model_status, "agent": payload, "model_run": report, "evidence_report": evidence_report}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Print or prepare the Nkama Fact Benchmark protocol for AI agents.")
    parser.add_argument("task", nargs="?", help="Task the AI agent should complete under the protocol.")
    parser.add_argument("--file", help="Read task text from a file.")
    parser.add_argument("--output", help="Output directory for the agent run package.")
    parser.add_argument("--title", default="Nkama Agent Run")
    parser.add_argument("--mode", choices=["strict", "compact"], default="strict")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser


def build_run_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run an AI provider under the Nkama Fact Benchmark agent protocol.")
    parser.add_argument("task", nargs="?", help="Task the AI provider should complete.")
    parser.add_argument("--file", help="Read task text from a file.")
    parser.add_argument("--output", help="Output directory for the agent run package.")
    parser.add_argument("--provider", choices=["claude"], default="claude")
    parser.add_argument("--model", default=DEFAULT_CLAUDE_MODEL)
    parser.add_argument("--max-budget-usd")
    parser.add_argument("--claude-command", default="claude")
    parser.add_argument("--allow-external-model", action="store_true")
    parser.add_argument("--allow-claude-tools", action="store_true", help="Allow scoped Claude tools for this run.")
    parser.add_argument("--allowed-dir", action="append", default=[], help="Additional directory Claude may access when --allow-claude-tools is used.")
    parser.add_argument("--allow-command", action="append", default=[], help="Allowed Bash command pattern for Claude, e.g. 'python3 -m pytest *'.")
    parser.add_argument("--allowed-browser-mcp-tools", default=DEFAULT_BROWSER_MCP_TOOLS)
    parser.add_argument("--permission-mode", choices=["default", "auto", "acceptEdits", "plan", "dontAsk"], default=None)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--title", default="Nkama Agent Run")
    parser.add_argument("--mode", choices=["strict", "compact"], default="strict")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser


def run_cli(args: argparse.Namespace) -> dict[str, Any] | str:
    task = _read_task(args).strip()
    if not task:
        protocol = render_agent_protocol()
        print(protocol)
        return protocol
    payload = create_agent_package(
        task=task,
        output_dir=args.output,
        title=args.title,
        mode=args.mode,
        overwrite=args.overwrite,
    )
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(render_agent_protocol(payload))
    return payload


def run_model_cli(args: argparse.Namespace) -> dict[str, Any]:
    task = _read_task(args).strip()
    if not task:
        raise SystemExit("Provide a task argument or --file path.")
    payload = run_agent_model(
        task=task,
        output_dir=args.output,
        provider=args.provider,
        model=args.model,
        max_budget_usd=args.max_budget_usd,
        claude_command=args.claude_command,
        allow_external_model=args.allow_external_model,
        allow_claude_tools=args.allow_claude_tools,
        allowed_dirs=args.allowed_dir,
        allowed_commands=args.allow_command,
        allowed_browser_mcp_tools=args.allowed_browser_mcp_tools,
        permission_mode=args.permission_mode,
        timeout_seconds=args.timeout_seconds,
        title=args.title,
        mode=args.mode,
        overwrite=args.overwrite,
    )
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        agent = payload["agent"]
        model_run = payload["model_run"]
        print(
            "\nNkama Fact Benchmark agent-run complete.\n\n"
            f"Status: {payload['status']}\n"
            f"Output folder: {agent['output_dir']}\n"
            f"Answer: {model_run['answer']}\n"
            f"Model run report: {Path(agent['output_dir']) / MODEL_RUN_REPORT_JSON}\n"
            f"Evidence manifest: {agent['evidence_manifest']}\n"
            f"Evidence summary: {model_run.get('evidence_summary', {})}\n"
        )
        permission_request = model_run.get("permission_request")
        if payload["status"] == "blocked" and permission_request:
            print(_permission_request_text(permission_request))
    return payload


def main() -> None:
    run_cli(build_parser().parse_args())


if __name__ == "__main__":
    main()
