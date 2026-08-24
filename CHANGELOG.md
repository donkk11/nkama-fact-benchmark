# Changelog

## 0.1.31 — 2026-08-24

- New `youtube-transcribe` subcommand: fetches a YouTube video's own real
  official/auto caption track via `yt-dlp` — never an LLM guess at what was
  said — and wraps it in a real nkama evidence-gated run package. Refuses to
  fabricate a transcript when `yt-dlp` or real captions aren't available;
  exits with an honest error instead. Verified end to end before release: a
  real video with real captions produced a genuine transcript with
  `clean_pass: true`; a real video with no captions correctly refused to
  invent one.

## 0.1.30 — 2026-08-19

Two rounds of adversarial third-party audit (Codex and Grok, each instructed to
attack the tool rather than validate it) found real ways this package could
report success without real evidence. Every fix below was reproduced first as a
failing case, then re-verified after the fix.

- **The starter template self-passed.** A freshly created run folder — zero work
  done, placeholder `ANSWER.md` untouched — verified as `clean_pass: true`,
  because the three starter checks only looked for the words "Evidence:" and
  "Limitations:", which the placeholder itself contained. Added a real
  `file_not_contains` check type and a starter check that fails until the
  placeholder text is actually replaced.
- **`clean_pass` now requires `checks_run > 0`.** An empty manifest previously
  certified "nothing checked" as "nothing wrong". Fixed in `evidence_layer`,
  and propagated to every module that had copied the old
  `fail == 0 and blocked == 0` formula instead of reading the field:
  `agent` (the live agent-run grader), `capability`, `truth_filter`,
  `inspector`, `story`, and the selftest summary.
- **CLI exit codes were always 0.** `nkama-evidence-layer`, `inspect`,
  `truth-filter run`, and `selftest` all exited 0 regardless of result, so any
  CI pipeline gating on them never actually gated. All now exit 1 on failure.
- **Malformed checks silently passed.** `file_contains` with an empty/omitted
  `text` matched everything (`"" in x` is always true); `no_forbidden_claims`
  with an empty `forbidden` list found nothing by construction. Both are now
  `blocked`, not `pass`.
- **Bridge verifier bypasses.** `"agrees": "false"` (a JSON string, truthy in
  Python) counted as *confirmed*; a verdict line reading "this is NOT A PASS"
  parsed as PASS via loose substring matching. Now requires a literal JSON
  `true` and an exact `Verdict: PASS|FAIL|BLOCKED` first line. The
  incomplete-review message also now distinguishes "didn't review every check"
  from "reviewed them and disputed some".
- **`claim-check` gaps.** A computed-but-unused tighter PR filter meant the
  loose full-text search decided pass/fail; PR *bodies* and *reviews* were never
  scanned (only comments); and GitHub's own `closedByPullRequestsReferences`
  signal — which correctly links closing PRs across repositories — was unused.
  All three fixed.
- Version desync fixed: README/README_PYPI pinned `0.1.25` while the published
  package was `0.1.29` and `__init__` fell back to `0.1.28`.

## 0.1.28 — 2026-07-08

- Fixed the product's core promise for strangers: added `examples/portable_demo`,
  a self-contained example whose manifest uses ONLY relative paths and verifies
  green on any fresh clone (`nkama-evidence-layer examples/portable_demo/evidence_manifest.json --allow-commands`).
- RECOMMENDED_RUN.md now leads with that portable example; the older field
  results are re-labeled "historical, maintainer-hosted, not fresh-clone
  portable" — honest about their absolute-path manifests.
- Fixed a version desync: `__init__.__version__` now reads the installed
  package version (was pinned at 0.1.26 while releases moved on).
- Added `tests/test_no_absolute_paths.py`: CI guard that fails if examples or
  re-verify docs hardcode local machine paths.
- inspect: strong clean command-evidence now classifies as verified_build even
  when verified files live outside the run folder (false-negative fix).


## 0.1.27 — 2026-07-08

- New `bridge` subcommand: connect two terminal agents with one command — one
  builds under a scoped contract, the other independently verifies and signs a
  verdict, and the harness re-verifies for clean_pass. No MCP server needed.
- Prompt stage now opens with an Intent Contract: the builder must state goal,
  audience, deliverable, definition of done, out-of-scope, and assumptions
  before building; both report formats gain an explicit intent check.
- Bridge verdict/evidence hardening and a new docs/BRIDGE_FLOW.md.

## 0.1.26 — 2026-07-05

- Fixed the reviewed naming/implementation mismatch: summaries now include an
  unambiguous `clean_pass` field (then defined as `fail == 0 AND blocked == 0`;
  tightened in 0.1.30 to also require `checks_run > 0`) alongside
  `passed_all_unblocked` (which keeps its literal meaning: no failures among
  non-blocked checks). Reported in external deep-research review.
- Published `evidence/`: raw logs, manifests, provider run reports, and
  freshly regenerated verification reports for all six README field results,
  answering the review finding that claims lacked published raw evidence.
- Added a standing invitation for third-party replications
  (`evidence/replications/`), including failed ones.

## 0.1.26 — unreleased

- Added `pilot-harness` for publication-style Nkama research design:
  Phase A 3-task SWE-bench Verified smoke test, Phase B 20-task pilot,
  Phase C 100-task publication run, and Phase D FEVER/TruthfulQA
  negative-control report.
- The harness creates fixed condition folders (`baseline_plain`,
  `decomposition_only`, `nkama_protocol`), task slots, condition protocols,
  result schemas, preflight reports, and a starter evidence manifest.
- SWE-bench execution is honestly marked blocked when local prerequisites such
  as Docker or official dataset instance IDs are unavailable.

## 0.1.25 — 2026-07-05

- Public maintainer contact now lives in SECURITY.md (repository level),
  fixing the reviewed inconsistency where SECURITY.md pointed at metadata
  that exposed no email. Package artifacts intentionally remain email-free:
  the release security audit's no_private_text rule rejected an attempt to
  embed the address in package metadata — the gate applies to its own
  maintainer, and repo-level contact is the compliant path.
- New `docs/MANIFEST_QUALITY.md`: evidence strength ladder, anti-gaming
  patterns, critic-model semantic checks, weak-vs-strong ablation.
- New `docs/STANDARD_TASKS.md`: Nkama Standard Tasks v1 (NST-1..5), a frozen
  shared task surface for cross-model comparability.
- README: "Known limits, by design and by roadmap" section, including the
  multilingual policy (evidence layer is language-neutral; prompt heuristics
  are English-first pending roadmap work).

## 0.1.24 — 2026-07-04

- Trusted Publishing verification release. PyPI now has a GitHub Actions
  Trusted Publisher configured for `donkk11/nkama-fact-benchmark`,
  workflow `publish.yml`, environment `pypi`.
- No runtime behavior changes from 0.1.23; this release exists to prove the
  token-free GitHub-to-PyPI release path.

## 0.1.23 — 2026-07-04 (on PyPI)

- Added explicit `permission_request` output for blocked `agent-run` provider
  calls. Blocked runs now tell the user what must be approved next: external
  model access, provider CLI availability, scoped tool access, budget cap, and
  timeout.
- The public selftest now verifies that blocked external-model runs include a
  permission request with budget and timeout suggestions.

## 0.1.22 — 2026-07-04 (on PyPI)

- Added Homepage/Repository/Issues URLs to package metadata. This fixes the
  externally reported finding that the PyPI page exposed no repository link
  (the fix missed the 0.1.21 upload, which shipped without project.urls).
- Added version-pinning guidance for CI to the README.
- Added `README_PYPI.md` so the PyPI release page has a public-safe long
  description instead of relying on missing package metadata.
- Added this changelog, SECURITY.md, RECOMMENDED_RUN.md, and the GitHub
  Actions Trusted Publishing workflow to the repository.
- Note: 0.1.22 was published manually with a project token after the first
  Trusted Publishing attempt failed because PyPI had no matching publisher
  configured.

## 0.1.21 — 2026-07-03 (on PyPI)

- Added "The Recommended Run" section to the README with field results.
- Note: published manually without repository metadata URLs; superseded by
  0.1.22 for that fix.

## 0.1.0 – 0.1.20 — 2026-06-22 to 2026-06-29

Rapid alpha iteration on PyPI: public CLI surface (`intro`, `activate`,
`selftest`, `browser-benchmark`, `capability-test`, `inspect`, `prompt`,
`prepare`, `run`, `start`, `agent`, `agent-run`, `security-audit`) and the
sister tools `nkama-prompt-filter`, `nkama-evidence-layer`,
`nkama-truth-filter`. Release-by-release notes were not kept during this
phase; from 0.1.21 onward this changelog is the record.
