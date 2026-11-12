#!/usr/bin/env bash
# ARMOR-DEVOPS - tests of scripts/ssh_host_pin.sh with stand-ins for ssh-keyscan and ssh-keygen: the key with the right fingerprint is pinned, another host (a different key) is refused, bad input is refused.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
# Nothing is connected to: the two programs are scripts in a temporary folder that come first in PATH.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIN="$HERE/ssh_host_pin.sh"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
PASSED=0; FAILED=0
ok() { PASSED=$((PASSED + 1)); }
bad() { FAILED=$((FAILED + 1)); echo "FAIL: $*"; }
GOOD="SHA256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
OTHER="SHA256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
mkdir -p "$WORK/bin"
# the "host" has two keys; ssh-keygen -lf - says the fingerprint written in the second word of the key line
cat > "$WORK/bin/ssh-keyscan" <<'S'
#!/usr/bin/env bash
echo "# comment"
echo "host ssh-ed25519 FP-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
echo "host ssh-rsa FP-cccccccccccccccccccccccccccccccccccccccccccc"
S
cat > "$WORK/bin/ssh-keygen" <<'S'
#!/usr/bin/env bash
read -r line
fp="${line##* FP-}"
echo "256 SHA256:$fp host (ED25519)"
S
chmod +x "$WORK/bin/"*
export PATH="$WORK/bin:$PATH"

out="$("$PIN" 192.168.0.180 22 "$GOOD" "$WORK/known" 2>&1)"; code=$?
[[ $code -eq 0 ]] && ok || bad "the right fingerprint should be pinned (code $code): $out"
[[ "$(wc -l < "$WORK/known")" -eq 1 ]] && grep -q "ssh-ed25519" "$WORK/known" && ok || bad "only the matching key is written"
grep -q "ssh-rsa" "$WORK/known" && bad "the other key must not be written" || ok

out="$("$PIN" 192.168.0.180 22 "$OTHER" "$WORK/known2" 2>&1)"; code=$?
[[ $code -eq 3 ]] && ok || bad "another fingerprint must be refused with 3 (code $code)"
[[ ! -s "$WORK/known2" ]] && ok || bad "nothing may be written for a host that does not match"
grep -q "not connecting" <<<"$out" && ok || bad "the refusal should say it does not connect"

for args in "bad host 22 $GOOD $WORK/k" "192.168.0.180 99x $GOOD $WORK/k" "192.168.0.180 22 SHA256:short $WORK/k" "192.168.0.180 22 $GOOD"; do
  # shellcheck disable=SC2086
  "$PIN" $args >/dev/null 2>&1; code=$?
  [[ $code -eq 2 ]] && ok || bad "should be refused with 2 (code $code): $args"
done

echo "ssh host pin: $PASSED passed, $FAILED failed"
[[ $FAILED -eq 0 ]]
