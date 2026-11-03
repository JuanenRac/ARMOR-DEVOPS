#!/usr/bin/env python3
# ARMOR-DEVOPS - the ports of the installer, the firewall, the Docker stack and the doctor are the ones of the registry of ports (ARMOR-COMMON/src/armor_common/ports.json).
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
COPY = json.loads((HERE / "ports.json").read_text(encoding="utf-8"))
PORTS = {name: entry["port"] for name, entry in COPY["ports"].items()}
COMMON = HERE.parents[1] / "ARMOR-COMMON" / "src" / "armor_common" / "ports.json"


def shell_default(file: str, name: str) -> int:
    match = re.search(rf'^\s*{name}="?(\d+)"?', (HERE / file).read_text(encoding="utf-8"), flags=re.M)
    assert match, f"{file} has no default for {name}"
    return int(match.group(1))


class PortsTests(unittest.TestCase):
    @unittest.skipUnless(COMMON.is_file(), "ARMOR-COMMON is not next to this repository")
    def test_the_copy_of_the_registry_is_the_one_of_common(self):
        self.assertEqual(COPY, json.loads(COMMON.read_text(encoding="utf-8")), "copy ARMOR-COMMON/src/armor_common/ports.json to scripts/ports.json")

    def test_the_installer_and_the_firewall_default_to_the_registered_ports(self):
        self.assertEqual(shell_default("install_cm5.sh", "SERVER_PORT"), PORTS["server"])
        self.assertEqual(shell_default("install_cm5.sh", "STUDIO_PORT"), PORTS["studio"])
        self.assertEqual(shell_default("install_cm5.sh", "MQTT_PORT"), PORTS["mqtt"])
        self.assertEqual(shell_default("install_cm5.sh", "VOICE_PORT"), PORTS["voice"])
        text = (HERE / "firewall_core.sh").read_text(encoding="utf-8")
        self.assertIn(f'MQTT_PORT="{PORTS["mqtt"]}"; SERVER_PORT="{PORTS["server"]}"; STUDIO_PORT="{PORTS["studio"]}"', text)

    def test_the_docker_stack_uses_the_same_numbering(self):
        compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        self.assertIn(f"ARMOR_PORT: {PORTS['server']}\n", compose)
        self.assertIn(f"mqtt://broker:{PORTS['mqtt']}", compose)
        self.assertIn(f"server:{PORTS['server']}", compose)
        self.assertIn(f":{PORTS['mqtt']}:{PORTS['mqtt']}\"]", compose)
        self.assertIn(f":{PORTS['studio']}:80\"]", compose)
        self.assertIn(f"${{ARMOR_TLS_PORT:-{PORTS['https']}}}", compose)
        self.assertIn(f"${{ARMOR_TLS_HTTP_PORT:-{PORTS['acme_http']}}}", compose)
        self.assertRegex((ROOT / "mosquitto" / "mosquitto.conf").read_text(encoding="utf-8"), rf"(?m)^listener {PORTS['mqtt']}$")
        tls = (ROOT / "mosquitto" / "mosquitto-tls.conf").read_text(encoding="utf-8")
        self.assertRegex(tls, rf"(?m)^listener {PORTS['mqtt']}$")
        self.assertRegex(tls, rf"(?m)^listener {PORTS['mqtt_tls']}$")
        self.assertIn(f"{PORTS['mqtt_tls']}:{PORTS['mqtt_tls']}", (ROOT / "docker-compose.tls.yml").read_text(encoding="utf-8"))
        env = (ROOT / ".env.example").read_text(encoding="utf-8")
        self.assertIn(f"ARMOR_PUBLIC_ORIGIN=http://127.0.0.1:{PORTS['studio']}", env)
        self.assertIn(f"ARMOR_TLS_PORT={PORTS['https']}", env)
        self.assertIn(f"ARMOR_TLS_HTTP_PORT={PORTS['acme_http']}", env)
        self.assertIn(f"http://127.0.0.1:{PORTS['studio']}", (HERE / "generate_secrets.sh").read_text(encoding="utf-8"))

    def test_no_file_of_the_stack_uses_an_old_number(self):
        legacy = [n for entry in COPY["ports"].values() for n in entry.get("legacy", [])]
        pattern = re.compile(r"(?<![\w.])(" + "|".join(map(str, legacy)) + r")(?!\w)")
        skip = ("test_", "ports.json", "armor_doctor.py", "architecture.json", "CHANGELOG", "README", "images/")
        for name in ("docker-compose.yml", "docker-compose.tls.yml", ".env.example", "mosquitto/mosquitto.conf", "mosquitto/mosquitto-tls.conf", "caddy/Caddyfile",
                     "scripts/generate_secrets.sh", "scripts/firewall_core.sh", "docs/BACKUP_AND_TLS.md", "docs/CM5_TEST_BENCH.md"):
            path = ROOT / name
            if path.is_file() and not any(word in name for word in skip):
                for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                    if pattern.search(line) and "old numbering" not in line and "used " not in line:
                        self.fail(f"{name}:{number} still uses an old port")

    def test_the_doctor_knows_the_old_numbers_of_the_registry(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("armor_doctor", HERE / "armor_doctor.py")
        doctor = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(doctor)
        expected = {int(old): (name, entry["port"]) for name, entry in COPY["ports"].items() for old in entry.get("legacy", [])}
        self.assertEqual(doctor.old_port_map(), expected)
        self.assertEqual(set(expected), {8080, 8088, 1883})


if __name__ == "__main__":
    unittest.main()
