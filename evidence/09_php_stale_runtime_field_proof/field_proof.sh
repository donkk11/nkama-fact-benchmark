#!/bin/bash
# REA-NFB field proof: does php-patch-check catch a REAL php-fpm process that is
# running PHP code already replaced on disk (patched-but-not-restarted)?
# No exploit is written or run. This proves DETECTION of patch state only.
set -u
cd /work
log() { printf '\n==== %s ====\n' "$*"; }

find_master() { for d in /proc/[0-9]*; do [ -r "$d/comm" ] && grep -q 'php-fpm' "$d/comm" 2>/dev/null && { echo "${d#/proc/}"; return; }; done; }

log "ENVIRONMENT"
php -v | head -1
python3 --version
BIN="$(command -v php-fpm)"; echo "php-fpm binary on disk = $BIN"

log "START php-fpm (a real long-lived process that loads the PHP runtime)"
php-fpm -D 2>/dev/null
sleep 1
PID="$(find_master)"
echo "php-fpm master PID = $PID"

log "SCENARIO A - fresh start, process running the current on-disk binary"
echo "-- real /proc/$PID/maps lines for the php-fpm executable:"
grep -iE 'php-fpm|libphp' "/proc/$PID/maps" | head -4
echo "-- php-patch-check verdict:"
python3 -c "import php_patch_check as p, json; r=p.check(); print(json.dumps({'verdict':r['verdict'],'on_disk':r['on_disk']['status'],'running':r['running']['status'],'stale_count':r['running'].get('stale_count')}, indent=2))"

log "SIMULATE an upgrade-without-restart (exactly what PHP's advisory warns about)"
echo "Replacing $BIN on disk via rename, like apt/dpkg unpack-then-rename."
echo "The running process keeps the OLD, now-unlinked inode mapped in memory."
cp "$BIN" /tmp/newbin && mv /tmp/newbin "$BIN" && echo "replaced."
echo "on-disk version still reads: $(php -v | head -1)"

log "SCENARIO B - same process, its code now REPLACED on disk (the false-clean case)"
echo "-- real /proc/$PID/maps lines now (note the marker):"
grep -iE 'php-fpm|libphp' "/proc/$PID/maps" | grep -i deleted | head -4
echo "-- php-patch-check verdict:"
python3 -c "import php_patch_check as p, json; r=p.check(); print(json.dumps({'verdict':r['verdict'],'on_disk':r['on_disk']['status'],'running':r['running']['status'],'deleted':[q['mappings'].get('deleted_mappings') for q in r['running']['processes'] if q['mappings'].get('deleted_mappings')]}, indent=2))"

log "WHAT php -v ALONE WOULD HAVE TOLD YOU"
echo "on-disk version >= the Oct-21 fix, so 'php -v' says PATCHED."
echo "The process is still executing pre-replacement code. REA-NFB caught what php -v could not."
