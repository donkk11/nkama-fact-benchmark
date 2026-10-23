# Nkama Fact Benchmark

Your AI says it built it. Nkama asks: can it prove it?

Nkama Fact Benchmark is an evidence-gated CLI toolkit for AI-assisted work. It
does not make an AI magically truthful. It makes the AI's claims easier to test
by turning them into files, checks, manifests, and clear pass/fail/blocked
reports.

## Quick Start

No install step — paste this to a terminal-capable AI coding agent:

```bash
uvx nkama-fact-benchmark agent
```

Full command reference and real shipped evidence: see the
[GitHub repository](https://github.com/donkk11/nkama-fact-benchmark).

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
