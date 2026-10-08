#!/usr/bin/env bash
# ARMOR-DEVOPS - runs the tests of the admin agent (scripts/test_admin_agent.py). Needs Python 3 and Unix sockets (Linux, macOS, WSL).
set -euo pipefail
exec python3 "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/test_admin_agent.py" "$@"
