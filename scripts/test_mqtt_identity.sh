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
if grep -q 'topic read\|readwrite\|/#$' <<<"$NODE"; then fail "the node has more than it needs: $NODE"; fi
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
echo "ARMOR_MQTT_IDENTITY=PASS the switch of an electrical node is reachable only after an explicit on, and off and remove take it away"
