#!/bin/bash
# REA-NFB field proof, honest edition: a REAL vulnerable PHP (8.3.35) keeps
# serving after the on-disk build is upgraded to the REAL patched 8.3.36 without
# a restart. No identical-copy shortcut; no exploit written or run.
set -u
cd /work
log() { printf '\n==== %s ====\n' "$*"; }
find_master() { for d in /proc/[0-9]*; do [ -r "$d/comm" ] && grep -q 'php-fpm' "$d/comm" 2>/dev/null && { echo "${d#/proc/}"; return; }; done; }
verdict() { python3 -c "import php_patch_check as p, json; r=p.check(); print(json.dumps({'verdict':r['verdict'],'on_disk':r['on_disk']['status'],'on_disk_version':r['on_disk'].get('version'),'running':r['running']['status'],'deleted':[q['mappings'].get('deleted_mappings') for q in r['running']['processes'] if q['mappings'].get('deleted_mappings')]}, indent=2))"; }

log "ENVIRONMENT - the service is running the PRE-PATCH, vulnerable build"
php -v | head -1
python3 --version

log "START php-fpm on the vulnerable 8.3.35 build (the real runtime under test)"
php-fpm -D 2>/dev/null; sleep 1
PID="$(find_master)"; echo "php-fpm master PID = $PID"

log "SCENARIO 1 - BEFORE any upgrade: tool on the live vulnerable process"
verdict

log "APPLY THE SECURITY UPGRADE to BOTH on-disk SAPIs (php + php-fpm), NO restart"
cp /work/php-fpm.patched /usr/local/sbin/php-fpm.new && mv /usr/local/sbin/php-fpm.new /usr/local/sbin/php-fpm
cp /work/php.patched     /usr/local/bin/php.new     && mv /usr/local/bin/php.new     /usr/local/bin/php
chmod +x /usr/local/sbin/php-fpm /usr/local/bin/php
echo "on-disk 'php -v' is NOW: $(php -v | head -1)"

log "SCENARIO 2 - AFTER the upgrade: the SAME old process is still serving"
echo "-- real /proc/$PID/maps lines for php-fpm (note the marker):"
grep -iE 'php-fpm|libphp' "/proc/$PID/maps" | grep -i deleted | head -3
verdict

log "php -v SAYS PATCHED. THE PROCESS IS STILL RUNNING 8.3.35."
echo "The on-disk version string now reads 8.3.36 (patched), but PID $PID is still"
echo "executing the vulnerable 8.3.35 code in memory. REA-NFB verdict: stale_runtime."
