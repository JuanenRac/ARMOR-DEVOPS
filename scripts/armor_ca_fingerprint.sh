#!/usr/bin/env bash
# ARMOR-DEVOPS - prints the SHA-256 fingerprint of the root certificate of the internal authority of the "lan-ca" profile (what the wall panel and the phone app pin).
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
#   scripts/armor_ca_fingerprint.sh                  # reads the certificate from the running proxy_lan container
#   scripts/armor_ca_fingerprint.sh /path/root.crt   # or from a copy of the file
# Only the public certificate is read; the key of the authority is never touched. Prints the 64 hexadecimal digits, upper case, no colons.
set -euo pipefail
ROOT="/data/caddy/pki/authorities/local/root.crt"
if [[ $# -ge 1 ]]; then
  [[ -f "$1" ]] || { echo "no such file: $1" >&2; exit 1; }
  PEM="$(cat -- "$1")"
else
  command -v docker >/dev/null || { echo "docker is not installed; give the path of a copy of root.crt" >&2; exit 1; }
  PEM="$(docker compose --profile lan-ca exec -T proxy_lan cat "$ROOT")" || { echo "the proxy_lan container is not running (docker compose --profile lan-ca up -d)" >&2; exit 1; }
fi
command -v openssl >/dev/null || { echo "openssl is needed" >&2; exit 1; }
printf '%s\n' "$PEM" | openssl x509 -noout -fingerprint -sha256 | sed 's/^.*=//; s/://g'
