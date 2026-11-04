#!/usr/bin/env python3
"""Live bench of the REST and WebSocket contract: starts a real ARMOR-SERVER on the loopback address with throw-away tokens and an empty data directory, plays simulated nodes
into it with ARMOR-SIMULATOR and checks what the server says over HTTP and over the live events socket.

  python scripts/bench_live.py --server DIR --simulator DIR [--seconds 8] [--nodes bench-1,bench-2,bench-3]

The server is run from DIR/dist/server.mjs when the repository has been built (npm run build) and from the sources with tsx otherwise. No Docker, no broker and no camera are
needed, and nothing leaves this machine: the port is a free one chosen by the operating system and the tokens are generated for the run. The process of the server is the only
one this script stops. Exit 0 when every assertion holds.
Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import secrets
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


class Bench:
    def __init__(self, server: Path, simulator: Path, nodes: list[str], seconds: float):
        self.server_dir, self.simulator_dir, self.nodes, self.seconds = server, simulator, nodes, seconds
        self.port = free_port()
        self.base = f"http://127.0.0.1:{self.port}"
        self.tokens = {name: secrets.token_hex(24) for name in ("ingest", "control", "operator")}
        self.failures: list[str] = []
        self.checks = 0
        self.events: list[dict] = []
        self.process: subprocess.Popen[bytes] | None = None

    # ---- assertions -------------------------------------------------------
    def check(self, ok: bool, what: str) -> None:
        self.checks += 1
        if not ok:
            self.failures.append(what)
        print(("ok    " if ok else "FAIL  ") + what)

    # ---- the server -------------------------------------------------------
    def start(self, data_dir: str) -> None:
        env = dict(os.environ, ARMOR_HOST="127.0.0.1", ARMOR_PORT=str(self.port), ARMOR_DATA_DIR=data_dir,
                   ARMOR_INGEST_TOKEN=self.tokens["ingest"], ARMOR_CONTROL_TOKEN=self.tokens["control"], ARMOR_OPERATOR_TOKEN=self.tokens["operator"],
                   ARMOR_CAMERA_CONFIG_KEY=secrets.token_hex(24), ARMOR_STUDIO_USERNAME="bench", ARMOR_STUDIO_PASSWORD=secrets.token_hex(16),
                   ARMOR_STUDIO_ORIGIN=self.base)
        env.pop("ARMOR_MQTT_URL", None)
        built = self.server_dir / "dist" / "server.mjs"
        if built.exists():
            command = ["node", str(built)]
        else:
            tsx = self.server_dir / "node_modules" / ".bin" / ("tsx.cmd" if os.name == "nt" else "tsx")
            command = [str(tsx), "src/server.ts"]
        self.process = subprocess.Popen(command, cwd=self.server_dir, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(90):
            if self.process.poll() is not None:
                raise SystemExit("the server stopped before it answered")
            try:
                if self.request("/healthz")[0] == 200:
                    return
            except OSError:
                time.sleep(1)
        raise SystemExit("the server did not answer in 90 seconds")

    def stop(self) -> None:
        if self.process and self.process.poll() is None:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(self.process.pid), "/T", "/F"], capture_output=True, check=False)
            else:
                self.process.terminate()
                try:
                    self.process.wait(10)
                except subprocess.TimeoutExpired:
                    self.process.kill()

    def request(self, path: str, token: str | None = None) -> tuple[int, str]:
        req = urllib.request.Request(self.base + path)
        if token:
            req.add_header("Authorization", "Bearer " + token)
        try:
            with urllib.request.urlopen(req, timeout=5) as answer:
                return answer.status, answer.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as error:
            return error.code, error.read().decode("utf-8", "replace")

    def json(self, path: str, token: str | None) -> dict:
        status, body = self.request(path, token)
        self.check(status == 200, f"GET {path} answers 200 to the right token")
        try:
            value = json.loads(body)
        except ValueError:
            value = {}
        return value if isinstance(value, dict) else {}

    # ---- the live events socket ---------------------------------------------
    def open_socket(self, token: str | None) -> tuple[socket.socket, int]:
        sock = socket.create_connection(("127.0.0.1", self.port), timeout=5)
        key = base64.b64encode(secrets.token_bytes(16)).decode()
        lines = ["GET /api/v1/events HTTP/1.1", f"Host: 127.0.0.1:{self.port}", "Upgrade: websocket", "Connection: Upgrade", f"Sec-WebSocket-Key: {key}", "Sec-WebSocket-Version: 13"]
        if token:
            lines.append("Authorization: Bearer " + token)
        sock.sendall(("\r\n".join(lines) + "\r\n\r\n").encode())
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = sock.recv(1)
            if not chunk:
                break
            head += chunk
        status = int(head.split(b" ", 2)[1]) if head.startswith(b"HTTP/") else 0
        return sock, status

    def listen(self, sock: socket.socket, until: float) -> None:
        sock.settimeout(1)
        buffer = b""
        while time.time() < until:
            try:
                chunk = sock.recv(65536)
            except socket.timeout:
                continue
            except OSError:
                return
            if not chunk:
                return
            buffer += chunk
            while True:
                frame = take_frame(buffer)
                if frame is None:
                    break
                opcode, payload, used = frame
                buffer = buffer[used:]
                if opcode == 1:
                    try:
                        value = json.loads(payload.decode("utf-8", "replace"))
                    except ValueError:
                        continue
                    if isinstance(value, dict):
                        self.events.append(value)
                elif opcode == 8:
                    return

    # ---- the run ----------------------------------------------------------
    def run(self) -> int:
        with tempfile.TemporaryDirectory() as data_dir:
            try:
                self.start(data_dir)
                self.assertions()
            finally:
                self.stop()
        print(f"{self.checks} checks, {len(self.failures)} failed")
        for failure in self.failures:
            print("  - " + failure, file=sys.stderr)
        return 1 if self.failures else 0

    def assertions(self) -> None:
        ingest, control, operator = self.tokens["ingest"], self.tokens["control"], self.tokens["operator"]
        status, body = self.request("/healthz")
        self.check(status == 200 and json.loads(body).get("ok") is True, "GET /healthz says ok")
        info = self.json("/api/v1/info", operator)
        self.check(isinstance(info.get("version"), str) and info.get("service") == "armor-server", "GET /api/v1/info names the service and its version")
        for path in ("/api/v1/node-health", "/api/v1/panel/summary", "/api/v1/alarms", "/api/v1/history/summary"):
            self.check(self.request(path)[0] == 401, f"GET {path} refuses a caller with no token")
            self.check(self.request(path, "x" * 48)[0] == 401, f"GET {path} refuses a wrong token")
        self.check(self.request("/api/v1/node-health", control)[0] == 401, "the control token does not read the operator routes")
        refused = self.open_socket(None)
        # the server drops the connection of a caller it does not know (no upgrade, status 0) or answers 401/403: anything but 101 is a refusal
        self.check(refused[1] != 101, f"the events socket refuses a caller with no token (answered {refused[1]})")
        refused[0].close()
        sock, upgraded = self.open_socket(control)
        self.check(upgraded == 101, "the events socket opens for the control token")
        window = time.time() + self.seconds
        listener = threading.Thread(target=self.listen, args=(sock, window), daemon=True)
        listener.start()
        play = subprocess.run([sys.executable, "-m", "armor_simulator.cli", "--nodes", ",".join(self.nodes), "--count", "6", "--interval-ms", "400", "--start-ms", "now",
                               "--server-url", self.base, "--ingest-token", ingest],
                              cwd=self.simulator_dir, env=dict(os.environ, PYTHONPATH="src"), capture_output=True, text=True, timeout=120, check=False)
        self.check(play.returncode == 0, "the simulator delivers every message to the server")
        listener.join(max(0.0, window - time.time()) + 3)
        sock.close()
        health = self.json("/api/v1/node-health", operator)
        known = {entry.get("node_id") for key in ("nodes", "waiting") for entry in health.get(key, []) if isinstance(entry, dict)}
        for node in self.nodes:
            self.check(node in known, f"/api/v1/node-health knows {node}")
        summary = self.json("/api/v1/panel/summary", operator)
        count = summary.get("nodes", {}) if isinstance(summary.get("nodes"), dict) else {}
        self.check(count.get("total") == len(self.nodes) and count.get("online") == len(self.nodes), "/api/v1/panel/summary counts every simulated node online")
        self.check(summary.get("mode") == "disarmed", "the system starts disarmed")
        alarms = self.json("/api/v1/alarms", operator)
        self.check(isinstance(alarms.get("active"), list) and isinstance(alarms.get("recent"), list), "/api/v1/alarms has its two lists")
        history = self.json("/api/v1/history/summary", operator)
        self.check(isinstance(history.get("total"), int) and history["total"] > 0, "/api/v1/history/summary counts the events of the run")
        self.check(len(self.events) > 0, "the events socket delivered something while the nodes played")
        seen = {json.dumps(event)[:4000] for event in self.events}
        for node in self.nodes:
            self.check(any(f'"{node}"' in text for text in seen), f"the events socket mentioned {node}")
        bad = [e for e in self.events if not isinstance(e.get("type", e.get("kind", "x")), str)]
        self.check(not bad, "every event names its type as text")


def take_frame(buffer: bytes) -> tuple[int, bytes, int] | None:
    """One WebSocket frame from the start of the buffer (the server never masks): (opcode, payload, bytes used), or None when it is not complete yet."""
    if len(buffer) < 2:
        return None
    opcode, length, offset = buffer[0] & 0x0F, buffer[1] & 0x7F, 2
    if length == 126:
        if len(buffer) < 4:
            return None
        length, offset = struct.unpack(">H", buffer[2:4])[0], 4
    elif length == 127:
        if len(buffer) < 10:
            return None
        length, offset = struct.unpack(">Q", buffer[2:10])[0], 10
    if len(buffer) < offset + length:
        return None
    return opcode, buffer[offset:offset + length], offset + length


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--server", type=Path, required=True, help="the ARMOR-SERVER checkout")
    parser.add_argument("--simulator", type=Path, required=True, help="the ARMOR-SIMULATOR checkout")
    parser.add_argument("--seconds", type=float, default=8.0, help="how long the events socket listens")
    parser.add_argument("--nodes", default="bench-1,bench-2,bench-3")
    args = parser.parse_args()
    return Bench(args.server.resolve(), args.simulator.resolve(), [n for n in args.nodes.split(",") if n], args.seconds).run()


if __name__ == "__main__":
    raise SystemExit(main())
