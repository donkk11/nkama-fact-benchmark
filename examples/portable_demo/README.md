# Portable demo — the canonical "re-run it yourself" example

This is the one example that verifies GREEN on any fresh clone, no absolute
paths, no external files. From the repo root:

```bash
uvx --from nkama-fact-benchmark nkama-evidence-layer \
    examples/portable_demo/evidence_manifest.json --allow-commands
```

Expected: `checks_run: 3, pass: 3, fail: 0, blocked: 0, clean_pass: true`.

The manifest uses only relative paths; its command check runs the unit tests
from this folder. If it does not pass on your machine, that is a real bug —
open an issue.
