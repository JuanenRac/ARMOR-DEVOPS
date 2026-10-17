#!/usr/bin/env bash
# ARMOR-DEVOPS - tests of scripts/armor_wireguard.sh: what it writes, what it refuses, and that a removed peer is gone. A stand-in for `wg` makes the keys, so it needs
# no root, no WireGuard and no network, and changes nothing outside a temporary folder.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WG="$HERE/armor_wireguard.sh"
PASSED=0; FAILED=0
ok() { PASSED=$((PASSED + 1)); }
bad() { FAILED=$((FAILED + 1)); echo "FAIL: $*"; }
expect_in()  { grep -qF -- "$2" <<<"$1" && ok || bad "expected: $2"; }
expect_out() { grep -qF -- "$2" <<<"$1" && bad "did not expect: $2" || ok; }
refused() { local out; out="$("$WG" "$@" 2>&1)"; local code=$?; [[ $code -eq 2 ]] && ok || bad "should have been refused (code $code): $*  -> $out"; }

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/bin" "$TMP/etc" "$TMP/state"
# a stand-in for wg: genkey/genpsk give numbered keys, pubkey turns a private key into a public one
cat >"$TMP/bin/wg" <<'EOF'
#!/usr/bin/env bash
case "$1" in
  genkey) echo "PRIV$(( ++N ))$RANDOM$RANDOM$RANDOM" ;;
  genpsk) echo "PSK$RANDOM$RANDOM$RANDOM" ;;
  pubkey) read -r key; echo "PUB-$(printf %s "$key" | md5sum | cut -c1-16)" ;;
esac
EOF
chmod +x "$TMP/bin/wg"
export PATH="$TMP/bin:$PATH" ARMOR_WG_ETC="$TMP/etc" ARMOR_WG_STATE="$TMP/state" ARMOR_WG_ENV_FILE="$TMP/armor.env" ARMOR_WG_NOSYSTEMD=1
echo "ARMOR_STUDIO_USERNAME=admin" >"$TMP/armor.env"

# the plan writes nothing
PLAN="$("$WG" plan --endpoint casa.example.org)"
expect_in "$PLAN" "10.66.0.0/24"
expect_in "$PLAN" "forward UDP 51820"
expect_in "$PLAN" "Address = 10.66.0.1/24"
[[ ! -e "$TMP/etc/armor-wg0.conf" ]] && ok || bad "plan must not write anything"

# what it refuses
refused plan
refused plan --endpoint "bad host"
refused plan --endpoint casa.example.org:99999
refused plan --endpoint casa.example.org --subnet 10.66.0.0/33
refused plan --endpoint casa.example.org --port 0
refused plan --endpoint casa.example.org --route-lan "eth0; reboot"
refused add-peer
refused add-peer "bad name" --endpoint x
refused frobnicate
refused add-peer phone-juan                       # before setup

# setup
OUT="$("$WG" setup --endpoint casa.example.org:51999 --lan 192.168.1.0/24 2>&1)"
expect_in "$OUT" "restart the server"
CONF="$(cat "$TMP/etc/armor-wg0.conf")"
expect_in "$CONF" "ListenPort = 51820"
expect_in "$CONF" "PrivateKey = PRIV"
grep -q '^ARMOR_VPN_NETWORKS=10.66.0.0/24$' "$TMP/armor.env" && ok || bad "the VPN network must be told to the server"
if [[ "$(uname -s)" == Linux ]]; then [[ "$(stat -c %a "$TMP/etc/armor-wg0.conf")" == "600" ]] && ok || bad "the server configuration must be private"; fi
"$WG" setup --endpoint casa.example.org:51999 --lan 192.168.1.0/24 >/dev/null 2>&1
[[ "$(grep -c '^ARMOR_VPN_NETWORKS=' "$TMP/armor.env")" == "1" ]] && ok || bad "setup twice must not repeat the line"

# peers
ADD="$("$WG" add-peer phone-juan 2>&1)"
expect_in "$ADD" "Address = 10.66.0.2/32"
expect_in "$ADD" "Endpoint = casa.example.org:51999"
expect_in "$ADD" "AllowedIPs = 10.66.0.0/24, 192.168.1.0/24"
expect_in "$ADD" "PersistentKeepalive = 25"
expect_in "$ADD" "PresharedKey = PSK"
SECOND="$("$WG" add-peer laptop 2>&1)"
expect_in "$SECOND" "Address = 10.66.0.3/32"
FULL="$("$WG" add-peer tablet --full-tunnel 2>&1)"
expect_in "$FULL" "AllowedIPs = 0.0.0.0/0"
refused add-peer phone-juan
LIST="$("$WG" list)"
expect_in "$LIST" "phone-juan  10.66.0.2"
expect_in "$LIST" "laptop  10.66.0.3"
grep -c '^\[Peer\]' "$TMP/etc/armor-wg0.conf" | grep -qx 3 && ok || bad "three peers expected in the server file"
SHOWN="$("$WG" show phone-juan 2>&1)"
expect_in "$SHOWN" "PrivateKey = PRIV"
# the private key of a peer is never in the server file, and the server's is never in a peer's
expect_out "$(cat "$TMP/etc/armor-wg0.conf")" "$(grep -m1 PrivateKey <<<"$SHOWN" | sed 's/PrivateKey = //')"

# removing a peer removes it from the server file and frees nothing else
"$WG" remove-peer laptop >/dev/null 2>&1
expect_out "$(cat "$TMP/etc/armor-wg0.conf")" "# peer: laptop"
expect_in  "$(cat "$TMP/etc/armor-wg0.conf")" "# peer: phone-juan"
refused show laptop
# the address of the removed peer is reused by the next one
expect_in "$("$WG" add-peer watch 2>&1)" "Address = 10.66.0.3/32"

# routing to the nodes of the house is optional and only written when asked
"$WG" setup --endpoint casa.example.org --route-lan eth0 >/dev/null 2>&1
expect_in "$(cat "$TMP/etc/armor-wg0.conf")" "masquerade"
expect_in "$(cat "$TMP/etc/armor-wg0.conf")" "# peer: phone-juan"

echo "armor_wireguard tests: $PASSED passed, $FAILED failed"
[[ "$FAILED" -eq 0 ]]
