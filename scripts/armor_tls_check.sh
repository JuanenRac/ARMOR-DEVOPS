#!/usr/bin/env bash
# ARMOR-DEVOPS - check the HTTPS of the installation the way a phone will meet it, and print the text that pairs a phone with it.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
#
#   scripts/armor_tls_check.sh HOST [PORT] [ROOT_CERTIFICATE]
#
# It connects to HOST:PORT (443 when not given), reads the certificates the server presents and says, one line each:
#   TLS_REACHABLE   the server answered a TLS handshake
#   TLS_CHAIN       the chain is valid for HOST against the root certificate (the one given, else the system's own)
#   TLS_NOT_EXPIRING  the certificate of the server has more than 14 days left
#   TLS_PIN         the authority above the server's certificate is the one whose pin it prints (the key a phone pins the first time)
# and finally `armor-pin:HOST:<pin>`, the text to paste in the app (More > Security) or to put in a QR code. Exit status 0 only when every line passed.
# Only public certificates are read. Nothing is written.
set -euo pipefail
HOST="${1:-}"; PORT="${2:-443}"; ROOT="${3:-}"
[[ "$HOST" =~ ^[A-Za-z0-9]([A-Za-z0-9.-]{0,251}[A-Za-z0-9])?$ ]] || { echo "usage: armor_tls_check.sh HOST [PORT] [ROOT_CERTIFICATE]" >&2; exit 2; }
[[ "$PORT" =~ ^[0-9]{1,5}$ ]] || { echo "the port must be a number" >&2; exit 2; }
[[ -z "$ROOT" || -f "$ROOT" ]] || { echo "the root certificate $ROOT does not exist" >&2; exit 2; }
command -v openssl >/dev/null || { echo "openssl is needed" >&2; exit 2; }
WORK="$(mktemp -d)"; trap 'rm -rf -- "$WORK"' EXIT
FAILED=0
say() { echo "$1=$2 $3"; [[ "$2" == PASS ]] || FAILED=1; }
pin_of() { openssl x509 -in "$1" -noout -pubkey | openssl pkey -pubin -outform DER | openssl dgst -sha256 -binary | base64; }

if ! echo | timeout 15 openssl s_client -connect "$HOST:$PORT" -servername "$HOST" -showcerts >"$WORK/chain.txt" 2>"$WORK/err.txt" || ! grep -q "BEGIN CERTIFICATE" "$WORK/chain.txt"; then
  say TLS_REACHABLE FAIL "no TLS answer from $HOST:$PORT"; exit 1
fi
say TLS_REACHABLE PASS "$HOST:$PORT"
# the certificates of the chain, in the order they were presented (the server's own first)
awk -v dir="$WORK" '/BEGIN CERTIFICATE/{n++; f=sprintf("%s/cert%d.pem",dir,n)} f{print > f} /END CERTIFICATE/{f=""}' "$WORK/chain.txt"
COUNT="$(ls "$WORK"/cert*.pem | wc -l)"
VERIFY=(openssl verify -verify_hostname "$HOST")
[[ -z "$ROOT" ]] || VERIFY+=(-CAfile "$ROOT")
UNTRUSTED=(); for ((i = 2; i <= COUNT; i++)); do UNTRUSTED+=(-untrusted "$WORK/cert$i.pem"); done
if "${VERIFY[@]}" "${UNTRUSTED[@]}" "$WORK/cert1.pem" >"$WORK/verify.txt" 2>&1; then say TLS_CHAIN PASS "valid for $HOST"; else say TLS_CHAIN FAIL "$(tail -1 "$WORK/verify.txt")"; fi
if openssl x509 -in "$WORK/cert1.pem" -noout -checkend $((14 * 86400)) >/dev/null; then say TLS_NOT_EXPIRING PASS "$(openssl x509 -in "$WORK/cert1.pem" -noout -enddate | cut -d= -f2)"; else say TLS_NOT_EXPIRING FAIL "$(openssl x509 -in "$WORK/cert1.pem" -noout -enddate | cut -d= -f2)"; fi
# the key worth pinning is the authority's when the chain has one above the server's certificate, and the server's own when it stands alone (what the phone does)
if [[ -n "$ROOT" ]]; then AUTHORITY="$ROOT"; elif [[ "$COUNT" -gt 1 ]]; then AUTHORITY="$WORK/cert$COUNT.pem"; else AUTHORITY="$WORK/cert1.pem"; fi
PIN="$(pin_of "$AUTHORITY")"
if [[ -n "$ROOT" ]]; then
  # the authority given must be the one that signed what the server presents
  LAST="$WORK/cert$COUNT.pem"
  if [[ "$(pin_of "$LAST")" == "$PIN" ]] || openssl verify -CAfile "$ROOT" "${UNTRUSTED[@]}" "$WORK/cert1.pem" >/dev/null 2>&1; then say TLS_PIN PASS "$PIN"; else say TLS_PIN FAIL "the server is not signed by $ROOT"; fi
else
  say TLS_PIN PASS "$PIN"
fi
echo "armor-pin:$HOST:$PIN"
exit "$FAILED"
