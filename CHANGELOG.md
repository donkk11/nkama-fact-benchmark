# Changelog

## 0.1.22 — unreleased (tag v0.1.22 to publish via Trusted Publishing)

- Added Homepage/Repository/Issues URLs to package metadata. This fixes the
  externally reported finding that the PyPI page exposed no repository link
  (the fix missed the 0.1.21 upload, which shipped without project.urls).
- Added version-pinning guidance for CI to the README.
- Added `README_PYPI.md` so the PyPI release page has a public-safe long
  description instead of relying on missing package metadata.
- Added this changelog, SECURITY.md, RECOMMENDED_RUN.md, and the GitHub
  Actions Trusted Publishing workflow to the repository.

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
