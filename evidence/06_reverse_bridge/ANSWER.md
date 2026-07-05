Answer:
Built manifest_stats.py — a small tool that summarizes any Nkama evidence
manifest: total checks, counts by type, strongest evidence tier
(command > content > presence), and whether command checks are allowlisted.
Built by Claude Fable 5; independently verified by OpenAI Codex (reverse of
the usual bridge direction).

Evidence:
- python3 -m unittest: 5 tests, all pass (exit 0).
- This manifest's command checks re-run the tests and dogfood the tool on
  the manifest itself at verification time.
- Verifier: uvx --from nkama-fact-benchmark nkama-evidence-layer <this file> --allow-commands

Limitations:
- The tool reads manifests; it does not execute their checks (that is the
  evidence layer's job).
- Codex's verification runs in its own sandbox; if that sandbox blocks
  network or cache access for uvx, its correct report is BLOCKED, not pass.

Files changed or created:
- manifest_stats.py, test_manifest_stats.py, evidence_manifest.json, ANSWER.md

Tests or checks run:
- python3 -m unittest discover (5/5), evidence layer 7 checks.
