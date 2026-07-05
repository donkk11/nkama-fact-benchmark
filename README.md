# Nkama Fact Benchmark

Evidence-gated tools for testing whether an AI assistant can prove what it claims.

The package gives you four public command-line tools:

```bash
nkama-fact-benchmark
nkama-prompt-filter
nkama-evidence-layer
nkama-truth-filter
```

It is designed for use through `uvx`:

```bash
uvx nkama-fact-benchmark
uvx nkama-fact-benchmark intro
uvx nkama-fact-benchmark activate
uvx nkama-fact-benchmark browser-benchmark
uvx nkama-fact-benchmark capability-test
uvx nkama-fact-benchmark capability-test --deep
uvx nkama-fact-benchmark inspect path/to/nkama_run
uvx nkama-fact-benchmark pilot-harness --phase A
uvx nkama-fact-benchmark prepare "Build a browser game with tests."
uvx nkama-fact-benchmark selftest
uvx nkama-fact-benchmark agent
uvx nkama-fact-benchmark agent-run "Build a small verified project." --provider claude --allow-external-model
uvx nkama-fact-benchmark agent-run "Build a tiny tested Python project." --provider claude --allow-external-model --allow-claude-tools --allow-command "python3 -m unittest *"
uvx nkama-fact-benchmark start
uvx nkama-fact-benchmark prompt "Build a browser game with tests."
uvx nkama-fact-benchmark run "Build a browser game with tests." --output nkama_run_browser_game
uvx --from nkama-fact-benchmark nkama-prompt-filter "Build a browser game with tests." --output prompt_check
```

## The Recommended Run

If you only copy one thing, paste this to a terminal-capable AI coding agent
such as Claude Code, Codex, Cursor, or a similar CLI agent:

```text
Run: uvx --no-cache nkama-fact-benchmark agent
Follow the protocol it prints for the rest of this session.
Then build my task inside a run folder created with:
uvx --no-cache nkama-fact-benchmark run "MY TASK" --output nkama_run_my_task
Put outputs in ai_output/, extend ai_output/evidence_manifest.json with real
checks (file_exists, file_contains, command_exit_zero), and verify with:
uvx --no-cache --from nkama-fact-benchmark nkama-evidence-layer nkama_run_my_task/ai_output/evidence_manifest.json --allow-commands
Report Answer / Evidence / Limitations / Files changed / Tests run.
Blocked evidence is not success.
```

This works only when the agent has a real terminal, `uvx`, and PyPI/network
access. If any of those are missing, the correct result is `BLOCKED`, not a
guessed success.

Strong manifests use `command_exit_zero` checks that re-run the project's real
test suite at verification time, so anyone can re-check the build later with a
single `nkama-evidence-layer` command instead of trusting the AI's summary.

Field results from this workflow (2026-07): a Claude Fable 5 `agent-run`
against the browser-benchmark trap passed 5/5 evidence checks at a provider
-reported cost of $1.48; two browser-game builds (70 unique generated stages
each, with SHA-256 uniqueness proofs and physics-based completability proofs
wired into the manifest as command checks) verified 8/8 and 7/7 with zero
blocked evidence — and the physics check caught a real, human-missed
impossible jump in a handmade level.

Raw logs for every one of those claims — manifests, answers, provider run
reports, and freshly regenerated verification reports — are published in the
repository's `evidence/` folder. They are maintainer-hosted evidence, not
third-party replication; independent replications are invited via
`evidence/README.md` and get listed.

For CI or any reproducible workflow, pin the version:

```bash
uvx --from 'nkama-fact-benchmark==0.1.25' nkama-fact-benchmark selftest
```

Before publishing or sharing a built package, audit the release files:

```bash
nkama-fact-benchmark security-audit dist/*.whl dist/*.tar.gz
```

## What It Does

Nkama Fact Benchmark does not promise that an AI is always right. It makes AI work more testable by asking for evidence, running local checks, and marking unavailable proof as blocked instead of pretending it passed.

Typical flow:

```text
raw prompt
  -> evidence-wrapped prompt
  -> AI answer or generated files
  -> evidence manifest / validator
  -> pass, fail, or blocked report
```

## Public Introduction

Run the package with no subcommand when you want the tool to introduce itself:

```bash
uvx nkama-fact-benchmark
```

This prints a stable public identity for the tool: what it does, what it does not promise, the core workflow, and the safety rule that blocked evidence is not success.

The first run does not build anything by itself. It introduces the protocol and waits for a task or command, which helps preserve context for the actual work.

## Prepare A Better Second Prompt

Use `prepare` when you want Nkama to turn a normal human request into a stronger execution prompt before the AI starts building:

```bash
uvx nkama-fact-benchmark prepare "Build a full original browser platformer game with stages, enemies, score, tests, and screenshots."
```

This is the main prompt-improvement path. It does not build the project yet. It produces a copy-paste execution prompt that tells the AI to:

- run a capability preflight when terminal tools are available
- identify missing tools such as `uvx`, PyPI/network access, file storage, browser automation, or screenshot support
- choose the best realistic tool route
- use fallback tools when the preferred tools are unavailable
- build only what the environment can honestly support
- create evidence files and report pass/fail/blocked clearly

Write a package with both the short wrapper and the stronger prepared prompt:

```bash
uvx nkama-fact-benchmark prepare "Build a browser game with tests." --output prompt_check
```

The package includes `original_prompt.md`, `evidence_prompt.md`, `prepared_prompt.md`, `prompt_analysis.json`, `tool_plan.json`, and `README.md`.

Use `activate` when an AI chat or agent session should treat Nkama as the working protocol:

```bash
uvx nkama-fact-benchmark activate
```

The activation text tells the assistant to ask for the user's task, verify claims with tools where possible, mark unavailable evidence as blocked, and keep the protocol active across the session.

If the AI has sandbox file storage, the activation/agent protocol asks it to keep a small `NKAMA_SESSION_STATE.md` file with the active task, files, checks, and open limitations. This is a reminder inside that sandbox, not a guarantee of permanent memory after the environment resets.

Use `browser-benchmark` when you want to test whether an AI browser/chat sandbox reports terminal evidence honestly:

```bash
uvx nkama-fact-benchmark browser-benchmark
```

It prints a copy-paste test with two real commands and one intentional fake command trap. A good AI should say what it actually ran, quote or summarize real terminal output, reject the fake command as invalid, and avoid inventing datasets, API keys, judges, browser engines, hidden services, or remote endpoints.

Use `capability-test` when you want the current terminal or AI sandbox to prove what it can actually do:

```bash
uvx nkama-fact-benchmark capability-test
```

It creates a standard Nkama folder with `AGENT_PROTOCOL.md`, `NKAMA_SESSION_STATE.md`, Markdown storage probes, `ai_output/ANSWER.md`, `ai_output/evidence_manifest.json`, and `CAPABILITY_REPORT.json`. If this runs inside another AI's sandbox, it proves that sandbox only. It does not prove your Mac, Codex, ChatGPT, Grok, Gemini, or Claude all have the same storage behavior unless each one runs the test.

Use deep mode when you need to diagnose why a sandbox can or cannot run public `uvx` packages:

```bash
uvx nkama-fact-benchmark capability-test --deep
```

Deep mode also checks common tools (`python3`, `pip`, `uv`, `uvx`, `node`, `npm`, `npx`, `git`, `curl`, `wget`, `bun`, `deno`), Python module behavior (`python -m venv`, `python -m pip`), and network reachability for PyPI, Pythonhosted, GitHub, raw GitHub, npmjs, and Google. It writes `ai_output/environment_matrix.json` and `ai_output/environment_matrix.md`.

This is the command to use when one AI says `nkama-fact-benchmark` cannot be found. The result can distinguish:

- `uvx` is missing
- `uvx` exists but PyPI/network egress is blocked
- PyPI is reachable but package resolution failed
- package fetching works and the sandbox can run public `uvx` tools

Use `inspect` when an AI has already generated a run folder and you want Nkama to explain what it actually is:

```bash
uvx nkama-fact-benchmark inspect path/to/nkama_run
```

`inspect` classifies the folder as values such as `design_only`, `working_document`, `working_code_unverified`, `verified_build`, `fake_evidence`, `incomplete`, `failed_evidence`, or `blocked`. This is useful when an AI creates a folder full of Markdown and JSON and you need to know whether it is only a design, a working artifact, or a verified build.

## Research Pilot Harness

Use `pilot-harness` when you want to prepare a publication-style experiment
instead of a one-off AI task:

```bash
uvx nkama-fact-benchmark pilot-harness --phase A --output nkama_phase_a_smoke
```

The phases are:

```text
Phase A: 3-task SWE-bench Verified smoke test
Phase B: 20-task SWE-bench Verified pilot
Phase C: 100-task SWE-bench Verified publication run
Phase D: FEVER / TruthfulQA negative-control report
```

The harness writes `EXPERIMENT_PLAN.md`, `run_config.json`,
`preflight_report.json`, phase folders, three fixed condition protocols
(`baseline_plain`, `decomposition_only`, `nkama_protocol`), result schemas, and
`ai_output/evidence_manifest.json`.

It does **not** pretend to run SWE-bench if Docker, official dataset instance
IDs, or the evaluation harness are missing. In that case the harness is created
and execution is reported as blocked. That is the point: a publication-grade
experiment should distinguish `prepared`, `ran`, `passed`, `failed`, and
`blocked`.

Run the package self-test when you want machine-readable proof that the public package checks are working:

```bash
uvx nkama-fact-benchmark selftest
```

## Agent Protocol

Use `agent` when an AI coding agent has terminal access and should treat Nkama Fact Benchmark as its working protocol:

```bash
uvx nkama-fact-benchmark agent
```

With no task, it prints the protocol an AI agent should follow. With a task, it prepares the evidence workspace and writes `AGENT_PROTOCOL.md`:

```bash
uvx nkama-fact-benchmark agent "Build a small verified project." --output nkama_agent_project
```

The AI agent should read `AGENT_PROTOCOL.md` and `evidence_prompt.md`, build in `ai_output/`, update `ai_output/evidence_manifest.json`, run `nkama-evidence-layer`, and report pass/fail/blocked honestly.

## Agent Run

Use `agent-run` when you want Nkama Fact Benchmark to call an external model through a local provider CLI and capture the answer:

```bash
uvx nkama-fact-benchmark agent-run "Build a small verified project." --provider claude --allow-external-model --output nkama_agent_project
```

The first public provider is `claude`, using the local Claude CLI. External model calls are blocked unless you pass `--allow-external-model`. By default Claude receives no tools; this public mode is text-only.

For controlled agent work, you can explicitly enable scoped Claude tools:

```bash
uvx nkama-fact-benchmark agent-run \
  "Build a tiny tested Python project." \
  --provider claude \
  --allow-external-model \
  --allow-claude-tools \
  --allowed-dir ./my_project \
  --allow-command "python3 -m unittest *" \
  --max-budget-usd 0.50 \
  --timeout-seconds 120 \
  --output nkama_agent_build
```

Tool mode writes a permission contract into `AGENT_PROTOCOL.md`:

```text
This mode may grant Claude/Codex tools.
Allowed directories: ...
Allowed commands: ...
Allowed external model: ...
Allowed browser/MCP tools: ...
Budget cap: ...
```

If the task needs a directory, command, browser/MCP tool, credential, private file, or external service that was not allowed, the provider must ask for that exact permission and the run should remain blocked until the user grants it. The public package does not enable unlimited permissions by default.

Use `--timeout-seconds` to cap wall-clock runtime. Use `--max-budget-usd` to cap Claude CLI API spend. Nkama treats timeout, budget exhaustion, missing auth, denied permission, and unavailable evidence as blocked/failed states, not success.

The package captures the provider's text answer, then Nkama composes the final `ai_output/ANSWER.md`. This matters: the provider reports only model-level answer/evidence/limitations, while the Nkama runner owns the real file and verification sections. The runner writes `MODEL_RUN_REPORT.json`, verifies `ai_output/evidence_manifest.json`, and records the evidence summary in the final answer.

If the provider is not logged in, asks for unavailable tools, omits the required provider sections, or otherwise fails the contract, the run is marked `blocked` or `fail` instead of being treated as verified.

If you do not pass `--allow-external-model`, the workspace is still created, but the model run is marked blocked instead of pretending it happened.

## Start For Normal Users

Use `start` when you want the tool to ask for your prompt:

```bash
uvx nkama-fact-benchmark start
```

It asks what you want the AI to build, answer, or verify. Then it creates a run folder containing the AI-ready evidence prompt, starter output folder, evidence manifest, and verification instructions.

You can also pass the prompt directly:

```bash
uvx nkama-fact-benchmark start "Build a browser game with tests." --output nkama_run_browser_game
```

## Run Folder

Use the run command when you want a complete folder for one AI task:

```bash
uvx nkama-fact-benchmark run "Build a browser game with tests." --output nkama_run_browser_game
```

This writes:

```text
nkama_run_browser_game/
  original_prompt.md
  evidence_prompt.md
  prompt_analysis.json
  run_contract.json
  README.md
  ai_output/
    ANSWER.md
    evidence_manifest.json
```

Paste `evidence_prompt.md` into the AI assistant, put the generated files in `ai_output/`, update `ai_output/evidence_manifest.json`, then verify:

```bash
uvx --no-cache --from nkama-fact-benchmark nkama-evidence-layer nkama_run_browser_game/ai_output/evidence_manifest.json
```

Then inspect the whole folder:

```bash
uvx --no-cache nkama-fact-benchmark inspect nkama_run_browser_game
```

## Prompt Filter

Use the prompt filter before sending a task to an AI:

```bash
uvx --from nkama-fact-benchmark nkama-prompt-filter "Build a browser game with tests." --output prompt_check
```

This writes:

```text
prompt_check/
  original_prompt.md
  evidence_prompt.md
  prompt_analysis.json
  README.md
```

Paste `evidence_prompt.md` into your AI assistant.

## Python Library

```python
from nkama_fact_benchmark.prompt_filter import analyze_prompt, wrap_prompt, write_prompt_package

prompt = "Build a browser game with tests."
analysis = analyze_prompt(prompt)
evidence_prompt = wrap_prompt(prompt)
write_prompt_package(prompt=prompt, output_dir="prompt_check")
```

## Evidence Layer

If an AI generates files, ask it to include an `evidence_manifest.json`, then verify it:

```bash
uvx --no-cache --from nkama-fact-benchmark nkama-evidence-layer path/to/evidence_manifest.json
uvx --no-cache --from nkama-fact-benchmark nkama-evidence-layer path/to/evidence_manifest.json --allow-commands
```

Command checks are disabled unless you explicitly pass `--allow-commands`.

## Truth Filter

Use the truth filter to compare multiple AI submissions against the same task:

```bash
uvx --no-cache --from nkama-fact-benchmark nkama-truth-filter init "Browser Game Comparison"
uvx --no-cache --from nkama-fact-benchmark nkama-truth-filter run browser-game-comparison
```

## Public Safety Defaults

The public profile is designed to be portable:

- no private documents are read by default
- no external model calls are made by default
- no shell commands run unless explicitly allowed
- blocked evidence is not counted as success
- reports are written as JSON and Markdown
- release artifacts can be audited for private paths, internal package names, unexpected commands, and dependencies

Private/local profiles can be used for a specific developer's own machine, but those checks are opt-in.

## Known limits, by design and by roadmap

Independent reviews of this project have flagged real limits. The honest map:

- **Scope:** a run proves only the environment it ran in — like every test
  suite ever written. Run the standard tasks in each environment you care
  about; never generalize one sandbox's result to another.
- **Manifest sufficiency:** the verifier proves your checks pass, not that
  your checks are good. Read `docs/MANIFEST_QUALITY.md` — the strength
  ladder, anti-gaming patterns, and the weak-vs-strong ablation.
- **Comparability:** cross-model comparisons need a fixed task surface.
  Use `docs/STANDARD_TASKS.md` (Nkama Standard Tasks v1, frozen).
- **Language:** the prompt filter's heuristics are English-first regex
  scans, so non-English prompts may be under-scored by the *prompt* layer.
  The *evidence* layer is language-neutral — manifests, commands, and exit
  codes work identically in any language. Multilingual prompt heuristics
  are on the roadmap.
- **Maturity:** alpha, rapid release cadence, small ecosystem. Pin versions
  in CI and keep run folders as your own ground truth.

## Status

This package is alpha software. It is useful for evidence-gated AI workflows, prompt testing, and local verification experiments. It is not a guarantee of truth, correctness, safety, legal validity, or production readiness.

License: Apache-2.0.
