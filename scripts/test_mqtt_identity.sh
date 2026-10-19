#!/usr/bin/env bash
# ARMOR-DEVOPS - test of mqtt_identity.sh in a temporary directory with stand-ins for the broker's tools: the identity of an electrical node, the two lines that make its
# switch reachable (and only `electrical-switching ... on` writes them), and that removing the node takes the server's line with it.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf -- "$WORK"' EXIT

# Stand-ins for what the script needs from the machine: being root, the broker's password tool, the service manager and the file owner.
mkdir -p "$WORK/bin" "$WORK/prefix/etc/mosquitto"
printf '#!/bin/sh\nif [ "$1" = "-u" ]; then echo 0; else /usr/bin/id "$@"; fi\n' >"$WORK/bin/id"
printf '#!/bin/sh\nexit 0\n' >"$WORK/bin/mosquitto_passwd"
printf '#!/bin/sh\nexit 0\n' >"$WORK/bin/systemctl"
printf '#!/bin/sh\nexit 0\n' >"$WORK/bin/chown"
chmod +x "$WORK/bin/"*
export PATH="$WORK/bin:$PATH" ARMOR_PREFIX="$WORK/prefix"
ACL="$WORK/prefix/etc/mosquitto/acl"
: >"$WORK/prefix/etc/mosquitto/passwd"
# The ACL as install_cm5.sh writes it for the server.
cat >"$ACL" <<'ACL'
# Managed by scripts/mqtt_identity.sh; one block per identity.
user armor-server
topic read armor/node/+/telemetry
topic read armor/electrical/#
topic read armor/alarm/#
topic write armor/node/+/command
topic write armor/server/alert
topic readwrite armor/device/#
ACL
run() { bash "$HERE/mqtt_identity.sh" "$@"; }
block() { awk -v u="user $1" 'BEGIN{inb=0} $0==u{inb=1; print; next} inb && /^$/{inb=0} inb{print}' "$ACL"; }
fail() { echo "FAIL: $*" >&2; exit 1; }

# A new electrical node writes its state and its answers, and reads nothing.
run add electrical-node electrical-1 >/dev/null
NODE="$(block electrical-node-electrical-1)"
grep -qx 'topic write armor/electrical/electrical-1/state' <<<"$NODE" || fail "the node cannot write its state"
grep -qx 'topic write armor/electrical/electrical-1/result' <<<"$NODE" || fail "the node cannot write its results"
if grep -v 'armor/control/' <<<"$NODE" | grep -q 'topic read\|readwrite\|/#$'; then fail "the node has more than it needs: $NODE"; fi
# Nothing lets the server send a command yet: the broker would refuse it.
if grep -q 'armor/electrical/electrical-1/command' "$ACL"; then fail "a command is reachable before it was turned on"; fi
if grep -q 'topic write armor/electrical/' <<<"$(block armor-server)"; then fail "the server can write to an electrical node by default"; fi

# Turned on for that node: the node reads its command topic and the server writes it, nothing else changes.
run electrical-switching electrical-1 on >/dev/null
grep -qx 'topic read armor/electrical/electrical-1/command' <<<"$(block electrical-node-electrical-1)" || fail "the node cannot read its commands after on"
grep -qx 'topic write armor/electrical/electrical-1/command' <<<"$(block armor-server)" || fail "the server cannot write the command after on"
[[ -f "$WORK/prefix/etc/mosquitto/acl.before-switching" ]] || fail "the previous ACL was not kept"
# Idempotent, and it only ever reaches the node it was asked for.
BEFORE="$(cat "$ACL")"
run electrical-switching electrical-1 on >/dev/null
[[ "$(cat "$ACL")" == "$BEFORE" ]] || fail "a second on changed the ACL"
run add electrical-node electrical-2 >/dev/null
if grep -q 'armor/electrical/electrical-2/command' "$ACL"; then fail "another node became reachable"; fi
# Every kind of node that has a health report may write its own, and only its own; the network node has none.
for ROLE_AND_NAME in "node:field-node-n1" "hmi-node:hmi-node-h1" "solar-node:solar-node-s1" "electrical-node:electrical-node-e9" "alarm-node:alarm-node-a1"; do
  ROLE="${ROLE_AND_NAME%%:*}"; USER_NAME="${ROLE_AND_NAME#*:}"; NODE_ID="${USER_NAME#*-node-}"; NODE_ID="${NODE_ID#field-node-}"
  run add "$ROLE" "$NODE_ID" >/dev/null
  grep -qx "topic write armor/health/$NODE_ID" <<<"$(block "$USER_NAME")" || fail "the $ROLE $NODE_ID cannot write its health report"
done
# An identity made before the report existed gets the one line, once, and the previous ACL is kept.
sed -i '/^topic write armor\/health\/a1$/d' "$ACL"
grep -qx 'topic write armor/health/a1' <<<"$(block alarm-node-a1)" && fail "the test could not take the line away"
run health-report alarm-node a1 >/dev/null
grep -qx 'topic write armor/health/a1' <<<"$(block alarm-node-a1)" || fail "health-report did not add the line"
[[ -f "$WORK/prefix/etc/mosquitto/acl.before-health" ]] || fail "the previous ACL was not kept"
BEFORE="$(cat "$ACL")"
run health-report alarm-node a1 >/dev/null
[[ "$(cat "$ACL")" == "$BEFORE" ]] || fail "a second health-report changed the ACL"
if run health-report alarm-node nobody >/dev/null 2>&1; then fail "an unknown node was accepted"; fi
if run health-report network-node a1 >/dev/null 2>&1; then fail "a node without a report was accepted"; fi
# A network node writes its state and reads nothing, and nothing reaches it from the broker.
run add network-node network-1 >/dev/null
NET="$(block network-node-network-1)"
grep -qx 'topic write armor/network/network-1/state' <<<"$NET" || fail "the network node cannot write its state"
if grep -q 'topic read\|readwrite\|/#$' <<<"$NET"; then fail "the network node has more than it needs: $NET"; fi
run remove network-node-network-1 >/dev/null
if grep -q 'network-1' "$ACL"; then fail "removing the network node left something of it"; fi
# A node that does not exist, and a bad word, change nothing.
if run electrical-switching nothing on >/dev/null 2>&1; then fail "an unknown node was accepted"; fi
if run electrical-switching electrical-1 maybe >/dev/null 2>&1; then fail "a bad state was accepted"; fi
if run electrical-switching 'Bad Node' on >/dev/null 2>&1; then fail "a bad node id was accepted"; fi

# Off takes both lines away and nothing else.
run electrical-switching electrical-1 off >/dev/null
if grep -q 'armor/electrical/electrical-1/command' "$ACL"; then fail "off left a line behind"; fi
grep -qx 'topic write armor/electrical/electrical-1/state' <<<"$(block electrical-node-electrical-1)" || fail "off took the node's own topics"
grep -qx 'topic readwrite armor/device/#' <<<"$(block armor-server)" || fail "off took the server's other rules"

# Removing a node that was turned on takes the server's line with it (an electrical node can be removed at all).
run electrical-switching electrical-2 on >/dev/null
run remove electrical-node-electrical-2 >/dev/null
if grep -q 'electrical-2' "$ACL"; then fail "removing the node left something of it: $(grep electrical-2 "$ACL")"; fi
grep -qx 'user electrical-node-electrical-1' "$ACL" || fail "removing one node removed another"
# The relays of an electrical node (devices of the device layer) are reachable only after an explicit `electrical-relays ... on`, for that node only.
run add electrical-node electrical-3 >/dev/null
run add electrical-node electrical-4 >/dev/null
if grep -q 'armor/device/electrical-3' "$ACL"; then fail "the relays of a new node are reachable before they were turned on"; fi
run electrical-relays electrical-3 on >/dev/null
grep -qx 'topic readwrite armor/device/electrical-3/#' <<<"$(block electrical-node-electrical-3)" || fail "the node cannot use its device topics after on"
if grep -q 'armor/device/electrical-4' "$ACL"; then fail "another node's relays became reachable"; fi
grep -qx 'topic write armor/electrical/electrical-3/state' <<<"$(block electrical-node-electrical-3)" || fail "turning the relays on took the node's own topics"
run electrical-relays electrical-3 on >/dev/null
[[ "$(grep -c 'armor/device/electrical-3/#' "$ACL")" == "1" ]] || fail "turning the relays on twice wrote the line twice"
if run electrical-relays nothing on >/dev/null 2>&1; then fail "relays of an unknown node were accepted"; fi
if run electrical-relays electrical-3 maybe >/dev/null 2>&1; then fail "a bad state was accepted for the relays"; fi
if run electrical-relays 'Bad Node' on >/dev/null 2>&1; then fail "a bad node id was accepted for the relays"; fi
run electrical-relays electrical-3 off >/dev/null
if grep -q 'armor/device/electrical-3' "$ACL"; then fail "off left the relays reachable"; fi
grep -qx 'topic write armor/electrical/electrical-3/state' <<<"$(block electrical-node-electrical-3)" || fail "turning the relays off took the node's own topics"
grep -qx 'topic readwrite armor/device/#' <<<"$(block armor-server)" || fail "the relays' off took the server's rules"
run electrical-relays electrical-3 off >/dev/null   # off again is harmless
# The same line in the block of a device with the same name must survive the node's off (the removal is scoped to the node's own block).
run add device garage >/dev/null
run add electrical-node garage >/dev/null
run electrical-relays garage on >/dev/null
run electrical-relays garage off >/dev/null
grep -qx 'topic readwrite armor/device/garage/#' <<<"$(block device-garage)" || fail "off for the node took the line of the device with the same name"

# An alarm node writes its state and its answers, reads nothing, and its commands are reachable only after an explicit `alarm-commands ... on`, for that node only.
run add alarm-node alarm-1 >/dev/null
run add alarm-node alarm-2 >/dev/null
AL="$(block alarm-node-alarm-1)"
grep -qx 'topic write armor/alarm/alarm-1/state' <<<"$AL" || fail "the alarm node cannot write its state"
grep -qx 'topic write armor/alarm/alarm-1/result' <<<"$AL" || fail "the alarm node cannot write its results"
grep -qx 'topic read armor/alarm/alarm-1/zigbee' <<<"$AL" || fail "the alarm node cannot read the Zigbee zones the server tells it"
if grep -v '^user ' <<<"$AL" | grep -v 'topic read armor/alarm/alarm-1/zigbee' | grep -v 'armor/control/' | grep -q 'topic read\|readwrite\|/#$'; then fail "the alarm node has more than it needs: $AL"; fi
if grep -q 'armor/alarm/alarm-1/command' "$ACL"; then fail "an alarm command is reachable before it was turned on"; fi
run alarm-commands alarm-1 on >/dev/null
grep -qx 'topic read armor/alarm/alarm-1/command' <<<"$(block alarm-node-alarm-1)" || fail "the alarm node cannot read its commands after on"
grep -qx 'topic write armor/alarm/alarm-1/command' <<<"$(block armor-server)" || fail "the server cannot write the alarm command after on"
if grep -q 'armor/alarm/alarm-2/command' "$ACL"; then fail "another alarm node became reachable"; fi
BEFORE="$(cat "$ACL")"
run alarm-commands alarm-1 on >/dev/null
[[ "$(cat "$ACL")" == "$BEFORE" ]] || fail "a second alarm on changed the ACL"
if run alarm-commands nothing on >/dev/null 2>&1; then fail "an unknown alarm node was accepted"; fi
if run alarm-commands alarm-1 maybe >/dev/null 2>&1; then fail "a bad state was accepted for the alarm"; fi
if run alarm-commands 'Bad Node' on >/dev/null 2>&1; then fail "a bad alarm node id was accepted"; fi
run alarm-commands alarm-1 off >/dev/null
if grep -q 'armor/alarm/alarm-1/command' "$ACL"; then fail "off left an alarm command reachable"; fi
grep -qx 'topic write armor/alarm/alarm-1/state' <<<"$(block alarm-node-alarm-1)" || fail "off took the alarm node's own topics"
# The relays of an alarm node (the siren and the others) are devices of the device layer, reachable only after an explicit `alarm-relays ... on`, for that node only.
if grep -q 'armor/device/alarm-1' "$ACL"; then fail "the relays of a new alarm node are reachable before they were turned on"; fi
run alarm-relays alarm-1 on >/dev/null
grep -qx 'topic readwrite armor/device/alarm-1/#' <<<"$(block alarm-node-alarm-1)" || fail "the alarm node cannot use its device topics after on"
if grep -q 'armor/device/alarm-2' "$ACL"; then fail "another alarm node's relays became reachable"; fi
grep -qx 'topic write armor/alarm/alarm-1/state' <<<"$(block alarm-node-alarm-1)" || fail "turning the alarm relays on took the node's own topics"
run alarm-relays alarm-1 on >/dev/null
[[ "$(grep -c 'armor/device/alarm-1/#' "$ACL")" == "1" ]] || fail "turning the alarm relays on twice wrote the line twice"
if run alarm-relays nothing on >/dev/null 2>&1; then fail "alarm relays of an unknown node were accepted"; fi
if run alarm-relays alarm-1 maybe >/dev/null 2>&1; then fail "a bad state was accepted for the alarm relays"; fi
run alarm-relays alarm-1 off >/dev/null
if grep -q 'armor/device/alarm-1' "$ACL"; then fail "off left the alarm relays reachable"; fi
grep -qx 'topic readwrite armor/device/#' <<<"$(block armor-server)" || fail "the alarm off took the server's rules"
run alarm-commands alarm-2 on >/dev/null
run remove alarm-node-alarm-2 >/dev/null
if grep -q 'alarm-2' "$ACL"; then fail "removing the alarm node left something of it"; fi
grep -qx 'user alarm-node-alarm-1' "$ACL" || fail "removing one alarm node removed another"

# The touch panel may say that it is alive and where its page is, and nothing else; Home Assistant's discovery is a line of the server's block that is there only on request.
run add hmi-node panel-1 >/dev/null
grep -qx 'topic write armor/node/panel-1/health' <<<"$(block hmi-node-panel-1)" || fail "the panel cannot say it is alive"
grep -qx 'topic write armor/node/panel-1/info' <<<"$(block hmi-node-panel-1)" || fail "the panel cannot say where its page is"
if grep -q 'armor/node/panel-1/telemetry\|armor/device/panel-1' "$ACL"; then fail "the panel can send radar tracks or use devices"; fi
if grep -qx 'topic write homeassistant/#' "$ACL"; then fail "Home Assistant discovery was reachable before it was asked for"; fi
run ha-discovery on >/dev/null
grep -qx 'topic write homeassistant/#' <<<"$(block armor-server)" || fail "ha-discovery on did not give the server the line"
run ha-discovery on >/dev/null
[[ "$(grep -c 'topic write homeassistant/#' "$ACL")" == "1" ]] || fail "turning discovery on twice wrote the line twice"
run ha-discovery off >/dev/null
if grep -q 'homeassistant' "$ACL"; then fail "ha-discovery off left the line"; fi
run ha-discovery on casa >/dev/null
grep -qx 'topic write casa/#' <<<"$(block armor-server)" || fail "a prefix of its own was not honoured"
if run ha-discovery on 'bad prefix' >/dev/null 2>&1; then fail "a prefix with a space was accepted"; fi
# Remote control of the nodes (restart, pause, standby ...): the five kinds of node read their own order topic and the broadcast one and write their own answer, and nothing more; only the
# server's identity may publish an order. No node can publish on any order topic, so none can command another.
sed -i 's|^topic readwrite armor/device/#$|topic write armor/control/+/command\ntopic read armor/control/+/result\ntopic read armor/control/+/maintenance\n&|' "$ACL"
grep -qx 'topic write armor/control/+/command' <<<"$(block armor-server)" || fail "the test could not give the server the order line"
for ROLE_AND_NAME in "node:field-node-c1" "hmi-node:hmi-node-c2" "solar-node:solar-node-c3" "electrical-node:electrical-node-c4" "alarm-node:alarm-node-c5"; do
  ROLE="${ROLE_AND_NAME%%:*}"; USER_NAME="${ROLE_AND_NAME#*:}"; NODE_ID="${USER_NAME#*-node-}"; NODE_ID="${NODE_ID#field-node-}"
  run add "$ROLE" "$NODE_ID" >/dev/null
  CB="$(block "$USER_NAME")"
  grep -qx "topic read armor/control/$NODE_ID/command" <<<"$CB" || fail "the $ROLE $NODE_ID cannot read its own control orders"
  grep -qx 'topic read armor/control/all/command' <<<"$CB" || fail "the $ROLE $NODE_ID cannot read the broadcast orders"
  grep -qx "topic write armor/control/$NODE_ID/result" <<<"$CB" || fail "the $ROLE $NODE_ID cannot write its own answer"
  grep -qx "topic write armor/control/$NODE_ID/maintenance" <<<"$CB" || fail "the $ROLE $NODE_ID cannot write its own maintenance signal"
  if grep -E 'armor/control/[^ ]*/maintenance' <<<"$CB" | grep -vx "topic write armor/control/$NODE_ID/maintenance" | grep -q .; then fail "the $ROLE $NODE_ID reaches a maintenance topic that is not its own: $CB"; fi
  if grep -E '^topic (write|readwrite) armor/control/.*/command|armor/control/(\+|#)|^topic readwrite armor/control' <<<"$CB" >/dev/null; then fail "the $ROLE $NODE_ID can publish an order: $CB"; fi
  if [[ "$(grep -c 'armor/control/' <<<"$CB")" != "4" ]]; then fail "the $ROLE $NODE_ID has other control rules than its four: $CB"; fi
done
# Only the server's block carries a write on an order topic, and no other identity reaches another node's answer or order.
[[ "$(grep -c '^topic write armor/control/.*/command' "$ACL")" == "1" ]] || fail "more than the server can publish orders"
grep -qx 'topic write armor/control/+/command' <<<"$(block armor-server)" || fail "the server lost the order line"
grep -qx 'topic read armor/control/+/maintenance' <<<"$(block armor-server)" || fail "the server cannot read the maintenance signals"
[[ "$(grep -c '^topic write armor/control/.*/maintenance' "$ACL")" == "$(grep -c '^topic write armor/control/[^+]*/result' "$ACL")" ]] || fail "every node that may answer may write its maintenance signal, and nothing else may"
if grep -E '^topic (write|readwrite) armor/control/(\+|#)/maintenance' "$ACL" >/dev/null; then fail "a wildcard may write maintenance signals"; fi
if grep -q 'armor/control/c3/\|armor/control/c1/' <<<"$(block electrical-node-c4)"; then fail "a node reaches another node's control topics"; fi
# A node with no control rules (installed before) gets exactly the four lines, once, and the previous ACL is kept; a node-control on a node that has them changes nothing.
awk -v u="user alarm-node-c5" 'BEGIN{inb=0} $0==u{inb=1; print; next} inb && /^$/{inb=0} inb && /armor\/control\//{next} {print}' "$ACL" >"$ACL.tmp" && cat "$ACL.tmp" >"$ACL"; rm -f "$ACL.tmp"
if grep -q 'armor/control/c5' "$ACL"; then fail "the test could not take the control lines away"; fi
run node-control alarm-node c5 >/dev/null
CB="$(block alarm-node-c5)"
grep -qx 'topic read armor/control/c5/command' <<<"$CB" || fail "node-control did not add the order line"
grep -qx 'topic read armor/control/all/command' <<<"$CB" || fail "node-control did not add the broadcast line"
grep -qx 'topic write armor/control/c5/result' <<<"$CB" || fail "node-control did not add the answer line"
grep -qx 'topic write armor/control/c5/maintenance' <<<"$CB" || fail "node-control did not add the maintenance line"
[[ -f "$WORK/prefix/etc/mosquitto/acl.before-control" ]] || fail "the previous ACL was not kept"
BEFORE="$(cat "$ACL")"
run node-control alarm-node c5 >/dev/null
[[ "$(cat "$ACL")" == "$BEFORE" ]] || fail "a second node-control changed the ACL"
if run node-control alarm-node nobody >/dev/null 2>&1; then fail "an unknown node was accepted for control"; fi
if run node-control network-node c5 >/dev/null 2>&1; then fail "a kind of node without control was accepted"; fi
if run node-control alarm-node 'Bad Node' >/dev/null 2>&1; then fail "a bad node id was accepted for control"; fi
# The network watcher and the plain devices get no control rules at all, and removing a node takes its control lines with it.
run add network-node cn1 >/dev/null
if grep -q 'armor/control/cn1' "$ACL"; then fail "the network node got control rules"; fi
run remove alarm-node-c5 >/dev/null
if grep -q 'armor/control/c5' "$ACL"; then fail "removing the node left control rules behind"; fi
grep -qx 'topic write armor/control/+/command' <<<"$(block armor-server)" || fail "removing a node took the server's order line"

echo "ARMOR_MQTT_IDENTITY=PASS the switch and the relays of an electrical node and the commands of an alarm node are reachable only after an explicit on, only the server publishes control orders and each node reads only its own, and off and remove take them away"
