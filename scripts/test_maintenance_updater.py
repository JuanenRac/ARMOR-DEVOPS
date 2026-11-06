#!/usr/bin/env python3
# ARMOR-DEVOPS - tests of the update of a program through the engine of ARMOR-UPDATER, as the maintenance helper offers it: off by default, a preview that hands out a one-use plan,
# an apply that wants the plan, the sensitive-call checks, the rate limit, the closed list of projects and the signature policy that is always forced.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
# Nothing real is touched: the engine is a stand-in script in a temporary folder that writes what it was given. Needs Linux, macOS or WSL (the stand-in is a shell script).
from __future__ import annotations

import importlib.util
import json
import os
import stat
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("armor_maintenance_agent", HERE / "armor_maintenance_agent.py")
assert spec is not None and spec.loader is not None
agent = importlib.util.module_from_spec(spec)
sys.modules["armor_maintenance_agent"] = agent
spec.loader.exec_module(agent)

STATUS = {
    "projects": [
        {"name": "ARMOR-SERVER", "installed": True, "local_version": "0.8.1.8", "github_version": "0.8.1.9", "state": "OUTDATED"},
        {"name": "ARMOR-STUDIO", "installed": True, "local_version": "0.8.2.1", "github_version": "0.8.2.1", "state": "UP TO DATE"},
    ],
    "signature_policy": "require",
}


def stand_in(folder: Path, status: dict[str, object], update_ok: bool = True) -> Path:
    """A shell script that answers `status` and `update` like the engine and writes its arguments and the signature variable to a log."""
    binary = folder / "armor-updater"
    log = folder / "calls.log"
    update = {"project": "x", "action": "update", "ok": update_ok, "error": "" if update_ok else "signature missing", "results": []}
    binary.write_text(
        "#!/bin/sh\n"
        f'echo "$@ REQUIRE=$ARMOR_UPDATER_REQUIRE_SIGNED" >> {log}\n'
        f'if [ "$1" = "status" ]; then cat <<\'EOF\'\n{json.dumps(status, indent=2)}\nEOF\n'
        f"else echo 'human line on stderr' >&2; echo '{json.dumps(update)}'; fi\n",
        encoding="utf-8",
    )
    binary.chmod(binary.stat().st_mode | stat.S_IXUSR)
    return binary


class UpdaterBridgeTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.binary = stand_in(self.root, STATUS)
        env = {"ARMOR_MAINT_UPDATER": "1", "ARMOR_UPDATER_BIN": str(self.binary), "ARMOR_UPDATER_WORKSPACE": str(self.root / "ws"),
               "ARMOR_MAINT_UPDATER_MIN_INTERVAL_S": "0", "ARMOR_MAINT_DATA": str(self.root / "data"), "ARMOR_UPDATER_REQUIRE_SIGNED": "0"}
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        agent._updater_plans.clear()
        agent._updater_clock.update({"apply": 0.0, "preview": 0.0})
        agent.JOBS.clear()

    def wait(self, job):
        for _ in range(200):
            if job.state != "running":
                return
            time.sleep(0.05)
        self.fail("the job did not finish")

    def refused(self, call, *args):
        with self.assertRaises(agent.Refused) as caught:
            call(*args)
        return caught.exception.status, caught.exception.code

    def test_it_is_off_until_it_is_turned_on(self):
        with mock.patch.dict(os.environ, {"ARMOR_MAINT_UPDATER": ""}):
            self.assertFalse(agent.updater_state()["enabled"])
            self.assertEqual(self.refused(agent.updater_preview, {"project": "ARMOR-SERVER"}), (403, "updater_disabled"))
            self.assertEqual(self.refused(agent.updater_apply, {"project": "ARMOR-SERVER", "plan_id": "x"}), (403, "updater_disabled"))

    def test_only_the_projects_the_helper_manages_are_accepted(self):
        for name in ("ARMOR-UNKNOWN", "../ARMOR-SERVER", "armor-server", "ARMOR-SERVER; rm -rf /", "", None, 7):
            self.assertEqual(self.refused(agent.updater_preview, {"project": name}), (422, "unknown_project"), name)

    def test_the_preview_says_what_is_installed_and_hands_out_a_plan_for_an_outdated_one(self):
        view = agent.updater_preview({"project": "ARMOR-SERVER"})
        self.assertEqual((view["local_version"], view["github_version"], view["update_available"]), ("0.8.1.8", "0.8.1.9", True))
        self.assertEqual(len(str(view["plan_id"])), 24)
        self.assertEqual(view["signature_policy"], "require")
        agent._updater_clock["preview"] = 0.0
        current = agent.updater_preview({"project": "ARMOR-STUDIO"})
        self.assertFalse(current["update_available"])
        self.assertNotIn("plan_id", current)
        self.assertNotIn("apply", (self.root / "calls.log").read_text())

    def test_the_preview_is_rate_limited(self):
        agent.updater_preview({"project": "ARMOR-SERVER"})
        self.assertEqual(self.refused(agent.updater_preview, {"project": "ARMOR-SERVER"}), (429, "too_soon"))

    def test_the_preview_refuses_an_engine_that_does_not_enforce_signatures(self):
        stand_in(self.root, {**STATUS, "signature_policy": "warn"})
        self.assertEqual(self.refused(agent.updater_preview, {"project": "ARMOR-SERVER"}), (409, "signature_not_enforced"))

    def test_the_apply_needs_the_plan_of_a_preview_and_a_plan_is_good_once(self):
        self.assertEqual(self.refused(agent.updater_apply, {"project": "ARMOR-SERVER"}), (404, "no_such_plan"))
        self.assertEqual(self.refused(agent.updater_apply, {"project": "ARMOR-SERVER", "plan_id": "0" * 24}), (404, "no_such_plan"))
        plan = str(agent.updater_preview({"project": "ARMOR-SERVER"})["plan_id"])
        job = agent.updater_apply({"project": "ARMOR-SERVER", "plan_id": plan})
        self.wait(job)
        self.assertEqual(job.state, "done")
        self.assertEqual(job.result["ok"], True)
        self.assertEqual(job.result["target"], "0.8.1.9")
        self.assertEqual(self.refused(agent.updater_apply, {"project": "ARMOR-SERVER", "plan_id": plan}), (404, "no_such_plan"))

    def test_a_plan_of_another_project_or_an_old_one_is_refused(self):
        plan = str(agent.updater_preview({"project": "ARMOR-SERVER"})["plan_id"])
        self.assertEqual(self.refused(agent.updater_apply, {"project": "ARMOR-STUDIO", "plan_id": plan}), (422, "plan_mismatch"))
        agent._updater_plans["old"] = {"project": "ARMOR-SERVER", "target": "1", "expires": time.time() - 1}
        self.assertEqual(self.refused(agent.updater_apply, {"project": "ARMOR-SERVER", "plan_id": "old"}), (410, "plan_expired"))

    def test_the_signature_policy_is_forced_and_the_engine_is_started_without_a_shell(self):
        plan = str(agent.updater_preview({"project": "ARMOR-SERVER"})["plan_id"])
        self.wait(agent.updater_apply({"project": "ARMOR-SERVER", "plan_id": plan}))
        calls = (self.root / "calls.log").read_text().splitlines()
        self.assertTrue(all(line.endswith("REQUIRE=1") for line in calls), calls)
        self.assertEqual(calls[-1], f"update ARMOR-SERVER --workspace {self.root / 'ws'} --json REQUIRE=1")

    def test_a_failed_update_is_reported_as_failed(self):
        stand_in(self.root, STATUS, update_ok=False)
        plan = str(agent.updater_preview({"project": "ARMOR-SERVER"})["plan_id"])
        job = agent.updater_apply({"project": "ARMOR-SERVER", "plan_id": plan})
        self.wait(job)
        self.assertEqual((job.state, job.error, job.result["ok"]), ("failed", "update_failed", False))

    def test_two_applies_in_a_row_are_held_back(self):
        with mock.patch.dict(os.environ, {"ARMOR_MAINT_UPDATER_MIN_INTERVAL_S": "300"}):
            first = str(agent.updater_preview({"project": "ARMOR-SERVER"})["plan_id"])
            self.wait(agent.updater_apply({"project": "ARMOR-SERVER", "plan_id": first}))
            agent._updater_clock["preview"] = 0.0
            second = str(agent.updater_preview({"project": "ARMOR-SERVER"})["plan_id"])
            self.assertEqual(self.refused(agent.updater_apply, {"project": "ARMOR-SERVER", "plan_id": second}), (429, "too_soon"))

    def test_a_missing_engine_is_said(self):
        with mock.patch.dict(os.environ, {"ARMOR_UPDATER_BIN": str(self.root / "nothing")}):
            self.assertFalse(agent.updater_state()["available"])
            self.assertEqual(self.refused(agent.updater_preview, {"project": "ARMOR-SERVER"}), (501, "updater_missing"))

    def test_the_apply_is_a_sensitive_call_and_the_preview_is_not(self):
        self.assertIn(("POST", ("updater", "apply")), agent.SENSITIVE_ROUTES)
        self.assertNotIn(("POST", ("updater", "preview")), agent.SENSITIVE_ROUTES)
        with mock.patch.dict(os.environ, {"ARMOR_MAINT_PEER_UIDS": "998"}):
            with self.assertRaises(agent.Refused) as caught:
                agent.guard_sensitive("POST", ["updater", "apply"], (1, 1000, 1), "")
            self.assertEqual(caught.exception.code, "peer_not_allowed")
            agent.guard_sensitive("POST", ["updater", "preview"], (1, 1000, 1), "")


if __name__ == "__main__":
    unittest.main()
