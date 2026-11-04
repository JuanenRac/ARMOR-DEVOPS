#!/usr/bin/env python3
# ARMOR-DEVOPS - tests of the pieces of bench_live.py that need no server: the WebSocket frame reader and the way a failed check is counted.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bench_live  # noqa: E402


def frame(payload: bytes, opcode: int = 1) -> bytes:
    if len(payload) < 126:
        return bytes([0x80 | opcode, len(payload)]) + payload
    if len(payload) < 65536:
        return bytes([0x80 | opcode, 126]) + struct.pack(">H", len(payload)) + payload
    return bytes([0x80 | opcode, 127]) + struct.pack(">Q", len(payload)) + payload


class TakeFrame(unittest.TestCase):
    def test_the_three_length_forms(self):
        for size in (0, 5, 125, 126, 300, 65535, 65536, 70000):
            payload = b"x" * size
            opcode, body, used = bench_live.take_frame(frame(payload))  # type: ignore[misc]
            self.assertEqual((opcode, body, used), (1, payload, len(frame(payload))))

    def test_an_incomplete_frame_waits_for_more_bytes(self):
        whole = frame(b"y" * 300)
        for cut in (0, 1, 2, 3, 100, len(whole) - 1):
            self.assertIsNone(bench_live.take_frame(whole[:cut]))

    def test_two_frames_in_one_buffer_come_out_one_at_a_time(self):
        buffer = frame(b"one") + frame(b"two", 8)
        opcode, body, used = bench_live.take_frame(buffer)  # type: ignore[misc]
        self.assertEqual((opcode, body), (1, b"one"))
        opcode, body, _ = bench_live.take_frame(buffer[used:])  # type: ignore[misc]
        self.assertEqual((opcode, body), (8, b"two"))


class Counting(unittest.TestCase):
    def test_a_failed_check_is_kept_and_a_passed_one_is_not(self):
        bench = bench_live.Bench(Path("."), Path("."), ["a"], 1.0)
        bench.check(True, "fine")
        bench.check(False, "broken")
        self.assertEqual((bench.checks, bench.failures), (2, ["broken"]))

    def test_the_tokens_are_different_and_long(self):
        bench = bench_live.Bench(Path("."), Path("."), ["a"], 1.0)
        self.assertEqual(len(set(bench.tokens.values())), 3)
        self.assertTrue(all(len(token) >= 48 for token in bench.tokens.values()))


if __name__ == "__main__":
    unittest.main()
