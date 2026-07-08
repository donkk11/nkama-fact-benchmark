# Nkama for Codex

This document records Codex's native view of Nkama Fact Benchmark as of the
0.1.27 local repo state.

## What Codex Thinks We Built

Nkama Fact Benchmark is no longer just a prompt wrapper. It is an evidence
workflow for AI work:

```text
task
  -> intent contract
  -> capability check
  -> build or answer
  -> evidence manifest
  -> verifier
  -> pass / fail / blocked
  -> correction
```

The important shift is not "AI becomes perfect." The important shift is that
the AI has to leave receipts.

## Verified Local Evidence

Codex checked the local repo and observed:

- package version: `0.1.27`
- current branch: `main`
- latest local commit: `3fe929d Release 0.1.27: bridge subcommand + Intent Contract prompt stage`
- local package selftest: `11 pass, 0 fail, 0 blocked, clean_pass: true`
- evidence appendix: six published case-study folders with regenerated
  `verification_report.json` files showing `clean_pass: true`
- bridge runs include:
  - `P1_fable_to_codex`: pass
  - `P1_codex_to_opus48`: fail, useful early failure
  - `P1_codex_to_opus48_rerun_20260707`: pass

The early failed P1 reverse run matters. It showed that the bridge and prompt
contract were still too weak. The later rerun matters because it passed after
the correction.

## Codex Correction

Codex would tighten the public story like this:

Do not say:

> Nkama stops hallucination.

Say:

> Nkama reduces unverified claims by forcing AI work to expose evidence,
> limitations, and blocked states.

Do not say:

> Two models make the answer true.

Say:

> A second model helps only when it independently reads artifacts, runs checks,
> and signs a verdict that the harness can re-check.

Do not say:

> Every AI can run it.

Say:

> Every terminal-capable AI can try to run it. `capability-test --deep` tells
> us what that environment can actually do.

## Codex Value Add

The Codex-specific layer should be:

- a personal Codex skill named `nkama-for-codex`
- an evidence-first operating mode triggered by `/nkama`, "Nkama for Codex",
  or "prove what it claims"
- a bridge discipline where Codex can build or verify, but cannot grade its own
  homework
- a checkpoint habit: run selftest, inspect manifests, and leave the repo clean
  before publishing

The skill source lives at:

```text
codex_skills/nkama-for-codex/
```

Install target for Codex discovery:

```text
~/.codex/skills/nkama-for-codex/
```

## Next Product Move

Codex recommends building one next command before broad promotion:

```bash
uvx nkama-fact-benchmark doctor path/to/run
```

Purpose:

- read `ANSWER.md`
- read `evidence_manifest.json`
- classify evidence strength
- find unverified claims
- detect weak manifests
- recommend the next correction

This would make Nkama easier for normal users because it answers the question:

> What exactly is wrong with this AI output, and what should I fix next?
