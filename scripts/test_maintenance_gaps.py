#!/usr/bin/env python3
# ARMOR-DEVOPS - more tests of scripts/armor_maintenance_agent.py: the routes of its socket one by one (what each refuses and what each answers), the one-time codes, the allowed
# users, the helpers of the remote access, the history and the switches of Studio.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
# It reuses the stand-ins of test_maintenance_agent.py (a temporary prefix, a stand-in GitHub and systemctl); nothing real is touched. Needs Linux, macOS or WSL.
from __future__ import annotations

import base64
import json
import os
import shutil
import socket
import stat
import sys
import threading
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_maintenance_agent as base  # noqa: E402

TOKEN = base.TOKEN
UNIX = hasattr(socket, "AF_UNIX")


@unittest.skipUnless(UNIX, "needs Unix sockets")
class MaintenanceGapTests(base.MaintenanceTest):
    server: object
    socket_path: str

    def setUp(self) -> None:
        super().setUp()
        cls = type(self)
        self.agent.Handler.token = TOKEN
        self.socket_path = str(Path(cls.tmp.name) / f"gap-{id(self)}.sock")
        self.server = self.agent.UnixServer(self.socket_path, self.agent.Handler)
        threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()  # type: ignore[attr-defined]
        self.addCleanup(self.stop)
        self.agent.DATA_DIR = Path(cls.tmp.name) / "data"
        shutil.rmtree(self.agent.DATA_DIR, ignore_errors=True)
        (self.prefix / "bin").mkdir(parents=True, exist_ok=True)

    def stop(self) -> None:
        self.server.shutdown()  # type: ignore[attr-defined]
        self.server.server_close()  # type: ignore[attr-defined]

    def call(self, method: str, path: str, body: object = None, token: str | None = TOKEN, headers: dict[str, str] | None = None) -> tuple[int, dict]:
        connection = base.UnixConnection(self.socket_path)
        sent = dict(headers or {})
        if token is not None:
            sent["X-Armor-Maint-Token"] = token
        payload = None
        if body is not None:
            payload = body if isinstance(body, str) else json.dumps(body)
            sent["Content-Type"] = "application/json"
        connection.request(method, path, body=payload, headers=sent)
        response = connection.getresponse()
        raw = response.read()
        return response.status, json.loads(raw) if raw else {}

    def helper(self, name: str, text: str) -> Path:
        script = self.prefix / "bin" / name
        script.write_text(text, encoding="utf-8")
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
        return script

    # ---- the front door of the socket ----
    def test_a_missing_token_is_refused_for_every_route(self) -> None:
        for method, path in (("GET", "/v1/overview"), ("GET", "/v1/staging"), ("POST", "/v1/history/clear"), ("GET", "/v1/remote"), ("GET", "/v1/updater")):
            self.assertEqual(self.call(method, path, token=None)[0], 401, path)

    def test_a_wrong_token_of_the_same_length_is_refused(self) -> None:
        self.assertEqual(self.call("GET", "/v1/overview", token="x" * len(TOKEN))[0], 401)

    def test_an_empty_token_configured_refuses_everyone(self) -> None:
        self.agent.Handler.token = ""
        self.assertEqual(self.call("GET", "/v1/overview", token="")[0], 401)

    def test_a_path_outside_the_version_prefix_is_not_found(self) -> None:
        self.assertEqual(self.call("GET", "/overview")[0], 404)
        self.assertEqual(self.call("GET", "/v2/overview")[0], 404)

    def test_an_unknown_route_under_the_prefix_is_not_found(self) -> None:
        status, body = self.call("GET", "/v1/nothing")
        self.assertEqual((status, body["error"]), (404, "not_found"))

    def test_the_answers_are_never_cached(self) -> None:
        connection = base.UnixConnection(self.socket_path)
        connection.request("GET", "/v1/console", headers={"X-Armor-Maint-Token": TOKEN})
        response = connection.getresponse()
        response.read()
        self.assertEqual(response.getheader("Cache-Control"), "no-store")
        self.assertEqual(response.getheader("Content-Type"), "application/json")

    def test_the_console_route_says_whether_the_console_is_enabled(self) -> None:
        status, body = self.call("GET", "/v1/console")
        self.assertEqual((status, body), (200, {"enabled": True}))

    # ---- the body of a request ----
    def test_a_body_that_is_not_json_is_refused(self) -> None:
        status, body = self.call("POST", "/v1/updates", body="{not json")
        self.assertEqual((status, body["error"]), (400, "invalid_json"))

    def test_a_body_that_is_not_an_object_is_refused(self) -> None:
        status, body = self.call("POST", "/v1/updates", body="[1, 2]")
        self.assertEqual((status, body["error"]), (400, "invalid_json"))

    def test_a_body_over_the_limit_is_refused(self) -> None:
        status, body = self.call("POST", "/v1/staging", body=json.dumps({"enabled": True, "pad": "x" * 70000}))
        self.assertEqual((status, body["error"]), (413, "body_too_large"))

    def test_a_negative_or_broken_length_is_refused(self) -> None:
        for length in ("-5", "abc"):
            status, body = self.call("POST", "/v1/staging", body="{}", headers={"Content-Length": length})
            self.assertEqual((status, body.get("error")), (400, "bad_length"), length)

    # ---- updates and rollbacks ----
    def test_an_update_without_components_is_refused(self) -> None:
        for wanted in ({}, {"components": []}, {"components": "server"}, {"components": ["server", "bogus"]}):
            status, body = self.call("POST", "/v1/updates", body=wanted)
            self.assertEqual((status, body["error"]), (422, "unknown_component"), str(wanted))

    def test_a_rollback_of_an_unknown_component_is_not_found(self) -> None:
        status, body = self.call("POST", "/v1/updates/bogus/rollback", body={})
        self.assertEqual((status, body["error"]), (404, "unknown_component"))

    def test_a_rollback_is_refused_while_another_change_runs(self) -> None:
        job = self.agent.Job("system-check", [("a", "x")], label="held")
        self.agent.remember(job)
        self.addCleanup(job.finish)
        status, body = self.call("POST", "/v1/updates/server/rollback", body={})
        self.assertEqual((status, body["error"]), (409, "busy"))
        self.assertEqual(self.call("POST", "/v1/updates", body={"components": ["server"]})[0], 409)
        self.assertEqual(self.call("POST", "/v1/system/check", body={})[0], 409)

    def test_a_job_that_does_not_exist_is_not_found(self) -> None:
        status, body = self.call("GET", "/v1/jobs/no-such-job")
        self.assertEqual((status, body["error"]), (404, "no_such_job"))
        self.assertEqual(self.call("GET", "/v1/console/jobs/no-such-job")[0], 404)
        self.assertEqual(self.call("POST", "/v1/console/jobs/no-such-job/cancel", body={})[0], 404)

    def test_a_known_job_is_read_from_a_given_line(self) -> None:
        job = self.agent.Job("system-check", [("a", "x")], label="shown")
        job.say("first")
        job.say("second")
        self.agent.remember(job)
        self.addCleanup(job.finish)
        status, body = self.call("GET", f"/v1/jobs/{job.id}?since=1")
        self.assertEqual(status, 200)
        self.assertEqual(body["id"], job.id)

    # ---- the switch of the trial start of the server ----
    def test_the_staging_switch_starts_from_the_environment_and_can_be_set_from_studio(self) -> None:
        status, body = self.call("GET", "/v1/staging")
        self.assertEqual((status, body["enabled"], body["source"]), (200, False, "env"))
        status, body = self.call("POST", "/v1/staging", body={"enabled": True})
        self.assertEqual((status, body["enabled"], body["source"]), (200, True, "studio"))
        self.assertTrue(self.call("GET", "/v1/staging")[1]["enabled"])

    def test_the_staging_switch_refuses_what_is_not_a_boolean_or_has_other_keys(self) -> None:
        for bad, code in (({"enabled": "yes"}, "bad_enabled"), ({"enabled": 1}, "bad_enabled"), ({"enabled": None}, "bad_enabled"), ({"enabled": True, "x": 1}, "unknown_setting"), ({}, "unknown_setting")):
            status, body = self.call("POST", "/v1/staging", body=bad)
            self.assertEqual((status, body["error"]), (422, code), str(bad))

    def test_a_refused_staging_change_leaves_the_stored_choice_alone(self) -> None:
        self.call("POST", "/v1/staging", body={"enabled": True})
        self.call("POST", "/v1/staging", body={"enabled": "off"})
        self.assertTrue(self.call("GET", "/v1/staging")[1]["enabled"])

    def test_the_staging_environment_word_on_turns_it_on_and_nothing_else_does(self) -> None:
        for text, expected in (("ARMOR_MAINT_STAGING=on\n", True), ("ARMOR_MAINT_STAGING=ON\n", True), ("ARMOR_MAINT_STAGING=yes\n", False), ("ARMOR_MAINT_STAGING=1\n", False), ("", False)):
            self.maint_env.write_text(text, encoding="utf-8")
            self.agent.auto_state_path().unlink(missing_ok=True)
            self.assertEqual(self.agent.staging_enabled(), expected, text)

    # ---- the list of what was done ----
    def test_the_history_is_empty_cleared_and_counted(self) -> None:
        self.assertEqual(self.agent.history(), [])
        for index in range(3):
            job = self.agent.Job("system-check", [("a", "x")], label=f"n{index}")
            job.finish()
            self.agent.record_history(job)
        self.assertEqual(len(self.agent.history()), 3)
        status, body = self.call("POST", "/v1/history/clear", body={})
        self.assertEqual((status, body), (200, {"ok": True, "cleared": 3}))
        self.assertEqual(self.agent.history(), [])
        self.assertEqual(self.call("POST", "/v1/history/clear", body={})[1]["cleared"], 0)

    def test_the_history_keeps_only_the_last_two_hundred_and_shows_the_newest_first(self) -> None:
        for index in range(205):
            job = self.agent.Job("system-check", [("a", "x")], label=f"n{index}")
            job.finish()
            self.agent.record_history(job)
        stored = json.loads(self.agent.history_path().read_text(encoding="utf-8"))
        self.assertEqual(len(stored), 200)
        shown = self.agent.history()
        self.assertEqual(len(shown), 60)
        self.assertEqual(shown[0]["label"], "n204")

    def test_a_damaged_history_file_reads_as_empty(self) -> None:
        self.agent.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.agent.history_path().write_text("{broken", encoding="utf-8")
        self.assertEqual(self.agent.history(), [])
        self.agent.history_path().write_text('{"not": "a list"}', encoding="utf-8")
        self.assertEqual(self.agent.history(), [])

    # ---- the files with settings ----
    def test_the_settings_reader_takes_only_upper_case_keys_and_strips_quotes(self) -> None:
        path = Path(self.tmp.name) / "s.env"
        path.write_text("A_B=1\nlower=2\nC='quoted'\n# comment\nno separator\nD=  spaced  \nE_F=a=b\n", encoding="utf-8")
        self.assertEqual(self.agent.read_settings(path), {"A_B": "1", "C": "quoted", "D": "spaced", "E_F": "a=b"})

    def test_the_settings_reader_gives_nothing_for_a_missing_file(self) -> None:
        self.assertEqual(self.agent.read_settings(Path(self.tmp.name) / "absent.env"), {})

    def test_a_failed_helper_passes_on_one_line_without_its_name_prefix(self) -> None:
        run = mock.Mock(returncode=2, stderr="noise\narmor_wireguard: the port is taken\n\n", stdout="")
        refused = self.agent.helper_failed(run)
        self.assertEqual((refused.status, refused.code), (422, "the port is taken"))
        run = mock.Mock(returncode=1, stderr="", stdout="")
        refused = self.agent.helper_failed(run)
        self.assertEqual((refused.status, refused.code), (502, "failed"))
        run = mock.Mock(returncode=1, stderr="armor_ddns: " + "x" * 500, stdout="")
        self.assertEqual(len(self.agent.helper_failed(run).code), 300)

    def test_a_missing_helper_is_not_implemented(self) -> None:
        with self.assertRaises(self.agent.Refused) as caught:
            self.agent.run_helper(self.prefix / "bin" / "absent.sh", ["x"])
        self.assertEqual((caught.exception.status, caught.exception.code), (501, "helper_missing"))

    # ---- the remote access ----
    def test_the_remote_state_of_an_installation_with_nothing_set_up(self) -> None:
        status, body = self.call("GET", "/v1/remote")
        self.assertEqual(status, 200)
        self.assertFalse(body["wireguard"]["configured"])
        self.assertEqual(body["wireguard"]["peers"], [])
        self.assertFalse(body["ddns"]["configured"])

    def test_the_remote_state_lists_the_peers_that_have_a_name_and_an_address(self) -> None:
        folder = self.prefix / "etc" / "wireguard"
        (folder / "peers").mkdir(parents=True)
        (folder / "settings").write_text("ENDPOINT_HOST=home.example\nPORT_PUBLIC=51820\nSUBNET=10.8.0.0/24\nPORT=51820\n", encoding="utf-8")
        (folder / "peers" / "a.env").write_text("NAME=phone\nADDRESS=10.8.0.2\nFULL_TUNNEL=1\n", encoding="utf-8")
        (folder / "peers" / "b.env").write_text("NAME=laptop\nADDRESS=10.8.0.3\n", encoding="utf-8")
        (folder / "peers" / "c.env").write_text("NAME=incomplete\n", encoding="utf-8")
        state = self.call("GET", "/v1/remote")[1]["wireguard"]
        self.assertTrue(state["configured"])
        self.assertEqual(state["endpoint"], "home.example:51820")
        self.assertEqual(state["peers"], [{"name": "phone", "address": "10.8.0.2", "full_tunnel": "yes"}, {"name": "laptop", "address": "10.8.0.3", "full_tunnel": "no"}])

    def test_the_remote_state_reads_the_ddns_provider_and_the_last_address(self) -> None:
        (self.prefix / "etc").mkdir(parents=True)
        (self.prefix / "etc" / "armor.ddns.env").write_text("PROVIDER=duckdns\nDOMAIN=armor-home\n", encoding="utf-8")
        (self.prefix / "data").mkdir()
        (self.prefix / "data" / "ddns.last").write_text("203.0.113.9\n", encoding="utf-8")
        with mock.patch.dict(os.environ, {"ARMOR_DDNS_ENV": str(self.prefix / "etc" / "armor.ddns.env")}):
            ddns = self.call("GET", "/v1/remote")[1]["ddns"]
        self.assertEqual((ddns["configured"], ddns["provider"], ddns["name"], ddns["last_address"]), (True, "duckdns", "armor-home", "203.0.113.9"))

    def test_the_wireguard_setup_refuses_a_bad_endpoint_before_running_anything(self) -> None:
        for endpoint in (None, "", 5, "a b", "bad;rm", "-x.example", "x.example-", "a" * 300):
            status, body = self.call("POST", "/v1/remote/wireguard/setup", body={"endpoint": endpoint})
            self.assertEqual((status, body["error"]), (422, "bad_endpoint"), str(endpoint))

    def test_the_wireguard_setup_checks_each_optional_value(self) -> None:
        for key, value in (("lan", "10.0.0/24"), ("lan", 5), ("subnet", "10.8.0.0"), ("route_lan", "eth0 eth1"), ("route_lan", "a" * 16)):
            status, body = self.call("POST", "/v1/remote/wireguard/setup", body={"endpoint": "home.example", key: value})
            self.assertEqual((status, body["error"]), (422, f"bad_{key}"), f"{key}={value}")
        for port in (0, 65536, "51820", True, 1.5):
            status, body = self.call("POST", "/v1/remote/wireguard/setup", body={"endpoint": "home.example", "port": port})
            self.assertEqual((status, body["error"]), (422, "bad_port"), str(port))

    def test_the_wireguard_setup_without_its_script_is_not_implemented(self) -> None:
        status, body = self.call("POST", "/v1/remote/wireguard/setup", body={"endpoint": "home.example"})
        self.assertEqual((status, body["error"]), (501, "helper_missing"))

    def test_the_wireguard_setup_hands_the_script_only_checked_arguments(self) -> None:
        log = Path(self.tmp.name) / "wg-args.txt"
        self.helper("armor_wireguard.sh", f'#!/bin/bash\necho "$@" > "{log}"\nexit 0\n')
        status, body = self.call("POST", "/v1/remote/wireguard/setup", body={"endpoint": "home.example:51820", "lan": "192.168.0.0/24", "subnet": "10.8.0.0/24", "route_lan": "eth0", "port": 51820})
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        arguments = log.read_text(encoding="utf-8").split()
        self.assertEqual(arguments[:3], ["setup", "--endpoint", "home.example:51820"])
        for flag in ("--lan", "--subnet", "--route-lan", "--port", "--prefix"):
            self.assertIn(flag, arguments)
        self.assertEqual(arguments[-1], str(self.prefix))

    def test_a_script_that_fails_with_code_2_is_a_refusal_of_the_input_and_any_other_a_bad_gateway(self) -> None:
        self.helper("armor_wireguard.sh", '#!/bin/bash\necho "armor_wireguard: the name is taken" >&2\nexit 2\n')
        status, body = self.call("POST", "/v1/remote/wireguard/peers", body={"name": "phone"})
        self.assertEqual((status, body["error"]), (422, "the name is taken"))
        self.helper("armor_wireguard.sh", '#!/bin/bash\necho "boom" >&2\nexit 1\n')
        status, body = self.call("POST", "/v1/remote/wireguard/peers", body={"name": "phone"})
        self.assertEqual((status, body["error"]), (502, "boom"))

    def test_a_peer_name_is_checked_in_every_route_that_takes_one(self) -> None:
        for bad in ("", "-x", "a b", "x" * 33, 5, None):
            self.assertEqual(self.call("POST", "/v1/remote/wireguard/peers", body={"name": bad})[1]["error"], "bad_name", str(bad))
        self.assertEqual(self.call("GET", "/v1/remote/wireguard/peers/-x")[1]["error"], "bad_name")
        self.assertEqual(self.call("POST", "/v1/remote/wireguard/peers/-x/remove", body={})[1]["error"], "bad_name")

    def test_a_peer_configuration_is_cut_out_of_the_output_of_the_script(self) -> None:
        self.helper("armor_wireguard.sh", '#!/bin/bash\necho "---- peer phone ----"\necho "[Interface]"\necho "Address = 10.8.0.2/32"\necho "----"\nexit 0\n')
        status, body = self.call("GET", "/v1/remote/wireguard/peers/phone")
        self.assertEqual(status, 200)
        self.assertEqual(body["name"], "phone")
        self.assertIn("[Interface]", body["config"])
        self.assertNotIn("----", body["config"])

    def test_an_output_without_a_configuration_is_a_bad_gateway(self) -> None:
        self.helper("armor_wireguard.sh", '#!/bin/bash\necho "nothing useful"\nexit 0\n')
        status, body = self.call("GET", "/v1/remote/wireguard/peers/phone")
        self.assertEqual((status, body["error"]), (502, "no_configuration"))

    def test_removing_a_peer_runs_the_script_with_the_name(self) -> None:
        log = Path(self.tmp.name) / "wg-remove.txt"
        self.helper("armor_wireguard.sh", f'#!/bin/bash\necho "$@" > "{log}"\nexit 0\n')
        status, body = self.call("POST", "/v1/remote/wireguard/peers/phone/remove", body={})
        self.assertEqual((status, body), (200, {"ok": True}))
        self.assertTrue(log.read_text(encoding="utf-8").startswith("remove-peer phone"))

    def test_the_ddns_setup_refuses_an_unknown_provider_and_values_with_line_breaks(self) -> None:
        for provider in (None, "", "noip", 5):
            self.assertEqual(self.call("POST", "/v1/remote/ddns/setup", body={"provider": provider})[1]["error"], "bad_provider", str(provider))
        for key, value in (("domain", "a\nb"), ("token", "a\rb"), ("zone", 5), ("record_name", "x" * 1001), ("url", "a\0b")):
            status, body = self.call("POST", "/v1/remote/ddns/setup", body={"provider": "duckdns", key: value})
            self.assertEqual((status, body["error"]), (422, f"bad_{key}"), key)

    def test_the_ddns_setup_hands_the_script_the_values(self) -> None:
        log = Path(self.tmp.name) / "ddns-args.txt"
        self.helper("armor_ddns.sh", f'#!/bin/bash\necho "$@" > "{log}"\nexit 0\n')
        status, body = self.call("POST", "/v1/remote/ddns/setup", body={"provider": "duckdns", "domain": "armor-home", "token": "abc"})
        self.assertEqual(status, 200)
        text = log.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("setup --provider duckdns --domain armor-home --token abc"))
        self.assertTrue(body["ok"])

    def test_the_ddns_update_and_remove_call_the_script_and_report_a_failure(self) -> None:
        self.helper("armor_ddns.sh", '#!/bin/bash\nexit 0\n')
        self.assertEqual(self.call("POST", "/v1/remote/ddns/update", body={})[0], 200)
        self.assertEqual(self.call("POST", "/v1/remote/ddns/remove", body={})[0], 200)
        self.helper("armor_ddns.sh", '#!/bin/bash\necho "armor_ddns: the provider said no" >&2\nexit 1\n')
        status, body = self.call("POST", "/v1/remote/ddns/update", body={})
        self.assertEqual((status, body["error"]), (502, "the provider said no"))

    # ---- the one-time codes (RFC 6238) ----
    def test_the_code_matches_the_vector_of_the_rfc(self) -> None:
        secret = base64.b32encode(b"12345678901234567890").decode()
        self.assertEqual(self.agent.totp_code(secret, 59 // 30, 8), "94287082")
        self.assertEqual(self.agent.totp_code(secret, 1111111109 // 30, 8), "07081804")
        self.assertEqual(self.agent.totp_code(secret, 2000000000 // 30, 8), "69279037")

    def test_the_code_is_six_digits_with_leading_zeros(self) -> None:
        secret = base64.b32encode(b"12345678901234567890").decode()
        for counter in range(40):
            code = self.agent.totp_code(secret, counter)
            self.assertRegex(code, r"^\d{6}$")

    def test_the_code_ignores_spaces_and_case_of_the_secret(self) -> None:
        secret = base64.b32encode(b"12345678901234567890").decode()
        spaced = " ".join(secret[i:i + 4] for i in range(0, len(secret), 4)).lower()
        self.assertEqual(self.agent.totp_code(spaced, 7), self.agent.totp_code(secret, 7))

    def test_a_good_code_is_spent_and_a_neighbouring_step_is_accepted_once(self) -> None:
        secret = base64.b32encode(b"12345678901234567890").decode()
        self.agent._totp_last_counter[0] = 0
        now = 1_000_000_000.0
        step = int(now // 30)
        self.assertTrue(self.agent.totp_accepts(secret, self.agent.totp_code(secret, step), now))
        self.assertFalse(self.agent.totp_accepts(secret, self.agent.totp_code(secret, step), now))
        self.assertTrue(self.agent.totp_accepts(secret, self.agent.totp_code(secret, step + 1), now))
        self.assertFalse(self.agent.totp_accepts(secret, self.agent.totp_code(secret, step - 1), now))

    def test_a_code_two_steps_away_or_of_the_wrong_shape_is_refused(self) -> None:
        secret = base64.b32encode(b"12345678901234567890").decode()
        self.agent._totp_last_counter[0] = 0
        now = 1_000_000_000.0
        step = int(now // 30)
        self.assertFalse(self.agent.totp_accepts(secret, self.agent.totp_code(secret, step + 5), now))
        for bad in ("", "12345", "1234567", "12345a", None, 123456):
            self.assertFalse(self.agent.totp_accepts(secret, bad, now), str(bad))  # type: ignore[arg-type]

    def test_the_enrolment_writes_a_secret_of_mode_0600_and_it_is_new_every_time(self) -> None:
        path = Path(self.tmp.name) / "etc" / "maint.totp"
        with mock.patch.dict(os.environ, {"ARMOR_MAINT_TOTP_FILE": str(path)}):
            first = self.agent.totp_enroll()
            self.assertEqual(path.read_text(encoding="ascii").strip(), first)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(len(base64.b32decode(first)), 20)
            second = self.agent.totp_enroll()
        self.assertNotEqual(first, second)

    # ---- who may make a sensitive call ----
    def test_the_allowed_users_are_read_from_a_list_and_a_junk_item_is_dropped(self) -> None:
        with mock.patch.dict(os.environ, {"ARMOR_MAINT_PEER_UIDS": "0, 1000,,x,-3, 12"}):
            self.assertEqual(self.agent.peer_uids(), [0, 1000, 12])
        with mock.patch.dict(os.environ, {"ARMOR_MAINT_PEER_UIDS": "  "}):
            self.assertIsNone(self.agent.peer_uids())
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ARMOR_MAINT_PEER_UIDS", None)
            self.assertIsNone(self.agent.peer_uids())

    def test_the_credentials_of_a_connection_that_cannot_say_are_none(self) -> None:
        self.assertIsNone(self.agent.peer_credentials(object()))
        broken = mock.Mock()
        broken.getsockopt.side_effect = OSError("no")
        self.assertIsNone(self.agent.peer_credentials(broken))

    def test_the_credentials_of_a_real_pair_of_sockets_are_this_process(self) -> None:
        left, right = socket.socketpair()
        try:
            pid, uid, _gid = self.agent.peer_credentials(left)
            self.assertEqual((pid, uid), (os.getpid(), os.getuid()))
        finally:
            left.close()
            right.close()

    def test_a_sensitive_call_is_refused_to_a_user_that_is_not_in_the_list(self) -> None:
        route = next(iter(self.agent.SENSITIVE_ROUTES))
        method, parts = route
        with mock.patch.dict(os.environ, {"ARMOR_MAINT_PEER_UIDS": "1000"}):
            with self.assertRaises(self.agent.Refused) as caught:
                self.agent.guard_sensitive(method, list(parts), (1, 5, 5), "")
            self.assertEqual((caught.exception.status, caught.exception.code), (403, "peer_not_allowed"))
            with self.assertRaises(self.agent.Refused):
                self.agent.guard_sensitive(method, list(parts), None, "")
            self.agent.guard_sensitive(method, list(parts), (1, 1000, 1000), "")      # the allowed user passes

    def test_a_route_that_is_not_sensitive_is_never_guarded(self) -> None:
        with mock.patch.dict(os.environ, {"ARMOR_MAINT_PEER_UIDS": "1000"}):
            self.agent.guard_sensitive("GET", ["overview"], (1, 5, 5), "")

    def test_a_sensitive_call_wants_the_code_when_a_secret_is_enrolled(self) -> None:
        method, parts = next(iter(self.agent.SENSITIVE_ROUTES))
        path = Path(self.tmp.name) / "guard.totp"
        secret = base64.b32encode(b"12345678901234567890").decode()
        path.write_text(secret + "\n", encoding="ascii")
        self.agent._totp_last_counter[0] = 0
        with mock.patch.dict(os.environ, {"ARMOR_MAINT_TOTP_FILE": str(path)}):
            os.environ.pop("ARMOR_MAINT_PEER_UIDS", None)
            with self.assertRaises(self.agent.Refused) as caught:
                self.agent.guard_sensitive(method, list(parts), None, "")
            self.assertEqual(caught.exception.code, "totp_required")
            with self.assertRaises(self.agent.Refused) as caught:
                self.agent.guard_sensitive(method, list(parts), None, "000000")
            self.assertEqual(caught.exception.code, "totp_invalid")

    # ---- the engine of updates of programs ----
    def test_the_updater_is_off_by_default_and_says_so(self) -> None:
        status, body = self.call("GET", "/v1/updater")
        self.assertEqual(status, 200)
        self.assertFalse(body["enabled"])
        self.assertTrue(body["require_signed"])
        status, body = self.call("POST", "/v1/updater/preview", body={"project": "ARMOR-SERVER"})
        self.assertEqual((status, body["error"]), (403, "updater_disabled"))
        status, body = self.call("POST", "/v1/updater/apply", body={"project": "ARMOR-SERVER"})
        self.assertEqual((status, body["error"]), (403, "updater_disabled"))

    def test_a_project_name_is_checked_against_a_pattern_and_a_list(self) -> None:
        for bad in (None, 5, "armor-server", "ARMOR-", "ARMOR-A B", "ARMOR-" + "A" * 41, "../ARMOR-X", "ARMOR-NOT-LISTED"):
            with self.assertRaises(self.agent.Refused, msg=str(bad)) as caught:
                self.agent.updater_project({"project": bad})
            self.assertEqual(caught.exception.code, "unknown_project")


for _name in [n for n in dir(base.MaintenanceTest) if n.startswith("test_")]:
    setattr(MaintenanceGapTests, _name, None)              # the tests of the parent class run in their own module, not twice


if __name__ == "__main__":
    unittest.main()
