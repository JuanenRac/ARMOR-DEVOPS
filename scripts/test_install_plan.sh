#!/usr/bin/env bash
# ARMOR-DEVOPS - tests of the checks install_cm5.sh makes before it changes anything (its dry run): what it refuses and what the plan says.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
# Nothing is installed: without --apply the installer only prints its plan. A copy of the script runs inside a temporary "unpacked release", with a prefix that does not exist.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf -- "$WORK"' EXIT
RELEASE="$WORK/release"
mkdir -p "$RELEASE/scripts" "$RELEASE/server/dist" "$RELEASE/studio/dist"
cp "$HERE/install_cm5.sh" "$HERE/mqtt_identity.sh" "$RELEASE/scripts/"
: >"$RELEASE/server/dist/server.mjs"
: >"$RELEASE/studio/dist/index.html"
PREFIX="/opt/armor-plan-test-$$"
PORTS=(--server-port 28080 --studio-port 28081)
FAILED=0
CHECKS=0

run() { bash "$RELEASE/scripts/install_cm5.sh" "$@" 2>&1; }

# expect STATUS "text that must be in the output" -- arguments...
expect() {
  local want_status="$1" want_text="$2"; shift 3
  local out status
  out="$(run "$@")"; status=$?
  CHECKS=$((CHECKS + 1))
  if [[ "$status" -ne "$want_status" ]]; then echo "FAIL (exit $status, wanted $want_status): $*" >&2; echo "$out" | tail -3 >&2; FAILED=$((FAILED + 1)); return; fi
  if ! grep -qF -- "$want_text" <<<"$out"; then echo "FAIL (missing \"$want_text\"): $*" >&2; echo "$out" | tail -3 >&2; FAILED=$((FAILED + 1)); fi
}
# never "text" -- arguments...: the output must NOT contain the text
never() {
  local text="$1"; shift 2
  local out
  out="$(run "$@")"
  CHECKS=$((CHECKS + 1))
  if grep -qF -- "$text" <<<"$out"; then echo "FAIL (\"$text\" should not be there): $*" >&2; FAILED=$((FAILED + 1)); fi
}

# ---- the command line
expect 0 "Usage: install_cm5.sh" -- --help
expect 2 "unknown option: --nonsense" -- --nonsense
expect 1 "--public-host is required" -- "${PORTS[@]}" --prefix "$PREFIX"
expect 1 "host name or IPv4 address" -- --public-host 'a b' --prefix "$PREFIX" "${PORTS[@]}"
expect 1 "host name or IPv4 address" -- --public-host 'host;reboot' --prefix "$PREFIX" "${PORTS[@]}"
expect 1 "host name or IPv4 address" -- --public-host '$(id)' --prefix "$PREFIX" "${PORTS[@]}"

# ---- ports
expect 1 "ports must be numbers between 1024 and 65535" -- --public-host 192.168.0.5 --prefix "$PREFIX" --server-port 80 --studio-port 28081
expect 1 "ports must be numbers between 1024 and 65535" -- --public-host 192.168.0.5 --prefix "$PREFIX" --server-port 28080 --studio-port 70000
expect 1 "ports must be numbers between 1024 and 65535" -- --public-host 192.168.0.5 --prefix "$PREFIX" --server-port abc --studio-port 28081
expect 1 "must differ" -- --public-host 192.168.0.5 --prefix "$PREFIX" --server-port 28080 --studio-port 28080
expect 1 "--mqtt-port must be a number" -- --public-host 192.168.0.5 --prefix "$PREFIX" "${PORTS[@]}" --with-mqtt --mqtt-port 12
expect 1 "must not be 1883 or another A.R.M.O.R. port" -- --public-host 192.168.0.5 --prefix "$PREFIX" "${PORTS[@]}" --with-mqtt --mqtt-port 1883
expect 1 "must not be 1883 or another A.R.M.O.R. port" -- --public-host 192.168.0.5 --prefix "$PREFIX" "${PORTS[@]}" --with-mqtt --mqtt-port 28080

# ---- where it may install
for bad in /tmp/armor /opt /opt/ /opt/a/b /opt/a\ b /etc /opt/../etc; do
  expect 1 "--prefix must be one directory directly under /opt" -- --public-host 192.168.0.5 "${PORTS[@]}" --prefix "$bad"
done

# ---- other ways in
expect 1 "--also-reach must look like" -- --public-host 192.168.0.5 --prefix "$PREFIX" "${PORTS[@]}" --also-reach 'javascript:alert(1)'
expect 1 "--also-reach must look like" -- --public-host 192.168.0.5 --prefix "$PREFIX" "${PORTS[@]}" --also-reach 'http://a.example:1'
expect 1 "--also-reach must look like" -- --public-host 192.168.0.5 --prefix "$PREFIX" "${PORTS[@]}" --also-reach 'http://a.example:1=ftp://b.example:2'
expect 0 "also reachable : http://203.0.113.7:2601 (server http://203.0.113.7:2600)" -- --public-host 192.168.0.5 --prefix "$PREFIX" "${PORTS[@]}" --also-reach http://203.0.113.7:2601=http://203.0.113.7:2600
# the same pair given twice is listed once
out="$(run --public-host 192.168.0.5 --prefix "$PREFIX" "${PORTS[@]}" --also-reach http://x.example:1=http://x.example:2 --also-reach http://x.example:1=http://x.example:2)"
CHECKS=$((CHECKS + 1))
[[ "$(grep -c 'also reachable' <<<"$out")" -eq 1 ]] || { echo "FAIL: a repeated --also-reach pair is listed twice" >&2; FAILED=$((FAILED + 1)); }

# ---- the release must be complete
mv "$RELEASE/server/dist/server.mjs" "$WORK/server.mjs.away"
expect 1 "run this from an unpacked release" -- --public-host 192.168.0.5 --prefix "$PREFIX" "${PORTS[@]}"
mv "$WORK/server.mjs.away" "$RELEASE/server/dist/server.mjs"
expect 1 "needed by the admin agent" -- --public-host 192.168.0.5 --prefix "$PREFIX" "${PORTS[@]}" --with-admin
expect 1 "needed by the maintenance helper" -- --public-host 192.168.0.5 --prefix "$PREFIX" "${PORTS[@]}" --with-maintenance
mv "$RELEASE/scripts/mqtt_identity.sh" "$WORK/mqtt_identity.sh.away"
expect 1 "the release has no scripts/mqtt_identity.sh" -- --public-host 192.168.0.5 --prefix "$PREFIX" "${PORTS[@]}"
mv "$WORK/mqtt_identity.sh.away" "$RELEASE/scripts/mqtt_identity.sh"

# ---- the plan, and that a dry run changes nothing
expect 0 "browser opens  : http://192.168.0.5:28081" -- --public-host 192.168.0.5 --prefix "$PREFIX" "${PORTS[@]}"
expect 0 "armor-server   : 0.0.0.0:28080" -- --public-host 192.168.0.5 --prefix "$PREFIX" "${PORTS[@]}"
expect 0 "dry run only - add --apply to install" -- --public-host 192.168.0.5 --prefix "$PREFIX" "${PORTS[@]}"
expect 0 "other software : untouched" -- --public-host my-bench.local --prefix "$PREFIX" "${PORTS[@]}"
expect 0 "armor-server   : 127.0.0.1:28080" -- --public-host 192.168.0.5 --prefix "$PREFIX" "${PORTS[@]}" --bind 127.0.0.1
expect 0 "armor-mosquitto: 0.0.0.0:18883" -- --public-host 192.168.0.5 --prefix "$PREFIX" "${PORTS[@]}" --with-mqtt
expect 0 "armor-mosquitto: 0.0.0.0:28883" -- --public-host 192.168.0.5 --prefix "$PREFIX" "${PORTS[@]}" --with-mqtt --mqtt-port 28883
expect 0 "armor-voice    : 127.0.0.1:18090" -- --public-host 192.168.0.5 --prefix "$PREFIX" "${PORTS[@]}" --with-voice
expect 0 "armor-backup   : daily, encrypted" -- --public-host 192.168.0.5 --prefix "$PREFIX" "${PORTS[@]}" --with-backup
cp "$HERE/armor_admin_agent.py" "$HERE/armor_maintenance_agent.py" "$RELEASE/scripts/"
expect 0 "armor-admin    : root agent on /run/armor-admin.sock" -- --public-host 192.168.0.5 --prefix "$PREFIX" "${PORTS[@]}" --with-admin
expect 0 "armor-maintenance: root helper" -- --public-host 192.168.0.5 --prefix "$PREFIX" "${PORTS[@]}" --with-maintenance
never "armor-mosquitto" -- --public-host 192.168.0.5 --prefix "$PREFIX" "${PORTS[@]}"
never "armor-voice" -- --public-host 192.168.0.5 --prefix "$PREFIX" "${PORTS[@]}"
never "armor-admin" -- --public-host 192.168.0.5 --prefix "$PREFIX" "${PORTS[@]}"
CHECKS=$((CHECKS + 1))
[[ ! -e "$PREFIX" ]] || { echo "FAIL: a dry run created $PREFIX" >&2; FAILED=$((FAILED + 1)); }

echo "$CHECKS checks, $FAILED failures"
if [[ "$FAILED" -ne 0 ]]; then exit 1; fi
echo "ARMOR_DEVOPS_INSTALL_PLAN=PASS"
