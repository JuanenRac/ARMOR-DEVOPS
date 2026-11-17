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
RFC_VECTOR_KEY = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"


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
        agent._totp_failures.update(count=0, until=0.0)

    def test_the_code_of_rfc_6238_is_right(self):
        self.assertEqual(agent.totp_code(RFC_VECTOR_KEY, 59 // 30), "287082")
        self.assertEqual(agent.totp_code(RFC_VECTOR_KEY.lower(), 1111111109 // 30), "081804")

    def test_a_code_is_good_once_and_only_near_its_time(self):
        self.assertTrue(agent.totp_accepts(RFC_VECTOR_KEY, "287082", now=59))
        self.assertFalse(agent.totp_accepts(RFC_VECTOR_KEY, "287082", now=59), "a code is spent when used")
        self.assertFalse(agent.totp_accepts(RFC_VECTOR_KEY, "081804", now=59 + 3600))
        for bad in ("", "12345", "1234567", "abcdef", None, 287082):
            self.assertFalse(agent.totp_accepts(RFC_VECTOR_KEY, bad, now=59))

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
        self.file.write_text(RFC_VECTOR_KEY + "\n", encoding="ascii")
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

    def test_wrong_codes_close_the_door_for_a_time_that_grows_and_a_right_code_opens_it(self):
        self.file.write_text(RFC_VECTOR_KEY + "\n", encoding="ascii")
        env = {"ARMOR_MAINT_TOTP_FAILURES": "3", "ARMOR_MAINT_TOTP_LOCK_S": "30", "ARMOR_MAINT_TOTP_LOCK_MAX_S": "100"}
        with mock.patch.dict(os.environ, env), mock.patch.object(agent.time, "time", return_value=59.0):
            for _ in range(2):
                with self.assertRaises(agent.Refused) as caught:
                    agent.guard_sensitive("POST", ["console", "run"], None, "000000")
                self.assertEqual(caught.exception.code, "totp_invalid")
            self.assertEqual(agent.totp_lock_wait(), 0, "two wrong codes are still allowed")
            with self.assertRaises(agent.Refused):
                agent.guard_sensitive("POST", ["console", "run"], None, "000000")   # the third closes it for 30 s
            self.assertEqual(agent.totp_lock_wait(), 31)
            # while it is closed even the right code is not looked at, so the door cannot be tried
            with self.assertRaises(agent.Refused) as caught:
                agent.guard_sensitive("POST", ["console", "run"], None, "287082")
            self.assertEqual((caught.exception.status, caught.exception.code), (429, "totp_locked"))
        with mock.patch.dict(os.environ, env), mock.patch.object(agent.time, "time", return_value=59.0 + 40):
            self.assertEqual(agent.totp_lock_wait(), 0)
            with self.assertRaises(agent.Refused):
                agent.guard_sensitive("POST", ["console", "run"], None, "000000")   # the fourth: twice as long
            self.assertEqual(agent.totp_lock_wait(), 61)
            agent.totp_failed()
            agent.totp_failed()
            self.assertEqual(agent.totp_lock_wait(), 101, "never longer than the longest lock")
        with mock.patch.dict(os.environ, env), mock.patch.object(agent.time, "time", return_value=59.0 + 400):
            self.assertEqual(agent.totp_lock_wait(), 0)
            self.assertTrue(agent.totp_accepts(RFC_VECTOR_KEY, agent.totp_code(RFC_VECTOR_KEY, int((59.0 + 400) // 30))))
            agent.totp_cleared()
            self.assertEqual(agent._totp_failures["count"], 0)

    def test_the_lock_can_be_switched_off_and_a_missing_code_does_not_count(self):
        self.file.write_text(RFC_VECTOR_KEY + "\n", encoding="ascii")
        with mock.patch.dict(os.environ, {"ARMOR_MAINT_TOTP_LOCKOUT": "0", "ARMOR_MAINT_TOTP_FAILURES": "1"}):
            for _ in range(5):
                with self.assertRaises(agent.Refused) as caught:
                    agent.guard_sensitive("POST", ["console", "run"], None, "000000")
                self.assertEqual(caught.exception.code, "totp_invalid")
            self.assertEqual(agent.totp_lock_wait(), 0)
        with mock.patch.dict(os.environ, {"ARMOR_MAINT_TOTP_FAILURES": "1"}):
            for _ in range(3):
                with self.assertRaises(agent.Refused) as caught:
                    agent.guard_sensitive("POST", ["console", "run"], None, "")
                self.assertEqual(caught.exception.code, "totp_required")
            self.assertEqual(agent.totp_lock_wait(), 0)
            self.assertEqual(agent.totp_lockout_settings(), (1, 30.0, 3600.0))
        with mock.patch.dict(os.environ, {"ARMOR_MAINT_TOTP_FAILURES": "banana", "ARMOR_MAINT_TOTP_LOCK_S": "0"}):
            self.assertEqual(agent.totp_lockout_settings(), (5, 1.0, 3600.0), "a value that is not a number falls back, one out of range is cut")

    def test_reading_never_needs_a_code(self):
        self.file.write_text(RFC_VECTOR_KEY + "\n", encoding="ascii")
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

    def test_the_extended_list_is_off_until_asked_for_and_then_guards_the_keys_of_remote_access(self):
        extended = [("POST", ["remote", "wireguard", "peers"]), ("GET", ["remote", "wireguard", "peers", "phone"]), ("POST", ["remote", "wireguard", "peers", "phone", "remove"]),
                    ("POST", ["remote", "ddns", "update"]), ("POST", ["updates", "armor-server", "rollback"])]
        os.environ["ARMOR_MAINT_PEER_UIDS"] = "998"
        for method, parts in extended:                      # off: nothing changes, a user outside the list still gets through
            agent.guard_sensitive(method, parts, (1, 1000, 1000), "")
        os.environ["ARMOR_MAINT_SENSITIVE_EXTENDED"] = "1"
        for method, parts in extended:
            with self.subTest(parts=parts):
                with self.assertRaises(agent.Refused) as caught:
                    agent.guard_sensitive(method, parts, (1, 1000, 1000), "")
                self.assertEqual((caught.exception.status, caught.exception.code), (403, "peer_not_allowed"))
                agent.guard_sensitive(method, parts, (1, 998, 998), "")
        with self.assertRaises(agent.Refused):                       # a forced update is guarded too, a plain one is not
            agent.guard_sensitive("POST", ["updates"], (1, 1000, 1000), "", True)
        agent.guard_sensitive("POST", ["updates"], (1, 998, 998), "", True)
        agent.guard_sensitive("POST", ["updates"], (1, 1000, 1000), "", False)
        os.environ["ARMOR_MAINT_SENSITIVE_EXTENDED"] = "0"
        agent.guard_sensitive("POST", ["updates"], (1, 1000, 1000), "", True)   # off: the forced update is not guarded
        os.environ["ARMOR_MAINT_SENSITIVE_EXTENDED"] = "1"
        for method, parts in (("GET", ["remote"]), ("GET", ["remote", "wireguard", "peers"]), ("GET", ["overview"]), ("POST", ["updates"]), ("GET", ["updates", "x", "rollback"])):
            agent.guard_sensitive(method, parts, (1, 1000, 1000), "")   # reading and the plain update are not on the extended list

    def test_every_sensitive_route_is_one_the_helper_serves(self):
        source = (HERE / "armor_maintenance_agent.py").read_text(encoding="utf-8")
        for method, parts in agent.SENSITIVE_ROUTES:
            self.assertIn(f'method == "{method}" and parts == {list(parts)!r}'.replace("'", '"'), source, parts)


if __name__ == "__main__":
    unittest.main()
