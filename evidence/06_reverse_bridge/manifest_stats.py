"""Summarize an Nkama evidence manifest.

Reads an evidence_manifest.json and reports how many checks it declares,
grouped by type, plus the strongest evidence tier present. Tier order
(strongest first): command checks re-run reality, content checks read it,
presence checks only glance at it.
"""

import json

TIER_OF_TYPE = {
    "command": "command",
    "command_exit_zero": "command",
    "file_contains": "content",
    "no_forbidden_claims": "content",
    "file_exists": "presence",
}

TIER_ORDER = ["command", "content", "presence", "none"]


def load_manifest(path):
    with open(path, "r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    if not isinstance(manifest.get("checks"), list):
        raise ValueError("manifest has no checks list")
    return manifest


def count_checks_by_type(manifest):
    counts = {}
    for check in manifest["checks"]:
        kind = str(check.get("type", "unknown"))
        counts[kind] = counts.get(kind, 0) + 1
    return counts


def strongest_tier(manifest):
    tiers = {TIER_OF_TYPE.get(str(c.get("type")), "presence") for c in manifest["checks"]}
    for tier in TIER_ORDER:
        if tier in tiers:
            return tier
    return "none"


def summarize(path):
    manifest = load_manifest(path)
    return {
        "checks_total": len(manifest["checks"]),
        "by_type": count_checks_by_type(manifest),
        "strongest_tier": strongest_tier(manifest),
        "command_checks_allowed": bool(manifest.get("allowed_command_prefixes")),
    }


if __name__ == "__main__":
    import sys

    print(json.dumps(summarize(sys.argv[1]), indent=2))
