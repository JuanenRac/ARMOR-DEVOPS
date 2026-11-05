#!/usr/bin/env bash
# ARMOR-DEVOPS - prints the SHA-256 fingerprint of the root certificate of the internal authority of the "lan-ca" profile (what the wall panel and the phone app pin).
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
#   scripts/armor_ca_fingerprint.sh                  # reads the certificate from the running proxy_lan container
#   scripts/armor_ca_fingerprint.sh /path/root.crt   # or from a copy of the file
#   --spki   prints instead the base64 SHA-256 of the public key of the authority (what the phone app pins)
#   --pem    prints instead the certificate itself (what the wall panel can hold as the end of the chain)
# Only the public certificate is read; the key of the authority is never touched. Without an option it prints the 64 hexadecimal digits of the SHA-256 of the certificate
# (upper case, no colons), which is what the wall panel pins as a fingerprint.
set -euo pipefail
MODE=fingerprint
if [[ "${1:-}" == "--spki" || "${1:-}" == "--pem" ]]; then MODE="${1#--}"; shift; fi
ROOT="/data/caddy/pki/authorities/local/root.crt"
if [[ $# -ge 1 ]]; then
  [[ -f "$1" ]] || { echo "no such file: $1" >&2; exit 1; }
  PEM="$(cat -- "$1")"
else
  command -v docker >/dev/null || { echo "docker is not installed; give the path of a copy of root.crt" >&2; exit 1; }
  PEM="$(docker compose --profile lan-ca exec -T proxy_lan cat "$ROOT")" || { echo "the proxy_lan container is not running (docker compose --profile lan-ca up -d)" >&2; exit 1; }
fi
command -v openssl >/dev/null || { echo "openssl is needed" >&2; exit 1; }
case "$MODE" in
  pem) printf '%s\n' "$PEM" | openssl x509 ;;
  spki) printf '%s\n' "$PEM" | openssl x509 -pubkey -noout | openssl pkey -pubin -outform DER | openssl dgst -sha256 -binary | base64 ;;
  *) printf '%s\n' "$PEM" | openssl x509 -noout -fingerprint -sha256 | sed 's/^.*=//; s/://g' ;;
esac
