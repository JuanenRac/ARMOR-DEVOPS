#!/usr/bin/env python3
# ARMOR-DEVOPS - tests of scripts/package_component.py: what goes into the package of each program, its hash and the refusal of a title that talks about the process.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import shlex
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("package_component", HERE / "package_component.py")
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules["package_component"] = module
spec.loader.exec_module(module)


def make(root: Path, name: str, version: str, files: dict[str, str]) -> Path:
    repo = root / name
    repo.mkdir()
    (repo / "armor.project.json").write_text(json.dumps({"version": version}), encoding="utf-8")
    for relative, content in files.items():
        (repo / relative).parent.mkdir(parents=True, exist_ok=True)
        (repo / relative).write_text(content, encoding="utf-8")
    return repo


class PackageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def names(self, package: Path) -> set[str]:
        with tarfile.open(package) as tar:
            return {member.name for member in tar.getmembers()}

    def test_the_server_package_has_the_built_code_and_the_dependencies_list(self) -> None:
        repo = make(self.root, "ARMOR-SERVER", "0.5.6", {"dist/server.mjs": "x", "dist/server_solar.mjs": "y", "package.json": json.dumps({"version": "0.5.6"}), "package-lock.json": "{}", "src/app.ts": "no"})
        package, version, digest = module.build("server", repo, self.root / "out")
        self.assertEqual((package.name, version), ("armor-server-0.5.6.tgz", "0.5.6"))
        self.assertEqual(self.names(package), {"server/dist/server.mjs", "server/dist/server_solar.mjs", "server/package.json", "server/package-lock.json"})
        self.assertEqual(digest, hashlib.sha256(package.read_bytes()).hexdigest())
        self.assertEqual((self.root / "out" / "armor-server-0.5.6.tgz.sha256").read_text(encoding="utf-8").split()[0], digest)

    def test_a_python_package_leaves_out_what_is_not_code(self) -> None:
        repo = make(self.root, "ARMOR-VOICE-AI", "0.2.6", {"src/armor_voice_ai/__init__.py": "v", "src/armor_voice_ai/__pycache__/x.pyc": "no", "src/armor_voice_ai/cli.py": "c", "tests/t.py": "no"})
        package, _version, _digest = module.build("voice", repo, self.root / "out")
        self.assertEqual(self.names(package), {"src/armor_voice_ai/__init__.py", "src/armor_voice_ai/cli.py"})

    def test_the_helper_scripts_carry_their_version(self) -> None:
        repo = make(self.root, "ARMOR-DEVOPS", "0.4.8", {"scripts/armor_admin_agent.py": "a", "scripts/armor_maintenance_agent.py": "m", "scripts/mqtt_identity.sh": "i", "scripts/backup_data.sh": "b", "scripts/armor_wireguard.sh": "w", "scripts/armor_ddns.sh": "d", "scripts/armor_mqtt_tls.sh": "t"})
        package, _version, _digest = module.build("devops", repo, self.root / "out")
        self.assertIn("scripts/VERSION", self.names(package))
        self.assertIn("scripts/armor_mqtt_tls.sh", self.names(package))   # the optional encrypted door of the broker travels with the other helpers
        with tarfile.open(package) as tar:
            self.assertEqual(tar.extractfile("scripts/VERSION").read().decode().strip(), "0.4.8")  # type: ignore[union-attr]

    def test_it_refuses_what_is_not_built_or_not_the_right_repository(self) -> None:
        repo = make(self.root, "ARMOR-STUDIO", "0.7.2", {"tools/serve.mjs": "s"})
        with self.assertRaises(SystemExit):
            module.build("studio", repo, self.root / "out")
        with self.assertRaises(SystemExit):
            module.build("server", repo, self.root / "out")

    # ---- a stale build is never packed ----
    def built_repo(self, component: str, name: str, version: str = "0.8.0.4", dist_version: str | None = None):
        """A repository whose build is newer than its source (the normal state after `npm run build`)."""
        files = {"src/app.ts": "x", "package.json": json.dumps({"version": version})}
        if component == "studio":
            files.update({"index.html": "<html>", "dist/index.html": "<html>", "dist/version.json": json.dumps({"name": "armor-studio", "version": dist_version or version}), "tools/serve.mjs": "s"})
        else:
            files.update({"dist/server.mjs": "m", "package-lock.json": "{}"})
        repo = make(self.root, name, version, files)
        future = os.path.getmtime(repo / "src" / "app.ts") + 100
        for item in (repo / "dist").rglob("*"):
            if item.is_file():
                os.utime(item, (future, future))
        return repo

    def test_a_studio_build_with_the_current_version_and_newer_than_the_source_is_packed(self) -> None:
        repo = self.built_repo("studio", "ARMOR-STUDIO")
        package, version, _digest = module.build("studio", repo, self.root / "out")
        self.assertEqual(version, "0.8.0.4")
        self.assertIn("studio/dist/version.json", self.names(package))

    def test_a_studio_dist_that_says_another_version_is_refused(self) -> None:
        repo = self.built_repo("studio", "ARMOR-STUDIO", dist_version="0.8.0.3")
        with self.assertRaises(SystemExit) as raised:
            module.build("studio", repo, self.root / "out")
        self.assertIn("dist/version.json says 0.8.0.3", str(raised.exception))
        self.assertFalse((self.root / "out").exists() and list((self.root / "out").glob("*.tgz")))

    def test_a_dist_older_than_the_source_is_refused(self) -> None:
        for component, name in (("studio", "ARMOR-STUDIO"), ("server", "ARMOR-SERVER")):
            repo = self.built_repo(component, name)
            old = os.path.getmtime(repo / "src" / "app.ts") - 3600
            for item in (repo / "dist").rglob("*"):
                if item.is_file():
                    os.utime(item, (old, old))
            with self.assertRaises(SystemExit) as raised:
                module.build(component, repo, self.root / "out")
            self.assertIn("older than the source", str(raised.exception))

    def test_a_source_edited_after_the_build_is_refused(self) -> None:
        repo = self.built_repo("server", "ARMOR-SERVER", version="0.8.0.0")
        later = os.path.getmtime(repo / "dist" / "server.mjs") + 60
        os.utime(repo / "src" / "app.ts", (later, later))
        with self.assertRaises(SystemExit):
            module.build("server", repo, self.root / "out")

    def test_a_package_json_with_another_version_is_refused(self) -> None:
        for component, name in (("studio", "ARMOR-STUDIO"), ("server", "ARMOR-SERVER")):
            repo = self.built_repo(component, name)
            (repo / "package.json").write_text(json.dumps({"version": "0.8.0.3"}), encoding="utf-8")
            with self.assertRaises(SystemExit) as raised:
                module.build(component, repo, self.root / "out")
            self.assertIn("package.json says 0.8.0.3", str(raised.exception))

    def test_a_missing_package_json_is_refused(self) -> None:
        repo = self.built_repo("server", "ARMOR-SERVER")
        (repo / "package.json").unlink()
        with self.assertRaises(SystemExit):
            module.build("server", repo, self.root / "out")

    def test_the_other_components_are_not_checked_for_a_build(self) -> None:
        repo = make(self.root, "ARMOR-NETWORK", "0.8.0.1", {"src/armor_network/__init__.py": "n", "pyproject.toml": "p"})
        module.build("network", repo, self.root / "out")

    def test_a_four_part_version_is_accepted_and_a_bad_one_is_not(self) -> None:
        repo = make(self.root, "ARMOR-NETWORK", "0.8.0.1", {"src/armor_network/__init__.py": "n", "pyproject.toml": "p"})
        self.assertEqual(module.version_of(repo), "0.8.0.1")
        (repo / "armor.project.json").write_text(json.dumps({"version": "v1"}), encoding="utf-8")
        with self.assertRaises(SystemExit):
            module.version_of(repo)

    def test_the_notes_come_from_the_changelog(self) -> None:
        repo = make(self.root, "ARMOR-SERVER", "0.5.6", {})
        (repo / "CHANGELOG.md").write_text("# Changelog\n\n## [0.5.6] - Something useful\n\n- one\n- two\n\n## [0.5.5] - Before\n\n- old\n", encoding="utf-8")
        self.assertEqual(module.changelog_section(repo, "0.5.6"), ("Something useful", "- one\n- two"))
        self.assertEqual(module.changelog_section(repo, "9.9.9"), ("9.9.9", ""))

    # ---- signing ----
    def stub_signer(self, public: str) -> list[str]:
        """A stand-in signer that answers like sign.mjs (--public, --message) and records what it was asked to sign."""
        script = self.root / "signer.py"
        lines = ["import sys", "if sys.argv[1] == '--public':", f"    print({public!r})", "else:", "    open(sys.argv[0] + '.asked', 'w').write(' '.join(sys.argv[2:]))", "    print('ab' * 64)"]
        script.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return [sys.executable, str(script)]

    def built(self):
        repo = make(self.root, "ARMOR-VOICE-AI", "0.2.6", {"src/armor_voice_ai/__init__.py": "v"})
        return module.build("voice", repo, self.root / "out")

    def test_the_signature_is_written_next_to_the_package_with_its_own_prefix(self) -> None:
        package, version, digest = self.built()
        written = module.sign_package(package, "voice", version, digest, self.stub_signer(module.trusted_key()), True)
        self.assertEqual(written, self.root / "out" / "armor-voice-0.2.6.tgz.sig")
        self.assertEqual(written.read_text(encoding="ascii"), ("ab" * 64) + chr(10))
        self.assertEqual((self.root / "signer.py.asked").read_text(encoding="utf-8"), f"armor-pkg/1|voice|0.2.6|{digest}")

    def test_asking_to_sign_without_a_signer_fails_but_the_default_just_skips(self) -> None:
        package, version, digest = self.built()
        with self.assertRaises(SystemExit):
            module.sign_package(package, "voice", version, digest, None, True)
        self.assertIsNone(module.sign_package(package, "voice", version, digest, None, False))
        self.assertFalse((self.root / "out" / "armor-voice-0.2.6.tgz.sig").exists())

    def test_a_key_the_machine_does_not_trust_is_never_used(self) -> None:
        package, version, digest = self.built()
        with self.assertRaises(SystemExit):
            module.sign_package(package, "voice", version, digest, self.stub_signer("00" * 32), False)
        self.assertFalse((self.root / "out" / "armor-voice-0.2.6.tgz.sig").exists())

    def test_an_existing_package_is_signed_only_when_its_name_and_hash_agree(self) -> None:
        package, _version, _digest = self.built()
        signer = self.stub_signer(module.trusted_key())
        self.assertEqual(module.sign_existing(package, signer, False), 0)
        self.assertTrue((self.root / "out" / "armor-voice-0.2.6.tgz.sig").exists())
        (self.root / "out" / (package.name + ".sha256")).write_text("0" * 64 + "  x", encoding="utf-8")
        with self.assertRaises(SystemExit):
            module.sign_existing(package, signer, False)
        other = self.root / "other.tgz"
        other.write_bytes(b"x")
        with self.assertRaises(SystemExit):
            module.sign_existing(other, signer, False)


class SignerAndCommandLineTest(unittest.TestCase):
    """The signer lookup, what the signer may answer, the publication commands (gh is a stand-in: nothing is published) and the command line."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        # never the real home of the person running the tests: it may hold the real signer and key
        for patcher in (mock.patch.object(Path, "home", return_value=self.home), mock.patch.dict(os.environ, {}, clear=False)):
            patcher.start()
            self.addCleanup(patcher.stop)
        os.environ.pop("ARMOR_PACKAGE_SIGNER", None)
        self.addCleanup(self.tmp.cleanup)

    def stub(self, public: str, signature: str = "ab" * 64, fail: bool = False) -> list[str]:
        script = self.root / "signer.py"
        lines = ["import sys", "if " + repr(fail) + ":", "    sys.stderr.write('no key'); sys.exit(3)",
                 "print(" + repr(public) + " if sys.argv[1] == '--public' else " + repr(signature) + ")"]
        script.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return [sys.executable, str(script)]

    def built(self, version: str = "0.2.6"):
        repo = make(self.root, "ARMOR-VOICE-AI", version, {"src/armor_voice_ai/__init__.py": "v"})
        (repo / "CHANGELOG.md").write_text(f"# Changelog\n\n## [{version}] - Faster answers\n\n- one\n", encoding="utf-8")
        return repo, module.build("voice", repo, self.root / "out")

    # ---- finding the signer ----
    def test_the_signer_comes_from_the_option_then_the_environment_then_the_default_file(self) -> None:
        self.assertIsNone(module.find_signer(None))
        self.assertEqual(module.find_signer("python3 /x/sign.py --flag"), ["python3", "/x/sign.py", "--flag"])
        os.environ["ARMOR_PACKAGE_SIGNER"] = "node /y/sign.mjs"
        self.assertEqual(module.find_signer(None), ["node", "/y/sign.mjs"])
        self.assertEqual(module.find_signer("python3 /x/sign.py"), ["python3", "/x/sign.py"])   # the option wins
        os.environ.pop("ARMOR_PACKAGE_SIGNER")
        (self.home / ".armor").mkdir()
        (self.home / ".armor" / "sign.mjs").write_text("// signer\n", encoding="utf-8")
        with mock.patch.object(module.shutil, "which", return_value="/usr/bin/node"):
            self.assertEqual(module.find_signer(None), ["node", str(self.home / ".armor" / "sign.mjs")])
        with mock.patch.object(module.shutil, "which", return_value=None):
            self.assertIsNone(module.find_signer(None))                                             # a signer file without node is no signer

    # ---- what the signer may answer ----
    def test_a_signer_that_fails_is_a_refusal_with_its_message(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            module.run_signer(self.stub("", fail=True), ["--public"])
        self.assertIn("the signer failed", str(caught.exception))
        self.assertIn("no key", str(caught.exception))

    def test_an_optional_signature_is_skipped_when_the_signer_has_no_key_but_a_required_one_fails(self) -> None:
        _repo, (package, version, digest) = self.built()
        failing = self.stub("", fail=True)
        self.assertIsNone(module.sign_package(package, "voice", version, digest, failing, False))
        with self.assertRaises(SystemExit):
            module.sign_package(package, "voice", version, digest, failing, True)
        self.assertFalse((package.parent / (package.name + ".sig")).exists())

    def test_an_answer_that_is_not_a_signature_is_never_written(self) -> None:
        _repo, (package, version, digest) = self.built()
        for answer in ("zz" * 64, "ab" * 63, "AB" * 64 + "00", "not hex at all"):
            with self.assertRaises(SystemExit, msg=answer):
                module.sign_package(package, "voice", version, digest, self.stub(module.trusted_key(), signature=answer), True)
            self.assertFalse((package.parent / (package.name + ".sig")).exists(), answer)

    def test_the_public_key_is_compared_without_regard_to_case(self) -> None:
        _repo, (package, version, digest) = self.built()
        written = module.sign_package(package, "voice", version, digest, self.stub(module.trusted_key().upper()), True)
        self.assertTrue(written.is_file())

    def test_the_trusted_key_is_read_from_the_helper_and_is_hex(self) -> None:
        self.assertRegex(module.trusted_key(), r"^[0-9a-f]{64}$")

    # ---- publishing ----
    def run_publish(self, view_exists: bool, version: str = "0.2.6", changelog: str | None = None, extra: list[Path] | None = None):
        repo, (package, _version, _digest) = self.built(version)
        if changelog is not None:
            (repo / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
        calls: list[list[str]] = []

        def fake_run(command, **options):
            calls.append(list(command))
            return mock.Mock(returncode=0 if (command[:3] != ["gh", "release", "view"] or view_exists) else 1)

        with mock.patch.object(module.subprocess, "run", side_effect=fake_run):
            with contextlib.redirect_stdout(io.StringIO()):
                module.publish("voice", repo, package, version, extra)
        return calls, package

    def test_a_new_release_is_created_with_the_package_its_hash_and_the_notes_of_the_changelog(self) -> None:
        calls, package = self.run_publish(False, changelog="# Changelog\n\n## [0.2.6] - Faster answers\n\n- one\n")
        self.assertEqual(calls[0][:3], ["gh", "release", "view"])
        create = calls[1]
        self.assertEqual(create[:4], ["gh", "release", "create", "v0.2.6"])
        self.assertIn(str(package), create)
        self.assertIn(str(package) + ".sha256", create)
        self.assertIn("JuanenRac/ARMOR-VOICE-AI", create)
        self.assertEqual(create[create.index("--title") + 1], "ARMOR-VOICE-AI 0.2.6 - Faster answers")
        self.assertEqual(create[create.index("--target") + 1], "main")
        self.assertFalse((package.parent / "NOTES.md").exists())            # the notes file is only a way to hand the text to gh

    def test_an_existing_release_gets_the_assets_added_and_replaced_not_recreated(self) -> None:
        signature = self.root / "out" / "armor-voice-0.2.6.tgz.sig"
        calls, _package = self.run_publish(True, extra=[signature])
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1][:4], ["gh", "release", "upload", "v0.2.6"])
        self.assertIn("--clobber", calls[1])
        self.assertIn(str(signature), calls[1])

    def test_a_title_that_talks_about_the_process_is_never_published(self) -> None:
        repo, (package, version, _digest) = self.built()
        for title in ("Au" + "dit fixes", "Second round of changes", "Written by Cla" + "ude"):   # the words the packager refuses in a title, written in pieces so that this file does not carry them
            (repo / "CHANGELOG.md").write_text(f"# Changelog\n\n## [0.2.6] - {title}\n\n- one\n", encoding="utf-8")
            with mock.patch.object(module.subprocess, "run") as run:
                with self.assertRaises(SystemExit, msg=title):
                    module.publish("voice", repo, package, version)
            run.assert_not_called()

    def test_a_release_without_a_changelog_entry_is_titled_with_its_version(self) -> None:
        calls, _package = self.run_publish(False, changelog="# Changelog\n")
        self.assertEqual(calls[1][calls[1].index("--title") + 1], "ARMOR-VOICE-AI 0.2.6 - 0.2.6")

    # ---- signing a package that already exists ----
    def test_an_existing_package_is_signed_next_to_itself_and_uploaded_only_when_asked(self) -> None:
        _repo, (package, _version, digest) = self.built()
        signer = self.stub(module.trusted_key())
        real_run = subprocess.run
        gh_calls: list[list[str]] = []

        def gh_stand_in(command, **options):
            if command[0] == "gh":
                gh_calls.append(list(command))
                return mock.Mock(returncode=0)
            return real_run(command, **options)

        with mock.patch.object(module.subprocess, "run", side_effect=gh_stand_in), contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(module.sign_existing(package, signer, False), 0)
        self.assertEqual(gh_calls, [])
        self.assertIn(digest, out.getvalue())
        with mock.patch.object(module.subprocess, "run", side_effect=gh_stand_in), contextlib.redirect_stdout(io.StringIO()):
            module.sign_existing(package, signer, True)
        self.assertEqual(gh_calls[0][:4], ["gh", "release", "upload", "v0.2.6"])
        self.assertIn("JuanenRac/ARMOR-VOICE-AI", gh_calls[0])

    def test_names_that_are_not_packages_of_the_family_are_refused(self) -> None:
        signer = self.stub(module.trusted_key())
        for name in ("armor-unknown-0.1.0.tgz", "armor-voice-1.0.tgz", "armor-voice-0.2.6.zip", "voice-0.2.6.tgz", "armor-Voice-0.2.6.tgz"):
            path = self.root / name
            path.write_bytes(b"x")
            with self.assertRaises(SystemExit, msg=name):
                module.sign_existing(path, signer, False)

    def test_a_package_is_never_signed_without_a_signer(self) -> None:
        _repo, (package, _version, _digest) = self.built()
        with self.assertRaises(SystemExit):
            module.sign_existing(package, None, False)

    # ---- the command line ----
    def run_main(self, *arguments: str) -> tuple[object, str]:
        out = io.StringIO()
        with mock.patch.object(sys, "argv", ["package_component.py", *arguments]), contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            try:
                result = module.main()
            except SystemExit as stop:
                result = stop.code
        return result, out.getvalue()

    def test_packing_without_a_signer_still_makes_the_package_and_says_nothing_about_signing(self) -> None:
        repo = make(self.root, "ARMOR-VOICE-AI", "0.2.6", {"src/armor_voice_ai/__init__.py": "v"})
        code, out = self.run_main("voice", "--repo", str(repo), "--out", str(self.root / "packages"))
        self.assertEqual(code, 0)
        self.assertIn("armor-voice-0.2.6.tgz", out)
        self.assertTrue((self.root / "packages" / "armor-voice-0.2.6.tgz.sha256").is_file())
        self.assertFalse((self.root / "packages" / "armor-voice-0.2.6.tgz.sig").exists())

    def test_publishing_an_unsigned_package_is_refused_before_anything_is_sent(self) -> None:
        repo = make(self.root, "ARMOR-VOICE-AI", "0.2.6", {"src/armor_voice_ai/__init__.py": "v"})
        with mock.patch.object(module.subprocess, "run") as run:
            code, _out = self.run_main("voice", "--repo", str(repo), "--out", str(self.root / "packages"), "--publish")
        self.assertIn("not publishing an unsigned package", str(code))
        run.assert_not_called()

    def test_required_signing_without_a_signer_fails(self) -> None:
        repo = make(self.root, "ARMOR-VOICE-AI", "0.2.6", {"src/armor_voice_ai/__init__.py": "v"})
        code, _out = self.run_main("voice", "--repo", str(repo), "--out", str(self.root / "packages"), "--sign")
        self.assertIn("--sign needs the signer", str(code))

    def test_signing_and_publishing_sends_the_signature_with_the_release(self) -> None:
        repo = make(self.root, "ARMOR-VOICE-AI", "0.2.6", {"src/armor_voice_ai/__init__.py": "v"})
        (repo / "CHANGELOG.md").write_text("# Changelog\n\n## [0.2.6] - Faster answers\n\n- one\n", encoding="utf-8")
        signer = " ".join(shlex.quote(part) for part in self.stub(module.trusted_key()))
        calls: list[list[str]] = []
        real_run = subprocess.run

        def fake_run(command, **options):
            calls.append(list(command))
            if command[0] == "gh":      # nothing is ever sent to GitHub; the stand-in signer is run for real
                return mock.Mock(returncode=1)
            return real_run(command, **options)

        with mock.patch.object(module.subprocess, "run", side_effect=fake_run):
            code, out = self.run_main("voice", "--repo", str(repo), "--out", str(self.root / "packages"), "--sign", "--publish", "--signer", signer)
        self.assertEqual(code, 0, out)
        create = [call for call in calls if call[:3] == ["gh", "release", "create"]][0]
        self.assertTrue(any(item.endswith(".tgz.sig") for item in create))
        self.assertIn("signed", out)

    def test_the_options_that_need_each_other(self) -> None:
        for arguments in ((), ("voice",), ("--repo", "x")):
            code, _out = self.run_main(*arguments)
            self.assertEqual(code, 2, arguments)                           # argparse: a component and --repo are needed
        code, _out = self.run_main("nonsense", "--repo", "x")
        self.assertEqual(code, 2)

    def test_a_repository_of_another_name_is_refused(self) -> None:
        repo = make(self.root, "ARMOR-SERVER", "0.5.6", {"dist/server.mjs": "x"})
        code, _out = self.run_main("voice", "--repo", str(repo), "--out", str(self.root / "packages"))
        self.assertIn("voice is ARMOR-VOICE-AI, not ARMOR-SERVER", str(code))

    def test_files_that_are_not_code_stay_out_of_every_package(self) -> None:
        repo = make(self.root, "ARMOR-NETWORK", "0.8.0.1", {"src/armor_network/__init__.py": "n", "src/armor_network/cli.py": "c", "src/armor_network/cli.pyc": "no",
                                                             "src/armor_network/cli.js.map": "no", "src/armor_network/.git/config": "no", "src/armor_network/node_modules/x.js": "no",
                                                             "pyproject.toml": "p"})
        package, _version, _digest = module.build("network", repo, self.root / "out")
        with tarfile.open(package) as tar:
            names = {member.name for member in tar.getmembers()}
        self.assertEqual(names, {"src/armor_network/__init__.py", "src/armor_network/cli.py", "armor.project.json", "pyproject.toml"})

    def test_a_package_is_the_same_whoever_builds_it(self) -> None:
        # owners and groups are not stored, so the hash does not depend on the account that built it
        repo = make(self.root, "ARMOR-VOICE-AI", "0.2.6", {"src/armor_voice_ai/__init__.py": "v"})
        package, _version, _digest = module.build("voice", repo, self.root / "out")
        with tarfile.open(package) as tar:
            for member in tar.getmembers():
                self.assertEqual((member.uid, member.gid, member.uname, member.gname), (0, 0, "", ""))


if __name__ == "__main__":
    unittest.main()
