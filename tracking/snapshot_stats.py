#!/usr/bin/env python3
"""Snapshot real, public nkama-fact-benchmark adoption signals into a local
JSONL log — one line per run, append-only, so growth (or its absence) is a
real time series instead of a single quoted number.

Deliberately does NOT track individual usage. This queries two public,
no-login APIs (GitHub's REST API, PyPI's public download-stats mirror) for
aggregate counts only — nobody's IP, machine, or identity is ever recorded.
The package itself has no telemetry and this script does not add any; it
only reads what's already public about the published artifacts.

Honest limits, every time this is read: PyPI download counts include CI
reinstalls, Docker builds, and mirror/bot traffic — they are NOT a count of
humans. GitHub stars/forks are a much more honest signal of real interest,
just a much smaller number.

Run manually:
    python3 tracking/snapshot_stats.py

Or on a schedule (weekly is plenty — PyPI stats lag 1-3 days anyway):
    python3 tracking/snapshot_stats.py >> tracking/stats_log.jsonl
"""
from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

PYPI_STATS_URL = "https://pypistats.org/api/packages/nkama-fact-benchmark/recent"
GITHUB_REPO_URL = "https://api.github.com/repos/donkk11/nkama-fact-benchmark"
LOG_FILE = Path(__file__).parent / "stats_log.jsonl"


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "nkama-fact-benchmark-tracker"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def take_snapshot() -> dict:
    pypi = _get_json(PYPI_STATS_URL)
    github = _get_json(GITHUB_REPO_URL)
    return {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "pypi_downloads_last_day": pypi["data"]["last_day"],
        "pypi_downloads_last_week": pypi["data"]["last_week"],
        "pypi_downloads_last_month": pypi["data"]["last_month"],
        "github_stars": github.get("stargazers_count"),
        "github_forks": github.get("forks_count"),
        "github_open_issues": github.get("open_issues_count"),
        "github_watchers": github.get("subscribers_count"),
        "pypi_latest_version": None,  # filled in below if available
        "note": "PyPI downloads include CI/mirror/bot traffic, not just humans. GitHub stars/forks are the more honest signal.",
    }


def main() -> None:
    try:
        pypi_version = _get_json("https://pypi.org/pypi/nkama-fact-benchmark/json")["info"]["version"]
    except Exception:
        pypi_version = None

    snapshot = take_snapshot()
    snapshot["pypi_latest_version"] = pypi_version

    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(snapshot) + "\n")

    print(json.dumps(snapshot, indent=2))
    print(f"\nAppended to {LOG_FILE}")


if __name__ == "__main__":
    main()
