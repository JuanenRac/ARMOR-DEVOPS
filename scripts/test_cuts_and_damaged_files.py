#!/usr/bin/env python3
# ARMOR-DEVOPS - scripts/test_cuts_and_damaged_files.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
"""Downloads and answers cut in the middle, a damaged history and configuration files in another encoding. Nothing real is touched."""
from __future__ import annotations

import http.client
import io
import json
import socketserver
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

if not hasattr(socketserver, "UnixStreamServer"):
    raise unittest.SkipTest("the helpers need Unix sockets (Linux, macOS or WSL)")

import armor_admin_agent as admin  # noqa: E402
import armor_doctor as doctor  # noqa: E402
import armor_maintenance_agent as maintenance  # noqa: E402


class _Answer(io.BytesIO):
    def __init__(self, body: bytes, declared: int) -> None:
        super().__init__(body)
        self.headers = {"Content-Length": str(declared)}


class CutTests(unittest.TestCase):
    def setUp(self) -> None:
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)

    def test_a_download_that_arrives_short_is_a_failed_download(self) -> None:
        job = maintenance.Job("test", [("get", "get")])
        with mock.patch.object(maintenance.urllib.request, "urlopen", return_value=_Answer(b"half", 100)):
            with self.assertRaises(maintenance.Refused) as stop:
                maintenance.download(job, "get", "https://example.invalid/a", self.folder / "a")
        self.assertEqual(str(stop.exception), "download_failed")

    def test_cut_answers_are_unreachable_not_a_crash(self) -> None:
        for broken in (http.client.IncompleteRead(b"{", 100), http.client.BadStatusLine("x")):
            with mock.patch.object(maintenance, "http_get", side_effect=broken):
                repo = next(iter(maintenance.COMPONENTS))
                self.assertEqual(maintenance.latest_release(repo, force=True), {"error": "github_unreachable"})
            with mock.patch.object(maintenance.urllib.request, "urlopen", side_effect=broken):
                self.assertIsNone(maintenance.armed_state())   # unknown is handled as armed
            found = doctor.live_contracts("http://127.0.0.1:1", "t", get=mock.Mock(side_effect=broken))
            self.assertEqual(found[0][0], "warn")

    def test_a_damaged_history_starts_again(self) -> None:
        job = maintenance.Job("test", [])
        job.state, job.error, job.started, job.finished, job.result = "done", "", 0, 0, {}
        with mock.patch.object(maintenance, "DATA_DIR", self.folder):
            for raw in (b'[{"id": "cut', b'{"not": "a list"}', b"\xff\xfe"):
                (self.folder / "history.json").write_bytes(raw)
                maintenance.record_history(job)
                self.assertEqual(len(json.loads((self.folder / "history.json").read_text(encoding="utf-8"))), 1, raw)

    def test_a_file_in_another_encoding_is_refused_and_does_not_hide_the_list(self) -> None:
        key = next(iter(admin.FILES))
        path = self.folder / "file"
        path.write_bytes(b"# se\xf1al\n")
        with mock.patch.object(admin, "file_path", return_value=path):
            with self.assertRaises(admin.Refused) as stop:
                admin.read_file(key)
            self.assertEqual(str(stop.exception), "file_not_utf8")
            entry = admin.listed_file(key)
        self.assertTrue(entry["unreadable"] and entry["exists"])
        self.assertEqual(path.read_bytes(), b"# se\xf1al\n")


if __name__ == "__main__":
    unittest.main()
