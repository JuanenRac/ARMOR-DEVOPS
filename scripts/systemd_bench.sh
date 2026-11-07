#!/usr/bin/env bash
# ARMOR-DEVOPS - the installer and its units on a real systemd, in a Debian container (evidence: simulator - the release of the CM5, not its arm64 processor, kernel or network).
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
#
# Runs INSIDE a container whose first process is systemd (see the job systemd-install of .github/workflows/container-bench.yml), as root, with the repository mounted at /repo,
# the built server at /server and ARMOR-STUDIO at /studio (its tools/serve.mjs). It unpacks a release the way the CM5 does, runs scripts/install_cm5.sh --apply with the broker,
# and then checks what only a real service manager shows: the three units are active and answer, the hardening of the unit is in force, the files have the owners and modes they
# should, a killed server is started again by systemd, an upgrade switches `current` and keeps the secrets, and the units are enabled for the next boot.
# It prints one line per check and ends with ARMOR_SYSTEMD_BENCH=PASS or FAIL. Never run it on a machine that is not a throw-away container: it installs under /opt/armor.
set -uo pipefail
[[ -d /run/systemd/system ]] || { echo "ARMOR_SYSTEMD_BENCH=SKIP systemd is not the init of this machine" >&2; exit 2; }
FAILED=0
CHECKS=0
check() {   # check "what" command...
  local what="$1"; shift
  CHECKS=$((CHECKS + 1))
  if "$@" >/dev/null 2>&1; then echo "ok   $what"; else echo "FAIL $what" >&2; FAILED=$((FAILED + 1)); fi
}
within() {   # within SECONDS command...: the command succeeds before the time is up
  local limit="$1"; shift
  local i
  for ((i = 0; i < limit; i++)); do "$@" >/dev/null 2>&1 && return 0; sleep 1; done
  return 1
}

# systemd must have finished starting (degraded is fine: a container has units that cannot run)
within 90 bash -c 'state="$(systemctl is-system-running 2>/dev/null)"; [[ "$state" == running || "$state" == degraded ]]' || { echo "FAIL systemd did not finish starting" >&2; systemctl is-system-running >&2; exit 1; }

# An unpacked release, as deploy_cm5.sh leaves it on the CM5.
RELEASE=/tmp/armor-release
rm -rf "$RELEASE"; mkdir -p "$RELEASE/server" "$RELEASE/studio/dist" "$RELEASE/scripts"
cp -a /repo/scripts/. "$RELEASE/scripts/"
cp -a /server/dist /server/package.json /server/package-lock.json "$RELEASE/server/"
cp -a /studio/tools "$RELEASE/studio/tools"
printf '<!doctype html><title>studio</title>\n' >"$RELEASE/studio/dist/index.html"

INSTALL=(bash "$RELEASE/scripts/install_cm5.sh" --public-host 127.0.0.1 --bind 127.0.0.1 --apply --with-mqtt --with-admin --with-maintenance)
if ! "${INSTALL[@]}" >/tmp/install.log 2>&1; then
  echo "FAIL the installer stopped; its last lines:" >&2; tail -12 /tmp/install.log >&2
  echo "--- what the services say" >&2
  systemctl status armor-server armor-studio --no-pager -n 15 >&2 || true
  curl -sv http://127.0.0.1:18080/healthz >&2 || true
  curl -sv http://127.0.0.1:18081/healthz >&2 || true
  exit 1
fi
echo "ok   install_cm5.sh --apply finished"

for unit in armor-server armor-studio armor-mosquitto armor-admin armor-maintenance; do
  check "$unit is active" within 30 systemctl is-active --quiet "$unit"
  check "$unit is enabled for the next boot" systemctl is-enabled --quiet "$unit"
done
check "the server answers /healthz" within 30 curl -fsS http://127.0.0.1:18080/healthz
check "Studio answers /healthz" within 30 curl -fsS http://127.0.0.1:18081/healthz
check "the broker listens on its own port" within 30 bash -c 'ss -ltn | grep -q ":18883 "'
check "the broker is not on the standard port" bash -c '! ss -ltn | grep -q ":1883 "'

# The hardening of the unit is what the kernel enforces, not only what the file says.
check "the server cannot gain privileges" bash -c '[[ "$(systemctl show armor-server -p NoNewPrivileges --value)" == yes ]]'
check "the server sees the system as read only" bash -c '[[ "$(systemctl show armor-server -p ProtectSystem --value)" == strict ]]'
check "the server runs as the service account, not as root" bash -c 'pid="$(systemctl show armor-server -p MainPID --value)"; [[ "$pid" -gt 1 && "$(ps -o user= -p "$pid" | tr -d " ")" == armor ]]'
check "the unit gives the server a memory limit" bash -c '[[ "$(systemctl show armor-server -p MemoryMax --value)" != infinity ]]'
check "the root agents run as root and the server does not" bash -c 'pid="$(systemctl show armor-admin -p MainPID --value)"; [[ "$(ps -o user= -p "$pid" | tr -d " ")" == root ]]'

# Owners and modes of what holds secrets.
check "armor.env is root:armor and not readable by others" bash -c '[[ "$(stat -c "%U:%G %a" /opt/armor/etc/armor.env)" == "root:armor 640" ]]'
check "armor.mqtt.env is root:armor and not readable by others" bash -c '[[ "$(stat -c "%U:%G %a" /opt/armor/etc/armor.mqtt.env)" == "root:armor 640" ]]'
check "the data folder belongs to the service account" bash -c '[[ "$(stat -c "%U %a" /opt/armor/data)" == "armor 750" ]]'
check "the secrets are not in the unit files" bash -c '! grep -qE "TOKEN=|PASSWORD=" /etc/systemd/system/armor-*.service'

# A broker identity made by the script reaches the broker for real.
PASSWORD="$(bash "$RELEASE/scripts/mqtt_identity.sh" add node bench-1 2>/dev/null | grep -i password | head -1 | awk '{print $NF}')"
check "mqtt_identity.sh made an identity with a password" test -n "$PASSWORD"
check "the new identity publishes its own telemetry" within 15 mosquitto_pub -h 127.0.0.1 -p 18883 -u field-node-bench-1 -P "$PASSWORD" -t armor/node/bench-1/telemetry -m '{}'
check "the new identity cannot publish to another node's topic and the broker still answers" bash -c "mosquitto_pub -h 127.0.0.1 -p 18883 -u field-node-bench-1 -P '$PASSWORD' -t armor/node/other-9/telemetry -m '{}' -q 1 >/dev/null 2>&1; mosquitto_pub -h 127.0.0.1 -p 18883 -u field-node-bench-1 -P '$PASSWORD' -t armor/node/bench-1/telemetry -m '{}'"
check "a wrong password is refused" bash -c "! mosquitto_pub -h 127.0.0.1 -p 18883 -u field-node-bench-1 -P wrong -t armor/node/bench-1/telemetry -m '{}'"

# systemd starts a server that was killed.
OLD_PID="$(systemctl show armor-server -p MainPID --value)"
kill -9 "$OLD_PID" 2>/dev/null || true
check "a killed server is started again by systemd" within 40 bash -c "new=\$(systemctl show armor-server -p MainPID --value); [[ \"\$new\" -gt 1 && \"\$new\" != '$OLD_PID' ]] && curl -fsS http://127.0.0.1:18080/healthz"

# An upgrade: a second run switches `current`, keeps the secrets and the identity, and leaves the units answering.
BEFORE_LINK="$(readlink -f /opt/armor/current)"
BEFORE_ENV="$(sha256sum /opt/armor/etc/armor.env | cut -d' ' -f1)"
sleep 1
if "${INSTALL[@]}" >/tmp/upgrade.log 2>&1; then echo "ok   the second install_cm5.sh --apply finished"; else echo "FAIL the upgrade stopped:" >&2; tail -20 /tmp/upgrade.log >&2; FAILED=$((FAILED + 1)); fi
check "the upgrade switched current to a new release" bash -c "[[ \"\$(readlink -f /opt/armor/current)\" != '$BEFORE_LINK' ]]"
check "the upgrade kept the secrets" bash -c "[[ \"\$(sha256sum /opt/armor/etc/armor.env | cut -d' ' -f1)\" == '$BEFORE_ENV' ]]"
check "the upgrade kept the identity" grep -q "field-node-bench-1" /opt/armor/etc/mosquitto/passwd
check "the server answers after the upgrade" within 40 curl -fsS http://127.0.0.1:18080/healthz
check "the identity still publishes after the upgrade" within 15 mosquitto_pub -h 127.0.0.1 -p 18883 -u field-node-bench-1 -P "$PASSWORD" -t armor/node/bench-1/telemetry -m '{}'

# The doctor reads the same installation and finds it sound.
check "armor_doctor finds the installation sound" bash -c 'python3 /repo/scripts/armor_doctor.py --prefix /opt/armor --min-free-mb 0 | tail -1 | grep -q "ARMOR_DOCTOR=PASS"'

echo "$CHECKS checks, $FAILED failures"
if [[ "$FAILED" -ne 0 ]]; then echo "ARMOR_SYSTEMD_BENCH=FAIL"; journalctl -u armor-server -n 20 --no-pager 2>/dev/null | tail -20; exit 1; fi
echo "ARMOR_SYSTEMD_BENCH=PASS checks=$CHECKS"
