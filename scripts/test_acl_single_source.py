#!/usr/bin/env python3
# =============================================================================
# A.R.M.O.R. - ARMOR-DEVOPS/scripts/test_acl_single_source.py
# The rules of the server in the broker's access list have ONE source, scripts/armor_server.acl. This test checks that every place that carries them agrees with it and that it
# agrees with what ARMOR-SERVER really publishes and listens to (when the repository of the server is next to this one).
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D)
# GPL-3.0-or-later - see LICENSE
# =============================================================================
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "scripts" / "armor_server.acl"
SERVER_SRC = ROOT.parent / "ARMOR-SERVER" / "src"

# Lines the server only gets on purpose, each one with the command of mqtt_identity.sh that writes it (all off by default).
OPT_IN = {
    "armor/alarm/+/command": "alarm-commands",
    "armor/electrical/+/command": "electrical-switching",
    "armor/solar/+/maintenance/command": "battery-write",
    "armor/alarm/+/state": "alarm-state-relay",
    "homeassistant/#": "ha-discovery",
}


def rules() -> list[tuple[str, str]]:
    found = []
    for line in SOURCE.read_text(encoding="utf-8").splitlines():
        if line.startswith("topic "):
            _, access, topic = line.split(" ", 2)
            found.append((access, topic))
    return found


def matches(rule: str, topic: str) -> bool:
    """MQTT filter `rule` against a topic that may itself contain `+` for a part that is not fixed."""
    a, b = rule.split("/"), topic.split("/")
    for index, part in enumerate(a):
        if part == "#":
            return True
        if index >= len(b):
            return False
        if part != "+" and part != b[index] and b[index] != "+":
            return False
    return len(a) == len(b)


def server_topics() -> tuple[set[str], set[str]]:
    """(topics the server subscribes to, topics it publishes), read from its source."""
    read: set[str] = set()
    write: set[str] = set()
    literal = re.compile(r"[`\"'](armor/[A-Za-z0-9_/+#${}.\->]*|homeassistant[A-Za-z0-9_/+#${}.\->]*)[`\"']")
    for path in sorted(SERVER_SRC.glob("*.ts")):
        for line in path.read_text(encoding="utf-8").splitlines():
            for found in literal.findall(line):
                topic = re.sub(r"\$\{[^}]*\}", "+", found)
                if path.name == "ha_discovery.ts" and topic.startswith("armor/"):  # the topics Home Assistant reads, written inside the discovery messages, not published by the server
                    continue
                if "subscribe" in line:
                    read.add(topic)
                elif "publish" in line or path.name in ("ha_discovery.ts", "notify.ts"):
                    write.add(topic)
    return read, write


class ServerRules(unittest.TestCase):
    def test_the_example_carries_the_same_block(self) -> None:
        text = (ROOT / "mosquitto" / "acl.example").read_text(encoding="utf-8")
        block = re.search(r"^user armor-server\n(.*?)\n\n", text, re.M | re.S)
        self.assertIsNotNone(block)
        lines = [line for line in block.group(1).splitlines() if line.startswith("topic ")]  # type: ignore[union-attr]
        self.assertEqual(lines, [f"topic {access} {topic}" for access, topic in rules()], "mosquitto/acl.example differs from scripts/armor_server.acl")

    def test_nothing_else_writes_the_servers_lines(self) -> None:
        installer = (ROOT / "scripts" / "install_cm5.sh").read_text(encoding="utf-8")
        copies = [line for line in installer.splitlines() if re.match(r"\s*topic (read|write|readwrite) armor/(alarm|control|solar|electrical|health|radar|network)/", line)]
        self.assertEqual(copies, [], "install_cm5.sh carries its own copy of the server's rules")

    def test_the_generated_list_uses_the_source(self) -> None:
        awk = shutil.which("awk")
        if awk is None:
            self.skipTest("no awk on this machine")
        script = (ROOT / "scripts" / "generate_secrets.sh").read_text(encoding="utf-8")
        program = re.search(r"awk -v rules=\"scripts/armor_server.acl\" '(.*?)' mosquitto/acl.example", script, re.S)
        self.assertIsNotNone(program)
        with tempfile.TemporaryDirectory() as work:
            example = Path(work) / "acl.example"
            example.write_text("user a\ntopic read x\n\nuser armor-server\ntopic read stale/line\n# old\n\nuser b\ntopic read y\n", encoding="utf-8", newline="\n")
            done = subprocess.run([awk, "-v", f"rules={SOURCE.as_posix()}", program.group(1), str(example)], capture_output=True, text=True, check=False)  # type: ignore[union-attr]
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertNotIn("stale/line", done.stdout)
        self.assertIn("user a\ntopic read x\n\nuser armor-server\n", done.stdout)
        self.assertTrue(done.stdout.endswith("\nuser b\ntopic read y\n"))
        for access, topic in rules():
            self.assertIn(f"topic {access} {topic}\n", done.stdout)

    def test_each_opt_in_line_has_its_command_and_is_not_by_default(self) -> None:
        script = (ROOT / "scripts" / "mqtt_identity.sh").read_text(encoding="utf-8")
        for topic, command in OPT_IN.items():
            self.assertFalse(any(matches(topic, t) and a != "read" for a, t in rules() if t != "armor/device/#"), f"{topic} is open by default")
            self.assertTrue(re.search(rf"^  {re.escape(command)}\)", script, re.M), f"mqtt_identity.sh has no `{command}`")

    @unittest.skipUnless(SERVER_SRC.is_dir(), "ARMOR-SERVER is not next to this repository")
    def test_it_covers_what_the_server_does(self) -> None:
        read, write = server_topics()
        self.assertGreater(len(read) + len(write), 10, "the topics could not be read from the server")
        can_read = [topic for access, topic in rules() if access in ("read", "readwrite")]
        can_write = [topic for access, topic in rules() if access in ("write", "readwrite")]
        for topic in sorted(read):
            self.assertTrue(any(matches(rule, topic) for rule in can_read), f"the server listens to {topic} and no rule lets it")
        for topic in sorted(write):
            if any(matches(opt, topic) for opt in OPT_IN):
                continue
            self.assertTrue(any(matches(rule, topic) for rule in can_write), f"the server publishes {topic} and no rule lets it")

    @unittest.skipUnless(SERVER_SRC.is_dir(), "ARMOR-SERVER is not next to this repository")
    def test_it_grants_nothing_the_server_does_not_use(self) -> None:
        read, write = server_topics()
        for access, topic in rules():
            if topic == "armor/device/#":                                  # the devices' topics are built from a configurable base, not from a literal
                continue
            if access in ("read", "readwrite"):
                self.assertTrue(any(matches(topic, used) for used in read), f"`{access} {topic}` is not used by the server")
            if access in ("write", "readwrite"):
                self.assertTrue(any(matches(topic, used) for used in write), f"`{access} {topic}` is not used by the server")


if __name__ == "__main__":
    unittest.main()
