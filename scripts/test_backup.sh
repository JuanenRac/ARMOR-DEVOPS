#!/usr/bin/env bash
# ARMOR-DEVOPS - round-trip test of backup_data.sh and restore_data.sh in a
# temporary directory: backup, wrong passphrase, dry run, restore over existing data.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf -- "$WORK"' EXIT

mkdir -p "$WORK/data/media/cam-01"
echo '{"schema":1}' >"$WORK/data/cameras.json"
echo '{"mode":"armed"}' >"$WORK/data/state.json"
echo big >"$WORK/data/media/cam-01/a.jpg"
printf 'a-long-enough-passphrase\n' >"$WORK/pass"
printf 'another-long-passphrase\n' >"$WORK/wrong"

OUT="$("$HERE/backup_data.sh" --data-dir "$WORK/data" --out-dir "$WORK/out" --passphrase-file "$WORK/pass")"
grep -q 'ARMOR_BACKUP=PASS' <<<"$OUT"
ARCHIVE="$(ls "$WORK"/out/*.enc)"
[[ -f "$ARCHIVE.sha256" ]]

# Evidence is excluded by default.
LISTING="$("$HERE/restore_data.sh" --file "$ARCHIVE" --data-dir "$WORK/restored" --passphrase-file "$WORK/pass")"
grep -q 'cameras.json' <<<"$LISTING"
if grep -q 'a.jpg' <<<"$LISTING"; then echo "media leaked into the default backup" >&2; exit 1; fi

# A wrong passphrase must fail and change nothing.
if "$HERE/restore_data.sh" --file "$ARCHIVE" --data-dir "$WORK/restored" --passphrase-file "$WORK/wrong" --apply 2>/dev/null; then echo "a wrong passphrase was accepted" >&2; exit 1; fi
[[ ! -e "$WORK/restored" ]]

# Restoring over existing data keeps the old directory.
mkdir -p "$WORK/live" && echo old >"$WORK/live/old.txt"
DONE="$("$HERE/restore_data.sh" --file "$ARCHIVE" --data-dir "$WORK/live" --passphrase-file "$WORK/pass" --apply)"
grep -q 'ARMOR_RESTORE=PASS' <<<"$DONE"
[[ "$(cat "$WORK/live/state.json")" == '{"mode":"armed"}' ]]
ls "$WORK"/live.before-restore-*/old.txt >/dev/null

# A damaged archive fails its checksum.
printf 'x' >>"$ARCHIVE"
if "$HERE/restore_data.sh" --file "$ARCHIVE" --data-dir "$WORK/again" --passphrase-file "$WORK/pass" 2>/dev/null; then echo "a damaged archive was accepted" >&2; exit 1; fi

echo "ARMOR_BACKUP_TEST=PASS"
