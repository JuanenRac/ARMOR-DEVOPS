#!/usr/bin/env bash
# ARMOR-DEVOPS - tests of scripts/armor_fail2ban.sh: what it writes, what it refuses, and that the filter matches the refused sign-ins of the audit log (and only those). The
# filter is run with Python's regular expressions (<HOST> replaced by an address pattern), so it needs no fail2ban and no root.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
F2B="$HERE/armor_fail2ban.sh"
PASSED=0; FAILED=0
ok() { PASSED=$((PASSED + 1)); }
bad() { FAILED=$((FAILED + 1)); echo "FAIL: $*"; }
expect_in()  { grep -qF -- "$2" <<<"$1" && ok || bad "expected: $2"; }
refused() { local out; out="$("$F2B" "$@" 2>&1)"; local code=$?; [[ $code -eq 2 ]] && ok || bad "should have been refused (code $code): $*  -> $out"; }
PY="$(command -v python3 || command -v python || command -v py)"

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
export ARMOR_F2B_ETC="$TMP/etc" ARMOR_F2B_NOSYSTEMD=1

PLAN="$("$F2B" plan --data-dir "$TMP/data" --maxretry 3 --findtime 300 --bantime 7200 --ignoreip "192.168.0.0/24")"
expect_in "$PLAN" "logpath  = $TMP/data/audit.log"
expect_in "$PLAN" "maxretry = 3"
expect_in "$PLAN" "findtime = 300"
expect_in "$PLAN" "bantime  = 7200"
expect_in "$PLAN" "ignoreip = 127.0.0.1/8 ::1 192.168.0.0/24"
expect_in "$PLAN" "port     = 18080,18081"
[[ ! -e "$TMP/etc" ]] && ok || bad "plan must not write anything"

refused plan --maxretry 0
refused plan --maxretry x
refused plan --ports "80;rm"
refused plan --ignoreip "1.2.3.4; reboot"
refused setup --bogus
refused bogus

"$F2B" setup --data-dir "$TMP/data" >/dev/null
[[ -f "$TMP/etc/filter.d/armor-studio.conf" && -f "$TMP/etc/jail.d/armor-studio.local" ]] && ok || bad "setup must write the filter and the jail"
"$F2B" status >/dev/null && ok || bad "status after setup"

# the filter against audit lines
cat >"$TMP/audit.log" <<'EOF'
{"at":"2026-01-01T10:00:00.000Z","action":"studio.login","outcome":"denied","actor":"admin","detail":"remote 203.0.113.9"}
{"at":"2026-01-01T10:00:01.000Z","action":"studio.login","outcome":"denied","actor":"nobody","detail":"local 192.168.0.40"}
{"at":"2026-01-01T10:00:02.000Z","action":"studio.totp","outcome":"denied","actor":"admin","detail":"remote 198.51.100.7"}
{"at":"2026-01-01T10:00:03.000Z","action":"studio.login","outcome":"denied","actor":"admin","detail":"remote ::ffff:203.0.113.10"}
{"at":"2026-01-01T10:00:04.000Z","action":"studio.login","outcome":"allowed","actor":"admin","detail":"remote 203.0.113.11"}
{"at":"2026-01-01T10:00:05.000Z","action":"studio.login","outcome":"denied","actor":"admin","detail":"remote 203.0.113.12, the second factor is required and not set up"}
{"at":"2026-01-01T10:00:06.000Z","action":"studio.login","outcome":"denied","actor":"x\",\"detail\":\"remote 9.9.9.9","detail":"remote 203.0.113.13"}
{"at":"2026-01-01T10:00:07.000Z","action":"alarm.disarm","outcome":"denied","actor":"admin","detail":"remote 203.0.113.14"}
EOF
FOUND="$("$PY" -I - "$TMP/etc/filter.d/armor-studio.conf" "$TMP/audit.log" <<'PYEOF' | tr -d '\r'
import re, sys
text = open(sys.argv[1], encoding="utf-8").read()
raw = re.search(r"^failregex\s*=\s*(.+)$", text, re.M).group(1)
pattern = re.compile(raw.replace("<HOST>", r"(?P<host>[0-9A-Fa-f:.]+)"))
for line in open(sys.argv[2], encoding="utf-8"):
    found = pattern.search(line.rstrip("\n"))
    if found:
        print(found.group("host"))
PYEOF
)"
[[ "$FOUND" == $'203.0.113.9\n192.168.0.40\n198.51.100.7\n::ffff:203.0.113.10\n203.0.113.13' ]] && ok || bad "the filter matched the wrong lines: $FOUND"
expect_in "$(cat "$TMP/etc/filter.d/armor-studio.conf")" "datepattern"

"$F2B" remove >/dev/null
[[ ! -e "$TMP/etc/jail.d/armor-studio.local" ]] && ok || bad "remove must delete the jail"
"$F2B" status >/dev/null 2>&1 && bad "status after remove" || ok

echo "armor_fail2ban tests: $PASSED passed, $FAILED failed"
[[ "$FAILED" -eq 0 ]] && echo "ARMOR_FAIL2BAN_TEST=PASS" || exit 1
