#!/usr/bin/env python3
# ARMOR-DEVOPS - the generator of the identity script's access lines (generate_node_roles.py): what it writes for each kind of identity, that the committed script is what the table
# makes, and that the check refuses a script that drifted. Nothing is written to the repository: the rewrite runs on copies.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate_node_roles as roles  # noqa: E402

HERE = Path(__file__).resolve().parent
TABLE = json.loads((HERE / "node_roles.json").read_text(encoding="utf-8"))["roles"]


class WhatItWrites(unittest.TestCase):
    def test_the_placeholder_of_the_name_becomes_the_shell_variable(self):
        self.assertEqual(roles.shell_text("armor/node/{name}/#"), "armor/node/$NAME/#")
        self.assertEqual(roles.shell_text("no placeholder"), "no placeholder")

    def test_every_kind_has_its_user_and_its_lines(self):
        text = roles.generated()
        self.assertIn("role_user() {", text)
        self.assertIn("role_lines() {", text)
        for role, entry in TABLE.items():
            self.assertIn(f"    {role}) echo \"{roles.shell_text(entry['user'])}\" ;;", text, role)
            for line in entry["topics"]:
                self.assertIn(f'echo "{roles.shell_text(line)}"', text, (role, line))
        self.assertIn("*) return 1 ;;", text, "an unknown kind is refused")

    def test_the_wide_line_of_the_relaxed_mode_is_only_written_behind_the_switch(self):
        with_extra = [role for role, entry in TABLE.items() if entry.get("relaxed_extra")]
        text = roles.generated()
        self.assertEqual(text.count('${ARMOR_ACL_STRICT_MAINTENANCE_COMMAND:-1}" == "0"'), len(with_extra))
        for role in with_extra:
            for line in TABLE[role]["relaxed_extra"]:
                at = text.index(f'echo "{roles.shell_text(line)}"')
                self.assertIn('== "0" ]]', text[max(0, at - 160):at], f"{role}: the line {line} is not behind the switch")

    def test_a_table_with_a_relaxed_line_and_one_without_are_both_written(self):
        table = {"roles": {"alpha": {"user": "alpha-{name}", "topics": ["a/{name}/#"], "relaxed_extra": ["a/#"]}, "beta": {"user": "beta", "topics": []}}}
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "node_roles.json").write_text(json.dumps(table), encoding="utf-8")
            with mock.patch.object(roles, "HERE", Path(folder)):
                text = roles.generated()
        self.assertIn('alpha) echo "alpha-$NAME" ;;', text)
        self.assertIn('echo "a/$NAME/#"', text)
        self.assertIn('echo "a/#"', text)
        self.assertEqual(text.count("ARMOR_ACL_STRICT_MAINTENANCE_COMMAND"), 1, "only the kind that has a relaxed line gets the switch")
        self.assertIn("    beta)\n      ;;", text)


class TheScript(unittest.TestCase):
    def test_the_committed_script_is_what_the_table_makes(self):
        current = (HERE / "mqtt_identity.sh").read_text(encoding="utf-8")
        self.assertEqual(roles.rewrite(current).replace("\r\n", "\n"), current.replace("\r\n", "\n"))

    def test_rewriting_changes_only_what_is_between_the_markers(self):
        text = "before\n" + roles.BEGIN + "\nold lines\n" + roles.END + "\nafter\n"
        new = roles.rewrite(text)
        self.assertTrue(new.startswith("before\n" + roles.BEGIN + "\nrole_user() {"))
        self.assertTrue(new.endswith(roles.END + "\nafter\n"))
        self.assertNotIn("old lines", new)
        self.assertEqual(roles.rewrite(new), new, "writing twice changes nothing")

    def test_a_script_without_the_markers_is_refused(self):
        with self.assertRaises(ValueError):
            roles.rewrite("no markers here\n")


class TheCommand(unittest.TestCase):
    def run_main(self, folder: str, argv: list[str], text: str) -> tuple[int, str]:
        script = Path(folder) / "mqtt_identity.sh"
        script.write_text(text, encoding="utf-8", newline="\n")
        (Path(folder) / "node_roles.json").write_text((HERE / "node_roles.json").read_text(encoding="utf-8"), encoding="utf-8")
        with mock.patch.object(roles, "HERE", Path(folder)), mock.patch.object(sys, "argv", ["generate_node_roles.py", *argv]):
            code = roles.main()
        return code, script.read_text(encoding="utf-8")

    def test_check_passes_on_a_script_that_is_current_and_fails_on_one_that_drifted(self):
        with tempfile.TemporaryDirectory() as folder:
            stale = "head\n" + roles.BEGIN + "\nstale\n" + roles.END + "\ntail\n"
            code, after = self.run_main(folder, ["--check"], stale)
            self.assertEqual(code, 1)
            self.assertEqual(after, stale, "--check never writes")
            current = roles.rewrite(stale)
            code, _ = self.run_main(folder, ["--check"], current)
            self.assertEqual(code, 0)

    def test_without_check_the_script_is_rewritten(self):
        with tempfile.TemporaryDirectory() as folder:
            stale = "head\n" + roles.BEGIN + "\nstale\n" + roles.END + "\ntail\n"
            code, after = self.run_main(folder, [], stale)
            self.assertEqual(code, 0)
            self.assertNotIn("stale", after)
            self.assertIn("role_lines() {", after)


if __name__ == "__main__":
    unittest.main()
