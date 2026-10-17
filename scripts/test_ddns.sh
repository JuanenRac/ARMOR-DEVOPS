#!/usr/bin/env bash
# ARMOR-DEVOPS - tests of scripts/armor_ddns.sh with a stand-in for curl: nothing leaves the machine and nothing outside a temporary folder is changed.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DDNS="$HERE/armor_ddns.sh"
PASSED=0; FAILED=0
ok() { PASSED=$((PASSED + 1)); }
bad() { FAILED=$((FAILED + 1)); echo "FAIL: $*"; }
expect_in()  { grep -qF -- "$2" <<<"$1" && ok || bad "expected: $2"; }
expect_out() { grep -qF -- "$2" <<<"$1" && bad "did not expect: $2" || ok; }
refused() { local out; out="$("$DDNS" "$@" 2>&1)"; local code=$?; [[ $code -eq 2 ]] && ok || bad "should have been refused (code $code): $*  -> $out"; }

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
# a stand-in for curl: the address service answers $FAKE_IP; a call with -K - writes what it was asked (from the standard input) and the arguments to the log
cat >"$TMP/curl" <<'EOF'
#!/usr/bin/env bash
if [[ "$*" == *"-K -"* ]]; then
  { echo "ARGS: $*"; cat; echo "----"; } >>"$FAKE_LOG"
  case "$(tail -n 40 "$FAKE_LOG")" in
    *duckdns*) echo "${FAKE_DUCK:-OK}" ;;
    *dns_records?type*) echo '{"result":[{"id":"0123456789abcdef0123456789abcdef"}]}' ;;
    *) echo '{"success":true}' ;;
  esac
  exit 0
fi
echo "$FAKE_IP"
EOF
chmod +x "$TMP/curl"
export ARMOR_DDNS_CURL="$TMP/curl" ARMOR_DDNS_ENV="$TMP/etc/armor.ddns.env" ARMOR_DDNS_STATE="$TMP/data/ddns.last" ARMOR_DDNS_NOSYSTEMD=1 FAKE_LOG="$TMP/log"

# what it refuses
refused
refused frobnicate
refused setup
refused setup --provider nope
refused setup --provider duckdns --domain "bad name" --token abcdefgh1234
refused setup --provider duckdns --domain casa
refused setup --provider cloudflare --zone nothex --record-name casa.example.org --token abcdefgh1234
refused setup --provider url --url http://insecure.example/update?ip={ip}
refused setup --provider url --url https://provider.example/update
refused update                                           # before setup

# DuckDNS
export FAKE_IP="203.0.113.9"
OUT="$("$DDNS" setup --provider duckdns --domain casa-armor --token abcdef-1234-5678 2>&1)"
expect_in "$OUT" "now points at 203.0.113.9"
LOG="$(cat "$TMP/log")"
expect_in "$LOG" "domains=casa-armor&token=abcdef-1234-5678&ip=203.0.113.9"
expect_out "$(grep '^ARGS' "$TMP/log")" "abcdef-1234-5678"      # the token is never on the command line
[[ "$(cat "$TMP/data/ddns.last")" == "203.0.113.9" ]] && ok || bad "the last address must be kept"
# nothing changed: nothing is called
: >"$TMP/log"
expect_in "$("$DDNS" update 2>&1)" "nothing to do"
[[ ! -s "$TMP/log" ]] && ok || bad "an unchanged address must not call the provider"
# the address changed
FAKE_IP="203.0.113.77" "$DDNS" update >/dev/null 2>&1
expect_in "$(cat "$TMP/log")" "ip=203.0.113.77"
# the provider refuses
FAKE_IP="203.0.113.78" FAKE_DUCK="KO" "$DDNS" update >/dev/null 2>&1; [[ $? -eq 2 ]] && ok || bad "a refusal of the provider must be an error"
[[ "$(cat "$TMP/data/ddns.last")" == "203.0.113.77" ]] && ok || bad "a failed update must not be remembered"

# addresses no name can reach
for bad_ip in 192.168.0.5 10.1.2.3 172.16.4.4 100.64.5.5 127.0.0.1 169.254.1.1; do
  out="$(FAKE_IP="$bad_ip" "$DDNS" update --force 2>&1)"; [[ $? -eq 2 ]] && ok || bad "$bad_ip must be refused"
  expect_in "$out" "no name can reach"
done
out="$(FAKE_IP="not an address" "$DDNS" update --force 2>&1)"; [[ $? -eq 2 ]] && ok || bad "garbage from the address service must be refused"

# Cloudflare: finds the record, updates it, the token goes in a header read from the standard input
: >"$TMP/log"
"$DDNS" setup --provider cloudflare --zone 0123456789abcdef0123456789abcdef --record-name casa.example.org --token cf-token-ABCDEFGH >/dev/null 2>&1
LOG="$(cat "$TMP/log")"
expect_in "$LOG" "header = \"Authorization: Bearer cf-token-ABCDEFGH\""
expect_in "$LOG" "request = \"PUT\""
expect_in "$LOG" "dns_records/0123456789abcdef0123456789abcdef"
expect_in "$LOG" 'content\":\"203.0.113.9'
expect_out "$(grep '^ARGS' "$TMP/log")" "cf-token-ABCDEFGH"

# any address you can call
: >"$TMP/log"
"$DDNS" setup --provider url --url 'https://provider.example/update?host=casa&ip={ip}' >/dev/null 2>&1
expect_in "$(cat "$TMP/log")" "https://provider.example/update?host=casa&ip=203.0.113.9"

expect_in "$("$DDNS" status)" "provider: url"
[[ "$(uname -s)" != Linux ]] || [[ "$(stat -c %a "$TMP/etc/armor.ddns.env")" == "600" ]] && ok || bad "the settings hold a token and must be private"
"$DDNS" remove >/dev/null 2>&1
[[ ! -f "$TMP/etc/armor.ddns.env" ]] && ok || bad "remove must put the token file aside"

echo "armor_ddns tests: $PASSED passed, $FAILED failed"
[[ "$FAILED" -eq 0 ]]
