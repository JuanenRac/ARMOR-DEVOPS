#!/usr/bin/env bash
# ARMOR-DEVOPS - build and start the real Compose topology from clean copies of the repositories,
# test it (broker, server, Studio behind nginx, and the optional TLS profile) and tear it down.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
#
# Needs Docker with the compose plugin and Internet access (it pulls and builds images). Run it on
# Linux or inside WSL; nothing is written to the repositories, and everything it starts is removed.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
W="$(mktemp -d)"
DOCKER="docker"; docker info >/dev/null 2>&1 || DOCKER="sudo docker"
FAILED=0
check() { if [[ "$2" == "$3" ]]; then echo "PASS $1"; else echo "FAIL $1 (got '$2', wanted '$3')"; FAILED=1; fi; }
cleanup() { ( cd "$W/ARMOR-DEVOPS" 2>/dev/null && $DOCKER compose --profile tls down -v >/dev/null 2>&1 ); $DOCKER run --rm -v "$W:/w" --entrypoint sh eclipse-mosquitto:2 -c 'rm -rf /w/* /w/.[!.]*' >/dev/null 2>&1; rm -rf -- "$W"; }
trap cleanup EXIT

for repo in ARMOR-SERVER ARMOR-STUDIO ARMOR-DEVOPS; do
  mkdir -p "$W/$repo"
  tar -C "$ROOT/$repo" --exclude=node_modules --exclude=dist --exclude=data --exclude=.env --exclude=.git --exclude=build --exclude=secrets -cf - . | tar -C "$W/$repo" -xf -
done
find "$W" -name '*.sh' -exec sed -i 's/\r$//' {} +
cd "$W/ARMOR-DEVOPS"
[[ "$DOCKER" == "docker" ]] || sed -i 's/^docker run/sudo docker run/' scripts/generate_secrets.sh

bash scripts/generate_secrets.sh >/dev/null 2>&1; check "secrets generated" "$?" "0"
out="$(bash scripts/check-required-env.sh 2>&1 | tail -1)"; check "environment accepted" "$out" "ARMOR_DEVOPS_ENV=PASS"
$DOCKER compose config --quiet; check "compose config" "$?" "0"
$DOCKER compose --profile tls config --quiet; check "compose config (tls profile)" "$?" "0"
$DOCKER compose up -d --build >/dev/null 2>&1; check "compose up" "$?" "0"

wait_for() { for _ in $(seq 1 40); do [[ "$(curl -s -m 5 -o /dev/null -w '%{http_code}' "$1")" == "200" ]] && return 0; sleep 2; done; return 1; }
wait_for http://127.0.0.1:8088/ ; check "studio answers" "$?" "0"
info="$(curl -s -m 8 http://127.0.0.1:8088/api/v1/info)"
check "studio reaches the server" "$(echo "$info" | grep -c '"service":"armor-server"')" "1"
sleep 5
check "broker running" "$($DOCKER compose ps --format '{{.Service}} {{.State}}' | grep -c '^broker running')" "1"
check "server connected to the broker as armor-server" "$($DOCKER compose logs broker 2>&1 | grep -c "u'armor-server'")" "1"

$DOCKER compose --profile tls up -d >/dev/null 2>&1; check "tls profile up" "$?" "0"
wait_for_tls() { for _ in $(seq 1 30); do [[ "$(curl -sk -m 5 -o /dev/null -w '%{http_code}' https://localhost:8443/)" == "200" ]] && return 0; sleep 2; done; return 1; }
wait_for_tls; check "https answers" "$?" "0"
check "https reaches the server" "$(curl -sk -m 8 https://localhost:8443/api/v1/info | grep -c '"service":"armor-server"')" "1"

if [[ "$FAILED" -eq 0 ]]; then echo "ARMOR_COMPOSE_TEST=PASS"; else echo "ARMOR_COMPOSE_TEST=FAIL"; exit 1; fi
