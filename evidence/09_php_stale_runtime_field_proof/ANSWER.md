# Field proof: catching a patched-but-not-restarted PHP process

**Date:** 2026-10-28 · **CVEs:** CVE-2026-109618, CVE-2026-109619 (PHP, CVSS 9.2,
fixed 2026-10-21) · **Tool:** `nkama-fact-benchmark`'s `php-patch-check`

## What this is — and is NOT

The detection technique here (a running process holding a `(deleted)` executable
mapping after an upgrade) is **not new**. Standard tools already do the general
version of it — `needrestart` (default on modern Debian/Ubuntu) and the older
`checkrestart`. This is **not a new detection method or a new vulnerability.**

What this adds is narrow and honest: a **PHP-CVE-specific pass/fail verdict**
(`patched` / `stale_runtime` / `vulnerable` / `blocked`) with **machine-readable
evidence**, wired into Nkama's verify-it-don't-claim-it discipline — and a
re-runnable proof that our own tool actually works on a real process. The value
is confidence that remediation is complete, not novelty.

## The problem

PHP's advisory says you must restart every service that loads PHP after
patching, because a running process keeps the vulnerable code in memory after
the package on disk is replaced. So `php -v` can report **patched** on a host
that is still fully exploitable.

## What was done (a REAL upgrade, no identical-copy shortcut, no exploit)

In a throwaway container, with the real patched 8.3.36 binaries extracted from
the official image:

1. Started a real `php-fpm` on the **pre-patch, vulnerable PHP 8.3.35**.
2. Ran `php-patch-check` on the live process → **`vulnerable`** (on-disk 8.3.35).
3. Upgraded **both** on-disk SAPIs (`php` and `php-fpm`) to the real **8.3.36**
   via rename — exactly how `apt`/`dpkg` unpack-then-rename — **without
   restarting** php-fpm.
4. `php -v` now reports 8.3.36 (patched). The same process is still serving.
5. Ran `php-patch-check` again → **`stale_runtime`**, naming the deleted mapping,
   because `/proc/<pid>/maps` shows the old 8.3.35 binary marked `(deleted)`.

No exploit, no PoC, no remote target. Detection of patch state only.

## The result (verbatim, from `run.log`)

Before the upgrade (vulnerable code running):
```
verdict "vulnerable", on_disk "fail", on_disk_version "8.3.35", running "pass"
```

After the on-disk upgrade, process NOT restarted:
```
/usr/local/sbin/php-fpm (deleted)
verdict "stale_runtime", on_disk "pass", on_disk_version "8.3.36", running "fail",
   deleted ["/usr/local/sbin/php-fpm"]
```

`php -v` reports `PHP 8.3.36 ... patched` after step 3. The REA-NFB check — reading
the actual runtime memory map, then gating the verdict — caught the vulnerable
8.3.35 code still executing, which the version string could not.

## The tool refuses to false-pass (shown, not asserted)

Run **without** `--cap-add=SYS_PTRACE`, root cannot read the www-data worker
maps, and the tool returns **`blocked`** for those processes — never `pass`. It
will not call a host clean that it could not fully inspect. (Outside review on
2026-10-23 found the opposite bug — an unreadable map silently counted as clean;
that false-pass is now fixed with regression tests in
`tests/test_php_patch_check.py`.)

## How to re-run

```bash
bash run.sh
```

Needs Docker and network (pulls `php:8.3.35-fpm` and `php:8.3-fpm`). Reproduces
the whole vulnerable → stale_runtime transition.

## Honest scope / limits

- Proves `stale_runtime` and `vulnerable` on a real `php-fpm` process. The
  verdict-combination logic and the false-pass guards are also unit-tested
  (`tests/test_php_patch_check.py`).
- Linux-only (needs `/proc`); on macOS/BSD the tool returns `blocked`.
- Reading other users' process maps needs `CAP_SYS_PTRACE` / real root; without
  it the tool blocks rather than passes.
- mod_php inside Apache is not separately version-probed; a host running it
  should be checked for that SAPI too.
- Says nothing about the pending CVE-2026-115560.
- Proves the operator's own host. Not a remote scanner.
