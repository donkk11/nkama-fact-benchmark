"""The Nkama Voice, made mechanical.

Generates NKAMA_STORY.md — the plain-language companion to a run's real
evidence. Never edits ANSWER.md or evidence_manifest.json; only reads them.
The rules this module follows are written out in full in NKAMA_VOICE.md at
the repo root — read that before changing this file.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

from .evidence_layer import verify_manifest


def _find_manifest(target: Path) -> Path:
    if target.is_file():
        return target
    candidates = [
        target / "ai_output" / "evidence_manifest.json",
        target / "evidence_manifest.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise SystemExit(
        f"No evidence_manifest.json found under {target}. "
        "Point --at a run folder or the manifest file directly."
    )


_PATH_NOISE = re.compile(r"`?/[A-Za-z0-9_./-]{6,}`?")
_BRANCH_PAREN = re.compile(r"\s*\((?:branch|commit)\b[^)]*\)")
_CLONE_BOILERPLATE = re.compile(
    r"\bend to end in the\b.*?\bworking clone at\b\s*", re.IGNORECASE | re.DOTALL
)
_ROUND_DRAMA = re.compile(
    r"Round\s*1\b[:\s]*(.+?)\.\s*Round\s*2\b[:\s]*(.+?)\.",
    re.IGNORECASE | re.DOTALL,
)


def _clean_sentence(raw: str) -> str:
    """Strip file paths, branch/commit asides, and clone boilerplate a human
    reader doesn't need in a headline — keep the substance, drop the scaffolding."""
    text = _CLONE_BOILERPLATE.sub("", raw)
    text = _BRANCH_PAREN.sub("", text)
    text = _PATH_NOISE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([.,;:])", r"\1", text)  # no space before trailing punctuation
    return text


def _eyebrow_title(text: str) -> str | None:
    match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    return match.group(1).strip() if match else None


def _round_drama_hook(text: str) -> str | None:
    """If the answer already narrates a reject-then-confirm arc (an adversarial
    verifier's round 1 / round 2), that's the strongest hook available and it's
    real — just extract it instead of falling back to a flat first sentence."""
    match = _ROUND_DRAMA.search(text)
    if not match:
        return None
    round1 = _clean_sentence(match.group(1))
    round2 = _clean_sentence(match.group(2))
    if not round1 or not round2:
        return None
    return (
        f"An independent AI verifier didn't take this on faith. "
        f"Round 1: {round1}. Round 2: {round2}."
    )


def _answer_hook(manifest_path: Path) -> str | None:
    answer = manifest_path.parent / "ANSWER.md"
    if not answer.exists():
        return None
    text = answer.read_text(encoding="utf-8")

    drama = _round_drama_hook(text)
    if drama:
        return drama

    # "Answer:" paragraphs wrap across lines until the next blank line — capture
    # the whole paragraph, not just its first line.
    match = re.search(r"^Answer:\s*(.+?)(?:\n\s*\n|\Z)", text, re.MULTILINE | re.DOTALL)
    if match:
        cleaned = _clean_sentence(match.group(1))
        if cleaned:
            return cleaned
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), None)
    return first_line


def _failure_lines(report: dict[str, Any]) -> list[str]:
    lines = []
    for check in report.get("checks", []):
        if check.get("status") in ("fail", "blocked"):
            name = check.get("name", check.get("id", "a check"))
            limitations = check.get("limitations") or []
            reason = limitations[0] if limitations else check.get("status")
            lines.append(f"- **{name}** — {reason}")
    return lines


def build_story(manifest_path: Path, *, allow_commands: bool = False) -> str:
    report = verify_manifest(manifest_path, allow_commands=allow_commands)
    summary = report["summary"]
    hook = _answer_hook(manifest_path)
    failures = _failure_lines(report)
    # Real bug, found by an adversarial audit: the fail==0/blocked==0
    # fallback re-introduced the empty-manifest hole if clean_pass were ever
    # missing from a report. verify_manifest always sets it now — trust that.
    clean = summary.get("clean_pass", False)

    answer_file = manifest_path.parent / "ANSWER.md"
    eyebrow = _eyebrow_title(answer_file.read_text(encoding="utf-8")) if answer_file.exists() else None

    lines: list[str] = []
    if eyebrow:
        lines.append(f"*{eyebrow}*")
        lines.append("")
    if hook:
        lines.append(f"# {hook}")
    else:
        lines.append("# A claim, checked against real evidence")
    lines.append("")

    if clean:
        lines.append(
            f"Every claim in this run was checked, not just stated. "
            f"**{summary['pass']} of {summary['checks_run']} checks passed**, "
            f"nothing blocked, nothing skipped."
        )
    else:
        lines.append(
            f"Not everything here passed — and that's on purpose. "
            f"{summary['pass']} of {summary['checks_run']} checks passed; "
            f"{summary['fail']} failed and {summary['blocked']} were blocked. "
            f"A story that hid that wouldn't be worth trusting."
        )
    lines.append("")

    if failures:
        lines.append("## What didn't hold up")
        lines.extend(failures)
        lines.append("")

    lines.append("## The receipt")
    lines.append(
        f"This isn't asking you to take my word for it. Re-run it yourself:"
    )
    lines.append("")
    lines.append("```bash")
    lines.append(
        f"uvx --from nkama-fact-benchmark nkama-evidence-layer {manifest_path} --allow-commands"
    )
    lines.append("```")
    lines.append("")
    lines.append(
        f"Real evidence: `{manifest_path}`. "
        f"Verdict: **{'clean_pass' if clean else 'not clean — see above'}**."
    )
    lines.append("")
    lines.append("*Written by the Nkama Voice — see NKAMA_VOICE.md for the rules it follows.*")
    return "\n".join(lines)


def run_cli(args: argparse.Namespace) -> None:
    target = Path(args.at).expanduser().resolve()
    manifest_path = _find_manifest(target)
    story = build_story(manifest_path, allow_commands=args.allow_commands)
    out_path = manifest_path.parent.parent / "NKAMA_STORY.md" if manifest_path.parent.name == "ai_output" else manifest_path.parent / "NKAMA_STORY.md"
    out_path.write_text(story, encoding="utf-8")
    print(story)
    print(f"\n[written to {out_path}]")
