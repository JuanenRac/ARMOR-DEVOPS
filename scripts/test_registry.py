#!/usr/bin/env python3
# ARMOR-DEVOPS - the programs this repository packages, installs and keeps up to date are the ones the registry of the family (ARMOR-COMMON/registry/repositories.json) says are deployable components.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REGISTRY = HERE.parents[1] / "ARMOR-COMMON" / "registry" / "repositories.json"


def constant(file: str, name: str):
    """The value of a module-level constant written as a literal, read without running the module (the agents need Unix sockets, which not every machine has)."""
    tree = ast.parse((HERE / file).read_text(encoding="utf-8"))
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        if any(isinstance(target, ast.Name) and target.id == name for target in targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{file} has no constant {name}")


@unittest.skipUnless(REGISTRY.is_file(), "ARMOR-COMMON is not next to this repository")
class RegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repositories = json.loads(REGISTRY.read_text(encoding="utf-8"))["repositories"]
        cls.components = {entry["component"]: entry["name"] for entry in cls.repositories if "component" in entry}

    def test_the_packager_builds_the_components_of_the_registry_from_their_repositories(self):
        layout = constant("package_component.py", "LAYOUT")
        self.assertEqual({key: repository for key, (repository, _files, _needed) in layout.items()}, self.components)

    def test_the_maintenance_agent_updates_the_components_of_the_registry_from_their_repositories(self):
        components = constant("armor_maintenance_agent.py", "COMPONENTS")
        self.assertEqual({key: str(item["repo"]) for key, item in components.items()}, self.components)
        self.assertEqual(sorted(constant("armor_maintenance_agent.py", "ORDER")), sorted(self.components))

    def test_every_repository_the_registry_marks_as_a_component_is_in_the_family(self):
        names = {entry["name"] for entry in self.repositories}
        self.assertTrue(set(self.components.values()) <= names)


if __name__ == "__main__":
    unittest.main()
