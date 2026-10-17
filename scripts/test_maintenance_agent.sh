#!/usr/bin/env bash
# ARMOR-DEVOPS - runs the tests of the maintenance helper and of the packager (scripts/test_maintenance_agent.py, scripts/test_package_component.py). Needs Python 3 and Unix sockets (Linux, macOS, WSL).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"
python3 -W ignore -m unittest test_maintenance_agent test_package_component "$@"
