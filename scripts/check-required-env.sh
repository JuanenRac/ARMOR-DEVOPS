#!/usr/bin/env bash
# ARMOR-DEVOPS - validate the deployment variables in .env without printing a secret.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
[[ -f .env ]] || { echo "ERROR: .env is missing; run scripts/generate_secrets.sh" >&2; exit 2; }

read_value() { grep -E "^$1=" .env | head -1 | cut -d= -f2-; }
status=0
for variable in ARMOR_INGEST_TOKEN ARMOR_CONTROL_TOKEN ARMOR_OPERATOR_TOKEN ARMOR_CAMERA_CONFIG_KEY ARMOR_STUDIO_PASSWORD ARMOR_MQTT_PASSWORD; do
  value="$(read_value "$variable")"
  if [[ -z "$value" || "$value" == replace-with-* ]]; then
    echo "ERROR: $variable is not set" >&2; status=2
  elif [[ "$variable" == ARMOR_STUDIO_PASSWORD && ${#value} -lt 12 ]] || [[ "$variable" != ARMOR_STUDIO_PASSWORD && ${#value} -lt 24 ]]; then
    echo "ERROR: $variable is too short" >&2; status=2
  fi
done
# The three tokens must all differ: one leaked credential must not open every door.
tokens="$(for v in ARMOR_INGEST_TOKEN ARMOR_CONTROL_TOKEN ARMOR_OPERATOR_TOKEN; do read_value "$v"; done | sort | uniq -d)"
[[ -z "$tokens" ]] || { echo "ERROR: the ingest, control and operator tokens must all be different" >&2; status=2; }
[[ -f secrets/mqtt.password && -f secrets/mqtt.acl ]] || { echo "ERROR: secrets/mqtt.password and secrets/mqtt.acl are required" >&2; status=2; }
[[ $status -eq 0 ]] && echo "ARMOR_DEVOPS_ENV=PASS"
exit $status
