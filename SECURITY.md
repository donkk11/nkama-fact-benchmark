# Security Policy

## Design principles

The public profile of nkama-fact-benchmark is closed by default:

- No private documents are read by default.
- No external model calls happen without `--allow-external-model`.
- No shell commands run without `--allow-commands` (evidence layer) or an
  explicit `--allow-command` pattern (agent-run), matched against an
  allowlist of command prefixes declared in the manifest.
- Evidence file checks refuse paths outside the manifest's own folder.
- Blocked evidence is reported as blocked, never as success.
- Release artifacts are audited before publishing
  (`nkama-fact-benchmark security-audit dist/*.whl dist/*.tar.gz`) for
  private paths, internal names, unexpected commands, and dependencies.

## Honest limits

No software is unhackable, and this project does not claim to be. In
particular: command checks execute whatever the manifest author allowlisted —
review a manifest before running `--allow-commands` on it, exactly as you
would review a shell script before running it. The evidence layer verifies
that declared checks pass; it cannot prove the checks themselves are
sufficient or that the machine running them is uncompromised.

## Reporting a vulnerability

Open a GitHub issue with the label `security`, or email the author
directly: kknkama@gmail.com. Please include reproduction steps. Do not include
private data in reports.
