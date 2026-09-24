#!/usr/bin/env bash
# ARMOR-DEVOPS - encrypted backup of the server data directory (camera vault,
# evidence index, state, rules, event history, audit log).
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
#
# The archive is encrypted with AES-256 (PBKDF2) using a passphrase read from a
# file, and is verified by decrypting it again before the script reports success.
# It never includes the environment file: the camera key (ARMOR_CAMERA_CONFIG_KEY)
# must be kept somewhere else, because the vault is unreadable without it.
# Recorded media can be large; by default only files up to --max-media-mb are kept
# out of the archive (evidence is excluded unless --with-media is given).
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: backup_data.sh --data-dir DIR --out-dir DIR --passphrase-file FILE [--with-media]

  --data-dir         the server data directory (ARMOR_DATA_DIR)
  --out-dir          where the .tar.gz.enc archive and its .sha256 are written
  --passphrase-file  a file whose first line is the passphrase (mode 600)
  --with-media       also include recorded evidence (can be very large)
USAGE
}

DATA_DIR="" OUT_DIR="" PASS_FILE="" WITH_MEDIA=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --data-dir) DATA_DIR="${2:-}"; shift 2 ;;
    --out-dir) OUT_DIR="${2:-}"; shift 2 ;;
    --passphrase-file) PASS_FILE="${2:-}"; shift 2 ;;
    --with-media) WITH_MEDIA=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done
[[ -d "$DATA_DIR" && -n "$OUT_DIR" && -f "$PASS_FILE" ]] || { usage >&2; exit 2; }
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
tar -C "$PARENT" -czf - "${EXCLUDES[@]}" "$BASE" | openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -pass "file:$PASS_PATH" -out "$TARGET"

# Verify: it must decrypt and list at least the directory itself.
COUNT="$(openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass "file:$PASS_PATH" -in "$TARGET" | tar -tzf - | wc -l)"
if [[ "$COUNT" -lt 1 ]]; then rm -f -- "$TARGET"; echo "verification failed: the archive is empty" >&2; exit 1; fi
( cd "$OUT_DIR" && sha256sum "$(basename "$TARGET")" >"$(basename "$TARGET").sha256" )
echo "ARMOR_BACKUP=PASS file=$TARGET entries=$COUNT media=$WITH_MEDIA"
