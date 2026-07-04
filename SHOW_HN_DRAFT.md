# Show HN Draft

Do not post this until the package is public, the repo is public, and the maker
is ready to answer comments.

## Title

```text
Show HN: Nkama Fact Benchmark - evidence-gated verification for AI agent claims
```

## URL

```text
https://github.com/donkk11/nkama-fact-benchmark
```

## First Comment

```text
Hi HN, I’m KK. I built Nkama Fact Benchmark because AI agents often say things
like “tests passed” or “I created the file” without leaving proof that can be
checked later.

Nkama is a small CLI that wraps AI-assisted work in an evidence contract. It
asks the agent to create real files, keep an evidence_manifest.json, and then a
separate verifier checks the manifest against the filesystem and reviewed
commands. If evidence is missing, it is BLOCKED, not silently treated as
success.

Try it with uvx:

uvx --no-cache nkama-fact-benchmark
uvx --no-cache nkama-fact-benchmark selftest
uvx --no-cache nkama-fact-benchmark capability-test

For a pinned release:

uvx --no-cache --from nkama-fact-benchmark==0.1.23 nkama-fact-benchmark selftest

It is early alpha. It does not make an AI magically truthful; it makes claims
easier to verify. Right now it is strongest for file evidence, command checks,
AI sandbox capability tests, prompt preparation, and external model runs under
explicit permissions.

I would love feedback on what checks would make you trust an AI agent’s output
more: screenshots, browser tests, source citations, reproducible builds,
multi-agent comparison, or something else?
```

## Notes Before Posting

- Be present for comments after posting.
- Do not ask friends to upvote or comment.
- Be direct about limitations.
- If GitHub Sponsors is enabled before posting, add one honest sentence in the
  first comment: “If this helps your agent workflow, sponsorship is open on the
  repo.”
