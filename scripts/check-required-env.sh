#!/usr/bin/env bash
# ARMOR-DEVOPS - validate the deployment variables in .env without printing a secret.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
# With --remote it also refuses what is not acceptable when the installation is reached from the Internet: an origin that is not https, an insecure cookie, a server that does not
# trust the proxy in front of it, a disarm without the PIN, a broker published on every address or on a public one, and a short or common administrator password.
set -euo pipefail
REMOTE=0
case "${1:-}" in
  "") ;;
  --remote) REMOTE=1 ;;
  *) echo "Usage: check-required-env.sh [--remote]" >&2; exit 2 ;;
esac
cd "$(dirname "${BASH_SOURCE[0]}")/.."
[[ -f .env ]] || { echo "ERROR: .env is missing; run scripts/generate_secrets.sh" >&2; exit 2; }

read_value() { grep -E "^$1=" .env | head -1 | cut -d= -f2- || true; }   # a missing variable is an empty value, said below, not the end of the script
status=0
for variable in ARMOR_INGEST_TOKEN ARMOR_CONTROL_TOKEN ARMOR_OPERATOR_TOKEN ARMOR_CAMERA_CONFIG_KEY ARMOR_STUDIO_PASSWORD ARMOR_MQTT_PASSWORD; do
  value="$(read_value "$variable")"
  if [[ -z "$value" || "$value" == replace-with-* ]]; then
    echo "ERROR: $variable is not set" >&2; status=2
  elif [[ "$variable" == ARMOR_STUDIO_PASSWORD && ${#value} -lt 12 ]] || [[ "$variable" != ARMOR_STUDIO_PASSWORD && ${#value} -lt 24 ]]; then
    echo "ERROR: $variable is too short" >&2; status=2
  fi
done
# The three tokens must all differ: one leaked credential must not open every door.
tokens="$(for v in ARMOR_INGEST_TOKEN ARMOR_CONTROL_TOKEN ARMOR_OPERATOR_TOKEN; do read_value "$v"; done | sort | uniq -d)"
[[ -z "$tokens" ]] || { echo "ERROR: the ingest, control and operator tokens must all be different" >&2; status=2; }
[[ -f secrets/mqtt.password && -f secrets/mqtt.acl ]] || { echo "ERROR: secrets/mqtt.password and secrets/mqtt.acl are required" >&2; status=2; }
# The private key of the broker's TLS door (docker-compose.tls.yml mounts it as a secret, keeping the mode and the owner it has on this machine). Readable by every user of the
# machine is refused. The broker starts as root and drops to its own user (1883) afterwards: a key only root can read is read at the start, but not again when the broker
# reloads its certificate, so that is said (a note, because it still starts). A mode that cannot be read (a file system without modes) says nothing.
KEY=secrets/mqtt_server.key
if [[ -f "$KEY" ]]; then
  mode="$(stat -c %a "$KEY" 2>/dev/null || true)"; owner="$(stat -c %u "$KEY" 2>/dev/null || true)"
  if [[ "$mode" =~ ^[0-7]{3,4}$ ]]; then
    if (( (8#$mode & 8#004) != 0 )); then
      echo "ERROR: $KEY is readable by every user of this machine (mode $mode); chmod 0640 and give the group 1883, or chmod 0600 and chown 1883" >&2; status=2
    elif (( (8#$mode & 8#040) == 0 )) && [[ "$owner" != "1883" ]]; then
      echo "NOTE: $KEY is readable only by its owner ($owner): the broker (user 1883 after it starts) reads it at the start but not when it reloads the certificate; chown 1883 $KEY, or chmod 0640 with the group 1883" >&2
    fi
  fi
fi
if [[ "$REMOTE" == 1 ]]; then
  origin="$(read_value ARMOR_PUBLIC_ORIGIN)"
  [[ "$origin" == https://* ]] || { echo "ERROR: ARMOR_PUBLIC_ORIGIN must be an https:// address for remote access" >&2; status=2; }
  [[ "$(read_value ARMOR_COOKIE_SECURE)" != 0 ]] || { echo "ERROR: ARMOR_COOKIE_SECURE=0 sends the session cookie in clear; leave it empty or 1 for remote access" >&2; status=2; }
  proxy="$(read_value ARMOR_TRUST_PROXY)"
  case "$proxy" in 0|false|off|no) echo "ERROR: ARMOR_TRUST_PROXY must trust the proxy in front of the server for remote access (the real address of a client is needed to limit it)" >&2; status=2 ;; esac
  [[ "$(read_value ARMOR_DISARM_PIN)" == required ]] || { echo "ERROR: ARMOR_DISARM_PIN must be required for remote access" >&2; status=2; }
  bind="$(read_value ARMOR_MQTT_BIND)"
  case "$bind" in
    ""|127.*|10.*|192.168.*|172.1[6-9].*|172.2[0-9].*|172.3[0-1].*) ;;
    *) echo "ERROR: ARMOR_MQTT_BIND is on every address or on a public one; the broker's port must stay on loopback or on the field network" >&2; status=2 ;;
  esac
  password="$(read_value ARMOR_STUDIO_PASSWORD)"
  if [[ ${#password} -lt 14 ]]; then echo "ERROR: ARMOR_STUDIO_PASSWORD needs at least 14 characters for remote access" >&2; status=2; fi
  case "${password,,}" in password*|12345*|qwerty*|admin*|letmein*|changeme*|welcome*) echo "ERROR: ARMOR_STUDIO_PASSWORD is a common password" >&2; status=2 ;; esac
  echo "NOTE: whether an administrator has a second factor is not in .env: ask the server (GET /api/v1/remote/check) after it starts"
fi
# The Docker stack used to publish Studio on 8088, the server on 8080 and the broker on 1883. The numbering is now the one of the CM5 (ports.json): an installation that still names
# an old number keeps starting, but the address the browser, the apps and the nodes use has to follow. A note, never a failure.
for variable in ARMOR_PUBLIC_ORIGIN ARMOR_MQTT_URL ARMOR_SIM_SERVER_URL; do
  case "$(read_value "$variable")" in
    *:8088|*:8088/*) echo "NOTE: $variable still names port 8088 of the old Docker numbering; Studio is now on 18081 (see docs/DEPLOYMENT_BOUNDARY.md, Ports)" >&2 ;;
    *:8080|*:8080/*) echo "NOTE: $variable still names port 8080 of the old Docker numbering; the server is now on 18080 (see docs/DEPLOYMENT_BOUNDARY.md, Ports)" >&2 ;;
    *:1883|*:1883/*) echo "NOTE: $variable still names port 1883 of the old Docker numbering; the broker is now on 18883 (see docs/DEPLOYMENT_BOUNDARY.md, Ports)" >&2 ;;
  esac
done
[[ $status -eq 0 ]] && echo "ARMOR_DEVOPS_ENV=PASS"
exit $status
