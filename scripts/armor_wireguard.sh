#!/usr/bin/env bash
# ARMOR-DEVOPS - a WireGuard VPN into the house for the core machine (the CM5 or a Jetson): the phone and the laptop reach A.R.M.O.R. as if they were at home, without
# publishing the server, Studio or any node to the Internet. Only one UDP port is opened on the router.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
#
#   armor_wireguard.sh plan   --endpoint HOST[:PORT] [--subnet 10.66.0.0/24] [--port 51820] [--lan 192.168.0.0/24] [--route-lan IFACE]   # what would be written; changes nothing
#   sudo armor_wireguard.sh setup --endpoint ... (same options)        # keys, /etc/wireguard/armor-wg0.conf, the boot unit, and the VPN network told to the server
#   sudo armor_wireguard.sh add-peer NAME [--full-tunnel]              # a new phone or laptop: prints its configuration (and a QR code when qrencode is installed)
#   sudo armor_wireguard.sh show NAME                                   # the configuration of a peer again
#   sudo armor_wireguard.sh remove-peer NAME                            # the peer can no longer connect
#   sudo armor_wireguard.sh list | status | remove
#
# The VPN network (10.66.0.0/24 by default) is written to ARMOR_VPN_NETWORKS in the server's environment file, so the server treats a phone on the VPN like a phone at home
# (restart the server for it to take effect). If the host firewall (firewall_core.sh) is used with --clients, add the VPN network to it.
# The private key of the server and the keys of the peers stay under $PREFIX/etc/wireguard (0700), never in a repository.
# Settings from the environment (for tests and unusual installs): ARMOR_WG_ETC (/etc/wireguard), ARMOR_WG_STATE (PREFIX/etc/wireguard), ARMOR_WG_ENV_FILE (PREFIX/etc/armor.env),
# ARMOR_WG_NOSYSTEMD=1 (do not touch systemd or a running interface).
# Nothing here has been run on the CM5.
set -euo pipefail

PREFIX="${ARMOR_PREFIX:-/opt/armor}"
IFACE="armor-wg0"
SUBNET="10.66.0.0/24"; PORT="51820"; LAN="192.168.0.0/24"; ENDPOINT=""; ROUTE_LAN=""; FULL_TUNNEL=0
WG_ETC="${ARMOR_WG_ETC:-/etc/wireguard}"
STATE="${ARMOR_WG_STATE:-$PREFIX/etc/wireguard}"
ENV_FILE="${ARMOR_WG_ENV_FILE:-$PREFIX/etc/armor.env}"

fail() { echo "armor_wireguard: $*" >&2; exit 2; }
say() { echo "[armor-wireguard] $*"; }

valid_cidr() {
  local text="$1" octet mask
  [[ "$text" =~ ^([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})/([0-9]{1,2})$ ]] || return 1
  for octet in "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}" "${BASH_REMATCH[3]}" "${BASH_REMATCH[4]}"; do (( 10#$octet <= 255 )) || return 1; done
  mask="${BASH_REMATCH[5]}"; (( 10#$mask >= 8 && 10#$mask <= 30 )) || return 1
}
valid_port() { [[ "$1" =~ ^[0-9]{1,5}$ ]] && (( 10#$1 >= 1 && 10#$1 <= 65535 )); }
valid_name() { [[ "$1" =~ ^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$ ]]; }
valid_host() { [[ "$1" =~ ^[A-Za-z0-9]([A-Za-z0-9.-]{0,251}[A-Za-z0-9])?$ ]]; }
valid_iface() { [[ "$1" =~ ^[A-Za-z0-9_.-]{1,15}$ ]]; }

# 10.66.0.0/24 -> 10.66.0 (the first three octets; the VPN network is always a /24 or wider and the hosts are numbered inside the last octet)
base_of() { local a b c; IFS=. read -r a b c _ <<<"${SUBNET%/*}"; echo "$a.$b.$c"; }

COMMAND="${1:-}"
[[ -n "$COMMAND" ]] || fail "usage: armor_wireguard.sh plan|setup|add-peer|show|remove-peer|list|status|remove [options]  (see the header of the script)"
shift
NAME=""
if [[ "$COMMAND" == add-peer || "$COMMAND" == show || "$COMMAND" == remove-peer ]]; then
  NAME="${1:-}"; [[ -n "$NAME" ]] || fail "$COMMAND wants the name of the peer, such as phone-juan"; valid_name "$NAME" || fail "the name of a peer is letters, digits, - and _ (at most 32)"; shift
fi
while [[ $# -gt 0 ]]; do
  case "$1" in
    --endpoint) ENDPOINT="${2:-}"; shift 2 ;;
    --subnet) valid_cidr "${2:-}" || fail "--subnet wants a network like 10.66.0.0/24"; SUBNET="$2"; shift 2 ;;
    --port) valid_port "${2:-}" || fail "--port wants a UDP port number"; PORT="$((10#$2))"; shift 2 ;;
    --lan) valid_cidr "${2:-}" || fail "--lan wants the network of the house, such as 192.168.0.0/24"; LAN="$2"; shift 2 ;;
    --route-lan) valid_iface "${2:-}" || fail "--route-lan wants the name of the interface that faces the house network (eth0)"; ROUTE_LAN="$2"; shift 2 ;;
    --full-tunnel) FULL_TUNNEL=1; shift ;;
    --prefix) PREFIX="${2:-}"; STATE="${ARMOR_WG_STATE:-$PREFIX/etc/wireguard}"; ENV_FILE="${ARMOR_WG_ENV_FILE:-$PREFIX/etc/armor.env}"; shift 2 ;;
    -h|--help) sed -n '2,22p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) fail "unknown option: $1" ;;
  esac
done

endpoint_check() {
  [[ -n "$ENDPOINT" ]] || fail "--endpoint is needed: the public name or address the phone will connect to (and the port, if it is not $PORT)"
  local host="${ENDPOINT%%:*}"
  if [[ "$ENDPOINT" == *:* ]]; then valid_port "${ENDPOINT##*:}" || fail "the port of --endpoint is not a port number"; PORT_PUBLIC="$((10#${ENDPOINT##*:}))"; else PORT_PUBLIC="$PORT"; fi
  valid_host "$host" || fail "--endpoint wants a host name or an address"
  ENDPOINT_HOST="$host"
}

server_conf() {
  local base private="$1"
  base="$(base_of)"
  echo "# A.R.M.O.R. VPN. Written by armor_wireguard.sh; the peers below are added and removed with it."
  echo "[Interface]"
  echo "Address = $base.1/24"
  echo "ListenPort = $PORT"
  echo "PrivateKey = $private"
  if [[ -n "$ROUTE_LAN" ]]; then
    echo "# The phone can also reach the nodes of the house through this machine."
    echo "PostUp = sysctl -w net.ipv4.ip_forward=1; nft add table ip armor_wg; nft 'add chain ip armor_wg post { type nat hook postrouting priority 100 ; }'; nft add rule ip armor_wg post oifname \"$ROUTE_LAN\" ip saddr $SUBNET masquerade"
    echo "PostDown = nft delete table ip armor_wg"
  fi
}

peer_block() {   # name public preshared address
  echo ""
  echo "# peer: $1"
  echo "[Peer]"
  echo "PublicKey = $2"
  echo "PresharedKey = $3"
  echo "AllowedIPs = $4/32"
}

case "$COMMAND" in
  plan)
    endpoint_check
    say "the VPN would be $SUBNET (this machine: $(base_of).1), UDP port $PORT, reached at $ENDPOINT_HOST:$PORT_PUBLIC; the phones would reach $LAN${ROUTE_LAN:+ through $ROUTE_LAN}"
    say "on the router: forward UDP $PORT_PUBLIC to this machine's port $PORT"
    say "ARMOR_VPN_NETWORKS=$SUBNET would be written to $ENV_FILE"
    server_conf "<private key made at setup>"
    ;;

  setup)
    [[ "$(id -u)" -eq 0 || -n "${ARMOR_WG_ETC:-}" ]] || fail "setup needs root (sudo)"
    command -v wg >/dev/null || fail "WireGuard is not installed: sudo apt install wireguard-tools"
    endpoint_check
    ( umask 077; mkdir -p "$STATE/peers" "$WG_ETC" )
    chmod 0700 "$STATE" "$STATE/peers"
    if [[ ! -f "$STATE/server.key" ]]; then ( umask 077; wg genkey >"$STATE/server.key" ); say "made the key of this machine"; fi
    wg pubkey <"$STATE/server.key" >"$STATE/server.pub"
    # The settings are remembered so that add-peer needs nothing but the name.
    ( umask 077; printf 'ENDPOINT_HOST=%s\nPORT_PUBLIC=%s\nPORT=%s\nSUBNET=%s\nLAN=%s\nROUTE_LAN=%s\n' "$ENDPOINT_HOST" "$PORT_PUBLIC" "$PORT" "$SUBNET" "$LAN" "$ROUTE_LAN" >"$STATE/settings" )
    private="$(cat "$STATE/server.key")"
    ( umask 077; { server_conf "$private"; for peer in "$STATE"/peers/*.env; do [[ -f "$peer" ]] || continue; ( . "$peer"; peer_block "$NAME" "$PUBLIC" "$PRESHARED" "$ADDRESS" ); done; } >"$WG_ETC/$IFACE.conf" )
    chmod 0600 "$WG_ETC/$IFACE.conf"
    # the server counts a phone on the VPN as one at home
    if [[ -f "$ENV_FILE" ]]; then
      if grep -q '^ARMOR_VPN_NETWORKS=' "$ENV_FILE"; then sed -i "s#^ARMOR_VPN_NETWORKS=.*#ARMOR_VPN_NETWORKS=$SUBNET#" "$ENV_FILE"; else printf 'ARMOR_VPN_NETWORKS=%s\n' "$SUBNET" >>"$ENV_FILE"; fi
      say "ARMOR_VPN_NETWORKS=$SUBNET is in $ENV_FILE: restart the server (sudo systemctl restart armor-server) so that it takes effect"
    else
      say "$ENV_FILE does not exist: put ARMOR_VPN_NETWORKS=$SUBNET in the environment of the server yourself"
    fi
    if [[ "${ARMOR_WG_NOSYSTEMD:-0}" != 1 ]]; then
      systemctl enable "wg-quick@$IFACE" >/dev/null
      systemctl restart "wg-quick@$IFACE"
    fi
    say "the VPN is ready. Forward UDP $PORT_PUBLIC on the router to this machine's port $PORT, then: sudo $0 add-peer phone-NAME"
    say "if the host firewall is used with --clients, add $SUBNET to it"
    ;;

  add-peer)
    [[ -f "$STATE/settings" ]] || fail "run setup first"
    command -v wg >/dev/null || fail "WireGuard is not installed: sudo apt install wireguard-tools"
    [[ ! -f "$STATE/peers/$NAME.env" ]] || fail "there is already a peer called $NAME (show it with: $0 show $NAME)"
    # shellcheck disable=SC1091
    . "$STATE/settings"
    SUBNET="$SUBNET"
    base="$(base_of)"
    used=" "
    for peer in "$STATE"/peers/*.env; do [[ -f "$peer" ]] || continue; used+="$(sed -n 's/^ADDRESS=//p' "$peer") "; done
    address=""
    for n in $(seq 2 254); do [[ "$used" == *" $base.$n "* ]] || { address="$base.$n"; break; }; done
    [[ -n "$address" ]] || fail "the VPN network is full"
    ( umask 077
      key="$(wg genkey)"; psk="$(wg genpsk)"; pub="$(printf '%s' "$key" | wg pubkey)"
      printf 'NAME=%s\nADDRESS=%s\nPUBLIC=%s\nPRESHARED=%s\nPRIVATE=%s\n' "$NAME" "$address" "$pub" "$psk" "$key" >"$STATE/peers/$NAME.env" )
    ( . "$STATE/peers/$NAME.env"; { echo ""; echo "# peer: $NAME"; echo "[Peer]"; echo "PublicKey = $PUBLIC"; echo "PresharedKey = $PRESHARED"; echo "AllowedIPs = $ADDRESS/32"; } >>"$WG_ETC/$IFACE.conf" )
    if [[ "${ARMOR_WG_NOSYSTEMD:-0}" != 1 ]] && ip link show "$IFACE" >/dev/null 2>&1; then wg syncconf "$IFACE" <(wg-quick strip "$IFACE"); fi
    [[ "$FULL_TUNNEL" -eq 1 ]] && echo "FULL_TUNNEL=1" >>"$STATE/peers/$NAME.env"
    say "added $NAME with the address $address"
    bash "$0" show "$NAME" --prefix "$PREFIX"
    ;;

  show)
    [[ -f "$STATE/peers/$NAME.env" ]] || fail "there is no peer called $NAME"
    # shellcheck disable=SC1091
    . "$STATE/settings"; . "$STATE/peers/$NAME.env"
    if [[ "${FULL_TUNNEL:-0}" == 1 ]]; then allowed="0.0.0.0/0"; else allowed="$SUBNET, $LAN"; fi
    config="[Interface]
PrivateKey = $PRIVATE
Address = $ADDRESS/32

[Peer]
PublicKey = $(cat "$STATE/server.pub")
PresharedKey = $PRESHARED
Endpoint = $ENDPOINT_HOST:$PORT_PUBLIC
AllowedIPs = $allowed
PersistentKeepalive = 25"
    echo "---- configuration for $NAME (it holds a private key: give it only to that device, then delete it) ----"
    echo "$config"
    echo "----"
    if command -v qrencode >/dev/null; then echo "$config" | qrencode -t ansiutf8; else say "install qrencode to get a QR code the WireGuard app can scan"; fi
    ;;

  remove-peer)
    [[ -f "$STATE/peers/$NAME.env" ]] || fail "there is no peer called $NAME"
    # shellcheck disable=SC1091
    . "$STATE/settings"
    rm -f "$STATE/peers/$NAME.env"
    # the server file is written again from what is left
    private="$(cat "$STATE/server.key")"
    ( umask 077; { server_conf "$private"; for peer in "$STATE"/peers/*.env; do [[ -f "$peer" ]] || continue; ( . "$peer"; peer_block "$NAME" "$PUBLIC" "$PRESHARED" "$ADDRESS" ); done; } >"$WG_ETC/$IFACE.conf" )
    if [[ "${ARMOR_WG_NOSYSTEMD:-0}" != 1 ]] && ip link show "$IFACE" >/dev/null 2>&1; then wg syncconf "$IFACE" <(wg-quick strip "$IFACE"); fi
    say "$NAME was removed: it can no longer connect"
    ;;

  list)
    [[ -d "$STATE/peers" ]] || { say "no VPN yet"; exit 0; }
    for peer in "$STATE"/peers/*.env; do [[ -f "$peer" ]] || continue; ( . "$peer"; echo "$NAME  $ADDRESS" ); done
    ;;

  status)
    [[ "${ARMOR_WG_NOSYSTEMD:-0}" == 1 ]] && { say "systemd is not used here"; exit 0; }
    wg show "$IFACE" 2>&1 || say "the VPN is not running"
    ;;

  remove)
    [[ "$(id -u)" -eq 0 ]] || fail "remove needs root (sudo)"
    if [[ "${ARMOR_WG_NOSYSTEMD:-0}" != 1 ]]; then systemctl disable --now "wg-quick@$IFACE" 2>/dev/null || true; fi
    # nothing is deleted: the keys are put aside
    if [[ -d "$STATE" ]]; then mv "$STATE" "$STATE.removed.$(date +%s)"; fi
    [[ ! -f "$WG_ETC/$IFACE.conf" ]] || mv "$WG_ETC/$IFACE.conf" "$WG_ETC/$IFACE.conf.removed.$(date +%s)"
    say "the VPN is off; its keys were kept aside next to the old folder"
    ;;

  *) fail "unknown command: $COMMAND" ;;
esac
