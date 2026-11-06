#!/usr/bin/env python3
# =============================================================================
# A.R.M.O.R. - ARMOR-DEVOPS/scripts/test_acl_enforcement.py
# A client with a solar or field-node identity can publish its readings and its maintenance answers and cannot publish the order topic of the batteries; only the server can, and only
# after `battery-write ... on`. The access list is the one mqtt_identity.sh really writes (run with stand-ins for the broker's tools) and the broker is simulated with the rules of
# Mosquitto's access list: a topic is allowed when ANY line of the user's block of that kind matches it, `+` stands for one level and `#` for the rest.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D)
# GPL-3.0-or-later - see LICENSE
# =============================================================================
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASH = shutil.which("bash")


def topic_matches(pattern: str, topic: str) -> bool:
    """Mosquitto's rule for a filter against the topic of a message."""
    a, b = pattern.split("/"), topic.split("/")
    for index, part in enumerate(a):
        if part == "#":
            return True
        if index >= len(b):
            return False
        if part != "+" and part != b[index]:
            return False
    return len(a) == len(b)


class Broker:
    """The access list of a Mosquitto broker: user blocks of `topic [read|write|readwrite] filter` lines."""

    def __init__(self, text: str) -> None:
        self.blocks: dict[str, list[tuple[str, str]]] = {}
        user = None
        for line in text.splitlines():
            if line.startswith("user "):
                user = line[5:].strip()
                self.blocks[user] = []
            elif line.startswith("topic ") and user is not None:
                _, mode, filter_ = line.split(" ", 2)
                self.blocks[user].append((mode, filter_))

    def may(self, user: str, verb: str, topic: str) -> bool:
        return any(mode in (verb, "readwrite") and topic_matches(filter_, topic) for mode, filter_ in self.blocks.get(user, []))


@unittest.skipIf(BASH is None, "bash is needed to run mqtt_identity.sh")
class MaintenanceCommandIsTheServers(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.work = Path(tempfile.mkdtemp())
        bin_dir = cls.work / "bin"
        etc = cls.work / "prefix" / "etc" / "mosquitto"
        bin_dir.mkdir()
        etc.mkdir(parents=True)
        stand_ins = {
            "id": '#!/bin/sh\nif [ "$1" = "-u" ]; then echo 0; else /usr/bin/id "$@"; fi\n',
            "mosquitto_passwd": "#!/bin/sh\nexit 0\n",
            "systemctl": "#!/bin/sh\nexit 0\n",
            "chown": "#!/bin/sh\nexit 0\n",
        }
        for name, body in stand_ins.items():
            (bin_dir / name).write_text(body, encoding="utf-8", newline="\n")
            (bin_dir / name).chmod(0o755)
        (etc / "passwd").write_text("", encoding="utf-8")
        cls.acl = etc / "acl"
        lines = ["user armor-server"]
        for line in (HERE / "armor_server.acl").read_text(encoding="utf-8").splitlines():
            if line.startswith("topic "):
                lines.append(line)
        cls.acl.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        cls.env = dict(os.environ, PATH=f"{bin_dir.as_posix()}{os.pathsep}{os.environ['PATH']}", ARMOR_PREFIX=(cls.work / "prefix").as_posix())
        cls.env.pop("ARMOR_ACL_STRICT_MAINTENANCE_COMMAND", None)
        cls.identity("add", "solar-node", "sol-1")
        cls.identity("add", "node", "fld-1")
        cls.identity("battery-write", "sol-1", "on")

    @classmethod
    def identity(cls, *args: str) -> None:
        done = subprocess.run([BASH, (HERE / "mqtt_identity.sh").as_posix(), *args], env=cls.env, capture_output=True, text=True, check=False)
        if done.returncode != 0:
            raise RuntimeError(done.stderr)

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.work, ignore_errors=True)

    def broker(self) -> Broker:
        return Broker(self.acl.read_text(encoding="utf-8"))

    def test_a_solar_node_publishes_its_readings_and_its_answers_but_not_the_order(self) -> None:
        broker = self.broker()
        user = "solar-node-sol-1"
        self.assertTrue(broker.may(user, "write", "armor/solar/sol-1/inverter-1/state"))
        self.assertTrue(broker.may(user, "write", "armor/solar/sol-1/battery-3/state"))
        self.assertTrue(broker.may(user, "write", "armor/solar/sol-1/maintenance/result"))
        self.assertFalse(broker.may(user, "write", "armor/solar/sol-1/maintenance/command"))
        self.assertFalse(broker.may(user, "write", "armor/solar/sol-1/anything/command"))
        self.assertFalse(broker.may(user, "write", "armor/solar/other/inverter-1/state"))
        self.assertTrue(broker.may(user, "read", "armor/solar/sol-1/maintenance/command"), "it must still read the order the server sends")

    def test_a_field_node_cannot_publish_the_order_either(self) -> None:
        broker = self.broker()
        user = "field-node-fld-1"
        self.assertTrue(broker.may(user, "write", "armor/solar/fld-1/inverter-1/state"))
        self.assertTrue(broker.may(user, "write", "armor/solar/fld-1/maintenance/result"))
        self.assertFalse(broker.may(user, "write", "armor/solar/fld-1/maintenance/command"))
        self.assertFalse(broker.may(user, "read", "armor/solar/fld-1/maintenance/command"))

    def test_the_server_publishes_the_order_and_reads_the_readings(self) -> None:
        broker = self.broker()
        self.assertTrue(broker.may("armor-server", "write", "armor/solar/sol-1/maintenance/command"))
        self.assertTrue(broker.may("armor-server", "read", "armor/solar/sol-1/inverter-1/state"))
        self.assertTrue(broker.may("armor-server", "read", "armor/solar/sol-1/maintenance/result"))
        self.assertFalse(broker.may("armor-server", "write", "armor/solar/fld-1/maintenance/command"), "only the node that was turned on")

    def test_no_node_identity_can_publish_a_command_topic(self) -> None:
        broker = self.broker()
        for user in ("solar-node-sol-1", "field-node-fld-1"):
            for topic in ("armor/solar/sol-1/maintenance/command", "armor/solar/fld-1/maintenance/command", "armor/electrical/e-1/command", "armor/alarm/a-1/command"):
                self.assertFalse(broker.may(user, "write", topic), f"{user} {topic}")


class MatcherTests(unittest.TestCase):
    def test_the_rules_of_a_broker(self) -> None:
        self.assertTrue(topic_matches("armor/solar/x/+/state", "armor/solar/x/inv/state"))
        self.assertFalse(topic_matches("armor/solar/x/+/state", "armor/solar/x/maintenance/command"))
        self.assertTrue(topic_matches("armor/solar/x/#", "armor/solar/x/maintenance/command"))
        self.assertFalse(topic_matches("armor/solar/x/maintenance/result", "armor/solar/x/maintenance/result/extra"))


if __name__ == "__main__":
    unittest.main()
