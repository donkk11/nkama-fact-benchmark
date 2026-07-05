# Changelog

## 0.1.25 — 2026-07-05

- Public maintainer contact now lives in SECURITY.md (repository level),
  fixing the reviewed inconsistency where SECURITY.md pointed at metadata
  that exposed no email. Package artifacts intentionally remain email-free:
  the release security audit's no_private_text rule rejected an attempt to
  embed the address in package metadata — the gate applies to its own
  maintainer, and repo-level contact is the compliant path.
- New `docs/MANIFEST_QUALITY.md`: evidence strength ladder, anti-gaming
  patterns, critic-model semantic checks, weak-vs-strong ablation.
- New `docs/STANDARD_TASKS.md`: Nkama Standard Tasks v1 (NST-1..5), a frozen
  shared task surface for cross-model comparability.
- README: "Known limits, by design and by roadmap" section, including the
  multilingual policy (evidence layer is language-neutral; prompt heuristics
  are English-first pending roadmap work).

## 0.1.24 — 2026-07-04

- Trusted Publishing verification release. PyPI now has a GitHub Actions
  Trusted Publisher configured for `donkk11/nkama-fact-benchmark`,
  workflow `publish.yml`, environment `pypi`.
- No runtime behavior changes from 0.1.23; this release exists to prove the
  token-free GitHub-to-PyPI release path.

## 0.1.23 — 2026-07-04 (on PyPI)

- Added explicit `permission_request` output for blocked `agent-run` provider
  calls. Blocked runs now tell the user what must be approved next: external
  model access, provider CLI availability, scoped tool access, budget cap, and
  timeout.
- The public selftest now verifies that blocked external-model runs include a
  permission request with budget and timeout suggestions.

## 0.1.22 — 2026-07-04 (on PyPI)

- Added Homepage/Repository/Issues URLs to package metadata. This fixes the
  externally reported finding that the PyPI page exposed no repository link
  (the fix missed the 0.1.21 upload, which shipped without project.urls).
- Added version-pinning guidance for CI to the README.
- Added `README_PYPI.md` so the PyPI release page has a public-safe long
  description instead of relying on missing package metadata.
- Added this changelog, SECURITY.md, RECOMMENDED_RUN.md, and the GitHub
  Actions Trusted Publishing workflow to the repository.
- Note: 0.1.22 was published manually with a project token after the first
  Trusted Publishing attempt failed because PyPI had no matching publisher
  configured.

## 0.1.21 — 2026-07-03 (on PyPI)

- Added "The Recommended Run" section to the README with field results.
- Note: published manually without repository metadata URLs; superseded by
  0.1.22 for that fix.

## 0.1.0 – 0.1.20 — 2026-06-22 to 2026-06-29

Rapid alpha iteration on PyPI: public CLI surface (`intro`, `activate`,
`selftest`, `browser-benchmark`, `capability-test`, `inspect`, `prompt`,
`prepare`, `run`, `start`, `agent`, `agent-run`, `security-audit`) and the
sister tools `nkama-prompt-filter`, `nkama-evidence-layer`,
`nkama-truth-filter`. Release-by-release notes were not kept during this
phase; from 0.1.21 onward this changelog is the record.
