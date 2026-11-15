#!/usr/bin/env bash
# ARMOR-DEVOPS - test of armor_tls_check.sh against a throwaway authority and a TLS server of openssl on the loopback: a good chain passes and prints the pin of the authority, a server signed by
# another authority, a wrong name and a closed port fail, and the pin printed is the one the maintenance agent computes for the same file.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK="$(mktemp -d)"; PIDS=()
cleanup() { for pid in "${PIDS[@]:-}"; do [[ -n "$pid" ]] && kill "$pid" 2>/dev/null || true; done; rm -rf -- "$WORK"; }
trap cleanup EXIT
fail() { echo "FAIL: $*" >&2; exit 1; }
command -v openssl >/dev/null || { echo "ARMOR_TLS_CHECK=SKIP no openssl"; exit 0; }
cd "$WORK"
make_ca() { openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes -keyout "$1.key" -out "$1.pem" -days 3650 -subj "/CN=$1" -addext "basicConstraints=critical,CA:TRUE" -addext "keyUsage=critical,keyCertSign,cRLSign" 2>/dev/null; }
make_leaf() { # authority name -> leaf.<name>.pem signed by the authority, valid for localhost
  openssl req -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes -keyout "$2.key" -out "$2.csr" -subj "/CN=localhost" 2>/dev/null
  printf 'subjectAltName=DNS:localhost\nbasicConstraints=CA:FALSE\n' >"$2.ext"
  openssl x509 -req -in "$2.csr" -CA "$1.pem" -CAkey "$1.key" -CAcreateserial -out "$2.pem" -days "${3:-90}" -extfile "$2.ext" 2>/dev/null; }
serve() { # port leaf authority-file
  openssl s_server -accept "$1" -cert "$2.pem" -key "$2.key" -cert_chain "$3.pem" -www >/dev/null 2>&1 & PIDS+=("$!"); sleep 1; }
make_ca home-authority; make_ca other-authority
make_leaf home-authority leaf-home; make_leaf other-authority leaf-other; make_leaf home-authority leaf-short 5
PORT=$((20000 + RANDOM % 20000))
serve "$PORT" leaf-home home-authority
EXPECTED="$(openssl x509 -in home-authority.pem -noout -pubkey | openssl pkey -pubin -outform DER | openssl dgst -sha256 -binary | base64)"

OUT="$(bash "$HERE/armor_tls_check.sh" localhost "$PORT" "$WORK/home-authority.pem")" || fail "a good chain was refused: $OUT"
for line in TLS_REACHABLE=PASS TLS_CHAIN=PASS TLS_NOT_EXPIRING=PASS TLS_PIN=PASS; do grep -q "^$line" <<<"$OUT" || fail "missing $line in: $OUT"; done
grep -qx "armor-pin:localhost:$EXPECTED" <<<"$OUT" || fail "the pin printed is not the pin of the authority: $OUT"
if grep -q "PRIVATE" <<<"$OUT"; then fail "a key was printed"; fi

# a wrong name is a failure of the chain
if bash "$HERE/armor_tls_check.sh" 127.0.0.1 "$PORT" "$WORK/home-authority.pem" >"$WORK/out2.txt" 2>&1; then fail "a name the certificate is not for passed"; fi
grep -q "^TLS_CHAIN=FAIL" "$WORK/out2.txt" || fail "the chain should have failed for a wrong name: $(cat "$WORK/out2.txt")"

# a server signed by another authority does not pass against ours
PORT2=$((PORT + 1)); serve "$PORT2" leaf-other other-authority
if bash "$HERE/armor_tls_check.sh" localhost "$PORT2" "$WORK/home-authority.pem" >"$WORK/out3.txt" 2>&1; then fail "a server of another authority passed"; fi
grep -q "^TLS_CHAIN=FAIL" "$WORK/out3.txt" || fail "the chain of another authority should have failed"

# a certificate that ends within two weeks is a warning that fails the check
PORT3=$((PORT + 2)); serve "$PORT3" leaf-short home-authority
if bash "$HERE/armor_tls_check.sh" localhost "$PORT3" "$WORK/home-authority.pem" >"$WORK/out4.txt" 2>&1; then fail "a certificate with five days left passed"; fi
grep -q "^TLS_NOT_EXPIRING=FAIL" "$WORK/out4.txt" || fail "the expiry should have been reported"

# a closed port, and arguments that are not a host name
if bash "$HERE/armor_tls_check.sh" localhost 1 "$WORK/home-authority.pem" >"$WORK/out5.txt" 2>&1; then fail "a closed port passed"; fi
grep -q "^TLS_REACHABLE=FAIL" "$WORK/out5.txt" || fail "an unreachable server should be said"
if bash "$HERE/armor_tls_check.sh" 'bad host;rm' >/dev/null 2>&1; then fail "a bad host name was accepted"; fi
if bash "$HERE/armor_tls_check.sh" localhost abc >/dev/null 2>&1; then fail "a bad port was accepted"; fi
echo "ARMOR_TLS_CHECK=PASS a good chain prints the pin of the authority; a wrong name, another authority, a nearly expired certificate and a closed port fail"
