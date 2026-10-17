#!/usr/bin/env python3
# =============================================================================
# A.R.M.O.R. - ARMOR-DEVOPS/scripts/package_component.py
# Packs one program of the A.R.M.O.R. family the way the maintenance helper of the machine (armor_maintenance_agent.py) installs it, and, if asked, publishes it as the
# release of its repository on GitHub, with the hash next to it:
#
#   python package_component.py server  --repo ../../ARMOR-SERVER
#   python package_component.py studio  --repo ../../ARMOR-STUDIO --publish
#
# The package is armor-<component>-<version>.tgz and its hash is armor-<component>-<version>.tgz.sha256 (the helper looks for that name); the version is the one of the
# repository's armor.project.json. Standard library only; --publish needs the GitHub CLI (`gh`) signed in.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D)
# GPL-3.0-or-later - see LICENSE
# =============================================================================
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tarfile
from pathlib import Path

OWNER = "JuanenRac"
SKIP = {"__pycache__", ".pytest_cache", ".git", "node_modules"}

# component -> (repository name, what goes in: [(path in the repository, path in the package)], what must be there first)
LAYOUT: dict[str, tuple[str, list[tuple[str, str]], list[str]]] = {
    "server": ("ARMOR-SERVER", [("dist", "server/dist"), ("package.json", "server/package.json"), ("package-lock.json", "server/package-lock.json")], ["dist/server.mjs"]),
    "studio": ("ARMOR-STUDIO", [("dist", "studio/dist"), ("tools/serve.mjs", "studio/tools/serve.mjs")], ["dist/index.html", "dist/version.json"]),
    "network": ("ARMOR-NETWORK", [("src", "src"), ("armor.project.json", "armor.project.json"), ("pyproject.toml", "pyproject.toml")], ["src/armor_network/__init__.py"]),
    "ai": ("ARMOR-SERVER-AI", [("src/armor_server_ai", "src/armor_server_ai")], ["src/armor_server_ai/__init__.py"]),
    "voice": ("ARMOR-VOICE-AI", [("src/armor_voice_ai", "src/armor_voice_ai")], ["src/armor_voice_ai/__init__.py"]),
    "devops": ("ARMOR-DEVOPS", [("scripts/armor_admin_agent.py", "scripts/armor_admin_agent.py"), ("scripts/armor_maintenance_agent.py", "scripts/armor_maintenance_agent.py"),
                                  ("scripts/mqtt_identity.sh", "scripts/mqtt_identity.sh"), ("scripts/backup_data.sh", "scripts/backup_data.sh"),
                                  ("scripts/armor_wireguard.sh", "scripts/armor_wireguard.sh"), ("scripts/armor_ddns.sh", "scripts/armor_ddns.sh")], ["scripts/armor_maintenance_agent.py"]),
}


def version_of(repo: Path) -> str:
    manifest = json.loads((repo / "armor.project.json").read_text(encoding="utf-8"))
    version = str(manifest["version"])
    if not re.fullmatch(r"\d+\.\d+\.\d+(\.\d+)?", version):
        raise SystemExit(f"{repo.name}: the version {version!r} is not one of the family's")
    return version


def files_under(root: Path):
    for path in sorted(root.rglob("*")):
        if path.is_file() and not (set(path.relative_to(root).parts) & SKIP) and not path.name.endswith((".pyc", ".map")):
            yield path


def build(component: str, repo: Path, out: Path) -> tuple[Path, str, str]:
    name, parts, required = LAYOUT[component]
    if repo.name != name:
        raise SystemExit(f"{component} is {name}, not {repo.name}")
    missing = [item for item in required if not (repo / item).exists()]
    if missing:
        raise SystemExit(f"{name} is not ready to pack (build it first): missing {', '.join(missing)}")
    version = version_of(repo)
    out.mkdir(parents=True, exist_ok=True)
    package = out / f"armor-{component}-{version}.tgz"
    with tarfile.open(package, "w:gz") as tar:
        def add(path: Path, arcname: str) -> None:
            info = tar.gettarinfo(str(path), arcname)
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mtime = int(path.stat().st_mtime)
            with open(path, "rb") as handle:
                tar.addfile(info, handle)
        for source, target in parts:
            path = repo / source
            if path.is_dir():
                for item in files_under(path):
                    add(item, f"{target}/{item.relative_to(path).as_posix()}")
            elif path.is_file():
                add(path, target)
        if component == "devops":
            version_file = out / "VERSION"
            version_file.write_text(version + "\n", encoding="utf-8")
            add(version_file, "scripts/VERSION")
            version_file.unlink()
    digest = hashlib.sha256(package.read_bytes()).hexdigest()
    (out / (package.name + ".sha256")).write_text(f"{digest}  {package.name}\n", encoding="utf-8")
    return package, version, digest


def changelog_section(repo: Path, version: str) -> tuple[str, str]:
    text = (repo / "CHANGELOG.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    match = re.search(rf"## \[{re.escape(version)}\] - (.*?)\n\n(.*?)(?=\n## \[|\Z)", text, re.S)
    if not match:
        return version, ""
    return match.group(1).strip(), match.group(2).strip()


def publish(component: str, repo: Path, package: Path, version: str) -> None:
    name = LAYOUT[component][0]
    title, notes = changelog_section(repo, version)
    if re.search(r"audit|round|claude", title, re.I):
        raise SystemExit(f"the title of the release {title!r} must describe the change, not the process")
    notes_file = package.parent / "NOTES.md"
    notes_file.write_text((notes or title) + "\n", encoding="utf-8")
    repo_name = f"{OWNER}/{name}"
    assets = [str(package), str(package) + ".sha256"]
    exists = subprocess.run(["gh", "release", "view", f"v{version}", "-R", repo_name], capture_output=True, text=True, check=False).returncode == 0
    if exists:
        subprocess.run(["gh", "release", "upload", f"v{version}", *assets, "--clobber", "-R", repo_name], check=True)
    else:
        subprocess.run(["gh", "release", "create", f"v{version}", *assets, "-R", repo_name, "--title", f"{name} {version} - {title}", "--notes-file", str(notes_file), "--target", "main"], check=True)
    notes_file.unlink(missing_ok=True)
    print(f"published {name} v{version}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Pack a program of the A.R.M.O.R. family for the maintenance helper, and publish it")
    parser.add_argument("component", choices=sorted(LAYOUT))
    parser.add_argument("--repo", required=True, help="the folder of the repository")
    parser.add_argument("--out", default="dist-packages", help="where the package is written")
    parser.add_argument("--publish", action="store_true", help="create the release on GitHub (or add the package to the one that exists)")
    arguments = parser.parse_args()
    repo = Path(arguments.repo).resolve()
    package, version, digest = build(arguments.component, repo, Path(arguments.out).resolve())
    print(f"{package.name}  {digest}")
    if arguments.publish:
        publish(arguments.component, repo, package, version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
