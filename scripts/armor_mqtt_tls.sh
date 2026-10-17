#!/usr/bin/env bash
# ARMOR-DEVOPS - an OPTIONAL encrypted door (MQTT over TLS, port 8883) into the broker, with a certificate from this installation's OWN certificate authority.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
#
# Off unless you run `setup`: the plain listener (18883) is never touched, so the nodes that talk plain MQTT keep working. With `setup` the broker also listens on 8883 with TLS; a node
# (or the server) that is told to use mqtts:// and the certificate of the authority checks that the broker is the one of this installation. No Internet authority is involved.
#
#   armor_mqtt_tls.sh plan   [--name HOST]... [--ip ADDRESS]... [--no-detect] [--port 8883]   # what would be made; changes nothing
#   sudo armor_mqtt_tls.sh setup [same options] [--force]                                      # the authority (once), the certificate of the broker, the 8883 listener, and the broker restarted
#   sudo armor_mqtt_tls.sh status                                                              # the authority, the certificate, the listener and whether the server uses it
#   sudo armor_mqtt_tls.sh export-ca [--out FILE]                                              # the certificate of the authority (PEM, public) to paste into the nodes
#   sudo armor_mqtt_tls.sh server-tls on|off                                                   # the server of this machine talks to the broker over TLS (on) or over the plain port (off)
#   sudo armor_mqtt_tls.sh remove [--forget-ca]                                                # the 8883 listener is gone; the keys are put aside, never deleted
#
# The names and addresses the certificate vouches for are the ones of this machine (its host name, host name.local, localhost, 127.0.0.1 and its IPv4 addresses) plus every --name
# and --ip. A node reaches the broker by one of them (mqtts://192.168.0.180:8883): when the address of the machine changes, run `setup` again (it makes a new broker certificate with
# the same authority, so the nodes do not have to be touched).
#
# The private key of the authority stays in $PREFIX/etc/mqtt-ca (0700, the key 0600, root only), never in a repository and never next to the broker; the broker only gets its own key.
# The certificate of the broker lasts two years and is renewed by running `setup` again (it does so by itself when less than 30 days are left); the authority lasts ten years: its
# certificate is the one pasted into the nodes, so it is not changed without a reason.
# Settings from the environment (for tests and unusual installs): ARMOR_PREFIX (/opt/armor), ARMOR_MQTT_DIR (PREFIX/etc/mosquitto), ARMOR_MQTT_CA_DIR (PREFIX/etc/mqtt-ca),
# ARMOR_MQTT_ENV_FILE (PREFIX/etc/armor.mqtt.env), ARMOR_SERVICE_USER (the owner of mosquitto.conf), ARMOR_MQTT_TLS_NOSYSTEMD=1 (do not touch systemd).
# Nothing here has been run on the CM5.
set -euo pipefail

PREFIX="${ARMOR_PREFIX:-/opt/armor}"
MQ="${ARMOR_MQTT_DIR:-$PREFIX/etc/mosquitto}"
CA_DIR="${ARMOR_MQTT_CA_DIR:-$PREFIX/etc/mqtt-ca}"
ENV_FILE="${ARMOR_MQTT_ENV_FILE:-$PREFIX/etc/armor.mqtt.env}"
NOSYSTEMD="${ARMOR_MQTT_TLS_NOSYSTEMD:-0}"
PORT="8883"; NAMES=(); IPS=(); DETECT=1; FORCE=0; FORGET_CA=0; OUT=""
CA_DAYS=3650; CERT_DAYS=730; RENEW_DAYS=30

fail() { echo "armor_mqtt_tls: $*" >&2; exit 2; }
say() { echo "[armor-mqtt-tls] $*"; }

valid_port() { [[ "$1" =~ ^[0-9]{1,5}$ ]] && (( 10#$1 >= 1 && 10#$1 <= 65535 )); }
valid_name() { [[ "$1" =~ ^[A-Za-z0-9]([A-Za-z0-9.-]{0,251}[A-Za-z0-9])?$ ]]; }
valid_ipv4() {
  local octet
  [[ "$1" =~ ^([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})$ ]] || return 1
  for octet in "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}" "${BASH_REMATCH[3]}" "${BASH_REMATCH[4]}"; do (( 10#$octet <= 255 )) || return 1; done
}
valid_ipv6() { [[ "$1" =~ ^[0-9A-Fa-f:]{2,39}$ && "$1" == *:* ]]; }

COMMAND="${1:-}"
[[ -n "$COMMAND" ]] || fail "usage: armor_mqtt_tls.sh plan|setup|status|export-ca|server-tls|remove [options]  (see the header of the script)"
shift
SERVER_TLS=""
if [[ "$COMMAND" == server-tls ]]; then
  SERVER_TLS="${1:-}"; [[ "$SERVER_TLS" == on || "$SERVER_TLS" == off ]] || fail "server-tls wants on or off"; shift
fi
while [[ $# -gt 0 ]]; do
  case "$1" in
    --name) valid_name "${2:-}" || fail "--name wants a host name"; NAMES+=("$2"); shift 2 ;;
    --ip) { valid_ipv4 "${2:-}" || valid_ipv6 "${2:-}"; } || fail "--ip wants an IP address"; IPS+=("$2"); shift 2 ;;
    --no-detect) DETECT=0; shift ;;
    --port) valid_port "${2:-}" || fail "--port wants a TCP port number"; PORT="$((10#$2))"; shift 2 ;;
    --force) FORCE=1; shift ;;
    --forget-ca) FORGET_CA=1; shift ;;
    --out) OUT="${2:-}"; [[ -n "$OUT" ]] || fail "--out wants a file name"; shift 2 ;;
    --prefix) PREFIX="${2:-}"; MQ="${ARMOR_MQTT_DIR:-$PREFIX/etc/mosquitto}"; CA_DIR="${ARMOR_MQTT_CA_DIR:-$PREFIX/etc/mqtt-ca}"; ENV_FILE="${ARMOR_MQTT_ENV_FILE:-$PREFIX/etc/armor.mqtt.env}"; shift 2 ;;
    -h|--help) sed -n '2,26p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) fail "unknown option: $1" ;;
  esac
done

TLS_DIR="$MQ/tls"; CONF_D="$MQ/conf.d"; CONF_FILE="$CONF_D/armor-tls.conf"; MAIN_CONF="$MQ/mosquitto.conf"
WORK=""
cleanup() { [[ -z "$WORK" ]] || rm -rf "$WORK"; }
trap cleanup EXIT

need_openssl() { command -v openssl >/dev/null || fail "OpenSSL is not installed: sudo apt install openssl"; }
need_root() { [[ "$(id -u)" -eq 0 || -n "${ARMOR_MQTT_DIR:-}" ]] || fail "$COMMAND needs root (sudo)"; }

# ---- the names and addresses the certificate of the broker vouches for ----------------------------------------------------------------

# One "DNS:name" or "IP:address" per line, without repeats.
wanted_names() {
  local item host
  {
    echo "DNS:localhost"; echo "IP:127.0.0.1"
    if [[ "$DETECT" -eq 1 ]]; then
      host="$(hostname 2>/dev/null || true)"
      if [[ -n "$host" ]] && valid_name "$host"; then echo "DNS:$host"; [[ "$host" == *.* ]] || echo "DNS:$host.local"; fi
      for item in $(hostname -I 2>/dev/null || true); do
        if valid_ipv4 "$item" && [[ "$item" != 127.* && "$item" != 169.254.* ]]; then echo "IP:$item"; fi
      done
    fi
    for item in "${NAMES[@]}"; do echo "DNS:$item"; done
    for item in "${IPS[@]}"; do echo "IP:$item"; done
  } | awk '!seen[$0]++'
}

# The same, from a certificate: the lines `openssl x509 -ext subjectAltName` prints, in the same form and sorted.
cert_names() { openssl x509 -in "$1" -noout -ext subjectAltName 2>/dev/null | sed -n '2,$p' | tr ',' '\n' | sed 's/^ *//; s/ *$//; s/^IP Address:/IP:/' | sed '/^$/d' | LC_ALL=C sort; }

# ---- the broker's configuration ---------------------------------------------------------------------------------------------------------

# The address the plain listener is bound to ("listener 18883 127.0.0.1" -> 127.0.0.1); the TLS listener uses the same one.
bind_address() { [[ -f "$MAIN_CONF" ]] && sed -n 's/^listener[[:space:]]\+[0-9]\+[[:space:]]\+\([^[:space:]#]\+\).*/\1/p' "$MAIN_CONF" | head -n1 || true; }
plain_port() { [[ -f "$MAIN_CONF" ]] && sed -n 's/^listener[[:space:]]\+\([0-9]\+\).*/\1/p' "$MAIN_CONF" | head -n1 || true; }
service_user() {
  if [[ -n "${ARMOR_SERVICE_USER:-}" ]]; then echo "$ARMOR_SERVICE_USER"; elif [[ -f "$MAIN_CONF" ]]; then stat -c %U "$MAIN_CONF"; else id -un; fi
}
restart_broker() {
  if [[ "$NOSYSTEMD" == 1 ]]; then say "systemd is not used here: restart the broker yourself"; return 0; fi
  if systemctl cat armor-mosquitto >/dev/null 2>&1; then systemctl restart armor-mosquitto && say "the broker was restarted (the nodes reconnect in a few seconds)"; else say "armor-mosquitto is not a service of this machine: restart your broker yourself"; fi
}

# Dates in the form `openssl ca` wants (one day back, so that a node whose clock is a little behind still accepts the certificate).
date_from() { date -u -d "$1" +%Y%m%d%H%M%SZ; }

openssl_files() {   # the configuration of a throw-away certificate authority in $WORK
  WORK="$(mktemp -d)"
  : >"$WORK/index.txt"
  openssl rand -hex 16 | tr 'a-f' 'A-F' >"$WORK/serial"
  local sans="$1" n=0 i=0 line
  {
    echo "[ca]"; echo "default_ca = CA_default"
    echo "[CA_default]"; echo "dir = $WORK"; echo "database = $WORK/index.txt"; echo "new_certs_dir = $WORK"; echo "serial = $WORK/serial"
    echo "default_md = sha256"; echo "policy = policy_any"; echo "unique_subject = no"; echo "copy_extensions = none"
    echo "[policy_any]"; echo "commonName = supplied"; echo "organizationName = optional"
    echo "[req]"; echo "distinguished_name = dn"; echo "[dn]"
    echo "[v3_ca]"; echo "basicConstraints = critical,CA:TRUE,pathlen:0"; echo "keyUsage = critical,keyCertSign,cRLSign"; echo "subjectKeyIdentifier = hash"
    echo "[v3_server]"; echo "basicConstraints = critical,CA:FALSE"; echo "keyUsage = critical,digitalSignature"; echo "extendedKeyUsage = serverAuth"
    echo "subjectKeyIdentifier = hash"; echo "authorityKeyIdentifier = keyid"; echo "subjectAltName = @alt"
    echo "[alt]"
    while IFS= read -r line; do
      case "$line" in DNS:*) n=$((n + 1)); echo "DNS.$n = ${line#DNS:}" ;; IP:*) i=$((i + 1)); echo "IP.$i = ${line#IP:}" ;; esac
    done <<<"$sans"
  } >"$WORK/openssl.cnf"
}

make_ca() {
  local host
  host="$(hostname 2>/dev/null || echo installation)"
  ( umask 077; mkdir -p "$CA_DIR" )
  chmod 0700 "$CA_DIR"
  ( umask 077; openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out "$CA_DIR/ca.key" )
  chmod 0600 "$CA_DIR/ca.key"
  openssl req -new -key "$CA_DIR/ca.key" -out "$WORK/ca.csr" -subj "/O=A.R.M.O.R. installation/CN=A.R.M.O.R. MQTT authority ($host)" -config "$WORK/openssl.cnf"
  openssl ca -batch -notext -selfsign -config "$WORK/openssl.cnf" -in "$WORK/ca.csr" -keyfile "$CA_DIR/ca.key" -out "$CA_DIR/ca.pem" -extensions v3_ca \
    -startdate "$(date_from '1 day ago')" -enddate "$(date_from "+$CA_DAYS days")" >/dev/null 2>&1
  chmod 0644 "$CA_DIR/ca.pem"
}

# The certificate of the broker is renewed when it is missing, was not signed by the current authority, vouches for other names than the wanted ones, or ends soon.
broker_cert_ok() {
  [[ -f "$TLS_DIR/server.pem" && -f "$TLS_DIR/server.key" ]] || return 1
  openssl verify -CAfile "$CA_DIR/ca.pem" "$TLS_DIR/server.pem" >/dev/null 2>&1 || return 1
  openssl x509 -in "$TLS_DIR/server.pem" -noout -checkend $((RENEW_DAYS * 86400)) >/dev/null 2>&1 || return 1
  [[ "$(cert_names "$TLS_DIR/server.pem")" == "$(wanted_names | LC_ALL=C sort)" ]] || return 1
}

make_broker_cert() {
  local user="$1"
  ( umask 027; mkdir -p "$TLS_DIR" )
  openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out "$WORK/server.key"
  openssl req -new -key "$WORK/server.key" -out "$WORK/server.csr" -subj "/O=A.R.M.O.R. installation/CN=armor-mqtt-broker" -config "$WORK/openssl.cnf"
  openssl ca -batch -notext -config "$WORK/openssl.cnf" -in "$WORK/server.csr" -keyfile "$CA_DIR/ca.key" -cert "$CA_DIR/ca.pem" -out "$WORK/server.pem" -extensions v3_server \
    -startdate "$(date_from '1 day ago')" -enddate "$(date_from "+$CERT_DAYS days")" >/dev/null 2>&1
  ( umask 027
    cat "$WORK/server.key" >"$TLS_DIR/server.key.new"; cat "$WORK/server.pem" >"$TLS_DIR/server.pem.new"; cat "$CA_DIR/ca.pem" >"$TLS_DIR/ca.pem.new"
    mv -f "$TLS_DIR/server.key.new" "$TLS_DIR/server.key"; mv -f "$TLS_DIR/server.pem.new" "$TLS_DIR/server.pem"; mv -f "$TLS_DIR/ca.pem.new" "$TLS_DIR/ca.pem" )
  chmod 0750 "$TLS_DIR"; chmod 0640 "$TLS_DIR/server.key" "$TLS_DIR/server.pem" "$TLS_DIR/ca.pem"
  if [[ "$(id -u)" -eq 0 ]]; then chown "root:$user" "$TLS_DIR" "$TLS_DIR/server.key" "$TLS_DIR/server.pem" "$TLS_DIR/ca.pem"; fi
}

write_listener() {
  local user="$1" bind
  bind="$(bind_address)"
  ( umask 027; mkdir -p "$CONF_D" )
  {
    echo "# Written by armor_mqtt_tls.sh: the encrypted door of the broker. The plain listener is in mosquitto.conf and is not touched by it."
    echo "listener $PORT${bind:+ $bind}"
    echo "certfile $TLS_DIR/server.pem"
    echo "keyfile $TLS_DIR/server.key"
    echo "tls_version tlsv1.2"
  } >"$CONF_FILE.new"
  chmod 0640 "$CONF_FILE.new"
  [[ "$(id -u)" -ne 0 ]] || chown "root:$user" "$CONF_FILE.new" "$CONF_D"
  chmod 0750 "$CONF_D"
  mv -f "$CONF_FILE.new" "$CONF_FILE"
  # the main file reads the folder (once; install_cm5.sh writes the line too)
  if [[ -f "$MAIN_CONF" ]]; then
    grep -qxF "include_dir $CONF_D" "$MAIN_CONF" || printf '\n# More listeners (armor_mqtt_tls.sh)\ninclude_dir %s\n' "$CONF_D" >>"$MAIN_CONF"
  else
    say "$MAIN_CONF does not exist: add the line  include_dir $CONF_D  to the configuration of your broker"
  fi
}

# ---- the server of this machine -----------------------------------------------------------------------------------------------------------

server_url() { sed -n 's/^ARMOR_MQTT_URL=//p' "$ENV_FILE" 2>/dev/null | head -n1 || true; }
set_env() {   # set_env NAME VALUE (replaces the line or adds it)
  if grep -q "^$1=" "$ENV_FILE"; then sed -i "s#^$1=.*#$1=$2#" "$ENV_FILE"; else printf '%s=%s\n' "$1" "$2" >>"$ENV_FILE"; fi
}
drop_env() { sed -i "/^$1=/d" "$ENV_FILE"; }

case "$COMMAND" in
  plan)
    need_openssl
    say "the broker would also listen on port $PORT with TLS (the plain port $(plain_port) stays as it is)"
    say "its certificate would vouch for:"; wanted_names | sed 's/^/  /'
    say "authority: $CA_DIR (the key stays there, root only); broker files: $TLS_DIR; configuration: $CONF_FILE"
    if [[ -f "$CA_DIR/ca.pem" ]]; then say "the authority already exists and would be kept"; else say "a new authority (EC P-256, $CA_DAYS days) would be made"; fi
    ;;

  setup)
    need_root; need_openssl
    [[ "$(date +%Y)" -ge 2024 ]] || fail "the clock of this machine is not set: a certificate made now would have the wrong dates"
    [[ -d "$MQ" ]] || fail "$MQ does not exist: the A.R.M.O.R. broker is not installed here (install_cm5.sh --with-mqtt)"
    sans="$(wanted_names)"
    user="$(service_user)"
    openssl_files "$sans"
    if [[ ! -f "$CA_DIR/ca.key" || ! -f "$CA_DIR/ca.pem" ]]; then make_ca; say "made the authority of this installation ($CA_DIR; its key never leaves this machine)"; else say "the authority already exists: kept"; fi
    if [[ "$FORCE" -eq 0 ]] && broker_cert_ok; then say "the certificate of the broker is still good: kept"; else make_broker_cert "$user"; say "made the certificate of the broker"; fi
    write_listener "$user"
    restart_broker
    say "port $PORT is open for TLS; the plain port was not touched"
    say "the certificate vouches for:"; wanted_names | sed 's/^/  /'
    say "next: sudo $0 export-ca    (paste it in the panel of each node, Broker page, with mqtts://ADDRESS:$PORT)"
    say "if the host firewall is used (firewall_core.sh), it only knows the plain port: allow $PORT/tcp from the field network yourself"
    ;;

  status)
    need_openssl
    [[ -d "$CA_DIR" && ! -r "$CA_DIR" ]] && fail "the folder of the authority ($CA_DIR) is private: run  sudo $0 status"
    if [[ -f "$CA_DIR/ca.pem" ]]; then
      say "authority: $(openssl x509 -in "$CA_DIR/ca.pem" -noout -subject | sed 's/^subject= *//')"
      say "  sha256 fingerprint: $(openssl x509 -in "$CA_DIR/ca.pem" -noout -fingerprint -sha256 | sed 's/^.*=//')"
      say "  valid until: $(openssl x509 -in "$CA_DIR/ca.pem" -noout -enddate | sed 's/^notAfter=//')"
      [[ -f "$CA_DIR/ca.key" ]] && say "  its key is on this machine ($CA_DIR/ca.key)" || say "  its key is NOT on this machine"
    else
      say "no authority yet: the encrypted door is off"
    fi
    if [[ -f "$TLS_DIR/server.pem" ]]; then
      say "broker certificate valid until: $(openssl x509 -in "$TLS_DIR/server.pem" -noout -enddate | sed 's/^notAfter=//')"
      say "  vouches for: $(cert_names "$TLS_DIR/server.pem" | tr '\n' ' ')"
      openssl x509 -in "$TLS_DIR/server.pem" -noout -checkend $((RENEW_DAYS * 86400)) >/dev/null 2>&1 || say "  it ends within $RENEW_DAYS days: run setup again"
    fi
    if [[ -f "$CONF_FILE" ]]; then say "listener: $(sed -n 's/^listener[[:space:]]\+//p' "$CONF_FILE" | head -n1) (TLS), written in $CONF_FILE"; else say "listener: none (the broker listens on its plain port only)"; fi
    [[ -f "$MAIN_CONF" ]] && { grep -qxF "include_dir $CONF_D" "$MAIN_CONF" && say "mosquitto.conf reads $CONF_D" || say "mosquitto.conf does not read $CONF_D yet"; }
    if [[ -f "$ENV_FILE" ]]; then
      case "$(server_url)" in
        mqtts://*) say "the server of this machine uses TLS ($(server_url))" ;;
        mqtt://*) say "the server of this machine uses the plain port ($(server_url))" ;;
        *) say "the server of this machine has no broker address in $ENV_FILE" ;;
      esac
    fi
    ;;

  export-ca)
    [[ -d "$CA_DIR" && ! -r "$CA_DIR" ]] && fail "the folder of the authority ($CA_DIR) is private: run  sudo $0 export-ca"
    [[ -f "$CA_DIR/ca.pem" ]] || fail "there is no authority yet: run  sudo $0 setup"
    if [[ -n "$OUT" ]]; then cat "$CA_DIR/ca.pem" >"$OUT"; say "the certificate of the authority (public) was written to $OUT"; else cat "$CA_DIR/ca.pem"; fi
    ;;

  server-tls)
    need_root; need_openssl
    [[ -f "$ENV_FILE" ]] || fail "$ENV_FILE does not exist: the server of this machine does not use the A.R.M.O.R. broker (install_cm5.sh --with-mqtt)"
    if [[ "$SERVER_TLS" == on ]]; then
      [[ -f "$TLS_DIR/ca.pem" && -f "$CONF_FILE" ]] || fail "the encrypted door is not set up: run  sudo $0 setup  first"
      set_env ARMOR_MQTT_URL "mqtts://localhost:$(sed -n 's/^listener[[:space:]]\+\([0-9]\+\).*/\1/p' "$CONF_FILE" | head -n1)"
      set_env ARMOR_MQTT_CA_FILE "$TLS_DIR/ca.pem"
      say "the server will use TLS: restart it (sudo systemctl restart armor-server)"
    else
      plain="$(plain_port)"; [[ -n "$plain" ]] || plain=18883
      bind="$(bind_address)"; [[ -n "$bind" && "$bind" != 0.0.0.0 ]] || bind=127.0.0.1
      set_env ARMOR_MQTT_URL "mqtt://$bind:$plain"
      drop_env ARMOR_MQTT_CA_FILE
      say "the server will use the plain port again: restart it (sudo systemctl restart armor-server)"
    fi
    ;;

  remove)
    need_root
    if [[ -f "$ENV_FILE" ]] && grep -q '^ARMOR_MQTT_CA_FILE=' "$ENV_FILE"; then bash "$0" server-tls off --prefix "$PREFIX"; fi
    stamp="$(date +%s)"
    [[ ! -f "$CONF_FILE" ]] || mv "$CONF_FILE" "$CONF_FILE.removed.$stamp"
    [[ ! -d "$TLS_DIR" ]] || mv "$TLS_DIR" "$TLS_DIR.removed.$stamp"
    [[ "$FORGET_CA" -eq 0 || ! -d "$CA_DIR" ]] || mv "$CA_DIR" "$CA_DIR.removed.$stamp"
    restart_broker
    say "the encrypted door is closed; its files were put aside next to the old ones (nothing was deleted)"
    [[ "$FORGET_CA" -eq 1 ]] || say "the authority was kept: a later setup makes a new broker certificate with it and the nodes that trust it keep working"
    ;;

  *) fail "unknown command: $COMMAND" ;;
esac
