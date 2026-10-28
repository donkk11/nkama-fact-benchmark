#!/bin/bash
# Reproduce the field proof. Needs Docker (any Linux engine) and network to pull
# the two official php images. Nothing here touches your host or any remote
# server, and no exploit is written or run.
#
#   bash run.sh
#
# It starts a REAL vulnerable PHP 8.3.35 php-fpm, upgrades the on-disk binaries
# to the REAL patched 8.3.36 without restarting the process, and shows
# php-patch-check go  vulnerable -> stale_runtime  while `php -v` flips to
# "patched". --cap-add=SYS_PTRACE lets root read the www-data worker maps, the
# way root on a normal host can; without it the tool returns `blocked` for those
# workers (it refuses to call a host clean it could not fully inspect).
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"

# Pull the patched 8.3.36 binaries out of the official image first.
docker run --rm -v "$HERE":/work php:8.3-fpm bash -c \
  'cp /usr/local/sbin/php-fpm /work/php-fpm.patched && cp /usr/local/bin/php /work/php.patched'

docker run --rm --cap-add=SYS_PTRACE -v "$HERE":/work php:8.3.35-fpm bash -c \
  'apt-get update -qq >/dev/null 2>&1 && apt-get install -y -qq python3 procps >/dev/null 2>&1 && bash /work/field_proof.sh'
