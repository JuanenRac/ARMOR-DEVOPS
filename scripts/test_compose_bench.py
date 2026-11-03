#!/usr/bin/env python3
# ARMOR-DEVOPS - the virtual bench of docker-compose.yml: an optional profile with simulated nodes that can reach only the server and never publishes a port.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
from __future__ import annotations

import os
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
ENV_EXAMPLE = (ROOT / ".env.example").read_text(encoding="utf-8")
SIMULATOR = ROOT.parent / "ARMOR-SIMULATOR"
TLS = (ROOT / "docker-compose.tls.yml").read_text(encoding="utf-8")
SH = os.environ.get("ARMOR_BASH") or shutil.which("sh")
if SH and "system32" in SH.lower():  # the shell of the Windows subsystem for Linux cannot use these paths
    SH = None


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


class BenchWithTlsTests(unittest.TestCase):
    def test_the_tls_overlay_touches_only_the_broker(self):
        self.assertNotIn("simulator", TLS)
        self.assertRegex(TLS, r"(?m)^  broker:")
        self.assertEqual(re.findall(r"(?m)^  ([a-z][a-z0-9_-]*):$", TLS.split("secrets:")[0]), ["broker"])

    def test_the_overlay_publishes_only_the_encrypted_port(self):
        ports = re.search(r"ports: !override \[(.*?)\]", TLS)
        self.assertIsNotNone(ports)
        self.assertIn(":8883:8883", ports.group(1))  # type: ignore[union-attr]
        self.assertNotIn("18883", ports.group(1))  # type: ignore[union-attr]

    def test_the_bench_needs_no_broker_secret_and_no_key_of_the_overlay(self):
        simulator = block("simulator")
        for word in ("mqtt_", "secrets:", "broker", "BROKER", "MQTT_PASSWORD"):
            self.assertNotIn(word, simulator, f"the simulated nodes of the bench must not hold {word}")

    def test_the_server_url_of_the_bench_is_inside_the_core_network(self):
        self.assertIn("ARMOR_SIM_SERVER_URL: http://server:18080", block("simulator"))

    @unittest.skipUnless(SH and (SIMULATOR / "docker" / "bench.sh").is_file(), "no sh or ARMOR-SIMULATOR is not next to this repository")
    def test_the_dry_run_of_the_bench_script_builds_one_command_per_node_and_hides_the_token(self):
        env = dict(os.environ, ARMOR_SIM_DRY_RUN="1", ARMOR_SIM_NODES="3", ARMOR_INGEST_TOKEN="secret-token-value", ARMOR_INGEST_STRICT="1", ARMOR_SIM_SOLAR="1")
        done = subprocess.run([SH, str(SIMULATOR / "docker" / "bench.sh")], env=env, capture_output=True, text=True, check=False)
        self.assertEqual(done.returncode, 0, done.stderr)
        commands = [line for line in done.stdout.splitlines() if line.startswith("armor-simulator ")]
        self.assertEqual(len(commands), 3)
        self.assertEqual(sorted(re.search(r"--node-id (\S+)", c).group(1) for c in commands), ["bench-1", "bench-2", "bench-3"])  # type: ignore[union-attr]
        for command in commands:
            self.assertIn("--per-node-token", command)
            self.assertIn("--solar", command)
            self.assertIn("--server-url http://server:18080", command)
        self.assertNotIn("secret-token-value", done.stdout + done.stderr)

    @unittest.skipUnless(SH and (SIMULATOR / "docker" / "bench.sh").is_file(), "no sh or ARMOR-SIMULATOR is not next to this repository")
    def test_the_bench_script_refuses_a_missing_token_and_a_wrong_count(self):
        base = {k: v for k, v in os.environ.items() if not k.startswith("ARMOR_")}
        for extra in ({"ARMOR_SIM_NODES": "3"}, {"ARMOR_SIM_NODES": "9", "ARMOR_INGEST_TOKEN": "x"}, {"ARMOR_SIM_NODES": "two", "ARMOR_INGEST_TOKEN": "x"}):
            done = subprocess.run([SH, str(SIMULATOR / "docker" / "bench.sh")], env=dict(base, ARMOR_SIM_DRY_RUN="1", **extra), capture_output=True, text=True, check=False)
            self.assertEqual(done.returncode, 2, str(extra))


if __name__ == "__main__":
    unittest.main()
