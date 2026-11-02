#!/usr/bin/env python3
# ARMOR-DEVOPS - the virtual bench of docker-compose.yml: an optional profile with simulated nodes that can reach only the server and never publishes a port.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
ENV_EXAMPLE = (ROOT / ".env.example").read_text(encoding="utf-8")
SIMULATOR = ROOT.parent / "ARMOR-SIMULATOR"


def block(name: str) -> str:
    """The text of one service of the compose file (from its header to the next service or section)."""
    match = re.search(rf"^  {name}:\n(.*?)(?=^  [a-z#]|^[a-z]|\Z)", COMPOSE, re.S | re.M)
    assert match, f"no service {name}"
    return match.group(1)


class BenchProfileTests(unittest.TestCase):
    def test_it_is_an_optional_profile_so_a_plain_up_does_not_start_it(self):
        self.assertIn("profiles: [bench]", block("simulator"))

    def test_it_is_as_hardened_as_the_other_services(self):
        self.assertIn("<<: *hardened", block("simulator"))
        self.assertIn('user: "10001:10001"', block("simulator"))

    def test_it_publishes_no_port_and_reaches_only_the_core_network(self):
        simulator = block("simulator")
        self.assertNotIn("ports:", simulator)
        self.assertIn("networks: [armor_core]", simulator)

    def test_it_waits_for_a_healthy_server_and_builds_the_simulator_next_to_this_repository(self):
        simulator = block("simulator")
        self.assertIn("server: { condition: service_healthy }", simulator)
        self.assertIn("build: ../ARMOR-SIMULATOR", simulator)

    def test_the_token_comes_from_the_environment_and_is_required(self):
        self.assertIn("ARMOR_INGEST_TOKEN: ${ARMOR_INGEST_TOKEN:?run scripts/generate_secrets.sh}", block("simulator"))

    def test_every_setting_it_passes_is_documented_in_the_example_environment(self):
        passed = set(re.findall(r"^\s+(ARMOR_SIM_[A-Z_]+):", block("simulator"), re.M)) - {"ARMOR_SIM_SERVER_URL"}
        self.assertTrue(passed)
        for name in passed:
            self.assertRegex(ENV_EXAMPLE, rf"(?m)^{name}=", name)

    @unittest.skipUnless((SIMULATOR / "docker" / "bench.sh").is_file(), "ARMOR-SIMULATOR is not next to this repository")
    def test_the_script_of_the_image_reads_every_setting_the_compose_file_passes(self):
        script = (SIMULATOR / "docker" / "bench.sh").read_text(encoding="utf-8")
        for name in re.findall(r"^\s+(ARMOR_SIM_[A-Z_]+):", block("simulator"), re.M):
            self.assertIn(name, script, name)


if __name__ == "__main__":
    unittest.main()
