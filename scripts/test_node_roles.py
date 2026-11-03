#!/usr/bin/env python3
# ARMOR-DEVOPS - what mqtt_identity.sh writes for each kind of identity is the table of ARMOR-COMMON (src/armor_common/node_roles.json), kept here as scripts/node_roles.json.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
COPY = json.loads((HERE / "node_roles.json").read_text(encoding="utf-8"))
COMMON = HERE.parents[1] / "ARMOR-COMMON" / "src" / "armor_common" / "node_roles.json"
BASH = os.environ.get("ARMOR_BASH") or shutil.which("bash")
if BASH and "system32" in BASH.lower():  # the bash of the Windows subsystem for Linux cannot use these paths
    BASH = None


def block(acl: str, user: str) -> list[str]:
    lines = acl.splitlines()
    start = lines.index(f"user {user}")
    out = []
    for line in lines[start + 1:]:
        if not line.strip():
            break
        out.append(line)
    return out


class NodeRolesTests(unittest.TestCase):
    @unittest.skipUnless(COMMON.is_file(), "ARMOR-COMMON is not next to this repository")
    def test_the_copy_of_the_table_is_the_one_of_common(self):
        self.assertEqual(COPY, json.loads(COMMON.read_text(encoding="utf-8")), "copy ARMOR-COMMON/src/armor_common/node_roles.json to scripts/node_roles.json")

    @unittest.skipUnless(BASH, "no bash on this machine")
    def test_the_script_writes_what_the_table_says_for_every_role(self):
        for role, entry in COPY["roles"].items():
            with self.subTest(role=role), tempfile.TemporaryDirectory() as work:
                work_path = Path(work)
                (work_path / "bin").mkdir()
                (work_path / "prefix" / "etc" / "mosquitto").mkdir(parents=True)
                for name, body in (("id", '#!/bin/sh\nif [ "$1" = "-u" ]; then echo 0; else /usr/bin/id "$@"; fi\n'), ("mosquitto_passwd", "#!/bin/sh\nexit 0\n"), ("systemctl", "#!/bin/sh\nexit 0\n"), ("chown", "#!/bin/sh\nexit 0\n")):
                    (work_path / "bin" / name).write_text(body, encoding="utf-8", newline="\n")
                    (work_path / "bin" / name).chmod(0o755)
                mq = work_path / "prefix" / "etc" / "mosquitto"
                (mq / "passwd").write_text("", encoding="utf-8")
                (mq / "acl").write_text("# Managed by scripts/mqtt_identity.sh; one block per identity.\nuser armor-server\ntopic read armor/node/+/telemetry\n", encoding="utf-8", newline="\n")
                env = dict(os.environ, PATH=f"{work_path / 'bin'}{os.pathsep}{os.environ['PATH']}", ARMOR_PREFIX=str(work_path / "prefix"))
                done = subprocess.run([BASH, str(HERE / "mqtt_identity.sh"), "add", role, "tbl-1"], env=env, capture_output=True, text=True, check=False)
                self.assertEqual(done.returncode, 0, done.stderr)
                user = entry["user"].replace("{name}", "tbl-1")
                self.assertEqual(block((mq / "acl").read_text(encoding="utf-8"), user), [line.replace("{name}", "tbl-1") for line in entry["topics"]])

    def test_the_script_is_what_the_table_generates(self):
        done = subprocess.run([sys.executable, str(HERE / "generate_node_roles.py"), "--check"], capture_output=True, text=True, check=False)
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_the_commented_examples_of_the_acl_example_follow_the_table(self):
        example = (HERE.parent / "mosquitto" / "acl.example").read_text(encoding="utf-8").splitlines()
        for role, name in (("solar-node", "solar-1"), ("electrical-node", "electrical-1"), ("alarm-node", "alarm-1"), ("network-node", "network-1")):
            user = COPY["roles"][role]["user"].replace("{name}", name)
            start = example.index(f"# user {user}")
            found = []
            for line in example[start + 1:]:
                if not line.startswith("# topic "):
                    break
                found.append(line[2:])
            wanted = [t.replace("{name}", name) for t in COPY["roles"][role]["topics"]]
            self.assertEqual(sorted(set(found) - set(wanted)), [], f"the example of {role} has a line the table does not")
            self.assertTrue(all(t in found for t in wanted if " write " in t), f"the example of {role} lacks a write line of the table")

    def test_the_script_has_no_role_the_table_lacks(self):
        script = (HERE / "mqtt_identity.sh").read_text(encoding="utf-8")
        for role in ("node", "solar-node", "electrical-node", "network-node", "alarm-node", "hmi-node", "consumer", "device", "bridge"):
            self.assertIn(role, COPY["roles"])
            self.assertIn(f"    {role})", script)


if __name__ == "__main__":
    unittest.main()
