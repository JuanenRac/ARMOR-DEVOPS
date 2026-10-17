#!/usr/bin/env bash
# ARMOR-DEVOPS - keeps a name that points at the house (DuckDNS, Cloudflare or any address you can call) up to date when the Internet provider changes the public address.
# The phone then reaches the house by a name that does not change. It only talks to the provider you choose and to one "what is my address" service, and only when the address
# changed.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
#
#   sudo armor_ddns.sh setup --provider duckdns    --domain NAME --token TOKEN
#   sudo armor_ddns.sh setup --provider cloudflare --zone ZONE_ID --record-name casa.example.org --token API_TOKEN      # the token needs "DNS: Edit" on that zone only
#   sudo armor_ddns.sh setup --provider url        --url 'https://provider.example/update?host=casa&ip={ip}'            # {ip} is replaced by the public address
#   sudo armor_ddns.sh update [--force]    # once now (the timer calls this every five minutes)
#   armor_ddns.sh status | sudo armor_ddns.sh remove
#
# The token is kept in $PREFIX/etc/armor.ddns.env (0600) and is never put on a command line of a program it calls. A public address that is private or in the range of a
# provider that shares one address between many houses (100.64.0.0/10) is refused with an explanation: no name can reach that house.
# Settings from the environment (for tests): ARMOR_DDNS_ENV (the env file), ARMOR_DDNS_STATE (the last address), ARMOR_DDNS_IP_URL (the address service),
# ARMOR_DDNS_NOSYSTEMD=1 (do not touch systemd), ARMOR_DDNS_CURL (the curl program).
# Nothing here has been run on the CM5.
set -euo pipefail

PREFIX="${ARMOR_PREFIX:-/opt/armor}"
ENV_FILE="${ARMOR_DDNS_ENV:-$PREFIX/etc/armor.ddns.env}"
STATE_FILE="${ARMOR_DDNS_STATE:-$PREFIX/data/ddns.last}"
IP_URL="${ARMOR_DDNS_IP_URL:-https://api.ipify.org}"
CURL="${ARMOR_DDNS_CURL:-curl}"
PROVIDER=""; DOMAIN=""; TOKEN=""; ZONE=""; RECORD=""; URL=""; FORCE=0

fail() { echo "armor_ddns: $*" >&2; exit 2; }
say() { echo "[armor-ddns] $*"; }

valid_ipv4() { local a b c d; [[ "$1" =~ ^([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})$ ]] || return 1; for n in "${BASH_REMATCH[@]:1}"; do (( 10#$n <= 255 )) || return 1; done; }
# an address a name can reach: not private, not loopback, not link-local, not in the shared range of a provider that gives one address to many houses
public_ipv4() {
  valid_ipv4 "$1" || return 1
  local a b; IFS=. read -r a b _ <<<"$1"; a=$((10#$a)); b=$((10#$b))
  (( a == 10 || a == 127 || a == 0 || a >= 224 )) && return 1
  (( a == 192 && b == 168 )) && return 1
  (( a == 172 && b >= 16 && b <= 31 )) && return 1
  (( a == 169 && b == 254 )) && return 1
  (( a == 100 && b >= 64 && b <= 127 )) && return 1
  return 0
}

COMMAND="${1:-}"
[[ -n "$COMMAND" ]] || fail "usage: armor_ddns.sh setup|update|status|remove [options]  (see the header of the script)"
shift
while [[ $# -gt 0 ]]; do
  case "$1" in
    --provider) PROVIDER="${2:-}"; [[ "$PROVIDER" == duckdns || "$PROVIDER" == cloudflare || "$PROVIDER" == url ]] || fail "--provider is duckdns, cloudflare or url"; shift 2 ;;
    --domain) DOMAIN="${2:-}"; [[ "$DOMAIN" =~ ^[a-z0-9][a-z0-9-]{0,62}$ ]] || fail "--domain is the DuckDNS name without .duckdns.org"; shift 2 ;;
    --token) TOKEN="${2:-}"; [[ "$TOKEN" =~ ^[A-Za-z0-9._~-]{8,200}$ ]] || fail "--token has characters a token does not have, or is too short"; shift 2 ;;
    --zone) ZONE="${2:-}"; [[ "$ZONE" =~ ^[a-f0-9]{32}$ ]] || fail "--zone is the Cloudflare zone id (32 hexadecimal digits)"; shift 2 ;;
    --record-name) RECORD="${2:-}"; [[ "$RECORD" =~ ^[A-Za-z0-9]([A-Za-z0-9.-]{0,251}[A-Za-z0-9])?$ ]] || fail "--record-name is the name to keep up to date"; shift 2 ;;
    --url) URL="${2:-}"; [[ "$URL" =~ ^https://[A-Za-z0-9.-]+(/[A-Za-z0-9._~:/?\#@!\$\&\'\(\)*+,\;=%{}-]*)?$ ]] || fail "--url must be an https address"; [[ "$URL" == *"{ip}"* ]] || fail "--url must contain {ip}"; shift 2 ;;
    --force) FORCE=1; shift ;;
    --prefix) PREFIX="${2:-}"; ENV_FILE="${ARMOR_DDNS_ENV:-$PREFIX/etc/armor.ddns.env}"; STATE_FILE="${ARMOR_DDNS_STATE:-$PREFIX/data/ddns.last}"; shift 2 ;;
    -h|--help) sed -n '2,19p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) fail "unknown option: $1" ;;
  esac
done

current_ip() {
  local ip
  ip="$("$CURL" -4 -fsS --max-time 10 "$IP_URL" 2>/dev/null | tr -d '[:space:]')" || fail "could not find out the public address of the house (the address service did not answer)"
  valid_ipv4 "$ip" || fail "the address service did not answer with an address"
  public_ipv4 "$ip" || fail "the address the Internet sees is $ip, which no name can reach (it is private or shared by the provider between many houses: ask the provider for a public address, or use the VPN with a service that has one)"
  echo "$ip"
}

# a request whose secret is not on the command line: the options go to curl through its standard input
call() {   # method url [header...] ; body from the variable BODY
  local method="$1" url="$2"; shift 2
  { printf 'url = "%s"\nrequest = "%s"\nsilent\nshow-error\nfail\nmax-time = 20\n' "$url" "$method"
    for header in "$@"; do printf 'header = "%s"\n' "$header"; done
    [[ -z "${BODY:-}" ]] || printf 'data = "%s"\n' "${BODY//\"/\\\"}"
  } | "$CURL" -K -
}

case "$COMMAND" in
  setup)
    [[ "$(id -u)" -eq 0 || -n "${ARMOR_DDNS_ENV:-}" ]] || fail "setup needs root (sudo)"
    [[ -n "$PROVIDER" ]] || fail "--provider is needed"
    case "$PROVIDER" in
      duckdns) [[ -n "$DOMAIN" && -n "$TOKEN" ]] || fail "duckdns needs --domain and --token" ;;
      cloudflare) [[ -n "$ZONE" && -n "$RECORD" && -n "$TOKEN" ]] || fail "cloudflare needs --zone, --record-name and --token" ;;
      url) [[ -n "$URL" ]] || fail "url needs --url" ;;
    esac
    mkdir -p "$(dirname "$ENV_FILE")" "$(dirname "$STATE_FILE")"
    ( umask 077; { echo "PROVIDER=$PROVIDER"; echo "DOMAIN=$DOMAIN"; echo "TOKEN=$TOKEN"; echo "ZONE=$ZONE"; echo "RECORD=$RECORD"; echo "URL='$URL'"; } >"$ENV_FILE" )
    chmod 0600 "$ENV_FILE"
    if [[ "${ARMOR_DDNS_NOSYSTEMD:-0}" != 1 ]]; then
      cat >/etc/systemd/system/armor-ddns.service <<EOF
[Unit]
Description=A.R.M.O.R. dynamic DNS update
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/bin/env bash $PREFIX/bin/armor_ddns.sh update --prefix $PREFIX
ProtectSystem=strict
ReadWritePaths=$PREFIX/data
PrivateTmp=true
NoNewPrivileges=true
EOF
      cat >/etc/systemd/system/armor-ddns.timer <<EOF
[Unit]
Description=A.R.M.O.R. dynamic DNS update every five minutes

[Timer]
OnBootSec=1min
OnUnitActiveSec=5min

[Install]
WantedBy=timers.target
EOF
      install -d -m 0755 "$PREFIX/bin"; install -m 0755 "${BASH_SOURCE[0]}" "$PREFIX/bin/armor_ddns.sh"
      systemctl daemon-reload; systemctl enable --now armor-ddns.timer >/dev/null
    fi
    say "set up for $PROVIDER; checking now"
    bash "${BASH_SOURCE[0]}" update --force --prefix "$PREFIX"
    ;;

  update)
    [[ -f "$ENV_FILE" ]] || fail "run setup first"
    # shellcheck disable=SC1090
    . "$ENV_FILE"
    ip="$(current_ip)"
    if [[ "$FORCE" -eq 0 && -f "$STATE_FILE" && "$(cat "$STATE_FILE")" == "$ip" ]]; then say "the address is still $ip: nothing to do"; exit 0; fi
    case "$PROVIDER" in
      duckdns)
        answer="$(BODY="" call GET "https://www.duckdns.org/update?domains=$DOMAIN&token=$TOKEN&ip=$ip")" || fail "DuckDNS did not accept the update"
        [[ "$answer" == OK* ]] || fail "DuckDNS answered: $answer"
        ;;
      cloudflare)
        auth="Authorization: Bearer $TOKEN"
        found="$(BODY="" call GET "https://api.cloudflare.com/client/v4/zones/$ZONE/dns_records?type=A&name=$RECORD" "$auth")" || fail "Cloudflare did not answer"
        id="$(grep -o '"id":"[a-f0-9]\{32\}"' <<<"$found" | head -1 | cut -d'"' -f4 || true)"
        body="{\"type\":\"A\",\"name\":\"$RECORD\",\"content\":\"$ip\",\"ttl\":120,\"proxied\":false}"
        if [[ -n "$id" ]]; then
          BODY="$body" call PUT "https://api.cloudflare.com/client/v4/zones/$ZONE/dns_records/$id" "$auth" "Content-Type: application/json" >/dev/null || fail "Cloudflare did not accept the update"
        else
          BODY="$body" call POST "https://api.cloudflare.com/client/v4/zones/$ZONE/dns_records" "$auth" "Content-Type: application/json" >/dev/null || fail "Cloudflare did not accept the new record"
        fi
        ;;
      url)
        BODY="" call GET "${URL//\{ip\}/$ip}" >/dev/null || fail "the provider did not accept the update"
        ;;
      *) fail "the settings file does not say which provider" ;;
    esac
    mkdir -p "$(dirname "$STATE_FILE")"; printf '%s\n' "$ip" >"$STATE_FILE"
    say "the name now points at $ip"
    ;;

  status)
    [[ -f "$ENV_FILE" ]] || { say "not set up"; exit 0; }
    # shellcheck disable=SC1090
    . "$ENV_FILE"
    say "provider: $PROVIDER; last address told: $( [[ -f "$STATE_FILE" ]] && cat "$STATE_FILE" || echo none )"
    ;;

  remove)
    [[ "$(id -u)" -eq 0 || -n "${ARMOR_DDNS_ENV:-}" ]] || fail "remove needs root (sudo)"
    if [[ "${ARMOR_DDNS_NOSYSTEMD:-0}" != 1 ]]; then systemctl disable --now armor-ddns.timer 2>/dev/null || true; rm -f /etc/systemd/system/armor-ddns.service /etc/systemd/system/armor-ddns.timer; systemctl daemon-reload || true; fi
    # the token is not kept: the file is put aside for the owner to delete
    [[ ! -f "$ENV_FILE" ]] || mv "$ENV_FILE" "$ENV_FILE.removed.$(date +%s)"
    say "the updates stopped"
    ;;

  *) fail "unknown command: $COMMAND" ;;
esac
