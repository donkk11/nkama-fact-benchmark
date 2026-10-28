#!/bin/bash
# Reproduce the field proof. Needs Docker (any Linux engine) and network to pull
# the official php image. Nothing here touches your host or any remote server.
#
#   bash run.sh
#
# It starts a real php-fpm inside a throwaway container, replaces the php-fpm
# binary on disk while the process keeps running (an upgrade-without-restart),
# and shows that php-patch-check flips from "patched" to "stale_runtime" while
# `php -v` keeps reporting the patched version. No exploit is written or run.
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
docker run --rm -v "$HERE":/work php:8.3-fpm bash -c \
  'apt-get update -qq >/dev/null 2>&1 && apt-get install -y -qq python3 procps >/dev/null 2>&1 && bash /work/field_proof.sh'
