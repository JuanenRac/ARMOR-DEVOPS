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


class LanCaProfileTests(unittest.TestCase):
    """The optional profile "lan-ca": HTTPS for the local network with the internal authority of Caddy, only port 443, and the profile "tls" untouched."""

    def test_it_is_an_optional_profile_with_one_published_port_and_no_port_80(self):
        lan = block("proxy_lan")
        self.assertIn("profiles: [lan-ca]", lan)
        ports = re.findall(r"ports: \[(.*?)\]", lan)
        self.assertEqual(len(ports), 1)
        published = re.findall(r'"([^"]+)"', ports[0])
        self.assertEqual(len(published), 1)
        self.assertTrue(published[0].endswith(":443:443"), published[0])
        self.assertNotIn(":80", published[0].replace(":443:443", ""))
        self.assertIn("${ARMOR_LAN_BIND:-127.0.0.1}", published[0])           # it listens on the network only when the administrator says so

    def test_the_profile_tls_is_not_touched(self):
        tls = block("proxy")
        self.assertIn("profiles: [tls]", tls)
        self.assertIn("./caddy/Caddyfile:/etc/caddy/Caddyfile:ro", tls)
        self.assertNotIn("lan-ca", tls)
        self.assertIn("ARMOR_TLS_PORT:-8443", tls)

    def test_the_proxy_has_its_own_authority_and_serves_only_https_with_the_internal_issuer(self):
        lan = block("proxy_lan")
        self.assertIn("lan-ca-data:/data", lan)
        self.assertNotIn("proxy-data", lan)                                    # not the volume of the other profile
        text = (ROOT / "caddy" / "Caddyfile.lan").read_text(encoding="utf-8")
        self.assertIn("tls internal", text)
        self.assertIn("auto_https disable_redirects", text)
        self.assertNotRegex(text, r"(?m)^\s*(http://|:80\b)")
        self.assertIn("reverse_proxy studio:80", text)
        self.assertNotIn("ARMOR_TLS_ISSUER", text)                             # an outside authority is not an option here

    def test_it_is_hardened_like_the_other_proxy_and_reaches_only_studio(self):
        lan = block("proxy_lan")
        self.assertIn("<<: *hardened", lan)
        self.assertIn("networks: [armor_edge, armor_core]", lan)
        self.assertIn("depends_on:\n      studio:", lan)

    def test_the_settings_are_in_the_example_file_and_the_fingerprint_script_reads_only_the_public_certificate(self):
        for name in ("ARMOR_LAN_HOST", "ARMOR_LAN_BIND"):
            self.assertRegex(ENV_EXAMPLE, rf"(?m)^{name}=")
        script = (ROOT / "scripts" / "armor_ca_fingerprint.sh").read_text(encoding="utf-8")
        self.assertIn("root.crt", script)
        self.assertNotIn("root.key", script)
        self.assertIn("-fingerprint -sha256", script)

    @unittest.skipUnless(shutil.which("bash") and shutil.which("openssl"), "no bash or openssl")
    def test_the_fingerprint_of_a_certificate_is_the_sha256_in_upper_case_without_colons(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            key, cert = Path(folder) / "k.pem", Path(folder) / "root.crt"
            made = subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", str(key), "-out", str(cert), "-days", "1", "-subj", "/CN=armor-test"], capture_output=True, text=True, check=False)
            if made.returncode != 0:
                self.skipTest("openssl could not make a certificate")
            done = subprocess.run(["bash", str(ROOT / "scripts" / "armor_ca_fingerprint.sh"), str(cert)], capture_output=True, text=True, check=False)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertRegex(done.stdout.strip(), r"^[0-9A-F]{64}$")
            spki = subprocess.run(["bash", str(ROOT / "scripts" / "armor_ca_fingerprint.sh"), "--spki", str(cert)], capture_output=True, text=True, check=False)
            self.assertEqual(spki.returncode, 0, spki.stderr)
            self.assertRegex(spki.stdout.strip(), r"^[A-Za-z0-9+/]{43}=$")                 # the base64 of 32 bytes: what the phone app pins
            pem = subprocess.run(["bash", str(ROOT / "scripts" / "armor_ca_fingerprint.sh"), "--pem", str(cert)], capture_output=True, text=True, check=False)
            self.assertTrue(pem.stdout.startswith("-----BEGIN CERTIFICATE-----"), pem.stdout[:40])

            missing = subprocess.run(["bash", str(ROOT / "scripts" / "armor_ca_fingerprint.sh"), str(Path(folder) / "none.crt")], capture_output=True, text=True, check=False)
            self.assertNotEqual(missing.returncode, 0)


class ResourceLimitsAndHealthTests(unittest.TestCase):
    """Every service has a limit of processes, memory and CPUs that .env can change, and a check of health (its own, or the one its image carries)."""

    SERVICES = ("broker", "server", "studio", "simulator", "proxy", "proxy_lan")

    def test_every_service_has_a_memory_and_cpu_limit_that_the_environment_can_change(self):
        for name in self.SERVICES:
            text = block(name)
            self.assertRegex(text, rf"mem_limit: \$\{{ARMOR_MEM_{name.upper()}:-[0-9]+[mg]\}}", name)
            self.assertRegex(text, rf"cpus: \$\{{ARMOR_CPUS_{name.upper()}:-[0-9.]+\}}", name)
            self.assertRegex(ENV_EXAMPLE, rf"(?m)^ARMOR_MEM_{name.upper()}=[0-9]+[mg]$", name)
            self.assertRegex(ENV_EXAMPLE, rf"(?m)^ARMOR_CPUS_{name.upper()}=[0-9.]+$", name)

    def test_the_limit_of_processes_is_in_the_shared_block_and_in_the_example(self):
        anchor = COMPOSE.split("services:")[0]
        self.assertIn("pids_limit: ${ARMOR_PIDS_LIMIT:-512}", anchor)
        self.assertRegex(ENV_EXAMPLE, r"(?m)^ARMOR_PIDS_LIMIT=512$")
        for name in self.SERVICES:
            self.assertIn("<<: *hardened", block(name), name)

    def test_the_defaults_leave_room_for_the_server(self):
        server = re.search(r"mem_limit: \$\{ARMOR_MEM_SERVER:-([0-9]+)([mg])\}", block("server"))
        self.assertIsNotNone(server)
        megabytes = int(server.group(1)) * (1024 if server.group(2) == "g" else 1)  # type: ignore[union-attr]
        self.assertGreaterEqual(megabytes, 512)

    def test_the_services_without_a_check_in_their_image_have_one_here(self):
        for name in ("broker", "proxy", "proxy_lan"):
            text = block(name)
            self.assertIn("healthcheck:", text, name)
            self.assertRegex(text, r"pidof (mosquitto|caddy)", name)
            for key in ("interval:", "timeout:", "retries:"):
                self.assertIn(key, text, name)

    def test_a_service_is_waited_for_as_healthy_only_if_something_checks_it(self):
        waited = set(re.findall(r"(\w+): \{ condition: service_healthy \}", COMPOSE))
        self.assertTrue(waited)
        carried = {"server": ROOT.parent / "ARMOR-SERVER" / "Dockerfile", "studio": ROOT.parent / "ARMOR-STUDIO" / "Dockerfile"}
        for name in waited:
            if "healthcheck:" in block(name):
                continue
            dockerfile = carried.get(name)
            if dockerfile is None or not dockerfile.is_file():
                self.skipTest(f"the image of {name} is not next to this repository")
            self.assertIn("HEALTHCHECK", dockerfile.read_text(encoding="utf-8"), name)


if __name__ == "__main__":
    unittest.main()
