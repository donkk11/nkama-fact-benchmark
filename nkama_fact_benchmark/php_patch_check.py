"""Prove whether PHP is *actually* patched against CVE-2026-109618 / -109619.

The reason this exists: `php -v` cannot answer the question. PHP's own advisory
(2026-10-21) says every service that loads PHP must be restarted, because a
running process keeps the vulnerable code in memory after the package on disk
is replaced. So the ordinary check — read the version string — returns
"patched" while the server is still exploitable. That is a claim the obvious
evidence cannot confirm, which is exactly what this package exists for.

Three states that `php -v` collapses into one:

  patched        on-disk build is fixed AND no running process still holds
                 pre-patch code in memory
  stale_runtime  on-disk build is fixed BUT a live process is still running
                 the old code — the dangerous false-clean case
  vulnerable     on-disk build is below the fixed version for its branch

Anything that cannot be determined is BLOCKED, never a pass.

Scope: your own hosts. This inspects local processes and local binaries. It is
not a remote scanner and performs no exploitation.

Authoritative fixed versions, from php.net's own 2026-10-21 security advisory:
8.5.12, 8.4.27, 8.3.36, 8.2.35. Branches 8.1 and older received no upstream
release — see UNFIXED_BRANCHES.
"""
from __future__ import annotations

import glob
import json
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

# php.net security advisory, 2026-10-21 (CVE-2026-109618 GHSA-w8hw-w9fx-j79w,
# CVE-2026-109619 GHSA-6wmf-4rv5-p3rp).
FIXED_IN_BRANCH = {
    (8, 5): (8, 5, 12),
    (8, 4): (8, 4, 27),
    (8, 3): (8, 3, 36),
    (8, 2): (8, 2, 35),
}

# These got no upstream fix at all. A distribution backport may still have
# patched them, which a version string cannot reveal — so they are reported as
# blocked-unknown, not as vulnerable. Crying wolf on a patched Debian build
# would make this tool untrustworthy in the one place it matters.
UNFIXED_BRANCHES = {(8, 1), (8, 0), (7, 4), (7, 3), (7, 2), (7, 1), (7, 0), (5, 6)}

CVES = ["CVE-2026-109618", "CVE-2026-109619"]

# Process names that load the PHP runtime into memory.
PHP_PROCESS_HINTS = ("php-fpm", "php_fpm", "php", "frankenphp", "httpd", "apache2")

# Mapped-file names that mean the PHP runtime itself is resident.
PHP_MAPPING_HINTS = ("libphp", "php-fpm", "/php", "frankenphp")

_VERSION_RE = re.compile(r"\b(\d+)\.(\d+)\.(\d+)")


def parse_version(text: str) -> tuple[int, int, int] | None:
    match = _VERSION_RE.search(text or "")
    if not match:
        return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def classify_version(version: tuple[int, int, int] | None) -> dict[str, Any]:
    """Judge an on-disk build. Unknown branches block rather than guess."""
    if version is None:
        return {
            "status": "blocked",
            "reason": "could not parse a PHP version string",
        }
    branch = (version[0], version[1])
    pretty = ".".join(str(part) for part in version)
    if branch in FIXED_IN_BRANCH:
        required = FIXED_IN_BRANCH[branch]
        if version >= required:
            return {
                "status": "pass",
                "version": pretty,
                "required": ".".join(str(part) for part in required),
                "reason": "on-disk build is at or above the fixed release for its branch",
            }
        return {
            "status": "fail",
            "version": pretty,
            "required": ".".join(str(part) for part in required),
            "reason": "on-disk build is below the fixed release for its branch",
        }
    if branch in UNFIXED_BRANCHES:
        return {
            "status": "blocked",
            "version": pretty,
            "required": None,
            "reason": (
                "this branch received no upstream fix; a distribution backport may "
                "have patched it, which a version string cannot prove. Confirm with "
                "your vendor's changelog, not with php -v."
            ),
        }
    return {
        "status": "blocked",
        "version": pretty,
        "required": None,
        "reason": (
            "unrecognised branch (pre-release or newer than this check's advisory "
            "data); not judged rather than guessed"
        ),
    }


def _classify_binary(binary: str) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            [binary, "-v"], capture_output=True, text=True, timeout=15
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"status": "blocked", "reason": f"could not execute {binary}: {exc}", "binary": binary}
    verdict = classify_version(parse_version(proc.stdout or proc.stderr))
    verdict["binary"] = binary
    try:
        verdict["binary_mtime"] = os.path.getmtime(binary)
    except OSError:
        verdict["binary_mtime"] = None
    return verdict


# Worst-wins ordering: a single vulnerable SAPI makes the host vulnerable; an
# unreadable one means we cannot claim clean; only all-pass is pass.
_RANK = {"fail": 0, "blocked": 1, "pass": 2}


def disk_build() -> dict[str, Any]:
    """Judge every PHP SAPI on the box, not just the `php` CLI.

    Real weakness this fixes (found by outside review, 2026-10-23): the CLI that
    `which php` returns can be a different, differently-patched build than the
    php-fpm or Apache runtime that actually serves web requests — which is the
    CVE's real attack surface. We classify every PHP binary we can find and
    report the WORST, so one vulnerable SAPI can't hide behind a patched CLI.
    """
    candidates: list[str] = []
    seen: set[str] = set()
    for name in ("php-fpm", "php"):
        found = shutil.which(name)
        if found and os.path.realpath(found) not in seen:
            seen.add(os.path.realpath(found))
            candidates.append(found)
    for directory in ("/usr/sbin", "/usr/local/sbin", "/usr/bin", "/usr/local/bin"):
        for match in glob.glob(f"{directory}/php-fpm*"):
            real = os.path.realpath(match)
            if real not in seen and os.path.isfile(real):
                seen.add(real)
                candidates.append(real)
    if not candidates:
        return {
            "status": "blocked",
            "reason": "no php or php-fpm found on PATH or in common sbin dirs; nothing on disk to judge",
            "binary": None,
            "binaries": [],
        }
    results = [_classify_binary(b) for b in candidates]
    worst = min(results, key=lambda r: _RANK.get(r["status"], 1))
    chosen = dict(worst)
    chosen["binaries"] = results  # full per-SAPI detail, not just the worst
    return chosen


def _proc_start_time(pid: int) -> float | None:
    """Wall-clock start time of a pid, from /proc's own stat mtime."""
    try:
        return os.path.getmtime(f"/proc/{pid}")
    except OSError:
        return None


def parse_maps(content: str) -> dict[str, Any]:
    """Find PHP runtime files this process holds that are gone from disk.

    Linux marks a mapping whose backing file was deleted or replaced with the
    literal suffix " (deleted)". For a patched-but-unrestarted service that is
    the decisive artifact: the process is executing code that no longer exists
    on disk. Kept pure so it can be tested against real /proc/maps text
    instead of only on a live Linux host.
    """
    deleted: list[str] = []
    resident = False
    for line in (content or "").splitlines():
        if not any(hint in line for hint in PHP_MAPPING_HINTS):
            continue
        resident = True
        stripped = line.rstrip()
        if stripped.endswith("(deleted)"):
            fields = stripped.split()
            path = fields[-2] if len(fields) >= 2 else stripped
            if path not in deleted:
                deleted.append(path)
    return {
        "status": "fail" if deleted else "pass",
        "php_runtime_resident": resident,
        "deleted_mappings": deleted,
    }


def _stale_mappings(pid: int) -> dict[str, Any]:
    maps = Path(f"/proc/{pid}/maps")
    try:
        content = maps.read_text(errors="ignore")
    except FileNotFoundError:
        # The process exited between enumeration and read (php-fpm cycles
        # workers constantly). A process that is gone cannot be stale and is not
        # evidence of anything -- drop it, don't block the whole verdict on it.
        return {"status": "gone"}
    except OSError as exc:
        # It still exists but we genuinely could not read it (permissions etc.).
        # THAT is a real "we did not look" and must block, never pass.
        return {"status": "blocked", "reason": f"cannot read {maps}: {exc}"}
    return parse_maps(content)


def _candidate_pids() -> dict[str, Any]:
    if not Path("/proc").is_dir():
        return {
            "status": "blocked",
            "reason": (
                f"no /proc on this host ({platform.system()}); the running-process "
                "check is Linux-only. On macOS or BSD the stale-runtime question is "
                "NOT answered by this tool — do not read a disk-only pass as patched."
            ),
            "pids": [],
        }
    pids: list[dict[str, Any]] = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            comm = (entry / "comm").read_text(errors="ignore").strip()
        except OSError:
            continue
        if not any(hint in comm.lower() for hint in PHP_PROCESS_HINTS):
            continue
        pids.append({"pid": int(entry.name), "comm": comm})
    return {"status": "pass", "pids": pids}


def running_processes(binary_mtime: float | None) -> dict[str, Any]:
    found = _candidate_pids()
    if found["status"] == "blocked":
        return found

    processes: list[dict[str, Any]] = []
    for item in found["pids"]:
        pid = item["pid"]
        mappings = _stale_mappings(pid)
        if mappings.get("status") == "gone":
            continue  # process exited mid-scan; nothing to judge
        started = _proc_start_time(pid)
        row: dict[str, Any] = {
            "pid": pid,
            "comm": item["comm"],
            "started_at": started,
            "mappings": mappings,
        }
        # Two independent signals that this process predates the patch.
        row["older_than_binary"] = (
            None
            if (started is None or binary_mtime is None)
            else started < binary_mtime
        )
        row["stale"] = bool(mappings.get("deleted_mappings")) or bool(
            row["older_than_binary"]
        )
        processes.append(row)

    return summarize_running(processes)


def summarize_running(processes: list[dict[str, Any]]) -> dict[str, Any]:
    """Pure verdict over scanned processes. Kept separate so the false-pass
    guard is testable without a live /proc.

    A process whose /proc/<pid>/maps we could not read is NOT evidence of clean:
    we simply did not look. It is reported as blocked (unless something is
    already confirmed stale), never folded into pass. That was the real
    false-pass found by outside review 2026-10-23 -- an unreadable map counted
    as not-stale and quietly became a 'patched' verdict.
    """
    stale = [row for row in processes if row["stale"]]
    unreadable = [
        row for row in processes if row["mappings"].get("status") == "blocked"
    ]
    if stale:
        status = "fail"
    elif unreadable:
        status = "blocked"
    else:
        status = "pass"
    return {
        "status": status,
        "process_count": len(processes),
        "stale_count": len(stale),
        "unreadable_count": len(unreadable),
        "processes": processes,
    }


def check(_argv: list[str] | None = None) -> dict[str, Any]:
    disk = disk_build()
    procs = running_processes(disk.get("binary_mtime"))

    if disk["status"] == "fail":
        verdict = "vulnerable"
    elif disk["status"] == "pass" and procs["status"] == "fail":
        verdict = "stale_runtime"
    elif disk["status"] == "pass" and procs["status"] == "pass":
        verdict = "patched"
    else:
        verdict = "blocked"

    return {
        "schema_version": 1,
        "check": "php_rce_2026_10_runtime_state",
        "cves": CVES,
        "advisory": "https://www.php.net/ (security advisory, 2026-10-21)",
        "principle": "a version string is a claim; resident code is the artifact",
        "host": {"system": platform.system(), "release": platform.release()},
        "verdict": verdict,
        "on_disk": disk,
        "running": procs,
        "limitations": [
            "Checks this host only; proves nothing about any other machine.",
            "The stale-runtime check requires /proc and is Linux-only.",
            "Reading another user's process memory map needs CAP_SYS_PTRACE "
            "(root on a normal host has it; a default container drops it). When a "
            "php process map cannot be read, the verdict is 'blocked', never "
            "'pass' -- the tool refuses to call a host clean it could not inspect.",
            "The on-disk check classifies every PHP SAPI it can find (php, "
            "php-fpm, versioned fpm binaries) and reports the worst, so a "
            "vulnerable php-fpm cannot hide behind a patched CLI. mod_php inside "
            "Apache is not separately version-probed and should be checked too.",
            "Branches with no upstream fix (8.1 and older) are reported blocked, "
            "not vulnerable, because a distribution backport cannot be seen in a "
            "version string.",
            "A separate CVE-2026-115560 was referenced by php.net on 2026-10-23 "
            "with its full advisory still pending; this check does not cover it.",
            "'patched' means the two CVEs above, on this host, at this moment. "
            "Restarting a service after this ran invalidates the result.",
            "The deleted-mapping technique itself is standard (see needrestart / "
            "checkrestart); what this adds is a PHP-CVE-specific pass/fail verdict "
            "and machine-readable evidence, not a new detection method.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    report = check(argv)
    print(json.dumps(report, indent=2, sort_keys=False))
    return 0 if report["verdict"] == "patched" else 1


if __name__ == "__main__":
    raise SystemExit(main())
