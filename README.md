# Nkama Fact Benchmark

An AI's claim about its own work is not proof. Proof is a checkable artifact
— a real file, a real command's real exit code, a real diff.

Nkama Fact Benchmark is the discipline and the tooling that enforces that,
for any AI coding agent.

## The Nkama Way

The discipline, in one loop:

1. **One AI builds** under an explicit contract (constraints, output folder, evidence manifest).
2. **A different AI independently verifies** — adversarially. It re-runs the commands, probes the
   edge cases, and is expected to reject work that cannot prove itself.
3. **Evidence gates the verdict.** A claim about the work is not proof; proof is a checkable
   artifact — a real file, a real command's real exit code and output, a real diff. Blocked
   evidence is not success.

A run's record lives in its manifest and verdict files — markdown + JSON you can re-run, diff,
and audit later. The evidence layer verifies that your declared checks pass — it cannot know
whether your checks are worth passing. A strong manifest (real commands, real tests) gives you a
real result; a weak one (file existence, substring matches) gives you exactly what it checked and
nothing more. Read [MANIFEST_QUALITY.md](docs/MANIFEST_QUALITY.md) before trusting a `clean_pass`
you didn't design yourself.

## Real-World Results

This discipline has shipped real code into a stranger-maintained open-source security tool
([kaaval](https://github.com/kaaval/kaaval), a Kubernetes RBAC scanner) — not a self-graded demo:

- **[PR #45](https://github.com/kaaval/kaaval/pull/45)** (merged): friendly error + exit 2 when the
  `--manifests` path is missing or unreadable. Built by Claude (Fable 5) under an Nkama contract;
  independently verified by gpt-5.6-sol, which **rejected round 1** — the first patch let an
  unreadable directory silently report a clean scan (exit 0), the exact false-negative a CI
  security gate cannot afford. The corrected fix ships regression tests that exercise real
  `chmod 000` conditions instead of mocks. The maintainer merged it citing those tests as
  "the deciding detail."
- **[PR #81](https://github.com/kaaval/kaaval/pull/81)** (merged): `--version` flag ([#40](https://github.com/kaaval/kaaval/issues/40))
  and JUnit XML output ([#2](https://github.com/kaaval/kaaval/issues/2)), same pipeline.
- **[PR #108](https://github.com/kaaval/kaaval/pull/108)** (merged 2026-07-26):
  new RBAC rule `token_automount` ([#7](https://github.com/kaaval/kaaval/issues/7), CIS 5.1.6 —
  ServiceAccount tokens only mounted where necessary). Same two-model loop, and it worked again:
  gpt-5.6-sol **rejected round 1** for two real defects Claude's own checks missed — four of the
  five CLI output formats crashed on the new finding type, and Deployment pod-template overrides
  went silently undetected. Both were fixed (not documented around), round 2 passed with the
  probes re-run, and only then was the PR opened. 53 tests, evidence manifest `clean_pass: true`.

The same loop has caught defects humans missed: in two browser-game builds, a physics-based
completability check wired into the manifest found a genuinely impossible jump in a hand-made
level.

The full run folders — contracts, round-by-round verdicts, and evidence manifests — are published
in this repository's `evidence/` folder. They are maintainer-hosted evidence, not third-party
replication; independent replications are invited via `evidence/README.md` and get listed.

## See It Work

*(Demo video — not recorded yet. This section is a placeholder, not a link, until a real
screen-capture of a build-then-verify loop exists.)*

## Get Started

No install step. Give this one line to any terminal-capable AI coding agent — Claude Code, Codex,
Cursor:

```bash
uvx nkama-fact-benchmark agent
```

It prints the protocol the agent follows for the rest of the session: build under an explicit
contract, leave real evidence, verify it, and report `BLOCKED` rather than guessing. If the agent
has no real terminal, no `uvx`, or no network, `BLOCKED` is the correct result — not a guessed
success.

Everything else — every subcommand and flag — is in the
[CLI reference](docs/CLI_REFERENCE.md), not here.

## Documentation

- [Full CLI reference](docs/CLI_REFERENCE.md) — every subcommand, every tool, in detail.
- [MANIFEST_QUALITY.md](docs/MANIFEST_QUALITY.md) — the evidence strength ladder and anti-gaming patterns.
- [STANDARD_TASKS.md](docs/STANDARD_TASKS.md) — fixed task surface for cross-model comparisons.
- [NKAMA_FOR_CODEX.md](docs/NKAMA_FOR_CODEX.md) / [BRIDGE_FLOW.md](docs/BRIDGE_FLOW.md) — cross-agent build/verify setups.

## Known Limits

Independent reviews of this project have flagged real limits. The honest map:

- **Scope:** a run proves only the environment it ran in — like every test suite ever written.
  Run the standard tasks in each environment you care about; never generalize one sandbox's
  result to another.
- **Manifest sufficiency:** the verifier proves your checks pass, not that your checks are good.
- **Comparability:** cross-model comparisons need a fixed task surface (see `STANDARD_TASKS.md`).
- **Language:** the prompt filter's heuristics are English-first regex scans, so non-English
  prompts may be under-scored by the *prompt* layer. The *evidence* layer is language-neutral —
  manifests, commands, and exit codes work identically in any language.
- **Maturity:** alpha, rapid release cadence, small ecosystem. Pin versions in CI and keep run
  folders as your own ground truth.

## Status

This package is alpha software. It is useful for evidence-gated AI workflows, prompt testing, and
local verification experiments. It is not a guarantee of truth, correctness, safety, legal
validity, or production readiness.

License: Apache-2.0.
