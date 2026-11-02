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
    write(etc / "armor.mqtt.env", "ARMOR_MQTT_URL=mqtt://127.0.0.1:1883\nARMOR_MQTT_PASSWORD=" + "m" * 30 + "\n")
    write(etc / "mosquitto.conf", "listener 1883\nallow_anonymous false\n")
    return Path(folder)


def levels(results):
    return [(level, subject) for level, subject, _m in results]


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
