#!/usr/bin/env bash
# ARMOR-DEVOPS - tests of the two safeguards of install_cm5.sh around the switch of `current`: the free-space check and the way back to the previous release.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
# Nothing is installed: the installer is loaded as a library (ARMOR_INSTALL_LIB_ONLY=1) and its functions run in a temporary folder.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf -- "$WORK"' EXIT
FAILED=0; CHECKS=0
check() { CHECKS=$((CHECKS + 1)); if ! "$@"; then echo "FAIL: $*" >&2; FAILED=$((FAILED + 1)); fi; }
lib() { ( fn=("$@"); set --; ARMOR_INSTALL_LIB_ONLY=1 source "$HERE/install_cm5.sh"; "${fn[@]}" ) 2>&1; }

# free space: a folder that does not exist yet is judged by its nearest parent
out="$(lib preflight_free_space "$WORK/not/yet/here" 1)"; check test $? -eq 0
out="$(lib preflight_free_space "$WORK" 999999999)"; st=$?
check test "$st" -eq 1
check grep -q "MB are needed" <<<"$out"
out="$(lib preflight_free_space "$WORK" abc)"; st=$?
check test "$st" -eq 1
check grep -q "must be a number" <<<"$out"

# the way back
mkdir -p "$WORK/p/releases/old" "$WORK/p/releases/new"
ln -sfn "$WORK/p/releases/new" "$WORK/p/current"
lib rollback_current "$WORK/p" "$WORK/p/releases/old" >/dev/null; check test $? -eq 0
check test "$(readlink "$WORK/p/current")" = "$WORK/p/releases/old"
check test ! -e "$WORK/p/current.new"
# no previous release (a first install), or one that is gone: nothing changes and it says so
ln -sfn "$WORK/p/releases/new" "$WORK/p/current"
lib rollback_current "$WORK/p" "" >/dev/null; check test $? -eq 1
lib rollback_current "$WORK/p" "$WORK/p/releases/gone" >/dev/null; check test $? -eq 1
check test "$(readlink "$WORK/p/current")" = "$WORK/p/releases/new"
# the installer wires them in
check grep -q 'preflight_free_space "\$PREFIX"' "$HERE/install_cm5.sh"
check grep -q 'rollback_current "\$PREFIX" "\$PREVIOUS_RELEASE"' "$HERE/install_cm5.sh"

echo "$CHECKS checks, $FAILED failures"
if [[ "$FAILED" -ne 0 ]]; then exit 1; fi
echo "ARMOR_DEVOPS_INSTALL_ROLLBACK=PASS"
