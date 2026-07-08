# Codex Perspective On Nkama Fact Benchmark

Use this reference when the user asks for Codex's own view of the project.

## Current observed state

As of local repo version `0.1.27`, Nkama has become a working evidence workflow, not only a prompt wrapper.

Observed command surface includes:

- `prepare`
- `run`
- `agent`
- `agent-run`
- `inspect`
- `capability-test --deep`
- `pilot-harness`
- `bridge`
- `nkama-evidence-layer`
- `nkama-prompt-filter`
- `nkama-truth-filter`

The repo has six published evidence case folders, each with regenerated verification reports showing `clean_pass: true`. A newer P1 bridge test also verified the reverse direction: Codex built, Claude Opus verified, and the harness re-verified cleanly.

## What I think the product is

Nkama is not a truth machine.

Nkama is a receipt machine for AI work. Its real value is forcing a task to leave behind enough structure that another person, agent, or future self can inspect what happened.

That makes it useful for:

- AI-generated code and games,
- documents and presentations,
- cross-model build/verify loops,
- sandbox capability testing,
- research harness preparation,
- evidence honesty audits.

## What I would correct

1. Do not market it as "stopping hallucination." Say "reducing unverified claims by making evidence visible."
2. Do not treat every AI chat as equally capable. Require capability-test proof per environment.
3. Do not rely on one second model as truth. The second model is a verifier only when it runs checks or reads artifacts.
4. Do not let a bridge verifier turn a blocked builder into a pass.
5. Do not call a design folder a build. Use `inspect`.
6. Do not publish every experiment immediately. Keep local tests local until the evidence is clean.

## What I would add next

The highest-value next feature is a `doctor` or `review-run` command:

- read a run folder,
- inspect command-check strength,
- detect weak manifests,
- identify missing tests,
- detect fake or unsupported claims in `ANSWER.md`,
- recommend the next correction.

The second highest-value feature is a stable `standard-task` runner for third-party replication:

- run NST tasks,
- save identical folder shape,
- compare manifests across agents,
- export a public replication report.

## Plain-language framing

Use this sentence:

> Your AI says it built it. Nkama asks: can it prove it?

Use this longer framing:

> Nkama turns AI work into a contract with evidence: what was requested, what was built, what was checked, what failed, and what stayed blocked.

Avoid this:

> Nkama makes AI truthful.

Better:

> Nkama makes AI claims harder to hide behind.
