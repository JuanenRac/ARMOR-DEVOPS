#!/usr/bin/env bash
# =============================================================================
# A.R.M.O.R. - ARMOR-DEVOPS/scripts/deploy_cm5.sh
# Builds ARMOR-SERVER and ARMOR-STUDIO on this computer, sends one release
# archive to the CM5 test bench and runs install_cm5.sh there.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D)
# GPL-3.0-or-later - see LICENSE
# =============================================================================
# Usage: deploy_cm5.sh --host 192.168.0.180 --user <user> --key ~/.ssh/id_key [--port N] [--public-host H] [--apply] [--with-mqtt]
#        --port N          the SSH port, when it is not 22 (a router that forwards a public port to it)
#        --public-host H   the address the browser uses, when it is not --host
#        [--also-reach http://PUBLIC:2601=http://PUBLIC:2600] [--forget-reach]   (another address the browser may log in from)
# Without --apply the remote side only prints its plan.
set -euo pipefail

HOST=""; USER_NAME=""; KEY=""; APPLY=""; EXTRA=""; SSH_PORT=""; PUBLIC_HOST=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST="${2:-}"; shift 2 ;;
    --user) USER_NAME="${2:-}"; shift 2 ;;
    --key) KEY="${2:-}"; shift 2 ;;
    --port) SSH_PORT="${2:-}"; shift 2 ;;
    --public-host) PUBLIC_HOST="${2:-}"; shift 2 ;;
    --apply) APPLY="--apply"; shift ;;
    --with-mqtt) EXTRA="$EXTRA --with-mqtt"; shift ;;
    --also-reach) EXTRA="$EXTRA --also-reach $(printf '%q' "${2:-}")"; shift 2 ;;
    --forget-reach) EXTRA="$EXTRA --forget-reach"; shift ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done
[[ -n "$HOST" && -n "$USER_NAME" ]] || { echo "usage: deploy_cm5.sh --host H --user U [--key K] [--port N] [--public-host H] [--apply] [--with-mqtt] [--also-reach STUDIO_URL=SERVER_URL]" >&2; exit 2; }

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=10)
[[ -n "$KEY" ]] && SSH_OPTS+=(-i "$KEY")
SCP_OPTS=("${SSH_OPTS[@]}")
[[ -n "$SSH_PORT" ]] && { SSH_OPTS+=(-p "$SSH_PORT"); SCP_OPTS+=(-P "$SSH_PORT"); }
# The address the browser will use defaults to the one the deploy connects to; give --public-host when they differ (an SSH port forwarded by a router).
PUBLIC_HOST="${PUBLIC_HOST:-$HOST}"
STAMP="$(date +%Y%m%d-%H%M%S)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# Build in a clean copy: a developer may have the servers running from the
# working trees, and a reinstall in place would fight them for locked files.
copy_sources() {
  mkdir -p "$WORK/build/$1"
  tar -C "$ROOT/$1" --exclude=node_modules --exclude=dist --exclude=data --exclude=.env --exclude=.git -cf - . | tar -C "$WORK/build/$1" -xf -
}
echo "[deploy] building ARMOR-SERVER"
copy_sources ARMOR-SERVER
( cd "$WORK/build/ARMOR-SERVER" && npm ci --no-audit --no-fund --loglevel=error && npm run typecheck && npm test && npm run build )
echo "[deploy] building ARMOR-STUDIO"
copy_sources ARMOR-STUDIO
( cd "$WORK/build/ARMOR-STUDIO" && npm ci --no-audit --no-fund --loglevel=error && npm run typecheck && npm test && npm run build )

mkdir -p "$WORK/release/server" "$WORK/release/studio/tools" "$WORK/release/scripts"
cp -r "$WORK/build/ARMOR-SERVER/dist" "$WORK/release/server/dist"
cp "$WORK/build/ARMOR-SERVER/package.json" "$WORK/build/ARMOR-SERVER/package-lock.json" "$WORK/release/server/"
cp -r "$WORK/build/ARMOR-STUDIO/dist" "$WORK/release/studio/dist"
cp "$WORK/build/ARMOR-STUDIO/tools/serve.mjs" "$WORK/release/studio/tools/"
cp "$ROOT/ARMOR-DEVOPS/scripts/install_cm5.sh" "$ROOT/ARMOR-DEVOPS/scripts/mqtt_identity.sh" "$WORK/release/scripts/"
tar -C "$WORK" -czf "$WORK/armor-$STAMP.tar.gz" release

echo "[deploy] sending the release to $USER_NAME@$HOST"
scp "${SCP_OPTS[@]}" -q "$WORK/armor-$STAMP.tar.gz" "$USER_NAME@$HOST:/tmp/armor-$STAMP.tar.gz"
ssh "${SSH_OPTS[@]}" "$USER_NAME@$HOST" "set -e; d=\$(mktemp -d); tar -mxzf /tmp/armor-$STAMP.tar.gz -C \$d; sudo bash \$d/release/scripts/install_cm5.sh --public-host $PUBLIC_HOST $APPLY$EXTRA; rm -rf \$d /tmp/armor-$STAMP.tar.gz"
