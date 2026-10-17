#!/usr/bin/env python3
# ARMOR-DEVOPS - tests of scripts/armor_maintenance_agent.py: the versions it reads, what it asks GitHub, how it installs, checks, refuses and rolls back, and the console.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
# Nothing real is touched: a temporary prefix, a stand-in GitHub on the loopback, a stand-in systemctl and a stand-in health address. Needs Linux, macOS or WSL.
from __future__ import annotations

import hashlib
import http.client
import http.server
import importlib.util
import io
import json
import os
import socket
import stat
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
                           "ARMOR_MAINT_DATA": str(root / "data"), "ARMOR_MAINT_CONSOLE": "1"})
        spec = importlib.util.spec_from_file_location("armor_maintenance_agent", HERE / "armor_maintenance_agent.py")
        assert spec and spec.loader
        cls.agent = importlib.util.module_from_spec(spec)
        sys.modules["armor_maintenance_agent"] = cls.agent
        spec.loader.exec_module(cls.agent)

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
        self.agent._cache.clear()
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

    def publish(self, repo: str, version: str, files: dict[str, bytes] | None, component: str, good_hash: bool = True) -> None:
        assets = []
        if files is not None:
            name = f"armor-{component}-{version}.tgz"
            content = tarball(files)
            FakeGitHub.assets[name] = content
            digest = hashlib.sha256(content).hexdigest() if good_hash else "0" * 64
            FakeGitHub.assets[name + ".sha256"] = f"{digest}  {name}\n".encode()
            assets = [{"name": name, "browser_download_url": f"{self.base}/assets/{name}"}, {"name": name + ".sha256", "browser_download_url": f"{self.base}/assets/{name}.sha256"}]
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
