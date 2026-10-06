#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
: "${SAYURI_LAN:=1}"
export SAYURI_LAN
exec python3 -m sayuri.app
