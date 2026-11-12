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

# A copy to another machine (scp + ssh) and to an rclone remote, and the contents of Docker volumes: stand-ins for scp, ssh, rclone and docker.
mkdir -p "$WORK/fake" "$WORK/remote" "$WORK/rcloned" "$WORK/volumes/broker-data" "$WORK/volumes/extra"
echo retained >"$WORK/volumes/broker-data/mosquitto.db"
echo other >"$WORK/volumes/extra/x.txt"
cat >"$WORK/fake/scp" <<'FAKE'
#!/usr/bin/env bash
# scp -q -o BatchMode=yes -- FILE... HOST:DIR/  (the remote folder is $ARMOR_TEST_REMOTE)
[[ "${ARMOR_TEST_FAIL:-}" != scp ]] || exit 1
args=("$@"); dest="${args[-1]}"; unset 'args[-1]'
[[ "$dest" == *:* ]] || exit 2
for f in "${args[@]}"; do [[ -f "$f" ]] && cp -- "$f" "$ARMOR_TEST_REMOTE/"; done
exit 0
FAKE
cat >"$WORK/fake/ssh" <<'FAKE'
#!/usr/bin/env bash
# ssh -o BatchMode=yes -- HOST "cd 'DIR' && sha256sum -c 'NAME.sha256'"
cmd="${*: -1}"; cmd="${cmd#cd \'*\' && }"
cd "$ARMOR_TEST_REMOTE" && eval "$cmd"
FAKE
cat >"$WORK/fake/rclone" <<'FAKE'
#!/usr/bin/env bash
case "$1" in
  copy) [[ "${ARMOR_TEST_FAIL:-}" != rclone ]] || exit 1; cp -- "${@: -2:1}" "$ARMOR_TEST_RCLONE/" ;;
  check) src="${@: -2:1}"; for f in "$ARMOR_TEST_RCLONE"/*; do cmp -s "$f" "$src/$(basename "$f")" || exit 1; done ;;
  *) exit 2 ;;
esac
FAKE
cat >"$WORK/fake/docker" <<'FAKE'
#!/usr/bin/env bash
# docker run --rm --network none -v NAME:/volume:ro busybox tar -C /volume -cf - .
vol=""; for a in "$@"; do [[ "$a" == *:/volume:ro ]] && vol="${a%%:*}"; done
[[ -d "$ARMOR_TEST_VOLUMES/$vol" ]] || { echo "no such volume: $vol" >&2; exit 1; }
tar -C "$ARMOR_TEST_VOLUMES/$vol" -cf - .
FAKE
chmod +x "$WORK"/fake/*
export ARMOR_TEST_REMOTE="$WORK/remote" ARMOR_TEST_RCLONE="$WORK/rcloned" ARMOR_TEST_VOLUMES="$WORK/volumes"
export PATH="$WORK/fake:$PATH"
OUTR="$("$HERE/backup_data.sh" --data-dir "$WORK/data" --out-dir "$WORK/remoteout" --passphrase-file "$WORK/pass" --copy-ssh backup@nas.local:/srv/armor --copy-rclone cloud:armor/backups)"
grep -q 'ARMOR_BACKUP=PASS' <<<"$OUTR"
[[ "$(ls "$WORK"/remote/*.enc | wc -l)" -eq 1 && "$(ls "$WORK"/rcloned/*.sha256 | wc -l)" -eq 1 ]]
# A remote copy that fails is not a success; the verified archive stays where it was made.
sleep 1
if ARMOR_TEST_FAIL=scp "$HERE/backup_data.sh" --data-dir "$WORK/data" --out-dir "$WORK/remoteout" --passphrase-file "$WORK/pass" --copy-ssh backup@nas.local:/srv/armor 2>/dev/null; then echo "a failed scp was reported as a success" >&2; exit 1; fi
sleep 1
if ARMOR_TEST_FAIL=rclone "$HERE/backup_data.sh" --data-dir "$WORK/data" --out-dir "$WORK/remoteout" --passphrase-file "$WORK/pass" --copy-rclone cloud:armor/backups 2>/dev/null; then echo "a failed rclone copy was reported as a success" >&2; exit 1; fi
[[ "$(ls "$WORK"/remoteout/*.enc | wc -l)" -ge 3 ]]
# A remote or a volume name that could be read as an option is refused before anything is written.
for bad in "-oProxyCommand=x:/a" "host:relative" "host:/a b" "host:/a;b"; do
  if "$HERE/backup_data.sh" --data-dir "$WORK/data" --out-dir "$WORK/refused" --passphrase-file "$WORK/pass" --copy-ssh "$bad" 2>/dev/null; then echo "--copy-ssh accepted: $bad" >&2; exit 1; fi
done
if "$HERE/backup_data.sh" --data-dir "$WORK/data" --out-dir "$WORK/refused" --passphrase-file "$WORK/pass" --copy-rclone "-bad:x" 2>/dev/null; then echo "--copy-rclone accepted a dash" >&2; exit 1; fi
if "$HERE/backup_data.sh" --data-dir "$WORK/data" --out-dir "$WORK/refused" --passphrase-file "$WORK/pass" --compose-volume "../x" 2>/dev/null; then echo "--compose-volume accepted a path" >&2; exit 1; fi
[[ ! -e "$WORK/refused" ]] || { echo "a refused option wrote something" >&2; exit 1; }
# Docker volumes go into the archive and come back out with --volumes-to; a volume that cannot be read stops the whole backup.
OUTV="$("$HERE/backup_data.sh" --data-dir "$WORK/data" --out-dir "$WORK/voluout" --passphrase-file "$WORK/pass" --compose-volume broker-data --compose-volume extra)"
grep -q 'volumes=2' <<<"$OUTV"
VARCHIVE="$(ls "$WORK"/voluout/*.enc)"
LISTV="$("$HERE/restore_data.sh" --file "$VARCHIVE" --data-dir "$WORK/vrestored" --passphrase-file "$WORK/pass")"
grep -q 'armor-volumes/broker-data.tar' <<<"$LISTV"
DONEV="$("$HERE/restore_data.sh" --file "$VARCHIVE" --data-dir "$WORK/vrestored" --passphrase-file "$WORK/pass" --apply --volumes-to "$WORK/vback")"
grep -q 'ARMOR_RESTORE=PASS' <<<"$DONEV"
[[ -f "$WORK/vrestored/cameras.json" && -s "$WORK/vback/broker-data.tar" && -s "$WORK/vback/extra.tar" ]]
TARV="$(tar -tf "$WORK/vback/broker-data.tar")"
grep -q 'mosquitto.db' <<<"$TARV"
if "$HERE/backup_data.sh" --data-dir "$WORK/data" --out-dir "$WORK/voluout2" --passphrase-file "$WORK/pass" --compose-volume does-not-exist 2>/dev/null; then echo "a missing volume was accepted" >&2; exit 1; fi
[[ -z "$(ls "$WORK"/voluout2/*.enc 2>/dev/null)" ]] || { echo "a backup with a missing volume left an archive" >&2; exit 1; }

echo "ARMOR_BACKUP_TEST=PASS"
