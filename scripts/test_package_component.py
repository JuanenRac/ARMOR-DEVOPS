#!/usr/bin/env python3
# ARMOR-DEVOPS - tests of scripts/package_component.py: what goes into the package of each program, its hash and the refusal of a title that talks about the process.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

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
        repo = make(self.root, "ARMOR-SERVER", "0.5.6", {"dist/server.mjs": "x", "dist/server_solar.mjs": "y", "package.json": "{}", "package-lock.json": "{}", "src/app.ts": "no"})
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


if __name__ == "__main__":
    unittest.main()
