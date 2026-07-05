Answer:
The roadmap execution package is complete in `/private/tmp/nkama_fable5_roadmap_v2/ai_output/`, with all 10 manifest checks passing:

1. **PHASE1_LAUNCH_CHECKLIST.md** — launch checklist for the current 0.1.22 release, covering release hygiene (tag/PyPI version match, truthful changelog, donkk11 URLs), a clean-venv functional smoke test (including a negative test that the verifier fails on a broken check, and that command checks stay blocked without `--allow-commands`), launch comms, and explicit exit criteria.
2. **PHASE2_FABLE_CODEX_WORKFLOW.md** — a dual-agent workflow where Fable 5 builds and Codex independently reviews under the same Tool Permission Contract: the reviewer gets only the workspace path, re-runs the verifier, grades claims CONFIRMED/CONTRADICTED/UNVERIFIED in `REVIEW.md`, and a run passes only when the verifier passes with zero contradicted claims.
3. **PHASE3_TRUSTED_PUBLISHING_0.1.23.md** — steps to ship 0.1.23 via PyPI Trusted Publishing (OIDC): register/verify the Trusted Publisher (owner `donkk11`, repo `nkama-fact-benchmark-repo`, exact workflow filename), set `id-token: write` at the job level with `pypa/gh-action-pypi-publish` and no token input, bump the version, dry-run against TestPyPI, release on tag `v0.1.23`, verify with `uvx --from nkama-fact-benchmark==0.1.23`, then revoke leftover API tokens.

`ANSWER.md` summarizes the package and `evidence_manifest.json` was replaced with 10 real checks tied to these files. `NKAMA_SESSION_STATE.md` in the workspace records the task state.

Evidence:
Model-level evidence:
Ran `uvx --from nkama-fact-benchmark nkama-evidence-layer /private/tmp/nkama_fable5_roadmap_v2/ai_output/evidence_manifest.json` (file-only mode, run_id `evidence_20260704T153618_71f67f7c`): 10 checks run, 10 pass, 0 fail, 0 blocked, `passed_all_unblocked: true`. Checks verify existence and key content of all three phase documents (smoke-test section, reviewer-independence rule, `0.1.23` target, `id-token: write`) plus the Evidence/Limitations sections in `ANSWER.md`. File SHA-256 hashes are recorded in the verifier output.

Nkama runner evidence:
- Provider `claude` model `claude-fable-5` was invoked through a local CLI subprocess and returned exit code 0.
- Provider metadata: `{"is_error": false, "kind": "claude_json", "stop_reason": "end_turn", "subtype": "success", "total_cost_usd": 1.421627, "type": "result"}`
- Nkama runner wrote `ai_output/ANSWER.md` and `MODEL_RUN_REPORT.json`.
- Evidence manifest verification: 10 checks, 10 pass, 0 fail, 0 blocked.

Limitations:
Model-level limitations:
- This is a planning/design package only: no release was performed, no GitHub Actions workflow was executed, and nothing was published to PyPI.
- The Tool Permission Contract scoped me to `/private/tmp/nkama_fable5_roadmap_v2`, so I did not inspect the actual repository (`.github/workflows/` file, `pyproject.toml`, current PyPI publisher settings). Phase 3 details (exact workflow filename, environment name, existing token state) are stated as steps to verify, not verified facts. If you want them checked against the real repo, grant read access to `/Users/kknkama/Documents/openklaw/ai_control_layer/nkama-fact-benchmark-repo`.
- Verification was file-only; no `--allow-commands` checks were defined or run.

Nkama runner limitations:
- The provider was run with scoped Claude tool access, not unlimited system access.
- Allowed directories: `/private/tmp/nkama_fable5_roadmap_v2`
- Allowed commands: `uvx *`, `python3 *`
- Allowed browser/MCP tools: `none`
- Anything outside the tool contract must be requested and reported as BLOCKED until granted.
- The runner created files and verified the starter evidence manifest outside the provider model session.
- The starter manifest proves basic output presence and evidence-section structure only; task-specific correctness is not deeply verified yet.

Files changed or created:
- `original_prompt.md`
- `evidence_prompt.md`
- `prompt_analysis.json`
- `run_contract.json`
- `AGENT_PROTOCOL.md`
- `ai_output/ANSWER.md`
- `ai_output/evidence_manifest.json`
- `MODEL_RUN_REPORT.json`

Tests or checks run:
- Provider subprocess completed.
- Nkama answer contract checked.
- Evidence manifest verification: 10 checks, 10 pass, 0 fail, 0 blocked.
