"""Claim-check: is a real GitHub issue actually unclaimed before building against it.

Built after a real incident (2026-08-08): before recommending dolthub/dolt#11397 as safe
to build against, only the issue's open/closed state was checked — not linked PRs. A
maintainer had already opened a fix in a *different* repo (the actual bug lived in a
dependency, go-mysql-server, not the repo the issue was filed in) 15+ hours earlier.
Checking "is this issue open" is not the same claim as "is this issue unclaimed", and
this tool exists because that distinction was skipped in person, from memory, and memory
alone is not a reliable enough gate for a check this cheap to make automatic.

This is the same lesson twice now (first on aquasecurity/trivy#10976, human-caught; then
on dolthub/dolt#11397, human-caught again) — which is exactly why it belongs in the tool,
not in a memory file that has to be remembered correctly every single time.

Like every other check in this package: this never says "safe." It says what it actually
checked, and what it found, or BLOCKED if a signal genuinely couldn't be checked. A
CONTESTED or BLOCKED verdict means read it yourself before building anything. A CLEAR
verdict means only what was actually checked came back clean — it is not a guarantee
nothing was missed, especially across repos this tool wasn't told to look at.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from typing import Any

CLAIM_PATTERNS = [
    r"\bI(?:'m| am) (?:working on|taking|fixing|handling) this\b",
    r"\bI(?:'ll| will) (?:take|fix|handle|work on) this\b",
    r"\b(?:fixes?|closes?|resolves?)\s+#\d+\b",
    r"\bshipped in\b",
    r"\balready (?:fixed|shipped|merged|covered)\b",
    r"\bworking on a (?:fix|PR)\b",
    r"\bopened a PR\b",
    r"\bassign(?:ed|ing)? (?:this )?to me\b",
]


def _run(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return completed.returncode, completed.stdout, completed.stderr
    except (OSError, subprocess.TimeoutExpired) as exc:
        return -1, "", str(exc)


def _check(id_: str, name: str, status: str, evidence: list[dict] | None = None, limitations: list[str] | None = None) -> dict[str, Any]:
    return {
        "id": id_,
        "name": name,
        "status": status,
        "evidence": evidence or [],
        "limitations": limitations or [],
    }


def _scan_claim_language(texts: list[str]) -> list[dict[str, str]]:
    hits = []
    for text in texts:
        for pattern in CLAIM_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                hits.append({"pattern": pattern, "matched_text": match.group(0)})
    return hits


def check_issue_claim(repo: str, issue_number: int, also_check_repos: list[str] | None = None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    also_check_repos = also_check_repos or []

    code, out, err = _run(["gh", "issue", "view", str(issue_number), "--repo", repo, "--json", "state,title,body,comments,assignees,closedByPullRequestsReferences"])
    if code != 0:
        checks.append(_check("issue_fetch", f"Fetch {repo}#{issue_number}", "blocked", limitations=[f"gh issue view failed: {err.strip()[:300]}"]))
        return _report(repo, issue_number, checks)

    issue = json.loads(out)
    # Real bug, found by an adversarial audit: this used to hardcode "pass"
    # regardless of state, so a CLOSED issue with nothing else suspicious
    # returned CLEAR overall — but "closed" isn't proof of "safely unclaimed."
    # It could be closed because someone already fixed it, or closed as
    # wontfix, or a dozen other reasons this tool can't distinguish without
    # a human reading it. A closed issue is the case that most needs a human
    # look, not the case that should sail through silently.
    is_open = issue["state"] == "OPEN"
    checks.append(_check(
        "issue_state", f"{repo}#{issue_number} open/closed state",
        "pass" if is_open else "fail",
        evidence=[{"state": issue["state"], "title": issue["title"]}],
        limitations=(
            ["state alone does not mean unclaimed — see linked-PR and claim-language checks below"]
            if is_open else
            [f"{repo}#{issue_number} is CLOSED — read it yourself before building. A closed issue "
             "commonly means already fixed elsewhere, not safe to build against."]
        ),
    ))

    assignees = issue.get("assignees") or []
    checks.append(_check(
        "assignees", "Formal assignees", "fail" if assignees else "pass",
        evidence=[{"assignees": [a.get("login") for a in assignees]}],
        limitations=[] if not assignees else ["Assigned to someone — do not treat as unclaimed."],
    ))

    comment_texts = [c.get("body", "") for c in issue.get("comments", [])]
    claim_hits = _scan_claim_language([issue.get("body", "")] + comment_texts)
    checks.append(_check(
        "claim_language_in_issue", f"No claim-language found in {repo}#{issue_number} body/comments",
        "fail" if claim_hits else "pass",
        evidence=[{"hits": claim_hits}],
        limitations=[] if not claim_hits else [f"{len(claim_hits)} claim-language match(es) — read the issue yourself before building."],
    ))

    # GitHub's own authoritative signal: PRs that will close this issue when
    # merged (real "Fixes #N" links GitHub itself parsed), not a text search
    # guess. This is the exact signal that was missing on dolthub/dolt#11397
    # — the fix lived in a different repo GitHub still linked correctly here.
    closing_prs = []
    for p in issue.get("closedByPullRequestsReferences", []) or []:
        pr_repo_obj = p.get("repository") or {}
        pr_owner = (pr_repo_obj.get("owner") or {}).get("login", "")
        pr_name = pr_repo_obj.get("name", "")
        closing_prs.append({
            "number": p.get("number"),
            "url": p.get("url"),
            "repo": f"{pr_owner}/{pr_name}" if pr_owner and pr_name else repo,
        })
    checks.append(_check(
        "closing_prs", f"PRs GitHub has linked as closing {repo}#{issue_number}",
        "fail" if closing_prs else "pass",
        evidence=[{"closing_prs": closing_prs}],
        limitations=[] if not closing_prs else [
            f"GitHub has {len(closing_prs)} PR(s) linked to close this issue — read them before building, "
            "even across repos (a linked PR can live outside this issue's own repo)."
        ],
    ))

    for search_repo in [repo] + also_check_repos:
        pr_code, pr_out, pr_err = _run(["gh", "pr", "list", "--repo", search_repo, "--search", str(issue_number), "--state", "all", "--json", "number,title,state,url"])
        if pr_code != 0:
            checks.append(_check(f"linked_prs_{search_repo}", f"Linked PRs in {search_repo}", "blocked", limitations=[f"gh pr list failed: {pr_err.strip()[:300]}"]))
            continue
        prs = json.loads(pr_out)
        # Real bug, found by an adversarial audit: real_hits was computed
        # (a tighter filter — the issue number must appear in the PR's own
        # title or URL, not just somewhere gh's full-text search matched)
        # but never used; the pass/fail decision below used the loose,
        # unfiltered `prs` list instead. Now it actually gates on the
        # tighter signal, with the loose count kept as visible context.
        real_hits = [p for p in prs if str(issue_number) in (p.get("title", "") + " " + p.get("url", ""))]
        checks.append(_check(
            f"linked_prs_{search_repo}", f"Linked PRs in {search_repo} mentioning #{issue_number}",
            "fail" if real_hits else "pass",
            evidence=[{"real_hits": real_hits, "all_search_hits": prs}],
            limitations=[] if not real_hits else [f"{len(real_hits)} PR(s) in {search_repo} directly reference #{issue_number} in their title or URL — read them before building."]
            + ([] if len(prs) == len(real_hits) else [f"{len(prs) - len(real_hits)} additional loose search match(es) in {search_repo} did not directly reference #{issue_number} — probably unrelated, but worth a glance."]),
        ))

        # Real gap this closes: a linked PR was already found to exist above, but
        # its own comment thread was never read — someone could write "already
        # fixed, see my other PR" inside a PR discussion and this tool would
        # miss it entirely. Read every linked PR's real comments, body, and
        # reviews too — a claim can live in any of the three, not just comments.
        scan_targets = {(search_repo, p.get("number")) for p in real_hits if p.get("number") is not None}
        scan_targets |= {(pr["repo"] or search_repo, pr["number"]) for pr in closing_prs if pr.get("number") is not None}
        for scan_repo, pr_number in scan_targets:
            c_code, c_out, c_err = _run([
                "gh", "pr", "view", str(pr_number), "--repo", scan_repo,
                "--json", "comments,reviews,body,title,state,url",
            ])
            check_id = f"linked_pr_comments_{scan_repo}_{pr_number}"
            if c_code != 0:
                checks.append(_check(
                    check_id, f"Comments/body/reviews on {scan_repo}#{pr_number}", "blocked",
                    limitations=[f"gh pr view failed: {c_err.strip()[:300]}"],
                ))
                continue
            pr_detail = json.loads(c_out)
            pr_texts = (
                [pr_detail.get("body", "")]
                + [c.get("body", "") for c in pr_detail.get("comments", [])]
                + [r.get("body", "") for r in pr_detail.get("reviews", [])]
            )
            pr_claim_hits = _scan_claim_language(pr_texts)
            checks.append(_check(
                check_id,
                f"No claim-language found in {scan_repo}#{pr_number}'s body/comments/reviews "
                f"(a linked PR for #{issue_number})",
                "fail" if pr_claim_hits else "pass",
                evidence=[{"pr_state": pr_detail.get("state"), "pr_title": pr_detail.get("title"), "hits": pr_claim_hits}],
                limitations=[] if not pr_claim_hits else [
                    f"{len(pr_claim_hits)} claim-language match(es) inside {scan_repo}#{pr_number}'s "
                    "body, comments, or reviews — read that PR's discussion yourself before building."
                ],
            ))

    return _report(repo, issue_number, checks, also_check_repos)


def _report(repo: str, issue_number: int, checks: list[dict[str, Any]], also_check_repos: list[str] | None = None) -> dict[str, Any]:
    fail = sum(1 for c in checks if c["status"] == "fail")
    blocked = sum(1 for c in checks if c["status"] == "blocked")
    if blocked:
        verdict = "BLOCKED"
    elif fail:
        verdict = "CONTESTED"
    else:
        verdict = "CLEAR"
    return {
        "schema_version": 1,
        "principle": "checked_signals_only_never_a_safety_guarantee",
        "repo": repo,
        "issue_number": issue_number,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "checks": checks,
        "limitations": [
            "Only checked the issue's own repo" + (f" and {also_check_repos}" if also_check_repos else "") + ".",
            "The real bug can live in a dependency repo this tool was not told about (this is exactly what was missed on dolthub/dolt#11397 — the fix belonged in go-mysql-server). Pass --also-check-repo for every dependency repo you can name.",
            "A CLEAR verdict means nothing checked came back positive — it is not proof nobody else is working on it somewhere unlisted.",
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check whether a GitHub issue is actually unclaimed before building a fix.")
    parser.add_argument("repo", help="owner/repo the issue is filed in")
    parser.add_argument("issue_number", type=int)
    parser.add_argument("--also-check-repo", action="append", default=[], dest="also_check_repos", help="Additional repo (owner/repo) to search for linked PRs, e.g. a dependency repo. Repeatable.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    report = check_issue_claim(args.repo, args.issue_number, args.also_check_repos)
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["verdict"] == "CLEAR" else 1)


if __name__ == "__main__":
    main()
