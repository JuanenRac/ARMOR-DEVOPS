#!/usr/bin/env bash
# ARMOR-DEVOPS - add or remove an MQTT identity on the A.R.M.O.R. test-bench broker.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
#
#   sudo mqtt_identity.sh add node north-1     # a field node: writes its own telemetry/health, reads its own commands (and writes armor/solar/north-1/+/state and .../maintenance/result if it also reads solar equipment)
#   sudo mqtt_identity.sh add solar-node solar-1  # a solar gateway node (ARMOR-NODE-SOLAR): writes armor/solar/solar-1/+/state and .../maintenance/result and nothing else (never the order topic: only the server writes it)
#   sudo mqtt_identity.sh add electrical-node electrical-1  # an electrical node (ARMOR-NODE-ELECTRICAL): writes armor/electrical/electrical-1/state and /result and nothing else, reads nothing
#   sudo mqtt_identity.sh add alarm-node alarm-1   # an alarm node (ARMOR-NODE-ALARM): writes armor/alarm/alarm-1/state and /result and reads only armor/alarm/alarm-1/zigbee and .../policy (the Zigbee zones and the security policy the server tells it)
#   sudo mqtt_identity.sh add network-node network-1   # a network node (ARMOR-NETWORK): writes armor/network/network-1/state and nothing else, reads nothing
#   sudo mqtt_identity.sh electrical-relays electrical-1 on     # lets that node's relays be devices of the house (armor/device/electrical-1/#): it publishes their state and reads their commands (off again with `off`): NOT part of any install
#   sudo mqtt_identity.sh alarm-commands alarm-1 on   # lets the server arm and disarm that alarm node, and the node read the commands (off again with `off`): NOT part of any install
#   sudo mqtt_identity.sh alarm-z2m-state alarm-1 on [TOPIC]   # lets that alarm node read the retained state of Zigbee2MQTT (default zigbee2mqtt/bridge/state) to know when it is down while the broker is up (off again with `off`): NOT part of any install
#   sudo mqtt_identity.sh electrical-switching electrical-1 on   # lets the server send commands to that node's switch, and the node read them (off again with `off`): NOT part of any install
#   sudo mqtt_identity.sh battery-write solar-1 on   # lets the server send an order to write to the batteries of that solar node, and the node read it (off again with `off`): NOT part of any install
#   sudo mqtt_identity.sh alarm-state-relay on   # lets the server publish again, signed, the state of the alarm panels (the option "alarm state signature"; off again with `off`): NOT part of any install
#   sudo mqtt_identity.sh add consumer siren   # an alarm consumer: reads armor/server/alert only
#   sudo mqtt_identity.sh add device kitchen   # one smart device (a plug, a sensor): reads and writes armor/device/kitchen/# only
#   sudo mqtt_identity.sh add bridge zigbee    # a bridge to many devices (Zigbee2MQTT, a Shelly gateway): all of armor/device/#
#   sudo mqtt_identity.sh upgrade-node north-1 # an existing field node: also let it write armor/node/north-1/info (where its panel is) use armor/device/north-1/# (its mapped pins) and write armor/solar/north-1/+/state and .../maintenance/result (inverters and batteries it reads)
#   sudo mqtt_identity.sh narrow-solar-acl solar-1  # a solar or field node made before the order topic was kept for the server: swap its wide line armor/solar/solar-1/# for the two narrow ones (idempotent; the previous ACL is kept)
#   ARMOR_ACL_STRICT_MAINTENANCE_COMMAND=0 sudo -E mqtt_identity.sh add solar-node solar-1  # the compatibility mode (default 1 = strict): also writes the old wide line, which lets a node publish the battery order topic
#   sudo mqtt_identity.sh alarm-policy alarm-1       # an alarm node made before the server's security options existed: also let it read armor/alarm/alarm-1/policy (idempotent)
#   sudo mqtt_identity.sh node-control alarm-node alarm-1   # an identity made before remote control existed: also let the node read its own control orders and write its own answers and maintenance signal
#   sudo mqtt_identity.sh radar-events north-1   # a radar node made before the events of its perimeter engine existed: let it write armor/radar/north-1/events and read armor/radar/north-1/control/armed, and let the server read the events
#   sudo mqtt_identity.sh rotate node north-1  # a new password for an identity that exists, in one step: the ACL block is not touched, so the node is never left without access (what a node adopted again needs)
#   sudo mqtt_identity.sh remove field-node-north-1
#
# The generated password is printed once, because the device needs it; it is
# never stored anywhere except (hashed) in the broker's password file.
set -euo pipefail
PREFIX="${ARMOR_PREFIX:-/opt/armor}"
MQ="$PREFIX/etc/mosquitto"
[[ "$(id -u)" -eq 0 ]] || { echo "run as root" >&2; exit 1; }
[[ -f "$MQ/passwd" && -f "$MQ/acl" ]] || { echo "the A.R.M.O.R. broker is not installed (install_cm5.sh --with-mqtt)" >&2; exit 1; }
# A broker whose identities were moved to the dynamic-security plugin (install_cm5.sh --broker-auth dynsec) is changed with mosquitto_ctrl, not by editing these files:
# the files stay only as the record of what was moved, and editing them would change nothing while looking as if it had.
if [[ -f "$MQ/dynamic-security.json" ]]; then
  echo "this broker keeps its identities in the dynamic-security plugin: change them with mosquitto_ctrl (the administrator password is in $PREFIX/etc/armor.dynsec.admin); this script edits the password and ACL files, which that broker no longer reads" >&2
  exit 1
fi

# BEGIN GENERATED FROM scripts/node_roles.json (python3 scripts/generate_node_roles.py): the user name and the access lines of each kind of identity.
role_user() {
  local NAME="$2"
  case "$1" in
    node) echo "field-node-$NAME" ;;
    hmi-node) echo "hmi-node-$NAME" ;;
    solar-node) echo "solar-node-$NAME" ;;
    electrical-node) echo "electrical-node-$NAME" ;;
    alarm-node) echo "alarm-node-$NAME" ;;
    network-node) echo "network-node-$NAME" ;;
    device) echo "device-$NAME" ;;
    bridge) echo "bridge-$NAME" ;;
    consumer) echo "alarm-$NAME" ;;
    *) return 1 ;;
  esac
}
role_lines() {
  local NAME="$2"
  case "$1" in
    node)
      echo "topic write armor/node/$NAME/telemetry"
      echo "topic write armor/node/$NAME/health"
      echo "topic write armor/node/$NAME/info"
      echo "topic write armor/health/$NAME"
      echo "topic read armor/node/$NAME/command"
      echo "topic readwrite armor/device/$NAME/#"
      echo "topic write armor/solar/$NAME/+/state"
      echo "topic write armor/solar/$NAME/maintenance/result"
      echo "topic write armor/solar/$NAME/system"
      echo "topic write armor/radar/$NAME/events"
      echo "topic read armor/radar/$NAME/control/armed"
      echo "topic read armor/control/$NAME/command"
      echo "topic read armor/control/all/command"
      echo "topic write armor/control/$NAME/result"
      echo "topic write armor/control/$NAME/maintenance"
      if [[ "${ARMOR_ACL_STRICT_MAINTENANCE_COMMAND:-1}" == "0" ]]; then
        echo "topic write armor/solar/$NAME/#"
      fi
      ;;
    hmi-node)
      echo "topic write armor/node/$NAME/health"
      echo "topic write armor/node/$NAME/info"
      echo "topic write armor/health/$NAME"
      echo "topic read armor/control/$NAME/command"
      echo "topic read armor/control/all/command"
      echo "topic write armor/control/$NAME/result"
      echo "topic write armor/control/$NAME/maintenance"
      ;;
    solar-node)
      echo "topic write armor/solar/$NAME/+/state"
      echo "topic write armor/solar/$NAME/maintenance/result"
      echo "topic write armor/solar/$NAME/system"
      echo "topic write armor/health/$NAME"
      echo "topic read armor/control/$NAME/command"
      echo "topic read armor/control/all/command"
      echo "topic write armor/control/$NAME/result"
      echo "topic write armor/control/$NAME/maintenance"
      if [[ "${ARMOR_ACL_STRICT_MAINTENANCE_COMMAND:-1}" == "0" ]]; then
        echo "topic write armor/solar/$NAME/#"
      fi
      ;;
    electrical-node)
      echo "topic write armor/electrical/$NAME/state"
      echo "topic write armor/electrical/$NAME/result"
      echo "topic write armor/health/$NAME"
      echo "topic read armor/control/$NAME/command"
      echo "topic read armor/control/all/command"
      echo "topic write armor/control/$NAME/result"
      echo "topic write armor/control/$NAME/maintenance"
      ;;
    alarm-node)
      echo "topic write armor/alarm/$NAME/state"
      echo "topic write armor/alarm/$NAME/result"
      echo "topic write armor/health/$NAME"
      echo "topic read armor/alarm/$NAME/zigbee"
      echo "topic read armor/alarm/$NAME/policy"
      echo "topic read armor/control/$NAME/command"
      echo "topic read armor/control/all/command"
      echo "topic write armor/control/$NAME/result"
      echo "topic write armor/control/$NAME/maintenance"
      ;;
    network-node)
      echo "topic write armor/network/$NAME/state"
      ;;
    device)
      echo "topic readwrite armor/device/$NAME/#"
      ;;
    bridge)
      echo "topic readwrite armor/device/#"
      ;;
    consumer)
      echo "topic read armor/server/alert"
      ;;
  esac
}
# END GENERATED

usage() { echo "Usage: mqtt_identity.sh add node ID | add solar-node ID | add electrical-node ID | add network-node ID | add alarm-node ID | add hmi-node ID | add consumer NAME | add device NAME | add bridge NAME | upgrade-node NODE_ID | health-report ROLE NODE_ID | alarm-policy NODE_ID | node-control ROLE NODE_ID | electrical-switching NODE_ID on|off | alarm-commands NODE_ID on|off | alarm-z2m-state NODE_ID on|off [TOPIC] | electrical-relays NODE_ID on|off | alarm-relays NODE_ID on|off | battery-write NODE_ID on|off | narrow-solar-acl NODE_ID | alarm-state-relay on|off | ha-discovery on|off [PREFIX] | remove USER" >&2; exit 2; }
ACTION="${1:-}"
# Removes one line from the block of ONE identity ("user NAME" up to the next blank line), never from the others: the same line (topic readwrite armor/device/garage/#) can be in the
# blocks of a device and of a node with the same name.
drop_line() { awk -v u="user $1" -v l="$2" 'BEGIN{inb=0} $0==u{inb=1; print; next} inb && /^$/{inb=0} inb && $0==l{next} {print}' "$MQ/acl" >"$MQ/acl.tmp" && cat "$MQ/acl.tmp" >"$MQ/acl"; rm -f "$MQ/acl.tmp"; }
reload_broker() { systemctl reload armor-mosquitto 2>/dev/null || systemctl restart armor-mosquitto; }

case "$ACTION" in
  add)
    ROLE="${2:-}"; NAME="${3:-}"
    [[ "$NAME" =~ ^[a-z0-9][a-z0-9_-]{0,63}$ ]] || { echo "the name must match ^[a-z0-9][a-z0-9_-]{0,63}\$" >&2; exit 2; }
    USER_NAME="$(role_user "$ROLE" "$NAME")" || usage
    if grep -qx "user $USER_NAME" "$MQ/acl"; then echo "$USER_NAME already exists; remove it first to change its password" >&2; exit 1; fi
    PASSWORD="$(head -c 48 /dev/urandom | base64 | tr -d '\n=+/' | head -c 32)"
    mosquitto_passwd -b "$MQ/passwd" "$USER_NAME" "$PASSWORD" >/dev/null
    {
      echo
      echo "user $USER_NAME"
      role_lines "$ROLE" "$NAME"
    } >>"$MQ/acl"
    chown root:armor "$MQ/passwd" "$MQ/acl"; chmod 0640 "$MQ/passwd" "$MQ/acl"
    reload_broker
    echo "user: $USER_NAME"
    echo "password: $PASSWORD"
    ;;
  rotate)
    # A new password for an identity that already exists: the broker's password file is replaced in one step (mosquitto_passwd writes the new hash over the old one) and the ACL is not
    # touched, so a failure leaves the old password working and an identity that was never made is refused instead of being made without its ACL.
    ROLE="${2:-}"; NAME="${3:-}"
    [[ "$NAME" =~ ^[a-z0-9][a-z0-9_-]{0,63}$ ]] || { echo "the name must match ^[a-z0-9][a-z0-9_-]{0,63}\$" >&2; exit 2; }
    case "$ROLE" in
      node) USER_NAME="field-node-$NAME" ;;
      solar-node) USER_NAME="solar-node-$NAME" ;;
      electrical-node) USER_NAME="electrical-node-$NAME" ;;
      network-node) USER_NAME="network-node-$NAME" ;;
      alarm-node) USER_NAME="alarm-node-$NAME" ;;
      hmi-node) USER_NAME="hmi-node-$NAME" ;;
      *) usage ;;
    esac
    grep -qx "user $USER_NAME" "$MQ/acl" || { echo "$USER_NAME does not exist (add it first)" >&2; exit 1; }
    PASSWORD="$(head -c 48 /dev/urandom | base64 | tr -d '
=+/' | head -c 32)"
    mosquitto_passwd -b "$MQ/passwd" "$USER_NAME" "$PASSWORD" >/dev/null
    chown root:armor "$MQ/passwd"; chmod 0640 "$MQ/passwd"
    reload_broker
    echo "user: $USER_NAME"
    echo "password: $PASSWORD"
    ;;
  ha-discovery)
    # Home Assistant finds the entities by the discovery messages the server publishes (retained) under a prefix, `homeassistant` by default. Without this line the broker drops them
    # in silence. Idempotent; `off` takes only that line away from the server's block.
    STATE="${2:-}"; PREFIX_NAME="${3:-homeassistant}"
    [[ "$STATE" == "on" || "$STATE" == "off" ]] || usage
    [[ "$PREFIX_NAME" =~ ^[A-Za-z0-9_-]{1,32}$ ]] || { echo "the prefix must match ^[A-Za-z0-9_-]{1,32}\$" >&2; exit 2; }
    grep -qx "user armor-server" "$MQ/acl" || { echo "the server's identity (armor-server) is not in the ACL" >&2; exit 1; }
    LINE="topic write $PREFIX_NAME/#"
    HAS="$(awk -v u="user armor-server" -v l="$LINE" 'BEGIN{inb=0; found=0} $0==u{inb=1; next} inb && /^$/{inb=0} inb && $0==l{found=1} END{print found}' "$MQ/acl")"
    if [[ "$STATE" == "on" ]]; then
      if [[ "$HAS" == "1" ]]; then echo "armor-server already has: $LINE"; else
        cp -p "$MQ/acl" "$MQ/acl.before-ha"
        sed -i "/^user armor-server\$/a $LINE" "$MQ/acl"; echo "armor-server now has: $LINE"
        chown root:armor "$MQ/acl"; chmod 0640 "$MQ/acl"; reload_broker
      fi
    else
      if [[ "$HAS" != "1" ]]; then echo "armor-server does not have: $LINE"; else
        cp -p "$MQ/acl" "$MQ/acl.before-ha"
        drop_line "armor-server" "$LINE"; echo "armor-server no longer has: $LINE"
        chown root:armor "$MQ/acl"; chmod 0640 "$MQ/acl"; reload_broker
      fi
    fi
    ;;
  upgrade-node)
    NAME="${2:-}"; USER_NAME="field-node-$NAME"
    [[ "$NAME" =~ ^[a-z0-9][a-z0-9_-]{0,63}$ ]] || { echo "the node id must match ^[a-z0-9][a-z0-9_-]{0,63}\$" >&2; exit 2; }
    grep -qx "user $USER_NAME" "$MQ/acl" || { echo "$USER_NAME does not exist" >&2; exit 1; }
    CHANGED=0
    # Idempotent: each line is added to the node's own block only when it is not there.
    for LINE in "topic write armor/node/$NAME/info" "topic readwrite armor/device/$NAME/#" "topic write armor/solar/$NAME/+/state" "topic write armor/solar/$NAME/maintenance/result"; do
      if awk -v u="user $USER_NAME" -v l="$LINE" 'BEGIN{inb=0; found=0} $0==u{inb=1; next} inb && /^$/{inb=0} inb && $0==l{found=1} END{exit found?0:1}' "$MQ/acl"; then
        echo "$USER_NAME already has: $LINE"
      else
        [[ "$CHANGED" -eq 1 ]] || cp -p "$MQ/acl" "$MQ/acl.before-upgrade"
        sed -i "/^user $USER_NAME\$/a $LINE" "$MQ/acl"
        CHANGED=1
        echo "$USER_NAME now has: $LINE"
      fi
    done
    if [[ "$CHANGED" -eq 1 ]]; then
      chown root:armor "$MQ/acl"; chmod 0640 "$MQ/acl"
      reload_broker
      echo "the previous ACL is kept as acl.before-upgrade"
    fi
    ;;
  narrow-solar-acl)
    # A node made before the order topic of the batteries was kept for the server has the wide line `topic write armor/solar/<node>/#`, which also lets it publish
    # armor/solar/<node>/maintenance/command. This swaps that line for the two narrow ones (the readings and the answers) in the block of the solar node and of the field node of that name.
    # Idempotent; the previous ACL is kept. Nodes keep working: they publish nothing else under their subtree.
    NAME="${2:-}"
    [[ "$NAME" =~ ^[a-z0-9][a-z0-9_-]{0,63}$ ]] || { echo "the node id must match ^[a-z0-9][a-z0-9_-]{0,63}\$" >&2; exit 2; }
    WIDE="topic write armor/solar/$NAME/#"; FOUND=0; CHANGED=0
    for USER_NAME in "solar-node-$NAME" "field-node-$NAME"; do
      grep -qx "user $USER_NAME" "$MQ/acl" || continue
      FOUND=1
      has_line() { awk -v u="user $USER_NAME" -v l="$1" 'BEGIN{inb=0; found=0} $0==u{inb=1; next} inb && /^$/{inb=0} inb && $0==l{found=1} END{exit found?0:1}' "$MQ/acl"; }
      if has_line "$WIDE"; then
        [[ "$CHANGED" -eq 1 ]] || cp -p "$MQ/acl" "$MQ/acl.before-narrow-solar"
        drop_line "$USER_NAME" "$WIDE"; CHANGED=1; echo "$USER_NAME no longer has: $WIDE"
        for LINE in "topic write armor/solar/$NAME/+/state" "topic write armor/solar/$NAME/maintenance/result"; do
          has_line "$LINE" || { sed -i "/^user $USER_NAME\$/a $LINE" "$MQ/acl"; echo "$USER_NAME now has: $LINE"; }
        done
      else
        echo "$USER_NAME does not have the wide line: nothing to narrow"
      fi
    done
    [[ "$FOUND" -eq 1 ]] || { echo "neither solar-node-$NAME nor field-node-$NAME exists" >&2; exit 1; }
    if [[ "$CHANGED" -eq 1 ]]; then
      chown root:armor "$MQ/acl"; chmod 0640 "$MQ/acl"
      reload_broker
      echo "the previous ACL is kept as acl.before-narrow-solar"
    fi
    ;;
  alarm-policy)
    # An alarm node made before the server told its panel the security options may not read armor/alarm/<node>/policy: this adds that one line to its block (idempotent; the previous ACL is kept).
    # The server's own right to write it (armor/alarm/+/policy) is added by install_cm5.sh.
    NAME="${2:-}"
    [[ "$NAME" =~ ^[a-z0-9][a-z0-9_-]{0,63}$ ]] || { echo "the node id must match ^[a-z0-9][a-z0-9_-]{0,63}\$" >&2; exit 2; }
    USER_NAME="alarm-node-$NAME"
    grep -qx "user $USER_NAME" "$MQ/acl" || { echo "$USER_NAME does not exist" >&2; exit 1; }
    LINE="topic read armor/alarm/$NAME/policy"
    if awk -v u="user $USER_NAME" -v l="$LINE" 'BEGIN{inb=0; found=0} $0==u{inb=1; next} inb && /^$/{inb=0} inb && $0==l{found=1} END{exit found?0:1}' "$MQ/acl"; then
      echo "$USER_NAME already has: $LINE"
    else
      cp -p "$MQ/acl" "$MQ/acl.before-alarm-policy"
      sed -i "/^user $USER_NAME\$/a $LINE" "$MQ/acl"
      chown root:armor "$MQ/acl"; chmod 0640 "$MQ/acl"; reload_broker
      echo "$USER_NAME now has: $LINE (the previous ACL is kept as acl.before-alarm-policy)"
    fi
    ;;
  health-report)
    # A node installed before the health report existed may not write armor/health/<node>: this adds that one line to its block (idempotent; the previous ACL is kept). The server's own
    # right to read it (armor/health/#) is added by install_cm5.sh.
    ROLE="${2:-}"; NAME="${3:-}"
    [[ "$NAME" =~ ^[a-z0-9][a-z0-9_-]{0,63}$ ]] || { echo "the node id must match ^[a-z0-9][a-z0-9_-]{0,63}\$" >&2; exit 2; }
    case "$ROLE" in
      node) USER_NAME="field-node-$NAME" ;;
      solar-node) USER_NAME="solar-node-$NAME" ;;
      electrical-node) USER_NAME="electrical-node-$NAME" ;;
      alarm-node) USER_NAME="alarm-node-$NAME" ;;
      hmi-node) USER_NAME="hmi-node-$NAME" ;;
      *) usage ;;
    esac
    grep -qx "user $USER_NAME" "$MQ/acl" || { echo "$USER_NAME does not exist" >&2; exit 1; }
    LINE="topic write armor/health/$NAME"
    if awk -v u="user $USER_NAME" -v l="$LINE" 'BEGIN{inb=0; found=0} $0==u{inb=1; next} inb && /^$/{inb=0} inb && $0==l{found=1} END{exit found?0:1}' "$MQ/acl"; then
      echo "$USER_NAME already has: $LINE"
    else
      cp -p "$MQ/acl" "$MQ/acl.before-health"
      sed -i "/^user $USER_NAME\$/a $LINE" "$MQ/acl"
      chown root:armor "$MQ/acl"; chmod 0640 "$MQ/acl"; reload_broker
      echo "$USER_NAME now has: $LINE (the previous ACL is kept as acl.before-health)"
    fi
    ;;
  node-control)
    # A node installed before remote control existed may not read its own control orders nor write its answer and its maintenance signal: this adds the four lines to its block (idempotent; the previous ACL is kept).
    # The server's right to publish the orders (armor/control/+/command) and to read the answers is added by install_cm5.sh. A node can never publish an order.
    ROLE="${2:-}"; NAME="${3:-}"
    [[ "$NAME" =~ ^[a-z0-9][a-z0-9_-]{0,63}$ ]] || { echo "the node id must match ^[a-z0-9][a-z0-9_-]{0,63}\$" >&2; exit 2; }
    case "$ROLE" in
      node) USER_NAME="field-node-$NAME" ;;
      solar-node) USER_NAME="solar-node-$NAME" ;;
      electrical-node) USER_NAME="electrical-node-$NAME" ;;
      alarm-node) USER_NAME="alarm-node-$NAME" ;;
      hmi-node) USER_NAME="hmi-node-$NAME" ;;
      *) usage ;;
    esac
    grep -qx "user $USER_NAME" "$MQ/acl" || { echo "$USER_NAME does not exist" >&2; exit 1; }
    CHANGED=0
    for LINE in "topic read armor/control/$NAME/command" "topic read armor/control/all/command" "topic write armor/control/$NAME/result" "topic write armor/control/$NAME/maintenance"; do
      if awk -v u="user $USER_NAME" -v l="$LINE" 'BEGIN{inb=0; found=0} $0==u{inb=1; next} inb && /^$/{inb=0} inb && $0==l{found=1} END{exit found?0:1}' "$MQ/acl"; then
        echo "$USER_NAME already has: $LINE"
      else
        [[ "$CHANGED" -eq 1 ]] || cp -p "$MQ/acl" "$MQ/acl.before-control"
        sed -i "/^user $USER_NAME\$/a $LINE" "$MQ/acl"; CHANGED=1; echo "$USER_NAME now has: $LINE"
      fi
    done
    if [[ "$CHANGED" -eq 1 ]]; then
      chown root:armor "$MQ/acl"; chmod 0640 "$MQ/acl"; reload_broker
      echo "the previous ACL is kept as acl.before-control"
    fi
    ;;
  radar-events)
    # A radar node installed before the events of its perimeter engine existed may not write armor/radar/<node>/events nor read whether the perimeter is armed, and the server may not read the events: this
    # adds the two lines to the node's block and the one line to the server's (idempotent; the previous ACL is kept). A node can write only its own subtree.
    NAME="${2:-}"; USER_NAME="field-node-$NAME"
    [[ "$NAME" =~ ^[a-z0-9][a-z0-9_-]{0,63}$ ]] || { echo "the node id must match ^[a-z0-9][a-z0-9_-]{0,63}\$" >&2; exit 2; }
    grep -qx "user $USER_NAME" "$MQ/acl" || { echo "$USER_NAME does not exist" >&2; exit 1; }
    grep -qx "user armor-server" "$MQ/acl" || { echo "the server's identity (armor-server) is not in the ACL" >&2; exit 1; }
    has_line() { awk -v u="user $1" -v l="$2" 'BEGIN{inb=0; found=0} $0==u{inb=1; next} inb && /^$/{inb=0} inb && $0==l{found=1} END{exit found?0:1}' "$MQ/acl"; }
    CHANGED=0
    for PAIR in "$USER_NAME|topic write armor/radar/$NAME/events" "$USER_NAME|topic read armor/radar/$NAME/control/armed" "armor-server|topic read armor/radar/+/events"; do
      WHO="${PAIR%%|*}"; LINE="${PAIR#*|}"
      if has_line "$WHO" "$LINE"; then echo "$WHO already has: $LINE"; continue; fi
      [[ "$CHANGED" -eq 1 ]] || cp -p "$MQ/acl" "$MQ/acl.before-radar-events"
      sed -i "/^user $WHO\$/a $LINE" "$MQ/acl"; CHANGED=1; echo "$WHO now has: $LINE"
    done
    if [[ "$CHANGED" -eq 1 ]]; then
      chown root:armor "$MQ/acl"; chmod 0640 "$MQ/acl"
      reload_broker
      echo "the previous ACL is kept as acl.before-radar-events"
    fi
    ;;
  alarm-z2m-state)
    # One line lets an alarm node READ the topic where Zigbee2MQTT says whether it is alive (zigbee2mqtt/bridge/state): with the node's setting zigbee_local.bridge_state_topic the node then takes
    # the Zigbee coordinator of the network when Zigbee2MQTT is down even while the broker is up. Read only, one topic, no wildcard. Without the line the broker itself refuses the subscription.
    NAME="${2:-}"; STATE="${3:-}"; TOPIC="${4:-zigbee2mqtt/bridge/state}"; USER_NAME="alarm-node-$NAME"
    [[ "$NAME" =~ ^[a-z0-9][a-z0-9_-]{0,63}$ ]] || { echo "the node id must match ^[a-z0-9][a-z0-9_-]{0,63}\$" >&2; exit 2; }
    [[ "$STATE" == "on" || "$STATE" == "off" ]] || usage
    [[ "$TOPIC" =~ ^[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)*$ && ${#TOPIC} -le 128 ]] || { echo "the topic must be plain levels of letters, digits, _ . - separated by one slash, with no wildcard (at most 128 characters)" >&2; exit 2; }
    grep -qx "user $USER_NAME" "$MQ/acl" || { echo "$USER_NAME does not exist (add alarm-node $NAME first)" >&2; exit 1; }
    LINE="topic read $TOPIC"
    if awk -v u="user $USER_NAME" -v l="$LINE" 'BEGIN{inb=0; found=0} $0==u{inb=1; next} inb && /^$/{inb=0} inb && $0==l{found=1} END{exit found?0:1}' "$MQ/acl"; then HAS=1; else HAS=0; fi
    if [[ "$STATE" == "on" ]]; then
      if [[ "$HAS" -eq 1 ]]; then echo "$USER_NAME already has: $LINE"; else
        cp -p "$MQ/acl" "$MQ/acl.before-alarm-z2m-state"
        sed -i "/^user $USER_NAME\$/a $LINE" "$MQ/acl"; echo "$USER_NAME now has: $LINE"
        chown root:armor "$MQ/acl"; chmod 0640 "$MQ/acl"; reload_broker
        echo "the previous ACL is kept as acl.before-alarm-z2m-state; the node also needs zigbee_local.bridge_state_topic set to $TOPIC in its panel"
      fi
    else
      if [[ "$HAS" -eq 0 ]]; then echo "$USER_NAME does not have: $LINE"; else
        cp -p "$MQ/acl" "$MQ/acl.before-alarm-z2m-state"
        drop_line "$USER_NAME" "$LINE"; echo "$USER_NAME no longer has: $LINE"
        chown root:armor "$MQ/acl"; chmod 0640 "$MQ/acl"; reload_broker
      fi
    fi
    ;;
  electrical-relays|alarm-relays)
    # The relays of an electrical node are devices of the device layer (armor/device/<node>/<relay>/state and /set). Only this command lets the node write its states and read its
    # commands there; the server's own identity already covers armor/device/#. Without the line the broker itself refuses, whatever the node's panel says. Idempotent; the previous ACL is kept.
    NAME="${2:-}"; STATE="${3:-}"; KIND="${ACTION%-relays}"; USER_NAME="$KIND-node-$NAME"
    [[ "$NAME" =~ ^[a-z0-9][a-z0-9_-]{0,63}$ ]] || { echo "the node id must match ^[a-z0-9][a-z0-9_-]{0,63}\$" >&2; exit 2; }
    [[ "$STATE" == "on" || "$STATE" == "off" ]] || usage
    grep -qx "user $USER_NAME" "$MQ/acl" || { echo "$USER_NAME does not exist (add $KIND-node $NAME first)" >&2; exit 1; }
    LINE="topic readwrite armor/device/$NAME/#"
    if awk -v u="user $USER_NAME" -v l="$LINE" 'BEGIN{inb=0; found=0} $0==u{inb=1; next} inb && /^$/{inb=0} inb && $0==l{found=1} END{exit found?0:1}' "$MQ/acl"; then HAS=1; else HAS=0; fi
    if [[ "$STATE" == "on" ]]; then
      if [[ "$HAS" -eq 1 ]]; then echo "$USER_NAME already has: $LINE"; else
        cp -p "$MQ/acl" "$MQ/acl.before-relays"
        sed -i "/^user $USER_NAME\$/a $LINE" "$MQ/acl"; echo "$USER_NAME now has: $LINE"
        chown root:armor "$MQ/acl"; chmod 0640 "$MQ/acl"; reload_broker
        echo "the previous ACL is kept as acl.before-relays; the node also needs remote.relays on in its panel, and a device in Studio with the connection ARMOR node and the name $NAME/<relay>"
      fi
    else
      if [[ "$HAS" -eq 0 ]]; then echo "$USER_NAME does not have: $LINE"; else
        cp -p "$MQ/acl" "$MQ/acl.before-relays"
        drop_line "$USER_NAME" "$LINE"; echo "$USER_NAME no longer has: $LINE"
        chown root:armor "$MQ/acl"; chmod 0640 "$MQ/acl"; reload_broker
      fi
    fi
    ;;
  alarm-commands)
    # Two lines make an alarm node armable and disarmable from the server, and this is the only thing that writes them: the node may READ its own command topic, and the server may
    # WRITE it. Without both the broker itself refuses the command, whatever the server's switch and the node's setting say. Idempotent; the previous ACL is kept.
    NAME="${2:-}"; STATE="${3:-}"; USER_NAME="alarm-node-$NAME"
    [[ "$NAME" =~ ^[a-z0-9][a-z0-9_-]{0,63}$ ]] || { echo "the node id must match ^[a-z0-9][a-z0-9_-]{0,63}\$" >&2; exit 2; }
    [[ "$STATE" == "on" || "$STATE" == "off" ]] || usage
    grep -qx "user $USER_NAME" "$MQ/acl" || { echo "$USER_NAME does not exist (add alarm-node $NAME first)" >&2; exit 1; }
    grep -qx "user armor-server" "$MQ/acl" || { echo "the server's identity (armor-server) is not in the ACL" >&2; exit 1; }
    COMMAND="armor/alarm/$NAME/command"
    has_line() { awk -v u="user $1" -v l="$2" 'BEGIN{inb=0; found=0} $0==u{inb=1; next} inb && /^$/{inb=0} inb && $0==l{found=1} END{exit found?0:1}' "$MQ/acl"; }
    CHANGED=0
    for PAIR in "$USER_NAME|topic read $COMMAND" "armor-server|topic write $COMMAND"; do
      WHO="${PAIR%%|*}"; LINE="${PAIR#*|}"
      if [[ "$STATE" == "on" ]]; then
        if has_line "$WHO" "$LINE"; then echo "$WHO already has: $LINE"; continue; fi
        [[ "$CHANGED" -eq 1 ]] || cp -p "$MQ/acl" "$MQ/acl.before-alarm-commands"
        sed -i "/^user $WHO\$/a $LINE" "$MQ/acl"; CHANGED=1; echo "$WHO now has: $LINE"
      else
        if ! has_line "$WHO" "$LINE"; then echo "$WHO does not have: $LINE"; continue; fi
        [[ "$CHANGED" -eq 1 ]] || cp -p "$MQ/acl" "$MQ/acl.before-alarm-commands"
        drop_line "$WHO" "$LINE"; CHANGED=1; echo "$WHO no longer has: $LINE"
      fi
    done
    if [[ "$CHANGED" -eq 1 ]]; then
      chown root:armor "$MQ/acl"; chmod 0640 "$MQ/acl"
      reload_broker
      echo "the previous ACL is kept as acl.before-alarm-commands; the server also needs its alarm commands turned on to send anything, and the node's setting server.commands has to allow it"
    fi
    ;;
  electrical-switching)
    # Two lines make a switch reachable from the server, and this is the only thing that writes them: the node may READ its own command topic, and the server may WRITE it.
    # Without both the broker itself refuses the command, whatever the server's ARMOR_ELECTRICAL_SWITCHING says. Idempotent; the previous ACL is kept.
    NAME="${2:-}"; STATE="${3:-}"; USER_NAME="electrical-node-$NAME"
    [[ "$NAME" =~ ^[a-z0-9][a-z0-9_-]{0,63}$ ]] || { echo "the node id must match ^[a-z0-9][a-z0-9_-]{0,63}\$" >&2; exit 2; }
    [[ "$STATE" == "on" || "$STATE" == "off" ]] || usage
    grep -qx "user $USER_NAME" "$MQ/acl" || { echo "$USER_NAME does not exist (add electrical-node $NAME first)" >&2; exit 1; }
    grep -qx "user armor-server" "$MQ/acl" || { echo "the server's identity (armor-server) is not in the ACL" >&2; exit 1; }
    COMMAND="armor/electrical/$NAME/command"
    has_line() { awk -v u="user $1" -v l="$2" 'BEGIN{inb=0; found=0} $0==u{inb=1; next} inb && /^$/{inb=0} inb && $0==l{found=1} END{exit found?0:1}' "$MQ/acl"; }
    CHANGED=0
    for PAIR in "$USER_NAME|topic read $COMMAND" "armor-server|topic write $COMMAND"; do
      WHO="${PAIR%%|*}"; LINE="${PAIR#*|}"
      if [[ "$STATE" == "on" ]]; then
        if has_line "$WHO" "$LINE"; then echo "$WHO already has: $LINE"; continue; fi
        [[ "$CHANGED" -eq 1 ]] || cp -p "$MQ/acl" "$MQ/acl.before-switching"
        sed -i "/^user $WHO\$/a $LINE" "$MQ/acl"; CHANGED=1; echo "$WHO now has: $LINE"
      else
        if ! has_line "$WHO" "$LINE"; then echo "$WHO does not have: $LINE"; continue; fi
        [[ "$CHANGED" -eq 1 ]] || cp -p "$MQ/acl" "$MQ/acl.before-switching"
        drop_line "$WHO" "$LINE"; CHANGED=1; echo "$WHO no longer has: $LINE"
      fi
    done
    if [[ "$CHANGED" -eq 1 ]]; then
      chown root:armor "$MQ/acl"; chmod 0640 "$MQ/acl"
      reload_broker
      echo "the previous ACL is kept as acl.before-switching; the server also needs ARMOR_ELECTRICAL_SWITCHING=1 to send anything, and the node has to allow it"
    fi
    ;;
  battery-write)
    # An order to write to a battery (the server's battery maintenance) is reachable only with two lines, and this is the only thing that writes them: the solar gateway node may READ its own
    # maintenance command topic, and the server may WRITE it (the node already writes its answer under armor/solar/<node>/#). Without both the broker itself refuses the order. Idempotent; the
    # previous ACL is kept. The server also needs its own switch for battery writes and the node has to allow it.
    NAME="${2:-}"; STATE="${3:-}"; USER_NAME="solar-node-$NAME"
    [[ "$NAME" =~ ^[a-z0-9][a-z0-9_-]{0,63}$ ]] || { echo "the node id must match ^[a-z0-9][a-z0-9_-]{0,63}\$" >&2; exit 2; }
    [[ "$STATE" == "on" || "$STATE" == "off" ]] || usage
    grep -qx "user $USER_NAME" "$MQ/acl" || { echo "$USER_NAME does not exist (add solar-node $NAME first)" >&2; exit 1; }
    grep -qx "user armor-server" "$MQ/acl" || { echo "the server's identity (armor-server) is not in the ACL" >&2; exit 1; }
    COMMAND="armor/solar/$NAME/maintenance/command"
    has_line() { awk -v u="user $1" -v l="$2" 'BEGIN{inb=0; found=0} $0==u{inb=1; next} inb && /^$/{inb=0} inb && $0==l{found=1} END{exit found?0:1}' "$MQ/acl"; }
    CHANGED=0
    for PAIR in "$USER_NAME|topic read $COMMAND" "armor-server|topic write $COMMAND"; do
      WHO="${PAIR%%|*}"; LINE="${PAIR#*|}"
      if [[ "$STATE" == "on" ]]; then
        if has_line "$WHO" "$LINE"; then echo "$WHO already has: $LINE"; continue; fi
        [[ "$CHANGED" -eq 1 ]] || cp -p "$MQ/acl" "$MQ/acl.before-battery-write"
        sed -i "/^user $WHO\$/a $LINE" "$MQ/acl"; CHANGED=1; echo "$WHO now has: $LINE"
      else
        if ! has_line "$WHO" "$LINE"; then echo "$WHO does not have: $LINE"; continue; fi
        [[ "$CHANGED" -eq 1 ]] || cp -p "$MQ/acl" "$MQ/acl.before-battery-write"
        drop_line "$WHO" "$LINE"; CHANGED=1; echo "$WHO no longer has: $LINE"
      fi
    done
    if [[ "$CHANGED" -eq 1 ]]; then
      chown root:armor "$MQ/acl"; chmod 0640 "$MQ/acl"
      reload_broker
      echo "the previous ACL is kept as acl.before-battery-write; the server also needs its battery-write switch on to send anything, and the node has to allow it"
    fi
    ;;
  alarm-state-relay)
    # With the server's option "alarm state signature" on, the server publishes again, signed, the state it heard from a panel (armor/alarm/<node>/state). Without this line the broker drops that copy
    # in silence. Not part of any install; idempotent; `off` takes only that line away from the server's block.
    STATE="${2:-}"
    [[ "$STATE" == "on" || "$STATE" == "off" ]] || usage
    grep -qx "user armor-server" "$MQ/acl" || { echo "the server's identity (armor-server) is not in the ACL" >&2; exit 1; }
    LINE="topic write armor/alarm/+/state"
    HAS="$(awk -v u="user armor-server" -v l="$LINE" 'BEGIN{inb=0; found=0} $0==u{inb=1; next} inb && /^$/{inb=0} inb && $0==l{found=1} END{print found}' "$MQ/acl")"
    if [[ "$STATE" == "on" ]]; then
      if [[ "$HAS" == "1" ]]; then echo "armor-server already has: $LINE"; else
        cp -p "$MQ/acl" "$MQ/acl.before-alarm-state-relay"
        sed -i "/^user armor-server\$/a $LINE" "$MQ/acl"; echo "armor-server now has: $LINE"
        chown root:armor "$MQ/acl"; chmod 0640 "$MQ/acl"; reload_broker
      fi
    else
      if [[ "$HAS" != "1" ]]; then echo "armor-server does not have: $LINE"; else
        cp -p "$MQ/acl" "$MQ/acl.before-alarm-state-relay"
        drop_line "armor-server" "$LINE"; echo "armor-server no longer has: $LINE"
        chown root:armor "$MQ/acl"; chmod 0640 "$MQ/acl"; reload_broker
      fi
    fi
    ;;
  remove)
    USER_NAME="${2:-}"
    [[ "$USER_NAME" =~ ^(field-node|solar-node|electrical-node|network-node|alarm-node|alarm|device|bridge)-[a-z0-9][a-z0-9_-]{0,63}$ ]] || { echo "only field-node-*, solar-node-*, electrical-node-*, network-node-*, alarm-*, device-* and bridge-* identities can be removed" >&2; exit 2; }
    mosquitto_passwd -D "$MQ/passwd" "$USER_NAME" >/dev/null
    # Drop the identity's block (its "user" line and the lines up to the next blank line), keeping a copy.
    cp -p "$MQ/acl" "$MQ/acl.before-remove"
    awk -v u="user $USER_NAME" 'BEGIN{skip=0} $0==u{skip=1; next} skip && /^$/{skip=0; next} !skip{print}' "$MQ/acl.before-remove" >"$MQ/acl"
    # An electrical node that goes leaves no way for the server to command it: its line in the server's block goes too.
    if [[ "$USER_NAME" == electrical-node-* ]]; then sed -i "\#^topic write armor/electrical/${USER_NAME#electrical-node-}/command\$#d" "$MQ/acl"; fi
    if [[ "$USER_NAME" == alarm-node-* ]]; then sed -i "\#^topic write armor/alarm/${USER_NAME#alarm-node-}/command\$#d" "$MQ/acl"; fi
    if [[ "$USER_NAME" == solar-node-* ]]; then sed -i "\#^topic write armor/solar/${USER_NAME#solar-node-}/maintenance/command\$#d" "$MQ/acl"; fi
    chown root:armor "$MQ/passwd" "$MQ/acl"; chmod 0640 "$MQ/passwd" "$MQ/acl"
    reload_broker
    echo "removed $USER_NAME (the previous ACL is kept as acl.before-remove)"
    ;;
  *) usage ;;
esac
