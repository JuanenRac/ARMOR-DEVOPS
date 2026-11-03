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

# Rotation and an extra copy: only the newest N stay; the copy is checked.
for n in 1 2 3; do
  sleep 1
  "$HERE/backup_data.sh" --data-dir "$WORK/data" --out-dir "$WORK/rot" --passphrase-file "$WORK/pass" --keep 2 --copy-to "$WORK/mirror" >/dev/null
done
[[ "$(ls "$WORK"/rot/*.enc | wc -l)" -eq 2 ]]
[[ "$(ls "$WORK"/rot/*.sha256 | wc -l)" -eq 2 ]]
[[ "$(ls "$WORK"/mirror/*.enc | wc -l)" -eq 3 ]]
if "$HERE/backup_data.sh" --data-dir "$WORK/data" --out-dir "$WORK/rot" --passphrase-file "$WORK/pass" --keep x 2>/dev/null; then echo "a bad --keep was accepted" >&2; exit 1; fi

# A USB copy: only onto a mounted disk (a stand-in for `mountpoint` answers for the mirror folder), and never onto the system card.
mkdir -p "$WORK/bin" "$WORK/usb"
cat >"$WORK/bin/mountpoint" <<'EOF'
#!/usr/bin/env bash
[[ "${*: -1}" == "$ARMOR_TEST_MOUNTED" ]]
EOF
chmod +x "$WORK/bin/mountpoint"
export PATH="$WORK/bin:$PATH"
export ARMOR_TEST_MOUNTED="$WORK/usb"
if "$HERE/backup_data.sh" --data-dir "$WORK/data" --out-dir "$WORK/usbout" --passphrase-file "$WORK/pass" --copy-to "$WORK/unplugged" --require-mount 2>/dev/null; then echo "an unmounted disk was accepted" >&2; exit 1; fi
[[ ! -e "$WORK/usbout" && ! -e "$WORK/unplugged" ]] || { echo "nothing may be written when the disk is not mounted" >&2; exit 1; }
if "$HERE/backup_data.sh" --data-dir "$WORK/data" --out-dir "$WORK/usbout" --passphrase-file "$WORK/pass" --require-mount 2>/dev/null; then echo "--require-mount without --copy-to was accepted" >&2; exit 1; fi
"$HERE/backup_data.sh" --data-dir "$WORK/data" --out-dir "$WORK/usbout" --passphrase-file "$WORK/pass" --copy-to "$WORK/usb" --require-mount | grep -q 'ARMOR_BACKUP=PASS'
[[ "$(ls "$WORK"/usb/*.enc | wc -l)" -eq 1 && -f "$(ls "$WORK"/usb/*.enc)".sha256 ]]

echo "ARMOR_BACKUP_TEST=PASS"
