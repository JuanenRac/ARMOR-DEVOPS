#!/usr/bin/env python3
# ARMOR-DEVOPS - tests of scripts/armor_maintenance_agent.py: the versions it reads, what it asks GitHub, how it installs, checks, refuses and rolls back, and the console.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
# Nothing real is touched: a temporary prefix, a stand-in GitHub on the loopback, a stand-in systemctl and a stand-in health address. Needs Linux, macOS or WSL.
from __future__ import annotations

from typing import Any

import hashlib
import http.client
import http.server
import importlib.util
import io
import json
import os
import re
import socket
import stat
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOKEN = "m" * 32


def tarball(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for name, content in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
    return buffer.getvalue()


class TestKey:
    """A throwaway Ed25519 key made with the openssl of the machine for one test run: the real key of the releases is never used here."""

    def __init__(self, folder: Path, name: str) -> None:
        self.pem = folder / (name + ".pem")
        subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", str(self.pem)], check=True, capture_output=True)
        der = subprocess.run(["openssl", "pkey", "-in", str(self.pem), "-pubout", "-outform", "DER"], check=True, capture_output=True).stdout
        self.public = der[-32:].hex()

    def sign(self, message: bytes) -> str:
        source = self.pem.with_suffix(".msg")
        source.write_bytes(message)
        return subprocess.run(["openssl", "pkeyutl", "-sign", "-rawin", "-inkey", str(self.pem), "-in", str(source)], check=True, capture_output=True).stdout.hex()


class FakeGitHub(http.server.BaseHTTPRequestHandler):
    releases: dict[str, dict[str, object]] = {}
    assets: dict[str, bytes] = {}
    healthy = True

    def log_message(self, format: str, *args: object) -> None:
        return

    def do_GET(self) -> None:
        path = self.path
        if path == "/health":
            body = b'{"ok":true}' if FakeGitHub.healthy else b'{"ok":false}'
        elif path.startswith("/repos/") and path.endswith("/releases/latest"):
            repo = path.split("/")[3]
            release = FakeGitHub.releases.get(repo)
            if release is None:
                self.send_response(404); self.end_headers(); return
            body = json.dumps(release).encode()
        elif path.startswith("/assets/"):
            content = FakeGitHub.assets.get(path[len("/assets/"):])
            if content is None:
                self.send_response(404); self.end_headers(); return
            body = content
        else:
            self.send_response(404); self.end_headers(); return
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class UnixConnection(http.client.HTTPConnection):
    def __init__(self, path: str) -> None:
        super().__init__("localhost")
        self._path = path

    def connect(self) -> None:
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self._path)


class MaintenanceTest(unittest.TestCase):
    agent: Any
    base: Any
    calls: Any
    httpd: Any
    key: Any
    maint_env: Any
    other_key: Any
    prefix: Any
    real_key: Any
    tmp: Any
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.prefix = root / "armor"
        cls.prefix.mkdir()
        # a stand-in systemctl that records what it is asked and says every unit is active
        cls.calls = root / "systemctl.log"
        fake = root / "systemctl"
        fake.write_text(f'#!/bin/sh\necho "$@" >> "{cls.calls}"\nif [ "$1" = "is-active" ]; then echo active; fi\nexit 0\n', encoding="utf-8")
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        cls.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeGitHub)
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"
        cls.base = base
        os.environ.update({"ARMOR_PREFIX": str(cls.prefix), "ARMOR_SYSTEMCTL": str(fake), "ARMOR_GITHUB_API": base, "ARMOR_HEALTH_URL": base + "/health",
                           "ARMOR_MAINT_DATA": str(root / "data"), "ARMOR_MAINT_CONSOLE": "1", "ARMOR_MAINT_ENV": str(root / "armor.maint.env")})
        cls.maint_env = root / "armor.maint.env"
        cls.key = TestKey(root, "releases")
        cls.other_key = TestKey(root, "other")
        spec = importlib.util.spec_from_file_location("armor_maintenance_agent", HERE / "armor_maintenance_agent.py")
        assert spec and spec.loader
        cls.agent = importlib.util.module_from_spec(spec)
        sys.modules["armor_maintenance_agent"] = cls.agent
        spec.loader.exec_module(cls.agent)
        cls.real_key = cls.agent.PACKAGE_PUBLIC_KEY
        cls.agent.PACKAGE_PUBLIC_KEY = cls.key.public            # the tests trust their own throwaway key

    def setUp(self) -> None:
        import shutil
        cls = type(self)
        for entry in cls.prefix.iterdir():
            if entry.is_symlink():
                entry.unlink()
            else:
                shutil.rmtree(entry)
        FakeGitHub.releases.clear()
        FakeGitHub.assets.clear()
        FakeGitHub.healthy = True
        cls.maint_env.unlink(missing_ok=True)
        self.agent._cache.clear()
        self.agent.DISK_USAGE = lambda path: type("Usage", (), {"free": 10**12})()       # a disk with room, unless a test says otherwise
        (cls.prefix / "releases" / "20260101-000000" / "server" / "dist").mkdir(parents=True)
        (cls.prefix / "releases" / "20260101-000000" / "server" / "package.json").write_text('{"version": "0.5.4"}', encoding="utf-8")
        (cls.prefix / "releases" / "20260101-000000" / "server" / "package-lock.json").write_text('{"lock": 1}', encoding="utf-8")
        (cls.prefix / "releases" / "20260101-000000" / "server" / "dist" / "server.mjs").write_text("old", encoding="utf-8")
        (cls.prefix / "releases" / "20260101-000000" / "studio" / "dist").mkdir(parents=True)
        (cls.prefix / "releases" / "20260101-000000" / "studio" / "dist" / "version.json").write_text('{"name":"armor-studio","version":"0.7.1"}', encoding="utf-8")
        (cls.prefix / "current").symlink_to(cls.prefix / "releases" / "20260101-000000")
        (cls.prefix / "apps" / "ARMOR-NETWORK" / "src" / "armor_network").mkdir(parents=True)
        (cls.prefix / "apps" / "ARMOR-NETWORK" / "armor.project.json").write_text('{"version": "0.0.6"}', encoding="utf-8")
        (cls.prefix / "apps" / "ARMOR-NETWORK" / "src" / "armor_network" / "__init__.py").write_text('__version__ = "0.0.6"\n', encoding="utf-8")
        (cls.prefix / "ai" / "armor_server_ai").mkdir(parents=True)
        (cls.prefix / "ai" / "armor_server_ai" / "__init__.py").write_text('__version__ = "0.2.4"\n', encoding="utf-8")
        (cls.prefix / "bin").mkdir(parents=True)
        cls.calls.write_text('', encoding='utf-8')

    @classmethod
    def tearDownClass(cls) -> None:
        cls.httpd.shutdown()
        cls.tmp.cleanup()

    def publish(self, repo: str, version: str, files: dict[str, bytes] | None, component: str, good_hash: bool = True, signature: str | None = "valid") -> None:
        """signature: "valid" (the manifest signature .sig2 and the older .sig, both made with the key the agent trusts), "manifest" (only the .sig2), "legacy" (only the older .sig),
        "other" (both made with another key), "garbage", or "none" (neither in the release)."""
        assets = []
        if files is not None:
            name = f"armor-{component}-{version}.tgz"
            content = tarball(files)
            FakeGitHub.assets[name] = content
            digest = hashlib.sha256(content).hexdigest() if good_hash else "0" * 64
            FakeGitHub.assets[name + ".sha256"] = f"{digest}  {name}\n".encode()
            assets = [{"name": name, "browser_download_url": f"{self.base}/assets/{name}"}, {"name": name + ".sha256", "browser_download_url": f"{self.base}/assets/{name}.sha256"}]
            sha = hashlib.sha256(content).hexdigest()
            older = f"armor-pkg/1|{component}|{version}|{sha}".encode()
            manifest = f"armor-fw/1|{component}|package|{version}|{sha}".encode()
            kind = signature or "none"
            texts: dict[str, str | None] = {".sig": None, ".sig2": None}
            if kind in ("valid", "legacy"):
                texts[".sig"] = self.key.sign(older)
            if kind in ("valid", "manifest"):
                texts[".sig2"] = self.key.sign(manifest)
            if kind == "other":
                texts = {".sig": self.other_key.sign(older), ".sig2": self.other_key.sign(manifest)}
            if kind == "garbage":
                texts = {".sig": "zz", ".sig2": "zz"}
            for suffix, text in texts.items():
                if text is not None:
                    FakeGitHub.assets[name + suffix] = (text + "\n").encode()
                    assets.append({"name": name + suffix, "browser_download_url": f"{self.base}/assets/{name}{suffix}"})
        FakeGitHub.releases[repo] = {"tag_name": f"v{version}", "published_at": "2026-10-15T10:00:00Z", "body": "notes", "assets": assets}
        self.agent._cache.clear()

    def wait(self, job) -> dict:
        deadline = time.time() + 30
        while time.time() < deadline:
            view = job.view(0)
            if view["state"] != "running":
                return view
            time.sleep(0.1)
        self.fail("the job did not finish")

    # ---- automatic security updates ----
    originals: dict[str, Any]

    def auto_setup(self) -> Any:
        """The agent pointed at throwaway folders for the apt configuration, the log of unattended-upgrades and the file that says a reboot is needed."""
        import datetime
        root = Path(self.tmp.name)
        agent = self.agent
        names = ("reboot_machine", "check_services_after_run", "armed_state", "installed_services", "unit_active", "AUTO_NOW", "APT_CONF_DIR", "UU_LOG", "REBOOT_REQUIRED", "UU_BIN", "ARMED_URL")
        originals = {name: getattr(agent, name) for name in names}
        self.originals = originals
        def restore() -> None:
            for name, value in originals.items():
                setattr(agent, name, value)

        self.addCleanup(restore)
        agent.APT_CONF_DIR = root / "apt.conf.d"
        agent.APT_CONF_DIR.mkdir(exist_ok=True)
        (agent.APT_CONF_DIR / agent.AUTO_CONF_NAME).unlink(missing_ok=True)
        agent.UU_LOG = root / "unattended-upgrades.log"
        agent.UU_LOG.unlink(missing_ok=True)
        agent.REBOOT_REQUIRED = root / "reboot-required"
        agent.REBOOT_REQUIRED.unlink(missing_ok=True)
        agent.UU_BIN = str(root / "unattended-upgrade")
        agent.auto_state_path().unlink(missing_ok=True)
        agent.AUTO_NOW = lambda: datetime.datetime(2026, 1, 1, 3, 30)
        rebooted: list[int] = []
        def reboot() -> dict[str, object]:
            rebooted.append(1)
            return {"ok": True}

        agent.reboot_machine = reboot
        agent.check_services_after_run = lambda: {"checked": 1, "ok": True, "restarted": [], "down": []}
        return rebooted

    def test_the_automatic_updates_are_on_by_default_security_only_and_never_reboot_by_themselves(self) -> None:
        self.auto_setup()
        settings = self.agent.auto_settings()
        self.assertEqual(settings, {"enabled": True, "reboot": "disarmed", "window_start": "03:00", "window_end": "05:00"})
        text = self.agent.render_auto_conf(settings)
        self.assertIn('Automatic-Reboot "false"', text)
        self.assertIn('APT::Periodic::Unattended-Upgrade "1";', text)
        self.assertIn("#clear Unattended-Upgrade::Allowed-Origins;", text)
        self.assertIn("#clear Unattended-Upgrade::Origins-Pattern;", text)
        origins = re.findall(r'"origin=[^"]+"', text)
        self.assertTrue(origins and all("security" in item.lower() or "Debian-Security" in item for item in origins), origins)
        self.assertNotIn("-updates", text)
        self.assertNotIn("proposed", text)
        self.assertIn('APT::Periodic::Unattended-Upgrade "0";', self.agent.render_auto_conf({**settings, "enabled": False}))

    def test_the_settings_are_validated_stored_and_written_to_apt(self) -> None:
        self.auto_setup()
        view = self.agent.set_auto_settings({"enabled": False, "reboot": "never", "window_start": "22:30", "window_end": "06:00"})
        self.assertEqual(view["settings"], {"enabled": False, "reboot": "never", "window_start": "22:30", "window_end": "06:00"})
        conf = (self.agent.APT_CONF_DIR / self.agent.AUTO_CONF_NAME).read_text(encoding="utf-8")
        self.assertIn('APT::Periodic::Unattended-Upgrade "0";', conf)
        self.assertEqual(self.agent.auto_settings()["window_start"], "22:30")
        for bad in ({"enabled": "yes"}, {"enabled": 1}, {"reboot": "always"}, {"window_start": "25:00"}, {"window_end": "9:00"}, {"window_start": 3}, {"x": 1}):
            with self.assertRaises(self.agent.Refused, msg=str(bad)) as caught:
                self.agent.set_auto_settings(bad)
            self.assertEqual(caught.exception.status, 422)
        self.assertEqual(self.agent.auto_settings()["window_start"], "22:30")            # a refused change changes nothing
        # a stored file that was damaged falls back to the defaults, key by key
        self.agent.auto_state_path().write_text(json.dumps({"settings": {"enabled": "x", "reboot": "disarmed", "window_start": "bad"}}), encoding="utf-8")
        self.assertEqual(self.agent.auto_settings(), {"enabled": True, "reboot": "disarmed", "window_start": "03:00", "window_end": "05:00"})
        self.agent.auto_state_path().write_text("not json", encoding="utf-8")
        self.assertTrue(self.agent.auto_settings()["enabled"])

    def test_the_provision_writes_the_apt_file_on_a_machine_that_has_the_folder_and_only_then(self) -> None:
        self.auto_setup()
        self.agent.auto_provision()
        self.assertTrue((self.agent.APT_CONF_DIR / self.agent.AUTO_CONF_NAME).is_file())
        self.agent.APT_CONF_DIR = Path(self.tmp.name) / "no-such-folder"
        self.agent.auto_provision()                                              # nothing to write to, nothing breaks
        self.assertFalse(self.agent.APT_CONF_DIR.exists())
        with self.assertRaises(self.agent.Refused) as caught:
            self.agent.set_auto_settings({"enabled": True})
        self.assertEqual(caught.exception.code, "apt_conf_unwritable")

    def test_the_log_of_what_was_applied_is_read_and_a_package_name_is_never_trusted_blindly(self) -> None:
        text = ("2026-01-01 03:10:01,100 INFO Starting unattended upgrades script\n"
                "2026-01-01 03:10:02,200 INFO Packages that will be upgraded: libssl3 openssl evil;rm -rf\n"
                "2026-01-01 03:11:00,300 INFO All upgrades installed\n"
                "2026-01-02 03:10:02,200 INFO Packages that will be upgraded: curl\n"
                "2026-01-02 03:11:00,300 ERROR Installing the upgrades failed!\n")
        runs = self.agent.parse_uu_log(text)
        self.assertEqual([item["at"] for item in runs], ["2026-01-02 03:10:02", "2026-01-01 03:10:02"])
        self.assertEqual(runs[0]["state"], "failed")
        self.assertEqual(runs[1]["state"], "installed")
        self.assertEqual(runs[1]["packages"], ["libssl3", "openssl"])
        self.assertEqual(self.agent.parse_uu_log(""), [])

    def test_the_window_of_the_night_may_cross_midnight(self) -> None:
        import datetime
        at = lambda hour, minute: datetime.datetime(2026, 1, 1, hour, minute)
        self.assertTrue(self.agent.in_window(at(3, 0), "03:00", "05:00"))
        self.assertFalse(self.agent.in_window(at(5, 0), "03:00", "05:00"))
        self.assertFalse(self.agent.in_window(at(2, 59), "03:00", "05:00"))
        self.assertTrue(self.agent.in_window(at(23, 30), "22:00", "06:00"))
        self.assertTrue(self.agent.in_window(at(5, 59), "22:00", "06:00"))
        self.assertFalse(self.agent.in_window(at(12, 0), "22:00", "06:00"))
        self.assertTrue(self.agent.in_window(at(12, 0), "00:00", "00:00"))

    def tick(self, armed: bool | None) -> str:
        self.agent.armed_state = lambda: armed
        self.agent.auto_tick()
        return str(self.agent.auto_view()["reboot_note"])

    def test_it_reboots_only_when_disarmed_inside_the_window_and_the_policy_allows_it(self) -> None:
        import datetime
        rebooted = self.auto_setup()
        self.agent.REBOOT_REQUIRED.write_text("*** System restart required ***\n", encoding="utf-8")
        self.assertEqual(self.tick(True), "armed")
        self.assertEqual(self.tick(None), "armed_unknown")                            # not knowing is not permission
        self.assertEqual(rebooted, [])
        self.agent.AUTO_NOW = lambda: datetime.datetime(2026, 1, 1, 12, 0)
        self.assertEqual(self.tick(False), "outside_window")
        self.assertEqual(rebooted, [])
        self.agent.AUTO_NOW = lambda: datetime.datetime(2026, 1, 1, 3, 30)
        self.agent.set_auto_settings({"reboot": "never"})
        self.assertEqual(self.tick(False), "policy_never")
        self.assertEqual(rebooted, [])
        self.assertTrue(self.agent.auto_view()["reboot_required"])                      # Studio says a reboot is waiting
        self.agent.set_auto_settings({"reboot": "disarmed"})
        busy = self.agent.Job("system", [("upgrade", "Upgrade")])
        self.agent.JOBS[busy.id] = busy
        try:
            self.assertEqual(self.tick(False), "busy")
        finally:
            del self.agent.JOBS[busy.id]
        self.assertEqual(rebooted, [])
        self.assertEqual(self.tick(False), "rebooting")
        self.assertEqual(rebooted, [1])
        self.assertGreater(self.agent.auto_view()["last_reboot"], 0)

    def test_nothing_is_done_while_the_switch_is_off_or_no_reboot_is_needed(self) -> None:
        rebooted = self.auto_setup()
        self.assertEqual(self.tick(False), "")                                          # no reboot needed
        self.agent.REBOOT_REQUIRED.write_text("x", encoding="utf-8")
        self.agent.set_auto_settings({"enabled": False})
        self.assertEqual(self.tick(False), "")
        self.assertEqual(rebooted, [])

    def test_a_new_run_of_the_updates_gets_its_services_checked_once(self) -> None:
        self.auto_setup()
        checks: list[int] = []
        def checked() -> dict[str, object]:
            checks.append(1)
            return {"checked": 5, "ok": False, "restarted": ["armor-server"], "down": ["armor-server"]}

        self.agent.check_services_after_run = checked
        self.agent.UU_LOG.write_text("2026-01-01 03:10:02,200 INFO Packages that will be upgraded: curl\n2026-01-01 03:11:00,300 INFO All upgrades installed\n", encoding="utf-8")
        self.tick(False)
        self.tick(False)
        self.assertEqual(checks, [1])                                                   # the same run is not checked twice
        health = self.agent.auto_view()["health"]
        self.assertEqual((health["ok"], health["down"]), (False, ["armor-server"]))
        self.agent.UU_LOG.write_text(self.agent.UU_LOG.read_text(encoding="utf-8") + "2026-01-02 03:10:02,200 INFO Packages that will be upgraded: wget\n", encoding="utf-8")
        self.tick(False)
        self.assertEqual(checks, [1, 1])

    def test_a_service_that_is_down_after_the_updates_is_restarted_once_and_reported(self) -> None:
        self.auto_setup()
        self.agent.check_services_after_run = self.originals["check_services_after_run"]
        answers = {"armor-server": [False, True], "armor-studio": [True], "armor-network": [False, False]}
        self.agent.installed_services = lambda: list(answers)
        self.agent.unit_active = lambda unit: answers[unit].pop(0) if len(answers[unit]) > 1 else answers[unit][0]
        result = self.agent.check_services_after_run()
        self.assertEqual(result["restarted"], ["armor-server", "armor-network"])
        self.assertEqual(result["down"], ["armor-network"])
        self.assertFalse(result["ok"])
        self.assertIn("restart armor-server", self.calls.read_text(encoding="utf-8"))

    def test_the_server_is_asked_whether_the_system_is_armed_and_an_unreachable_one_is_unknown(self) -> None:
        self.auto_setup()
        self.agent.armed_state = self.originals["armed_state"]
        answers = [b'{"armed": true}', b'{"armed": false}', b'{"armed": "no"}', b"nonsense"]

        class Armed(http.server.BaseHTTPRequestHandler):
            seen: list[str] = []

            def log_message(self, format: str, *args: object) -> None:
                return

            def do_GET(self) -> None:
                Armed.seen.append(self.headers.get("X-Armor-Maint-Token", ""))
                body = answers.pop(0)
                self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Armed)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        old, token = self.agent.ARMED_URL, os.environ.get("ARMOR_MAINT_TOKEN")
        os.environ["ARMOR_MAINT_TOKEN"] = TOKEN
        try:
            self.agent.ARMED_URL = f"http://127.0.0.1:{server.server_address[1]}/armed"
            self.assertEqual([self.agent.armed_state() for _ in range(4)], [True, False, None, None])
            self.assertEqual(set(Armed.seen), {TOKEN})
        finally:
            server.shutdown()
            self.agent.ARMED_URL = "http://127.0.0.1:9/armed"
            if token is None:
                del os.environ["ARMOR_MAINT_TOKEN"]
            else:
                os.environ["ARMOR_MAINT_TOKEN"] = token
        self.assertIsNone(self.agent.armed_state())
        self.agent.ARMED_URL = old

    def test_the_overview_carries_the_state_of_the_automatic_updates(self) -> None:
        self.auto_setup()
        view = self.agent.overview(False)["auto_updates"]
        self.assertEqual(view["settings"]["enabled"], True)
        self.assertEqual((view["package"], view["reboot_required"], view["applied"]), (False, False, []))
        Path(self.agent.UU_BIN).write_text("#!/bin/sh\n", encoding="utf-8")
        self.assertTrue(self.agent.auto_view()["package"])

    def test_the_staging_switch_of_studio_wins_over_the_settings_file_and_takes_only_a_boolean(self) -> None:
        self.auto_setup()
        self.maint_env.write_text("ARMOR_MAINT_STAGING=on\n", encoding="utf-8")
        self.assertEqual(self.agent.staging_view(), {"enabled": True, "source": "env", "wait_s": 30})
        self.assertEqual(self.agent.set_staging({"enabled": False}), {"enabled": False, "source": "studio", "wait_s": 30})
        self.assertFalse(self.agent.staging_enabled())
        self.assertTrue(self.agent.set_staging({"enabled": True})["enabled"])
        for bad, code in (({"enabled": "on"}, "bad_enabled"), ({"enabled": 1}, "bad_enabled"), ({"wait": 5}, "unknown_setting"), ({}, "unknown_setting"), ({"enabled": True, "x": 1}, "unknown_setting")):
            with self.assertRaises(self.agent.Refused) as caught:
                self.agent.set_staging(bad)
            self.assertEqual(caught.exception.code, code)
        self.assertTrue(self.agent.staging_enabled())
        self.assertIn(("POST", ("staging",)), self.agent.SENSITIVE_ROUTES)

    def test_the_staging_is_off_when_nobody_chose_and_the_file_says_nothing(self) -> None:
        self.auto_setup()
        self.assertEqual(self.agent.staging_view(), {"enabled": False, "source": "env", "wait_s": 30})

    # ---- npm ----
    def test_npm_gets_its_own_home_because_the_unit_hides_the_home_of_root(self) -> None:
        source = Path(self.agent.__file__).read_text(encoding="utf-8")
        self.assertIn('"HOME": str(npm_home)', source)
        self.assertIn('"npm_config_cache"', source)
        self.assertIn('job.say("npm: " + line[:200])', source)

    def test_a_new_version_of_the_project_alone_does_not_run_npm_again(self) -> None:
        folder = Path(self.tmp.name) / "locks"
        folder.mkdir(exist_ok=True)
        def write(name: str, version: str, dependency: str) -> Path:
            path = folder / name
            path.write_text(json.dumps({"name": "armor-server", "version": version, "packages": {"": {"name": "armor-server", "version": version, "dependencies": {"express": dependency}}, "node_modules/express": {"version": dependency}}}), encoding="utf-8")
            return path
        same = self.agent.lock_fingerprint(write("a.json", "0.8.0.5", "5.1.0"))
        self.assertEqual(same, self.agent.lock_fingerprint(write("b.json", "0.8.0.6", "5.1.0")))
        self.assertNotEqual(same, self.agent.lock_fingerprint(write("c.json", "0.8.0.6", "5.2.0")))
        broken = folder / "broken.json"
        broken.write_text("{ not json", encoding="utf-8")
        self.assertEqual(len(self.agent.lock_fingerprint(broken)), 32)

    # ---- versions ----
    def test_versions_compare_with_three_and_four_components(self) -> None:
        key = self.agent.version_key
        self.assertLess(key("0.7.9"), key("0.8.0"))
        self.assertEqual(key("0.8.0"), key("0.8.0.0"))
        self.assertLess(key("0.8.0.9"), key("0.8.1.0"))
        self.assertGreater(key("0.8.1.0"), key("0.8.0.9"))
        self.assertGreater(key("0.10.0"), key("0.9.9"))

    def test_the_installed_versions_are_read(self) -> None:
        self.assertEqual(self.agent.installed_version("server"), "0.5.4")
        self.assertEqual(self.agent.installed_version("studio"), "0.7.1")
        self.assertEqual(self.agent.installed_version("network"), "0.0.6")
        self.assertEqual(self.agent.installed_version("ai"), "0.2.4")
        self.assertEqual(self.agent.installed_version("voice"), "")

    def test_a_component_is_compared_with_its_release(self) -> None:
        self.publish("ARMOR-SERVER", "0.5.5", {"server/package.json": b'{"version":"0.5.5"}'}, "server")
        state = self.agent.component_state("server", True)
        self.assertEqual((state["installed"], state["latest"], state["status"], state["installable"]), ("0.5.4", "0.5.5", "update_available", True))
        self.publish("ARMOR-SERVER-AI", "0.2.4", None, "ai")
        self.assertEqual(self.agent.component_state("ai", True)["status"], "up_to_date")
        self.publish("ARMOR-STUDIO", "0.7.0", None, "studio")
        self.assertEqual(self.agent.component_state("studio", True)["status"], "ahead")
        FakeGitHub.releases.pop("ARMOR-VOICE-AI", None)
        self.agent._cache.clear()
        self.assertEqual(self.agent.component_state("voice", True)["status"], "unknown")

    # ---- installing ----
    def test_a_python_component_is_replaced_checked_and_kept(self) -> None:
        self.publish("ARMOR-NETWORK", "0.0.7", {"armor.project.json": b'{"version": "0.0.7"}', "src/armor_network/__init__.py": b'__version__ = "0.0.7"\n', "src/armor_network/new.py": b"x = 1\n"}, "network")
        view = self.wait(self.agent.update_job(["network"], False))
        self.assertEqual(view["state"], "done", view["log"])
        self.assertEqual(self.agent.installed_version("network"), "0.0.7")
        self.assertTrue((self.prefix / "apps/ARMOR-NETWORK/src/armor_network/new.py").exists())
        self.assertTrue(list((self.prefix / "releases-old").glob("maint-network-*")))
        self.assertIn("restart armor-network", self.calls.read_text(encoding="utf-8"))
        self.assertTrue(all(step["state"] == "done" for step in view["steps"]))
        # and back
        back = self.wait(self.agent.rollback_job("network"))
        self.assertEqual(back["state"], "done", back["log"])
        self.assertEqual(self.agent.installed_version("network"), "0.0.6")
        self.assertFalse((self.prefix / "apps/ARMOR-NETWORK/src/armor_network/new.py").exists())

    # ---- signatures ----
    def test_the_key_the_agent_trusts_is_the_one_the_firmware_trusts(self) -> None:
        header = HERE.parent.parent / "ARMOR-COMMON" / "firmware_base" / "core" / "fw_trust.hpp"
        if not header.is_file():
            self.skipTest("the firmware sources are not next to this repository")
        block = re.search(r"kPublicKey\[32\] = \{([^}]*)\}", header.read_text(encoding="utf-8"))
        assert block
        self.assertEqual("".join(f"{int(item, 16):02x}" for item in block.group(1).split(",")), self.real_key)

    def test_ed25519_matches_the_published_test_vector(self) -> None:
        public = bytes.fromhex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
        signature = bytes.fromhex("e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b")
        self.assertTrue(self.agent.ed25519_verify(public, b"", signature))
        self.assertFalse(self.agent.ed25519_verify(public, b"x", signature))
        self.assertFalse(self.agent.ed25519_verify(public, b"", signature[:-1] + bytes([signature[-1] ^ 1])))

    def test_a_signature_binds_the_component_the_version_and_the_hash(self) -> None:
        digest = "a" * 64
        good = self.key.sign(f"armor-pkg/1|ai|0.2.5|{digest}".encode())
        self.assertTrue(self.agent.package_signature_ok("ai", "0.2.5", digest, good))
        self.assertFalse(self.agent.package_signature_ok("voice", "0.2.5", digest, good))
        self.assertFalse(self.agent.package_signature_ok("ai", "0.2.6", digest, good))
        self.assertFalse(self.agent.package_signature_ok("ai", "0.2.5", "b" * 64, good))
        # what the firmware signs (another prefix, or the bare hash) can never pass as a package signature
        self.assertFalse(self.agent.package_signature_ok("ai", "0.2.5", digest, self.key.sign(f"armor-fw/1|ai|x|0.2.5|{digest}".encode())))
        self.assertFalse(self.agent.package_signature_ok("ai", "0.2.5", digest, self.key.sign(bytes.fromhex(digest))))

    def test_the_manifest_signature_binds_the_component_the_version_and_the_hash_and_is_not_a_firmware_one(self) -> None:
        digest = "a" * 64
        good = self.key.sign(f"armor-fw/1|ai|package|0.2.5|{digest}".encode())
        self.assertTrue(self.agent.manifest_signature_ok("ai", "0.2.5", digest, good))
        self.assertFalse(self.agent.manifest_signature_ok("voice", "0.2.5", digest, good))
        self.assertFalse(self.agent.manifest_signature_ok("ai", "0.2.6", digest, good))
        self.assertFalse(self.agent.manifest_signature_ok("ai", "0.2.5", "b" * 64, good))
        # a firmware image of a node (its project, a real board) signed with the same key is not a package, nor is the older text, the bare hash or a garbage line
        self.assertFalse(self.agent.manifest_signature_ok("ai", "0.2.5", digest, self.key.sign(f"armor-fw/1|ai|wifi|0.2.5|{digest}".encode())))
        self.assertFalse(self.agent.manifest_signature_ok("ai", "0.2.5", digest, self.key.sign(f"armor-pkg/1|ai|0.2.5|{digest}".encode())))
        self.assertFalse(self.agent.manifest_signature_ok("ai", "0.2.5", digest, self.key.sign(bytes.fromhex(digest))))
        self.assertFalse(self.agent.manifest_signature_ok("ai", "0.2.5", digest, "zz"))
        self.assertFalse(self.agent.manifest_signature_ok("ai", "0.2.5", digest, self.other_key.sign(f"armor-fw/1|ai|package|0.2.5|{digest}".encode())))
        # and the manifest is not the older text
        self.assertFalse(self.agent.package_signature_ok("ai", "0.2.5", digest, good))

    def test_a_package_with_only_the_older_signature_is_refused_unless_the_file_says_either(self) -> None:
        self.publish("ARMOR-SERVER-AI", "0.2.5", {"src/armor_server_ai/__init__.py": b'__version__ = "0.2.5"\n'}, "ai", signature="legacy")
        self.assertEqual(self.agent.signature_mode(), "manifest")
        self.assertEqual(self.agent.overview(False)["signature_mode"], "manifest")
        view = self.wait(self.agent.update_job(["ai"], False))
        self.assertEqual(view["state"], "failed")
        self.assertIn("missing_signature", view["error"])
        self.assertEqual(self.agent.installed_version("ai"), "0.2.4")
        # the process environment is not the file
        os.environ["ARMOR_MAINT_SIGNATURE"] = "either"
        try:
            self.assertEqual(self.agent.signature_mode(), "manifest")
        finally:
            del os.environ["ARMOR_MAINT_SIGNATURE"]
        self.maint_env.write_text("ARMOR_MAINT_SIGNATURE=either\n", encoding="utf-8")
        self.assertEqual(self.agent.overview(False)["signature_mode"], "either")
        view = self.wait(self.agent.update_job(["ai"], False))
        self.assertEqual(view["state"], "done", view["log"])
        self.assertIn("older .sig", str(view["log"]))
        self.assertEqual(self.agent.installed_version("ai"), "0.2.5")

    def test_a_bad_manifest_signature_is_not_saved_by_a_good_older_one_unless_either_and_then_the_older_decides(self) -> None:
        self.publish("ARMOR-SERVER-AI", "0.2.5", {"src/armor_server_ai/__init__.py": b'__version__ = "0.2.5"\n'}, "ai", signature="manifest")
        name = "armor-ai-0.2.5.tgz"
        FakeGitHub.assets[name + ".sig2"] = b"zz\n"
        view = self.wait(self.agent.update_job(["ai"], False))
        self.assertEqual((view["state"], "bad_signature" in view["error"]), ("failed", True))
        self.maint_env.write_text("ARMOR_MAINT_SIGNATURE=either\n", encoding="utf-8")
        view = self.wait(self.agent.update_job(["ai"], False))      # no .sig at all: still refused
        self.assertEqual(view["state"], "failed")
        self.assertEqual(self.agent.installed_version("ai"), "0.2.4")

    def test_the_keys_of_a_rotation_are_two_at_most_and_only_from_the_file(self) -> None:
        files = {"src/armor_server_ai/__init__.py": b'__version__ = "0.2.5"\n'}
        self.publish("ARMOR-SERVER-AI", "0.2.5", files, "ai", signature="other")
        self.assertEqual(self.agent.trusted_keys(), [self.key.public])
        self.assertEqual(self.wait(self.agent.update_job(["ai"], False))["state"], "failed")
        # the second key: from the file, 64 hexadecimal digits, not the process environment, not the same one twice, and not a value that is not a key
        os.environ["ARMOR_MAINT_NEXT_KEY"] = self.other_key.public
        try:
            self.assertEqual(self.agent.trusted_keys(), [self.key.public])
        finally:
            del os.environ["ARMOR_MAINT_NEXT_KEY"]
        for value in ("not a key", self.other_key.public[:-2], self.key.public):
            self.maint_env.write_text(f"ARMOR_MAINT_NEXT_KEY={value}\n", encoding="utf-8")
            self.assertEqual(self.agent.trusted_keys(), [self.key.public], value)
        self.maint_env.write_text(f"ARMOR_MAINT_NEXT_KEY={self.other_key.public}\n", encoding="utf-8")
        self.assertEqual(self.agent.trusted_keys(), [self.key.public, self.other_key.public])
        prints = self.agent.overview(False)["trusted_fingerprints"]
        self.assertEqual(prints, [self.agent.key_fingerprint(self.key.public), self.agent.key_fingerprint(self.other_key.public)])
        self.assertTrue(all(re.fullmatch(r"[0-9a-f]{16}", item) for item in prints) and prints[0] != prints[1])
        self.assertNotIn(self.key.public, json.dumps(self.agent.overview(False)))
        view = self.wait(self.agent.update_job(["ai"], False))
        self.assertEqual(view["state"], "done", view["log"])
        self.assertEqual(self.agent.installed_version("ai"), "0.2.5")

    def test_a_third_key_is_never_trusted(self) -> None:
        third = TestKey(Path(self.tmp.name), "third")
        self.maint_env.write_text(f"ARMOR_MAINT_NEXT_KEY={self.other_key.public}\n", encoding="utf-8")
        digest = "c" * 64
        self.assertFalse(self.agent.manifest_signature_ok("ai", "0.2.5", digest, third.sign(f"armor-fw/1|ai|package|0.2.5|{digest}".encode())))
        self.assertTrue(self.agent.manifest_signature_ok("ai", "0.2.5", digest, self.other_key.sign(f"armor-fw/1|ai|package|0.2.5|{digest}".encode())))

    def test_a_valid_signature_installs(self) -> None:
        self.publish("ARMOR-SERVER-AI", "0.2.5", {"src/armor_server_ai/__init__.py": b'__version__ = "0.2.5"\n'}, "ai")
        view = self.wait(self.agent.update_job(["ai"], False))
        self.assertEqual(view["state"], "done", view["log"])
        self.assertEqual(self.agent.installed_version("ai"), "0.2.5")
        self.assertIn("signature of the release verified", str(view["log"]))

    def test_a_tampered_package_is_refused(self) -> None:
        self.publish("ARMOR-SERVER-AI", "0.2.5", {"src/armor_server_ai/__init__.py": b'__version__ = "0.2.5"\n'}, "ai")
        # somebody swaps the package and its published hash, but cannot make a signature for them
        evil = tarball({"src/armor_server_ai/__init__.py": b'__version__ = "0.2.5"\n', "src/armor_server_ai/evil.py": b"x = 1\n"})
        FakeGitHub.assets["armor-ai-0.2.5.tgz"] = evil
        FakeGitHub.assets["armor-ai-0.2.5.tgz.sha256"] = f"{hashlib.sha256(evil).hexdigest()}  armor-ai-0.2.5.tgz\n".encode()
        view = self.wait(self.agent.update_job(["ai"], False))
        self.assertEqual(view["state"], "failed")
        self.assertIn("bad_signature", view["error"])
        self.assertEqual(self.agent.installed_version("ai"), "0.2.4")
        self.assertFalse((self.prefix / "ai" / "armor_server_ai" / "evil.py").exists())

    def test_a_release_without_a_signature_is_refused(self) -> None:
        self.publish("ARMOR-SERVER-AI", "0.2.5", {"src/armor_server_ai/__init__.py": b'__version__ = "0.2.5"\n'}, "ai", signature="none")
        view = self.wait(self.agent.update_job(["ai"], False))
        self.assertEqual(view["state"], "failed")
        self.assertIn("missing_signature", view["error"])
        self.assertEqual(self.agent.installed_version("ai"), "0.2.4")
        self.assertFalse(list((self.prefix / "releases-old").glob("maint-ai-*")) if (self.prefix / "releases-old").exists() else False)

    def test_a_signature_by_another_key_or_garbage_is_refused(self) -> None:
        for kind in ("other", "garbage"):
            self.publish("ARMOR-SERVER-AI", "0.2.5", {"src/armor_server_ai/__init__.py": b'__version__ = "0.2.5"\n'}, "ai", signature=kind)
            view = self.wait(self.agent.update_job(["ai"], False))
            self.assertEqual(view["state"], "failed", kind)
            self.assertIn("bad_signature", view["error"])
            self.assertEqual(self.agent.installed_version("ai"), "0.2.4")

    def test_the_override_works_only_from_the_environment_file(self) -> None:
        self.publish("ARMOR-SERVER-AI", "0.2.5", {"src/armor_server_ai/__init__.py": b'__version__ = "0.2.5"\n'}, "ai", signature="none")
        # the process environment is not the file
        os.environ["ARMOR_MAINT_ALLOW_UNSIGNED"] = "1"
        try:
            self.assertFalse(self.agent.unsigned_allowed())
            self.assertEqual(self.wait(self.agent.update_job(["ai"], False))["state"], "failed")
        finally:
            del os.environ["ARMOR_MAINT_ALLOW_UNSIGNED"]
        self.assertFalse(self.agent.overview(False)["unsigned_allowed"])
        # any other value in the file is not the override
        self.maint_env.write_text("ARMOR_MAINT_ALLOW_UNSIGNED=0\n", encoding="utf-8")
        self.assertFalse(self.agent.unsigned_allowed())
        # the file with the setting is, and the log says so loudly
        self.maint_env.write_text("ARMOR_MAINT_TOKEN=x\nARMOR_MAINT_ALLOW_UNSIGNED=1\n", encoding="utf-8")
        self.assertTrue(self.agent.overview(False)["unsigned_allowed"])
        view = self.wait(self.agent.update_job(["ai"], False))
        self.assertEqual(view["state"], "done", view["log"])
        self.assertIn("WARNING", str(view["log"]))
        self.assertEqual(self.agent.installed_version("ai"), "0.2.5")

    def test_a_wrong_hash_changes_nothing(self) -> None:
        self.publish("ARMOR-SERVER-AI", "0.2.5", {"src/armor_server_ai/__init__.py": b'__version__ = "0.2.5"\n'}, "ai", good_hash=False)
        view = self.wait(self.agent.update_job(["ai"], False))
        self.assertEqual(view["state"], "failed")
        self.assertIn("checksum_mismatch", view["error"])
        self.assertEqual(self.agent.installed_version("ai"), "0.2.4")

    def test_an_archive_that_reaches_outside_is_refused(self) -> None:
        self.publish("ARMOR-SERVER-AI", "0.2.6", {"../escape.txt": b"x", "src/armor_server_ai/__init__.py": b'__version__ = "0.2.6"\n'}, "ai")
        view = self.wait(self.agent.update_job(["ai"], False))
        self.assertEqual(view["state"], "failed")
        self.assertIn("unsafe_archive", view["error"])
        self.assertEqual(self.agent.installed_version("ai"), "0.2.4")
        self.assertFalse((self.prefix.parent / "escape.txt").exists())

    def test_a_release_without_a_published_hash_is_not_installed(self) -> None:
        name = "armor-ai-0.2.7.tgz"
        FakeGitHub.assets[name] = tarball({"src/armor_server_ai/__init__.py": b'__version__ = "0.2.7"\n'})
        FakeGitHub.releases["ARMOR-SERVER-AI"] = {"tag_name": "v0.2.7", "assets": [{"name": name, "browser_download_url": f"{self.base}/assets/{name}"}]}
        self.agent._cache.clear()
        view = self.wait(self.agent.update_job(["ai"], False))
        self.assertEqual(view["state"], "failed")
        self.assertIn("no_checksum", view["error"])

    def test_the_server_gets_a_new_release_folder_and_the_old_one_stays(self) -> None:
        self.publish("ARMOR-SERVER", "0.5.5", {"server/dist/server.mjs": b"new", "server/package.json": b'{"version":"0.5.5"}', "server/package-lock.json": b'{"lock": 1}'}, "server")
        before = os.readlink(self.prefix / "current")
        view = self.wait(self.agent.update_job(["server"], False))
        self.assertEqual(view["state"], "done", view["log"])
        after = os.readlink(self.prefix / "current")
        self.assertNotEqual(before, after)
        self.assertEqual(self.agent.installed_version("server"), "0.5.5")
        self.assertEqual((Path(after) / "server/dist/server.mjs").read_text(encoding="utf-8"), "new")
        self.assertEqual((Path(before) / "server/dist/server.mjs").read_text(encoding="utf-8"), "old")       # the old folder is untouched
        self.assertEqual(self.agent.installed_version("studio"), "0.7.1")                                        # the other part came along unchanged
        back = self.wait(self.agent.rollback_job("server"))
        self.assertEqual(back["state"], "done", back["log"])
        self.assertEqual(self.agent.installed_version("server"), "0.5.4")

    def test_a_server_that_does_not_answer_is_put_back(self) -> None:
        self.publish("ARMOR-SERVER", "0.5.6", {"server/dist/server.mjs": b"broken", "server/package.json": b'{"version":"0.5.6"}'}, "server")
        before = os.readlink(self.prefix / "current")
        FakeGitHub.healthy = False
        try:
            original = self.agent.healthy
            self.agent.healthy = lambda component, unit, wait=40.0: original(component, unit, wait=3.0)
            view = self.wait(self.agent.update_job(["server"], False))
        finally:
            self.agent.healthy = original
            FakeGitHub.healthy = True
        self.assertEqual(view["state"], "failed")
        self.assertIn("unhealthy_rolled_back", view["error"])
        self.assertEqual(os.readlink(self.prefix / "current"), before)

    # ---- trying the new server before the switch (blue/green) ----
    def stand_in_node(self) -> Path:
        """A stand-in for `node`: it answers /healthz on ARMOR_PORT when the server file says `ok`, exits when it says `crash`, and never answers when it says `hang`; it writes down what it was given."""
        script = self.prefix.parent / "fake-node"
        report = self.prefix.parent / "staging-report.json"
        source = """#!/usr/bin/env python3
import http.server, json, os, sys, time
mode = open(sys.argv[1]).read().strip()
keys = ("ARMOR_PORT", "ARMOR_HOST", "ARMOR_DATA_DIR", "ARMOR_MQTT_URL", "ARMOR_SECRET", "TLS_CERT_PATH")
seen = {key: os.environ.get(key) for key in keys}
seen.update({"empty": os.listdir(os.environ["ARMOR_DATA_DIR"]), "mode": mode, "cwd": os.getcwd()})
json.dump(seen, open(REPORT, "w"))
if mode == "crash":
    print("boom: the new server cannot start")
    sys.exit(1)
if mode == "hang":
    time.sleep(60)


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        body = b'{"ok":true}'
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


http.server.HTTPServer(("127.0.0.1", int(os.environ["ARMOR_PORT"])), H).serve_forever()
"""
        script.write_text(source.replace("REPORT", repr(str(report))), encoding="utf-8")
        script.chmod(0o755)
        report.unlink(missing_ok=True)
        return script

    def with_staging(self, mode: str, setting: str = "on"):
        node = self.stand_in_node()
        (self.prefix / "etc").mkdir(parents=True, exist_ok=True)
        (self.prefix / "etc" / "armor.env").write_text("ARMOR_SECRET=s3cret\nARMOR_PORT=18080\nTLS_CERT_PATH=/x/cert.pem\nARMOR_MQTT_URL=mqtt://127.0.0.1:18883\n", encoding="utf-8")
        self.maint_env.write_text(f"ARMOR_MAINT_STAGING={setting}\nARMOR_MAINT_STAGING_WAIT_S=5\n", encoding="utf-8")
        self.publish("ARMOR-SERVER", "0.5.7", {"server/dist/server.mjs": mode.encode(), "server/package.json": b'{"version":"0.5.7"}'}, "server")
        original = self.agent.NODE_BINARY
        self.agent.NODE_BINARY = str(node)
        try:
            return self.wait(self.agent.update_job(["server"], False))
        finally:
            self.agent.NODE_BINARY = original

    def test_a_server_that_answers_on_the_side_is_switched_to(self) -> None:
        before = os.readlink(self.prefix / "current")
        view = self.with_staging("ok")
        self.assertEqual(view["state"], "done", view["log"])
        self.assertNotEqual(os.readlink(self.prefix / "current"), before)
        report = json.loads((self.prefix.parent / "staging-report.json").read_text(encoding="utf-8"))
        self.assertNotEqual(report["ARMOR_PORT"], "18080")                          # its own port, not the one in use
        self.assertEqual(report["ARMOR_HOST"], "127.0.0.1")
        self.assertEqual(report["ARMOR_SECRET"], "s3cret")                          # the settings of the real server came along
        self.assertIsNone(report["ARMOR_MQTT_URL"])                                  # but not the broker (a second client of the same name would throw the real one out)
        self.assertIsNone(report["TLS_CERT_PATH"])                                   # plain http on the loopback
        self.assertEqual(report["empty"], [])                                        # an empty data folder, never the real one
        self.assertNotIn(str(self.prefix / "data"), str(report["ARMOR_DATA_DIR"]))
        steps = {item["id"]: item["state"] for item in view["steps"]}
        self.assertEqual(steps["server.stage"], "done")
        self.assertIn("trying the new server", "\n".join(view["log"]))

    def test_a_server_that_does_not_start_on_the_side_never_replaces_the_running_one(self) -> None:
        before = os.readlink(self.prefix / "current")
        folders = sorted(path.name for path in (self.prefix / "releases").iterdir())
        view = self.with_staging("crash")
        self.assertEqual(view["state"], "failed")
        self.assertIn("staging_failed", view["error"])
        self.assertEqual(os.readlink(self.prefix / "current"), before)              # nothing was switched
        self.assertEqual(sorted(path.name for path in (self.prefix / "releases").iterdir()), folders)   # the useless folder is gone
        self.assertNotIn("restart armor-server", self.calls.read_text(encoding="utf-8"))   # and the running server was not even restarted: no cut
        self.assertIn("boom: the new server cannot start", "\n".join(view["log"]))
        self.assertIn("nothing was switched", "\n".join(view["log"]))

    def test_a_server_that_never_answers_on_the_side_is_stopped_and_refused(self) -> None:
        before = os.readlink(self.prefix / "current")
        started = time.time()
        view = self.with_staging("hang")
        self.assertEqual(view["state"], "failed")
        self.assertIn("staging_failed", view["error"])
        self.assertLess(time.time() - started, 30)                                   # the wait of the setting (5 s), not the 60 s of the stand-in
        self.assertEqual(os.readlink(self.prefix / "current"), before)

    def test_without_the_setting_the_server_is_switched_as_before_and_never_tried(self) -> None:
        for setting in ("off", "maybe", "1"):                          # off, a word that is not `on`, and a number: all keep the old behaviour
            self.setUp()
            view = self.with_staging("crash", setting)                               # a server that would fail the trial passes, because the trial is not made
            self.assertEqual(view["state"], "done", (setting, view["log"]))
            self.assertEqual({item["id"]: item["state"] for item in view["steps"]}["server.stage"], "skipped")
            self.assertFalse((self.prefix.parent / "staging-report.json").exists(), setting)

    def test_the_wait_of_the_trial_is_limited(self) -> None:
        for text, wanted in (("", 30.0), ("1", 5.0), ("45", 45.0), ("9999", 120.0), ("abc", 30.0)):
            self.maint_env.write_text(f"ARMOR_MAINT_STAGING_WAIT_S={text}\n", encoding="utf-8")
            self.assertEqual(self.agent.staging_wait(), wanted, text)

    def unhealthy_update(self, component: str):
        """Runs an update after which the health check says no: the server's address answers not-ok, and for the others systemctl reports the unit failed (three seconds of waiting, not forty)."""
        failing = self.prefix.parent / "systemctl-failed"
        failing.write_text(f'#!/bin/sh\necho "$@" >> "{self.calls}"\nif [ "$1" = "is-active" ]; then echo failed; fi\nexit 0\n', encoding="utf-8")
        failing.chmod(0o755)
        FakeGitHub.healthy = False
        original, original_systemctl = self.agent.healthy, self.agent.SYSTEMCTL
        self.agent.healthy = lambda name, unit, wait=40.0: original(name, unit, wait=3.0)
        self.agent.SYSTEMCTL = str(failing)
        try:
            return self.wait(self.agent.update_job([component], False))
        finally:
            self.agent.healthy, self.agent.SYSTEMCTL = original, original_systemctl
            FakeGitHub.healthy = True

    def test_a_python_package_that_does_not_answer_is_put_back(self) -> None:
        self.publish("ARMOR-SERVER-AI", "0.2.5", {"src/armor_server_ai/__init__.py": b'__version__ = "0.2.5"\n', "src/armor_server_ai/new.py": b"x = 1\n"}, "ai")
        view = self.unhealthy_update("ai")
        self.assertEqual(view["state"], "failed")
        self.assertIn("unhealthy_rolled_back", view["error"])
        self.assertEqual(self.agent.installed_version("ai"), "0.2.4")
        self.assertFalse((self.prefix / "ai" / "armor_server_ai" / "new.py").exists())
        self.assertGreaterEqual(self.calls.read_text(encoding="utf-8").count("restart armor-server-ai"), 2)   # restarted with the new code, and again with the old

    def test_a_python_program_that_does_not_answer_gets_its_files_back(self) -> None:
        self.publish("ARMOR-NETWORK", "0.0.7", {"armor.project.json": b'{"version": "0.0.7"}', "src/armor_network/__init__.py": b'__version__ = "0.0.7"\n', "src/armor_network/new.py": b"x = 1\n"}, "network")
        view = self.unhealthy_update("network")
        self.assertEqual(view["state"], "failed")
        self.assertIn("unhealthy_rolled_back", view["error"])
        self.assertEqual(self.agent.installed_version("network"), "0.0.6")
        self.assertFalse((self.prefix / "apps/ARMOR-NETWORK/src/armor_network/new.py").exists())
        self.assertEqual(json.loads((self.prefix / "apps/ARMOR-NETWORK/armor.project.json").read_text(encoding="utf-8"))["version"], "0.0.6")

    def test_a_package_that_lacks_its_package_folder_is_refused_and_changes_nothing(self) -> None:
        self.publish("ARMOR-SERVER-AI", "0.2.5", {"readme.txt": b"nothing useful"}, "ai")
        view = self.wait(self.agent.update_job(["ai"], False))
        self.assertEqual(view["state"], "failed")
        self.assertIn("bad_archive", view["error"])
        self.assertEqual(self.agent.installed_version("ai"), "0.2.4")
        self.assertEqual(self.calls.read_text(encoding="utf-8").count("restart"), 0)

    def test_the_helper_scripts_are_replaced_with_the_right_modes_and_the_old_ones_kept(self) -> None:
        bin_folder = self.prefix / "bin"
        (bin_folder / "backup_data.sh").write_text("old backup\n", encoding="utf-8")
        (bin_folder / "VERSION").write_text("0.4.7\n", encoding="utf-8")
        (bin_folder / "unrelated.sh").write_text("not ours\n", encoding="utf-8")
        files = {"scripts/backup_data.sh": b"new backup\n", "scripts/armor_admin_agent.py": b"print('admin')\n", "scripts/VERSION": b"0.4.8\n", "scripts/evil.sh": b"rm -rf /\n"}
        self.publish("ARMOR-DEVOPS", "0.4.8", files, "devops")
        calls = self.prefix.parent / "systemd-run.log"
        stand_in = self.prefix.parent / "stand-in-bin"
        stand_in.mkdir(exist_ok=True)
        (stand_in / "systemd-run").write_text(f'#!/bin/sh\necho "$@" >> "{calls}"\n', encoding="utf-8")
        (stand_in / "systemd-run").chmod(0o755)
        saved = os.environ["PATH"]
        os.environ["PATH"] = str(stand_in) + os.pathsep + saved
        try:
            view = self.wait(self.agent.update_job(["devops"], False))
        finally:
            os.environ["PATH"] = saved
        self.assertEqual(view["state"], "done", view["log"])
        self.assertEqual((bin_folder / "backup_data.sh").read_text(encoding="utf-8"), "new backup\n")
        self.assertEqual((bin_folder / "VERSION").read_text(encoding="utf-8"), "0.4.8\n")
        self.assertTrue(os.access(bin_folder / "backup_data.sh", os.X_OK))
        self.assertTrue(os.access(bin_folder / "armor_admin_agent.py", os.X_OK))
        self.assertFalse(os.access(bin_folder / "VERSION", os.X_OK))
        self.assertFalse((bin_folder / "evil.sh").exists())                                  # only the closed list of names is copied
        self.assertEqual((bin_folder / "unrelated.sh").read_text(encoding="utf-8"), "not ours\n")
        (kept,) = (self.prefix / "releases-old").glob("maint-devops-*")
        self.assertEqual((kept / "backup_data.sh").read_text(encoding="utf-8"), "old backup\n")
        self.assertIn("armor-admin armor-maintenance", calls.read_text(encoding="utf-8"))   # the services that run them restart later, from outside
        self.assertEqual(self.calls.read_text(encoding="utf-8").count("restart"), 0)      # the helper does not restart itself while it works
        self.assertEqual(view["result"]["components"]["devops"]["backup"], kept.name)

    def test_the_helper_scripts_package_without_a_scripts_folder_is_refused(self) -> None:
        self.publish("ARMOR-DEVOPS", "0.4.8", {"src/other.py": b"x"}, "devops")
        view = self.wait(self.agent.update_job(["devops"], False))
        self.assertEqual(view["state"], "failed")
        self.assertIn("bad_archive", view["error"])

    def test_going_back_when_there_is_nothing_to_go_back_to_says_so(self) -> None:
        view = self.wait(self.agent.rollback_job("ai"))
        self.assertEqual(view["state"], "failed")
        self.assertIn("nothing_to_go_back_to", view["error"])
        view = self.wait(self.agent.rollback_job("server"))                   # the only release folder is the current one
        self.assertEqual(view["state"], "failed")
        self.assertIn("nothing_to_go_back_to", view["error"])

    def test_going_back_restores_the_newest_copy_of_a_python_package(self) -> None:
        self.publish("ARMOR-SERVER-AI", "0.2.5", {"src/armor_server_ai/__init__.py": b'__version__ = "0.2.5"\n'}, "ai")
        self.assertEqual(self.wait(self.agent.update_job(["ai"], False))["state"], "done")
        self.assertEqual(self.agent.installed_version("ai"), "0.2.5")
        back = self.wait(self.agent.rollback_job("ai"))
        self.assertEqual(back["state"], "done", back["log"])
        self.assertEqual(self.agent.installed_version("ai"), "0.2.4")

    def test_archives_with_links_devices_or_parent_references_are_never_unpacked(self) -> None:
        folder = self.prefix.parent / "archives"
        folder.mkdir(exist_ok=True)

        def archive(name: str, member: tarfile.TarInfo, content: bytes = b"") -> Path:
            path = folder / name
            with tarfile.open(path, "w:gz") as tar:
                tar.addfile(member, io.BytesIO(content))
            return path

        link = tarfile.TarInfo("src/link")
        link.type = tarfile.SYMTYPE
        link.linkname = "/etc/passwd"
        fifo = tarfile.TarInfo("src/pipe")
        fifo.type = tarfile.FIFOTYPE
        absolute = tarfile.TarInfo("/tmp/armor-escape")
        absolute.size = 1
        parent = tarfile.TarInfo("src/../../escape")
        parent.size = 1
        for name, member in (("link.tgz", link), ("fifo.tgz", fifo), ("absolute.tgz", absolute), ("parent.tgz", parent)):
            destination = folder / (name + ".out")
            destination.mkdir(exist_ok=True)
            with self.assertRaises(self.agent.Refused, msg=name) as caught:
                self.agent.safe_extract(archive(name, member, b"x" if member.size else b""), destination)
            self.assertEqual(caught.exception.code, "unsafe_archive")
            self.assertEqual(list(destination.iterdir()), [], name)

    def test_the_settings_file_is_read_as_plain_pairs(self) -> None:
        path = self.prefix.parent / "settings.env"
        path.write_text("# comment\nA=1\n\nB = two words \nlower=case\nbroken line\nC=a=b\n", encoding="utf-8")
        self.assertEqual(self.agent.read_settings(path), {"A": "1", "C": "a=b"})
        self.assertEqual(self.agent.read_settings(self.prefix.parent / "missing.env"), {})

    def test_old_copies_are_pruned_per_component_and_the_installers_are_left_alone(self) -> None:
        old = self.prefix / "releases-old"
        old.mkdir(exist_ok=True)
        now = time.time()
        for index in range(9):
            folder = old / f"maint-voice-{index}"
            folder.mkdir()
            os.utime(folder, (now + index, now + index))
        (old / "maint-ai-1").mkdir()
        (old / "20261016-000000").mkdir()
        self.agent.prune_old(old, "maint-voice-")
        voice = sorted(entry.name for entry in old.glob("maint-voice-*"))
        self.assertEqual(len(voice), self.agent.KEEP_OLD)
        self.assertIn("maint-voice-8", voice)
        self.assertNotIn("maint-voice-0", voice)
        self.assertTrue((old / "maint-ai-1").exists())
        self.assertTrue((old / "20261016-000000").exists())

    def test_a_nearly_full_disk_loses_its_oldest_copies_first_but_never_the_newest_or_the_active_one(self) -> None:
        releases = self.prefix / "releases"
        releases.mkdir(exist_ok=True)
        for index in range(self.agent.KEEP_OLD):
            (releases / f"2026101{index}-000000").mkdir()
        active = releases / "20261010-000000"
        free = [10 * 1024 * 1024]                       # 10 MB free, the floor is 500 MB
        def usage(path):
            return type("Usage", (), {"free": free[0]})()
        self.agent.DISK_USAGE = usage
        self.agent.prune_old(releases, protect=(active,))
        names = sorted(entry.name for entry in releases.iterdir())
        self.assertEqual(names, ["20261010-000000", "20261015-000000"], "only the one in use and the newest are left")

    def test_the_copies_stop_going_when_there_is_room_again_and_the_floor_is_a_setting(self) -> None:
        releases = self.prefix / "releases"
        releases.mkdir(exist_ok=True)
        for index in range(self.agent.KEEP_OLD):
            (releases / f"2026101{index}-000000").mkdir()
        def usage(path):
            return type("Usage", (), {"free": (400 + 150 * (self.agent.KEEP_OLD - len(list(releases.iterdir())))) * 1024 * 1024})()
        self.agent.DISK_USAGE = usage
        self.agent.prune_old(releases)
        left = sorted(entry.name for entry in releases.iterdir())
        self.assertEqual(len(left), self.agent.KEEP_OLD - 1, "one copy gave the room that was missing")
        self.assertNotIn("20261010-000000", left)
        # the floor is read from the settings file: 0 turns it off, a bad value is the default
        self.assertEqual(self.agent.min_free_bytes(), 500 * 1024 * 1024)
        self.maint_env.write_text("ARMOR_MAINT_MIN_FREE_MB=0\n", encoding="utf-8")
        self.assertEqual(self.agent.min_free_bytes(), 0)
        self.maint_env.write_text("ARMOR_MAINT_MIN_FREE_MB=lots\n", encoding="utf-8")
        self.assertEqual(self.agent.min_free_bytes(), 500 * 1024 * 1024)
        self.maint_env.write_text("ARMOR_MAINT_MIN_FREE_MB=2048\n", encoding="utf-8")
        self.assertEqual(self.agent.min_free_bytes(), 2048 * 1024 * 1024)
        self.maint_env.write_text("ARMOR_MAINT_MIN_FREE_MB=0\n", encoding="utf-8")
        self.agent.DISK_USAGE = lambda path: type("Usage", (), {"free": 1})()
        before = len(list(releases.iterdir()))
        self.agent.prune_old(releases)
        self.assertEqual(len(list(releases.iterdir())), before, "with the floor off nothing more goes")

    CA_PEM = """-----BEGIN CERTIFICATE-----
MIIBoDCCAUegAwIBAgIUPfPshr4Eb3mV74kEv9qGieOcCwUwCgYIKoZIzj0EAwIw
JTEjMCEGA1UEAwwaQVJNT1IgVGVzdCBMb2NhbCBBdXRob3JpdHkwIBcNMjYxMDIz
MTkyNzMwWhgPMjEyNjA5MjkxOTI3MzBaMCUxIzAhBgNVBAMMGkFSTU9SIFRlc3Qg
TG9jYWwgQXV0aG9yaXR5MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEKUcMwzBV
32BNQgj4tNq5MePPgzGWikgb23f2YD3z76yFzhF2dCDFFndT8C4KEHJC0eIqhTdY
HWOIYWLExr93P6NTMFEwHQYDVR0OBBYEFMe8GLKFhRsx34EB6UBK1ervXAdkMB8G
A1UdIwQYMBaAFMe8GLKFhRsx34EB6UBK1ervXAdkMA8GA1UdEwEB/wQFMAMBAf8w
CgYIKoZIzj0EAwIDRwAwRAIgL47fw4JQEAgCHps2ltPX/FTlW875zxwNsSYyzFIj
SToCID/Tnl749Xyavje+uW2Avtcf/y5Kwy5X4vsDAWQuAWBQ
-----END CERTIFICATE-----
"""

    def test_the_pin_of_the_installations_authority_is_the_one_a_phone_pins(self) -> None:
        # a stand-in authority (made with openssl for this test only): the pin is the SHA-256 of its public key, in base64, as the phone computes it
        folder = self.prefix / "tls"
        folder.mkdir(exist_ok=True)
        (folder / "root.crt").write_text(self.CA_PEM, encoding="utf-8")
        self.assertEqual(self.agent.tls_ca_info(), {"present": False}, "nothing is claimed while no authority is set")
        self.maint_env.write_text("ARMOR_TLS_CA_FILE=%s\n" % (folder / "root.crt"), encoding="utf-8")
        info = self.agent.tls_ca_info()
        self.assertEqual(info["pin"], "fRsI9SH78MeN93Xk+x0jam6g1I38j9Bv3yYxAwFoKZs=")
        self.assertIn("ARMOR Test Local Authority", str(info["subject"]))
        self.assertTrue(str(info["not_after"]).endswith("2126 GMT"))
        self.assertNotIn("PRIVATE", json.dumps(info))
        # a file that is not a certificate is said, not guessed
        (folder / "root.crt").write_text("not a certificate\n", encoding="utf-8")
        self.assertEqual(self.agent.tls_ca_info(), {"present": True, "error": "unreadable_certificate"})
        # a relative path in the settings is never followed
        self.maint_env.write_text("ARMOR_TLS_CA_FILE=tls/root.crt\n", encoding="utf-8")
        self.assertEqual(self.agent.tls_ca_info(), {"present": False})

    def test_the_release_just_made_is_never_the_one_pruned(self) -> None:
        releases = self.prefix / "releases"
        releases.mkdir(exist_ok=True)
        long_ago = time.time() - 86400
        for index in range(self.agent.KEEP_OLD):
            folder = releases / f"2026101{index}-000000"
            folder.mkdir()
            os.utime(folder, (long_ago, long_ago))
        newest = releases / "20261017-201003"          # a copy keeps the old time of the folder it was copied from
        newest.mkdir()
        os.utime(newest, (long_ago - 1000, long_ago - 1000))
        self.agent.prune_old(releases, protect=(newest,))
        names = sorted(entry.name for entry in releases.iterdir())
        self.assertIn("20261017-201003", names)
        self.assertEqual(len(names), self.agent.KEEP_OLD)
        self.assertNotIn("20261010-000000", names)

    def test_the_release_current_points_to_is_never_pruned(self) -> None:
        releases = self.prefix / "releases"
        releases.mkdir(exist_ok=True)
        for index in range(self.agent.KEEP_OLD + 2):
            (releases / f"2026101{index}-000000").mkdir()
        active = releases / "20261010-000000"
        self.agent.prune_old(releases, protect=(active,))
        self.assertTrue(active.exists())

    def test_the_machine_is_not_restarted_while_something_is_being_installed(self) -> None:
        busy = self.agent.Job("system", [("upgrade", "Upgrade")])
        self.agent.JOBS[busy.id] = busy
        try:
            with self.assertRaises(self.agent.Refused) as caught:
                self.agent.reboot_machine()
            self.assertEqual(caught.exception.code, "busy")
        finally:
            del self.agent.JOBS[busy.id]

    def test_the_list_of_operations_can_be_emptied(self) -> None:
        self.fake_apt()
        self.wait(self.agent.system_check_job())
        self.assertGreaterEqual(len(self.agent.history()), 1)
        count = self.agent.clear_history()
        self.assertGreaterEqual(count, 1)
        self.assertEqual(self.agent.history(), [])
        self.assertEqual(self.agent.clear_history(), 0)         # emptying an empty list is not an error

    # ---- the console ----
    def test_the_console_runs_a_command_and_remembers_the_folder(self) -> None:
        job = self.agent.console_run("echo hello; cd /tmp; pwd", "/", 20)
        deadline = time.time() + 10
        view = job
        while time.time() < deadline:
            view = self.agent.CONSOLE_JOBS[job["id"]].view(0)
            if view["state"] != "running":
                break
            time.sleep(0.1)
        self.assertEqual(view["state"], "done")
        self.assertEqual(view["code"], 0)
        self.assertIn("hello", view["output"])
        self.assertNotIn("__ARMOR_PWD__", view["output"])
        self.assertEqual(view["cwd"], "/tmp")

    def test_the_console_stops_a_command_that_takes_too_long(self) -> None:
        job = self.agent.console_run("sleep 30", "/", 1)
        deadline = time.time() + 10
        view = job
        while time.time() < deadline:
            view = self.agent.CONSOLE_JOBS[job["id"]].view(0)
            if view["state"] != "running":
                break
            time.sleep(0.1)
        self.assertEqual(view["state"], "timeout")

    def test_the_console_is_off_unless_it_was_turned_on(self) -> None:
        self.agent.CONSOLE_ENABLED = False
        try:
            with self.assertRaises(self.agent.Refused) as caught:
                self.agent.console_run("id", "/", 5)
            self.assertEqual(caught.exception.code, "console_disabled")
        finally:
            self.agent.CONSOLE_ENABLED = True
        with self.assertRaises(self.agent.Refused):
            self.agent.console_run("   ", "/", 5)

    # ---- the operating system ----
    def fake_apt(self, fail: bool = False) -> None:
        root = Path(self.tmp.name)
        apt = root / "apt"
        apt.write_text("""#!/bin/sh
echo "Listing..."
echo "libfoo/stable 1.2 arm64 [upgradable from: 1.1]"
echo "bar/stable 2.0 all [upgradable from: 1.9]"
""", encoding="utf-8")
        aptget = root / "apt-get"
        aptget.write_text("""#!/bin/sh
fd=""
for a in "$@"; do case "$a" in APT::Status-Fd=*) fd="${a#APT::Status-Fd=}";; esac; done
echo "$@" >> "$(dirname "$0")/apt-calls.txt"
if [ "$1" = "update" ]; then echo "Hit:1 http://deb stable InRelease"; exit 0; fi
if [ "$1" = "-s" ]; then echo "The following packages have been kept back:"; echo "  linux-image-rpi-2712 rpi-swap"; echo "0 upgraded, 0 newly installed"; exit 0; fi
if [ -n "$fd" ]; then echo "dlstatus:1:40.0:Downloading" >&$fd; echo "dlstatus:2:100.0:Downloading" >&$fd; echo "pmstatus:libfoo:0.0:Preparing" >&$fd; echo "pmstatus:libfoo:100.0:Installed" >&$fd; fi
echo "Setting up libfoo"
exit """ + ("100" if fail else "0") + chr(10), encoding="utf-8")
        dpkg = root / "dpkg"
        dpkg.write_text("""#!/bin/sh
echo "dpkg $@" >> "$(dirname "$0")/apt-calls.txt"
if [ "$1" = "--audit" ]; then echo "The following packages are only half configured:"; echo " raspi-firmware  firmware for the Raspberry Pi"; exit 0; fi
echo "Setting up raspi-firmware"
exit 0
""", encoding="utf-8")
        for script in (apt, aptget, dpkg):
            script.chmod(script.stat().st_mode | stat.S_IEXEC)
        self.agent.APT, self.agent.APT_GET, self.agent.DPKG = str(apt), str(aptget), str(dpkg)
        self.agent._ATTENTION["at"] = 0.0

    def test_the_packages_that_can_be_upgraded_are_listed(self) -> None:
        self.fake_apt()
        packages = self.agent.upgradable()
        self.assertEqual([item["name"] for item in packages], ["libfoo", "bar"])
        self.assertEqual(packages[0]["from"], "1.1")
        self.assertEqual(packages[0]["to"], "1.2")

    def test_the_system_check_counts_what_can_be_upgraded(self) -> None:
        self.fake_apt()
        view = self.wait(self.agent.system_check_job())
        self.assertEqual(view["state"], "done", view["log"])
        self.assertEqual(view["result"], {"upgradable": 2})

    def test_the_system_upgrade_follows_the_progress_of_apt(self) -> None:
        self.fake_apt()
        view = self.wait(self.agent.system_upgrade_job())
        self.assertEqual(view["state"], "done", view["log"])
        self.assertEqual(view["percent"], 100)
        self.assertTrue(all(step["state"] == "done" for step in view["steps"]), view["steps"])
        self.assertTrue(any("Setting up libfoo" in line for line in view["log"]))
        self.assertEqual(view["result"]["upgraded"], 2)

    def apt_calls(self) -> str:
        path = Path(self.tmp.name) / "apt-calls.txt"
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def test_a_full_upgrade_uses_full_upgrade_and_a_plain_one_does_not(self) -> None:
        self.fake_apt()
        self.assertEqual(self.wait(self.agent.system_upgrade_job("upgrade"))["state"], "done")
        self.assertNotIn("full-upgrade", self.apt_calls())
        view = self.wait(self.agent.system_upgrade_job("full"))
        self.assertEqual(view["state"], "done", view["log"])
        self.assertIn("full-upgrade", self.apt_calls())

    def test_a_repair_finishes_the_half_installed_packages_and_fixes_the_dependencies(self) -> None:
        self.fake_apt()
        view = self.wait(self.agent.system_upgrade_job("repair"))
        self.assertEqual(view["state"], "done", view["log"])
        self.assertEqual([step["id"] for step in view["steps"]], ["configure", "fix"])
        self.assertIn("dpkg --configure -a", self.apt_calls())
        self.assertIn("-f", self.apt_calls())

    def test_the_unit_of_the_helper_can_write_where_a_kernel_package_writes(self) -> None:
        installer = (Path(__file__).parent / "install_cm5.sh").read_text(encoding="utf-8")
        start = installer.index("armor-maintenance.service <<EOF") if "armor-maintenance.service <<EOF" in installer else installer.index("Description=A.R.M.O.R. maintenance helper")
        unit = installer[start:installer.index("[Install]", start)]
        unit = " ".join(line for line in unit.splitlines() if not line.lstrip().startswith("#"))   # what the unit sets, not what its comments say
        self.assertNotIn("ProtectKernelModules", unit)
        self.assertNotIn("ProtectSystem", unit)
        self.assertIn("MemoryMax=1G", unit)

    def test_an_unknown_mode_is_refused(self) -> None:
        self.fake_apt()
        with self.assertRaises(self.agent.Refused):
            self.agent.system_upgrade_job("everything")

    def test_what_a_plain_upgrade_keeps_back_and_what_is_half_installed_are_reported(self) -> None:
        self.fake_apt()
        state = self.agent.system_attention()
        self.assertEqual(state["kept_back"], ["linux-image-rpi-2712", "rpi-swap"])
        self.assertEqual(state["broken"], ["raspi-firmware"])

    def test_a_system_upgrade_that_fails_says_so(self) -> None:
        self.fake_apt(fail=True)
        view = self.wait(self.agent.system_upgrade_job())
        self.assertEqual(view["state"], "failed")
        self.assertEqual(view["error"], "apt_upgrade_failed")

    def test_only_one_change_is_accepted_at_a_time(self) -> None:
        self.fake_apt()
        socket_path = str(Path(self.tmp.name) / "busy.sock")
        self.agent.Handler.token = TOKEN
        server = self.agent.UnixServer(socket_path, self.agent.Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        gate = threading.Lock()
        gate.acquire()
        job = self.agent.Job("system-check", [("refresh", "x")], label="held")
        self.agent.remember(job)
        try:
            connection = UnixConnection(socket_path)
            connection.request("POST", "/v1/system/upgrade", body="{}", headers={"X-Armor-Maint-Token": TOKEN, "Content-Type": "application/json"})
            self.assertEqual(connection.getresponse().status, 409)
        finally:
            job.finish()
            server.shutdown()
            server.server_close()

    # ---- the socket ----
    def test_the_socket_wants_the_token_and_answers_the_overview(self) -> None:
        socket_path = str(Path(self.tmp.name) / "maint.sock")
        self.agent.Handler.token = TOKEN
        server = self.agent.UnixServer(socket_path, self.agent.Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            connection = UnixConnection(socket_path)
            connection.request("GET", "/v1/overview")
            self.assertEqual(connection.getresponse().status, 401)
            connection = UnixConnection(socket_path)
            connection.request("GET", "/v1/overview", headers={"X-Armor-Maint-Token": TOKEN})
            response = connection.getresponse()
            body = json.loads(response.read())
            self.assertEqual(response.status, 200)
            self.assertEqual([item["id"] for item in body["components"]], ["server", "studio", "network", "ai", "voice", "devops"])
            self.assertTrue(body["console"])
            connection = UnixConnection(socket_path)
            connection.request("POST", "/v1/updates", body=json.dumps({"components": ["nothing"]}), headers={"X-Armor-Maint-Token": TOKEN, "Content-Type": "application/json"})
            self.assertEqual(connection.getresponse().status, 422)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
