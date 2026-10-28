# Field proof: catching a patched-but-not-restarted PHP process

**Date:** 2026-10-28 · **CVEs:** CVE-2026-109618, CVE-2026-109619 (PHP, CVSS 9.2,
fixed 2026-10-21) · **Tool:** `nkama-fact-benchmark`'s `php-patch-check`

## The claim being proven

PHP's own advisory says you must restart every service that loads PHP after
patching, because a running process keeps the vulnerable code in memory after
the package on disk is replaced. So `php -v` can report **patched** on a host
that is still fully exploitable. `php-patch-check` was written to catch that,
but until now its stale-runtime detection was proven only against hand-written
`/proc/maps` fixtures — never a real process. This run closes that gap.

## What was done (no exploit written or run)

A throwaway `php:8.3-fpm` container (PHP **8.3.36**, the Oct-21 fixed release):

1. Started a real `php-fpm` master process (PID 300).
2. Read its real `/proc/300/maps` → `php-patch-check` returned **`patched`**.
3. Replaced `/usr/local/sbin/php-fpm` on disk via rename — exactly how
   `apt`/`dpkg` unpack-then-rename an upgrade — while the process kept running.
4. Read the same real `/proc/300/maps` again → `php-patch-check` returned
   **`stale_runtime`**, naming the deleted mapping.

No exploit, no PoC, no network target. Only detection of patch state on a
process the operator controls.

## The result (verbatim, from `run.log`)

Scenario A, clean:
```
/usr/local/sbin/php-fpm
-> verdict "patched", on_disk "pass", running "pass"
```

Scenario B, after the on-disk replace (process NOT restarted):
```
/usr/local/sbin/php-fpm (deleted)
-> verdict "stale_runtime", on_disk "pass", running "fail",
   deleted ["/usr/local/sbin/php-fpm"]
```

`php -v` reported `PHP 8.3.36 ... PATCHED` in **both** scenarios. The REA-NFB
check — reading the actual runtime memory map, then gating the verdict — caught
what the version string could not.

## How to re-run

```bash
bash run.sh
```

Needs Docker and network (to pull the image). Reproduces the whole transition.

## Honest scope

- This proves the **`stale_runtime`** detection on a real `php-fpm` process. The
  `vulnerable` verdict is the version-comparison axis, covered by the package's
  unit tests (`tests/test_php_patch_check.py`).
- The detection is **Linux-only** (it needs `/proc`); on macOS/BSD the tool
  returns `blocked`, never a disk-only pass.
- This says nothing about the separate pending CVE-2026-115560.
- It proves the operator's own host. It is not a remote scanner.
