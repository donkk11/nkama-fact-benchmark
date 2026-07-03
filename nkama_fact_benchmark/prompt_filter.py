from __future__ import annotations

import argparse
import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROMPT_ANALYSIS_JSON = "prompt_analysis.json"
ORIGINAL_PROMPT_MD = "original_prompt.md"
EVIDENCE_PROMPT_MD = "evidence_prompt.md"
PREPARED_PROMPT_MD = "prepared_prompt.md"
TOOL_PLAN_JSON = "tool_plan.json"
PACKAGE_README_MD = "README.md"


@dataclass
class PromptCheck:
    id: str
    name: str
    status: str
    evidence: list[dict[str, Any]] = field(default_factory=list)
    limitation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "evidence": self.evidence,
            "limitation": self.limitation,
        }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip().lower()).strip("-")
    return slug or f"prompt-{uuid.uuid4().hex[:8]}"


def _count_matches(text: str, pattern: str) -> int:
    return len(re.findall(pattern, text, flags=re.IGNORECASE | re.MULTILINE))


def analyze_prompt(prompt: str) -> dict[str, Any]:
    stripped = prompt.strip()
    checks = [
        PromptCheck(
            id="non_empty",
            name="Prompt is not empty",
            status="pass" if stripped else "fail",
            evidence=[{"kind": "length", "characters": len(stripped)}],
            limitation="" if stripped else "Prompt is empty, so no AI task can be evaluated.",
        ),
        PromptCheck(
            id="deliverable",
            name="Prompt asks for a concrete deliverable",
            status="pass"
            if _count_matches(prompt, r"\b(build|create|write|generate|produce|return|output|fix|test|verify|compare)\b")
            else "warn",
            evidence=[
                {
                    "kind": "keyword_scan",
                    "matches": _count_matches(
                        prompt, r"\b(build|create|write|generate|produce|return|output|fix|test|verify|compare)\b"
                    ),
                }
            ],
            limitation="" if _count_matches(prompt, r"\b(build|create|write|generate|produce|return|output|fix|test|verify|compare)\b") else "No clear deliverable verb found.",
        ),
        PromptCheck(
            id="evidence_request",
            name="Prompt asks for evidence or verification",
            status="pass"
            if _count_matches(prompt, r"\b(evidence|verify|verified|test|tests|run|assert|source|cite|citation|screenshot|log)\b")
            else "warn",
            evidence=[
                {
                    "kind": "keyword_scan",
                    "matches": _count_matches(
                        prompt, r"\b(evidence|verify|verified|test|tests|run|assert|source|cite|citation|screenshot|log)\b"
                    ),
                }
            ],
            limitation="" if _count_matches(prompt, r"\b(evidence|verify|verified|test|tests|run|assert|source|cite|citation|screenshot|log)\b") else "Prompt does not require evidence, tests, citations, logs, or verified output.",
        ),
        PromptCheck(
            id="external_claim_risk",
            name="Prompt may require current or external facts",
            status="warn"
            if _count_matches(prompt, r"\b(latest|today|current|price|law|legal|medical|financial|news|CEO|president|API docs?)\b")
            else "pass",
            evidence=[
                {
                    "kind": "risk_keyword_scan",
                    "matches": _count_matches(
                        prompt, r"\b(latest|today|current|price|law|legal|medical|financial|news|CEO|president|API docs?)\b"
                    ),
                }
            ],
            limitation="Prompt appears to need current/external verification." if _count_matches(prompt, r"\b(latest|today|current|price|law|legal|medical|financial|news|CEO|president|API docs?)\b") else "",
        ),
        PromptCheck(
            id="permission_risk",
            name="Prompt avoids unsafe permission language",
            status="warn"
            if _count_matches(prompt, r"\b(dangerously-skip-permissions|bypass|unlimited|full filesystem|delete everything|reset --hard)\b")
            else "pass",
            evidence=[
                {
                    "kind": "risk_keyword_scan",
                    "matches": _count_matches(
                        prompt, r"\b(dangerously-skip-permissions|bypass|unlimited|full filesystem|delete everything|reset --hard)\b"
                    ),
                }
            ],
            limitation="Prompt contains broad permission language. Keep it explicit and opt-in." if _count_matches(prompt, r"\b(dangerously-skip-permissions|bypass|unlimited|full filesystem|delete everything|reset --hard)\b") else "",
        ),
    ]
    rows = [check.to_dict() for check in checks]
    summary = {
        "pass": sum(1 for check in rows if check["status"] == "pass"),
        "warn": sum(1 for check in rows if check["status"] == "warn"),
        "fail": sum(1 for check in rows if check["status"] == "fail"),
    }
    readiness = "not_ready" if summary["fail"] else "needs_evidence_rules" if summary["warn"] else "evidence_ready"
    return {
        "schema_version": 1,
        "generated_at": utc_now(),
        "principle": "fact_verified_only",
        "readiness": readiness,
        "summary": summary,
        "checks": rows,
    }


def _task_profile(prompt: str) -> dict[str, Any]:
    lowered = prompt.lower()
    profiles = {
        "game": ["game", "platformer", "mario", "fighter", "street fighter", "shooter", "3d", "arcade", "level", "sprite"],
        "presentation": ["ppt", "pptx", "slide", "slideshow", "presentation", "deck"],
        "web_app": [
            "website",
            "web app",
            "frontend",
            "front end",
            "interface",
            "chat interface",
            "html",
            "css",
            "javascript",
            "dashboard",
            "browser",
            "ollama",
            "backend",
            "local ai",
        ],
        "python_app": ["python", ".py", "script", "cli", "package", "library"],
        "research": ["research", "sources", "cite", "citation", "latest", "current", "fact"],
        "document": ["write", "report", "lesson plan", "document", "markdown", "essay"],
    }
    matches: dict[str, int] = {}
    for name, terms in profiles.items():
        matches[name] = sum(1 for term in terms if term in lowered)
    primary = max(matches, key=matches.get)
    if matches[primary] == 0:
        primary = "general_build"
    return {"primary": primary, "matches": matches}


def _tool_plan(prompt: str) -> dict[str, Any]:
    profile = _task_profile(prompt)
    primary = profile["primary"]
    base = {
        "schema_version": 1,
        "task_profile": profile,
        "preflight_command": "uvx --no-cache --from nkama-fact-benchmark nkama-fact-benchmark capability-test --deep",
        "preflight_fallback_command": "uvx --no-cache --from nkama-fact-benchmark nkama-fact-benchmark capability-test",
        "always_check": [
            "Can this AI run terminal commands?",
            "Can it write/read files in its sandbox?",
            "Can it run Python or Node?",
            "Can it fetch packages from PyPI/npm/GitHub?",
            "Can it render or screenshot the output?",
        ],
        "evidence_outputs": ["ANSWER.md", "evidence_manifest.json", "tests/logs/screenshots when available"],
        "artifact_proof_checks": [
            "Verify the final user-facing artifact through its native route, not only through helper scripts, fallback previews, or file listings.",
            "For code or CLI work, run the actual command, import, tests, or help path that a user would use.",
            "For browser or visual work, open or serve the real entry point and record browser/page errors when tools exist.",
            "For documents, slides, PDFs, or data files, read back, parse, render, or inspect the generated artifact in its real format when tools exist.",
            "For research or factual work, connect each load-bearing claim to sources or mark it unverified.",
            "If native verification is unavailable, mark that proof path BLOCKED instead of treating fallback output as success.",
        ],
        "browser_render_checks": [],
    }
    routes = {
        "game": {
            "deliverables": [
                "Playable game files, preferably openable from the sandbox or downloadable as a project folder.",
                "Multiple stages or clear level progression when the environment can support it.",
                "Player, enemy, scoring, health/state, collision, and win/lose mechanics.",
                "A test or smoke-check log that proves the main loop and controls were checked.",
                "An evidence report that says what was verified, what was not, and why.",
            ],
            "phases": [
                "Define the game contract: genre, controls, mechanics, win/lose states, level count, and visual ambition.",
                "Audit available rendering and asset tools before choosing 2D, 3D, or procedural fallback.",
                "Build the core loop and controls first, then add enemies, stages, scoring, and polish.",
                "Run a browser/file smoke check and screenshot/render check when available.",
                "Fix observed defects, update the evidence manifest, and write the final report.",
            ],
            "preferred_tools": ["HTML/CSS/JavaScript Canvas", "Three.js for 3D", "Playwright or browser screenshot checks", "local asset generation when available"],
            "fallback_tools": ["2D Canvas if 3D tooling is unavailable", "procedural placeholder assets if image generation is unavailable", "keyboard-only smoke tests if browser automation is unavailable"],
            "quality_checks": [
                "game loop runs",
                "player controls respond",
                "collisions work",
                "level progression exists",
                "actual browser render of index.html is nonblank when a browser tool exists",
                "browser console/page errors are checked when a browser tool exists",
                "no copyrighted assets unless user provides rights",
            ],
            "browser_render_checks": [
                "Serve or open the real `index.html`; do not rely only on a fallback renderer or isolated game-core screenshot.",
                "Capture browser console/page errors and save them to `ai_output/browser_render_log.md` or an equivalent log.",
                "Capture a screenshot from the actual browser page when a browser tool exists, and verify the canvas/page is nonblank.",
                "If fallback-rendered screenshots are used, label them as fallback visual evidence, not proof that `index.html` works.",
                "If no browser/screenshot tool exists, mark browser render verification BLOCKED instead of claiming the game is playable.",
            ],
        },
        "presentation": {
            "deliverables": [
                "A finished presentation file when slide tooling exists, otherwise a structured slide deck in Markdown or HTML.",
                "Speaker notes or teacher notes when useful for the audience.",
                "A source map showing which facts or inputs support each section.",
                "A readability and layout check, including render/read-back when possible.",
                "An evidence report that identifies sources, assumptions, and unverified items.",
            ],
            "phases": [
                "Extract source material and identify the audience, level, and intended outcome.",
                "Create a slide architecture before drafting visual content.",
                "Generate the deck or fallback deck format.",
                "Render, read back, or inspect the deck for missing text and layout problems.",
                "Write the evidence report and mark unsupported claims clearly.",
            ],
            "preferred_tools": ["python-pptx or document tool", "PDF/image render for visual QA", "source document parser when files are attached"],
            "fallback_tools": ["Markdown slide outline if PPTX tooling is unavailable", "HTML deck if presentation libraries are unavailable"],
            "quality_checks": ["slide count", "titles and body fit", "source facts cited", "rendered preview checked"],
        },
        "web_app": {
            "deliverables": [
                "Working app files with a clear entry point.",
                "The primary user workflow implemented, not only described.",
                "Responsive layout behavior for desktop and mobile where relevant.",
                "Test, smoke-check, or browser inspection output.",
                "An evidence report listing files, checks, and limitations.",
            ],
            "phases": [
                "Turn the request into a product contract and data/UI model.",
                "Build the simplest complete workflow first.",
                "Add interaction states, error states, and responsive styling.",
                "Run browser, DOM, or file checks and fix observed issues.",
                "Update the manifest and final report.",
            ],
            "preferred_tools": ["HTML/CSS/JavaScript", "Node test runner when available", "browser screenshot or DOM smoke test"],
            "fallback_tools": ["single-file HTML app", "manual DOM/file checks if browser automation is blocked"],
            "quality_checks": [
                "app opens",
                "primary workflow works",
                "responsive layout",
                "actual browser render is nonblank when a browser tool exists",
                "console errors checked when possible",
            ],
            "browser_render_checks": [
                "Serve or open the real app entry point; do not rely only on static file presence.",
                "Capture browser console/page errors and save them to `ai_output/browser_render_log.md` or an equivalent log.",
                "Capture a screenshot from the actual browser page when a browser tool exists, and verify it is nonblank.",
                "If no browser/screenshot tool exists, mark browser render verification BLOCKED instead of claiming the app works visually.",
            ],
        },
        "python_app": {
            "deliverables": [
                "Python source files with a clear interface.",
                "CLI or API usage instructions when applicable.",
                "Unit tests or executable assertions.",
                "Edge-case coverage for empty, invalid, and boundary inputs.",
                "An evidence report with exact commands and results.",
            ],
            "phases": [
                "Define the interface and expected behavior.",
                "Implement with standard library or available dependencies.",
                "Add focused tests before broad polish.",
                "Run tests and fix failures.",
                "Document usage, evidence, and known limitations.",
            ],
            "preferred_tools": ["Python standard library", "unittest/pytest if available", "type/lint checks when configured"],
            "fallback_tools": ["unittest instead of pytest", "doctest or simple assertions if no test framework exists"],
            "quality_checks": ["unit tests pass", "edge cases covered", "CLI help works if applicable"],
        },
        "research": {
            "deliverables": [
                "A direct answer or report with claim-level evidence.",
                "A source list with dates, URLs, and authority notes when browsing is available.",
                "A claim-evidence table separating verified facts from inference.",
                "Uncertainty notes for unavailable or unstable claims.",
                "An evidence report stating what was sourced, verified, or blocked.",
            ],
            "phases": [
                "Decompose the question into checkable claims.",
                "Search current authoritative sources when browsing is available.",
                "Cross-check load-bearing claims against at least one suitable source.",
                "Separate fact, inference, and opinion.",
                "Write the final report with citations and limitations.",
            ],
            "preferred_tools": ["browser/search tools", "official or primary sources", "citation list"],
            "fallback_tools": ["mark current/external claims unverified if browsing is unavailable"],
            "quality_checks": ["sources cited", "dates included", "claims separated from inference"],
        },
        "document": {
            "deliverables": [
                "A finished document in the requested format or a clear fallback format.",
                "A structure map showing sections, audience, and purpose.",
                "Source/assumption notes for factual or attached-file content.",
                "A read-back, render, or file-existence check when possible.",
                "An evidence report that avoids claiming unavailable verification.",
            ],
            "phases": [
                "Clarify audience, objective, tone, and constraints.",
                "Extract or organize source material.",
                "Create the document structure before drafting.",
                "Draft, review, and check the file/readability.",
                "Report evidence and limitations.",
            ],
            "preferred_tools": ["Markdown/docx generation", "source file extraction if attachments exist", "render/read-back checks"],
            "fallback_tools": ["Markdown draft if document tooling is unavailable"],
            "quality_checks": ["audience fit", "structure complete", "no unsupported claims", "files saved and readable"],
        },
        "general_build": {
            "deliverables": [
                "Named deliverables that match the user's real goal.",
                "A design or implementation artifact, depending on available tools.",
                "A verification plan tied to actual files, commands, or sources.",
                "An evidence report with pass, fail, or blocked states.",
            ],
            "phases": [
                "Define the scope and success conditions.",
                "Audit available tools and permissions.",
                "Build or design the highest-value artifact the environment supports.",
                "Verify with actual checks where possible.",
                "Report results without overclaiming.",
            ],
            "preferred_tools": ["available terminal/file tools", "language/framework tools already present in sandbox"],
            "fallback_tools": ["design-only package if execution tools are unavailable"],
            "quality_checks": ["deliverables named", "assumptions listed", "evidence checks defined"],
        },
    }
    base.update(routes[primary])
    return base


def _markdown_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _numbered_list(items: list[str]) -> str:
    return "\n".join(f"{index}. {item}" for index, item in enumerate(items, start=1))


def _json_block(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2)


def prepare_execution_prompt(prompt: str, *, mode: str = "strict") -> str:
    analysis = analyze_prompt(prompt)
    plan = _tool_plan(prompt)
    preferred = _markdown_list(plan["preferred_tools"])
    fallback = _markdown_list(plan["fallback_tools"])
    deliverables = _markdown_list(plan["deliverables"])
    phases = _numbered_list(plan["phases"])
    checks = _markdown_list(plan["quality_checks"])
    artifact_proof_section = (
        "## Universal Artifact Proof\n\n"
        "A generated helper preview, fallback renderer, static file listing, isolated core test, or friendly final sentence is not enough to prove a build works. "
        "For every kind of task, verify the actual artifact through the path a real user would use.\n\n"
        f"{_markdown_list(plan['artifact_proof_checks'])}\n\n"
    )
    browser_render_section = ""
    if plan["browser_render_checks"]:
        browser_render_section = (
            "## Browser Render Proof\n\n"
            "For browser games, web apps, Canvas projects, and HTML interfaces, screenshots from fallback renderers or isolated state renderers are not enough. "
            "They may prove that data can be drawn somewhere, but they do not prove that the real `index.html` or app entry point works in a browser.\n\n"
            f"{_markdown_list(plan['browser_render_checks'])}\n\n"
        )
    global_checks = _markdown_list(
        [
            "The final answer matches the original user task, not a smaller invented task.",
            "The result is not merely a plan unless the environment cannot build.",
            "Every blocked tool, file, source, test, or permission is named plainly.",
            "No copyrighted/protected assets are copied unless the user supplied rights or asked for an original alternative.",
            "No current or external factual claim is treated as verified without a source or tool result.",
            "The final report separates built, verified, unverified, failed, and blocked work.",
        ]
    )
    evidence_manifest = {
        "schema_version": 1,
        "root": "ai_output",
        "checks": [
            {"id": "answer_file_exists", "type": "file_exists", "path": "ANSWER.md"},
            {"id": "answer_mentions_evidence", "type": "file_contains", "path": "ANSWER.md", "text": "Evidence"},
            {"id": "main_artifact_exists", "type": "file_exists", "path": "REPLACE_WITH_MAIN_ARTIFACT"},
            {"id": "test_or_smoke_log_exists", "type": "file_exists", "path": "test_log.md"},
            {"id": "artifact_proof_log_exists", "type": "file_exists", "path": "artifact_proof_log.md"},
        ],
    }
    if plan["browser_render_checks"]:
        evidence_manifest["checks"].extend(
            [
                {"id": "browser_render_log_exists", "type": "file_exists", "path": "browser_render_log.md"},
                {"id": "browser_render_mentions_no_page_errors", "type": "file_contains", "path": "browser_render_log.md", "text": "page errors"},
                {"id": "browser_screenshot_exists", "type": "file_exists", "path": "screenshots/browser_render.png"},
            ]
        )
    compact_note = ""
    if mode == "compact":
        compact_note = "\nCompact mode: keep the build small enough to complete in one pass, then list what was intentionally left out.\n"
    return (
        "# Nkama Prepared Execution Prompt\n\n"
        "Use this as the second prompt after Nkama has prepared the task. Treat it as a professional execution contract, not a decoration. "
        "The goal is to produce the strongest result the current AI sandbox can honestly support, while proving what was actually done.\n\n"
        "## Original User Task\n\n"
        f"{prompt.strip()}\n\n"
        "## 1. Executive Interpretation\n\n"
        "Before building, convert the user's rough request into a clear mission. Identify the audience, the real deliverable, the expected quality level, "
        "the likely hidden requirements, and the evidence needed to prove completion. Do not rush into building. The first job is to remove ambiguity without wasting context.\n\n"
        "## 2. Deliverable Map\n\n"
        f"{deliverables}\n\n"
        "## 3. Capability Preflight\n\n"
        "If terminal access is available, run this command first and use the result to choose tools:\n\n"
        "```bash\n"
        f"{plan['preflight_command']}\n"
        "```\n\n"
        "If that command fails because `--deep` is not supported by the installed public version, run this fallback instead:\n\n"
        "```bash\n"
        f"{plan['preflight_fallback_command']}\n"
        "```\n\n"
        "If the Nkama package cannot be fetched, run direct local probes when shell access exists:\n\n"
        "```bash\n"
        "python3 --version\n"
        "node --version\n"
        "npm --version\n"
        "npx --version\n"
        "git --version\n"
        "```\n\n"
        "If none of these can run, do not pretend. State exactly which part is blocked: no terminal, missing `uvx`, blocked PyPI/network, missing file storage, no browser, no screenshots, or no permission. "
        "Then continue only with the best available fallback.\n\n"
        "## 4. Tool Route\n\n"
        "Preferred tools:\n\n"
        f"{preferred}\n\n"
        "Fallback Route if tools are missing:\n\n"
        f"{fallback}\n\n"
        f"{artifact_proof_section}"
        f"{browser_render_section}"
        "## 5. Assumption And Risk Register\n\n"
        "| Item | What to do |\n"
        "|---|---|\n"
        "| Missing requirements | Make conservative assumptions, list them, and proceed unless the missing detail changes the whole task. |\n"
        "| Missing tools | Use the fallback route and mark the unsupported part BLOCKED. |\n"
        "| Large build scope | Build a complete vertical slice first, then extend if context and tools allow. |\n"
        "| Current/external facts | Browse/cite authoritative sources or mark the claim unverified. |\n"
        "| Generated files | Save them in `ai_output/` or the requested project folder and verify they exist. |\n"
        "| Tests/screenshots | Run them only when the environment supports them; otherwise report the limitation. |\n\n"
        "## 6. Implementation Phases\n\n"
        f"{phases}\n\n"
        "## 7. Required Project Structure\n\n"
        "When file storage exists, create or update this structure:\n\n"
        "```text\n"
        "ai_output/\n"
        "  ANSWER.md\n"
        "  evidence_manifest.json\n"
        "  build_log.md\n"
        "  test_log.md\n"
        "  artifact_proof_log.md\n"
        "  screenshots/ or previews/ when available\n"
        "  generated project/document files...\n"
        "```\n\n"
        "If file storage is unavailable, produce the same structure as clearly labeled text blocks and mark file creation BLOCKED.\n\n"
        "## 8. Evidence Manifest Starter\n\n"
        "Use this as a starter only. Replace placeholder paths with real files that actually exist:\n\n"
        "```json\n"
        f"{_json_block(evidence_manifest)}\n"
        "```\n\n"
        "## 9. Acceptance Criteria\n\n"
        f"{checks}\n"
        f"{global_checks}\n\n"
        "## 10. Build Contract\n\n"
        "1. Restate the task as clear deliverables.\n"
        "2. Run the capability preflight when tools exist.\n"
        "3. Choose the strongest realistic build route from the actual environment evidence.\n"
        "4. Ask at most three essential questions only if the task cannot safely continue; otherwise proceed with stated assumptions.\n"
        "5. Build the result in files when file storage is available.\n"
        "6. Create or update `ai_output/ANSWER.md` with the useful human-facing result.\n"
        "7. Create or update `ai_output/evidence_manifest.json` with checks for files and tests that actually exist.\n"
        "8. Run relevant tests/checks when execution is available.\n"
        "9. If a required tool is unavailable, mark that part BLOCKED and use the fallback route.\n"
        "10. Never claim screenshots, tests, browsing, package installs, external model calls, or file creation unless actually performed.\n"
        f"{compact_note}\n"
        "## 11. Failure Modes To Avoid\n\n"
        "- Do not turn the task into only a design document if the sandbox can actually build.\n"
        "- Do not call a package install, browser render, screenshot, or test successful unless it truly ran.\n"
        "- Do not hide blocked evidence inside friendly wording.\n"
        "- Do not spend the whole context on explanation before producing the artifact.\n"
        "- Do not use vague phrases like 'fully working' without naming the checks that support it.\n\n"
        "## 12. Required Final Report\n\n"
        "Answer:\n"
        "Evidence:\n"
        "Limitations:\n"
        "Files changed or created:\n"
        "Tests or checks run:\n"
        "Next best improvement:\n\n"
        "## Nkama Analysis Snapshot\n\n"
        f"- Readiness: `{analysis['readiness']}`\n"
        f"- Prompt checks: {analysis['summary']['pass']} pass, {analysis['summary']['warn']} warn, {analysis['summary']['fail']} fail\n"
        f"- Task profile: `{plan['task_profile']['primary']}`\n"
    )


def wrap_prompt(prompt: str, *, mode: str = "strict") -> str:
    rules = [
        "Do not begin building until the task, available tools, and evidence route are clear.",
        "Do not claim file access, code execution, browsing, database writes, screenshots, or tests unless actually performed.",
        "If a tool can verify a claim, use the tool or mark the claim as unverified.",
        "For code, run relevant tests when execution is available and report the exact command/result.",
        "For current or external facts, cite current authoritative sources or mark the answer unverified.",
        "For generated files, include an `evidence_manifest.json` when possible so `nkama-evidence-layer` can verify the output.",
        "If evidence is unavailable, mark the result BLOCKED instead of pretending it passed.",
        "If sandbox file storage is available, keep `NKAMA_SESSION_STATE.md` updated with the active task, files, checks, and limitations.",
    ]
    if mode == "compact":
        rules = rules[:4]
    numbered_rules = "\n".join(f"{index}. {rule}" for index, rule in enumerate(rules, start=1))
    return (
        "# Nkama Fact Benchmark Prompt Wrapper\n\n"
        "You are being evaluated by an evidence-gated checker. Complete the user task, but make the result verifiable.\n\n"
        "## Evidence Rules\n\n"
        f"{numbered_rules}\n\n"
        "## Required Output Structure\n\n"
        "When file creation is available, create or update this structure:\n\n"
        "```text\n"
        "ai_output/\n"
        "  ANSWER.md\n"
        "  evidence_manifest.json\n"
        "  generated files for the task...\n"
        "```\n\n"
        "`ANSWER.md` should be useful to a human, but it must not overclaim. `evidence_manifest.json` should check the actual files and tests.\n\n"
        "## Required Final Report\n\n"
        "Return a concise final report with these exact fields:\n\n"
        "- Answer\n"
        "- Evidence\n"
        "- Limitations\n"
        "- Files changed, if any\n"
        "- Tests or checks run, if any\n\n"
        "If you only produced a plan or design document, say that plainly in Limitations.\n\n"
        "## User Task\n\n"
        f"{prompt.strip()}\n"
    )


def write_prompt_package(*, prompt: str, output_dir: str | Path, title: str = "Nkama Prompt Check", mode: str = "strict") -> dict[str, Any]:
    output_path = Path(output_dir).expanduser().resolve()
    output_path.mkdir(parents=True, exist_ok=True)
    analysis = analyze_prompt(prompt)
    tool_plan = _tool_plan(prompt)
    (output_path / ORIGINAL_PROMPT_MD).write_text(prompt.strip() + "\n", encoding="utf-8")
    (output_path / EVIDENCE_PROMPT_MD).write_text(wrap_prompt(prompt, mode=mode), encoding="utf-8")
    (output_path / PREPARED_PROMPT_MD).write_text(prepare_execution_prompt(prompt, mode=mode), encoding="utf-8")
    (output_path / PROMPT_ANALYSIS_JSON).write_text(json.dumps(analysis, indent=2), encoding="utf-8")
    (output_path / TOOL_PLAN_JSON).write_text(json.dumps(tool_plan, indent=2), encoding="utf-8")
    (output_path / PACKAGE_README_MD).write_text(
        "# Nkama Prompt Package\n\n"
        f"Title: {title}\n\n"
        "Use `prepared_prompt.md` when you want Nkama to turn the original request into a stronger execution prompt before the AI starts building. "
        "Use `evidence_prompt.md` when you want a shorter evidence-gated wrapper.\n\n"
        "After the AI produces files or an answer, verify the output with `nkama-evidence-layer` or compare submissions with `nkama-truth-filter`.\n",
        encoding="utf-8",
    )
    return {
        "schema_version": 1,
        "title": title,
        "output_dir": str(output_path),
        "readiness": analysis["readiness"],
        "analysis": str(output_path / PROMPT_ANALYSIS_JSON),
        "original_prompt": str(output_path / ORIGINAL_PROMPT_MD),
        "evidence_prompt": str(output_path / EVIDENCE_PROMPT_MD),
        "prepared_prompt": str(output_path / PREPARED_PROMPT_MD),
        "tool_plan": str(output_path / TOOL_PLAN_JSON),
        "readme": str(output_path / PACKAGE_README_MD),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Wrap any AI prompt with evidence-gated verification rules.")
    parser.add_argument("prompt", nargs="?", help="Prompt text to wrap.")
    parser.add_argument("--file", help="Read prompt text from a file.")
    parser.add_argument("--output", help="Write a prompt package to this directory.")
    parser.add_argument("--title", default="Nkama Prompt Check")
    parser.add_argument("--mode", choices=["strict", "compact"], default="strict")
    parser.add_argument("--prepare", action="store_true", help="Print the stronger second prompt instead of the shorter evidence wrapper.")
    parser.add_argument("--json", action="store_true", help="Print JSON prompt analysis instead of prompt text.")
    return parser


def _read_prompt(args: argparse.Namespace) -> str:
    if args.file:
        return Path(args.file).expanduser().read_text(encoding="utf-8")
    if args.prompt:
        return args.prompt
    raise SystemExit("Provide a prompt argument or --file path.")


def run_cli(args: argparse.Namespace) -> dict[str, Any] | str:
    prompt = _read_prompt(args)
    if args.output:
        payload = write_prompt_package(prompt=prompt, output_dir=args.output, title=args.title, mode=args.mode)
        print(json.dumps(payload, indent=2))
        return payload
    if args.json:
        payload = analyze_prompt(prompt)
        print(json.dumps(payload, indent=2))
        return payload
    wrapped = prepare_execution_prompt(prompt, mode=args.mode) if args.prepare else wrap_prompt(prompt, mode=args.mode)
    print(wrapped)
    return wrapped


def main() -> None:
    run_cli(build_parser().parse_args())


if __name__ == "__main__":
    main()
