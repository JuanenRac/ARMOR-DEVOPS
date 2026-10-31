#!/usr/bin/env python3
# ARMOR-DEVOPS - tests of the way in from outside the house, as the maintenance helper offers it (scripts/armor_maintenance_agent.py with scripts/armor_wireguard.sh and
# scripts/armor_ddns.sh): the state, the VPN and its devices, the dynamic DNS name, and what is refused. Stand-ins for wg, curl and systemctl; a temporary prefix.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
from __future__ import annotations

from typing import Any

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
TOKEN = "r" * 32


class UnixConnection(http.client.HTTPConnection):
    def __init__(self, path: str) -> None:
        super().__init__("localhost")
        self._path = path

    def connect(self) -> None:
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self._path)


def script(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


class RemoteAccessTest(unittest.TestCase):
    agent: Any
    prefix: Any
    server: Any
    socket_path: Any
    tmp: Any
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.prefix = root / "armor"
        (cls.prefix / "bin").mkdir(parents=True)
        (cls.prefix / "etc").mkdir()
        for name in ("armor_wireguard.sh", "armor_ddns.sh"):
            (cls.prefix / "bin" / name).write_bytes((HERE / name).read_bytes().replace(b"\r\n", b"\n"))
        tools = root / "tools"
        tools.mkdir()
        script(tools / "wg", '#!/usr/bin/env bash\ncase "$1" in genkey) echo "PRIV$RANDOM$RANDOM$RANDOM$RANDOM";; genpsk) echo "PSK$RANDOM$RANDOM$RANDOM";; pubkey) read -r key; echo "PUB-$(printf %s "$key" | md5sum | cut -c1-16)";; esac\n')
        script(tools / "systemctl", '#!/bin/sh\nif [ "$1" = "is-active" ]; then echo active; fi\nexit 0\n')
        script(tools / "curl", '#!/usr/bin/env bash\nif [[ "$*" == *"-K -"* ]]; then cat >/dev/null; echo OK; exit 0; fi\necho 203.0.113.9\n')
        os.environ.update({
            "PATH": f"{tools}{os.pathsep}{os.environ['PATH']}", "ARMOR_PREFIX": str(cls.prefix), "ARMOR_SYSTEMCTL": str(tools / "systemctl"), "ARMOR_MAINT_DATA": str(root / "data"),
            "ARMOR_WG_ETC": str(root / "wg"), "ARMOR_WG_NOSYSTEMD": "1", "ARMOR_DDNS_NOSYSTEMD": "1", "ARMOR_DDNS_CURL": str(tools / "curl"), "ARMOR_DDNS_ENV": str(cls.prefix / "etc" / "armor.ddns.env"),
        })
        spec = importlib.util.spec_from_file_location("armor_maintenance_agent_remote", HERE / "armor_maintenance_agent.py")
        assert spec and spec.loader
        cls.agent = importlib.util.module_from_spec(spec)
        sys.modules["armor_maintenance_agent_remote"] = cls.agent
        spec.loader.exec_module(cls.agent)
        cls.socket_path = str(root / "maint.sock")
        cls.agent.Handler.token = TOKEN
        cls.server = cls.agent.UnixServer(cls.socket_path, cls.agent.Handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp.cleanup()

    def call(self, method: str, path: str, body: object | None = None, token: str = TOKEN) -> tuple[int, dict[str, object]]:
        connection = UnixConnection(self.socket_path)
        headers = {"X-Armor-Maint-Token": token, "Content-Type": "application/json"}
        connection.request(method, path, body=None if body is None else json.dumps(body), headers=headers)
        response = connection.getresponse()
        return response.status, json.loads(response.read() or b"{}")

    def test_everything_in_order(self) -> None:
        # nothing is set up and the door wants the token
        self.assertEqual(self.call("GET", "/v1/remote", token="wrong")[0], 401)
        status, state = self.call("GET", "/v1/remote")
        self.assertEqual(status, 200)
        self.assertFalse(state["wireguard"]["configured"])      # type: ignore[index]
        self.assertFalse(state["ddns"]["configured"])           # type: ignore[index]

        # what is refused is refused here, before any script runs
        for bad in ({}, {"endpoint": "bad host"}, {"endpoint": "casa.example.org", "route_lan": "eth0; reboot"}, {"endpoint": "casa.example.org", "lan": "192.168.0.0"},
                    {"endpoint": "casa.example.org", "port": 0}, {"endpoint": "casa.example.org", "port": True}):
            self.assertEqual(self.call("POST", "/v1/remote/wireguard/setup", bad)[0], 422, bad)
        self.assertEqual(self.call("POST", "/v1/remote/wireguard/peers", {"name": "bad name"})[0], 422)
        self.assertEqual(self.call("POST", "/v1/remote/wireguard/peers", {"name": "phone"})[0], 422)       # before setup the script refuses: run setup first

        # the VPN
        status, state = self.call("POST", "/v1/remote/wireguard/setup", {"endpoint": "casa.example.org:51999", "lan": "192.168.1.0/24"})
        self.assertEqual(status, 200)
        vpn: Any = state["wireguard"]                                 # type: ignore[index]
        self.assertTrue(vpn["configured"])
        self.assertEqual((vpn["endpoint"], vpn["subnet"], vpn["lan"]), ("casa.example.org:51999", "10.66.0.0/24", "192.168.1.0/24"))
        status, made = self.call("POST", "/v1/remote/wireguard/peers", {"name": "phone-juan"})
        self.assertEqual(status, 201, made)
        self.assertIn("PrivateKey = PRIV", str(made["config"]))
        self.assertIn("Endpoint = casa.example.org:51999", str(made["config"]))
        self.assertEqual(self.call("POST", "/v1/remote/wireguard/peers", {"name": "phone-juan"})[0], 422)  # already there
        status, again = self.call("GET", "/v1/remote/wireguard/peers/phone-juan")
        self.assertEqual((status, again["config"]), (200, made["config"]))
        status, state = self.call("GET", "/v1/remote")
        peers = state["wireguard"]["peers"]                      # type: ignore[index]
        self.assertEqual([(peer["name"], peer["address"]) for peer in peers], [("phone-juan", "10.66.0.2")])
        self.assertNotIn("PRIV", json.dumps(state), "the state never carries a key")
        self.assertEqual(self.call("POST", "/v1/remote/wireguard/peers/phone-juan/remove")[0], 200)
        self.assertEqual(self.call("GET", "/v1/remote/wireguard/peers/phone-juan")[0], 422)

        # the dynamic DNS name
        self.assertEqual(self.call("POST", "/v1/remote/ddns/setup", {"provider": "nothing"})[0], 422)
        self.assertEqual(self.call("POST", "/v1/remote/ddns/setup", {"provider": "duckdns", "domain": "bad name", "token": "abcdefgh1234"})[0], 422)
        status, state = self.call("POST", "/v1/remote/ddns/setup", {"provider": "duckdns", "domain": "casa-armor", "token": "abcdef-1234-5678"})
        self.assertEqual(status, 200)
        dynamic: Any = state["ddns"]                                  # type: ignore[index]
        self.assertEqual((dynamic["provider"], dynamic["name"], dynamic["last_address"]), ("duckdns", "casa-armor", "203.0.113.9"))
        self.assertNotIn("abcdef-1234-5678", json.dumps(state), "the state never carries a token")
        self.assertEqual(self.call("POST", "/v1/remote/ddns/update")[0], 200)
        status, state = self.call("POST", "/v1/remote/ddns/remove")
        self.assertEqual(status, 200)
        self.assertFalse(state["ddns"]["configured"])            # type: ignore[index]


if __name__ == "__main__":
    unittest.main()
