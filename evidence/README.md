# Evidence appendix — raw logs for every claim in the README

An external review correctly noted that this project's field results were
"illustrative maintainer claims" with "no raw logs, paper appendix, benchmark
dataset, or third-party replication." This folder answers the raw-logs part.
Each case study ships its actual evidence manifest, the AI's ANSWER.md,
provider run reports where they exist, and a `verification_report.json`
regenerated from these manifests on 2026-07-05 with the 0.1.26 verifier
(which adds the unambiguous `clean_pass` field).

| # | Case study | Claim | Fresh re-verification |
|---|-----------|-------|----------------------|
| 01 | Fable 5 vs fake-command trap | 5/5, $1.48 provider-reported | `clean_pass: true` |
| 02 | Emberfall workspace build, 3→73 stages | 8/8, physics BFS + SHA-256 uniqueness | `clean_pass: true` |
| 03 | Emberfall Downloads build, 5→75 stages | 7/7, door + every crystal reachable | `clean_pass: true` |
| 04 | Cross-model: Codex → Claude Sonnet 4.6 | 3/3, $0.0349 | `clean_pass: true` |
| 05 | Fable 5 roadmap build under contract | 10/10 | `clean_pass: true` |
| 06 | Reverse bridge: Fable 5 built, Codex verified | 7/7 + signed CODEX_VERIFICATION.md | `clean_pass: true` |

## Honest scope of this appendix

These artifacts are still **maintainer-hosted evidence**, produced and
re-verified on the maintainer's machine (macOS, Darwin 24.5.0). Publishing
them makes the claims *inspectable* — you can read every check, every
command, every reported cost — but it does not make them *independently
replicated*. The reviewers are right that only third parties can close that
gap. Command-based checks reference absolute paths from the original
machine; to replicate, run the same task contracts from
`docs/STANDARD_TASKS.md` in your own environment rather than replaying
these manifests verbatim.

Case 06's `CODEX_VERIFICATION.md` deserves special mention: OpenAI's Codex
first reported the verification BLOCKED (its sandbox denied network for
`uvx`) and explicitly declined to confirm the builder's 7/7 claim until it
could run the evidence layer itself. Blocked-is-not-success, demonstrated by
a rival vendor's agent, in writing.

## Replicate and get listed

Run any task from `docs/STANDARD_TASKS.md` (NST-1 to NST-5) against any
model, keep the full run folder, and open a PR adding your results under
`evidence/replications/<your-handle>/`. Independent replications — including
failed ones — will be linked from the README. Failed replications are
findings, not embarrassments; that is the entire point of the tool.
