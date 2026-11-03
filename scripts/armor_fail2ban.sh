#!/usr/bin/env bash
# ARMOR-DEVOPS - bans, with fail2ban, the addresses that keep failing to sign in to Studio (wrong password or wrong second-factor code). The server writes every refused sign-in to
# its audit log (data directory, audit.log) with the address it came from; the filter below reads only those lines.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
#
#   armor_fail2ban.sh plan   [--data-dir DIR] [options]     # prints the filter and the jail that would be written; changes nothing
#   sudo armor_fail2ban.sh setup [--data-dir DIR] [options] # writes them, checks them with fail2ban-regex and reloads fail2ban
#   armor_fail2ban.sh status                                # whether the files are in place and who is banned
#   sudo armor_fail2ban.sh remove                           # deletes the two files and reloads fail2ban
#
# Options: --maxretry N (5)   --findtime SECONDS (600)   --bantime SECONDS (3600)   --ports LIST (18080,18081)   --ignoreip "ADDR ..." (the house network is never banned: give it here)
# The settings live in the jail file it writes (jail.d/armor-studio.local); edit that file, not this script, to tune them afterwards.
# The address in the audit log is the one the server sees: behind a reverse proxy it is the client's only when the server is told to trust that proxy (ARMOR_TRUST_PROXY).
# Settings from the environment (for tests and unusual installs): ARMOR_F2B_ETC (/etc/fail2ban), ARMOR_F2B_NOSYSTEMD=1 (do not call fail2ban-client).
# Nothing here has been run on the CM5.
set -euo pipefail

PREFIX="${ARMOR_PREFIX:-/opt/armor}"
DATA_DIR="$PREFIX/data"
ETC="${ARMOR_F2B_ETC:-/etc/fail2ban}"
MAXRETRY=5; FINDTIME=600; BANTIME=3600; PORTS="18080,18081"; IGNOREIP="127.0.0.1/8 ::1"
FILTER_NAME="armor-studio"

fail() { echo "armor_fail2ban: $*" >&2; exit 2; }
say() { echo "[armor-fail2ban] $*"; }
whole() { [[ "$2" =~ ^[0-9]{1,7}$ ]] && (( 10#$2 >= 1 )) || fail "$1 wants a whole number of at least 1"; }

COMMAND="${1:-}"
[[ -n "$COMMAND" ]] || fail "usage: armor_fail2ban.sh plan|setup|status|remove [options]  (see the header of the script)"
shift
while [[ $# -gt 0 ]]; do
  case "$1" in
    --data-dir) DATA_DIR="${2:-}"; [[ -n "$DATA_DIR" ]] || fail "--data-dir wants a folder"; shift 2 ;;
    --maxretry) whole --maxretry "${2:-}"; MAXRETRY="$((10#$2))"; shift 2 ;;
    --findtime) whole --findtime "${2:-}"; FINDTIME="$((10#$2))"; shift 2 ;;
    --bantime) whole --bantime "${2:-}"; BANTIME="$((10#$2))"; shift 2 ;;
    --ports) [[ "${2:-}" =~ ^[0-9]{1,5}(,[0-9]{1,5})*$ ]] || fail "--ports wants a list such as 18080,18081"; PORTS="$2"; shift 2 ;;
    --ignoreip) [[ "${2:-}" =~ ^[0-9a-fA-F:./\ ]+$ ]] || fail "--ignoreip wants addresses or networks separated by spaces"; IGNOREIP="127.0.0.1/8 ::1 $2"; shift 2 ;;
    *) fail "unknown option: $1" ;;
  esac
done

FILTER_FILE="$ETC/filter.d/$FILTER_NAME.conf"
JAIL_FILE="$ETC/jail.d/$FILTER_NAME.local"

# One audit line looks like {"at":"...Z","action":"studio.login","outcome":"denied","actor":"name","detail":"remote 203.0.113.9"}. The actor is JSON text, so a quote inside it is
# escaped: a name made to look like a second "detail" cannot get another address banned. A refusal for a missing second factor ends its detail with a sentence, so it does not match.
filter_text() {
  cat <<'EOF'
# Written by armor_fail2ban.sh. Reads the audit log of the A.R.M.O.R. server: refused Studio sign-ins and refused second-factor codes.
[Definition]
failregex = ^\{"at":"[^"]+","action":"studio\.(?:login|totp)","outcome":"denied",(?:"actor":"(?:[^"\\]|\\.)*",)?"detail":"[A-Za-z]+ <HOST>"\}\s*$
ignoreregex =
datepattern = ^\{"at":"%%Y-%%m-%%dT%%H:%%M:%%S
EOF
}
jail_text() {
  cat <<EOF
# Written by armor_fail2ban.sh. Edit the numbers here to tune it.
[$FILTER_NAME]
enabled  = true
filter   = $FILTER_NAME
logpath  = $DATA_DIR/audit.log
backend  = auto
port     = $PORTS
maxretry = $MAXRETRY
findtime = $FINDTIME
bantime  = $BANTIME
ignoreip = $IGNOREIP
EOF
}

case "$COMMAND" in
  plan)
    say "filter -> $FILTER_FILE"; filter_text; echo
    say "jail -> $JAIL_FILE"; jail_text ;;
  setup)
    command -v fail2ban-client >/dev/null 2>&1 || [[ "${ARMOR_F2B_NOSYSTEMD:-}" == 1 ]] || fail "fail2ban is not installed (sudo apt install fail2ban), then run this again"
    mkdir -p "$ETC/filter.d" "$ETC/jail.d"
    filter_text >"$FILTER_FILE"; jail_text >"$JAIL_FILE"
    say "wrote $FILTER_FILE and $JAIL_FILE"
    if [[ "${ARMOR_F2B_NOSYSTEMD:-}" != 1 ]]; then
      if [[ -s "$DATA_DIR/audit.log" ]]; then fail2ban-regex "$DATA_DIR/audit.log" "$FILTER_FILE" || say "WARNING: fail2ban-regex reported a problem; read its output above"; fi
      fail2ban-client reload && say "fail2ban reloaded" || say "WARNING: fail2ban could not reload; check: fail2ban-client -t"
    fi ;;
  status)
    [[ -f "$FILTER_FILE" && -f "$JAIL_FILE" ]] && say "installed ($JAIL_FILE)" || { say "not installed"; exit 1; }
    if [[ "${ARMOR_F2B_NOSYSTEMD:-}" != 1 ]] && command -v fail2ban-client >/dev/null 2>&1; then fail2ban-client status "$FILTER_NAME" || true; fi ;;
  remove)
    rm -f -- "$FILTER_FILE" "$JAIL_FILE"
    say "removed the filter and the jail"
    if [[ "${ARMOR_F2B_NOSYSTEMD:-}" != 1 ]] && command -v fail2ban-client >/dev/null 2>&1; then fail2ban-client reload >/dev/null || true; fi ;;
  *) fail "unknown command: $COMMAND (plan, setup, status or remove)" ;;
esac
