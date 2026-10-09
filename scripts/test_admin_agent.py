#!/usr/bin/env python3
# ARMOR-DEVOPS - tests of scripts/armor_admin_agent.py: what it refuses, what it does to the files and what it asks of systemctl and the identity script.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
# Nothing real is touched: a temporary prefix, a stand-in systemctl and a stand-in identity script. Needs a system with Unix sockets (Linux, macOS, WSL).
from __future__ import annotations

import http.client
import importlib.util
import json
import os
import socket
import stat
import sys
import tempfile
import threading
import unittest
from pathlib import Path

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

    def call(self, method: str, path: str, body: object | None = None, token: str | None = TOKEN) -> tuple[int, dict]:
        connection = UnixConnection(self.sock)
        headers = {"Content-Type": "application/json"}
        if token is not None:
            headers["X-Armor-Admin-Token"] = token
        connection.request(method, path, json.dumps(body) if body is not None else None, headers)
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
        self.assertEqual([item["id"] for item in data["services"]], ["server", "studio", "mosquitto", "network", "voice", "extra"])
        self.assertTrue(all(item["active"] == "active" and item["installed"] for item in data["services"]))

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
