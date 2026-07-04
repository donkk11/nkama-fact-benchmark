# Nkama Fact Benchmark

Your AI says it built it. Nkama asks: can it prove it?

Nkama Fact Benchmark is an evidence-gated CLI toolkit for AI-assisted work. It
does not make an AI magically truthful. It makes the AI's claims easier to test
by turning them into files, checks, manifests, and clear pass/fail/blocked
reports.

## Quick Start

```bash
uvx nkama-fact-benchmark
uvx nkama-fact-benchmark activate
uvx nkama-fact-benchmark prepare "Build a browser game with tests."
uvx nkama-fact-benchmark capability-test
uvx nkama-fact-benchmark inspect path/to/nkama_run
uvx nkama-fact-benchmark selftest
```

For reproducible runs, pin the version:

```bash
uvx --from 'nkama-fact-benchmark==0.1.24' nkama-fact-benchmark selftest
```

## What It Helps With

- Turn a normal prompt into a stronger evidence-gated execution prompt.
- Ask terminal-capable AI agents to keep evidence files as they work.
- Test whether the current sandbox can write files, run Python, and use `uvx`.
- Inspect generated folders and classify them as design-only, incomplete,
  blocked, failed, or verified.
- Mark missing evidence as `BLOCKED` instead of pretending it passed.

## Core Rule

Blocked evidence is not success. Fix it, rerun it, or report the limitation.

## Important Limits

This package verifies only the environment where it runs. If it runs inside a
ChatGPT, Claude, Grok, Gemini, Codex, Cursor, or other AI sandbox, the result
describes that sandbox only. A blocked PyPI, GitHub, or network connection is a
real capability result, not proof that the package does not exist.

External model calls are disabled by default. Tool access and command execution
must be explicitly requested with the relevant command flags.

## Links

- Repository: https://github.com/donkk11/nkama-fact-benchmark
- Issues: https://github.com/donkk11/nkama-fact-benchmark/issues
