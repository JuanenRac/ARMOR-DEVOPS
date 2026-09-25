#!/usr/bin/env bash
# =============================================================================
# A.R.M.O.R. - ARMOR-DEVOPS/scripts/install_cm5.sh
# Installs A.R.M.O.R. on a Raspberry Pi CM5 test bench as a fully separate
# project, next to (and without touching) any other software on the machine.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D)
# GPL-3.0-or-later - see LICENSE
# =============================================================================
# What it does, and only this:
#   * a dedicated system user `armor` (no login shell, no sudo)
#   * everything under /opt/armor (releases, data, etc)
#   * two systemd units, armor-server and armor-studio, on their own ports
#   * optionally (--with-mqtt) a third unit, armor-mosquitto: A.R.M.O.R.'s own MQTT
#     broker on its own port, with its own passwords and ACL, never the system broker
#   * resource limits so the bench can never starve the other software
# What it never does: edit, restart or read anything belonging to another
# project, open a port outside the two below, or touch the firewall.
#
# Usage (as root, from the unpacked release):
#   install_cm5.sh --public-host 192.168.0.180           # dry run: prints the plan
#   install_cm5.sh --public-host 192.168.0.180 --apply   # installs / upgrades
#   install_cm5.sh --public-host 192.168.0.180 --apply --with-mqtt   # also the broker
set -euo pipefail

PREFIX="/opt/armor"
SERVICE_USER="armor"
SERVER_PORT="18080"
STUDIO_PORT="18081"
MQTT_PORT="18883"
WITH_MQTT=0
BIND_ADDRESS="0.0.0.0"
PUBLIC_HOST=""
APPLY=0
ALSO_REACH=(); FORGET_REACH=0
RELEASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
  cat <<EOF
Usage: install_cm5.sh --public-host HOST [--apply] [--server-port N] [--studio-port N]
                      [--also-reach STUDIO_URL=SERVER_URL] [--forget-reach] [--bind ADDRESS] [--prefix DIR]
  --public-host  address the browser will use to reach this machine (required)
  --apply        actually install; without it the plan is only printed
  --also-reach   another way to reach this machine, for example from the Internet through a router:
                 --also-reach http://203.0.113.7:2601=http://203.0.113.7:2600 (Studio address = server address).
                 Repeatable, and remembered for the next installs; the browser is then allowed to log in that way too
  --forget-reach forget every address given with --also-reach before now
  --server-port  ARMOR-SERVER port (default ${SERVER_PORT})
  --studio-port  ARMOR-STUDIO port (default ${STUDIO_PORT})
  --with-mqtt    also run A.R.M.O.R.'s own MQTT broker (needs the mosquitto package installed)
  --mqtt-port    broker port (default ${MQTT_PORT}; never the standard 1883, which other software may use)
  --bind         address all services listen on (default ${BIND_ADDRESS})
  --prefix       install directory (default ${PREFIX})
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --public-host) PUBLIC_HOST="${2:-}"; shift 2 ;;
    --apply) APPLY=1; shift ;;
    --server-port) SERVER_PORT="${2:-}"; shift 2 ;;
    --studio-port) STUDIO_PORT="${2:-}"; shift 2 ;;
    --also-reach) ALSO_REACH+=("${2:-}"); shift 2 ;;
    --forget-reach) FORGET_REACH=1; shift ;;
    --with-mqtt) WITH_MQTT=1; shift ;;
    --mqtt-port) MQTT_PORT="${2:-}"; shift 2 ;;
    --bind) BIND_ADDRESS="${2:-}"; shift 2 ;;
    --prefix) PREFIX="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

fail() { echo "ERROR: $*" >&2; exit 1; }
# An upgrade of an install that already has the broker keeps it, whether or not the flag is repeated.
[[ -f "$PREFIX/etc/armor.mqtt.env" ]] && WITH_MQTT=1
say()  { echo "[armor-install] $*"; }

[[ -n "$PUBLIC_HOST" ]] || { usage >&2; fail "--public-host is required"; }
[[ "$PUBLIC_HOST" =~ ^[A-Za-z0-9.-]+$ ]] || fail "--public-host must be a host name or IPv4 address"
# Other ways in (a public address behind a router): remembered in armor.reach, one "studio=server" pair per line.
ORIGIN_PATTERN='https?://[A-Za-z0-9.-]+(:[0-9]{1,5})?'
REACH_FILE="$PREFIX/etc/armor.reach"
REACH_PAIRS=()
if [[ "$FORGET_REACH" -eq 0 && -f "$REACH_FILE" ]]; then
  while IFS= read -r line; do [[ "$line" =~ ^${ORIGIN_PATTERN}=${ORIGIN_PATTERN}$ ]] && REACH_PAIRS+=("$line"); done <"$REACH_FILE"
fi
for pair in "${ALSO_REACH[@]}"; do
  [[ "$pair" =~ ^${ORIGIN_PATTERN}=${ORIGIN_PATTERN}$ ]] || fail "--also-reach must look like http://HOST:PORT=http://HOST:PORT (Studio address = server address), not: $pair"
  REACH_PAIRS+=("$pair")
done
STUDIO_ORIGINS="http://$PUBLIC_HOST:$STUDIO_PORT"; SERVER_ORIGINS="http://$PUBLIC_HOST:$SERVER_PORT"; REACH_UNIQUE=()
for pair in "${REACH_PAIRS[@]}"; do
  studio="${pair%%=*}"; server="${pair#*=}"
  [[ ",$STUDIO_ORIGINS," == *",$studio,"* ]] || STUDIO_ORIGINS="$STUDIO_ORIGINS,$studio"
  [[ ",$SERVER_ORIGINS," == *",$server,"* ]] || SERVER_ORIGINS="$SERVER_ORIGINS,$server"
  [[ " ${REACH_UNIQUE[*]:-} " == *" $pair "* ]] || REACH_UNIQUE+=("$pair")
done
for port in "$SERVER_PORT" "$STUDIO_PORT"; do
  [[ "$port" =~ ^[0-9]+$ && "$port" -ge 1024 && "$port" -le 65535 ]] || fail "ports must be numbers between 1024 and 65535"
done
[[ "$SERVER_PORT" != "$STUDIO_PORT" ]] || fail "the server and studio ports must differ"
if [[ "$WITH_MQTT" -eq 1 ]]; then
  [[ "$MQTT_PORT" =~ ^[0-9]+$ && "$MQTT_PORT" -ge 1024 && "$MQTT_PORT" -le 65535 ]] || fail "--mqtt-port must be a number between 1024 and 65535"
  [[ "$MQTT_PORT" != "1883" && "$MQTT_PORT" != "$SERVER_PORT" && "$MQTT_PORT" != "$STUDIO_PORT" ]] || fail "--mqtt-port must not be 1883 or another A.R.M.O.R. port"
fi
[[ "$PREFIX" == /opt/* && "$PREFIX" != "/opt/hydra-umc"* ]] || fail "--prefix must be under /opt and never inside a HYDRA-UMC directory"
# An existing, non-empty prefix must already be this project's own (an upgrade), never someone else's directory.
if [[ -d "$PREFIX" && -n "$(ls -A "$PREFIX" 2>/dev/null)" && ! -f "$PREFIX/etc/armor.network.env" ]]; then
  fail "$PREFIX already exists and is not an A.R.M.O.R. install; choose another --prefix"
fi
[[ -f "$RELEASE_DIR/server/dist/server.mjs" && -f "$RELEASE_DIR/studio/dist/index.html" ]] || fail "run this from an unpacked release (server/dist and studio/dist are missing)"

port_owner() { ss -tlnpH "sport = :$1" 2>/dev/null | head -1; }
# A port may already be in use only by this project's own unit (an upgrade).
check_port() {
  local port="$1" unit="$2" owner
  owner="$(port_owner "$port")"
  [[ -z "$owner" ]] && return 0
  systemctl is-active --quiet "$unit" 2>/dev/null && return 0
  fail "port $port is already in use by another program: $owner"
}
check_port "$SERVER_PORT" armor-server
check_port "$STUDIO_PORT" armor-studio
[[ "$WITH_MQTT" -ne 1 ]] || check_port "$MQTT_PORT" armor-mosquitto

say "plan"
say "  install prefix : $PREFIX (owner: $SERVICE_USER)"
say "  armor-server   : $BIND_ADDRESS:$SERVER_PORT"
say "  armor-studio   : $BIND_ADDRESS:$STUDIO_PORT"
say "  browser opens  : http://$PUBLIC_HOST:$STUDIO_PORT"
for pair in "${REACH_UNIQUE[@]}"; do say "  also reachable : ${pair%%=*} (server ${pair#*=})"; done
[[ "$WITH_MQTT" -ne 1 ]] || say "  armor-mosquitto: $BIND_ADDRESS:$MQTT_PORT (own broker, own passwords)"
say "  other software : untouched"
if [[ "$APPLY" -ne 1 ]]; then say "dry run only - add --apply to install"; exit 0; fi

[[ "$(id -u)" -eq 0 ]] || fail "--apply must run as root"
command -v node >/dev/null || fail "Node.js is required"
command -v npm >/dev/null || fail "npm is required"
if [[ "$WITH_MQTT" -eq 1 ]]; then
  command -v mosquitto >/dev/null || fail "--with-mqtt needs the mosquitto package (its own service is not used; install it with your package manager)"
  command -v mosquitto_passwd >/dev/null || fail "--with-mqtt needs mosquitto_passwd (package mosquitto or mosquitto-clients)"
fi

STAMP="$(date +%Y%m%d-%H%M%S)"
RELEASE="$PREFIX/releases/$STAMP"

if ! id "$SERVICE_USER" >/dev/null 2>&1; then
  say "creating system user $SERVICE_USER"
  useradd --system --home-dir "$PREFIX" --shell /usr/sbin/nologin --no-create-home "$SERVICE_USER"
fi
install -d -o root -g "$SERVICE_USER" -m 0750 "$PREFIX" "$PREFIX/etc"
install -d -o "$SERVICE_USER" -g "$SERVICE_USER" -m 0750 "$PREFIX/releases" "$PREFIX/data" "$PREFIX/.npm"

say "installing release $STAMP"
install -d -o "$SERVICE_USER" -g "$SERVICE_USER" -m 0750 "$RELEASE" "$RELEASE/server" "$RELEASE/studio"
cp -a "$RELEASE_DIR/server/." "$RELEASE/server/"
cp -a "$RELEASE_DIR/studio/." "$RELEASE/studio/"
chown -R "$SERVICE_USER:$SERVICE_USER" "$RELEASE"
say "installing server dependencies (production only)"
sudo -u "$SERVICE_USER" env HOME="$PREFIX" npm_config_cache="$PREFIX/.npm" \
  npm --prefix "$RELEASE/server" ci --omit=dev --ignore-scripts --no-audit --no-fund --loglevel=error

ENV_FILE="$PREFIX/etc/armor.env"
random() { head -c "$1" /dev/urandom | base64 | tr -d '\n=+/' | head -c "$2"; }
if [[ ! -f "$ENV_FILE" ]]; then
  say "creating $ENV_FILE with new random secrets (kept across upgrades)"
  umask 0137
  cat >"$ENV_FILE" <<EOF
# A.R.M.O.R. test-bench environment. Generated once; never committed or printed.
ARMOR_INGEST_TOKEN=$(random 64 43)
ARMOR_CONTROL_TOKEN=$(random 64 43)
ARMOR_OPERATOR_TOKEN=$(random 64 43)
ARMOR_CAMERA_CONFIG_KEY=$(random 96 64)
ARMOR_STUDIO_USERNAME=admin
ARMOR_STUDIO_PASSWORD=$(random 48 32)
EOF
  chown "root:$SERVICE_USER" "$ENV_FILE"; chmod 0640 "$ENV_FILE"
fi

# Live video and captures need FFmpeg; when it is installed the server is pointed at it, and it gets more memory.
FFMPEG_BIN="$(command -v ffmpeg || true)"
FFMPEG_ENV_LINE=""; SERVER_MEMORY="384M"
if [[ -n "$FFMPEG_BIN" ]]; then FFMPEG_ENV_LINE="ARMOR_FFMPEG_PATH=$FFMPEG_BIN"; SERVER_MEMORY="768M"; say "FFmpeg found at $FFMPEG_BIN: live video enabled"; else say "FFmpeg not found: live video stays disabled (apt install ffmpeg, then run this again)"; fi

# Settings that follow this install (ports, host) live in their own file so a
# re-run can change them without touching the secrets above.
cat >"$PREFIX/etc/armor.network.env" <<EOF
ARMOR_HOST=$BIND_ADDRESS
ARMOR_PORT=$SERVER_PORT
ARMOR_STUDIO_ORIGIN=$STUDIO_ORIGINS
ARMOR_DATA_DIR=$PREFIX/data
ARMOR_STUDIO_HOST=$BIND_ADDRESS
ARMOR_STUDIO_PORT=$STUDIO_PORT
ARMOR_SERVER_ORIGIN=$SERVER_ORIGINS
${FFMPEG_ENV_LINE}
EOF
chown "root:$SERVICE_USER" "$PREFIX/etc/armor.network.env"; chmod 0640 "$PREFIX/etc/armor.network.env"
if [[ ${#REACH_UNIQUE[@]} -gt 0 ]]; then printf '%s\n' "${REACH_UNIQUE[@]}" >"$REACH_FILE"; chown "root:$SERVICE_USER" "$REACH_FILE"; chmod 0640 "$REACH_FILE"; else rm -f "$REACH_FILE"; fi

MQTT_ENV_LINE=""
if [[ "$WITH_MQTT" -eq 1 ]]; then
  say "configuring A.R.M.O.R.'s own MQTT broker on port $MQTT_PORT"
  MQ="$PREFIX/etc/mosquitto"
  install -d -o "$SERVICE_USER" -g "$SERVICE_USER" -m 0750 "$MQ" "$PREFIX/data/mqtt"
  if [[ ! -f "$PREFIX/etc/armor.mqtt.env" ]]; then
    SERVER_MQTT_PASSWORD="$(random 48 32)"
    ( umask 0177; : >"$MQ/passwd"; )
    mosquitto_passwd -b "$MQ/passwd" armor-server "$SERVER_MQTT_PASSWORD" >/dev/null
    cat >"$MQ/acl" <<'ACL'
# Managed by scripts/mqtt_identity.sh; one block per identity.
user armor-server
topic read armor/node/+/telemetry
topic read armor/node/+/health
topic write armor/node/+/command
topic write armor/server/alert
topic readwrite armor/device/#
ACL
    chown "$SERVICE_USER:$SERVICE_USER" "$MQ/passwd" "$MQ/acl"; chmod 0600 "$MQ/passwd" "$MQ/acl"
    ( umask 0137; printf 'ARMOR_MQTT_URL=mqtt://127.0.0.1:%s\nARMOR_MQTT_USERNAME=armor-server\nARMOR_MQTT_PASSWORD=%s\n' "$MQTT_PORT" "$SERVER_MQTT_PASSWORD" >"$PREFIX/etc/armor.mqtt.env" )
    chown "root:$SERVICE_USER" "$PREFIX/etc/armor.mqtt.env"; chmod 0640 "$PREFIX/etc/armor.mqtt.env"
  fi
  # An install made before devices existed: let the server listen on, and command, the devices' topics too.
  grep -qx 'topic readwrite armor/device/#' "$MQ/acl" || sed -i '0,/^topic write armor\/server\/alert$/s//topic write armor\/server\/alert\ntopic readwrite armor\/device\/#/' "$MQ/acl"
  cat >"$MQ/mosquitto.conf" <<EOF
# A.R.M.O.R. broker: authenticated only, its own port, its own files.
listener $MQTT_PORT $BIND_ADDRESS
allow_anonymous false
password_file $MQ/passwd
acl_file $MQ/acl
persistence true
persistence_location $PREFIX/data/mqtt/
log_dest stderr
connection_messages true
EOF
  chown "$SERVICE_USER:$SERVICE_USER" "$MQ/mosquitto.conf"; chmod 0640 "$MQ/mosquitto.conf"
  MQTT_ENV_LINE="EnvironmentFile=$PREFIX/etc/armor.mqtt.env"
fi

ln -sfn "$RELEASE" "$PREFIX/current.new" && mv -Tf "$PREFIX/current.new" "$PREFIX/current"

HARDENING="NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
PrivateDevices=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictSUIDSGID=true
LockPersonality=true
RestrictNamespaces=true
# AF_NETLINK is needed by Node to list network interfaces (camera discovery).
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6 AF_NETLINK
CapabilityBoundingSet=
SystemCallArchitectures=native
UMask=0077
# The bench must never take resources from the software it shares the machine with.
Nice=10
CPUWeight=20
IOWeight=20"

cat >/etc/systemd/system/armor-server.service <<EOF
[Unit]
Description=A.R.M.O.R. server (test bench)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$PREFIX/current/server
EnvironmentFile=$ENV_FILE
EnvironmentFile=$PREFIX/etc/armor.network.env
$MQTT_ENV_LINE
ExecStart=$(command -v node) $PREFIX/current/server/dist/server.mjs
Restart=on-failure
RestartSec=3
MemoryMax=$SERVER_MEMORY
TasksMax=128
ReadWritePaths=$PREFIX/data
$HARDENING

[Install]
WantedBy=multi-user.target
EOF

cat >/etc/systemd/system/armor-studio.service <<EOF
[Unit]
Description=A.R.M.O.R. Studio static host (test bench)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$PREFIX/current/studio
EnvironmentFile=$PREFIX/etc/armor.network.env
Environment=ARMOR_STUDIO_DIST=$PREFIX/current/studio/dist
ExecStart=$(command -v node) $PREFIX/current/studio/tools/serve.mjs
Restart=on-failure
RestartSec=3
MemoryMax=96M
TasksMax=32
$HARDENING

[Install]
WantedBy=multi-user.target
EOF

if [[ "$WITH_MQTT" -eq 1 ]]; then
  cat >/etc/systemd/system/armor-mosquitto.service <<EOF
[Unit]
Description=A.R.M.O.R. MQTT broker (test bench)
After=network-online.target
Wants=network-online.target
Before=armor-server.service

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_USER
ExecStart=$(command -v mosquitto) -c $PREFIX/etc/mosquitto/mosquitto.conf
ExecReload=/bin/kill -HUP \$MAINPID
Restart=on-failure
RestartSec=3
MemoryMax=96M
TasksMax=64
ReadWritePaths=$PREFIX/data/mqtt
$HARDENING

[Install]
WantedBy=multi-user.target
EOF
fi

systemctl daemon-reload
systemctl enable armor-server armor-studio >/dev/null
if [[ "$WITH_MQTT" -eq 1 ]]; then
  systemctl enable armor-mosquitto >/dev/null
  systemctl restart armor-mosquitto
fi
systemctl restart armor-server armor-studio

say "waiting for the services"
ok=0
for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:$SERVER_PORT/healthz" >/dev/null 2>&1 && curl -fsS "http://127.0.0.1:$STUDIO_PORT/healthz" >/dev/null 2>&1; then ok=1; break; fi
  sleep 1
done
if [[ "$ok" -ne 1 ]]; then
  journalctl -u armor-server -u armor-studio -n 30 --no-pager >&2 || true
  fail "the services did not become healthy"
fi

# Keep the four newest releases; older ones are moved aside, never deleted.
mkdir -p "$PREFIX/releases-old"
ls -1dt "$PREFIX"/releases/*/ 2>/dev/null | tail -n +5 | while read -r old; do mv "$old" "$PREFIX/releases-old/" || true; done

say "A.R.M.O.R. is running"
say "  Studio : http://$PUBLIC_HOST:$STUDIO_PORT"
say "  Server : http://$PUBLIC_HOST:$SERVER_PORT/healthz"
[[ "$WITH_MQTT" -ne 1 ]] || say "  Broker : mqtt://$PUBLIC_HOST:$MQTT_PORT (add devices with scripts/mqtt_identity.sh)"
say "  Studio login user 'admin'; its password is in $ENV_FILE (ARMOR_STUDIO_PASSWORD), readable by root"
