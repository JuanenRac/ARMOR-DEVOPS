"""Tests of armor_lan_cert.py: the authority and the certificate are made in a throwaway folder with the openssl of the machine; no key is ever printed; the switch is off until it is turned on.

Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import armor_lan_cert as lan  # noqa: E402


def run_cli(*argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = lan.main(list(argv))
    return code, out.getvalue(), err.getvalue()


@unittest.skipUnless(shutil.which("openssl"), "openssl is not installed")
class LanCertTests(unittest.TestCase):
    def setUp(self) -> None:
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.folder = Path(holder.name) / "lan-ca"
        patcher = mock.patch.dict(os.environ, {"ARMOR_LAN_CA_DIR": str(self.folder)})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_it_is_off_until_it_is_switched_on_and_plan_changes_nothing(self) -> None:
        code, out, _ = run_cli("plan", "--ip", "192.168.0.180")
        self.assertEqual(code, 0)
        self.assertIn("switch: off", out)
        self.assertFalse(self.folder.exists())
        code, _, err = run_cli("setup", "--ip", "192.168.0.180")
        self.assertEqual(code, 2)
        self.assertIn("switched off", err)
        self.assertFalse((self.folder / "ca.key").exists())

    def test_setup_makes_an_authority_and_a_certificate_for_the_address_without_printing_a_key(self) -> None:
        code, out, err = run_cli("setup", "--ip", "192.168.0.180", "--name", "armor.lan", "--enable")
        self.assertEqual(code, 0, err)
        self.assertNotIn("PRIVATE", out + err)
        for name in ("ca.key", "ca.crt", "leaf.key", "leaf.crt", "fullchain.pem", "lan-ca.json"):
            self.assertTrue((self.folder / name).is_file(), name)
        self.assertTrue(json.loads((self.folder / "lan-ca.json").read_text())["enabled"])
        # the chain verifies, for the address, with the authority
        verify = subprocess.run(["openssl", "verify", "-CAfile", str(self.folder / "ca.crt"), "-verify_ip", "192.168.0.180", str(self.folder / "leaf.crt")], capture_output=True, text=True)
        self.assertEqual(verify.returncode, 0, verify.stdout + verify.stderr)
        wrong = subprocess.run(["openssl", "verify", "-CAfile", str(self.folder / "ca.crt"), "-verify_ip", "192.168.0.99", str(self.folder / "leaf.crt")], capture_output=True, text=True)
        self.assertNotEqual(wrong.returncode, 0)
        text = subprocess.run(["openssl", "x509", "-in", str(self.folder / "leaf.crt"), "-noout", "-text"], capture_output=True, text=True).stdout
        self.assertIn("IP Address:192.168.0.180", text)
        self.assertIn("DNS:armor.lan", text)
        self.assertIn("CA:FALSE", text)
        authority = subprocess.run(["openssl", "x509", "-in", str(self.folder / "ca.crt"), "-noout", "-text"], capture_output=True, text=True).stdout
        self.assertIn("CA:TRUE, pathlen:0", authority)
        self.assertIn("Name Constraints", authority)
        # the public parts hold no key
        for name in ("ca.crt", "leaf.crt"):
            self.assertNotIn("PRIVATE", (self.folder / name).read_text())
        self.assertNotIn("PRIVATE", (self.folder / "fullchain.pem").read_text())

    def test_a_second_run_keeps_the_authority_and_the_certificate_until_the_address_changes(self) -> None:
        run_cli("setup", "--ip", "192.168.0.180", "--enable")
        before = (self.folder / "ca.crt").read_text(), (self.folder / "leaf.crt").read_text()
        _, out, _ = run_cli("setup", "--ip", "192.168.0.180")
        self.assertIn("authority: kept", out)
        self.assertIn("certificate: kept", out)
        self.assertEqual(before, ((self.folder / "ca.crt").read_text(), (self.folder / "leaf.crt").read_text()))
        _, out, _ = run_cli("setup", "--ip", "192.168.0.181")
        self.assertIn("certificate: made for 192.168.0.181", out)
        self.assertEqual(before[0], (self.folder / "ca.crt").read_text())   # the authority is the same, so the devices do not have to be touched
        self.assertNotEqual(before[1], (self.folder / "leaf.crt").read_text())

    def test_a_public_address_or_a_foreign_name_is_refused(self) -> None:
        for ip in ("8.8.8.8", "not-an-ip", "::1", "0.0.0.0"):
            code, _, err = run_cli("plan", "--ip", ip)
            self.assertEqual(code, 2, ip)
            self.assertTrue(err, ip)
        code, _, err = run_cli("plan", "--ip", "192.168.0.180", "--name", "example.com")
        self.assertEqual(code, 2)
        self.assertIn(".lan or .local", err)
        code, _, _ = run_cli("plan", "--ip", "192.168.0.180", "--name", "bad name.lan")
        self.assertEqual(code, 2)

    def test_the_settings_file_is_checked(self) -> None:
        self.folder.mkdir(parents=True)
        for bad in ('{"enabled": "yes"}', '{"leaf_days": 0}', '{"leaf_days": 900}', '{"curve": "rsa"}', '{"unknown": 1}', "[1]", "not json"):
            (self.folder / "lan-ca.json").write_text(bad)
            code, _, err = run_cli("status")
            self.assertEqual(code, 2, bad)
            self.assertIn("lan-ca.json", err)
        (self.folder / "lan-ca.json").write_text('{"enabled": true, "leaf_days": 90, "curve": "secp384r1", "name_constraints": false}')
        code, _, err = run_cli("setup", "--ip", "10.1.2.3")
        self.assertEqual(code, 0, err)
        authority = subprocess.run(["openssl", "x509", "-in", str(self.folder / "ca.crt"), "-noout", "-text"], capture_output=True, text=True).stdout
        self.assertNotIn("Name Constraints", authority)
        self.assertIn("secp384r1", authority)

    def test_fingerprint_export_status_and_remove(self) -> None:
        code, _, err = run_cli("fingerprint")
        self.assertEqual(code, 2)
        self.assertIn("no authority", err)
        run_cli("setup", "--ip", "192.168.0.180", "--enable")
        _, out, _ = run_cli("fingerprint")
        self.assertRegex(out.strip(), r"^[0-9A-F]{64}$")
        _, spki, _ = run_cli("fingerprint", "--spki")
        self.assertRegex(spki.strip(), r"^[A-Za-z0-9+/]{43}=$")
        _, pem, _ = run_cli("export-ca")
        self.assertTrue(pem.startswith("-----BEGIN CERTIFICATE-----"))
        self.assertNotIn("PRIVATE", pem)
        target = self.folder.parent / "ca-export.crt"
        run_cli("export-ca", "--out", str(target))
        self.assertEqual(target.read_text(), pem)
        _, status, _ = run_cli("status")
        self.assertIn("switch: on", status)
        self.assertIn("days left", status)
        self.assertNotIn("PRIVATE", status)
        _, removed, _ = run_cli("remove")
        self.assertIn("not deleted", removed)
        self.assertFalse(self.folder.exists())
        self.assertTrue(any(path.name.startswith("lan-ca.removed-") for path in self.folder.parent.iterdir()))   # put aside, never deleted

    def test_the_default_folder_is_under_the_armor_folder_of_the_user(self) -> None:
        with mock.patch.dict(os.environ, {"ARMOR_LAN_CA_DIR": ""}):
            self.assertEqual(lan.base_dir(), Path.home() / ".armor" / "lan-ca")


if __name__ == "__main__":
    unittest.main()
