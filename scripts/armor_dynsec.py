#!/usr/bin/env python3
# ARMOR-DEVOPS - moves the identities of the A.R.M.O.R. broker from the password and ACL files to the dynamic-security plugin of Mosquitto 2.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
"""The broker of an installation reads ``etc/mosquitto/passwd`` and ``etc/mosquitto/acl``, which ``mqtt_identity.sh`` edits with awk and sed. The
dynamic-security plugin that ships with Mosquitto 2 keeps the same information in one JSON file and manages it through the broker (``mosquitto_ctrl``),
so an identity is added, changed or removed by a command that is either applied or refused, not by rewriting a text file.

This helper does not touch a running broker. It

* ``convert``: reads the two files and writes the ``dynamic-security.json`` the plugin loads at start. Each password hash is carried over (the
  ``$7$`` PBKDF2-SHA512 lines of ``mosquitto_passwd`` are the same hash the plugin stores), so no identity has to be given a new password; each ACL block becomes
  one role of the same name, and ``read`` / ``write`` / ``readwrite`` become the matching permissions. The default access is *deny*. An administrator
  identity is added for ``mosquitto_ctrl``; its password is generated and written only to the file given with ``--admin-password-file`` (mode 0600),
  never printed.
* ``check``: compares what the ACL file lets every identity do with what the converted file lets it do, on every topic the ACL names (wildcards filled in
  with sample values) and on topics no block names, and fails on the first difference.
* ``conf``: prints the lines of ``mosquitto.conf`` that replace ``password_file`` and ``acl_file`` (the plugin path and the file are settings).

Exit 0 when it did what was asked, 1 when ``check`` found a difference or the input cannot be converted, 2 for a wrong command line.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import secrets
import sys
from pathlib import Path
from typing import Any

ITERATIONS = 101  # what mosquitto_passwd writes and the plugin reads back
ADMIN_USER = "armor-dynsec-admin"
ADMIN_ROLE = "armor-dynsec-admin"
DEFAULT_PLUGIN = "/usr/lib/mosquitto_dynamic_security.so"
DEFAULT_CONFIG = "/opt/armor/etc/mosquitto/dynamic-security.json"
ACL_WORDS = {"read": ("read",), "write": ("write",), "readwrite": ("read", "write")}


class ConvertError(Exception):
    pass


def parse_passwd(text: str) -> dict[str, tuple[bytes, bytes, int]]:
    """username -> (salt, hash, iterations) for every ``user:$7$iterations$salt$hash`` line."""
    out: dict[str, tuple[bytes, bytes, int]] = {}
    for number, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, sep, rest = line.partition(":")
        parts = rest.split("$")
        if not sep or len(parts) != 5 or parts[0] != "" or parts[1] != "7":
            raise ConvertError(f"passwd line {number}: only the $7$ (PBKDF2-SHA512) hash can be carried over; set a new password for this identity with mosquitto_passwd first")
        try:
            iterations = int(parts[2])
            salt = base64.b64decode(parts[3], validate=True)
            digest = base64.b64decode(parts[4], validate=True)
        except Exception as error:  # noqa: BLE001 - any malformed field is the same refusal
            raise ConvertError(f"passwd line {number}: the hash is not valid base64") from error
        if name in out:
            raise ConvertError(f"passwd line {number}: the identity appears twice")
        out[name] = (salt, digest, iterations)
    return out


def parse_acl(text: str) -> dict[str, list[tuple[str, str]]]:
    """identity -> [(``read`` | ``write``, topic)] from the blocks ``user NAME`` followed by ``topic ...`` lines."""
    blocks: dict[str, list[tuple[str, str]]] = {}
    current: str | None = None
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        word, _, rest = line.partition(" ")
        rest = rest.strip()
        if word == "user":
            if not rest:
                raise ConvertError(f"acl line {number}: a user block without a name")
            current = rest
            blocks.setdefault(current, [])
        elif word == "topic":
            if current is None:
                raise ConvertError(f"acl line {number}: a topic before any user block (anonymous rules are not carried over)")
            kind, _, topic = rest.partition(" ")
            topic = topic.strip()
            if kind not in ACL_WORDS or not topic:
                raise ConvertError(f"acl line {number}: only 'topic read|write|readwrite TOPIC' can be carried over")
            for side in ACL_WORDS[kind]:
                if (side, topic) not in blocks[current]:
                    blocks[current].append((side, topic))
        else:
            raise ConvertError(f"acl line {number}: '{word}' cannot be carried over (the broker's own files only use user and topic lines)")
    return blocks


def role_for(name: str, rules: list[tuple[str, str]]) -> dict[str, Any]:
    acls: list[dict[str, Any]] = []
    for side, topic in rules:
        if side == "write":
            acls.append({"acltype": "publishClientSend", "topic": topic, "allow": True})
        else:
            acls.append({"acltype": "subscribePattern", "topic": topic, "allow": True})
            acls.append({"acltype": "publishClientReceive", "topic": topic, "allow": True})
    return {"rolename": name, "textdescription": "carried over from the ACL file", "acls": acls}


def hash_password(password: str) -> tuple[bytes, bytes]:
    salt = secrets.token_bytes(12)
    return salt, hashlib.pbkdf2_hmac("sha512", password.encode(), salt, ITERATIONS, dklen=64)


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def convert(passwd_text: str, acl_text: str, admin_password: str) -> dict[str, Any]:
    users = parse_passwd(passwd_text)
    blocks = parse_acl(acl_text)
    if ADMIN_USER in users or ADMIN_USER in blocks:
        raise ConvertError(f"the identity {ADMIN_USER} is reserved for the dynamic-security administrator")
    without_acl = sorted(set(users) - set(blocks))
    without_password = sorted(set(blocks) - set(users))
    if without_password:
        raise ConvertError("identities in the ACL without a password: " + ", ".join(without_password))
    clients: list[dict[str, Any]] = []
    roles: list[dict[str, Any]] = []
    for name in sorted(users):
        salt, digest, iterations = users[name]
        clients.append({"username": name, "textname": "", "roles": [{"rolename": name}] if name in blocks else [],
                        "password": b64(digest), "salt": b64(salt), "iterations": iterations})
        if name in blocks:
            roles.append(role_for(name, blocks[name]))
    # An identity with a password and no block could connect and do nothing in the old broker: it keeps that, with no role.
    _ = without_acl
    salt, digest = hash_password(admin_password)
    clients.append({"username": ADMIN_USER, "textname": "administrator of the plugin", "roles": [{"rolename": ADMIN_ROLE}],
                    "password": b64(digest), "salt": b64(salt), "iterations": ITERATIONS})
    roles.append({"rolename": ADMIN_ROLE, "textdescription": "manages the plugin and nothing else", "acls": [
        {"acltype": "publishClientSend", "topic": "$CONTROL/dynamic-security/#", "allow": True},
        {"acltype": "publishClientReceive", "topic": "$CONTROL/dynamic-security/#", "allow": True},
        {"acltype": "subscribePattern", "topic": "$CONTROL/dynamic-security/#", "allow": True},
    ]})
    return {
        "defaultACLAccess": {"publishClientToBroker": False, "publishBrokerToClient": False, "subscribe": False, "unsubscribe": True},
        "clients": clients, "groups": [], "roles": roles,
    }


# ---- the two ways of deciding, written independently so that ``check`` compares two implementations ----

def topic_matches(pattern: str, topic: str) -> bool:
    p, t = pattern.split("/"), topic.split("/")
    for i, part in enumerate(p):
        if part == "#":
            return i == len(p) - 1 and (len(t) >= i)
        if i >= len(t):
            return False
        if part != "+" and part != t[i]:
            return False
    return len(p) == len(t)


def acl_allows(blocks: dict[str, list[tuple[str, str]]], user: str, op: str, topic: str) -> bool:
    """op: ``write`` (publish) or ``read`` (subscribe to, or receive from, ``topic``)."""
    return any(side == op and topic_matches(rule, topic) for side, rule in blocks.get(user, []))


def dynsec_allows(doc: dict[str, Any], user: str, op: str, topic: str) -> bool:
    roles = {r["rolename"]: r for r in doc["roles"]}
    client = next((c for c in doc["clients"] if c["username"] == user), None)
    if client is None:
        return False
    acls = [a for c in client["roles"] for a in roles[c["rolename"]]["acls"]]
    if op == "write":
        return any(a["acltype"] == "publishClientSend" and a["allow"] and topic_matches(a["topic"], topic) for a in acls)
    # to read, a client must be allowed to subscribe to the filter and to receive the messages
    return (any(a["acltype"] == "subscribePattern" and a["allow"] and topic_matches(a["topic"], topic) for a in acls)
            and any(a["acltype"] == "publishClientReceive" and a["allow"] and topic_matches(a["topic"], topic) for a in acls))


def probes(blocks: dict[str, list[tuple[str, str]]]) -> list[str]:
    found: set[str] = {"armor/other/x/state", "armor/control/x/command", "$SYS/broker/uptime", "armor/node/zz/command", "armor/server/alert", "x"}
    for rules in blocks.values():
        for _, topic in rules:
            found.add(topic)
            found.add(topic.replace("#", "probe/deep").replace("+", "probe"))
            found.add(topic.replace("#", "").replace("+", "other").rstrip("/") + "/extra")
            found.add(re.sub(r"/[^/]+$", "/changed", topic.replace("+", "probe").replace("#", "probe")))
    return sorted(found)


def differences(blocks: dict[str, list[tuple[str, str]]], doc: dict[str, Any]) -> list[str]:
    out: list[str] = []
    topics = probes(blocks)
    users = sorted(set(blocks) | {c["username"] for c in doc["clients"]})
    for user in users:
        if user == ADMIN_USER:
            continue
        for op in ("read", "write"):
            for topic in topics:
                if acl_allows(blocks, user, op, topic) != dynsec_allows(doc, user, op, topic):
                    out.append(f"{user} {op} {topic}")
    return out


def read_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def write_private(path: str, text: str) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(text)
    if os.name == "posix":
        os.chmod(path, 0o600)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    sub = parser.add_subparsers(dest="action", required=True)
    for name in ("convert", "check"):
        one = sub.add_parser(name)
        one.add_argument("--passwd", required=True, help="the broker's password file")
        one.add_argument("--acl", required=True, help="the broker's ACL file")
    sub.choices["convert"].add_argument("--out", required=True, help="the dynamic-security.json to write (mode 0600)")
    sub.choices["convert"].add_argument("--admin-password-file", required=True, help="where the generated administrator password is written (mode 0600); it is never printed")
    sub.choices["check"].add_argument("--dynsec", required=True, help="the converted file to compare with")
    conf = sub.add_parser("conf")
    conf.add_argument("--plugin", default=DEFAULT_PLUGIN)
    conf.add_argument("--config-file", default=DEFAULT_CONFIG)
    args = parser.parse_args(argv)
    try:
        if args.action == "conf":
            print(f"plugin {args.plugin}\nplugin_opt_config_file {args.config_file}")
            return 0
        passwd_text, acl_text = read_text(args.passwd), read_text(args.acl)
        if args.action == "convert":
            admin_password = secrets.token_urlsafe(32)
            doc = convert(passwd_text, acl_text, admin_password)
            write_private(args.admin_password_file, admin_password + "\n")
            write_private(args.out, json.dumps(doc, indent=2) + "\n")
            wrong = differences(parse_acl(acl_text), doc)
            if wrong:
                print("DYNSEC=FAIL the converted file differs from the ACL: " + "; ".join(wrong[:5]))
                return 1
            print(f"DYNSEC=PASS {len(doc['clients'])} identities, {len(doc['roles'])} roles written to {args.out}")
            return 0
        doc = json.loads(read_text(args.dynsec))
        wrong = differences(parse_acl(acl_text), doc)
        if wrong:
            print(f"DYNSEC=FAIL {len(wrong)} differences, first: " + "; ".join(wrong[:5]))
            return 1
        print("DYNSEC=PASS the converted file allows exactly what the ACL file allows")
        return 0
    except (ConvertError, OSError, ValueError, KeyError) as error:
        print(f"DYNSEC=FAIL {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
