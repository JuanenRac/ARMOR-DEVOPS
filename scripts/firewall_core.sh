#!/usr/bin/env bash
# ARMOR-DEVOPS - the host firewall of the core machine (the CM5 or a Jetson): who may reach A.R.M.O.R.'s own ports, and nobody else.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
#
# It puts the design of docs/SECURITY_BASELINE.md into rules for the machine that runs the server, the broker and Studio:
#   - the broker's port is reachable only from the FIELD network (the nodes) and from this machine: never from the clients' network, never from the Internet;
#   - the server's and Studio's ports are reachable only from the CLIENTS' network (and this machine), when --clients is given.
# The rules live in ONE table of their own (inet armor_core) that only ever mentions A.R.M.O.R.'s ports and has an "accept" policy: everything else on the
# machine (SSH, another project's ports, DNS...) is left exactly as it was. The default ports are the ones install_cm5.sh uses. The rules act on the machine's
# INPUT: services installed natively (install_cm5.sh) are covered; a port that Docker publishes is forwarded, not input, and is not (publish it on loopback,
# as docker-compose.yml does, and let Caddy answer).
#
#   firewall_core.sh print  --field 192.168.0.0/24 [--clients 192.168.0.0/24] [--admin-any] ...   # the rules, on the standard output (nothing is changed)
#   firewall_core.sh check  --field ...                                                             # the same rules, checked by nft (-c) when it is installed
#   sudo firewall_core.sh apply --field ... [--clients ...] [--rollback-after 120] [--persist]      # loads them; with --rollback-after they are removed again after that many seconds
#                                                                                                     unless you run `confirm` (a rule that shut you out undoes itself)
#   sudo firewall_core.sh confirm                                                                   # keep the rules loaded by `apply --rollback-after`
#   sudo firewall_core.sh revert                                                                    # remove the table (and the boot unit, if there is one)
#   firewall_core.sh status                                                                         # the table as loaded
#
# Options: --field CIDR (required except for revert/status/confirm), --clients CIDR (repeatable), --mqtt-port N (18883), --server-port N (18080), --studio-port N (18081),
#          --trust-iface NAME (repeatable: an interface whose traffic is accepted, e.g. a Docker bridge), --table NAME (armor_core).
# IPv4 networks only. Nothing here has been run on the CM5.
set -euo pipefail

TABLE="armor_core"
MQTT_PORT="18883"; SERVER_PORT="18080"; STUDIO_PORT="18081"
FIELD=(); CLIENTS=(); IFACES=()
ROLLBACK=0; PERSIST=0
CONF_DIR="/etc/armor"; CONF_FILE="$CONF_DIR/firewall.nft"; UNIT="armor-firewall"; ROLLBACK_UNIT="armor-firewall-rollback"

fail() { echo "firewall_core: $*" >&2; exit 2; }

valid_cidr() {
  local text="$1" address mask octet
  [[ "$text" =~ ^([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})(/([0-9]{1,2}))?$ ]] || return 1
  for octet in "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}" "${BASH_REMATCH[3]}" "${BASH_REMATCH[4]}"; do
    (( 10#$octet <= 255 )) || return 1
  done
  mask="${BASH_REMATCH[6]:-32}"
  (( 10#$mask <= 32 )) || return 1
  return 0
}

valid_port() { [[ "$1" =~ ^[0-9]{1,5}$ ]] && (( 10#$1 >= 1 && 10#$1 <= 65535 )); }
valid_name() { [[ "$1" =~ ^[A-Za-z0-9_.-]{1,15}$ ]]; }

COMMAND="${1:-}"
[[ -n "$COMMAND" ]] || fail "usage: firewall_core.sh print|check|apply|confirm|revert|status [options]  (see the header of the script)"
shift
while [[ $# -gt 0 ]]; do
  case "$1" in
    --field) valid_cidr "${2:-}" || fail "--field wants an IPv4 network like 192.168.0.0/24, not '${2:-}'"; FIELD+=("$2"); shift 2 ;;
    --clients) valid_cidr "${2:-}" || fail "--clients wants an IPv4 network like 192.168.0.0/24, not '${2:-}'"; CLIENTS+=("$2"); shift 2 ;;
    --mqtt-port) valid_port "${2:-}" || fail "--mqtt-port wants a port number"; MQTT_PORT="$2"; shift 2 ;;
    --server-port) valid_port "${2:-}" || fail "--server-port wants a port number"; SERVER_PORT="$2"; shift 2 ;;
    --studio-port) valid_port "${2:-}" || fail "--studio-port wants a port number"; STUDIO_PORT="$2"; shift 2 ;;
    --trust-iface) valid_name "${2:-}" || fail "--trust-iface wants an interface name"; IFACES+=("$2"); shift 2 ;;
    --table) valid_name "${2:-}" || fail "--table wants a plain name"; TABLE="$2"; shift 2 ;;
    --rollback-after) [[ "${2:-}" =~ ^[0-9]{1,4}$ ]] && (( 10#$2 >= 10 )) || fail "--rollback-after wants a number of seconds, at least 10"; ROLLBACK="$((10#$2))"; shift 2 ;;
    --persist) PERSIST=1; shift ;;
    *) fail "unknown option '$1'" ;;
  esac
done

joined() { local IFS=,; echo "$*"; }

ruleset() {
  [[ ${#FIELD[@]} -gt 0 ]] || fail "the field network is required (--field 192.168.0.0/24): without it the broker would be closed to the nodes"
  [[ "$MQTT_PORT" != "$SERVER_PORT" && "$MQTT_PORT" != "$STUDIO_PORT" && "$SERVER_PORT" != "$STUDIO_PORT" ]] || fail "the three ports must differ"
  local field clients
  field="$(joined "${FIELD[@]}")"
  echo "# A.R.M.O.R. host firewall (ARMOR-DEVOPS scripts/firewall_core.sh). Only A.R.M.O.R.'s own ports are mentioned; the policy accepts everything else."
  echo "table inet $TABLE {"
  echo "  chain input {"
  echo "    type filter hook input priority -5; policy accept;"
  echo "    ct state established,related accept"
  echo "    iifname \"lo\" accept"
  local iface
  for iface in "${IFACES[@]+"${IFACES[@]}"}"; do echo "    iifname \"$iface\" accept"; done
  echo "    # the broker: the nodes of the field network, and this machine"
  echo "    tcp dport $MQTT_PORT ip saddr { $field } accept"
  echo "    tcp dport $MQTT_PORT counter drop"
  if [[ ${#CLIENTS[@]} -gt 0 ]]; then
    clients="$(joined "${CLIENTS[@]}")"
    echo "    # the server and Studio: the clients' network, and this machine"
    echo "    tcp dport { $SERVER_PORT, $STUDIO_PORT } ip saddr { $clients } accept"
    echo "    tcp dport { $SERVER_PORT, $STUDIO_PORT } counter drop"
  else
    echo "    # the server and Studio: no --clients given, so they stay as open as they were (the login protects them)"
  fi
  echo "  }"
  echo "}"
}

need_root() { [[ "$(id -u)" == "0" ]] || fail "$COMMAND needs root (sudo)"; }
need_nft() { command -v nft >/dev/null 2>&1 || fail "nft (nftables) is not installed"; }

case "$COMMAND" in
  print) ruleset ;;
  check)
    text="$(ruleset)"
    if ! command -v nft >/dev/null 2>&1; then echo "FIREWALL_CHECK=SKIP nft is not installed here; the rules were generated but not checked"; exit 0; fi
    printf '%s\n' "$text" | nft -c -f - && echo "FIREWALL_CHECK=PASS nft accepts the rules"
    ;;
  apply)
    need_root; need_nft
    text="$(ruleset)"
    printf '%s\n' "$text" | nft -c -f - || fail "nft refused the rules: nothing was changed"
    install -d -m 0750 "$CONF_DIR"
    printf '%s\n' "$text" > "$CONF_FILE"; chmod 0640 "$CONF_FILE"
    nft delete table inet "$TABLE" 2>/dev/null || true
    nft -f "$CONF_FILE"
    echo "loaded: table inet $TABLE (the rules are in $CONF_FILE)"
    if (( ROLLBACK > 0 )); then
      command -v systemd-run >/dev/null 2>&1 || { nft delete table inet "$TABLE"; fail "--rollback-after needs systemd-run; the rules were removed again"; }
      systemctl stop "$ROLLBACK_UNIT.timer" 2>/dev/null || true
      systemd-run --unit "$ROLLBACK_UNIT" --on-active="${ROLLBACK}s" "$(command -v nft)" delete table inet "$TABLE" >/dev/null
      echo "they will be REMOVED again in ${ROLLBACK} s unless you run: sudo $0 confirm"
    fi
    if (( PERSIST )); then
      cat > "/etc/systemd/system/$UNIT.service" <<EOF
[Unit]
Description=A.R.M.O.R. host firewall (only its own ports)
After=network-pre.target
Before=network.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/sh -c '$(command -v nft) delete table inet $TABLE 2>/dev/null; $(command -v nft) -f $CONF_FILE'
ExecStop=$(command -v nft) delete table inet $TABLE

[Install]
WantedBy=multi-user.target
EOF
      systemctl daemon-reload; systemctl enable "$UNIT.service" >/dev/null
      echo "the rules will be loaded at every boot ($UNIT.service)"
    fi
    ;;
  confirm)
    need_root
    systemctl stop "$ROLLBACK_UNIT.timer" 2>/dev/null && echo "confirmed: the rules stay" || echo "nothing to confirm (no rollback was pending)"
    ;;
  revert)
    need_root; need_nft
    systemctl stop "$ROLLBACK_UNIT.timer" 2>/dev/null || true
    nft delete table inet "$TABLE" 2>/dev/null && echo "removed: table inet $TABLE" || echo "there was no table inet $TABLE"
    if [[ -f "/etc/systemd/system/$UNIT.service" ]]; then
      systemctl disable --now "$UNIT.service" >/dev/null 2>&1 || true
      rm -f "/etc/systemd/system/$UNIT.service"; systemctl daemon-reload
      echo "removed: $UNIT.service"
    fi
    rm -f "$CONF_FILE"
    ;;
  status) need_nft; nft list table inet "$TABLE" ;;
  *) fail "unknown command '$COMMAND' (print, check, apply, confirm, revert, status)" ;;
esac
