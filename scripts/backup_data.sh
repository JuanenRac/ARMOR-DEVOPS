#!/usr/bin/env bash
# ARMOR-DEVOPS - encrypted backup of the server data directory (camera vault,
# evidence index, state, rules, event history, audit log).
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
#
# The archive is encrypted with AES-256 (PBKDF2) using a passphrase read from a
# file, and is verified by decrypting it again before the script reports success.
# It never includes the environment file: the camera key (ARMOR_CAMERA_CONFIG_KEY)
# must be kept somewhere else, because the vault is unreadable without it.
# Recorded media can be large: the whole media folder is left out of the archive
# unless --with-media is given.
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: backup_data.sh --data-dir DIR --out-dir DIR --passphrase-file FILE [--with-media]
                      [--keep N] [--copy-to DIR [--require-mount]]
                      [--copy-ssh HOST:DIR] [--copy-rclone REMOTE:PATH] [--compose-volume NAME]...

  --data-dir         the server data directory (ARMOR_DATA_DIR)
  --out-dir          where the .tar.gz.enc archive and its .sha256 are written
  --passphrase-file  a file whose first line is the passphrase (mode 600)
  --with-media       also include recorded evidence (can be very large)
  --keep N           after a verified backup, keep only the N newest archives of the
                     output folder (and their .sha256); 0 or unset keeps everything
  --copy-to DIR      also copy the archive and its .sha256 to DIR (a mounted share or
                     an external disk), and check the copy with sha256sum
  --require-mount    with --copy-to: refuse unless DIR is a mounted device of its own (a USB
                     disk that is plugged in), so an unplugged disk never makes the copy land
                     on the system card; the copy is also refused when the disk lacks room
                     for the archive, and is flushed to the disk before the script reports success
  --copy-ssh         also copy the archive and its .sha256 to a folder of another machine with scp, and
                     check the copy there with sha256sum (the key and the host come from your ssh setup)
  --copy-rclone      also copy them to an rclone remote (REMOTE:PATH) and check the copy with rclone check
  --compose-volume   also include the contents of a Docker volume (the named volumes of docker-compose.yml,
                     for example the broker's data); repeat the option for each volume. Each one is read
                     with a throw-away container, read-only, and goes into the archive under armor-volumes/
USAGE
}

DATA_DIR="" OUT_DIR="" PASS_FILE="" WITH_MEDIA=0 KEEP=0 COPY_TO="" REQUIRE_MOUNT=0 COPY_SSH="" COPY_RCLONE="" VOLUMES=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --data-dir) DATA_DIR="${2:-}"; shift 2 ;;
    --out-dir) OUT_DIR="${2:-}"; shift 2 ;;
    --passphrase-file) PASS_FILE="${2:-}"; shift 2 ;;
    --with-media) WITH_MEDIA=1; shift ;;
    --keep) KEEP="${2:-}"; shift 2 ;;
    --copy-to) COPY_TO="${2:-}"; shift 2 ;;
    --require-mount) REQUIRE_MOUNT=1; shift ;;
    --copy-ssh) COPY_SSH="${2:-}"; shift 2 ;;
    --copy-rclone) COPY_RCLONE="${2:-}"; shift 2 ;;
    --compose-volume) VOLUMES+=("${2:-}"); shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done
[[ -d "$DATA_DIR" && -n "$OUT_DIR" && -f "$PASS_FILE" ]] || { usage >&2; exit 2; }
[[ "$KEEP" =~ ^[0-9]+$ ]] || { echo "--keep needs a whole number" >&2; exit 2; }
# A remote or a volume name never starts with a dash (it would be read as an option by scp, rclone or docker) and never holds a space or a control character.
if [[ -n "$COPY_SSH" ]] && ! [[ "$COPY_SSH" =~ ^[A-Za-z0-9._@-]+:/[A-Za-z0-9._/@+-]+$ && "$COPY_SSH" != -* ]]; then echo "--copy-ssh needs HOST:/ABSOLUTE/DIR (letters, digits and . _ @ - / +)" >&2; exit 2; fi
if [[ -n "$COPY_RCLONE" ]] && ! [[ "$COPY_RCLONE" =~ ^[A-Za-z0-9_][A-Za-z0-9_.-]*:[A-Za-z0-9._/@+-]+$ ]]; then echo "--copy-rclone needs REMOTE:PATH (letters, digits and . _ @ - / +)" >&2; exit 2; fi
for v in "${VOLUMES[@]+"${VOLUMES[@]}"}"; do
  [[ "$v" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]*$ ]] || { echo "--compose-volume needs a Docker volume name (letters, digits and . _ -)" >&2; exit 2; }
done
if [[ "$REQUIRE_MOUNT" -eq 1 ]]; then
  [[ -n "$COPY_TO" ]] || { echo "--require-mount needs --copy-to" >&2; exit 2; }
  command -v mountpoint >/dev/null || { echo "mountpoint is required for --require-mount" >&2; exit 1; }
  mountpoint -q -- "$COPY_TO" || { echo "$COPY_TO is not a mounted disk: plug the USB disk in (nothing was backed up)" >&2; exit 1; }
fi
command -v openssl >/dev/null || { echo "openssl is required" >&2; exit 1; }
# A native Windows openssl (Git Bash) does not translate the path inside "file:"; give it a Windows path.
PASS_PATH="$PASS_FILE"; if command -v cygpath >/dev/null 2>&1; then PASS_PATH="$(cygpath -m "$PASS_FILE")"; fi
[[ -s "$PASS_FILE" ]] || { echo "the passphrase file is empty" >&2; exit 1; }
if [[ "$(wc -c <"$PASS_FILE")" -lt 12 ]]; then echo "the passphrase must be at least 12 characters" >&2; exit 1; fi

mkdir -p "$OUT_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
TARGET="$OUT_DIR/armor-data-$STAMP.tar.gz.enc"
[[ ! -e "$TARGET" ]] || { echo "refusing to overwrite $TARGET" >&2; exit 1; }
PARENT="$(cd "$DATA_DIR/.." && pwd)"
BASE="$(basename "$(cd "$DATA_DIR" && pwd)")"

EXCLUDES=(--exclude="$BASE/*.tmp")
[[ "$WITH_MEDIA" -eq 1 ]] || EXCLUDES+=(--exclude="$BASE/media")

umask 077
STAGE=""
if [[ "${#VOLUMES[@]}" -gt 0 ]]; then
  command -v docker >/dev/null || { echo "docker is required for --compose-volume" >&2; exit 1; }
  STAGE="$(mktemp -d)"; trap 'rm -rf -- "$STAGE"' EXIT
  mkdir -p "$STAGE/armor-volumes"
  for v in "${VOLUMES[@]}"; do
    # Read-only, no network, nothing else mounted: the container only streams the volume as a tar.
    docker run --rm --network none -v "$v:/volume:ro" busybox tar -C /volume -cf - . >"$STAGE/armor-volumes/$v.tar" || { echo "the Docker volume $v could not be read (nothing was backed up)" >&2; exit 1; }
    [[ -s "$STAGE/armor-volumes/$v.tar" ]] || { echo "the Docker volume $v gave an empty archive (nothing was backed up)" >&2; exit 1; }
  done
fi
VOLUME_ARGS=(); [[ -z "$STAGE" ]] || VOLUME_ARGS=(-C "$STAGE" armor-volumes)
tar -C "$PARENT" -czf - "${EXCLUDES[@]}" "$BASE" "${VOLUME_ARGS[@]+"${VOLUME_ARGS[@]}"}" | openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -pass "file:$PASS_PATH" -out "$TARGET"

# Verify: it must decrypt and list at least the directory itself.
COUNT="$(openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass "file:$PASS_PATH" -in "$TARGET" | tar -tzf - | wc -l)"
if [[ "$COUNT" -lt 1 ]]; then rm -f -- "$TARGET"; echo "verification failed: the archive is empty" >&2; exit 1; fi
( cd "$OUT_DIR" && sha256sum "$(basename "$TARGET")" >"$(basename "$TARGET").sha256" )

if [[ -n "$COPY_TO" ]]; then
  mkdir -p "$COPY_TO"
  if [[ "$REQUIRE_MOUNT" -eq 1 ]]; then
    NEED_KB="$(( ($(wc -c <"$TARGET") + 1023) / 1024 + 1 ))"
    FREE_KB="$(df -Pk -- "$COPY_TO" | awk 'NR==2 {print $4}')"
    if [[ ! "$FREE_KB" =~ ^[0-9]+$ || "$FREE_KB" -lt "$NEED_KB" ]]; then echo "the disk at $COPY_TO has no room for the archive (needs $NEED_KB KiB); the verified archive stays in $OUT_DIR" >&2; exit 1; fi
  fi
  cp -- "$TARGET" "$TARGET.sha256" "$COPY_TO/"
  ( cd "$COPY_TO" && sha256sum -c "$(basename "$TARGET").sha256" >/dev/null ) || { echo "the copy in $COPY_TO does not match its checksum" >&2; exit 1; }
  [[ "$REQUIRE_MOUNT" -ne 1 ]] || sync
fi

if [[ -n "$COPY_SSH" ]]; then
  command -v scp >/dev/null && command -v ssh >/dev/null || { echo "scp and ssh are required for --copy-ssh" >&2; exit 1; }
  RHOST="${COPY_SSH%%:*}"; RDIR="${COPY_SSH#*:}"; NAME="$(basename "$TARGET")"
  scp -q -o BatchMode=yes -- "$TARGET" "$TARGET.sha256" "$RHOST:$RDIR/" || { echo "the copy to $COPY_SSH failed; the verified archive stays in $OUT_DIR" >&2; exit 1; }
  ssh -o BatchMode=yes -- "$RHOST" "cd '$RDIR' && sha256sum -c '$NAME.sha256'" >/dev/null || { echo "the copy at $COPY_SSH does not match its checksum" >&2; exit 1; }
fi
if [[ -n "$COPY_RCLONE" ]]; then
  command -v rclone >/dev/null || { echo "rclone is required for --copy-rclone" >&2; exit 1; }
  NAME="$(basename "$TARGET")"
  rclone copy -- "$TARGET" "$COPY_RCLONE" && rclone copy -- "$TARGET.sha256" "$COPY_RCLONE" || { echo "the copy to $COPY_RCLONE failed; the verified archive stays in $OUT_DIR" >&2; exit 1; }
  rclone check --one-way --include "$NAME" --include "$NAME.sha256" -- "$OUT_DIR" "$COPY_RCLONE" >/dev/null || { echo "the copy at $COPY_RCLONE does not match" >&2; exit 1; }
fi

# Rotation: only after this backup is verified (and copied), drop the oldest ones.
if [[ "$KEEP" -gt 0 ]]; then
  mapfile -t OLD < <(ls -1 "$OUT_DIR"/armor-data-*.tar.gz.enc 2>/dev/null | sort -r | tail -n +"$((KEEP + 1))")
  for f in "${OLD[@]}"; do [[ -n "$f" ]] && rm -f -- "$f" "$f.sha256"; done
fi
echo "ARMOR_BACKUP=PASS file=$TARGET entries=$COUNT media=$WITH_MEDIA volumes=${#VOLUMES[@]}"
