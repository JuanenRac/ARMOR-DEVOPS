#!/usr/bin/env python3
# ARMOR-DEVOPS - tests of scripts/armor_admin_agent.py: what it refuses, what it does to the files and what it asks of systemctl and the identity script.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
# Nothing real is touched: a temporary prefix, a stand-in systemctl and a stand-in identity script. Needs a system with Unix sockets (Linux, macOS, WSL).
from __future__ import annotations

import contextlib
import http.client
import importlib.util
import io
import json
import os
import socket
import stat
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
TOKEN = "t" * 32


class UnixConnection(http.client.HTTPConnection):
    def __init__(self, path: str) -> None:
        super().__init__("localhost")
        self._path = path

    def connect(self) -> None:
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self._path)


class AgentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.prefix = root / "armor"
        (cls.prefix / "etc/mosquitto").mkdir(parents=True)
        (cls.prefix / "etc/armor.env").write_text("ARMOR_STUDIO_PASSWORD=secret-one\nARMOR_PORT=18080\n", encoding="utf-8")
        (cls.prefix / "etc/mosquitto/acl").write_text(
            "user armor-server\ntopic write armor/server/alert\ntopic read armor/node/+/telemetry\n\n"
            "user field-node-north-1\ntopic write armor/node/north-1/telemetry\ntopic read armor/node/north-1/command\n", encoding="utf-8")
        cls.calls = root / "systemctl.log"
        systemctl = root / "systemctl"
        systemctl.write_text(
            f"#!/bin/sh\necho \"$@\" >> '{cls.calls}'\n"
            "case \"$1\" in show) echo LoadState=loaded; echo ActiveState=active; echo SubState=running; echo UnitFileState=enabled; echo MainPID=42; echo ActiveEnterTimestamp=today;; esac\n"
            "exit 0\n", encoding="utf-8")
        systemctl.chmod(0o755)
        identity = root / "identity.sh"
        identity.write_text(
            f"#!/bin/bash\necho \"$@\" >> '{root}/identity.log'\n"
            "case \"$1\" in\n"
            "  rotate) if [ \"$3\" = ghost ]; then echo 'field-node-ghost does not exist' >&2; exit 1; fi; echo \"user: field-node-$3\"; echo 'password: pw456';;\n"
            "  add) if [ \"$3\" = taken ]; then echo 'field-node-taken already exists' >&2; exit 1; fi; echo \"user: field-node-$3\"; echo 'password: pw123';;\n"
            "  remove) echo removed;;\n"
            "esac\n", encoding="utf-8")
        os.environ.update(ARMOR_PREFIX=str(cls.prefix), ARMOR_SYSTEMCTL=str(systemctl), ARMOR_MQTT_IDENTITY=str(identity),
                          ARMOR_ADMIN_EXTRA_SERVICES="extra=armor-extra,bad key=x")
        spec = importlib.util.spec_from_file_location("armor_admin_agent", HERE / "armor_admin_agent.py")
        assert spec and spec.loader
        cls.agent = importlib.util.module_from_spec(spec)
        sys.modules["armor_admin_agent"] = cls.agent
        spec.loader.exec_module(cls.agent)
        cls.sock = str(root / "agent.sock")
        threading.Thread(target=cls.agent.serve, args=(cls.sock, TOKEN, None), daemon=True).start()
        for _ in range(100):
            if Path(cls.sock).exists():
                break
            threading.Event().wait(0.05)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def call(self, method: str, path: str, body: object | None = None, token: str | None = TOKEN, extra: dict[str, str] | None = None) -> tuple[int, dict]:
        connection = UnixConnection(self.sock)
        headers = {"Content-Type": "application/json"}
        if token is not None:
            headers["X-Armor-Admin-Token"] = token
        headers.update(extra or {})
        try:
            connection.request(method, path, json.dumps(body) if body is not None else None, headers)
        except (BrokenPipeError, ConnectionResetError):
            pass      # the agent answered a refusal and closed before it read the body: the answer is already there to be read
        response = connection.getresponse()
        data = json.loads(response.read().decode("utf-8"))
        connection.close()
        return response.status, data

    def test_refuses_without_the_token(self) -> None:
        self.assertEqual(self.call("GET", "/v1/services", token=None)[0], 401)
        self.assertEqual(self.call("GET", "/v1/services", token="x" * 32)[0], 401)

    def test_lists_the_services_and_knows_the_extra_one_only_when_its_name_is_valid(self) -> None:
        status, data = self.call("GET", "/v1/services")
        self.assertEqual(status, 200)
        self.assertEqual([item["id"] for item in data["services"]], ["server", "studio", "mosquitto", "network", "ai", "voice", "extra"])
        self.assertTrue(all(item["active"] == "active" and item["installed"] for item in data["services"]))

    def test_a_service_can_be_paused_and_resumed_but_not_the_console_itself(self) -> None:
        self.assertEqual(self.call("POST", "/v1/services/mosquitto/pause")[0], 200)
        self.assertEqual(self.call("POST", "/v1/services/mosquitto/resume")[0], 200)
        log = self.calls.read_text(encoding="utf-8")
        self.assertIn("kill --signal=SIGSTOP --kill-whom=main armor-mosquitto", log)
        self.assertIn("kill --signal=SIGCONT --kill-whom=main armor-mosquitto", log)
        for service_id in ("server", "studio"):          # a paused console could not be used to resume itself
            self.assertEqual(self.call("POST", f"/v1/services/{service_id}/pause")[1], {"error": "cannot_pause"})
        status, data = self.call("GET", "/v1/services")
        self.assertTrue(all(item["paused"] is False for item in data["services"]))

    def test_service_actions_go_to_systemctl_and_only_the_allowed_ones(self) -> None:
        self.assertEqual(self.call("POST", "/v1/services/mosquitto/restart")[0], 200)
        self.assertEqual(self.call("POST", "/v1/services/server/restart")[0], 200)
        log = self.calls.read_text(encoding="utf-8")
        self.assertIn("restart armor-mosquitto", log)
        self.assertIn("--no-block restart armor-server", log)        # the server cannot wait for its own restart
        self.assertEqual(self.call("POST", "/v1/services/mosquitto/format")[1], {"error": "unknown_action"})
        self.assertEqual(self.call("POST", "/v1/services/sshd/stop")[1], {"error": "unknown_service"})
        self.assertEqual(self.call("POST", "/v1/services/../stop")[0], 404)

    def test_reads_and_writes_a_file_with_a_copy_and_the_same_mode(self) -> None:
        env = self.prefix / "etc/armor.env"
        env.chmod(0o640)
        status, data = self.call("GET", "/v1/files/server.env")
        self.assertEqual((status, data["exists"], data["format"]), (200, True, "env"))
        self.assertIn("ARMOR_PORT=18080", data["content"])
        status, _ = self.call("PUT", "/v1/files/server.env", {"content": "ARMOR_PORT=19090\n", "expect_mtime": data["mtime"]})
        self.assertEqual(status, 200)
        self.assertEqual(env.read_text(encoding="utf-8"), "ARMOR_PORT=19090\n")
        self.assertEqual(stat.S_IMODE(env.stat().st_mode), 0o640)
        self.assertEqual(len(list(env.parent.glob("armor.env.bak-*"))), 1)
        self.assertEqual(self.call("PUT", "/v1/files/server.env", {"content": "ARMOR_PORT=1\n", "expect_mtime": data["mtime"] - 100})[1], {"error": "file_changed"})

    def test_checks_the_format_and_never_takes_a_path_from_the_request(self) -> None:
        self.assertEqual(self.call("PUT", "/v1/files/server.env", {"content": "not an env line\n"})[1], {"error": "invalid_line:1"})
        self.assertEqual(self.call("PUT", "/v1/files/mosquitto.acl", {"content": "rm -rf /\n"})[1], {"error": "invalid_line:1"})
        self.assertEqual(self.call("PUT", "/v1/files/server.env", {"content": "A=1\x00\n"})[1], {"error": "invalid_content"})
        self.assertEqual(self.call("PUT", "/v1/files/server.env", {"content": "A=" + "x" * 70000})[0], 413)
        self.assertEqual(self.call("GET", "/v1/files/..%2Fetc%2Fpasswd")[1], {"error": "unknown_file"})
        self.assertEqual(self.call("PUT", "/v1/files/reach.txt", {"content": "http://203.0.113.7:2601=http://203.0.113.7:2600\n"})[0], 200)
        self.assertEqual(self.call("PUT", "/v1/files/reach.txt", {"content": "javascript:alert(1)\n"})[1], {"error": "invalid_line:1"})
        self.assertEqual(self.call("GET", "/v1/files/passwd")[1], {"error": "unknown_file"})   # the hashed passwords are never offered

    def test_a_file_that_does_not_exist_yet_can_be_created_and_the_service_restarted(self) -> None:
        status, data = self.call("GET", "/v1/files/mqtt.env")
        self.assertEqual((status, data["exists"]), (200, False))
        status, saved = self.call("PUT", "/v1/files/mqtt.env", {"content": "ARMOR_MQTT_URL=mqtt://127.0.0.1:18883\n", "restart": True})
        self.assertEqual((status, saved["restarted"]), (200, ["server"]))
        self.assertTrue((self.prefix / "etc/armor.mqtt.env").is_file())

    def test_lists_the_broker_accounts_with_their_role_and_what_each_may_do(self) -> None:
        status, data = self.call("GET", "/v1/mqtt/accounts")
        self.assertEqual(status, 200)
        by_user = {item["user"]: item for item in data["accounts"]}
        self.assertFalse(by_user["armor-server"]["manageable"])
        node = by_user["field-node-north-1"]
        self.assertEqual((node["role"], node["name"], node["manageable"]), ("field-node", "north-1", True))
        self.assertIn("topic read armor/node/north-1/command", node["topics"])

    def test_adds_and_removes_an_account_through_the_identity_script_only(self) -> None:
        status, data = self.call("POST", "/v1/mqtt/accounts", {"role": "node", "name": "south-2"})
        self.assertEqual((status, data), (200, {"ok": True, "user": "field-node-south-2", "password": "pw123"}))
        self.assertEqual(self.call("POST", "/v1/mqtt/accounts", {"role": "node", "name": "taken"})[0], 409)
        self.assertEqual(self.call("POST", "/v1/mqtt/accounts", {"role": "root", "name": "x"})[1], {"error": "unknown_role"})
        self.assertEqual(self.call("POST", "/v1/mqtt/accounts", {"role": "node", "name": "Bad Name"})[1], {"error": "invalid_name"})
        self.assertEqual(self.call("DELETE", "/v1/mqtt/accounts/field-node-south-2")[0], 200)
        self.assertEqual(self.call("DELETE", "/v1/mqtt/accounts/armor-server")[1], {"error": "invalid_user"})   # the server's own identity cannot be removed from here
        log = (Path(self.tmp.name) / "identity.log").read_text(encoding="utf-8")
        self.assertIn("add node south-2", log)
        self.assertIn("remove field-node-south-2", log)
        self.assertNotIn("armor-server", log)

    def test_an_account_that_exists_gets_a_new_password_in_one_step_through_the_script(self) -> None:
        status, data = self.call("POST", "/v1/mqtt/accounts", {"role": "node", "name": "taken", "rotate": True})
        self.assertEqual((status, data), (200, {"ok": True, "user": "field-node-taken", "password": "pw456"}))
        self.assertEqual(self.call("POST", "/v1/mqtt/accounts", {"role": "node", "name": "ghost", "rotate": True})[0], 502)       # an identity that was never made is not made by a rotation
        self.assertEqual(self.call("POST", "/v1/mqtt/accounts", {"role": "node", "name": "taken", "rotate": "yes"})[0], 409)     # only a real true asks for it
        self.assertEqual(self.call("POST", "/v1/mqtt/accounts", {"role": "root", "name": "x", "rotate": True})[1], {"error": "unknown_role"})
        log = (Path(self.tmp.name) / "identity.log").read_text(encoding="utf-8")
        self.assertIn("rotate node taken", log)
        self.assertNotIn("remove field-node-taken", log)

    def raw(self, method: str, path: str, headers: dict[str, str], body: bytes = b"") -> tuple[int, dict]:
        connection = UnixConnection(self.sock)
        connection.putrequest(method, path)
        for key, value in headers.items():
            connection.putheader(key, value)
        connection.endheaders(body)
        response = connection.getresponse()
        data = json.loads(response.read().decode("utf-8"))
        connection.close()
        return response.status, data

    def test_the_request_body_is_checked_before_anything_is_done(self) -> None:
        token = {"X-Armor-Admin-Token": TOKEN}
        self.assertEqual(self.raw("PUT", "/v1/files/server.env", {**token, "Content-Length": "-5"}), (400, {"error": "bad_length"}))
        self.assertEqual(self.raw("PUT", "/v1/files/server.env", {**token, "Content-Length": "abc"}), (400, {"error": "bad_length"}))
        self.assertEqual(self.raw("PUT", "/v1/files/server.env", {**token, "Content-Length": str(10 * 1024 * 1024)}), (413, {"error": "body_too_large"}))
        self.assertEqual(self.raw("PUT", "/v1/files/server.env", {**token, "Content-Length": "5"}, b"{nope"), (400, {"error": "invalid_json"}))
        self.assertEqual(self.raw("PUT", "/v1/files/server.env", {**token, "Content-Length": "2"}, b"[]"), (400, {"error": "invalid_json"}))
        self.assertEqual(self.call("PUT", "/v1/files/server.env", {"content": 5})[1], {"error": "invalid_content"})
        self.assertEqual(self.call("PUT", "/v1/files/server.env", {})[1], {"error": "invalid_content"})

    def test_a_token_that_is_nearly_right_or_in_another_case_is_refused(self) -> None:
        for token in (TOKEN[:-1], TOKEN + "t", TOKEN.upper(), ""):
            self.assertEqual(self.call("GET", "/v1/services", token=token)[0], 401, repr(token))

    def test_unknown_routes_and_methods_are_not_found_only_with_the_token(self) -> None:
        self.assertEqual(self.call("GET", "/v2/services", token=None)[0], 401)          # nothing is learned without the token
        for method, path in (("GET", "/v2/services"), ("GET", "/services"), ("GET", "/v1/nothing"), ("DELETE", "/v1/services"), ("POST", "/v1/files/server.env"), ("GET", "/v1/mqtt/accounts/x")):
            self.assertEqual(self.call(method, path)[1], {"error": "not_found"}, (method, path))

    def test_the_list_of_files_never_carries_their_contents(self) -> None:
        status, data = self.call("GET", "/v1/files")
        self.assertEqual(status, 200)
        self.assertEqual([item["id"] for item in data["files"]], ["server.env", "mqtt.env", "network.env", "reach.txt", "mosquitto.conf", "mosquitto.acl"])
        self.assertTrue(all("content" not in item for item in data["files"]))
        self.assertNotIn("secret-one", json.dumps(data))

    def test_only_the_newest_copies_of_a_file_are_kept_and_they_are_private(self) -> None:
        path = self.prefix / "etc/armor.reach"
        path.write_text("http://a.example:1=http://a.example:2\n", encoding="utf-8")
        for index in range(8):
            for old in path.parent.glob("armor.reach.bak-*"):
                os.rename(old, old.with_name(old.name.replace("bak-", f"bak-0000{index}-")))   # distinct names without waiting a second
            self.agent.write_file("reach.txt", f"http://b.example:{index + 10}=http://b.example:{index + 20}\n", None)
        copies = sorted(path.parent.glob("armor.reach.bak-*"))
        self.assertEqual(len(copies), self.agent.KEEP_BACKUPS)
        self.assertTrue(all(stat.S_IMODE(copy.stat().st_mode) == 0o600 for copy in copies))
        self.assertFalse(list(path.parent.glob(".armor.reach.*")))                       # no temporary file is left behind

    def test_every_format_refuses_what_it_does_not_understand(self) -> None:
        check = self.agent.check_content
        for fmt, good, bad in (("env", "A_B=1\n# c\n\n", "1A=2"), ("acl", "user x\ntopic read a/b\npattern read a/%u\n", "allow all"),
                               ("reach", "http://a.example:1=https://b.example:2\n", "http://a.example:1"), ("conf", "listener 1883\nallow_anonymous false\n", "=1")):
            check(fmt, good)
            with self.assertRaises(self.agent.Refused) as caught:
                check(fmt, bad)
            self.assertEqual(caught.exception.status, 422)
        with self.assertRaises(self.agent.Refused) as caught:
            check("env", "A=" + "x" * 1100)
        self.assertEqual(caught.exception.code, "line_too_long:1")
        with self.assertRaises(self.agent.Refused) as caught:
            check("env", "A=1\nB=2\nbad line\n")
        self.assertEqual(caught.exception.code, "invalid_line:3")

    def test_a_failing_systemctl_is_a_bad_gateway_not_a_success(self) -> None:
        failing = Path(self.tmp.name) / "systemctl-fails"
        failing.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        failing.chmod(0o755)
        original = self.agent.SYSTEMCTL
        self.agent.SYSTEMCTL = str(failing)
        try:
            with self.assertRaises(self.agent.Refused) as caught:
                self.agent.service_action("mosquitto", "restart")
        finally:
            self.agent.SYSTEMCTL = original
        self.assertEqual((caught.exception.status, caught.exception.code), (502, "systemctl_failed"))

    def test_a_process_is_paused_only_when_its_state_says_stopped(self) -> None:
        self.assertFalse(self.agent.is_stopped_by_signal(0))
        self.assertFalse(self.agent.is_stopped_by_signal(-4))
        self.assertFalse(self.agent.is_stopped_by_signal(os.getpid()))            # this process is running
        self.assertFalse(self.agent.is_stopped_by_signal(4194000))                # a process that does not exist

    def test_accounts_of_unknown_shape_are_listed_but_not_manageable(self) -> None:
        accounts = self.agent.parse_accounts("user armor-server\ntopic read a\n\nuser bridge-cnc\npattern read x/%u\n\nuser alarm-front-door\n# comment\ntopic write y\n")
        by_user = {item["user"]: item for item in accounts}
        self.assertEqual((by_user["armor-server"]["manageable"], by_user["armor-server"]["role"]), (False, "other"))
        self.assertEqual((by_user["bridge-cnc"]["role"], by_user["bridge-cnc"]["name"], by_user["bridge-cnc"]["topics"]), ("bridge", "cnc", ["pattern read x/%u"]))
        self.assertEqual((by_user["alarm-front-door"]["role"], by_user["alarm-front-door"]["name"]), ("alarm", "front-door"))
        self.assertEqual(self.agent.parse_accounts(""), [])

    def test_an_identity_script_that_fails_is_not_reported_as_success(self) -> None:
        broken = Path(self.tmp.name) / "identity-broken.sh"
        broken.write_text("#!/bin/bash\necho 'boom' >&2\nexit 3\n", encoding="utf-8")
        original = self.agent.IDENTITY_SCRIPT
        self.agent.IDENTITY_SCRIPT = broken
        try:
            with self.assertRaises(self.agent.Refused) as caught:
                self.agent.add_account("node", "north-9")
            self.assertEqual((caught.exception.status, caught.exception.code), (502, "identity_failed"))
            with self.assertRaises(self.agent.Refused) as caught:
                self.agent.remove_account("field-node-north-9")
            self.assertEqual((caught.exception.status, caught.exception.code), (502, "identity_failed"))
        finally:
            self.agent.IDENTITY_SCRIPT = original

    def test_the_agent_does_not_start_without_a_long_enough_token(self) -> None:
        for token in ("", "short", "x" * 23):
            with mock.patch.dict(os.environ, {"ARMOR_ADMIN_TOKEN": token}), mock.patch.object(sys, "argv", ["armor_admin_agent.py", "--socket", str(Path(self.tmp.name) / "never.sock")]):
                with contextlib.redirect_stderr(io.StringIO()) as err:
                    self.assertEqual(self.agent.main(), 2, token)
            self.assertIn("ARMOR_ADMIN_TOKEN", err.getvalue())
            self.assertFalse((Path(self.tmp.name) / "never.sock").exists())

    def with_sensitive(self, mode: str, token: str = "") -> None:
        self.addCleanup(self.agent.configure_sensitive, "open", "")
        self.assertIsNone(self.agent.configure_sensitive(mode, token, TOKEN))

    def test_by_default_the_broker_rules_and_the_env_files_stay_writable_with_the_admin_token_alone(self) -> None:
        status, data = self.call("GET", "/v1/status")
        self.assertEqual((status, data["sensitive_writes"]["mode"], data["sensitive_writes"]["warning"]), (200, "open", "open"))
        self.assertEqual(self.call("PUT", "/v1/files/server.env", {"content": "ARMOR_PORT=18080\n"})[0], 200)

    def test_with_a_second_secret_the_sensitive_files_and_accounts_need_it_and_the_rest_does_not(self) -> None:
        second = "s" * 32
        self.with_sensitive("second_token", second)
        status, data = self.call("GET", "/v1/status")
        self.assertEqual((data["sensitive_writes"]["mode"], data["sensitive_writes"]["protected"], data["sensitive_writes"]["warning"]), ("second_token", True, ""))
        for file_id, text in (("mosquitto.acl", "user x\n"), ("server.env", "A=1\n"), ("mqtt.env", "A=1\n"), ("network.env", "A=1\n")):
            self.assertEqual(self.call("PUT", f"/v1/files/{file_id}", {"content": text}), (403, {"error": "sensitive_token_required"}), file_id)
            self.assertEqual(self.call("PUT", f"/v1/files/{file_id}", {"content": text}, extra={"X-Armor-Admin-Sensitive-Token": TOKEN})[1], {"error": "sensitive_token_required"})
        self.assertEqual(self.call("POST", "/v1/mqtt/accounts", {"role": "node", "name": "north-2"})[1], {"error": "sensitive_token_required"})
        self.assertEqual(self.call("DELETE", "/v1/mqtt/accounts/field-node-north-1")[1], {"error": "sensitive_token_required"})
        self.assertEqual(self.call("PUT", "/v1/files/server.env", {"content": "ARMOR_PORT=18080\n"}, extra={"X-Armor-Admin-Sensitive-Token": second})[0], 200)
        self.assertEqual(self.call("PUT", "/v1/files/reach.txt", {"content": ""})[0], 200)       # not sensitive
        self.assertEqual(self.call("GET", "/v1/files/server.env")[0], 200)                       # reading is not locked

    def test_read_only_refuses_every_sensitive_write_even_with_a_secret(self) -> None:
        self.with_sensitive("read_only")
        self.assertEqual(self.call("PUT", "/v1/files/mosquitto.acl", {"content": "user x\n"}, extra={"X-Armor-Admin-Sensitive-Token": "s" * 32}), (403, {"error": "sensitive_read_only"}))
        self.assertEqual(self.call("POST", "/v1/mqtt/accounts", {"role": "node", "name": "n"})[0], 403)
        self.assertEqual(self.call("GET", "/v1/status")[1]["sensitive_writes"]["mode"], "read_only")

    def test_a_bad_protection_setting_is_never_taken_as_open(self) -> None:
        self.addCleanup(self.agent.configure_sensitive, "open", "")
        self.assertEqual(self.agent.configure_sensitive("nonsense", "", TOKEN), "unknown_mode")
        self.assertEqual(self.agent.configure_sensitive("second_token", "short", TOKEN), "second_token_missing_or_equal")
        self.assertEqual(self.agent.configure_sensitive("second_token", TOKEN, TOKEN), "second_token_missing_or_equal")
        for env in ({"ARMOR_ADMIN_SENSITIVE": "nonsense"}, {"ARMOR_ADMIN_SENSITIVE": "second_token"}):
            with mock.patch.dict(os.environ, {"ARMOR_ADMIN_TOKEN": TOKEN, **env}), mock.patch.object(sys, "argv", ["armor_admin_agent.py", "--socket", str(Path(self.tmp.name) / "never.sock")]):
                with contextlib.redirect_stderr(io.StringIO()) as err:
                    self.assertEqual(self.agent.main(), 2)
            self.assertIn("ARMOR_ADMIN_SENSITIVE", err.getvalue())

    def test_the_socket_is_not_open_to_everybody(self) -> None:
        mode = stat.S_IMODE(os.stat(self.sock).st_mode)
        self.assertEqual(mode & 0o007, 0, oct(mode))                                # nothing for "others"


if __name__ == "__main__":
    unittest.main(verbosity=2)
