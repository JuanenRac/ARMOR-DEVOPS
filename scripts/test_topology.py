#!/usr/bin/env python3
# ARMOR-DEVOPS - static checks of the whole service topology: every service of docker-compose.yml and of the TLS overlay, the files they mount, and the variables they read.
# No Docker and no network: the compose files are read as text with a small reader, so the checks run anywhere in milliseconds.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
OVERLAY = (ROOT / "docker-compose.tls.yml").read_text(encoding="utf-8")
ENV_EXAMPLE = (ROOT / ".env.example").read_text(encoding="utf-8")
PORTS = json.loads((ROOT / "scripts" / "ports.json").read_text(encoding="utf-8"))["ports"]

CAPABILITIES_ALLOWED = {"CHOWN", "SETUID", "SETGID", "NET_BIND_SERVICE"}
PROFILES_KNOWN = {"bench", "tls", "lan-ca"}


def section(text: str, name: str) -> str:
    """The body of a top-level section (services, networks, volumes, secrets) up to the next top-level key."""
    match = re.search(rf"^{name}:\n(.*?)(?=^[a-z][a-z-]*:|\Z)", text, re.S | re.M)
    assert match, f"no section {name}"
    return match.group(1)


def services(text: str) -> dict[str, str]:
    body = section(text, "services")
    found: dict[str, str] = {}
    for match in re.finditer(r"^  ([a-z][a-z_0-9-]*):\n(.*?)(?=^  [a-z][a-z_0-9-]*:\n|\Z)", body, re.S | re.M):
        found[match.group(1)] = match.group(2)
    return found


def keys(text: str, name: str) -> list[str]:
    return re.findall(r"^  ([a-z][a-z_0-9-]*):", section(text, name), re.M)


def strip_comments(text: str) -> str:
    return "\n".join(re.sub(r"\s+#.*$", "", line) for line in text.splitlines() if not line.lstrip().startswith("#"))


def flow_list(block: str, key: str) -> list[str]:
    match = re.search(rf"^    {key}: \[(.*?)\]", block, re.M)
    return [item.strip().strip('"') for item in match.group(1).split(",") if item.strip()] if match else []


SERVICES = services(COMPOSE)
CLEAN = {name: strip_comments(block) for name, block in SERVICES.items()}


class ServiceInventoryTests(unittest.TestCase):
    def test_the_services_are_the_known_set(self):
        self.assertEqual(set(SERVICES), {"broker", "server", "studio", "simulator", "proxy", "proxy_lan"})

    def test_the_services_that_start_by_default_are_exactly_the_three_core_ones(self):
        default = [n for n, b in CLEAN.items() if "profiles:" not in b]
        self.assertEqual(sorted(default), ["broker", "server", "studio"])

    def test_every_profile_is_a_known_one_and_each_optional_service_has_exactly_one(self):
        for name, block in CLEAN.items():
            profiles = flow_list(block, "profiles")
            if name in {"broker", "server", "studio"}:
                self.assertEqual(profiles, [], name)
            else:
                self.assertEqual(len(profiles), 1, name)
                self.assertIn(profiles[0], PROFILES_KNOWN, name)

    def test_each_profile_names_a_distinct_service(self):
        profiles = [flow_list(b, "profiles")[0] for b in CLEAN.values() if "profiles:" in b]
        self.assertEqual(len(profiles), len(set(profiles)))

    def test_the_project_name_is_fixed(self):
        self.assertRegex(COMPOSE, r"(?m)^name: armor$")


class HardeningTests(unittest.TestCase):
    def test_every_service_merges_the_hardened_block(self):
        for name, block in CLEAN.items():
            self.assertIn("<<: *hardened", block, name)

    def test_the_hardened_block_is_read_only_drops_everything_and_forbids_new_privileges(self):
        anchor = re.search(r"x-hardened: &hardened\n(.*?)(?=^[a-z])", COMPOSE, re.S | re.M).group(1)
        anchor = strip_comments(anchor)
        self.assertIn("read_only: true", anchor)
        self.assertIn("cap_drop: [ALL]", anchor)
        self.assertIn('no-new-privileges:true', anchor)
        self.assertIn("restart: unless-stopped", anchor)
        self.assertRegex(anchor, r"pids_limit: \$\{ARMOR_PIDS_LIMIT:-\d+\}")

    def test_no_service_is_privileged_or_shares_a_namespace_of_the_host(self):
        for name, block in CLEAN.items():
            for forbidden in ("privileged:", "network_mode:", "pid:", "ipc:", "userns_mode:", "devices:", "cgroup_parent:"):
                self.assertNotIn(forbidden, block, f"{name} uses {forbidden}")

    def test_no_service_mounts_the_docker_socket_or_a_path_of_the_host_system(self):
        for name, block in CLEAN.items():
            self.assertNotIn("docker.sock", block, name)
            for source in re.findall(r"^\s+- (\S+?):/", block, re.M):
                self.assertNotIn(source, {"/", "/etc", "/var", "/proc", "/sys", "/dev", "/run", "/root", "/home"}, f"{name} mounts {source}")

    def test_added_capabilities_are_few_and_from_the_allowed_list(self):
        for name, block in CLEAN.items():
            added = set(flow_list(block, "cap_add"))
            self.assertLessEqual(added, CAPABILITIES_ALLOWED, name)

    def test_the_proxies_add_only_the_low_port_capability(self):
        for name in ("proxy", "proxy_lan"):
            self.assertEqual(flow_list(CLEAN[name], "cap_add"), ["NET_BIND_SERVICE"], name)

    def test_the_broker_adds_the_three_capabilities_to_drop_to_its_own_user_and_nothing_more(self):
        self.assertEqual(set(flow_list(CLEAN["broker"], "cap_add")), {"CHOWN", "SETUID", "SETGID"})

    def test_the_server_adds_no_capability_and_runs_on_its_own_image(self):
        self.assertEqual(flow_list(CLEAN["server"], "cap_add"), [])
        self.assertIn("build: ../ARMOR-SERVER", CLEAN["server"])

    def test_the_writable_places_are_memory_only_or_named_volumes(self):
        for name, block in CLEAN.items():
            self.assertTrue(flow_list(block, "tmpfs"), f"{name} has no tmpfs for /tmp")
            self.assertIn("/tmp", flow_list(block, "tmpfs"), name)

    def test_no_volume_of_the_host_is_writable_except_none(self):
        for name, block in CLEAN.items():
            for line in re.findall(r"^\s+- (\./\S+)$", block, re.M):
                self.assertTrue(line.endswith(":ro"), f"{name}: {line}")

    def test_mounted_files_of_the_host_exist_in_the_repository(self):
        for name, block in CLEAN.items():
            for source in re.findall(r"^\s+- (\./[^:$]+):", block, re.M):
                self.assertTrue((ROOT / source).exists(), f"{name}: {source}")

    def test_the_images_that_are_pulled_carry_a_version_and_a_sha256_digest(self):
        for name, block in CLEAN.items():
            match = re.search(r"^    image: (\S+)", block, re.M)
            if match:
                self.assertRegex(match.group(1), r"^[a-z0-9./-]+:[0-9][0-9.]*@sha256:[0-9a-f]{64}$", name)

    def test_the_images_that_are_built_come_from_a_sibling_repository(self):
        for name, block in CLEAN.items():
            match = re.search(r"^    build: (\S+)", block, re.M)
            if match:
                self.assertRegex(match.group(1), r"^\.\./ARMOR-[A-Z-]+$", name)

    def test_a_service_is_either_pulled_or_built_never_both(self):
        for name, block in CLEAN.items():
            self.assertNotEqual("image:" in block, "build:" in block, name)

    def test_the_numeric_user_of_the_simulator_is_not_root(self):
        match = re.search(r'user: "(\d+):(\d+)"', CLEAN["simulator"])
        self.assertTrue(match)
        self.assertGreater(int(match.group(1)), 0)
        self.assertGreater(int(match.group(2)), 0)

    def test_no_service_asks_for_user_root(self):
        for name, block in CLEAN.items():
            self.assertNotRegex(block, r'user: "?(0|root)(:\S+)?"?\s*$', name)


class LimitTests(unittest.TestCase):
    def test_every_service_has_its_own_memory_and_cpu_variable_with_a_default(self):
        for name, block in CLEAN.items():
            suffix = name.upper()
            self.assertRegex(block, rf"mem_limit: \$\{{ARMOR_MEM_{suffix}:-\d+[mg]\}}", name)
            self.assertRegex(block, rf"cpus: \$\{{ARMOR_CPUS_{suffix}:-\d+(\.\d+)?\}}", name)

    def test_the_limit_variables_are_in_the_example_environment_with_the_same_defaults(self):
        for name, block in CLEAN.items():
            suffix = name.upper()
            mem = re.search(rf"ARMOR_MEM_{suffix}:-(\w+)", block).group(1)
            cpus = re.search(rf"ARMOR_CPUS_{suffix}:-([\d.]+)", block).group(1)
            self.assertRegex(ENV_EXAMPLE, rf"(?m)^ARMOR_MEM_{suffix}={mem}$")
            self.assertRegex(ENV_EXAMPLE, rf"(?m)^ARMOR_CPUS_{suffix}={re.escape(cpus)}$")

    def test_the_memory_of_the_core_services_fits_a_small_board(self):
        total = 0
        for name in ("broker", "server", "studio"):
            value = re.search(r"ARMOR_MEM_\w+:-(\d+)([mg])", CLEAN[name])
            total += int(value.group(1)) * (1024 if value.group(2) == "g" else 1)
        self.assertLessEqual(total, 2048)

    def test_the_limit_of_processes_default_is_sane(self):
        value = int(re.search(r"ARMOR_PIDS_LIMIT:-(\d+)", COMPOSE).group(1))
        self.assertTrue(64 <= value <= 4096)


class NetworkTests(unittest.TestCase):
    def test_two_networks_are_declared_and_the_core_one_is_internal(self):
        body = section(COMPOSE, "networks")
        self.assertEqual(keys(COMPOSE, "networks"), ["armor_core", "armor_edge"])
        self.assertRegex(body, r"armor_core:\n    internal: true")
        self.assertNotRegex(body, r"armor_edge:\n    internal")

    def test_every_network_a_service_uses_is_declared(self):
        declared = set(keys(COMPOSE, "networks"))
        for name, block in CLEAN.items():
            used = set(flow_list(block, "networks"))
            self.assertTrue(used, name)
            self.assertLessEqual(used, declared, name)

    def test_the_services_that_publish_a_port_are_on_the_edge_network(self):
        for name, block in CLEAN.items():
            if re.search(r"^    ports:", block, re.M):
                self.assertIn("armor_edge", flow_list(block, "networks"), name)

    def test_the_services_without_a_port_are_not_on_the_edge_network_unless_they_reach_out(self):
        self.assertEqual(flow_list(CLEAN["simulator"], "networks"), ["armor_core"])

    def test_the_server_publishes_no_port(self):
        self.assertNotRegex(CLEAN["server"], r"(?m)^    ports:")

    def test_every_published_port_binds_to_a_variable_that_defaults_to_the_loopback(self):
        for name, block in CLEAN.items():
            for entry in re.findall(r'"(\$\{[^"]+)"', "".join(re.findall(r"^    ports: \[(.*?)\]", block, re.M))):
                self.assertRegex(entry, r"^\$\{ARMOR_[A-Z_]*BIND:-127\.0\.0\.1\}:", f"{name}: {entry}")

    def test_the_published_ports_are_the_ones_of_the_port_table(self):
        self.assertIn(f":{PORTS['mqtt']['port']}:{PORTS['mqtt']['port']}", CLEAN["broker"])
        self.assertIn(f":{PORTS['studio']['port']}:80", CLEAN["studio"])
        self.assertIn(f"ARMOR_PORT: {PORTS['server']['port']}", CLEAN["server"])
        self.assertIn(f"mqtt://broker:{PORTS['mqtt']['port']}", CLEAN["server"])

    def test_the_port_of_the_tls_overlay_is_the_encrypted_one_of_the_table(self):
        self.assertIn(f":{PORTS['mqtt_tls']['port']}:{PORTS['mqtt_tls']['port']}", OVERLAY)

    def test_no_default_port_is_a_standard_one_other_software_may_use(self):
        for entry in re.findall(r"(\d+):(\d+)\"", "".join(re.findall(r"^    ports: \[(.*?)\]", COMPOSE, re.M))):
            self.assertNotIn(entry[0], {"1883", "8080", "3000", "5432"})

    def test_the_simulator_and_the_proxies_wait_for_what_they_talk_to(self):
        self.assertIn("server: { condition: service_healthy }", CLEAN["simulator"])
        self.assertIn("studio: { condition: service_started }", CLEAN["proxy"])
        self.assertIn("studio: { condition: service_started }", CLEAN["proxy_lan"])

    def test_every_dependency_names_an_existing_service(self):
        for name, block in CLEAN.items():
            for target in re.findall(r"^      ([a-z_]+): \{ condition:", block, re.M):
                self.assertIn(target, SERVICES, f"{name} -> {target}")
                self.assertNotEqual(target, name)

    def test_the_dependencies_have_no_cycle(self):
        edges = {n: re.findall(r"^      ([a-z_]+): \{ condition:", b, re.M) for n, b in CLEAN.items()}
        seen: set[str] = set()

        def visit(node: str, path: tuple[str, ...]) -> None:
            self.assertNotIn(node, path, f"cycle through {node}")
            if node in seen:
                return
            for nxt in edges[node]:
                visit(nxt, path + (node,))
            seen.add(node)

        for node in edges:
            visit(node, ())


class VolumeAndSecretTests(unittest.TestCase):
    def test_every_named_volume_in_use_is_declared_and_every_declared_one_is_used(self):
        declared = set(keys(COMPOSE, "volumes"))
        used = set(re.findall(r"^\s+- ([a-z][a-z-]+):/", "\n".join(CLEAN.values()), re.M))
        self.assertEqual(declared, used)

    def test_each_state_volume_belongs_to_one_service_only(self):
        owners: dict[str, list[str]] = {}
        for name, block in CLEAN.items():
            for volume in re.findall(r"^\s+- ([a-z][a-z-]+):/", block, re.M):
                owners.setdefault(volume, []).append(name)
        for volume, who in owners.items():
            self.assertEqual(len(who), 1, f"{volume} shared by {who}")

    def test_the_secrets_in_use_are_declared_and_come_from_the_ignored_folder(self):
        declared = dict(re.findall(r"^  ([a-z_]+):\n    file: (\S+)", section(COMPOSE, "secrets"), re.M))
        used = set()
        for block in CLEAN.values():
            used |= set(flow_list(block, "secrets"))
        self.assertEqual(set(declared), used)
        for path in declared.values():
            self.assertTrue(path.startswith("./secrets/"), path)

    def test_the_folder_of_secrets_is_ignored_by_git(self):
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertRegex(ignore, r"(?m)^/?secrets/")
        self.assertRegex(ignore, r"(?m)^/?\.env$")

    def test_the_overlay_secrets_are_declared_and_come_from_the_secrets_folder(self):
        declared = dict(re.findall(r"^  ([a-z_]+):\n    file: (\S+)", section(OVERLAY, "secrets"), re.M))
        self.assertEqual(set(declared), {"mqtt_tls_ca", "mqtt_tls_cert", "mqtt_tls_key"})
        for path in declared.values():
            self.assertTrue(path.startswith("./secrets/"), path)

    def test_the_overlay_secrets_list_keeps_the_two_base_secrets(self):
        listed = re.search(r"secrets: \[(.*?)\]", strip_comments(OVERLAY)).group(1)
        for name in ("mqtt_password_file", "mqtt_acl_file", "mqtt_tls_ca", "mqtt_tls_cert", "mqtt_tls_key"):
            self.assertIn(name, listed)

    def test_the_overlay_touches_only_the_broker_service(self):
        self.assertEqual(list(services(OVERLAY)), ["broker"])

    def test_the_overlay_replaces_the_ports_instead_of_adding(self):
        self.assertIn("ports: !override", OVERLAY)

    def test_the_overlay_mounts_the_tls_configuration_read_only(self):
        self.assertIn("./mosquitto/mosquitto-tls.conf:/mosquitto/config/mosquitto.conf:ro", OVERLAY)


class VariableTests(unittest.TestCase):
    VARIABLES = sorted(set(re.findall(r"\$\{([A-Z][A-Z0-9_]*)[:?-]", COMPOSE)))

    def test_there_are_variables_to_check(self):
        self.assertGreater(len(self.VARIABLES), 40)

    def test_every_variable_the_compose_file_reads_is_in_the_example_environment_or_a_generated_secret(self):
        generated = set(re.findall(r"^(ARMOR_[A-Z_]+)=", ENV_EXAMPLE, re.M))
        optional_paths = {"ARMOR_LAN_CADDYFILE", "ARMOR_LAN_CERT_DIR"}
        for name in self.VARIABLES:
            if name in optional_paths:
                continue
            self.assertIn(name, generated, f"{name} is read by docker-compose.yml but absent from .env.example")

    def test_every_required_variable_says_how_to_create_it(self):
        for name, message in re.findall(r"\$\{([A-Z_]+):\?([^}]*)\}", COMPOSE):
            self.assertIn("generate_secrets.sh", message, name)

    def test_every_required_variable_is_generated_by_the_secrets_script(self):
        script = (ROOT / "scripts" / "generate_secrets.sh").read_text(encoding="utf-8")
        for name in re.findall(r"\$\{([A-Z_]+):\?", COMPOSE):
            self.assertIn(name, script, name)

    def test_the_example_environment_has_no_duplicate_keys(self):
        names = re.findall(r"^([A-Z][A-Z0-9_]*)=", ENV_EXAMPLE, re.M)
        self.assertEqual(len(names), len(set(names)))

    def test_the_example_environment_holds_only_placeholders_for_secrets(self):
        for name, value in re.findall(r"^(ARMOR_[A-Z_]*(?:TOKEN|PASSWORD|KEY|SECRET))=(.*)$", ENV_EXAMPLE, re.M):
            self.assertTrue(value == "" or value.startswith("replace-with"), f"{name}={value}")

    def test_the_example_environment_has_no_trailing_spaces_or_quotes(self):
        for line in ENV_EXAMPLE.splitlines():
            if re.match(r"^[A-Z]", line):
                self.assertEqual(line, line.rstrip(), line)
                self.assertNotIn('"', line)
                self.assertNotIn("'", line)

    def test_every_default_of_the_compose_file_matches_the_example_environment(self):
        values = dict(re.findall(r"^([A-Z][A-Z0-9_]*)=(.*)$", ENV_EXAMPLE, re.M))
        for name, default in re.findall(r"\$\{([A-Z][A-Z0-9_]*):-([^}$]*)\}", COMPOSE):
            if name in values and values[name] != "" and default != "":
                self.assertEqual(values[name], default, name)

    def test_the_server_reads_each_secret_from_the_environment_and_not_from_a_literal(self):
        for name in ("ARMOR_INGEST_TOKEN", "ARMOR_CONTROL_TOKEN", "ARMOR_OPERATOR_TOKEN", "ARMOR_STUDIO_PASSWORD", "ARMOR_MQTT_PASSWORD"):
            self.assertRegex(CLEAN["server"], rf"{name}: \$\{{{name}:\?")

    def test_the_three_api_tokens_are_three_different_variables(self):
        tokens = re.findall(r"^      (ARMOR_(?:INGEST|CONTROL|OPERATOR)_TOKEN):", CLEAN["server"], re.M)
        self.assertEqual(sorted(tokens), ["ARMOR_CONTROL_TOKEN", "ARMOR_INGEST_TOKEN", "ARMOR_OPERATOR_TOKEN"])


class HealthcheckTests(unittest.TestCase):
    def test_a_service_waited_for_as_healthy_has_a_check_here_or_is_built_with_one_in_its_image(self):
        for name, block in CLEAN.items():
            for target in re.findall(r"^      ([a-z_]+): \{ condition: service_healthy", block, re.M):
                self.assertTrue("healthcheck:" in CLEAN[target] or "build:" in CLEAN[target], f"{name} waits for {target}")

    def test_the_checks_defined_here_have_interval_timeout_and_retries(self):
        for name, block in CLEAN.items():
            if "healthcheck:" in block:
                for field in ("interval:", "timeout:", "retries:", "test:"):
                    self.assertIn(field, block, f"{name} {field}")

    def test_the_checks_defined_here_have_a_timeout_shorter_than_the_interval(self):
        for name, block in CLEAN.items():
            if "healthcheck:" in block:
                interval = int(re.search(r"interval: (\d+)s", block).group(1))
                timeout = int(re.search(r"timeout: (\d+)s", block).group(1))
                self.assertLess(timeout, interval, name)

    def test_the_process_checks_name_the_process_of_their_image(self):
        self.assertIn("pidof mosquitto", CLEAN["broker"])
        self.assertIn("pidof caddy", CLEAN["proxy"])
        self.assertIn("pidof caddy", CLEAN["proxy_lan"])


class MosquittoConfigTests(unittest.TestCase):
    PLAIN = strip_comments((ROOT / "mosquitto" / "mosquitto.conf").read_text(encoding="utf-8"))
    TLS = strip_comments((ROOT / "mosquitto" / "mosquitto-tls.conf").read_text(encoding="utf-8"))

    def directives(self, text: str) -> list[tuple[str, str]]:
        return [tuple(line.split(None, 1)) for line in text.splitlines() if line.strip()]  # type: ignore[misc]

    def test_both_files_are_made_of_known_directives_only(self):
        known = {"persistence", "persistence_location", "allow_anonymous", "password_file", "acl_file", "listener", "cafile", "certfile", "keyfile", "tls_version"}
        for text in (self.PLAIN, self.TLS):
            for key, _ in self.directives(text):
                self.assertIn(key, known)

    def test_both_files_refuse_anonymous_clients(self):
        for text in (self.PLAIN, self.TLS):
            self.assertIn("allow_anonymous false", text)
            self.assertNotIn("allow_anonymous true", text)

    def test_both_files_read_the_password_and_the_acl_from_the_mounted_secrets(self):
        for text in (self.PLAIN, self.TLS):
            self.assertIn("password_file /run/secrets/mqtt_password_file", text)
            self.assertIn("acl_file /run/secrets/mqtt_acl_file", text)

    def test_the_plain_file_listens_on_one_port_only_the_one_of_the_table(self):
        self.assertEqual(re.findall(r"(?m)^listener (\d+)", self.PLAIN), [str(PORTS["mqtt"]["port"])])

    def test_the_tls_file_listens_on_the_encrypted_and_the_internal_port_only(self):
        self.assertEqual(re.findall(r"(?m)^listener (\d+)", self.TLS), [str(PORTS["mqtt_tls"]["port"]), str(PORTS["mqtt"]["port"])])

    def test_the_tls_listener_comes_before_its_certificate_lines_and_the_plain_one_has_none(self):
        order = [key for key, _ in self.directives(self.TLS)]
        first = order.index("listener")
        self.assertLess(first, order.index("cafile"))
        self.assertLess(order.index("cafile"), order.index("certfile"))
        self.assertLess(order.index("certfile"), order.index("keyfile"))
        self.assertLess(order.index("keyfile"), len(order) - 1 - order[::-1].index("listener"))

    def test_the_tls_file_reads_the_three_files_of_the_overlay_secrets(self):
        for name in ("mqtt_tls_ca", "mqtt_tls_cert", "mqtt_tls_key"):
            self.assertIn(f"/run/secrets/{name}", self.TLS)
            self.assertIn(name, OVERLAY)

    def test_the_tls_file_does_not_allow_a_version_older_than_1_2(self):
        self.assertIn("tls_version tlsv1.2", self.TLS)
        self.assertNotRegex(self.TLS, r"tlsv1(\.[01])?\s*$")

    def test_the_state_is_persisted_in_the_volume_of_the_broker(self):
        for text in (self.PLAIN, self.TLS):
            self.assertIn("persistence true", text)
            self.assertIn("persistence_location /mosquitto/data/", text)

    def test_the_acl_example_is_well_formed(self):
        text = (ROOT / "mosquitto" / "acl.example").read_text(encoding="utf-8")
        users = 0
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            self.assertRegex(line, r"^(user \S+|topic (read |write |readwrite )?\S+|pattern (read |write |readwrite )?\S+)$", line)
            users += line.startswith("user ")
        self.assertGreaterEqual(users, 1)

    def test_the_acl_example_gives_no_user_the_whole_tree(self):
        text = (ROOT / "mosquitto" / "acl.example").read_text(encoding="utf-8")
        self.assertNotRegex(text, r"(?m)^topic (readwrite )?#\s*$")


class CaddyfileTests(unittest.TestCase):
    FILES = {name: (ROOT / "caddy" / name).read_text(encoding="utf-8") for name in ("Caddyfile", "Caddyfile.lan", "Caddyfile.lan-issued")}

    def test_the_braces_are_balanced_in_every_file(self):
        for name, text in self.FILES.items():
            code = "\n".join(line.split("#")[0] for line in text.splitlines())
            code = re.sub(r"\{\$[A-Z_]+(:[^}]*)?\}", "", code)
            self.assertEqual(code.count("{"), code.count("}"), name)

    def test_no_file_serves_plain_http(self):
        for name, text in self.FILES.items():
            self.assertNotRegex(text, r"(?m)^http://", name)

    def test_every_file_proxies_to_studio_on_the_internal_network(self):
        for name, text in self.FILES.items():
            self.assertIn("reverse_proxy studio:80", text, name)

    def test_every_file_sets_the_security_headers(self):
        for name, text in self.FILES.items():
            self.assertIn("Strict-Transport-Security", text, name)
            self.assertIn("X-Content-Type-Options", text, name)
            self.assertIn("-Server", text, name)

    def test_the_variables_the_files_read_are_passed_by_the_compose_file(self):
        passed = CLEAN["proxy"] + CLEAN["proxy_lan"]
        for name, text in self.FILES.items():
            for variable in re.findall(r"\{\$(ARMOR_[A-Z_]+)", text):
                self.assertIn(f"{variable}:", passed, f"{name}: {variable}")

    def test_the_issued_variant_reads_its_certificate_from_the_read_only_mount(self):
        self.assertIn("/lan-certs/", self.FILES["Caddyfile.lan-issued"])

    def test_the_internal_variant_uses_the_local_authority(self):
        self.assertIn("tls internal", self.FILES["Caddyfile.lan"])


if __name__ == "__main__":
    unittest.main()
