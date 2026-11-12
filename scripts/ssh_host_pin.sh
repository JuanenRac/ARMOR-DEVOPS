#!/usr/bin/env bash
# =============================================================================
# A.R.M.O.R. - ARMOR-DEVOPS/scripts/ssh_host_pin.sh
# Pins the SSH host key of the machine a deploy connects to: it asks the host for its keys,
# compares the SHA-256 fingerprint of each with the one the administrator gave, and writes ONLY
# the key that matches to a known_hosts file, so the connection that follows can run with
# StrictHostKeyChecking=yes and cannot talk to another machine.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D)
# GPL-3.0-or-later - see LICENSE
# =============================================================================
# Usage: ssh_host_pin.sh HOST PORT SHA256:FINGERPRINT KNOWN_HOSTS_FILE
# Exit: 0 pinned; 2 bad arguments; 3 the host showed no key with that fingerprint (nothing written).
set -euo pipefail
HOST="${1:-}"; PORT="${2:-22}"; WANT="${3:-}"; OUT="${4:-}"
[[ "$HOST" =~ ^[A-Za-z0-9._:-]+$ ]] || { echo "the host must be a host name or an address" >&2; exit 2; }
[[ "$PORT" =~ ^[0-9]{1,5}$ ]] || { echo "the port must be a number" >&2; exit 2; }
[[ "$WANT" =~ ^SHA256:[A-Za-z0-9+/]{43}=?$ ]] || { echo "the fingerprint must look like SHA256:<43 base64 characters>" >&2; exit 2; }
[[ -n "$OUT" ]] || { echo "usage: ssh_host_pin.sh HOST PORT SHA256:FINGERPRINT KNOWN_HOSTS_FILE" >&2; exit 2; }
WANT="${WANT%=}"
SCANNED="$(ssh-keyscan -T 10 -p "$PORT" "$HOST" 2>/dev/null || true)"
: > "$OUT"
FOUND=""
while IFS= read -r line; do
  [[ -z "$line" || "$line" == \#* ]] && continue
  got="$(printf '%s\n' "$line" | ssh-keygen -lf - -E sha256 2>/dev/null | awk '{print $2}' || true)"
  if [[ "${got%=}" == "$WANT" ]]; then printf '%s\n' "$line" >> "$OUT"; FOUND=1; fi
done <<<"$SCANNED"
if [[ -z "$FOUND" ]]; then
  : > "$OUT"
  echo "the host $HOST showed no SSH key with the fingerprint $WANT: not connecting" >&2
  exit 3
fi
echo "[deploy] the SSH host key of $HOST matches the fingerprint you gave"
