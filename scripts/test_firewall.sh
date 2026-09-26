#!/usr/bin/env bash
# ARMOR-DEVOPS - tests of scripts/firewall_core.sh: the rules it prints, what it refuses, and (when nft is installed) that nft accepts them.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
# Nothing is loaded: only `print` and `check` are used, so it needs no root and changes nothing.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FW="$HERE/firewall_core.sh"
PASSED=0; FAILED=0
ok() { PASSED=$((PASSED + 1)); }
bad() { FAILED=$((FAILED + 1)); echo "FAIL: $*"; }
expect_in()  { grep -qF -- "$2" <<<"$1" && ok || bad "expected: $2"; }
expect_out() { grep -qF -- "$2" <<<"$1" && bad "did not expect: $2" || ok; }
refused() { local out; out="$("$FW" "$@" 2>&1)"; local code=$?; [[ $code -eq 2 ]] && ok || bad "should have been refused (code $code): $*  -> $out"; }

# the standard rules: the field network on the broker, the clients on the web ports
RULES="$("$FW" print --field 192.168.0.0/24 --clients 192.168.10.0/24 --clients 10.8.0.0/24)"
expect_in  "$RULES" "table inet armor_core {"
expect_in  "$RULES" "policy accept;"
expect_in  "$RULES" "tcp dport 18883 ip saddr { 192.168.0.0/24 } accept"
expect_in  "$RULES" "tcp dport 18883 counter drop"
expect_in  "$RULES" "tcp dport { 18080, 18081 } ip saddr { 192.168.10.0/24,10.8.0.0/24 } accept"
expect_in  "$RULES" "tcp dport { 18080, 18081 } counter drop"
expect_in  "$RULES" "iifname \"lo\" accept"
expect_in  "$RULES" "ct state established,related accept"
# it never takes over the machine: no drop policy, and no port but A.R.M.O.R.'s
expect_out "$RULES" "policy drop"
expect_out "$RULES" "dport 22"
expect_out "$RULES" "dport 1883"
[[ "$(grep -c 'dport' <<<"$RULES")" == "4" ]] && ok || bad "only the four rules of A.R.M.O.R.'s ports were expected"

# without --clients the server and Studio stay open (the login protects them): only the broker is closed
OPEN="$("$FW" print --field 192.168.0.0/24)"
expect_in  "$OPEN" "tcp dport 18883 counter drop"
expect_out "$OPEN" "tcp dport { 18080, 18081 }"

# other ports, a trusted interface, more than one field network
OTHER="$("$FW" print --field 192.168.0.0/24 --field 172.16.5.0/28 --mqtt-port 28883 --server-port 28080 --studio-port 28081 --clients 10.0.0.0/8 --trust-iface docker0)"
expect_in  "$OTHER" "tcp dport 28883 ip saddr { 192.168.0.0/24,172.16.5.0/28 } accept"
expect_in  "$OTHER" "tcp dport { 28080, 28081 } ip saddr { 10.0.0.0/8 } accept"
expect_in  "$OTHER" "iifname \"docker0\" accept"
expect_out "$OTHER" "18883"

# a single host is a /32
expect_in  "$("$FW" print --field 192.168.0.50)" "ip saddr { 192.168.0.50 } accept"

# what it refuses (exit 2, nothing printed as rules)
refused print                                                   # no field network
refused print --clients 192.168.10.0/24                         # still no field network
refused print --field 192.168.0.0/33
refused print --field 300.1.1.0/24
refused print --field 192.168.0.0/24/8
refused print --field "192.168.0.0/24; drop"
refused print --field 192.168.0.0/24 --clients not-a-network
refused print --field 192.168.0.0/24 --mqtt-port 0
refused print --field 192.168.0.0/24 --mqtt-port 70000
refused print --field 192.168.0.0/24 --mqtt-port 18080          # two services on one port
refused print --field 192.168.0.0/24 --server-port 18081
refused print --field 192.168.0.0/24 --trust-iface 'eth0; flush ruleset'
refused print --field 192.168.0.0/24 --table 'a b'
refused print --field 192.168.0.0/24 --unknown
refused frobnicate
refused apply --field 192.168.0.0/24 --rollback-after 3        # not as root here, and too short anyway
refused

# the syntax is checked by nft itself when the machine has it
CHECK="$("$FW" check --field 192.168.0.0/24 --clients 192.168.10.0/24 2>&1)"
if grep -q "FIREWALL_CHECK=SKIP" <<<"$CHECK"; then echo "note: nft is not installed here; the rules were not checked by it"; else expect_in "$CHECK" "FIREWALL_CHECK=PASS"; fi

echo "$PASSED checks, $FAILED failures"
[[ $FAILED -eq 0 ]] && echo "ARMOR_DEVOPS_FIREWALL=PASS"
exit $(( FAILED == 0 ? 0 : 1 ))
