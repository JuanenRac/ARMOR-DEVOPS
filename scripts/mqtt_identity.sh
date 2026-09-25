#!/usr/bin/env bash
# ARMOR-DEVOPS - add or remove an MQTT identity on the A.R.M.O.R. test-bench broker.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
#
#   sudo mqtt_identity.sh add node north-1     # a field node: writes its own telemetry/health, reads its own commands
#   sudo mqtt_identity.sh add consumer siren   # an alarm consumer: reads armor/server/alert only
#   sudo mqtt_identity.sh add device kitchen   # one smart device (a plug, a sensor): reads and writes armor/device/kitchen/# only
#   sudo mqtt_identity.sh add bridge zigbee    # a bridge to many devices (Zigbee2MQTT, a Shelly gateway): all of armor/device/#
#   sudo mqtt_identity.sh remove field-node-north-1
#
# The generated password is printed once, because the device needs it; it is
# never stored anywhere except (hashed) in the broker's password file.
set -euo pipefail
PREFIX="${ARMOR_PREFIX:-/opt/armor}"
MQ="$PREFIX/etc/mosquitto"
[[ "$(id -u)" -eq 0 ]] || { echo "run as root" >&2; exit 1; }
[[ -f "$MQ/passwd" && -f "$MQ/acl" ]] || { echo "the A.R.M.O.R. broker is not installed (install_cm5.sh --with-mqtt)" >&2; exit 1; }

usage() { echo "Usage: mqtt_identity.sh add node ID | add consumer NAME | add device NAME | add bridge NAME | remove USER" >&2; exit 2; }
ACTION="${1:-}"
reload_broker() { systemctl reload armor-mosquitto 2>/dev/null || systemctl restart armor-mosquitto; }

case "$ACTION" in
  add)
    ROLE="${2:-}"; NAME="${3:-}"
    [[ "$NAME" =~ ^[a-z0-9][a-z0-9_-]{0,63}$ ]] || { echo "the name must match ^[a-z0-9][a-z0-9_-]{0,63}\$" >&2; exit 2; }
    case "$ROLE" in
      node) USER_NAME="field-node-$NAME" ;;
      consumer) USER_NAME="alarm-$NAME" ;;
      device) USER_NAME="device-$NAME" ;;
      bridge) USER_NAME="bridge-$NAME" ;;
      *) usage ;;
    esac
    if grep -qx "user $USER_NAME" "$MQ/acl"; then echo "$USER_NAME already exists; remove it first to change its password" >&2; exit 1; fi
    PASSWORD="$(head -c 48 /dev/urandom | base64 | tr -d '\n=+/' | head -c 32)"
    mosquitto_passwd -b "$MQ/passwd" "$USER_NAME" "$PASSWORD" >/dev/null
    {
      echo
      echo "user $USER_NAME"
      if [[ "$ROLE" == "node" ]]; then
        echo "topic write armor/node/$NAME/telemetry"
        echo "topic write armor/node/$NAME/health"
        echo "topic read armor/node/$NAME/command"
      elif [[ "$ROLE" == "device" ]]; then
        echo "topic readwrite armor/device/$NAME/#"
      elif [[ "$ROLE" == "bridge" ]]; then
        echo "topic readwrite armor/device/#"
      else
        echo "topic read armor/server/alert"
      fi
    } >>"$MQ/acl"
    chown armor:armor "$MQ/passwd" "$MQ/acl"; chmod 0600 "$MQ/passwd" "$MQ/acl"
    reload_broker
    echo "user: $USER_NAME"
    echo "password: $PASSWORD"
    ;;
  remove)
    USER_NAME="${2:-}"
    [[ "$USER_NAME" =~ ^(field-node|alarm|device|bridge)-[a-z0-9][a-z0-9_-]{0,63}$ ]] || { echo "only field-node-*, alarm-*, device-* and bridge-* identities can be removed" >&2; exit 2; }
    mosquitto_passwd -D "$MQ/passwd" "$USER_NAME" >/dev/null
    # Drop the identity's block (its "user" line and the lines up to the next blank line), keeping a copy.
    cp -p "$MQ/acl" "$MQ/acl.before-remove"
    awk -v u="user $USER_NAME" 'BEGIN{skip=0} $0==u{skip=1; next} skip && /^$/{skip=0; next} !skip{print}' "$MQ/acl.before-remove" >"$MQ/acl"
    chown armor:armor "$MQ/passwd" "$MQ/acl"; chmod 0600 "$MQ/passwd" "$MQ/acl"
    reload_broker
    echo "removed $USER_NAME (the previous ACL is kept as acl.before-remove)"
    ;;
  *) usage ;;
esac
