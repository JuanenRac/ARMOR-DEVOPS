#!/usr/bin/env bash
# ARMOR-DEVOPS - restore an encrypted data backup made by backup_data.sh.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
#
# Without --apply it only lists what the archive holds. With --apply it restores
# into --data-dir; an existing, non-empty data directory is never overwritten or
# deleted: it is renamed to <dir>.before-restore-<time> first. Stop armor-server
# before restoring.
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: restore_data.sh --file ARCHIVE --data-dir DIR --passphrase-file FILE [--apply]
USAGE
}

FILE="" DATA_DIR="" PASS_FILE="" APPLY=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --file) FILE="${2:-}"; shift 2 ;;
    --data-dir) DATA_DIR="${2:-}"; shift 2 ;;
    --passphrase-file) PASS_FILE="${2:-}"; shift 2 ;;
    --apply) APPLY=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done
[[ -f "$FILE" && -n "$DATA_DIR" && -f "$PASS_FILE" ]] || { usage >&2; exit 2; }
command -v openssl >/dev/null || { echo "openssl is required" >&2; exit 1; }
# A native Windows openssl (Git Bash) does not translate the path inside "file:"; give it a Windows path.
PASS_PATH="$PASS_FILE"; if command -v cygpath >/dev/null 2>&1; then PASS_PATH="$(cygpath -m "$PASS_FILE")"; fi

if [[ -f "$FILE.sha256" ]]; then
  ( cd "$(dirname "$FILE")" && sha256sum -c "$(basename "$FILE").sha256" >/dev/null ) || { echo "the archive does not match its checksum" >&2; exit 1; }
fi

decrypt() { openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass "file:$PASS_PATH" -in "$FILE"; }
LISTING="$(decrypt | tar -tzf -)" || { echo "wrong passphrase or damaged archive" >&2; exit 1; }
if [[ "$APPLY" -ne 1 ]]; then
  echo "$LISTING"
  echo "ARMOR_RESTORE=DRY-RUN entries=$(echo "$LISTING" | wc -l)"
  exit 0
fi

# An archive never contains absolute paths or parent references; refuse one that does.
if echo "$LISTING" | grep -qE '(^/|(^|/)\.\.(/|$))'; then echo "the archive holds unsafe paths" >&2; exit 1; fi

PARENT="$(cd "$(dirname "$DATA_DIR")" && pwd)"
BASE="$(basename "$DATA_DIR")"
ARCHIVE_BASE="$(echo "$LISTING" | head -n1 | cut -d/ -f1)"
if [[ -d "$DATA_DIR" && -n "$(ls -A "$DATA_DIR" 2>/dev/null)" ]]; then
  MOVED="$PARENT/$BASE.before-restore-$(date -u +%Y%m%dT%H%M%SZ)"
  mv -- "$DATA_DIR" "$MOVED"
  echo "the previous data directory was kept at $MOVED"
fi
TMP="$(mktemp -d "$PARENT/.armor-restore.XXXXXX")"
trap 'rm -rf -- "$TMP"' EXIT
decrypt | tar -xzf - -C "$TMP"
mkdir -p "$DATA_DIR"
cp -a "$TMP/$ARCHIVE_BASE/." "$DATA_DIR/"
echo "ARMOR_RESTORE=PASS data-dir=$DATA_DIR"
