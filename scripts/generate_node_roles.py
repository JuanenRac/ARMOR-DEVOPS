#!/usr/bin/env python3
# ARMOR-DEVOPS - writes into mqtt_identity.sh the user name and the access lines of every kind of identity from scripts/node_roles.json (the copy of the table of ARMOR-COMMON).
# `--check` fails when the script is not what the table makes. Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BEGIN = "# BEGIN GENERATED FROM scripts/node_roles.json (python3 scripts/generate_node_roles.py): the user name and the access lines of each kind of identity."
END = "# END GENERATED"


def shell_text(template: str) -> str:
    return template.replace("{name}", "$NAME")


def generated() -> str:
    roles = json.loads((HERE / "node_roles.json").read_text(encoding="utf-8"))["roles"]
    out = ["role_user() {", '  local NAME="$2"', '  case "$1" in']
    for role, entry in roles.items():
        out.append(f'    {role}) echo "{shell_text(entry["user"])}" ;;')
    out += ["    *) return 1 ;;", "  esac", "}", "role_lines() {", '  local NAME="$2"', '  case "$1" in']
    for role, entry in roles.items():
        out.append(f"    {role})")
        out += [f'      echo "{shell_text(line)}"' for line in entry["topics"]]
        if entry.get("relaxed_extra"):
            # the old wide line, only when the strict mode is turned off on purpose (it also covers the maintenance command topic)
            out.append('      if [[ "${ARMOR_ACL_STRICT_MAINTENANCE_COMMAND:-1}" == "0" ]]; then')
            out += [f'        echo "{shell_text(line)}"' for line in entry["relaxed_extra"]]
            out.append("      fi")
        out.append("      ;;")
    out += ["  esac", "}"]
    return "\n".join(out)


def rewrite(text: str) -> str:
    head, rest = text.split(BEGIN + "\n", 1)
    _, tail = rest.split(END, 1)
    return head + BEGIN + "\n" + generated() + "\n" + END + tail


def main() -> int:
    path = HERE / "mqtt_identity.sh"
    current = path.read_text(encoding="utf-8")
    new = rewrite(current)
    if "--check" in sys.argv:
        if new != current:
            print("mqtt_identity.sh is not what scripts/node_roles.json makes: run python3 scripts/generate_node_roles.py", file=sys.stderr)
            return 1
        return 0
    path.write_text(new, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
