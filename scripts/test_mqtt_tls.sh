#!/usr/bin/env bash
# ARMOR-DEVOPS - tests of scripts/armor_mqtt_tls.sh: the authority and the certificate it makes (checked with OpenSSL itself, including a real TLS handshake), what it writes to the broker's
# configuration, that it is idempotent, that the key of the authority stays out of the broker's folder, and that remove puts files aside instead of deleting them. It needs OpenSSL, no
# root, no broker and no network, and changes nothing outside a temporary folder.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TLS="$HERE/armor_mqtt_tls.sh"
PASSED=0; FAILED=0
ok() { PASSED=$((PASSED + 1)); }
bad() { FAILED=$((FAILED + 1)); echo "FAIL: $*"; }
expect_in()  { grep -qF -- "$2" <<<"$1" && ok || bad "expected: $2"; }
expect_out() { grep -qF -- "$2" <<<"$1" && bad "did not expect: $2" || ok; }
refused() { local out; out="$("$TLS" "$@" 2>&1)"; local code=$?; [[ $code -eq 2 ]] && ok || bad "should have been refused (code $code): $*  -> $out"; }

if ! command -v openssl >/dev/null; then echo "armor_mqtt_tls tests: skipped (OpenSSL is not installed)"; exit 0; fi

TMP="$(mktemp -d)"; SERVER_PID=""
trap '[[ -z "$SERVER_PID" ]] || kill "$SERVER_PID" 2>/dev/null; rm -rf "$TMP"' EXIT
mkdir -p "$TMP/mosquitto"
cat >"$TMP/mosquitto/mosquitto.conf" <<'EOF'
# A.R.M.O.R. broker: authenticated only, its own port, its own files.
listener 18883 192.168.0.180
allow_anonymous false
password_file /x/passwd
EOF
printf 'ARMOR_MQTT_URL=mqtt://192.168.0.180:18883\nARMOR_MQTT_USERNAME=armor-server\nARMOR_MQTT_PASSWORD=s3cret\n' >"$TMP/armor.mqtt.env"
export ARMOR_MQTT_DIR="$TMP/mosquitto" ARMOR_MQTT_CA_DIR="$TMP/mqtt-ca" ARMOR_MQTT_ENV_FILE="$TMP/armor.mqtt.env" ARMOR_MQTT_TLS_NOSYSTEMD=1 ARMOR_SERVICE_USER="$(id -un)"
unset OPENSSL_CONF
ARGS=(--no-detect --name broker.example.test --ip 192.168.0.180)
ls_tree() { find "$TMP/mosquitto" "$TMP/mqtt-ca" -type f 2>/dev/null | sort; }
mode_of() { stat -c %a "$1"; }

# the plan writes nothing and says what it would vouch for
BEFORE="$(ls_tree)"
PLAN="$("$TLS" plan "${ARGS[@]}")"
expect_in "$PLAN" "DNS:broker.example.test"
expect_in "$PLAN" "IP:192.168.0.180"
expect_in "$PLAN" "DNS:localhost"
expect_in "$PLAN" "port 8883"
expect_in "$PLAN" "a new authority"
[[ "$(ls_tree)" == "$BEFORE" && ! -e "$TMP/mqtt-ca" ]] && ok || bad "plan must not write anything"

# what it refuses
refused plan --name "bad host"
refused plan --name "x;reboot"
refused plan --ip 999.1.1.1
refused plan --ip not-an-ip
refused plan --port 0
refused plan --port 70000
refused plan --frobnicate
refused frobnicate
refused server-tls maybe
refused server-tls
refused export-ca                                  # before setup

# setup
OUT="$("$TLS" setup "${ARGS[@]}" 2>&1)"; CODE=$?
[[ $CODE -eq 0 ]] && ok || bad "setup failed ($CODE): $OUT"
expect_in "$OUT" "made the authority"
expect_in "$OUT" "made the certificate of the broker"
expect_in "$OUT" "plain port was not touched"
for f in "$TMP/mqtt-ca/ca.key" "$TMP/mqtt-ca/ca.pem" "$TMP/mosquitto/tls/server.key" "$TMP/mosquitto/tls/server.pem" "$TMP/mosquitto/tls/ca.pem" "$TMP/mosquitto/conf.d/armor-tls.conf"; do [[ -s "$f" ]] && ok || bad "missing: $f"; done
# the private key of the authority is private and is not in the folder of the broker
[[ "$(mode_of "$TMP/mqtt-ca")" == "700" ]] && ok || bad "the authority's folder must be 0700 (is $(mode_of "$TMP/mqtt-ca"))"
[[ "$(mode_of "$TMP/mqtt-ca/ca.key")" == "600" ]] && ok || bad "the authority's key must be 0600"
[[ "$(mode_of "$TMP/mosquitto/tls/server.key")" == "640" ]] && ok || bad "the broker's key must be 0640"
[[ "$(mode_of "$TMP/mosquitto/tls")" == "750" ]] && ok || bad "the broker's folder must be 0750"
grep -rl "PRIVATE KEY" "$TMP/mosquitto" | grep -v "server.key" >/dev/null && bad "a private key outside server.key in the broker's folder" || ok
grep -q "BEGIN PRIVATE KEY\|BEGIN EC PRIVATE KEY" "$TMP/mosquitto/tls/ca.pem" && bad "the copy of the authority in the broker's folder must be the certificate only" || ok
# the configuration: a second listener with TLS, the plain one untouched, the folder read by the main file
CONF="$(cat "$TMP/mosquitto/conf.d/armor-tls.conf")"
expect_in "$CONF" "listener 8883 192.168.0.180"
expect_in "$CONF" "certfile $TMP/mosquitto/tls/server.pem"
expect_in "$CONF" "keyfile $TMP/mosquitto/tls/server.key"
expect_in "$CONF" "tls_version tlsv1.2"
expect_out "$CONF" "allow_anonymous"
MAIN="$(cat "$TMP/mosquitto/mosquitto.conf")"
expect_in "$MAIN" "listener 18883 192.168.0.180"
expect_in "$MAIN" "include_dir $TMP/mosquitto/conf.d"
[[ "$(head -n 5 "$TMP/mosquitto/mosquitto.conf")" == "$(printf '# A.R.M.O.R. broker: authenticated only, its own port, its own files.\nlistener 18883 192.168.0.180\nallow_anonymous false\npassword_file /x/passwd\n')"* ]] && ok || bad "the plain part of mosquitto.conf changed"
# the certificates are what they should be, according to OpenSSL
CA="$TMP/mqtt-ca/ca.pem"; SRV="$TMP/mosquitto/tls/server.pem"
CA_TEXT="$(openssl x509 -in "$CA" -noout -text)"; SRV_TEXT="$(openssl x509 -in "$SRV" -noout -text)"
expect_in "$CA_TEXT" "CA:TRUE"
expect_in "$SRV_TEXT" "CA:FALSE"
expect_in "$SRV_TEXT" "TLS Web Server Authentication"
expect_in "$SRV_TEXT" "DNS:broker.example.test"
expect_in "$SRV_TEXT" "IP Address:192.168.0.180"
expect_in "$SRV_TEXT" "prime256v1"
openssl verify -CAfile "$CA" -verify_hostname broker.example.test "$SRV" >/dev/null 2>&1 && ok || bad "the certificate must verify for its name"
openssl verify -CAfile "$CA" -verify_ip 192.168.0.180 "$SRV" >/dev/null 2>&1 && ok || bad "the certificate must verify for its address"
openssl verify -CAfile "$CA" -verify_ip 10.0.0.9 "$SRV" >/dev/null 2>&1 && bad "the certificate must NOT verify for another address" || ok
openssl verify -CAfile "$CA" -verify_hostname other.example.test "$SRV" >/dev/null 2>&1 && bad "the certificate must NOT verify for another name" || ok
openssl x509 -in "$CA" -noout -checkend $((86400 * 3000)) >/dev/null 2>&1 && ok || bad "the authority should last years"
openssl x509 -in "$SRV" -noout -checkend $((86400 * 700)) >/dev/null 2>&1 && ok || bad "the broker certificate should last about two years"
openssl x509 -in "$SRV" -noout -checkend $((86400 * 800)) >/dev/null 2>&1 && bad "the broker certificate should not last more than about two years" || ok
# it is valid from a day back (a node whose clock is a little behind still accepts it)
openssl x509 -in "$SRV" -noout -startdate | sed 's/^notBefore=//' | { read -r d; [[ "$(date -u -d "$d" +%s)" -lt "$(date -u +%s)" ]]; } && ok || bad "the certificate must already be valid"
# another authority does not verify it
OTHER="$TMP/other"; mkdir -p "$OTHER"
openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes -keyout "$OTHER/k.pem" -out "$OTHER/ca.pem" -days 2 -subj "/CN=other" >/dev/null 2>&1
openssl verify -CAfile "$OTHER/ca.pem" "$SRV" >/dev/null 2>&1 && bad "another authority must not verify the broker certificate" || ok

# a real TLS handshake: a server with the broker's files, a client that trusts only the authority (and checks the name)
if command -v timeout >/dev/null && openssl s_server -help 2>&1 | grep -q -- "-cert"; then
  PORT_TEST=$((20000 + RANDOM % 20000))
  openssl s_server -accept "$PORT_TEST" -cert "$SRV" -key "$TMP/mosquitto/tls/server.key" -www -quiet >/dev/null 2>&1 &
  SERVER_PID=$!
  sleep 1
  GOOD="$(echo | timeout 10 openssl s_client -connect "127.0.0.1:$PORT_TEST" -CAfile "$CA" -verify_hostname broker.example.test -verify_return_error 2>&1)"
  expect_in "$GOOD" "Verify return code: 0 (ok)"
  WRONG_CA="$(echo | timeout 10 openssl s_client -connect "127.0.0.1:$PORT_TEST" -CAfile "$OTHER/ca.pem" -verify_return_error 2>&1)"
  expect_out "$WRONG_CA" "Verify return code: 0 (ok)"
  WRONG_NAME="$(echo | timeout 10 openssl s_client -connect "127.0.0.1:$PORT_TEST" -CAfile "$CA" -verify_hostname intruder.example.test -verify_return_error 2>&1)"
  expect_out "$WRONG_NAME" "Verify return code: 0 (ok)"
  kill "$SERVER_PID" 2>/dev/null; SERVER_PID=""
else
  echo "(the handshake test needs openssl s_server and timeout: skipped)"
fi

# idempotent: a second setup changes nothing that matters
FP1="$(openssl x509 -in "$CA" -noout -fingerprint -sha256)"; SUM1="$(sha256sum "$SRV" | cut -d' ' -f1)"
AGAIN="$("$TLS" setup "${ARGS[@]}" 2>&1)"
expect_in "$AGAIN" "the authority already exists: kept"
expect_in "$AGAIN" "the certificate of the broker is still good: kept"
[[ "$(openssl x509 -in "$CA" -noout -fingerprint -sha256)" == "$FP1" ]] && ok || bad "the authority must not change"
[[ "$(sha256sum "$SRV" | cut -d' ' -f1)" == "$SUM1" ]] && ok || bad "the broker certificate must not change when nothing did"
[[ "$(grep -c '^include_dir' "$TMP/mosquitto/mosquitto.conf")" == "1" ]] && ok || bad "the include line must be written once"
[[ "$(grep -c '^listener 8883' "$TMP/mosquitto/conf.d/armor-tls.conf")" == "1" ]] && ok || bad "one TLS listener"

# a new address: a new broker certificate from the SAME authority (the nodes are not touched)
NEW="$("$TLS" setup "${ARGS[@]}" --ip 192.168.0.200 2>&1)"
expect_in "$NEW" "made the certificate of the broker"
expect_in "$NEW" "the authority already exists: kept"
expect_in "$(openssl x509 -in "$SRV" -noout -text)" "IP Address:192.168.0.200"
[[ "$(openssl x509 -in "$CA" -noout -fingerprint -sha256)" == "$FP1" ]] && ok || bad "the authority must stay when the addresses change"
openssl verify -CAfile "$CA" -verify_ip 192.168.0.200 "$SRV" >/dev/null 2>&1 && ok || bad "the renewed certificate must verify"
# the same list again: nothing to renew; --force renews anyway
expect_in "$("$TLS" setup "${ARGS[@]}" --ip 192.168.0.200 2>&1)" "still good: kept"
SUM2="$(sha256sum "$SRV" | cut -d' ' -f1)"
"$TLS" setup "${ARGS[@]}" --ip 192.168.0.200 --force >/dev/null 2>&1
[[ "$(sha256sum "$SRV" | cut -d' ' -f1)" != "$SUM2" ]] && ok || bad "--force must make a new certificate"

# the status says what is there and shows no key
STATUS="$("$TLS" status 2>&1)"
expect_in "$STATUS" "sha256 fingerprint"
expect_in "$STATUS" "vouches for"
expect_in "$STATUS" "listener: 8883"
expect_in "$STATUS" "plain port"
expect_out "$STATUS" "PRIVATE"

# export-ca: the certificate, public
EXPORT="$("$TLS" export-ca)"
[[ "$EXPORT" == "$(cat "$CA")" ]] && ok || bad "export-ca must print the certificate of the authority"
expect_out "$EXPORT" "PRIVATE"
expect_in "$EXPORT" "BEGIN CERTIFICATE"
"$TLS" export-ca --out "$TMP/exported.pem" >/dev/null && [[ "$(cat "$TMP/exported.pem")" == "$EXPORT" ]] && ok || bad "export-ca --out"
[[ "$(wc -c <"$CA")" -le 2048 ]] && ok || bad "the certificate of the authority must fit the 2 KB of the nodes"

# the server of this machine
"$TLS" server-tls on >/dev/null 2>&1
ENVTXT="$(cat "$TMP/armor.mqtt.env")"
expect_in "$ENVTXT" "ARMOR_MQTT_URL=mqtts://localhost:8883"
expect_in "$ENVTXT" "ARMOR_MQTT_CA_FILE=$TMP/mosquitto/tls/ca.pem"
expect_in "$ENVTXT" "ARMOR_MQTT_PASSWORD=s3cret"
expect_in "$("$TLS" status 2>&1)" "the server of this machine uses TLS"
"$TLS" server-tls on >/dev/null 2>&1
[[ "$(grep -c '^ARMOR_MQTT_CA_FILE=' "$TMP/armor.mqtt.env")" == "1" ]] && ok || bad "the CA line must be written once"
"$TLS" server-tls off >/dev/null 2>&1
ENVTXT="$(cat "$TMP/armor.mqtt.env")"
expect_in "$ENVTXT" "ARMOR_MQTT_URL=mqtt://192.168.0.180:18883"
expect_out "$ENVTXT" "ARMOR_MQTT_CA_FILE"
expect_in "$ENVTXT" "ARMOR_MQTT_PASSWORD=s3cret"

# remove: the door is closed, the files are put aside (nothing deleted), the authority is kept
"$TLS" server-tls on >/dev/null 2>&1
RM="$("$TLS" remove 2>&1)"
expect_in "$RM" "nothing was deleted"
expect_in "$RM" "the authority was kept"
[[ ! -e "$TMP/mosquitto/conf.d/armor-tls.conf" && ! -e "$TMP/mosquitto/tls" ]] && ok || bad "remove must take the listener and the broker files away"
ls "$TMP/mosquitto/conf.d/" | grep -q 'armor-tls.conf.removed' && ok || bad "the configuration must be put aside"
ls -d "$TMP/mosquitto"/tls.removed.* >/dev/null 2>&1 && [[ -s "$(ls -d "$TMP/mosquitto"/tls.removed.* | head -n1)/server.key" ]] && ok || bad "the broker key must be put aside, not deleted"
[[ -s "$TMP/mqtt-ca/ca.key" ]] && ok || bad "the authority must be kept by remove"
expect_out "$(cat "$TMP/armor.mqtt.env")" "mqtts://"          # the server went back to the plain port by itself
expect_in "$("$TLS" status 2>&1)" "listener: none"
# setting up again reuses the authority: the nodes that trust it keep working
sleep 1
"$TLS" setup "${ARGS[@]}" >/dev/null 2>&1
[[ "$(openssl x509 -in "$CA" -noout -fingerprint -sha256)" == "$FP1" ]] && ok || bad "setup after remove must reuse the authority"
# forgetting the authority puts it aside as well
"$TLS" remove --forget-ca >/dev/null 2>&1
[[ ! -e "$TMP/mqtt-ca" ]] && ls -d "$TMP"/mqtt-ca.removed.* >/dev/null 2>&1 && ok || bad "--forget-ca must put the authority aside"
refused export-ca

echo "armor_mqtt_tls tests: $PASSED passed, $FAILED failed"
[[ "$FAILED" -eq 0 ]]
