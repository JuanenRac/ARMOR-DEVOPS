#!/usr/bin/env python3
# ARMOR-DEVOPS - the Ed25519 verifier of scripts/armor_maintenance_agent.py against the fixed cases of scripts/fixtures/ed25519_vectors.json.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
# The cases are data (the three vectors of RFC 8032 and changes of them that must be refused), so another verifier of the family can be tried against the same file.
from __future__ import annotations

import importlib.util
import json
import socketserver
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
VECTORS = json.loads((HERE / "fixtures" / "ed25519_vectors.json").read_text(encoding="utf-8"))["vectors"]


def load_agent():
    spec = importlib.util.spec_from_file_location("armor_maintenance_agent_vectors", HERE / "armor_maintenance_agent.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(hasattr(socketserver, "UnixStreamServer"), "the helper is a Linux service (Unix sockets): run on Linux, macOS or WSL")
class Ed25519VectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.agent = load_agent()

    def test_every_case_gives_its_answer(self) -> None:
        for case in VECTORS:
            with self.subTest(case["name"]):
                got = self.agent.ed25519_verify(bytes.fromhex(case["public_key"]), bytes.fromhex(case["message"]), bytes.fromhex(case["signature"]))
                self.assertIs(got, case["valid"])

    def test_the_file_holds_good_and_bad_cases_with_a_name_each(self) -> None:
        names = [case["name"] for case in VECTORS]
        self.assertEqual(len(names), len(set(names)))
        self.assertGreaterEqual(sum(case["valid"] for case in VECTORS), 3)
        self.assertGreaterEqual(sum(not case["valid"] for case in VECTORS), 40)

    def test_every_family_of_bad_input_is_present(self) -> None:
        text = " ".join(case["name"] for case in VECTORS if not case["valid"])
        for family in ("S plus the group order", "S equal to the group order", "public key not canonical", "R not canonical", "small order", "not on the curve", "bytes", "one bit of R"):
            self.assertIn(family, text)


if __name__ == "__main__":
    unittest.main()
