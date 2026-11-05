#!/usr/bin/env python3
# ARMOR-DEVOPS - tests of armor_dynsec.py: the converted file allows what the ACL file allows, and keeps the password hashes.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
from __future__ import annotations

import base64
import contextlib
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import armor_dynsec as dyn  # noqa: E402


def passwd_line(user: str, password: str, salt: bytes = b"0123456789ab") -> str:
    digest = hashlib.pbkdf2_hmac("sha512", password.encode(), salt, 101, dklen=64)
    return f"{user}:$7$101${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


ACL = """# managed
user armor-server
topic read armor/node/+/telemetry
topic read armor/health/#
topic write armor/control/+/command
topic readwrite armor/device/#
topic write armor/server/alert

user field-node-north-1
topic write armor/node/north-1/telemetry
topic read armor/node/north-1/command
topic readwrite armor/device/north-1/#
topic read armor/control/all/command

user alarm-siren
topic read armor/server/alert
"""
LEGACY_USERS_TEXT = "\n".join([passwd_line("armor-server", "a" * 20), passwd_line("field-node-north-1", "b" * 20, b"abcdefghijkl"), passwd_line("alarm-siren", "c" * 20, b"zyxwvutsrqpo")]) + "\n"


class Convert(unittest.TestCase):
    def doc(self) -> dict:
        return dyn.convert(LEGACY_USERS_TEXT, ACL, "admin-secret")

    def test_every_identity_has_a_client_and_a_role(self) -> None:
        doc = self.doc()
        names = {c["username"] for c in doc["clients"]}
        self.assertEqual(names, {"armor-server", "field-node-north-1", "alarm-siren", dyn.ADMIN_USER})
        self.assertEqual({r["rolename"] for r in doc["roles"]}, {"armor-server", "field-node-north-1", "alarm-siren", dyn.ADMIN_ROLE})

    def test_the_password_hash_is_carried_over(self) -> None:
        doc = self.doc()
        client = next(c for c in doc["clients"] if c["username"] == "field-node-north-1")
        digest = hashlib.pbkdf2_hmac("sha512", ("b" * 20).encode(), base64.b64decode(client["salt"]), client["iterations"], dklen=64)
        self.assertEqual(base64.b64decode(client["password"]), digest)
        self.assertEqual(base64.b64decode(client["salt"]), b"abcdefghijkl")

    def test_default_access_is_deny(self) -> None:
        access = self.doc()["defaultACLAccess"]
        self.assertFalse(access["publishClientToBroker"])
        self.assertFalse(access["publishBrokerToClient"])
        self.assertFalse(access["subscribe"])

    def test_the_converted_file_allows_exactly_what_the_acl_allows(self) -> None:
        self.assertEqual(dyn.differences(dyn.parse_acl(ACL), self.doc()), [])

    def test_a_node_cannot_command_another_node(self) -> None:
        doc = self.doc()
        self.assertFalse(dyn.dynsec_allows(doc, "field-node-north-1", "write", "armor/control/north-1/command"))
        self.assertTrue(dyn.dynsec_allows(doc, "armor-server", "write", "armor/control/north-1/command"))
        self.assertFalse(dyn.dynsec_allows(doc, "field-node-north-1", "read", "armor/node/south-1/command"))
        self.assertFalse(dyn.dynsec_allows(doc, "alarm-siren", "write", "armor/server/alert"))

    def test_the_check_notices_a_difference(self) -> None:
        doc = self.doc()
        role = next(r for r in doc["roles"] if r["rolename"] == "alarm-siren")
        role["acls"].append({"acltype": "publishClientSend", "topic": "armor/server/alert", "allow": True})
        self.assertTrue(dyn.differences(dyn.parse_acl(ACL), doc))

    def test_the_administrator_may_only_manage_the_plugin(self) -> None:
        doc = self.doc()
        self.assertTrue(dyn.dynsec_allows(doc, dyn.ADMIN_USER, "write", "$CONTROL/dynamic-security/v1"))
        self.assertFalse(dyn.dynsec_allows(doc, dyn.ADMIN_USER, "write", "armor/control/north-1/command"))

    def test_refuses_what_it_cannot_carry_over(self) -> None:
        with self.assertRaises(dyn.ConvertError):
            dyn.parse_passwd("old:$6$salt$hash\n")
        with self.assertRaises(dyn.ConvertError):
            dyn.parse_acl("topic read armor/x\n")
        with self.assertRaises(dyn.ConvertError):
            dyn.parse_acl("pattern read armor/%u\n")
        with self.assertRaises(dyn.ConvertError):
            dyn.convert(passwd_line("ghost", "x"), "user other\ntopic read a/b\n", "p")
        with self.assertRaises(dyn.ConvertError):
            dyn.convert(passwd_line(dyn.ADMIN_USER, "x"), "user " + dyn.ADMIN_USER + "\ntopic read a/b\n", "p")


class CommandLine(unittest.TestCase):
    def test_convert_then_check_and_the_password_is_never_printed(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            (base / "passwd").write_text(LEGACY_USERS_TEXT, encoding="utf-8")
            (base / "acl").write_text(ACL, encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = dyn.main(["convert", "--passwd", str(base / "passwd"), "--acl", str(base / "acl"), "--out", str(base / "dyn.json"), "--admin-password-file", str(base / "admin")])
            self.assertEqual(code, 0)
            self.assertIn("DYNSEC=PASS", out.getvalue())
            secret = (base / "admin").read_text(encoding="utf-8").strip()
            self.assertGreaterEqual(len(secret), 32)
            self.assertNotIn(secret, out.getvalue())
            self.assertNotIn(secret, (base / "dyn.json").read_text(encoding="utf-8"))
            if os.name == "posix":
                self.assertEqual((base / "dyn.json").stat().st_mode & 0o777, 0o600)
                self.assertEqual((base / "admin").stat().st_mode & 0o777, 0o600)
            json.loads((base / "dyn.json").read_text(encoding="utf-8"))
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = dyn.main(["check", "--passwd", str(base / "passwd"), "--acl", str(base / "acl"), "--dynsec", str(base / "dyn.json")])
            self.assertEqual(code, 0)
            # an ACL that changed after the conversion no longer matches
            (base / "acl").write_text(ACL + "topic write armor/node/north-1/info\n", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                code = dyn.main(["check", "--passwd", str(base / "passwd"), "--acl", str(base / "acl"), "--dynsec", str(base / "dyn.json")])
            self.assertEqual(code, 1)

    def test_conf_lines(self) -> None:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(dyn.main(["conf", "--config-file", "/x/d.json"]), 0)
        self.assertIn("plugin_opt_config_file /x/d.json", out.getvalue())

    def test_the_real_acl_example_converts(self) -> None:
        example = Path(__file__).resolve().parent.parent / "mosquitto" / "acl.example"
        blocks = dyn.parse_acl(example.read_text(encoding="utf-8"))
        passwd = "\n".join(passwd_line(name, "p" * 12) for name in blocks)
        self.assertEqual(dyn.differences(blocks, dyn.convert(passwd, example.read_text(encoding="utf-8"), "p")), [])


if __name__ == "__main__":
    unittest.main()
