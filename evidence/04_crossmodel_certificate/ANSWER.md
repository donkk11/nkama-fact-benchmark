Answer:
## Certificate of Discovery

---

**NKAMA FACT BENCHMARK**
*Evidence-Gated Achievement Record*

---

# Certificate of Verified Discovery

**Awarded to:**
**KK Nkama** and **OpenAI Codex**

**Date of Record:** 4 July 2026

**Achievement:**
*Discovery and Successful Testing of the Evidence-Gated Codex-to-Claude Sidecar Workflow*

---

This certificate recognizes that KK Nkama, owner and architect of the Nkama Fact Benchmark system, in collaboration with OpenAI Codex as an autonomous agent, successfully designed, executed, and validated a novel **Codex-to-Claude sidecar workflow** operating under the Nkama evidence-gating protocol.

### What Was Accomplished

- Codex was invoked as a primary agent under the Nkama Fact Benchmark protocol
- Claude served as a **sidecar** — a secondary agent called within the same evidence-gated run
- The workflow demonstrated that two distinct AI systems (Codex + Claude) can operate within a single verifiable task contract, each bound by the same evidence rules
- The `nkama-evidence-layer` verifier was positioned as the shared arbiter of truth for both agents
- The protocol successfully prevented overclaiming: blocked items were marked BLOCKED, not rewritten as passes

### Why This Matters

Most multi-agent AI workflows lack a neutral verification layer. This discovery establishes a reproducible pattern: **one task contract, one evidence manifest, multiple agents, one verifier.** Neither agent can self-certify its own output.

---

*Issued under the authority of the Nkama Fact Benchmark evidence protocol.*
*This certificate is itself a text-only verified output — no fabricated execution was claimed.*

---

### Image-Generation Prompt (for Codex)

```
A formal ceremonial certificate rendered as a high-resolution digital artwork.
The certificate is on aged parchment with a dark navy border trimmed in gold leaf.
At the top center: a stylized emblem combining a circuit-board pattern and a Nigerian
eagle, glowing softly in amber and green. The title text reads "Certificate of Verified
Discovery" in an elegant serif typeface. Below it, two medallion icons side by side:
one showing the OpenAI Codex symbol, one showing a Claude-style geometric flower.
A subtle holographic seal watermark sits at the bottom right. The background has faint
binary code flowing diagonally, very low opacity. Color palette: deep navy, gold,
ivory parchment, with emerald green accents. Photorealistic print quality, 4K.
```

---

Evidence:
Model-level evidence:
- The workflow described (Codex calling Claude as a sidecar within a Nkama evidence-gated run) is accurately reflected by the structure of this very response: Claude was invoked by the Nkama agent runner (`nkama-fact-benchmark agent-run`) under `text_only` tool mode with explicit budget and permission constraints
- The session prompt confirms the evidence-gating apparatus (manifest path, verifier command, tool permission contract) was in place before this response was generated
- The certificate makes no claims about file writes, test execution, or external verification that did not occur in this text-only mode

Nkama runner evidence:
- Provider `claude` model `claude-sonnet-4-6` was invoked through a local CLI subprocess and returned exit code 0.
- Provider metadata: `{"is_error": false, "kind": "claude_json", "stop_reason": "end_turn", "subtype": "success", "total_cost_usd": 0.0348631, "type": "result"}`
- Nkama runner wrote `ai_output/ANSWER.md` and `MODEL_RUN_REPORT.json`.
- Evidence manifest verification: 3 checks, 3 pass, 0 fail, 0 blocked.

Limitations:
Model-level limitations:
- BLOCKED: No files were written to `/private/tmp/nkama_claude_certificate/ai_output/` — this run is `text_only` with `allowed directories: none`
- BLOCKED: `evidence_manifest.json` was not updated — no filesystem access
- BLOCKED: `nkama-evidence-layer` verifier was not run — no shell access
- The certificate is a ceremonial text document, not a cryptographically signed artifact
- The image-generation prompt is a specification only; no image was generated or verified in this run

Nkama runner limitations:
- The provider was intentionally run in text-only mode with no filesystem, shell, browser, screenshot, or database tools.
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
- Evidence manifest verification: 3 checks, 3 pass, 0 fail, 0 blocked.
