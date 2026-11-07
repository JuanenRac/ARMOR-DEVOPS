#!/usr/bin/env bash
# ARMOR-DEVOPS - the service bench: the real server runs as an unprivileged user of a Debian container behind the real access list of the broker, and the updater's own tests run there too.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
#
# It is what the job "service-bench" of the workflow "DevOps container bench" runs inside a node:22-trixie image (Debian trixie is the release of the CM5; its arm64 processor, its
# kernel, systemd and its network are not there). /repo is this repository, /server a BUILT checkout of ARMOR-SERVER (dist/ and node_modules/), /updater a checkout of ARMOR-UPDATER:
#
#   docker run --rm -v "$PWD:/repo:ro" -v "$SERVER:/server:ro" -v "$UPDATER:/updater:ro" node:22-trixie bash /repo/scripts/service_bench.sh
#
# A green run says the server starts and works under a service account with the access list this repository ships and that the updater's tests pass on a Debian userland. It says
# nothing about the CM5 itself, about systemd (the unit is not run) or about the machine's resources. Nothing here has run on the CM5.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK="$(mktemp -d)"; chmod 0711 "$WORK"
PASSED=0; FAILED=0
BROKER_PID=""; SERVER_PID=""
trap '[[ -z "$SERVER_PID" ]] || kill "$SERVER_PID" 2>/dev/null; [[ -z "$BROKER_PID" ]] || kill "$BROKER_PID" 2>/dev/null; rm -rf -- "$WORK"' EXIT
ok() { PASSED=$((PASSED + 1)); echo "PASS $1"; }
bad() { FAILED=$((FAILED + 1)); echo "FAIL $1${2:+ - $2}"; }
check() { local name="$1"; shift; if "$@"; then ok "$name"; else bad "$name"; fi; }
token() { head -c 16 /dev/urandom | od -An -tx1 | tr -d ' \n'; }

[[ "$(id -u)" -eq 0 ]] || { echo "the service bench runs as root, inside a container" >&2; exit 2; }
apt-get update -qq >/dev/null && apt-get install -y -qq --no-install-recommends mosquitto mosquitto-clients curl python3 python3-pytest >/dev/null || { echo "could not install the tools" >&2; exit 2; }
getent group armor >/dev/null || groupadd --system armor
id armor >/dev/null 2>&1 || useradd --system --gid armor --home-dir /nonexistent --shell /usr/sbin/nologin armor

# ---- 1. The broker, with the server's block of the access list taken from the one source this repository has ----
export ARMOR_PREFIX="$WORK/prefix"
MQ="$ARMOR_PREFIX/etc/mosquitto"
mkdir -p "$MQ"
SERVER_PASSWORD="$(token)"
mosquitto_passwd -c -b "$MQ/passwd" armor-server "$SERVER_PASSWORD" >/dev/null 2>&1
{ echo "# Managed by scripts/mqtt_identity.sh; one block per identity."; echo "user armor-server"; cat "$HERE/armor_server.acl"; } >"$MQ/acl"
chown root:armor "$MQ/passwd" "$MQ/acl"; chmod 0640 "$MQ/passwd" "$MQ/acl"
PORT=28884
cat >"$MQ/mosquitto.conf" <<CONF
listener $PORT 127.0.0.1
allow_anonymous false
password_file $MQ/passwd
acl_file $MQ/acl
persistence false
user root
pid_file $WORK/mosquitto.pid
CONF
mkdir -p "$WORK/bin"
printf '#!/bin/sh\ncase "$1" in reload|restart) kill -HUP "$(cat "$BENCH_PID_FILE")" 2>/dev/null ;; esac\ntrue\n' >"$WORK/bin/systemctl"; chmod +x "$WORK/bin/systemctl"
export PATH="$WORK/bin:$PATH" BENCH_PID_FILE="$WORK/mosquitto.pid"
start_broker() {
  mosquitto -c "$MQ/mosquitto.conf" >>"$WORK/mosquitto.log" 2>&1 &
  BROKER_PID=$!
  for _ in $(seq 1 50); do (exec 3<>"/dev/tcp/127.0.0.1/$PORT") 2>/dev/null && break; sleep 0.2; done
}
start_broker
ID_OUT="$(bash "$HERE/mqtt_identity.sh" add node n1 2>&1)"
NODE_PASSWORD="$(sed -n 's/^password: //p' <<<"$ID_OUT")"
if [[ -n "$NODE_PASSWORD" ]]; then ok "identity: a node identity is made for the bench"; else bad "identity: a node identity is made for the bench"; fi
sleep 1

# ---- 2. The server as the service account: its data directory is its own, the files it makes are private ----
DATA="$WORK/data"; mkdir -p "$DATA"; chown armor:armor "$DATA"; chmod 0700 "$DATA"
OPERATOR="$(token)"
cat >"$WORK/server.env" <<ENV
ARMOR_INGEST_TOKEN=$(token)
ARMOR_CONTROL_TOKEN=$(token)
ARMOR_OPERATOR_TOKEN=$OPERATOR
ARMOR_CAMERA_CONFIG_KEY=$(token)
ARMOR_STUDIO_USERNAME=admin
ARMOR_STUDIO_PASSWORD=$(token)
ARMOR_DATA_DIR=$DATA
ARMOR_HOST=127.0.0.1
ARMOR_PORT=28080
ARMOR_TZ=UTC
ARMOR_MQTT_URL=mqtt://127.0.0.1:$PORT
ARMOR_MQTT_USERNAME=armor-server
ARMOR_MQTT_PASSWORD=$SERVER_PASSWORD
ENV
chown root:armor "$WORK/server.env"; chmod 0640 "$WORK/server.env"
SERVER_VARS="$(grep -v '^#' "$WORK/server.env" | tr '\n' ' ')"
# shellcheck disable=SC2086
( cd /server && exec setpriv --reuid=armor --regid=armor --clear-groups --no-new-privs env -i PATH="$PATH" HOME=/nonexistent $SERVER_VARS "$(command -v node)" dist/server.mjs ) >"$WORK/server.log" 2>&1 &
SERVER_PID=$!
UP=0; for _ in $(seq 1 100); do curl -fs http://127.0.0.1:28080/healthz >/dev/null 2>&1 && { UP=1; break; }; sleep 0.3; done
if [[ "$UP" -eq 1 ]]; then ok "service: the server starts as the unprivileged user and answers /healthz"; else bad "service: the server starts as the unprivileged user and answers /healthz" "$(tail -c 400 "$WORK/server.log")"; fi
check "service: the process runs as the service account, not as root" bash -c "ps -eo user,args | grep -v grep | grep 'dist/server.mjs' | grep -q '^armor'"

# ---- 3. The server hears a node through the real access list ----
status() { curl -fs -H "Authorization: Bearer $OPERATOR" http://127.0.0.1:28080/api/v1/status; }
mosquitto_pub -h 127.0.0.1 -p "$PORT" -u field-node-n1 -P "$NODE_PASSWORD" -t armor/node/n1/telemetry -m "{\"node_id\":\"n1\",\"timestamp_ms\":$(date +%s%3N),\"lux\":250.5,\"targets\":[]}" >/dev/null 2>&1
SEEN=0; for _ in $(seq 1 30); do status | grep -q '"n1"' && { SEEN=1; break; }; sleep 0.3; done
if [[ "$SEEN" -eq 1 ]]; then ok "broker road: a node message through the access list reaches the server's status"; else bad "broker road: a node message through the access list reaches the server's status" "$(tail -c 900 "$WORK/server.log")"; fi
mosquitto_pub -h 127.0.0.1 -p "$PORT" -u field-node-n1 -P "$NODE_PASSWORD" -t armor/node/other/telemetry -m '{"node_id":"other","timestamp_ms":1000,"lux":1,"targets":[]}' >/dev/null 2>&1
sleep 1.5
check "broker road: a node that writes on another node's topic is not heard" bash -c "! curl -fs -H 'Authorization: Bearer $OPERATOR' http://127.0.0.1:28080/api/v1/status | grep -q '\"other\"'"

# ---- 4. Failures played on purpose: the broker goes away and comes back; the data directory stays private ----
kill "$BROKER_PID" 2>/dev/null; wait "$BROKER_PID" 2>/dev/null
sleep 1
check "failure: the server keeps answering while the broker is gone" curl -fs http://127.0.0.1:28080/healthz -o /dev/null
start_broker
mosquitto_pub -h 127.0.0.1 -p "$PORT" -u field-node-n1 -P "$NODE_PASSWORD" -t armor/node/n1/telemetry -m "{\"node_id\":\"n1\",\"timestamp_ms\":$(date +%s%3N),\"lux\":260.5,\"targets\":[]}" >/dev/null 2>&1
BACK=0; for _ in $(seq 1 60); do status | grep -q '260.5' && { BACK=1; break; }; sleep 0.5; done
if [[ "$BACK" -eq 1 ]]; then ok "failure: the server reconnects by itself when the broker comes back"; else bad "failure: the server reconnects by itself when the broker comes back" "$(status | head -c 500) // $(tail -c 900 "$WORK/server.log")"; fi
check "service: nothing in the data directory is readable by others" bash -c "! find '$DATA' -perm /o+rwx | grep -q ."
kill "$SERVER_PID" 2>/dev/null; wait "$SERVER_PID" 2>/dev/null; SERVER_PID=""

# ---- 5. The updater's own tests on a Debian userland, as the unprivileged user ----
if [[ -d /updater/tests ]]; then
  UOUT="$(cd /updater && setpriv --reuid=armor --regid=armor --clear-groups env -i PATH="$PATH" HOME=/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/updater/src python3 -m pytest -q -p no:cacheprovider /updater/tests 2>&1 | tail -4)"
  if grep -Eq "[0-9]+ passed" <<<"$UOUT" && ! grep -Eq "[0-9]+ (failed|error)" <<<"$UOUT"; then ok "updater: its tests pass on Debian as the unprivileged user ($(grep -Eo '[0-9]+ passed' <<<"$UOUT"))"; else bad "updater: its tests pass on Debian as the unprivileged user" "$UOUT"; fi
else
  echo "SKIP updater: no checkout at /updater"
fi

echo "$PASSED checks, $FAILED failures"
if [[ $FAILED -eq 0 ]]; then echo "DEVOPS_SERVICE_BENCH=PASS"; exit 0; fi
echo "DEVOPS_SERVICE_BENCH=FAIL"; exit 1
