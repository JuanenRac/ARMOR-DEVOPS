#!/usr/bin/env bash
# =============================================================================
# A.R.M.O.R. - ARMOR-DEVOPS/scripts/generate_secrets.sh
# Creates .env (random secrets) and secrets/mqtt.password + secrets/mqtt.acl for
# docker compose. Refuses to overwrite anything that exists. Prints no secret.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D)
# GPL-3.0-or-later - see LICENSE
# =============================================================================
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

random() { head -c 96 /dev/urandom | base64 | tr -d '\n=+/' | head -c "$1"; }
[[ ! -e .env ]] || { echo "ERROR: .env already exists; move it aside first" >&2; exit 1; }
mkdir -p secrets
[[ ! -e secrets/mqtt.password && ! -e secrets/mqtt.acl ]] || { echo "ERROR: secrets/ already has broker files; move them aside first" >&2; exit 1; }

broker_password="$(random 32)"
umask 0177
cat >.env <<ENV
ARMOR_INGEST_TOKEN=$(random 43)
ARMOR_CONTROL_TOKEN=$(random 43)
ARMOR_OPERATOR_TOKEN=$(random 43)
ARMOR_CAMERA_CONFIG_KEY=$(random 64)
ARMOR_STUDIO_USERNAME=admin
ARMOR_STUDIO_PASSWORD=$(random 24)
ARMOR_MQTT_USERNAME=armor-server
ARMOR_MQTT_PASSWORD=${broker_password}
ARMOR_PUBLIC_ORIGIN=http://127.0.0.1:18081
ARMOR_COOKIE_SECURE=0
ENV

# Mosquitto's own tool hashes the password; run it in the broker image so nothing is installed here.
# The broker drops to its own unprivileged user inside the container, so it must be able to read these two files:
# they are world-readable on purpose (a salted hash and an access list, no plaintext secret; .env stays private).
docker run --rm --entrypoint sh -v "$PWD/secrets:/out" eclipse-mosquitto:2.0.21 \
  -c 'mosquitto_passwd -b -c /out/mqtt.password armor-server "$1" >/dev/null && chmod 0644 /out/mqtt.password' _ "${broker_password}"
# The access list is the example with the server's block taken from scripts/armor_server.acl, the one source of what the server may do (the installer uses the same file).
[[ -f scripts/armor_server.acl ]] || { echo "ERROR: scripts/armor_server.acl is missing" >&2; exit 1; }
awk -v rules="scripts/armor_server.acl" '
  $0 == "user armor-server" { print; while ((getline line < rules) > 0) if (line ~ /^(topic |#)/) print line; skip = 1; next }
  skip && /^$/ { skip = 0 }
  !skip { print }
' mosquitto/acl.example >secrets/mqtt.acl
chmod 0644 secrets/mqtt.acl 2>/dev/null || true

echo "ARMOR_SECRETS=CREATED .env, secrets/mqtt.password and secrets/mqtt.acl (all Git-ignored)"
echo "Add one broker user per field node (mosquitto_passwd) and one block per node in secrets/mqtt.acl."
echo "The Studio login is user 'admin'; its password is ARMOR_STUDIO_PASSWORD in .env."
