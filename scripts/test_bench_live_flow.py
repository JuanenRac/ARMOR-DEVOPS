#!/usr/bin/env python3
# ARMOR-DEVOPS - the whole flow of bench_live.py against a stand-in server on the loopback address: the assertions it makes, what a wrong answer does to the count, how the server
# process is started and stopped, and the command line. Nothing here starts the real server or the simulator (both are stand-ins).
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
from __future__ import annotations

import http.server
import json
import socket
import struct
import subprocess
import sys
import threading
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bench_live  # noqa: E402

NODES = ["bench-1", "bench-2", "bench-3"]


def frame(payload: bytes, opcode: int = 1) -> bytes:
    return bytes([0x80 | opcode, len(payload)]) + payload


class StandIn(http.server.BaseHTTPRequestHandler):
    """The routes the bench reads, answered the way the real server does when every contract holds; `behaviour` changes one thing at a time."""

    protocol_version = "HTTP/1.1"
    tokens: dict[str, str] = {}
    behaviour: set[str] = set()

    def log_message(self, *_args) -> None:
        pass

    def reply(self, status: int, body: object) -> None:
        raw = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def bearer(self) -> str:
        header = self.headers.get("Authorization", "")
        return header[7:] if header.startswith("Bearer ") else ""

    def do_GET(self) -> None:  # noqa: N802
        path, token = self.path, self.bearer()
        operator, control = self.tokens["operator"], self.tokens["control"]
        if path == "/healthz":
            return self.reply(200, {"ok": "no_ok" not in self.behaviour})
        if path == "/api/v1/events":
            if token != control:
                return self.reply(401, {"error": "unauthorized"})
            self.send_response(101)
            self.send_header("Upgrade", "websocket")
            self.send_header("Connection", "Upgrade")
            self.end_headers()
            if "silent_socket" not in self.behaviour:
                for node in NODES:
                    self.wfile.write(frame(json.dumps({"type": "telemetry", "node_id": node}).encode()))
                self.wfile.write(frame(b"not json"))
                self.wfile.write(frame(b"[1]"))
            self.wfile.write(frame(b"", 8))
            self.wfile.flush()
            return None
        if token != operator and not (path == "/api/v1/info" and token == operator):
            return self.reply(401, {"error": "unauthorized"})
        if path == "/api/v1/info":
            return self.reply(200, {"service": "armor-server", "version": 5 if "bad_info" in self.behaviour else "0.8.2.0"})
        if path == "/api/v1/node-health":
            return self.reply(200, {"nodes": [{"node_id": n} for n in NODES[:2 if "missing_node" in self.behaviour else 3]], "waiting": []})
        if path == "/api/v1/panel/summary":
            return self.reply(200, {"nodes": {"total": 3, "online": 3}, "mode": "armed" if "armed" in self.behaviour else "disarmed"})
        if path == "/api/v1/alarms":
            return self.reply(200, {"active": [], "recent": []})
        if path == "/api/v1/history/summary":
            return self.reply(200, {"total": 0 if "empty_history" in self.behaviour else 12})
        return self.reply(404, {"error": "not_found"})


class QuietServer(http.server.ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address) -> None:   # a client that closes its socket in the middle of a request is part of these tests
        pass


class Server:
    def __init__(self, behaviour: set[str] | None = None) -> None:
        self.httpd = QuietServer(("127.0.0.1", 0), StandIn)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.behaviour = behaviour or set()

    def __enter__(self) -> "Server":
        StandIn.behaviour = self.behaviour
        self.thread.start()
        return self

    def __exit__(self, *_exc) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()

    @property
    def port(self) -> int:
        return int(self.httpd.server_address[1])


def bench_for(server: Server, seconds: float = 1.0) -> bench_live.Bench:
    bench = bench_live.Bench(Path("."), Path("."), list(NODES), seconds)
    bench.port = server.port
    bench.base = f"http://127.0.0.1:{server.port}"
    StandIn.tokens = bench.tokens
    return bench


def played(code: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(["simulator"], code, "", "")


class TheAssertionsOfTheBench(unittest.TestCase):
    def run_bench(self, behaviour: set[str], simulator_code: int = 0) -> bench_live.Bench:
        with Server(behaviour) as server:
            bench = bench_for(server)
            with mock.patch.object(bench_live.subprocess, "run", return_value=played(simulator_code)):
                bench.assertions()
        return bench

    def test_a_server_that_keeps_every_contract_passes_every_check(self):
        bench = self.run_bench(set())
        self.assertEqual(bench.failures, [])
        self.assertGreater(bench.checks, 25)
        self.assertGreaterEqual(len(bench.events), 3, "the events of the socket were read, and the lines that are not JSON objects were skipped")

    def test_a_server_that_answers_the_wrong_thing_is_counted_check_by_check(self):
        for behaviour, expected in (({"no_ok"}, "GET /healthz says ok"), ({"bad_info"}, "names the service and its version"),
                                    ({"missing_node"}, "knows bench-3"), ({"armed"}, "starts disarmed"), ({"empty_history"}, "counts the events of the run")):
            with self.subTest(behaviour=behaviour):
                bench = self.run_bench(behaviour)
                self.assertTrue(any(expected in failure for failure in bench.failures), (behaviour, bench.failures))

    def test_a_socket_that_says_nothing_fails_the_two_checks_about_the_events(self):
        bench = self.run_bench({"silent_socket"})
        self.assertTrue(any("delivered something" in failure for failure in bench.failures))
        self.assertTrue(any("mentioned bench-1" in failure for failure in bench.failures))

    def test_a_simulator_that_fails_is_a_failed_check(self):
        bench = self.run_bench(set(), simulator_code=2)
        self.assertEqual([f for f in bench.failures if "simulator delivers" in f], ["the simulator delivers every message to the server"])

    def test_the_helpers_read_status_body_and_json(self):
        with Server() as server:
            bench = bench_for(server)
            self.assertEqual(bench.request("/healthz")[0], 200)
            self.assertEqual(bench.request("/api/v1/alarms")[0], 401)
            self.assertEqual(bench.request("/api/v1/alarms", bench.tokens["operator"])[0], 200)
            self.assertEqual(bench.request("/nothing", bench.tokens["operator"])[0], 404)
            self.assertEqual(bench.json("/api/v1/alarms", bench.tokens["operator"]), {"active": [], "recent": []})
            self.assertEqual(bench.json("/nothing", bench.tokens["operator"]), {"error": "not_found"})
            self.assertEqual(bench.failures, ["GET /nothing answers 200 to the right token"])


class Running(unittest.TestCase):
    def test_run_stops_the_server_and_answers_zero_when_nothing_failed(self):
        bench = bench_live.Bench(Path("."), Path("."), list(NODES), 1.0)
        with mock.patch.object(bench, "start") as start, mock.patch.object(bench, "assertions") as assertions, mock.patch.object(bench, "stop") as stop:
            self.assertEqual(bench.run(), 0)
        start.assert_called_once()
        assertions.assert_called_once()
        stop.assert_called_once()

    def test_run_stops_the_server_even_when_the_assertions_raise_and_answers_one_on_a_failure(self):
        bench = bench_live.Bench(Path("."), Path("."), list(NODES), 1.0)
        with mock.patch.object(bench, "start"), mock.patch.object(bench, "assertions", side_effect=RuntimeError("boom")), mock.patch.object(bench, "stop") as stop:
            with self.assertRaises(RuntimeError):
                bench.run()
        stop.assert_called_once()
        bench = bench_live.Bench(Path("."), Path("."), list(NODES), 1.0)
        bench.failures.append("something")
        with mock.patch.object(bench, "start"), mock.patch.object(bench, "assertions"), mock.patch.object(bench, "stop"):
            self.assertEqual(bench.run(), 1)


class FakeProcess:
    def __init__(self, alive: bool = True, hang: bool = False) -> None:
        self.pid, self.alive, self.hang, self.terminated, self.killed = 4242, alive, hang, False, False

    def poll(self) -> int | None:
        return None if self.alive else 1

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True

    def wait(self, timeout: float) -> None:
        if self.hang and not self.killed:
            raise subprocess.TimeoutExpired("server", timeout)


class StartingAndStopping(unittest.TestCase):
    def test_the_server_is_started_from_the_build_or_from_the_sources(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder, Server() as server:
            root = Path(folder)
            bench = bench_for(server)
            bench.server_dir = root
            popen = mock.Mock(return_value=FakeProcess())
            with mock.patch.object(bench_live.subprocess, "Popen", popen):
                bench.start(folder)
            self.assertIn("src/server.ts", " ".join(popen.call_args[0][0]).replace("\\", "/"), "no build next to it: the sources are run with tsx")
            (root / "dist").mkdir()
            (root / "dist" / "server.mjs").write_text("// built", encoding="utf-8")
            popen = mock.Mock(return_value=FakeProcess())
            with mock.patch.object(bench_live.subprocess, "Popen", popen):
                bench.start(folder)
            self.assertEqual(popen.call_args[0][0][0], "node")
            environment = popen.call_args[1]["env"]
            self.assertEqual(environment["ARMOR_HOST"], "127.0.0.1")
            self.assertEqual(environment["ARMOR_INGEST_TOKEN"], bench.tokens["ingest"])
            self.assertNotIn("ARMOR_MQTT_URL", environment)

    def test_a_server_that_stops_before_it_answers_is_an_error(self):
        bench = bench_live.Bench(Path("."), Path("."), list(NODES), 1.0)
        with mock.patch.object(bench_live.subprocess, "Popen", return_value=FakeProcess(alive=False)), self.assertRaises(SystemExit) as caught:
            bench.start("data")
        self.assertIn("stopped before it answered", str(caught.exception))

    def test_a_server_that_never_answers_is_an_error_after_ninety_tries(self):
        bench = bench_live.Bench(Path("."), Path("."), list(NODES), 1.0)
        bench.port = 1   # nothing listens there
        with mock.patch.object(bench_live.subprocess, "Popen", return_value=FakeProcess()), mock.patch.object(bench_live.time, "sleep") as sleep, \
                mock.patch.object(bench, "request", side_effect=OSError), self.assertRaises(SystemExit) as caught:
            bench.start("data")
        self.assertIn("did not answer in 90 seconds", str(caught.exception))
        self.assertEqual(sleep.call_count, 90)

    def test_stop_asks_first_and_kills_what_does_not_leave(self):
        bench = bench_live.Bench(Path("."), Path("."), list(NODES), 1.0)
        bench.process = FakeProcess()
        with mock.patch.object(bench_live.os, "name", "posix"):
            bench.stop()
        self.assertTrue(bench.process.terminated and not bench.process.killed)
        bench.process = FakeProcess(hang=True)
        with mock.patch.object(bench_live.os, "name", "posix"):
            bench.stop()
        self.assertTrue(bench.process.terminated and bench.process.killed)
        bench.process = FakeProcess(alive=False)
        bench.stop()
        self.assertFalse(bench.process.terminated, "a process that is gone is not touched")
        bench.process = None
        bench.stop()

    def test_on_windows_the_tree_of_the_process_is_stopped_by_its_own_pid_only(self):
        bench = bench_live.Bench(Path("."), Path("."), list(NODES), 1.0)
        bench.process = FakeProcess()
        with mock.patch.object(bench_live.os, "name", "nt"), mock.patch.object(bench_live.subprocess, "run") as run:
            bench.stop()
        self.assertEqual(run.call_args[0][0], ["taskkill", "/PID", "4242", "/T", "/F"])


class TheSocket(unittest.TestCase):
    def test_a_refused_upgrade_is_not_101_and_the_listener_ends_on_the_close_frame(self):
        with Server() as server:
            bench = bench_for(server)
            sock, status = bench.open_socket(None)
            sock.close()
            self.assertEqual(status, 401)
            sock, status = bench.open_socket(bench.tokens["control"])
            self.assertEqual(status, 101)
            bench.listen(sock, __import__("time").time() + 5)
            sock.close()
            self.assertEqual(len(bench.events), 3)

    def test_a_connection_that_drops_ends_the_listener(self):
        left, right = socket.socketpair()
        bench = bench_live.Bench(Path("."), Path("."), list(NODES), 1.0)
        right.sendall(frame(b'{"type": "x"}'))
        right.close()
        bench.listen(left, __import__("time").time() + 5)
        left.close()
        self.assertEqual(bench.events, [{"type": "x"}])

    def test_the_frames_of_the_wire_are_cut_at_their_own_length(self):
        self.assertIsNone(bench_live.take_frame(b""))
        self.assertIsNone(bench_live.take_frame(bytes([0x81, 126, 0])))
        self.assertIsNone(bench_live.take_frame(bytes([0x81, 127]) + b"\0" * 5))
        self.assertEqual(bench_live.take_frame(bytes([0x81, 127]) + struct.pack(">Q", 2) + b"ab"), (1, b"ab", 12))


class CommandLine(unittest.TestCase):
    def test_main_builds_the_bench_from_its_arguments(self):
        with mock.patch.object(sys, "argv", ["bench_live.py", "--server", "s", "--simulator", "m", "--seconds", "2", "--nodes", "a,,b"]), \
                mock.patch.object(bench_live, "Bench") as bench:
            bench.return_value.run.return_value = 0
            self.assertEqual(bench_live.main(), 0)
        server, simulator, nodes, seconds = bench.call_args[0]
        self.assertEqual((server.name, simulator.name, nodes, seconds), ("s", "m", ["a", "b"], 2.0))

    def test_a_free_port_is_a_port(self):
        port = bench_live.free_port()
        self.assertTrue(1024 <= port <= 65535)


if __name__ == "__main__":
    unittest.main()
