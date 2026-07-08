# Nkama Command Map For Codex

Use this reference when choosing how Codex should run Nkama.

## First-run protocol

```bash
uvx --no-cache nkama-fact-benchmark
uvx --no-cache nkama-fact-benchmark activate
```

Use when the user wants the AI chat or agent session to adopt the protocol before building.

## Prepare a stronger second prompt

```bash
uvx --no-cache nkama-fact-benchmark prepare "USER TASK" --output nkama_prepare_task
```

Use when the user wants a better prompt before execution. This should not build yet.

## Create a task workspace

```bash
uvx --no-cache nkama-fact-benchmark run "USER TASK" --output nkama_run_task
```

Use when an AI should put outputs under `ai_output/`, update `evidence_manifest.json`, and verify the result.

## Inspect an existing folder

```bash
uvx --no-cache nkama-fact-benchmark inspect path/to/folder
uvx --no-cache nkama-fact-benchmark inspect path/to/folder --allow-commands
```

Use when the user asks whether a generated folder is design-only, incomplete, fake evidence, failed evidence, working code, or verified build.

## Test sandbox capability

```bash
uvx --no-cache nkama-fact-benchmark capability-test --deep
```

Use when the question is what the current sandbox can actually do. Interpret blocked PyPI/network as environment evidence, not proof that the package does not exist.

## Research harness

```bash
uvx --no-cache nkama-fact-benchmark pilot-harness --phase A --output nkama_phase_a
```

Use for SWE-bench / FEVER / TruthfulQA style experiment preparation. Do not claim the experiment ran if Docker, datasets, task IDs, or evaluation harness are unavailable.

## Bridge two terminal agents

Codex builds, Claude verifies:

```bash
uvx nkama-fact-benchmark bridge "USER TASK" \
  --builder codex \
  --verifier claude \
  --verifier-model claude-opus-4-8 \
  --allow-external-model \
  --max-budget-usd 3 \
  --timeout-seconds 600 \
  --output ~/Documents/nkama_bridge_run \
  --allow-command "python3 *" \
  --allow-command "uvx *"
```

Claude builds, Codex verifies:

```bash
uvx nkama-fact-benchmark bridge "USER TASK" \
  --builder claude \
  --verifier codex \
  --model claude-fable-5 \
  --allow-external-model \
  --max-budget-usd 3 \
  --timeout-seconds 600 \
  --output ~/Documents/nkama_bridge_run \
  --allow-command "python3 *" \
  --allow-command "uvx *"
```

Call the run passed only when the bridge report says `status: pass`, the verifier verdict is `PASS`, and the harness re-verification is `clean_pass: true`.
