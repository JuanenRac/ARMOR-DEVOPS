#!/usr/bin/env bash
# ARMOR-DEVOPS — compose validation only; does not deploy services.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
set -euo pipefail
docker compose config --quiet
echo "ARMOR_DEVOPS_COMPOSE=PASS"
