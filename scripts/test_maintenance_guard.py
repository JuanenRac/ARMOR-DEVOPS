#!/usr/bin/env python3
# ARMOR-DEVOPS - tests of who may change the sensitive settings of the maintenance helper: the user of the caller (SO_PEERCRED) and the one-time code (TOTP).
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
# Pure functions and a temporary folder: no socket, no root, nothing real is touched, so it runs on any system.
from __future__ import annotations

import importlib.util
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("armor_maintenance_agent", HERE / "armor_maintenance_agent.py")
assert spec is not None and spec.loader is not None
agent = importlib.util.module_from_spec(spec)
sys.modules["armor_maintenance_agent"] = agent
spec.loader.exec_module(agent)

# The test vector of RFC 6238 (SHA-1, secret "12345678901234567890"), the code for the time 59 s is 94287082 (eight digits), so 287082 in six.
RFC_SECRET = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"


class FakeConnection:
    def __init__(self, pid=10, uid=998, gid=998):
        self.packed = struct.pack("3i", pid, uid, gid)

    def getsockopt(self, level, option, size):
        return self.packed


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.file = Path(self.folder.name) / "maint.totp"
        patcher = mock.patch.dict(os.environ, {"ARMOR_MAINT_TOTP_FILE": str(self.file)})
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("ARMOR_MAINT_PEER_UIDS", None)
        agent._totp_last_counter[0] = 0

    def test_the_code_of_rfc_6238_is_right(self):
        self.assertEqual(agent.totp_code(RFC_SECRET, 59 // 30), "287082")
        self.assertEqual(agent.totp_code(RFC_SECRET.lower(), 1111111109 // 30), "081804")

    def test_a_code_is_good_once_and_only_near_its_time(self):
        self.assertTrue(agent.totp_accepts(RFC_SECRET, "287082", now=59))
        self.assertFalse(agent.totp_accepts(RFC_SECRET, "287082", now=59), "a code is spent when used")
        self.assertFalse(agent.totp_accepts(RFC_SECRET, "081804", now=59 + 3600))
        for bad in ("", "12345", "1234567", "abcdef", None, 287082):
            self.assertFalse(agent.totp_accepts(RFC_SECRET, bad, now=59))

    def test_nothing_is_asked_while_the_checks_are_off(self):
        agent.guard_sensitive("POST", ["console", "run"], None, "")

    def test_only_the_listed_users_make_sensitive_calls(self):
        os.environ["ARMOR_MAINT_PEER_UIDS"] = "998, 0"
        agent.guard_sensitive("POST", ["system", "reboot"], (1, 998, 998), "")
        for credentials in ((1, 1000, 1000), None):
            with self.assertRaises(agent.Refused) as caught:
                agent.guard_sensitive("POST", ["system", "reboot"], credentials, "")
            self.assertEqual((caught.exception.status, caught.exception.code), (403, "peer_not_allowed"))
        agent.guard_sensitive("GET", ["overview"], (1, 1000, 1000), "")   # what only reads is not sensitive

    def test_a_current_code_is_needed_once_the_authenticator_is_enrolled(self):
        self.file.write_text(RFC_SECRET + "\n", encoding="ascii")
        with self.assertRaises(agent.Refused) as caught:
            agent.guard_sensitive("POST", ["console", "run"], None, "")
        self.assertEqual(caught.exception.code, "totp_required")
        with self.assertRaises(agent.Refused) as caught:
            agent.guard_sensitive("POST", ["console", "run"], None, "000000")
        self.assertEqual((caught.exception.status, caught.exception.code), (401, "totp_invalid"))
        with mock.patch.object(agent.time, "time", return_value=59):
            agent.guard_sensitive("POST", ["console", "run"], None, "287082")
            with self.assertRaises(agent.Refused):
                agent.guard_sensitive("POST", ["console", "run"], None, "287082")

    def test_reading_never_needs_a_code(self):
        self.file.write_text(RFC_SECRET + "\n", encoding="ascii")
        agent.guard_sensitive("GET", ["overview"], None, "")
        agent.guard_sensitive("POST", ["updates"], None, "")

    def test_the_peer_is_read_from_the_kernel_report(self):
        with mock.patch.object(agent.socket, "SO_PEERCRED", 17, create=True):
            self.assertEqual(agent.peer_credentials(FakeConnection(5, 998, 120)), (5, 998, 120))
            self.assertIsNone(agent.peer_credentials(object()))
        with mock.patch.object(agent.socket, "SO_PEERCRED", None, create=True):
            self.assertIsNone(agent.peer_credentials(FakeConnection()))

    @unittest.skipUnless(hasattr(os, "fchmod") and os.name == "posix", "file modes are a Unix thing")
    def test_enrolling_writes_a_secret_only_its_owner_can_read(self):
        secret = agent.totp_enroll()
        self.assertEqual(self.file.read_text(encoding="ascii").strip(), secret)
        self.assertEqual(self.file.stat().st_mode & 0o777, 0o600)
        self.assertEqual(len(agent.totp_code(secret, 1)), 6)

    def test_every_sensitive_route_is_one_the_helper_serves(self):
        source = (HERE / "armor_maintenance_agent.py").read_text(encoding="utf-8")
        for method, parts in agent.SENSITIVE_ROUTES:
            self.assertIn(f'method == "{method}" and parts == {list(parts)!r}'.replace("'", '"'), source, parts)


if __name__ == "__main__":
    unittest.main()
