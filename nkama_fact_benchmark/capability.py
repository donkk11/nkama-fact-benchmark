from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .evidence_layer import verify_manifest
from .workflow import create_run_package, slugify


CAPABILITY_REPORT_JSON = "CAPABILITY_REPORT.json"
AGENT_PROTOCOL_MD = "AGENT_PROTOCOL.md"
SESSION_STATE_MD = "NKAMA_SESSION_STATE.md"
ENVIRONMENT_MATRIX_JSON = "environment_matrix.json"
ENVIRONMENT_MATRIX_MD = "environment_matrix.md"

CLI_TOOLS = (
    "python3",
    "pip",
    "pip3",
    "uv",
    "uvx",
    "node",
    "npm",
    "npx",
    "bun",
    "deno",
    "git",
    "curl",
    "wget",
)

NETWORK_TARGETS = (
    "https://pypi.org",
    "https://files.pythonhosted.org",
    "https://github.com",
    "https://raw.githubusercontent.com",
    "https://npmjs.com",
    "https://google.com",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_output_dir() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return Path(f"nkama_capability_{stamp}_{uuid.uuid4().hex[:8]}")


def _file_info(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {"path": str(path), "size_bytes": stat.st_size, "modified_epoch": int(stat.st_mtime)}


def _check(id_: str, name: str, status: str, evidence: list[dict[str, Any]] | None = None, limitation: str = "") -> dict[str, Any]:
    return {
        "id": id_,
        "name": name,
        "status": status,
        "evidence": evidence or [],
        "limitation": limitation,
    }


def _excerpt(value: str, limit: int = 700) -> str:
    return value.strip()[:limit]


def _command_label(command: list[str]) -> str:
    return " ".join(command)


def _write_read_check(path: Path, text: str, *, expected: str | None = None) -> dict[str, Any]:
    expected = expected if expected is not None else text
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        read_back = path.read_text(encoding="utf-8")
    except OSError as exc:
        return _check(
            "file_write_read",
            f"Write and read {path.name}",
            "blocked",
            evidence=[{"kind": "path", "path": str(path)}],
            limitation=f"Could not write/read file: {exc}",
        )
    matched = read_back == expected
    return _check(
        "file_write_read",
        f"Write and read {path.name}",
        "pass" if matched else "fail",
        evidence=[{"kind": "file", **_file_info(path)}, {"kind": "read_back_match", "matched": matched}],
        limitation="" if matched else "Read-back content did not match written content.",
    )


def _tool_version_check(tool: str) -> dict[str, Any]:
    path = shutil.which(tool)
    if not path:
        return _check(
            f"tool_{tool}",
            f"CLI tool available: {tool}",
            "blocked",
            evidence=[{"kind": "command_lookup", "command": tool, "resolved_path": None}],
            limitation=f"{tool} is not installed or not on PATH.",
        )
    command = [tool, "--version"]
    try:
        completed = subprocess.run(command, text=True, capture_output=True, timeout=8, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return _check(
            f"tool_{tool}",
            f"CLI tool available: {tool}",
            "blocked",
            evidence=[{"kind": "command_lookup", "command": tool, "resolved_path": path}, {"kind": "subprocess_attempt", "command": command}],
            limitation=f"{tool} was found, but its version command could not run: {exc}",
        )
    output = _excerpt(completed.stdout or completed.stderr)
    passed = completed.returncode == 0 and bool(output)
    return _check(
        f"tool_{tool}",
        f"CLI tool available: {tool}",
        "pass" if passed else "fail",
        evidence=[
            {"kind": "command_lookup", "command": tool, "resolved_path": path},
            {
                "kind": "subprocess",
                "command": command,
                "exit_code": completed.returncode,
                "stdout_excerpt": _excerpt(completed.stdout),
                "stderr_excerpt": _excerpt(completed.stderr),
                "version_output": output,
            },
        ],
        limitation="" if passed else f"{tool} was found, but `{_command_label(command)}` did not return usable version output.",
    )


def _python_module_check(module: str, args: list[str], *, name: str, root: Path) -> dict[str, Any]:
    command = [sys.executable, "-m", module, *args]
    try:
        completed = subprocess.run(command, cwd=str(root), text=True, capture_output=True, timeout=20, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return _check(
            f"python_module_{module.replace('.', '_')}",
            name,
            "blocked",
            evidence=[{"kind": "subprocess_attempt", "command": command, "cwd": str(root)}],
            limitation=f"Could not run `{_command_label(command)}`: {exc}",
        )
    output = _excerpt(completed.stdout or completed.stderr)
    passed = completed.returncode == 0 and bool(output)
    return _check(
        f"python_module_{module.replace('.', '_')}",
        name,
        "pass" if passed else "blocked",
        evidence=[
            {
                "kind": "subprocess",
                "command": command,
                "cwd": str(root),
                "exit_code": completed.returncode,
                "stdout_excerpt": _excerpt(completed.stdout),
                "stderr_excerpt": _excerpt(completed.stderr),
                "output": output,
            }
        ],
        limitation="" if passed else f"`{_command_label(command)}` could not run successfully in this environment.",
    )


def _python_venv_creation_check(root: Path) -> dict[str, Any]:
    venv_dir = root / "tool_probe" / "venv_check"
    command = [sys.executable, "-m", "venv", str(venv_dir)]
    try:
        completed = subprocess.run(command, cwd=str(root), text=True, capture_output=True, timeout=40, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return _check(
            "python_module_venv_create",
            "Create a Python virtual environment",
            "blocked",
            evidence=[{"kind": "subprocess_attempt", "command": command, "cwd": str(root)}],
            limitation=f"Could not run `{_command_label(command)}`: {exc}",
        )
    created = venv_dir.exists()
    passed = completed.returncode == 0 and created
    return _check(
        "python_module_venv_create",
        "Create a Python virtual environment",
        "pass" if passed else "blocked",
        evidence=[
            {
                "kind": "subprocess",
                "command": command,
                "cwd": str(root),
                "exit_code": completed.returncode,
                "stdout_excerpt": _excerpt(completed.stdout),
                "stderr_excerpt": _excerpt(completed.stderr),
            },
            {"kind": "path_probe", "path": str(venv_dir), "exists": created},
        ],
        limitation="" if passed else "Python venv creation failed or the venv folder was not created.",
    )


def _network_check(url: str) -> dict[str, Any]:
    curl_path = shutil.which("curl")
    safe_id = (
        url.replace("https://", "")
        .replace("http://", "")
        .replace(".", "_")
        .replace("/", "_")
        .replace("-", "_")
    )
    if curl_path:
        command = ["curl", "-sS", "-L", "-I", "--max-time", "8", url]
        try:
            completed = subprocess.run(command, text=True, capture_output=True, timeout=12, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return _check(
                f"network_{safe_id}",
                f"Network target reachable: {url}",
                "blocked",
                evidence=[{"kind": "subprocess_attempt", "command": command}],
                limitation=f"Could not run curl network probe: {exc}",
            )
        headers = completed.stdout
        status_line = next((line.strip() for line in headers.splitlines() if line.startswith("HTTP/")), "")
        http_status = None
        if status_line:
            parts = status_line.split()
            if len(parts) >= 2 and parts[1].isdigit():
                http_status = int(parts[1])
        passed = completed.returncode == 0 and http_status is not None and 200 <= http_status < 400
        limitation = ""
        if not passed:
            if http_status == 403 or "403" in completed.stderr or "403" in completed.stdout:
                limitation = "Network probe reached a blocking response, commonly a sandbox egress allowlist/proxy denial."
            elif completed.returncode != 0:
                limitation = "Network probe could not complete from this sandbox."
            else:
                limitation = f"Network probe returned HTTP status {http_status}."
        return _check(
            f"network_{safe_id}",
            f"Network target reachable: {url}",
            "pass" if passed else "blocked",
            evidence=[
                {
                    "kind": "network_probe",
                    "tool": "curl",
                    "tool_path": curl_path,
                    "command": command,
                    "exit_code": completed.returncode,
                    "http_status": http_status,
                    "status_line": status_line,
                    "stdout_excerpt": _excerpt(completed.stdout),
                    "stderr_excerpt": _excerpt(completed.stderr),
                }
            ],
            limitation=limitation,
        )

    # Last-resort probe for Python-only environments. This still uses real network access.
    command = [sys.executable, "-c", "import urllib.request,sys; r=urllib.request.urlopen(sys.argv[1], timeout=8); print(r.status)", url]
    try:
        completed = subprocess.run(command, text=True, capture_output=True, timeout=12, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return _check(
            f"network_{safe_id}",
            f"Network target reachable: {url}",
            "blocked",
            evidence=[{"kind": "subprocess_attempt", "command": command}],
            limitation=f"Could not run Python network probe: {exc}",
        )
    output = _excerpt(completed.stdout or completed.stderr)
    passed = completed.returncode == 0 and output.isdigit() and 200 <= int(output) < 400
    return _check(
        f"network_{safe_id}",
        f"Network target reachable: {url}",
        "pass" if passed else "blocked",
        evidence=[
            {
                "kind": "network_probe",
                "tool": "python_urllib",
                "command": command,
                "exit_code": completed.returncode,
                "output": output,
            }
        ],
        limitation="" if passed else "Python network probe could not reach this target from the current sandbox.",
    )


def _python_subprocess_check(root: Path) -> dict[str, Any]:
    command = [sys.executable, "-c", "print('nkama-python-ok')"]
    try:
        completed = subprocess.run(command, cwd=str(root), text=True, capture_output=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return _check(
            "python_subprocess",
            "Run a small Python subprocess",
            "blocked",
            evidence=[{"kind": "subprocess_attempt", "command": command, "cwd": str(root)}],
            limitation=f"Could not run Python subprocess: {exc}",
        )
    passed = completed.returncode == 0 and "nkama-python-ok" in completed.stdout
    return _check(
        "python_subprocess",
        "Run a small Python subprocess",
        "pass" if passed else "fail",
        evidence=[
            {
                "kind": "subprocess",
                "command": command,
                "cwd": str(root),
                "exit_code": completed.returncode,
                "stdout_excerpt": completed.stdout.strip()[:300],
                "stderr_excerpt": completed.stderr.strip()[:300],
            }
        ],
        limitation="" if passed else "Python subprocess did not return the expected output.",
    )


def _manifest(root: Path, *, deep: bool = False) -> dict[str, Any]:
    checks = [
        {"id": "agent_protocol_exists", "type": "file_contains", "path": AGENT_PROTOCOL_MD, "text": "Nkama Capability Test"},
        {"id": "session_state_exists", "type": "file_contains", "path": SESSION_STATE_MD, "text": "Protocol: Nkama Fact Benchmark active"},
        {"id": "storage_probe_exists", "type": "file_contains", "path": "storage_probe/read_write_check.md", "text": "updated"},
        {"id": "nested_probe_exists", "type": "file_contains", "path": "storage_probe/nested/nested_check.md", "text": "nested folder"},
        {"id": "answer_file_exists", "type": "file_contains", "path": "ai_output/ANSWER.md", "text": "Capability test"},
        {"id": "capability_summary_exists", "type": "file_contains", "path": "ai_output/capability_summary.md", "text": "Capability Summary"},
    ]
    if deep:
        checks.extend(
            [
                {"id": "environment_matrix_json_exists", "type": "file_contains", "path": f"ai_output/{ENVIRONMENT_MATRIX_JSON}", "text": "network_targets"},
                {"id": "environment_matrix_md_exists", "type": "file_contains", "path": f"ai_output/{ENVIRONMENT_MATRIX_MD}", "text": "Environment Matrix"},
            ]
        )
    return {
        "schema_version": 1,
        "root": str(root),
        "allowed_command_prefixes": [],
        "checks": checks,
    }


def _answer_text(report: dict[str, Any]) -> str:
    summary = report["summary"]
    evidence_lines = [
        f"- Output folder: `{report['output_dir']}`",
        f"- Checks run: {summary['checks_run']}",
        f"- Passed: {summary['pass']}",
        f"- Failed: {summary['fail']}",
        f"- Blocked: {summary['blocked']}",
        f"- Evidence report: `{report['evidence_manifest']}`",
        f"- Capability report: `{report['capability_report']}`",
    ]
    created_files = [
        "`AGENT_PROTOCOL.md`",
        "`NKAMA_SESSION_STATE.md`",
        "`storage_probe/read_write_check.md`",
        "`storage_probe/nested/nested_check.md`",
        "`ai_output/ANSWER.md`",
        "`ai_output/capability_summary.md`",
        "`ai_output/evidence_manifest.json`",
        "`CAPABILITY_REPORT.json`",
    ]
    checks_run = [
        "Markdown file write/read probe",
        "Session-state update/read-back probe",
        "Nested folder creation probe",
        "Python subprocess probe",
        "Nkama evidence manifest verification",
    ]
    if report.get("deep"):
        evidence_lines.extend(
            [
                f"- Environment matrix: `{Path(report['output_dir']) / 'ai_output' / ENVIRONMENT_MATRIX_JSON}`",
                f"- Human-readable matrix: `{Path(report['output_dir']) / 'ai_output' / ENVIRONMENT_MATRIX_MD}`",
            ]
        )
        created_files.extend([f"`ai_output/{ENVIRONMENT_MATRIX_JSON}`", f"`ai_output/{ENVIRONMENT_MATRIX_MD}`"])
        checks_run.extend(["CLI tool availability/version probes", "Python venv/pip module probes", "Network reachability probes"])
    return (
        "Answer:\n"
        "Capability test completed for the environment where this command ran.\n\n"
        "Evidence:\n"
        + "\n".join(evidence_lines)
        + "\n\n"
        "Limitations:\n"
        "This proves only the current environment. If this command is run inside ChatGPT, Grok, Gemini, Claude, Codex, or another AI sandbox, it proves that sandbox only. It does not prove another computer or another AI session has the same storage/tools.\n\n"
        "Files changed or created:\n"
        + "\n".join(f"- {item}" for item in created_files)
        + "\n\n"
        "Tests or checks run:\n"
        + "\n".join(f"- {item}" for item in checks_run)
        + "\n"
    )


def _status_counts(checks: list[dict[str, Any]]) -> dict[str, Any]:
    summary = {
        "checks_run": len(checks),
        "pass": sum(1 for item in checks if item["status"] == "pass"),
        "fail": sum(1 for item in checks if item["status"] == "fail"),
        "blocked": sum(1 for item in checks if item["status"] == "blocked"),
    }
    summary["passed_all_unblocked"] = summary["fail"] == 0
    return summary


def _evidence_value(check: dict[str, Any], key: str, default: Any = None) -> Any:
    for item in check.get("evidence", []):
        if key in item:
            return item[key]
    return default


def _environment_matrix(checks: list[dict[str, Any]]) -> dict[str, Any]:
    cli_rows = []
    python_rows = []
    network_rows = []
    for check in checks:
        if check["id"].startswith("tool_"):
            cli_rows.append(
                {
                    "tool": check["id"].replace("tool_", "", 1),
                    "status": check["status"],
                    "path": _evidence_value(check, "resolved_path"),
                    "version_output": _evidence_value(check, "version_output", ""),
                    "limitation": check.get("limitation", ""),
                }
            )
        elif check["id"].startswith("python_module_"):
            python_rows.append(
                {
                    "name": check["name"],
                    "status": check["status"],
                    "output": _evidence_value(check, "output", ""),
                    "limitation": check.get("limitation", ""),
                }
            )
        elif check["id"].startswith("network_"):
            url = check["name"].replace("Network target reachable: ", "", 1)
            network_rows.append(
                {
                    "url": url,
                    "status": check["status"],
                    "http_status": _evidence_value(check, "http_status"),
                    "status_line": _evidence_value(check, "status_line", ""),
                    "limitation": check.get("limitation", ""),
                }
            )
    tool_status = {row["tool"]: row["status"] for row in cli_rows}
    network_status = {row["url"]: row["status"] for row in network_rows}
    can_fetch_pypi = network_status.get("https://pypi.org") == "pass" and network_status.get("https://files.pythonhosted.org") == "pass"
    derived_modes = {
        "can_run_uvx_command_if_package_already_available": tool_status.get("uvx") == "pass",
        "can_fetch_python_packages_from_pypi": can_fetch_pypi,
        "can_run_uvx_package_from_pypi": tool_status.get("uvx") == "pass" and can_fetch_pypi,
        "can_run_npx_if_package_already_available": tool_status.get("npx") == "pass",
        "can_fetch_from_github": network_status.get("https://github.com") == "pass"
        and network_status.get("https://raw.githubusercontent.com") == "pass",
        "can_fetch_from_npmjs": network_status.get("https://npmjs.com") == "pass",
        "internet_or_proxy_blocks_detected": any(row["status"] == "blocked" for row in network_rows),
    }
    return {
        "schema_version": 1,
        "generated_at": utc_now(),
        "principle": "fact_verified_only",
        "cli_tools": cli_rows,
        "python_modules": python_rows,
        "network_targets": network_rows,
        "derived_modes": derived_modes,
        "interpretation": [
            "If uvx is present but PyPI/Pythonhosted are blocked, this sandbox can run uvx but cannot fetch nkama-fact-benchmark from PyPI.",
            "If uvx is missing, use protocol/prompt mode or ask the AI environment to install/provide uvx.",
            "If file and Python probes pass, Nkama can still create local evidence files even when public package fetching is blocked.",
        ],
    }


def _render_environment_matrix_md(matrix: dict[str, Any]) -> str:
    lines = [
        "# Environment Matrix",
        "",
        "This file records what the current AI/terminal sandbox can actually run or reach.",
        "",
        "## Derived Modes",
        "",
    ]
    for key, value in matrix["derived_modes"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## CLI Tools", "", "| Tool | Status | Path | Version / Limitation |", "|---|---:|---|---|"])
    for row in matrix["cli_tools"]:
        detail = row["version_output"] or row["limitation"]
        lines.append(f"| `{row['tool']}` | {row['status'].upper()} | {row['path'] or ''} | {detail} |")
    lines.extend(["", "## Python Module Probes", "", "| Probe | Status | Output / Limitation |", "|---|---:|---|"])
    for row in matrix["python_modules"]:
        detail = row["output"] or row["limitation"]
        lines.append(f"| {row['name']} | {row['status'].upper()} | {detail} |")
    lines.extend(["", "## Network Targets", "", "| URL | Status | HTTP | Limitation |", "|---|---:|---:|---|"])
    for row in matrix["network_targets"]:
        lines.append(f"| {row['url']} | {row['status'].upper()} | {row['http_status'] or ''} | {row['limitation']} |")
    lines.extend(
        [
            "",
            "## Reading The Result",
            "",
            "- `PASS` means the capability was observed in this environment.",
            "- `BLOCKED` means the capability was unavailable or denied here; it is not proof the package, website, or tool does not exist.",
            "- `FAIL` means something ran but returned an unexpected result.",
            "",
        ]
    )
    return "\n".join(lines)


def run_capability_test(*, output_dir: str | Path | None = None, overwrite: bool = False, deep: bool = False) -> dict[str, Any]:
    output_path = Path(output_dir).expanduser() if output_dir else _default_output_dir()
    prompt = "Nkama capability test: prove sandbox file storage, Markdown state, folder creation, Python subprocess, and evidence verification."
    if deep:
        prompt += " Deep mode also probes CLI tools, Python modules, and network/package-registry reachability."
    package = create_run_package(
        prompt=prompt,
        output_dir=output_path,
        title="Nkama Capability Test",
        overwrite=overwrite,
    )
    root = Path(package["output_dir"])
    ai_output = Path(package["ai_output_dir"])
    checks: list[dict[str, Any]] = []

    protocol_text = (
        "# Nkama Capability Test Agent Protocol\n\n"
        "Nkama Capability Test verifies what this current environment can actually do.\n\n"
        "- Do not claim another AI sandbox has the same capability unless this command ran there.\n"
        "- Treat this file as proof that Markdown storage was created in the current run folder.\n"
        "- Keep evidence separate from assumptions.\n"
    )
    protocol_check = _write_read_check(root / AGENT_PROTOCOL_MD, protocol_text)
    protocol_check["id"] = "agent_protocol_markdown"
    protocol_check["name"] = "Create AGENT_PROTOCOL.md"
    checks.append(protocol_check)

    state_initial = (
        "Protocol: Nkama Fact Benchmark active\n"
        "Task: capability-test\n"
        "Mode: inspect\n"
        "Files created: pending\n"
        "Checks run: pending\n"
        "Open limitations: current environment only\n"
    )
    state_path = root / SESSION_STATE_MD
    state_check = _write_read_check(state_path, state_initial)
    state_check["id"] = "session_state_markdown"
    state_check["name"] = "Create NKAMA_SESSION_STATE.md"
    checks.append(state_check)

    try:
        updated_state = state_initial.replace("Files created: pending", "Files created: AGENT_PROTOCOL.md, NKAMA_SESSION_STATE.md, storage probes")
        updated_state = updated_state.replace("Checks run: pending", "Checks run: file write/read, nested folder, Python subprocess, manifest verification")
        state_path.write_text(updated_state, encoding="utf-8")
        read_back = state_path.read_text(encoding="utf-8")
        matched = "storage probes" in read_back and "manifest verification" in read_back
        checks.append(
            _check(
                "session_state_update",
                "Update and reread NKAMA_SESSION_STATE.md",
                "pass" if matched else "fail",
                evidence=[{"kind": "file", **_file_info(state_path)}, {"kind": "read_back_contains_update", "matched": matched}],
                limitation="" if matched else "Updated session-state markers were not found after reread.",
            )
        )
    except OSError as exc:
        checks.append(
            _check(
                "session_state_update",
                "Update and reread NKAMA_SESSION_STATE.md",
                "blocked",
                evidence=[{"kind": "path", "path": str(state_path)}],
                limitation=f"Could not update/read session state: {exc}",
            )
        )

    storage_text = "# Nkama Storage Probe\n\nStatus: created then updated.\n"
    probe = _write_read_check(root / "storage_probe" / "read_write_check.md", storage_text, expected=storage_text)
    probe["id"] = "markdown_storage_probe"
    probe["name"] = "Create and read Markdown storage probe"
    checks.append(probe)
    try:
        probe_path = root / "storage_probe" / "read_write_check.md"
        probe_path.write_text(storage_text + "\nRead-back: updated\n", encoding="utf-8")
        read_back = probe_path.read_text(encoding="utf-8")
        matched = "updated" in read_back
        checks.append(
            _check(
                "markdown_storage_update",
                "Update and reread Markdown storage probe",
                "pass" if matched else "fail",
                evidence=[{"kind": "file", **_file_info(probe_path)}, {"kind": "read_back_contains_update", "matched": matched}],
                limitation="" if matched else "Updated storage probe marker was not found after reread.",
            )
        )
    except OSError as exc:
        checks.append(
            _check(
                "markdown_storage_update",
                "Update and reread Markdown storage probe",
                "blocked",
                evidence=[{"kind": "path", "path": str(root / "storage_probe" / "read_write_check.md")}],
                limitation=f"Could not update/read storage probe: {exc}",
            )
        )

    nested_text = "# Nested Folder Probe\n\nThis proves nested folder creation in the current environment.\n"
    nested = _write_read_check(root / "storage_probe" / "nested" / "nested_check.md", nested_text)
    nested["id"] = "nested_folder_probe"
    nested["name"] = "Create nested folder and Markdown file"
    checks.append(nested)

    checks.append(_python_subprocess_check(root))

    environment_matrix = None
    if deep:
        for tool in CLI_TOOLS:
            checks.append(_tool_version_check(tool))
        checks.append(_python_venv_creation_check(root))
        checks.append(_python_module_check("pip", ["--version"], name="Run python -m pip", root=root))
        for url in NETWORK_TARGETS:
            checks.append(_network_check(url))
        environment_matrix = _environment_matrix(checks)
        (ai_output / ENVIRONMENT_MATRIX_JSON).write_text(json.dumps(environment_matrix, indent=2), encoding="utf-8")
        (ai_output / ENVIRONMENT_MATRIX_MD).write_text(_render_environment_matrix_md(environment_matrix), encoding="utf-8")

    manifest_path = ai_output / "evidence_manifest.json"
    manifest_path.write_text(json.dumps(_manifest(root, deep=deep), indent=2), encoding="utf-8")
    report_skeleton = {
        "schema_version": 1,
        "run_id": f"capability_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}",
        "generated_at": utc_now(),
        "principle": "fact_verified_only",
        "deep": deep,
        "output_dir": str(root),
        "capability_report": str(root / CAPABILITY_REPORT_JSON),
        "evidence_manifest": str(manifest_path),
        "environment": {
            "python_executable": sys.executable,
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
            "cwd": str(Path.cwd()),
        },
        "checks": checks,
    }
    if environment_matrix:
        report_skeleton["environment_matrix"] = str(ai_output / ENVIRONMENT_MATRIX_JSON)
        report_skeleton["environment_matrix_markdown"] = str(ai_output / ENVIRONMENT_MATRIX_MD)
        report_skeleton["derived_modes"] = environment_matrix["derived_modes"]
    report_skeleton["summary"] = _status_counts(checks)

    capability_summary = (
        "# Capability Summary\n\n"
        "This file was written inside the environment that ran `nkama-fact-benchmark capability-test`.\n\n"
        "## What Was Proved\n\n"
        "- Markdown files can be created and read back.\n"
        "- `NKAMA_SESSION_STATE.md` can be created, updated, and read back.\n"
        "- Nested folders can be created.\n"
        "- A small Python subprocess can run if the subprocess check passed.\n"
        "- `nkama-evidence-layer` can verify the generated manifest.\n\n"
        + (
            "## Deep Mode Matrix\n\n"
            f"- Machine-readable matrix: `{ENVIRONMENT_MATRIX_JSON}`\n"
            f"- Human-readable matrix: `{ENVIRONMENT_MATRIX_MD}`\n"
            "- This separates installed tools from network/package-registry access.\n\n"
            if deep
            else ""
        )
        + "## Limitation\n\n"
        "This result proves only this current environment. Other AI sandboxes must run their own capability test.\n"
    )
    (ai_output / "capability_summary.md").write_text(capability_summary, encoding="utf-8")
    (ai_output / "ANSWER.md").write_text(_answer_text(report_skeleton), encoding="utf-8")
    evidence_report = verify_manifest(manifest_path)
    report_skeleton["evidence_report"] = evidence_report
    report_skeleton["summary"]["evidence_manifest_pass"] = evidence_report["summary"]["fail"] == 0 and evidence_report["summary"]["blocked"] == 0
    (root / CAPABILITY_REPORT_JSON).write_text(json.dumps(report_skeleton, indent=2), encoding="utf-8")
    return report_skeleton


def render_capability_report(report: dict[str, Any]) -> str:
    summary = report["summary"]
    if summary["fail"] > 0:
        status = "fail"
    elif summary["blocked"] > 0:
        status = "complete_with_blocked_capabilities"
    else:
        status = "pass"
    created_files = [
        f"- {AGENT_PROTOCOL_MD}",
        f"- {SESSION_STATE_MD}",
        "- storage_probe/read_write_check.md",
        "- storage_probe/nested/nested_check.md",
        "- ai_output/ANSWER.md",
        "- ai_output/capability_summary.md",
    ]
    if report.get("deep"):
        created_files.extend([f"- ai_output/{ENVIRONMENT_MATRIX_JSON}", f"- ai_output/{ENVIRONMENT_MATRIX_MD}"])
    return (
        "\nNkama capability-test complete.\n\n"
        f"Output folder: {report['output_dir']}\n"
        f"Status: {status}\n"
        f"Checks: {summary['checks_run']} run, {summary['pass']} pass, {summary['fail']} fail, {summary['blocked']} blocked\n"
        f"Capability report: {report['capability_report']}\n"
        f"Evidence manifest: {report['evidence_manifest']}\n\n"
        "Created proof files:\n"
        + "\n".join(created_files)
        + "\n\n"
        "Important: this proves only the environment where the command ran. Run it inside each AI sandbox to test that AI's storage/tools.\n"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Test what the current AI/terminal sandbox can actually do.")
    parser.add_argument("--output", help="Output directory. Defaults to a timestamped nkama_capability_* folder.")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--deep", action="store_true", help="Also probe CLI tools, Python modules, and network/package-registry reachability.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser


def run_cli(args: argparse.Namespace) -> dict[str, Any]:
    report = run_capability_test(output_dir=args.output, overwrite=args.overwrite, deep=args.deep)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(render_capability_report(report))
    return report


def main() -> None:
    run_cli(build_parser().parse_args())


if __name__ == "__main__":
    main()
