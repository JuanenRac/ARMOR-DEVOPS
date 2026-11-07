#!/usr/bin/env python3
# ARMOR-DEVOPS - tests of armor_doctor.py on installations built in a temporary folder.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
from __future__ import annotations

import contextlib
import hashlib
import hmac
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import armor_doctor  # noqa: E402

INGEST = "i" * 43
NODE_ID = "network-1"


def derived(ingest: str = INGEST, node: str = NODE_ID) -> str:
    return hmac.new(ingest.encode(), f"armor-node:{node}".encode(), hashlib.sha256).hexdigest()


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    if os.name == "posix":
        path.chmod(0o640)


def installation(folder: str) -> Path:
    etc = Path(folder) / "etc"
    etc.mkdir()
    write(etc / "armor.env", f"ARMOR_INGEST_TOKEN={INGEST}\nARMOR_CONTROL_TOKEN={'c' * 43}\nARMOR_OPERATOR_TOKEN={'o' * 43}\nARMOR_STUDIO_PASSWORD={'p' * 30}\n")
    write(etc / "armor.network-node.env", f"ARMOR_INGEST_TOKEN={derived()}\nARMOR_NETWORK_NODE_ID={NODE_ID}\n")
    write(etc / "armor.mqtt.env", "ARMOR_MQTT_URL=mqtt://127.0.0.1:18883\nARMOR_MQTT_PASSWORD=" + "m" * 30 + "\n")
    write(etc / "mosquitto.conf", "listener 18883\nallow_anonymous false\n")
    return Path(folder)


def levels(results):
    return [(level, subject) for level, subject, _m in results]


class AclTests(unittest.TestCase):
    HERE = Path(__file__).resolve().parent
    ROLES = json.loads((HERE / "node_roles.json").read_text(encoding="utf-8"))["roles"]
    SERVER = [line for line in (HERE / "armor_server.acl").read_text(encoding="utf-8").splitlines() if line.startswith("topic ")]

    def run_acl(self, text: str):
        found: list[tuple[str, str, str]] = []
        armor_doctor.acl_findings(text, self.ROLES, self.SERVER, lambda level, subject, message: found.append((level, subject, message)))
        return found

    def block(self, user: str, lines) -> str:
        return f"user {user}\n" + "\n".join(lines) + "\n\n"

    def role_lines(self, kind: str, name: str) -> list[str]:
        return [topic.replace("{name}", name) for topic in self.ROLES[kind]["topics"]]

    def test_blocks_made_by_the_script_are_exactly_their_kind(self):
        text = self.block("armor-server", self.SERVER) + self.block("field-node-north-1", self.role_lines("node", "north-1")) + self.block("alarm-node-alarm-1", self.role_lines("alarm-node", "alarm-1"))
        found = self.run_acl(text)
        self.assertEqual([(level, subject) for level, subject, _m in found], [("ok", "mosquitto/acl")], found)
        self.assertIn("3 identities have", found[0][2])

    def test_the_most_specific_kind_wins_for_a_name_two_kinds_fit(self):
        self.assertEqual(armor_doctor.role_for("alarm-node-alarm-1", self.ROLES), ("alarm-node", "alarm-1"))
        self.assertEqual(armor_doctor.role_for("alarm-siren", self.ROLES), ("consumer", "siren"))
        self.assertIsNone(armor_doctor.role_for("somebody", self.ROLES))
        self.assertIsNone(armor_doctor.role_for("field-node-", self.ROLES))

    def test_a_line_that_opens_everything_to_a_node_fails_and_to_the_server_does_not(self):
        wide = self.block("field-node-north-1", self.role_lines("node", "north-1") + ["topic readwrite #"])
        self.assertEqual([r[0] for r in self.run_acl(wide)], ["fail"])
        self.assertIn("is given everything", self.run_acl(wide)[0][2])
        for line in ("topic read armor/#", "topic write #", "topic readwrite $SYS/#"):
            self.assertEqual([r[0] for r in self.run_acl(self.block("device-kitchen", [line]))], ["fail"], line)
        self.assertFalse([r for r in self.run_acl(self.block("armor-server", self.SERVER + ["topic read armor/#"])) if r[0] == "fail"])

    def test_a_line_beyond_the_kind_and_a_missing_one_are_warnings_that_say_which(self):
        lines = self.role_lines("node", "north-1")
        extra = self.run_acl(self.block("field-node-north-1", lines + ["topic write armor/node/south-1/telemetry"]))
        self.assertEqual([r[0] for r in extra], ["warn"])
        self.assertIn("1 line(s) beyond its kind", extra[0][2])
        self.assertIn("armor/node/south-1/telemetry", extra[0][2])
        short = self.run_acl(self.block("field-node-north-1", lines[1:]))
        self.assertEqual([r[0] for r in short], ["warn"])
        self.assertIn("lacks 1 line(s)", short[0][2])

    def test_the_old_wide_line_of_the_relaxed_mode_is_not_beyond_the_kind(self):
        relaxed = self.block("field-node-north-1", self.role_lines("node", "north-1") + ["topic write armor/solar/north-1/#"])
        self.assertEqual([r[0] for r in self.run_acl(relaxed)], ["ok"])

    def test_an_identity_of_no_kind_and_an_empty_list_are_warnings(self):
        self.assertEqual([r[0] for r in self.run_acl(self.block("somebody", ["topic read a/b"]))], ["warn"])
        self.assertEqual([r[0] for r in self.run_acl("# nothing\n")], ["warn"])

    def test_comments_and_blank_lines_end_and_skip_what_they_should(self):
        parsed = armor_doctor.acl_blocks("# a\nuser a\n# note\ntopic read x/y\n\ntopic read lost\nuser b\ntopic  write   z\n")
        self.assertEqual(parsed, {"a": ["topic read x/y"], "b": ["topic write z"]})

    def test_diagnose_reads_the_list_of_an_installation_and_names_the_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            prefix = installation(folder)
            (prefix / "etc" / "mosquitto").mkdir()
            write(prefix / "etc" / "mosquitto" / "acl", self.block("armor-server", self.SERVER) + self.block("device-kitchen", ["topic readwrite #"]))
            results = armor_doctor.diagnose(prefix)
        self.assertTrue([r for r in results if r[0] == "fail" and "device-kitchen" in r[2]], results)


class DoctorTests(unittest.TestCase):
    def test_a_good_installation_passes(self):
        with tempfile.TemporaryDirectory() as folder:
            results = armor_doctor.diagnose(installation(folder))
        self.assertFalse([r for r in results if r[0] == "fail"], results)
        self.assertIn(("ok", "armor.network-node.env"), levels(results))
        self.assertIn(("ok", "armor.mqtt.env"), levels(results))

    def test_a_missing_folder_or_no_env_files_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(armor_doctor.diagnose(Path(folder))[0][0], "fail")
            (Path(folder) / "etc").mkdir()
            self.assertEqual(armor_doctor.diagnose(Path(folder))[0][0], "fail")

    def test_a_short_or_empty_secret_fails_without_saying_how_short(self):
        with tempfile.TemporaryDirectory() as folder:
            prefix = installation(folder)
            write(prefix / "etc" / "armor.admin.env", "ARMOR_ADMIN_TOKEN=abc123\nARMOR_OTHER_PASSWORD=\n")
            results = armor_doctor.diagnose(prefix)
        messages = " ".join(m for lvl, s, m in results if lvl == "fail" and s == "armor.admin.env")
        self.assertIn("too short", messages)
        self.assertIn("empty", messages)
        self.assertNotIn("abc123", messages)
        self.assertNotRegex(messages, r"\b6\b")

    def test_the_same_secret_in_two_places_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            prefix = installation(folder)
            write(prefix / "etc" / "armor.voice.env", f"ARMOR_VOICE_TOKEN={'c' * 43}\n")
            results = armor_doctor.diagnose(prefix)
        self.assertTrue(any(lvl == "fail" and s == "armor.voice.env" and "same value" in m for lvl, s, m in results))

    def test_a_node_token_that_is_not_the_derived_one_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            prefix = installation(folder)
            write(prefix / "etc" / "armor.network-node.env", f"ARMOR_INGEST_TOKEN={'x' * 64}\nARMOR_NETWORK_NODE_ID={NODE_ID}\n")
            results = armor_doctor.diagnose(prefix)
        self.assertTrue(any(lvl == "fail" and "derived" in m for lvl, _s, m in results))

    def test_a_broker_port_nobody_listens_on_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            prefix = installation(folder)
            write(prefix / "etc" / "armor.mqtt.env", "ARMOR_MQTT_URL=mqtt://127.0.0.1:8883\n")
            results = armor_doctor.diagnose(prefix)
        self.assertTrue(any(lvl == "fail" and "8883" in m for lvl, _s, m in results))

    def test_a_good_installation_has_no_old_port(self):
        with tempfile.TemporaryDirectory() as folder:
            results = armor_doctor.diagnose(installation(folder))
        self.assertFalse([r for r in results if r[0] == "warn" and "old Docker numbering" in r[2]], results)

    def test_an_old_docker_port_is_a_warning_that_names_the_new_one_and_prints_no_secret(self):
        with tempfile.TemporaryDirectory() as folder:
            prefix = installation(folder)
            write(prefix / "etc" / "armor.mqtt.env", "ARMOR_MQTT_URL=mqtt://user:" + "s" * 30 + "@127.0.0.1:1883\nARMOR_MQTT_PASSWORD=" + "m" * 30 + "\n")
            write(prefix / "etc" / "armor.studio.env", "ARMOR_PUBLIC_ORIGIN=http://127.0.0.1:8088\n")
            write(prefix / "etc" / "mosquitto.conf", "listener 1883\nallow_anonymous false\n")
            results = armor_doctor.diagnose(prefix)
        old = [r for r in results if "old Docker numbering" in r[2]]
        self.assertEqual({r[0] for r in old}, {"warn"})
        text = "\n".join(m for _l, _s, m in old)
        self.assertIn("1883", text); self.assertIn("18883", text); self.assertIn("8088", text); self.assertIn("18081", text)
        self.assertNotIn("s" * 30, text)
        self.assertFalse([r for r in results if r[0] == "fail" and "old" in r[2]])

    @unittest.skipUnless(os.name == "posix", "file modes are a POSIX matter")
    def test_a_world_readable_file_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            prefix = installation(folder)
            (prefix / "etc" / "armor.env").chmod(0o644)
            results = armor_doctor.diagnose(prefix)
        self.assertTrue(any(lvl == "fail" and s == "armor.env" and "any user" in m for lvl, s, m in results))

    def test_the_command_line_exit_codes_and_json(self):
        with tempfile.TemporaryDirectory() as folder:
            prefix = installation(folder)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = armor_doctor.main(["--prefix", str(prefix), "--json"])
            report = json.loads(out.getvalue())
            self.assertEqual((code, report["ok"]), (0, True))
            self.assertNotIn(INGEST, out.getvalue())
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(armor_doctor.main(["--prefix", str(Path(folder) / "none")]), 1)
                self.assertEqual(armor_doctor.main(["--prefix", str(prefix), "--min-free-mb", str(10**9), "--strict"]), 1)
                self.assertEqual(armor_doctor.main(["--prefix", str(prefix), "--min-free-mb", str(10**9)]), 0)
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                armor_doctor.main(["--min-token-length", "3"])


if __name__ == "__main__":
    unittest.main()
