#!/usr/bin/env bash
# ARMOR-DEVOPS - add or remove an MQTT identity on the A.R.M.O.R. test-bench broker.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
#
#   sudo mqtt_identity.sh add node north-1     # a field node: writes its own telemetry/health, reads its own commands (and writes armor/solar/north-1/# if it also reads solar equipment)
#   sudo mqtt_identity.sh add solar-node solar-1  # a solar gateway node (ARMOR-SOLAR): writes armor/solar/solar-1/# and nothing else
#   sudo mqtt_identity.sh add electrical-node electrical-1  # an electrical node (ARMOR-ELECTRICAL): writes armor/electrical/electrical-1/state and /result and nothing else, reads nothing
#   sudo mqtt_identity.sh add alarm-node alarm-1   # an alarm node (ARMOR-ALARM): writes armor/alarm/alarm-1/state and /result and nothing else, reads nothing
#   sudo mqtt_identity.sh add network-node network-1   # a network node (ARMOR-NETWORK): writes armor/network/network-1/state and nothing else, reads nothing
#   sudo mqtt_identity.sh electrical-relays electrical-1 on     # lets that node's relays be devices of the house (armor/device/electrical-1/#): it publishes their state and reads their commands (off again with `off`): NOT part of any install
#   sudo mqtt_identity.sh alarm-commands alarm-1 on   # lets the server arm and disarm that alarm node, and the node read the commands (off again with `off`): NOT part of any install
#   sudo mqtt_identity.sh electrical-switching electrical-1 on   # lets the server send commands to that node's switch, and the node read them (off again with `off`): NOT part of any install
#   sudo mqtt_identity.sh add consumer siren   # an alarm consumer: reads armor/server/alert only
#   sudo mqtt_identity.sh add device kitchen   # one smart device (a plug, a sensor): reads and writes armor/device/kitchen/# only
#   sudo mqtt_identity.sh add bridge zigbee    # a bridge to many devices (Zigbee2MQTT, a Shelly gateway): all of armor/device/#
#   sudo mqtt_identity.sh upgrade-node north-1 # an existing field node: also let it write armor/node/north-1/info (where its panel is) use armor/device/north-1/# (its mapped pins) and write armor/solar/north-1/# (inverters and batteries it reads)
#   sudo mqtt_identity.sh remove field-node-north-1
#
# The generated password is printed once, because the device needs it; it is
# never stored anywhere except (hashed) in the broker's password file.
set -euo pipefail
PREFIX="${ARMOR_PREFIX:-/opt/armor}"
MQ="$PREFIX/etc/mosquitto"
[[ "$(id -u)" -eq 0 ]] || { echo "run as root" >&2; exit 1; }
[[ -f "$MQ/passwd" && -f "$MQ/acl" ]] || { echo "the A.R.M.O.R. broker is not installed (install_cm5.sh --with-mqtt)" >&2; exit 1; }

usage() { echo "Usage: mqtt_identity.sh add node ID | add solar-node ID | add electrical-node ID | add network-node ID | add alarm-node ID | add consumer NAME | add device NAME | add bridge NAME | upgrade-node NODE_ID | electrical-switching NODE_ID on|off | alarm-commands NODE_ID on|off | electrical-relays NODE_ID on|off | remove USER" >&2; exit 2; }
ACTION="${1:-}"
reload_broker() { systemctl reload armor-mosquitto 2>/dev/null || systemctl restart armor-mosquitto; }

case "$ACTION" in
  add)
    ROLE="${2:-}"; NAME="${3:-}"
    [[ "$NAME" =~ ^[a-z0-9][a-z0-9_-]{0,63}$ ]] || { echo "the name must match ^[a-z0-9][a-z0-9_-]{0,63}\$" >&2; exit 2; }
    case "$ROLE" in
      node) USER_NAME="field-node-$NAME" ;;
      solar-node) USER_NAME="solar-node-$NAME" ;;
      electrical-node) USER_NAME="electrical-node-$NAME" ;;
      network-node) USER_NAME="network-node-$NAME" ;;
      alarm-node) USER_NAME="alarm-node-$NAME" ;;
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
        echo "topic write armor/node/$NAME/info"   # the address of its own web panel, for a console to link to
        echo "topic read armor/node/$NAME/command"
        # The pins mapped in the node's own panel are devices named after the node: armor/device/<node>/<pin>/state and /set.
        echo "topic readwrite armor/device/$NAME/#"
        # A node that also reads solar inverters and batteries publishes them as armor/solar/<node>/<device>/state.
        echo "topic write armor/solar/$NAME/#"
      elif [[ "$ROLE" == "solar-node" ]]; then
        # ARMOR-SOLAR: the readings of the inverters and batteries on its serial ports, armor/solar/<node>/<device>/state; it reads nothing.
        echo "topic write armor/solar/$NAME/#"
      elif [[ "$ROLE" == "electrical-node" ]]; then
        # ARMOR-ELECTRICAL: what it measures on the house's network (armor/electrical/<node>/state) and its answers to a command (.../result); it reads nothing, so no command
        # reaches it from the broker until `electrical-switching <node> on` is run for it, on purpose.
        echo "topic write armor/electrical/$NAME/state"
        echo "topic write armor/electrical/$NAME/result"
      elif [[ "$ROLE" == "alarm-node" ]]; then
        # ARMOR-ALARM: its state (armor/alarm/<node>/state) and its answers to a command (.../result); it reads nothing, so no command reaches it from the broker
        # until `alarm-commands <node> on` is run for it, on purpose.
        echo "topic write armor/alarm/$NAME/state"
        echo "topic write armor/alarm/$NAME/result"
      elif [[ "$ROLE" == "network-node" ]]; then
        # ARMOR-NETWORK: what it sees on the local network (armor/network/<node>/state); it reads nothing, so nothing can be sent to it from the broker.
        echo "topic write armor/network/$NAME/state"
      elif [[ "$ROLE" == "device" ]]; then
        echo "topic readwrite armor/device/$NAME/#"
      elif [[ "$ROLE" == "bridge" ]]; then
        echo "topic readwrite armor/device/#"
      else
        echo "topic read armor/server/alert"
      fi
    } >>"$MQ/acl"
    chown root:armor "$MQ/passwd" "$MQ/acl"; chmod 0640 "$MQ/passwd" "$MQ/acl"
    reload_broker
    echo "user: $USER_NAME"
    echo "password: $PASSWORD"
    ;;
  upgrade-node)
    NAME="${2:-}"; USER_NAME="field-node-$NAME"
    [[ "$NAME" =~ ^[a-z0-9][a-z0-9_-]{0,63}$ ]] || { echo "the node id must match ^[a-z0-9][a-z0-9_-]{0,63}\$" >&2; exit 2; }
    grep -qx "user $USER_NAME" "$MQ/acl" || { echo "$USER_NAME does not exist" >&2; exit 1; }
    CHANGED=0
    # Idempotent: each line is added to the node's own block only when it is not there.
    for LINE in "topic write armor/node/$NAME/info" "topic readwrite armor/device/$NAME/#" "topic write armor/solar/$NAME/#"; do
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
  electrical-relays)
    # The relays of an electrical node are devices of the device layer (armor/device/<node>/<relay>/state and /set). Only this command lets the node write its states and read its
    # commands there; the server's own identity already covers armor/device/#. Without the line the broker itself refuses, whatever the node's panel says. Idempotent; the previous ACL is kept.
    NAME="${2:-}"; STATE="${3:-}"; USER_NAME="electrical-node-$NAME"
    [[ "$NAME" =~ ^[a-z0-9][a-z0-9_-]{0,63}$ ]] || { echo "the node id must match ^[a-z0-9][a-z0-9_-]{0,63}\$" >&2; exit 2; }
    [[ "$STATE" == "on" || "$STATE" == "off" ]] || usage
    grep -qx "user $USER_NAME" "$MQ/acl" || { echo "$USER_NAME does not exist (add electrical-node $NAME first)" >&2; exit 1; }
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
        sed -i "\|^$LINE\$|d" "$MQ/acl"; echo "$USER_NAME no longer has: $LINE"
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
        sed -i "\#^$LINE\$#d" "$MQ/acl"; CHANGED=1; echo "$WHO no longer has: $LINE"
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
        sed -i "\#^$LINE\$#d" "$MQ/acl"; CHANGED=1; echo "$WHO no longer has: $LINE"
      fi
    done
    if [[ "$CHANGED" -eq 1 ]]; then
      chown root:armor "$MQ/acl"; chmod 0640 "$MQ/acl"
      reload_broker
      echo "the previous ACL is kept as acl.before-switching; the server also needs ARMOR_ELECTRICAL_SWITCHING=1 to send anything, and the node has to allow it"
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
    chown root:armor "$MQ/passwd" "$MQ/acl"; chmod 0640 "$MQ/passwd" "$MQ/acl"
    reload_broker
    echo "removed $USER_NAME (the previous ACL is kept as acl.before-remove)"
    ;;
  *) usage ;;
esac
