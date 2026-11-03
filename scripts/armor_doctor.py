#!/usr/bin/env python3
# ARMOR-DEVOPS - "armor doctor": checks that an installation hangs together, read only, without printing a secret.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
"""What it checks, in an installation made by install_cm5.sh (default prefix /opt/armor):

* every ``etc/armor*.env`` file: not readable by everybody, and every token in it long enough;
* no token repeated between the files (one leaked credential must not open two doors);
* the token of the network node is the one derived from the ingest token and its node id;
* the port of the broker in ``armor.mqtt.env`` is a port ``mosquitto.conf`` listens on, when both are found;
* no address or listener still on a port of the old Docker numbering (8080, 8088, 1883): the installations keep working, but the numbering is now 18080, 18081 and 18883 everywhere (ports.json);
* the free space of the disk of the prefix.

It only reads. No value is printed, nor the length of one: a line says "too short", not how short. Exit 0 when nothing failed, 1 when something failed, 2 for a wrong
command line. Warnings do not change the exit code unless ``--strict`` is given.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import shutil
import stat
import sys
from pathlib import Path

DEFAULT_PREFIX = "/opt/armor"
DEFAULT_MIN_TOKEN = 24
DEFAULT_MIN_FREE_MB = 500
SECRET_NAME = re.compile(r"(TOKEN|PASSWORD|KEY|SECRET)$")
MAX_ENV_BYTES = 256 * 1024


def old_port_map() -> dict[int, tuple[str, int]]:
    """{old number: (service, current port)} from ports.json, the copy of the registry of ARMOR-COMMON that sits next to this script."""
    try:
        registry = json.loads((Path(__file__).with_name("ports.json")).read_text(encoding="utf-8"))["ports"]
    except (OSError, ValueError, KeyError):
        return {8080: ("server", 18080), 8088: ("studio", 18081), 1883: ("mqtt", 18883)}
    return {int(old): (name, int(entry["port"])) for name, entry in registry.items() for old in entry.get("legacy", [])}


def read_env(path: Path) -> dict[str, str]:
    """KEY=VALUE lines; comments and blank lines are skipped, a value may be quoted. A file over 256 KiB is not an env file."""
    if path.stat().st_size > MAX_ENV_BYTES:
        raise ValueError("too big for an env file")
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        values[name.strip()] = value.strip().strip("'\"")
    return values


def listener_ports(conf: Path) -> set[int]:
    ports: set[int] = set()
    for line in conf.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == "listener" and parts[1].isdigit():
            ports.add(int(parts[1]))
    return ports


def diagnose(prefix: Path, min_token: int = DEFAULT_MIN_TOKEN, min_free_mb: int = DEFAULT_MIN_FREE_MB, mosquitto_conf: Path | None = None) -> list[tuple[str, str, str]]:
    """A list of (level, subject, message); level is ok, warn or fail."""
    found: list[tuple[str, str, str]] = []

    def add(level: str, subject: str, message: str) -> None:
        found.append((level, subject, message))

    etc = prefix / "etc"
    if not etc.is_dir():
        add("fail", str(etc), "there is no etc/ folder: this is not an installation (or the prefix is wrong)")
        return found
    files = sorted(etc.glob("armor*.env"))
    if not files:
        add("fail", str(etc), "no armor*.env file found")
    seen: dict[str, str] = {}
    envs: dict[str, dict[str, str]] = {}
    for path in files:
        try:
            env = read_env(path)
        except (OSError, ValueError) as error:
            add("fail", path.name, f"cannot be read ({error})")
            continue
        envs[path.name] = env
        start = len(found)
        if os.name == "posix" and path.stat().st_mode & stat.S_IROTH:
            add("fail", path.name, "can be read by any user of the machine (it should be 0640 or tighter)")
        elif os.name == "posix" and path.stat().st_mode & stat.S_IWOTH:
            add("fail", path.name, "can be written by any user of the machine")
        short = [name for name, value in env.items() if SECRET_NAME.search(name) and name != "ARMOR_CAMERA_CONFIG_KEY" and 0 < len(value) < min_token]
        empty = [name for name, value in env.items() if SECRET_NAME.search(name) and not value]
        if short:
            add("fail", path.name, f"too short (under {min_token} characters): {', '.join(sorted(short))}")
        if empty:
            add("fail", path.name, f"empty: {', '.join(sorted(empty))}")
        for name, value in env.items():
            if SECRET_NAME.search(name) and len(value) >= min_token:
                other = seen.get(value)
                if other and other != f"{path.name}:{name}":
                    add("fail", path.name, f"{name} has the same value as {other}: each door needs its own secret")
                seen.setdefault(value, f"{path.name}:{name}")
        if len(found) == start:
            add("ok", path.name, "readable only by its owners and its secrets are long enough" if os.name == "posix" else "its secrets are long enough")

    main = envs.get("armor.env", {})
    node = envs.get("armor.network-node.env")
    if node is not None and main.get("ARMOR_INGEST_TOKEN") and node.get("ARMOR_NETWORK_NODE_ID"):
        expected = hmac.new(main["ARMOR_INGEST_TOKEN"].encode(), f"armor-node:{node['ARMOR_NETWORK_NODE_ID']}".encode(), hashlib.sha256).hexdigest()
        if hmac.compare_digest(expected, node.get("ARMOR_INGEST_TOKEN", "")):
            add("ok", "armor.network-node.env", "the token of the network node is the one derived for its node id")
        else:
            add("fail", "armor.network-node.env", "the token is not the one derived from the ingest token and the node id: the server will refuse the node (run the installer again)")

    mqtt = envs.get("armor.mqtt.env", {})
    conf = mosquitto_conf or next((p for p in (prefix / "etc" / "mosquitto.conf", prefix / "mosquitto" / "mosquitto.conf") if p.is_file()), None)
    match = re.match(r"^mqtts?://[^:/]*:(\d+)", mqtt.get("ARMOR_MQTT_URL", ""))
    if match and conf is not None:
        ports = listener_ports(conf)
        if not ports:
            add("warn", conf.name, "no listener found in it: the port of the broker could not be compared")
        elif int(match.group(1)) in ports:
            add("ok", "armor.mqtt.env", f"the broker port is one the broker listens on ({match.group(1)})")
        else:
            add("fail", "armor.mqtt.env", f"the server connects to port {match.group(1)} but {conf.name} listens on {', '.join(map(str, sorted(ports)))}")
    elif mqtt:
        add("warn", "armor.mqtt.env", "the port of the broker could not be compared (no mosquitto.conf found or no ARMOR_MQTT_URL)")

    old = old_port_map()
    old_pattern = re.compile(r"(?::|=)(" + "|".join(str(n) for n in old) + r")(?![0-9])")
    for name, env in sorted(envs.items()):
        for key, value in sorted(env.items()):
            hit = old_pattern.search(value if not value.isdigit() else "=" + value) if key.endswith(("URL", "ORIGIN", "UPSTREAM", "HOST_PORT", "_PORT")) else None
            if hit:
                service, current = old[int(hit.group(1))]
                add("warn", name, f"{key} still uses port {hit.group(1)} of the old Docker numbering; the {service} is now on {current} (docs/DEPLOYMENT_BOUNDARY.md, ports): update it and the address the clients and nodes use")
    if conf is not None:
        stale = sorted(listener_ports(conf) & set(old))
        for number in stale:
            add("warn", conf.name, f"listens on port {number} of the old Docker numbering; the {old[number][0]} is now on {old[number][1]}: change the listener and the address the nodes use")
    try:
        free_mb = shutil.disk_usage(prefix).free // (1024 * 1024)
        add("ok" if free_mb >= min_free_mb else "warn", str(prefix), "enough free space" if free_mb >= min_free_mb else f"less than {min_free_mb} MB free: an update or a backup may not fit")
    except OSError as error:
        add("warn", str(prefix), f"the free space could not be read ({error})")
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="armor_doctor", description="Check that an ARMOR installation hangs together (read only, no secret is printed)")
    parser.add_argument("--prefix", type=Path, default=Path(DEFAULT_PREFIX), help=f"the installation (default {DEFAULT_PREFIX})")
    parser.add_argument("--min-token-length", type=int, default=DEFAULT_MIN_TOKEN, help=f"shortest secret accepted (default {DEFAULT_MIN_TOKEN})")
    parser.add_argument("--min-free-mb", type=int, default=DEFAULT_MIN_FREE_MB, help=f"free space below which it warns (default {DEFAULT_MIN_FREE_MB})")
    parser.add_argument("--mosquitto-conf", type=Path, help="the broker configuration to compare the port with (default: the one next to the installation)")
    parser.add_argument("--strict", action="store_true", help="a warning also makes the exit code 1")
    parser.add_argument("--json", action="store_true", help="print the result as JSON")
    args = parser.parse_args(argv)
    if args.min_token_length < 8 or args.min_free_mb < 0:
        parser.error("--min-token-length must be at least 8 and --min-free-mb not negative")
    results = diagnose(args.prefix, args.min_token_length, args.min_free_mb, args.mosquitto_conf)
    failed = sum(1 for level, _s, _m in results if level == "fail")
    warned = sum(1 for level, _s, _m in results if level == "warn")
    if args.json:
        print(json.dumps({"ok": not failed, "failed": failed, "warnings": warned, "checks": [{"level": level, "subject": subject, "message": message} for level, subject, message in results]}, sort_keys=True))
    else:
        for level, subject, message in results:
            print(f"{level.upper():4} {subject}: {message}")
        print(f"ARMOR_DOCTOR={'PASS' if not failed else 'FAIL'} failed={failed} warnings={warned}")
    return 1 if failed or (args.strict and warned) else 0


if __name__ == "__main__":
    sys.exit(main())
