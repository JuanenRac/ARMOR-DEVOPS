#!/usr/bin/env python3
# ARMOR-DEVOPS - the files of this repository agree with each other: the scripts are well formed and executable, the data files parse, the eight READMEs list the same things, the
# documents exist in the eight languages, and the lists of components and ports match the registry of the family and the table of ports.
# No network and no Docker; the registry of the family is read from the sibling repository when it is there.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
REGISTRY = ROOT.parent / "ARMOR-COMMON" / "registry" / "repositories.json"
CODES = ("spa", "deu", "fra", "ita", "jpn", "por", "zho")
README_FILES = ["README.md"] + [f"README_{code}.md" for code in CODES]
BASH = shutil.which("bash")
if BASH and "system32" in BASH.lower():          # the launcher of the Windows subsystem for Linux cannot read these paths
    BASH = None
MANIFEST = json.loads((ROOT / "armor.project.json").read_text(encoding="utf-8"))
SHELL_SCRIPTS = sorted(SCRIPTS.glob("*.sh")) + sorted(ROOT.glob("*.sh"))
PYTHON_FILES = sorted(SCRIPTS.glob("*.py")) + sorted((ROOT / "tools").glob("*.py"))
README_TEXT = {name: (ROOT / name).read_text(encoding="utf-8") for name in README_FILES}


def tracked_modes() -> dict[str, str]:
    """The mode git records for each shell script (an executable script must be 100755 or it fails with 'Permission denied' in a clean checkout); empty without git or a repository."""
    git = shutil.which("git")
    if not git or not (ROOT / ".git").exists():
        return {}
    done = subprocess.run([git, "ls-files", "-s", "--", "*.sh"], cwd=ROOT, capture_output=True, text=True, check=False)
    return {line.split("\t", 1)[1]: line.split()[0] for line in done.stdout.splitlines() if "\t" in line}


class ShellScriptTests(unittest.TestCase):
    def test_there_are_scripts_to_check(self):
        self.assertGreater(len(SHELL_SCRIPTS), 25)

    def test_every_script_starts_with_a_bash_or_sh_shebang(self):
        for path in SHELL_SCRIPTS:
            first = path.read_text(encoding="utf-8").splitlines()[0]
            self.assertRegex(first, r"^#!/usr/bin/(env )?(bash|sh)$", path.name)

    def test_the_attributes_force_lf_for_shell_scripts_and_crlf_for_batch_files(self):
        attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
        for rule in ("*.sh text eol=lf", "*.bat text eol=crlf", "mosquitto/* text eol=lf", "caddy/* text eol=lf"):
            self.assertIn(rule, attributes.splitlines(), rule)

    @unittest.skipIf(os.name == "nt", "a Windows checkout turns the line endings into CRLF by design")
    def test_no_script_has_windows_line_endings(self):
        for path in SHELL_SCRIPTS:
            self.assertNotIn(b"\r", path.read_bytes(), path.name)

    def test_the_scripts_that_do_the_work_stop_at_the_first_error(self):
        for path in SCRIPTS.glob("*.sh"):
            if path.name.startswith("test_") or path.name in {"validate-compose.sh"}:
                continue
            text = path.read_text(encoding="utf-8")
            self.assertRegex(text, r"(?m)^set -[euo]+(o pipefail)?", path.name)

    def test_the_scripts_are_stored_with_the_executable_bit(self):
        modes = tracked_modes()
        if not modes:
            self.skipTest("not a git checkout")
        for name, mode in modes.items():
            self.assertEqual(mode, "100755", f"{name} is {mode}: run git update-index --chmod=+x")

    def test_no_script_pipes_a_download_into_a_shell(self):
        for path in SHELL_SCRIPTS:
            self.assertNotRegex(path.read_text(encoding="utf-8"), r"(curl|wget)[^\n|]*\|\s*(sudo\s+)?(ba)?sh\b", path.name)

    def test_no_script_deletes_the_root_or_a_variable_without_a_guard(self):
        for path in SHELL_SCRIPTS:
            text = path.read_text(encoding="utf-8")
            self.assertNotRegex(text, r"rm -rf\s+/(\s|$)", path.name)
            self.assertNotRegex(text, r'rm -rf\s+"?\$\{?[A-Za-z_]+\}?"?/?\s*$', path.name)

    def test_no_script_holds_a_literal_token_or_private_key(self):
        for path in SHELL_SCRIPTS + [p for p in PYTHON_FILES if p != Path(__file__).resolve()]:
            text = path.read_text(encoding="utf-8")
            self.assertNotRegex(text, r"BEGIN [A-Z ]*PRIVATE KEY-----\s*\n[A-Za-z0-9+/]{20}", path.name)
            self.assertNotRegex(text, r"\b(ghp_|github_pat_|xox[bp]-|sk-[A-Za-z0-9]{20})", path.name)

    @unittest.skipUnless(BASH, "needs a bash that reads these paths")
    def test_every_script_passes_the_syntax_check_of_bash(self):
        for path in SHELL_SCRIPTS:
            done = subprocess.run([BASH, "-n", path.as_posix()], capture_output=True, text=True, check=False)
            self.assertEqual(done.returncode, 0, f"{path.name}: {done.stderr}")

    def test_the_wrappers_at_the_root_hand_over_to_the_common_script(self):
        for name in ("build.sh", "run.sh", "test.sh", "build-test.sh"):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn("armor-project.sh", text, name)
            self.assertIn("ARMOR-COMMON", text, name)

    def test_the_batch_wrappers_exist_next_to_each_shell_wrapper(self):
        for name in ("build", "run", "test", "build-test"):
            self.assertTrue((ROOT / f"{name}.bat").is_file(), name)

    def test_every_test_script_is_runnable_by_the_runner_of_the_tests(self):
        names = {p.name for p in SCRIPTS.glob("test_*.sh")}
        self.assertTrue(names)
        for name in names:
            self.assertTrue(name.endswith(".sh"))
            self.assertNotIn(" ", name)


class PythonFileTests(unittest.TestCase):
    def test_every_python_file_parses(self):
        for path in PYTHON_FILES:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    @unittest.skipIf(os.name == "nt", "a Windows checkout turns the line endings into CRLF by design")
    def test_no_python_file_has_windows_line_endings(self):
        for path in PYTHON_FILES:
            self.assertNotIn(b"\r\n", path.read_bytes(), path.name)

    def test_every_script_that_has_a_main_guard_exits_through_systemexit_or_unittest(self):
        for path in SCRIPTS.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            if '__name__ == "__main__"' in text:
                body = text.split('__name__ == "__main__"', 1)[1]
                self.assertRegex(body, r"(sys\.exit|SystemExit|unittest\.main|main\(\))", path.name)

    def test_every_module_under_test_has_a_test_file(self):
        for module in ("armor_admin_agent", "armor_doctor", "armor_dynsec", "armor_lan_cert", "armor_maintenance_agent", "bench_live", "generate_node_roles", "package_component"):
            self.assertTrue(any(SCRIPTS.glob(f"test_*{module.replace('armor_', '').replace('_agent', '')}*.py")), module)

    def test_no_test_writes_inside_the_repository(self):
        for path in SCRIPTS.glob("test_*.py"):
            text = path.read_text(encoding="utf-8")
            self.assertNotRegex(text, r"open\(ROOT[^)]*['\"]w", path.name)


class DataFileTests(unittest.TestCase):
    JSON_FILES = [ROOT / "armor.project.json", SCRIPTS / "ports.json", SCRIPTS / "node_roles.json", SCRIPTS / "env_masking.json",
                  ROOT / "docs" / "architecture.json", ROOT / "docs" / "structure.json", ROOT / "docs" / "coverage_threshold.json"]

    def test_every_data_file_is_valid_json_in_utf8(self):
        for path in self.JSON_FILES:
            json.loads(path.read_text(encoding="utf-8"))

    def test_the_coverage_floor_is_a_percentage_pair_and_the_branches_are_below_the_lines(self):
        floor = json.loads((ROOT / "docs" / "coverage_threshold.json").read_text(encoding="utf-8"))
        self.assertTrue(0 < floor["branches"] <= floor["lines"] <= 100)

    def test_every_port_of_the_table_is_in_range_with_a_known_protocol_and_unique(self):
        ports = json.loads((SCRIPTS / "ports.json").read_text(encoding="utf-8"))["ports"]
        seen: dict[int, str] = {}
        for name, entry in ports.items():
            self.assertTrue(1 <= entry["port"] <= 65535, name)
            self.assertIn(entry["protocol"], {"http", "https", "mqtt", "mqtts", "udp", "tcp", "wireguard", "ssh"}, name)
            self.assertNotIn(entry["port"], seen, f"{name} repeats the port of {seen.get(entry['port'])}")
            seen[entry["port"]] = name
            self.assertTrue(entry["note"], name)

    def test_the_old_ports_listed_as_legacy_are_not_current_ports(self):
        ports = json.loads((SCRIPTS / "ports.json").read_text(encoding="utf-8"))["ports"]
        current = {entry["port"] for entry in ports.values()}
        for name, entry in ports.items():
            for old in entry.get("legacy", []):
                self.assertNotIn(old, current, name)

    def test_the_manifest_says_what_this_repository_is(self):
        self.assertEqual(MANIFEST["name"], "ARMOR-DEVOPS")
        self.assertEqual(MANIFEST["ecosystem"], "A.R.M.O.R.")
        self.assertEqual(MANIFEST["version"], MANIFEST["native_version"])
        self.assertRegex(MANIFEST["version"], r"^\d+\.\d+\.\d+(\.\d+)?$")
        self.assertIn(MANIFEST["maturity"], {"scaffolding", "functional", "established", "production"})

    def test_the_changelog_has_an_unreleased_section_and_the_current_version(self):
        text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn("## [Unreleased]", text)
        self.assertRegex(text, rf"(?m)^## \[{re.escape(MANIFEST['version'])}\]")

    def test_the_example_node_roles_file_is_a_mapping_of_names_to_lists_or_objects(self):
        roles = json.loads((SCRIPTS / "node_roles.json").read_text(encoding="utf-8"))
        self.assertIsInstance(roles, dict)
        self.assertTrue(roles)

    def test_the_masking_table_is_versioned_and_explains_itself(self):
        masking = json.loads((SCRIPTS / "env_masking.json").read_text(encoding="utf-8"))
        self.assertEqual(masking["version"], 1)
        self.assertGreater(len(masking["note"]), 40)

class ReadmeTests(unittest.TestCase):
    def test_the_eight_readmes_exist_and_are_not_empty(self):
        for name, text in README_TEXT.items():
            self.assertGreater(len(text), 2000, name)

    def test_the_eight_readmes_have_the_same_number_of_sections(self):
        counts = {name: len(re.findall(r"(?m)^## ", text)) for name, text in README_TEXT.items()}
        self.assertEqual(len(set(counts.values())), 1, counts)

    def test_the_eight_readmes_carry_the_version_of_the_manifest(self):
        for name, text in README_TEXT.items():
            self.assertIn(f"Version-{MANIFEST['version']}-", text, name)
            self.assertIn(f"`{MANIFEST['version']}`", text, name)

    def test_the_eight_readmes_link_the_same_set_of_family_repositories(self):
        sets = {name: set(re.findall(r"github\.com/JuanenRac/(ARMOR-[A-Z0-9-]+)\)", text)) for name, text in README_TEXT.items()}
        reference = sets["README.md"]
        self.assertGreater(len(reference), 10)
        for name, found in sets.items():
            self.assertEqual(found, reference, name)

    def test_the_family_list_has_no_repository_twice(self):
        listed = re.findall(r"(?m)^\* \*\*\[(ARMOR-[A-Z0-9-]+)\]", README_TEXT["README.md"])
        self.assertEqual(len(listed), len(set(listed)))

    def test_the_family_list_never_includes_this_repository(self):
        listed = re.findall(r"(?m)^\* \*\*\[(ARMOR-[A-Z0-9-]+)\]", README_TEXT["README.md"])
        self.assertNotIn("ARMOR-DEVOPS", listed)

    @unittest.skipUnless(REGISTRY.is_file(), "ARMOR-COMMON is not next to this repository")
    def test_every_repository_the_readme_lists_is_in_the_registry_of_the_family(self):
        registry = {entry["name"] for entry in json.loads(REGISTRY.read_text(encoding="utf-8"))["repositories"]}
        listed = re.findall(r"(?m)^\* \*\*\[(ARMOR-[A-Z0-9-]+)\]", README_TEXT["README.md"])
        for name in listed:
            self.assertIn(name, registry, name)

    @unittest.skipUnless(REGISTRY.is_file(), "ARMOR-COMMON is not next to this repository")
    def test_every_deployable_component_of_the_registry_is_named_in_the_readme(self):
        for entry in json.loads(REGISTRY.read_text(encoding="utf-8"))["repositories"]:
            if "component" in entry:
                self.assertIn(entry["name"], README_TEXT["README.md"], entry["name"])

    def test_every_script_the_english_readme_names_exists(self):
        for name in set(re.findall(r"`?(scripts/[A-Za-z0-9_.-]+\.(?:sh|py))`?", README_TEXT["README.md"])):
            self.assertTrue((ROOT / name).is_file(), name)

    def test_every_document_the_english_readme_links_exists(self):
        for target in set(re.findall(r"\]\((docs/[A-Za-z0-9_.-]+\.md)\)", README_TEXT["README.md"])):
            self.assertTrue((ROOT / target).is_file(), target)

    def test_the_readme_says_the_truth_about_what_is_not_proven(self):
        text = README_TEXT["README.md"]
        self.assertIn("Honesty check", text)
        self.assertIn("not", text.split("Honesty check", 1)[1][:1500])

    def test_the_status_table_uses_one_light_per_row_and_the_same_rows_in_every_language(self):
        rows = {name: re.findall(r"(?m)^\| [^|\n]+ \| ([\U0001F7E2\U0001F7E1\U0001F7E0\U0001F534⚪]) \|", text) for name, text in README_TEXT.items()}
        reference = rows["README.md"]
        self.assertTrue(reference)
        for name, lights in rows.items():
            self.assertEqual(lights, reference, name)

class DocumentTests(unittest.TestCase):
    TRANSLATED = ("AUTOMATIC_SECURITY_UPDATES", "HTTPS_PAIRING", "LAN_CERTIFICATE", "MQTT_TLS", "PUBLIC_ACCESS", "REMOTE_ACCESS", "SIGNED_PACKAGES")

    def test_each_translated_document_exists_in_the_eight_languages(self):
        for name in self.TRANSLATED:
            self.assertTrue((ROOT / "docs" / f"{name}.md").is_file(), name)
            for code in CODES:
                self.assertTrue((ROOT / "docs" / f"{name}_{code}.md").is_file(), f"{name}_{code}")

    def test_the_translations_have_the_same_number_of_headings_as_the_english_original(self):
        for name in self.TRANSLATED:
            original = len(re.findall(r"(?m)^#{1,3} ", (ROOT / "docs" / f"{name}.md").read_text(encoding="utf-8")))
            for code in CODES:
                text = (ROOT / "docs" / f"{name}_{code}.md").read_text(encoding="utf-8")
                self.assertEqual(len(re.findall(r"(?m)^#{1,3} ", text)), original, f"{name}_{code}")

    def test_the_translations_keep_every_command_of_the_original(self):
        for name in self.TRANSLATED:
            original = (ROOT / "docs" / f"{name}.md").read_text(encoding="utf-8")
            commands = {c for c in re.findall(r"`((?:scripts/|docker compose)[^`<>]+)`", original)}
            for code in CODES:
                text = (ROOT / "docs" / f"{name}_{code}.md").read_text(encoding="utf-8")
                for command in commands:
                    self.assertIn(command, text, f"{name}_{code}: {command}")

    def test_every_script_a_document_cites_exists(self):
        for path in (ROOT / "docs").glob("*.md"):
            for script in set(re.findall(r"scripts/([A-Za-z0-9_-]+\.(?:sh|py))", path.read_text(encoding="utf-8"))):
                self.assertTrue((SCRIPTS / script).is_file(), f"{path.name}: {script}")

    def test_the_structure_file_lists_only_files_that_exist(self):
        data = json.loads((ROOT / "docs" / "structure.json").read_text(encoding="utf-8"))
        for card in data["cards"]:
            base = ROOT / card["name"] if isinstance(card["name"], str) else ROOT
            for row in card.get("rows", []):
                for item in (row.get("tree_name") or row["name"]).split():
                    if "*" in item:
                        continue
                    found = (base / item).exists() or (ROOT / item).exists() or bool(list(ROOT.glob(item + "*")))
                    self.assertTrue(found, item)


    def test_every_description_of_the_structure_file_has_the_eight_languages(self):
        data = json.loads((ROOT / "docs" / "structure.json").read_text(encoding="utf-8"))
        languages = {"en", "es", "de", "fr", "it", "ja", "zh", "pt"}
        for card in data["cards"]:
            self.assertEqual(set(card["sub"]), languages, card["name"])
            for row in card.get("rows", []):
                self.assertEqual(set(row["desc"]), languages, row["name"])

    def test_the_templates_for_issues_and_pull_requests_exist(self):
        for name in (".github/PULL_REQUEST_TEMPLATE.md", ".github/ISSUE_TEMPLATE/bug-report.yml", ".github/ISSUE_TEMPLATE/config.yml"):
            self.assertTrue((ROOT / name).is_file(), name)

    def test_the_licence_is_the_gpl_and_the_readmes_say_so(self):
        self.assertIn("GNU GENERAL PUBLIC LICENSE", (ROOT / "LICENSE").read_text(encoding="utf-8"))
        for name, text in README_TEXT.items():
            self.assertIn("GPL-3.0", text, name)


class WorkflowTests(unittest.TestCase):
    WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))

    def test_there_are_workflows(self):
        self.assertGreaterEqual(len(self.WORKFLOWS), 8)

    def test_every_workflow_has_a_name_a_trigger_and_least_privilege_permissions(self):
        for path in self.WORKFLOWS:
            text = path.read_text(encoding="utf-8")
            self.assertRegex(text, r"(?m)^name: \S", path.name)
            self.assertRegex(text, r"(?m)^on:", path.name)
            self.assertRegex(text, r"(?m)^permissions:", path.name)
            self.assertNotRegex(text, r"(?m)^permissions:\s*write-all", path.name)

    def test_every_action_is_pinned_to_a_full_commit(self):
        for path in self.WORKFLOWS:
            for use in re.findall(r"(?m)^\s*(?:-\s+)?uses: (\S+)", path.read_text(encoding="utf-8")):
                if use.startswith("./"):
                    continue
                self.assertRegex(use, r"@[0-9a-f]{40}$", f"{path.name}: {use}")

    def test_no_workflow_checks_out_with_the_default_credentials_kept(self):
        for path in self.WORKFLOWS:
            text = path.read_text(encoding="utf-8")
            if "actions/checkout" in text:
                self.assertIn("persist-credentials: false", text, path.name)

    def test_the_coverage_workflow_reads_the_floor_file_and_measures_the_scripts(self):
        text = (ROOT / ".github" / "workflows" / "coverage-floor.yml").read_text(encoding="utf-8")
        self.assertIn("docs/coverage_threshold.json", text)
        self.assertIn("--source=scripts", text)
        self.assertIn("--branch", text)
        self.assertIn("unittest discover -s scripts", text)

    def test_the_workflows_do_not_print_secrets_into_the_log(self):
        for path in self.WORKFLOWS:
            text = path.read_text(encoding="utf-8")
            self.assertNotRegex(text, r"echo\s+\"?\$\{\{\s*secrets\.", path.name)


if __name__ == "__main__":
    unittest.main()
