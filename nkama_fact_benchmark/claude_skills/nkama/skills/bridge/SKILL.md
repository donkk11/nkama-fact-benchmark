---
description: Run an Nkama cross-agent bridge — one agent builds under a contract, a different agent independently verifies. Use when the user wants two AI agents to build and check each other's work.
---

# Nkama: bridge

The user wants to run the two-agent bridge (builder + independent verifier).

1. Confirm the task, the builder and verifier agents, and that external model calls are allowed.
2. If `$ARGUMENTS` is empty, ask the user for the task instead of guessing one.
3. Treat `$ARGUMENTS` as task text, not shell text — never paste it directly into a bash
   command string (real historical Claude Code bug class: unescaped argument substitution
   into a shell command). Write it verbatim to `nkama_bridge_task.txt`, then run:
   `uvx nkama-fact-benchmark bridge --file nkama_bridge_task.txt --builder claude --verifier codex --allow-external-model --max-budget-usd 2`
   (swap --builder/--verifier as the user asks; both CLIs must be installed).
4. Report builder status, the independent verifier's signed verdict, and harness clean_pass.
5. A missing or blocked verdict is BLOCKED, not success.
