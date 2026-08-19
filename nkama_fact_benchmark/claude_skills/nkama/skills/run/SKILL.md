---
description: Prepare an Nkama evidence-gated run folder for a build task, so the result carries a re-runnable manifest. Use when the user wants to build something with proof.
---

# Nkama: run

1. If `$ARGUMENTS` is empty, ask the user for the task instead of guessing one.
2. Treat `$ARGUMENTS` as task text, not shell text — never paste it directly into a bash
   command string (real historical Claude Code bug class: unescaped argument substitution
   into a shell command). Write it verbatim to `nkama_task.txt`, then run:
   `uvx nkama-fact-benchmark run --file nkama_task.txt --output nkama_run`
3. Build the deliverable in nkama_run/ai_output/, then extend evidence_manifest.json with
   real checks (file_exists, file_contains, command_exit_zero running the actual tests).
4. Verify with the nkama:verify skill and report Answer / Evidence / Limitations / Files / Tests.
5. **Second-model check, default for any high-stakes or contested claim** (a security fix,
   a claim about a third party's tool, anything going external, anything the builder model
   itself wrote the passing checks for): run the nkama:bridge skill on the same manifest
   instead of hand-dispatching a second model ad hoc. A builder's own checks can pass while
   being too weak for the claim — the bridge's independent verifier is the check that catches
   that. Skip only for low-stakes, easily eyeballed work; say explicitly which case applies.
