---
description: Verify an Nkama evidence manifest and report pass/fail/blocked. Use when the user wants to check that AI-generated work actually holds up, or names an evidence_manifest.json to verify.
---

# Nkama: verify

The user wants to verify claimed work with the Nkama evidence layer.

1. Find the evidence_manifest.json (ask the user for the path if "$ARGUMENTS" is empty).
2. Run: `uvx --from nkama-fact-benchmark nkama-evidence-layer <path> --allow-commands`
   (only pass --allow-commands after confirming the manifest's commands are safe to run).
3. Report the summary honestly: checks_run, pass, fail, blocked, and clean_pass.
4. State plainly: blocked evidence is NOT success. If anything is blocked or failed,
   say so and name what is missing. Never describe unverified work as verified.
