#!/usr/bin/env bash
# ARMOR-DEVOPS - tests of check-required-env.sh (the deployment settings are complete and not weak), of what generate_secrets.sh refuses to overwrite, and of the edges of
# backup_data.sh / restore_data.sh that test_backup.sh does not reach (short passphrase, media, unsafe archives, a dry run that changes nothing).
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
# Everything runs on copies of the scripts inside a temporary folder; Docker is never used (generate_secrets.sh is only run where it stops before it).
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf -- "$WORK"' EXIT
FAILED=0
CHECKS=0

ok() { CHECKS=$((CHECKS + 1)); }
bad() { echo "FAIL: $*" >&2; FAILED=$((FAILED + 1)); }
# expect STATUS "text" COMMAND... (stdout and stderr together)
expect() {
  local want_status="$1" want_text="$2"; shift 2
  local out status
  out="$("$@" 2>&1)"; status=$?
  ok
  if [[ "$status" -ne "$want_status" ]]; then bad "exit $status, wanted $want_status: $* -> $(tail -1 <<<"$out")"; return; fi
  grep -qF -- "$want_text" <<<"$out" || bad "missing \"$want_text\": $* -> $(tail -1 <<<"$out")"
}

token() { head -c "$1" /dev/zero | tr '\0' 'a'; }

# ---------------------------------------------------------------- check-required-env.sh
project() {   # a folder that looks like the repository: scripts/ with a copy of the check, and a complete configuration
  local folder="$1"
  mkdir -p "$folder/scripts" "$folder/secrets"
  cp "$HERE/check-required-env.sh" "$folder/scripts/"
  : >"$folder/secrets/mqtt.password"; : >"$folder/secrets/mqtt.acl"
  cat >"$folder/.env" <<ENV
ARMOR_INGEST_TOKEN=$(token 30)i
ARMOR_CONTROL_TOKEN=$(token 30)c
ARMOR_OPERATOR_TOKEN=$(token 30)o
ARMOR_CAMERA_CONFIG_KEY=$(token 40)
ARMOR_STUDIO_PASSWORD=$(token 14)
ARMOR_MQTT_PASSWORD=$(token 30)
ENV
}
check() { bash "$1/scripts/check-required-env.sh"; }
set_value() { sed -i "s|^$2=.*|$2=$3|" "$1/.env"; }

P="$WORK/p1"; project "$P"
expect 0 "ARMOR_DEVOPS_ENV=PASS" check "$P"

P="$WORK/p2"; project "$P"; rm "$P/.env"
expect 2 ".env is missing" check "$P"

P="$WORK/p3"; project "$P"; set_value "$P" ARMOR_CONTROL_TOKEN "replace-with-a-long-random-value"
expect 2 "ARMOR_CONTROL_TOKEN is not set" check "$P"

P="$WORK/p4"; project "$P"; sed -i '/^ARMOR_CAMERA_CONFIG_KEY=/d' "$P/.env"
expect 2 "ARMOR_CAMERA_CONFIG_KEY is not set" check "$P"

P="$WORK/p5"; project "$P"; set_value "$P" ARMOR_INGEST_TOKEN "short"
expect 2 "ARMOR_INGEST_TOKEN is too short" check "$P"

P="$WORK/p6"; project "$P"; set_value "$P" ARMOR_STUDIO_PASSWORD "$(token 11)"
expect 2 "ARMOR_STUDIO_PASSWORD is too short" check "$P"
set_value "$P" ARMOR_STUDIO_PASSWORD "$(token 12)"
expect 0 "ARMOR_DEVOPS_ENV=PASS" check "$P"     # twelve is enough for the console password, twenty-four is needed for the rest

P="$WORK/p7"; project "$P"; set_value "$P" ARMOR_OPERATOR_TOKEN "$(token 30)i"
expect 2 "must all be different" check "$P"

P="$WORK/p8"; project "$P"; rm "$P/secrets/mqtt.acl"
expect 2 "secrets/mqtt.password and secrets/mqtt.acl are required" check "$P"

P="$WORK/p9"; project "$P"; set_value "$P" ARMOR_MQTT_PASSWORD ""
out="$(check "$P" 2>&1)"; ok
grep -q "ARMOR_MQTT_PASSWORD is not set" <<<"$out" || bad "an empty broker password was accepted"
# a problem is reported for every variable at once, and no value is ever printed
P="$WORK/p10"; project "$P"; set_value "$P" ARMOR_INGEST_TOKEN "weak"; set_value "$P" ARMOR_CONTROL_TOKEN "weak2"
out="$(check "$P" 2>&1)"; ok
[[ "$(grep -c "too short" <<<"$out")" -eq 2 ]] || bad "both short tokens should be named: $out"
ok; if grep -q "weak" <<<"$out"; then bad "a secret value was printed"; fi

# ---------------------------------------------------------------- generate_secrets.sh: it never overwrites (these stop before Docker is needed)
gen_project() {
  local folder="$1"
  mkdir -p "$folder/scripts" "$folder/mosquitto"
  cp "$HERE/generate_secrets.sh" "$folder/scripts/"
  echo "user x" >"$folder/mosquitto/acl.example"
}
P="$WORK/g1"; gen_project "$P"; echo "KEEP=1" >"$P/.env"
expect 1 ".env already exists" bash "$P/scripts/generate_secrets.sh"
ok; [[ "$(cat "$P/.env")" == "KEEP=1" ]] || bad ".env was modified"
ok; [[ ! -e "$P/secrets/mqtt.password" ]] || bad "a broker file was created next to an existing .env"

P="$WORK/g2"; gen_project "$P"; mkdir "$P/secrets"; echo "hash" >"$P/secrets/mqtt.password"
expect 1 "secrets/ already has broker files" bash "$P/scripts/generate_secrets.sh"
ok; [[ "$(cat "$P/secrets/mqtt.password")" == "hash" ]] || bad "the broker password file was modified"

P="$WORK/g3"; gen_project "$P"; mkdir "$P/secrets"; echo "user keep" >"$P/secrets/mqtt.acl"
expect 1 "secrets/ already has broker files" bash "$P/scripts/generate_secrets.sh"
ok; [[ "$(cat "$P/secrets/mqtt.acl")" == "user keep" ]] || bad "the access list was modified"

# ---------------------------------------------------------------- backup and restore edges
if command -v openssl >/dev/null && command -v sha256sum >/dev/null; then
  mkdir -p "$WORK/data/media/cam-01" "$WORK/data/sub"
  echo '{"schema":1}' >"$WORK/data/cameras.json"
  echo scratch >"$WORK/data/scratch.tmp"
  echo big >"$WORK/data/media/cam-01/a.jpg"
  echo deep >"$WORK/data/sub/deep.txt"
  printf 'a-long-enough-passphrase\n' >"$WORK/pass"
  printf 'short\n' >"$WORK/short"
  : >"$WORK/empty"

  expect 1 "the passphrase must be at least 12 characters" bash "$HERE/backup_data.sh" --data-dir "$WORK/data" --out-dir "$WORK/out-short" --passphrase-file "$WORK/short"
  expect 1 "the passphrase file is empty" bash "$HERE/backup_data.sh" --data-dir "$WORK/data" --out-dir "$WORK/out-empty" --passphrase-file "$WORK/empty"
  ok; ls "$WORK"/out-short/*.enc >/dev/null 2>&1 && bad "an archive was made with a short passphrase"
  expect 2 "unknown option: --bogus" bash "$HERE/backup_data.sh" --bogus
  expect 2 "Usage: backup_data.sh" bash "$HERE/backup_data.sh" --data-dir "$WORK/does-not-exist" --out-dir "$WORK/o" --passphrase-file "$WORK/pass"
  expect 0 "Usage: backup_data.sh" bash "$HERE/backup_data.sh" --help
  expect 2 "Usage: restore_data.sh" bash "$HERE/restore_data.sh" --file "$WORK/nothing.enc" --data-dir "$WORK/r" --passphrase-file "$WORK/pass"

  # temporary files and (by default) the media folder stay out; with --with-media the media goes in
  expect 0 "media=0" bash "$HERE/backup_data.sh" --data-dir "$WORK/data" --out-dir "$WORK/out" --passphrase-file "$WORK/pass"
  ARCHIVE="$(ls "$WORK"/out/*.enc)"
  LISTING="$(bash "$HERE/restore_data.sh" --file "$ARCHIVE" --data-dir "$WORK/r1" --passphrase-file "$WORK/pass" 2>&1)"
  ok; grep -q "deep.txt" <<<"$LISTING" || bad "a nested file is missing from the backup"
  ok; grep -q "scratch.tmp" <<<"$LISTING" && bad "a temporary file was backed up"
  ok; grep -q "ARMOR_RESTORE=DRY-RUN" <<<"$LISTING" || bad "without --apply the restore must say it is a dry run"
  ok; [[ ! -e "$WORK/r1" ]] || bad "a dry run created the data directory"
  ok; [[ "$(stat -c %a "$ARCHIVE")" == "600" ]] || bad "the archive is not private (mode $(stat -c %a "$ARCHIVE"))"
  sleep 1
  expect 0 "media=1" bash "$HERE/backup_data.sh" --data-dir "$WORK/data" --out-dir "$WORK/out" --passphrase-file "$WORK/pass" --with-media
  WITH_MEDIA="$(ls -t "$WORK"/out/*.enc | head -1)"
  MEDIA_LISTING="$(bash "$HERE/restore_data.sh" --file "$WITH_MEDIA" --data-dir "$WORK/r2" --passphrase-file "$WORK/pass" 2>&1)"
  ok; grep -q "a.jpg" <<<"$MEDIA_LISTING" || bad "--with-media did not include the media"

  # an archive that reaches outside its folder is never restored
  EVIL="$WORK/evil"; mkdir -p "$EVIL/pkg"; echo x >"$EVIL/pkg/ok.txt"; echo y >"$EVIL/outside.txt"
  tar -C "$EVIL/pkg" -czf "$WORK/evil.tgz" --transform 's|^|../|' ok.txt 2>/dev/null || tar -C "$EVIL/pkg" -czf "$WORK/evil.tgz" ok.txt
  if tar -tzf "$WORK/evil.tgz" | grep -q '^\.\./'; then
    openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -pass "file:$WORK/pass" -in "$WORK/evil.tgz" -out "$WORK/evil.enc"
    expect 1 "the archive holds unsafe paths" bash "$HERE/restore_data.sh" --file "$WORK/evil.enc" --data-dir "$WORK/r3" --passphrase-file "$WORK/pass" --apply
    ok; [[ ! -e "$WORK/r3" && ! -e "$WORK/ok.txt" ]] || bad "something from an unsafe archive was written"
  fi

  # a wrong checksum file is refused even when the passphrase is right
  echo "$(printf '0%.0s' {1..64})  $(basename "$ARCHIVE")" >"$ARCHIVE.sha256"
  expect 1 "does not match its checksum" bash "$HERE/restore_data.sh" --file "$ARCHIVE" --data-dir "$WORK/r4" --passphrase-file "$WORK/pass" --apply
else
  echo "note: openssl or sha256sum is not installed; the backup and restore edges were not checked"
fi

# ---------------------------------------------------------------- deploy_cm5.sh: only what it refuses before it builds or connects to anything
expect 2 "unknown option: --nonsense" bash "$HERE/deploy_cm5.sh" --nonsense
expect 2 "usage: deploy_cm5.sh" bash "$HERE/deploy_cm5.sh"
expect 2 "usage: deploy_cm5.sh" bash "$HERE/deploy_cm5.sh" --host 192.0.2.1
expect 2 "usage: deploy_cm5.sh" bash "$HERE/deploy_cm5.sh" --user someone --with-mqtt

echo "$CHECKS checks, $FAILED failures"
if [[ "$FAILED" -ne 0 ]]; then exit 1; fi
echo "ARMOR_DEVOPS_ENV_RESTORE=PASS"
