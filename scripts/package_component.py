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
#
# SIGNING. The helper of the machine installs nothing without a signature by the key of the releases (the one the firmware of the nodes trusts): armor-<component>-<version>.tgz.sig2 holds
# the Ed25519 signature of the manifest `armor-fw/1|<component>|package|<version>|<sha256>` (the same manifest the firmware images use, with `package` where the board goes), and
# armor-<component>-<version>.tgz.sig the one of the older text `armor-pkg/1|<component>|<version>|<sha256>`, which a helper that has not been updated still checks. Both are written
# and published. The key is never read here: the signer (default ~/.armor/sign.mjs, or --signer / ARMOR_PACKAGE_SIGNER) reads it from ARMOR_FIRMWARE_KEY
# or ~/.armor/firmware_ed25519.pem. When the signer and a key are there the .sig is written; --sign makes that mandatory (it fails without them). A signature made with a key
# other than the one the helper trusts is never written.
#
#   python package_component.py server --repo ../../ARMOR-SERVER --sign --publish
#   python package_component.py --sign-existing armor-server-0.5.7.tgz --upload       # sign a package that is already published (downloaded next to it) and add the .sig to its release
#
# WHERE THE PROGRAM IS BUILT. Nothing is compiled on the machine of the maintainer: the build is the workflow package-build.yml of the repository (GitHub Actions), and
# --from-actions FOLDER packs only from the artifact of that run once it is downloaded and verified (the folder holds armor-<component>-<version>.tgz and its SHA256SUMS; the
# package is checked against the sums, copied to --out with its .sha256 and then signed and published like any other). Packing from a local dist still works, with a note on how it
# gets built: with ALLOW_LOCAL_BUILD=1 the stale-build refusals say to run npm run build; without it they say to launch the workflow.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D)
# GPL-3.0-or-later - see LICENSE
# =============================================================================
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
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
                                  ("scripts/mqtt_identity.sh", "scripts/mqtt_identity.sh"), ("scripts/armor_server.acl", "scripts/armor_server.acl"), ("scripts/backup_data.sh", "scripts/backup_data.sh"),
                                  ("scripts/armor_wireguard.sh", "scripts/armor_wireguard.sh"), ("scripts/armor_ddns.sh", "scripts/armor_ddns.sh"),
                                  ("scripts/armor_mqtt_tls.sh", "scripts/armor_mqtt_tls.sh")], ["scripts/armor_maintenance_agent.py"]),
}


def trusted_key() -> str:
    """The public key the helper of the machine trusts (read from the helper itself, so the two cannot differ)."""
    text = (Path(__file__).resolve().parent / "armor_maintenance_agent.py").read_text(encoding="utf-8")
    match = re.search(r'^PACKAGE_PUBLIC_KEY = "([0-9a-f]{64})"', text, re.M)
    if not match:
        raise SystemExit("the helper does not say which key it trusts")
    return match.group(1)


def find_signer(command: str | None) -> list[str] | None:
    """The command that signs (as a list), or None when there is none: --signer, ARMOR_PACKAGE_SIGNER, or ~/.armor/sign.mjs."""
    text = command or os.environ.get("ARMOR_PACKAGE_SIGNER")
    if text:
        return shlex.split(text)
    default = Path.home() / ".armor" / "sign.mjs"
    return ["node", str(default)] if default.is_file() and shutil.which("node") else None


def run_signer(signer: list[str], arguments: list[str]) -> str:
    result = subprocess.run([*signer, *arguments], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise SystemExit("the signer failed: " + (result.stderr.strip() or result.stdout.strip())[:300])
    return result.stdout.strip()


def manifest_text(component: str, version: str, digest: str) -> str:
    """The manifest a package signature (.sig2) covers: the one of the firmware images, with `package` in the place of the board."""
    return f"armor-fw/1|{component}|package|{version}|{digest}"


def signature_files(package: Path) -> list[Path]:
    """The signature files that exist next to a package: the manifest one (.sig2) and the older one (.sig)."""
    return [item for item in (package.parent / (package.name + ".sig2"), package.parent / (package.name + ".sig")) if item.is_file()]


def sign_package(package: Path, component: str, version: str, digest: str, signer: list[str] | None, required: bool) -> Path | None:
    """Writes <package>.sig2 (the manifest) and <package>.sig; returns the second. Without a signer and a key: None, or a failure when `required`."""
    if signer is None:
        if required:
            raise SystemExit("--sign needs the signer (~/.armor/sign.mjs, --signer or ARMOR_PACKAGE_SIGNER) and the key (ARMOR_FIRMWARE_KEY or ~/.armor/firmware_ed25519.pem)")
        return None
    try:
        public = run_signer(signer, ["--public"]).lower()
    except SystemExit:
        if required:
            raise
        return None
    if public != trusted_key():
        raise SystemExit("the key that would sign is not the one the helper of the machine trusts: it would refuse the package")
    manifest = run_signer(signer, ["--message", manifest_text(component, version, digest)]).lower()
    signature = run_signer(signer, ["--message", f"armor-pkg/1|{component}|{version}|{digest}"]).lower()
    if not re.fullmatch(r"[0-9a-f]{128}", signature) or not re.fullmatch(r"[0-9a-f]{128}", manifest):
        raise SystemExit("the signer did not give a signature")
    (package.parent / (package.name + ".sig2")).write_text(manifest + "\n", encoding="ascii", newline="\n")
    target = package.parent / (package.name + ".sig")
    target.write_text(signature + "\n", encoding="ascii", newline="\n")
    return target


def version_of(repo: Path) -> str:
    manifest = json.loads((repo / "armor.project.json").read_text(encoding="utf-8"))
    version = str(manifest["version"])
    if not re.fullmatch(r"\d+\.\d+\.\d+(\.\d+)?", version):
        raise SystemExit(f"{repo.name}: the version {version!r} is not one of the family's")
    return version


# What a built program is made from, by component: if any of it is newer than what was built, the build is stale (the package would carry the OLD program under the NEW version).
SOURCES = {"server": ["src", "tsconfig.json"], "studio": ["src", "index.html", "public", "vite.config.ts"]}
BUILT = {"server": ["dist/server.mjs", "dist/server_solar.mjs"], "studio": ["dist/index.html", "dist/version.json"]}
STALE_TOLERANCE_SECONDS = 2.0


def rebuild_hint() -> str:
    """How a stale or missing build gets rebuilt: on this machine only when the owner allowed local builds, otherwise in GitHub Actions."""
    if os.environ.get("ALLOW_LOCAL_BUILD", "").strip() == "1":
        return "run `npm run build`"
    return "launch package-build.yml in GitHub Actions and pack its artifact with --from-actions"


def newest_mtime(root: Path, names: list[str]) -> float:
    newest = 0.0
    for name in names:
        path = root / name
        if path.is_file():
            newest = max(newest, path.stat().st_mtime)
        elif path.is_dir():
            newest = max([newest, *(item.stat().st_mtime for item in files_under(path))])
    return newest


def check_built_is_current(component: str, repo: Path, version: str) -> None:
    """Refuses to pack a build that is not the current version of the code: the version it says, and the age of what it was built from."""
    if component not in SOURCES:
        return
    problems: list[str] = []
    package_json = repo / "package.json"
    if not package_json.is_file():
        problems.append("package.json is missing")
    else:
        found = str(json.loads(package_json.read_text(encoding="utf-8")).get("version"))
        if found != version:
            problems.append(f"package.json says {found} and the manifest {version}")
    if component == "studio":
        built = str(json.loads((repo / "dist" / "version.json").read_text(encoding="utf-8")).get("version"))
        if built != version:
            problems.append(f"dist/version.json says {built} and the manifest {version}: dist is stale, {rebuild_hint()}")
    built_at = min((repo / name).stat().st_mtime for name in BUILT[component] if (repo / name).is_file())
    source_at = newest_mtime(repo, SOURCES[component])
    if source_at > built_at + STALE_TOLERANCE_SECONDS:
        problems.append("the build is older than the source it was built from (dist is stale): {rebuild_hint()}")
    if problems:
        raise SystemExit(f"{repo.name} is not ready to pack: " + "; ".join(problems))


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
        raise SystemExit(f"{name} is not ready to pack ({rebuild_hint()}): missing {', '.join(missing)}")
    version = version_of(repo)
    check_built_is_current(component, repo, version)
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


def existing_digests(view_output: str) -> dict[str, str]:
    """The sha256 of every asset a release already holds, by name (an asset the listing gives no digest for maps to an empty string)."""
    try:
        listed = json.loads(view_output or "{}").get("assets", [])
    except (ValueError, AttributeError):
        raise SystemExit("could not read the assets of the existing release: refusing to change it") from None
    return {str(item.get("name", "")): str(item.get("digest", "")).removeprefix("sha256:").lower() for item in listed if isinstance(item, dict)}


def new_assets(assets: list[str], held: dict[str, str]) -> list[str]:
    """What still has to be uploaded to a release that exists: an asset it already holds with the same hash is skipped, one with another hash (or no known hash) is refused, because a
    published version never changes under the same number (the signature, the hash file and the agent's cache all depend on it)."""
    pending: list[str] = []
    for asset in assets:
        name = Path(asset).name
        if name not in held:
            pending.append(asset)
            continue
        if not held[name] or held[name] != hashlib.sha256(Path(asset).read_bytes()).hexdigest():
            raise SystemExit(f"{name} is already published under this version with other content: raise the version instead of replacing it")
    return pending


def publish(component: str, repo: Path, package: Path, version: str, extra: list[Path] | None = None) -> None:
    name = LAYOUT[component][0]
    title, notes = changelog_section(repo, version)
    if re.search(r"audit|round|claude", title, re.I):
        raise SystemExit(f"the title of the release {title!r} must describe the change, not the process")
    notes_file = package.parent / "NOTES.md"
    notes_file.write_text((notes or title) + "\n", encoding="utf-8")
    repo_name = f"{OWNER}/{name}"
    assets = [str(package), str(package) + ".sha256", *[str(item) for item in (extra or [])]]
    view = subprocess.run(["gh", "release", "view", f"v{version}", "-R", repo_name, "--json", "assets"], capture_output=True, text=True, check=False)
    if view.returncode == 0:
        to_upload = new_assets(assets, existing_digests(view.stdout))
        if to_upload:
            subprocess.run(["gh", "release", "upload", f"v{version}", *to_upload, "-R", repo_name], check=True)
    else:
        subprocess.run(["gh", "release", "create", f"v{version}", *assets, "-R", repo_name, "--title", f"{name} {version} - {title}", "--notes-file", str(notes_file), "--target", "main"], check=True)
    notes_file.unlink(missing_ok=True)
    print(f"published {name} v{version}")


def from_actions(folder: Path, out: Path) -> tuple[Path, str, str, str]:
    """Packs from the artifact of a run of package-build.yml that was downloaded and verified: nothing is built here and no dist is looked at.

    The folder must hold exactly one armor-<component>-<version>.tgz and the SHA256SUMS of the artifact; the package must be the one the sums list, and the build manifest,
    when it is there, must name the same version and say the package is unsigned. Returns the package copied into ``out`` (with its .sha256), the version, the hash and the component."""
    packages = sorted(folder.glob("armor-*.tgz"))
    if len(packages) != 1:
        raise SystemExit(f"{folder} must hold exactly one armor-<component>-<version>.tgz (the artifact of package-build.yml), found {len(packages)}")
    source = packages[0]
    match = re.fullmatch(r"armor-([a-z]+)-(\d+\.\d+\.\d+(?:\.\d+)?)\.tgz", source.name)
    if not match or match.group(1) not in LAYOUT:
        raise SystemExit(f"{source.name} is not a package named armor-<component>-<version>.tgz")
    component, version = match.groups()
    sums = folder / "SHA256SUMS"
    if not sums.is_file():
        raise SystemExit(f"{folder} has no SHA256SUMS: it is not a verified artifact (download it with armor_fetch_and_sign.py, which checks it)")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    listed = {parts[1].lstrip("*"): parts[0].lower() for parts in (line.split() for line in sums.read_text(encoding="utf-8").splitlines()) if len(parts) == 2}
    if listed.get(source.name) != digest:
        raise SystemExit(f"{source.name} is not the package that SHA256SUMS lists (hash {digest})")
    manifest = folder / "build-manifest.json"
    if manifest.is_file():
        data = json.loads(manifest.read_text(encoding="utf-8"))
        if str(data.get("version", version)) != version or data.get("signed") is True:
            raise SystemExit("build-manifest.json does not describe this package (another version, or it says the package is already signed)")
    out.mkdir(parents=True, exist_ok=True)
    package = out / source.name
    shutil.copyfile(source, package)
    (out / (package.name + ".sha256")).write_text(f"{digest}  {package.name}\n", encoding="utf-8")
    return package, version, digest, component


def sign_existing(file: Path, signer: list[str] | None, upload: bool) -> int:
    match = re.fullmatch(r"armor-([a-z]+)-(\d+\.\d+\.\d+(?:\.\d+)?)\.tgz", file.name)
    if not match or match.group(1) not in LAYOUT:
        raise SystemExit(f"{file.name} is not a package named armor-<component>-<version>.tgz")
    component, version = match.groups()
    digest = hashlib.sha256(file.read_bytes()).hexdigest()
    sha_file = file.parent / (file.name + ".sha256")
    if sha_file.is_file() and not sha_file.read_text(encoding="utf-8").lower().startswith(digest):
        raise SystemExit("the .sha256 next to the package is not the hash of this file")
    signature = sign_package(file, component, version, digest, signer, True)
    print(f"{signature.name}  ({component} {version}, {digest})")            # type: ignore[union-attr]
    if upload:
        subprocess.run(["gh", "release", "upload", f"v{version}", *[str(item) for item in signature_files(file)], "--clobber", "-R", f"{OWNER}/{LAYOUT[component][0]}"], check=True)
        print(f"uploaded to {OWNER}/{LAYOUT[component][0]} v{version}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Pack a program of the A.R.M.O.R. family for the maintenance helper, sign it and publish it")
    parser.add_argument("component", nargs="?", choices=sorted(LAYOUT))
    parser.add_argument("--repo", help="the folder of the repository")
    parser.add_argument("--out", default="dist-packages", help="where the package is written")
    parser.add_argument("--publish", action="store_true", help="create the release on GitHub (or add the package to the one that exists)")
    parser.add_argument("--sign", action="store_true", help="the package MUST be signed: fail when there is no signer or key (without it, it is signed when they are there)")
    parser.add_argument("--signer", help="the command that signs (default: node ~/.armor/sign.mjs); it is given --public or --message <text>")
    parser.add_argument("--from-actions", metavar="FOLDER", help="pack from the downloaded and verified artifact of package-build.yml (nothing is built here): the folder with armor-<component>-<version>.tgz and SHA256SUMS")
    parser.add_argument("--sign-existing", metavar="PACKAGE", help="only sign a package that already exists (armor-<component>-<version>.tgz); its .sig is written next to it")
    parser.add_argument("--upload", action="store_true", help="with --sign-existing: add the .sig to the release of that version")
    arguments = parser.parse_args()
    signer = find_signer(arguments.signer)
    if arguments.sign_existing:
        return sign_existing(Path(arguments.sign_existing).resolve(), signer, arguments.upload)
    if arguments.from_actions:
        package, version, digest, component = from_actions(Path(arguments.from_actions).resolve(), Path(arguments.out).resolve())
        if arguments.component and arguments.component != component:
            raise SystemExit(f"the artifact is the {component} package, not {arguments.component}")
        arguments.component = component
        if arguments.publish and not arguments.repo:
            parser.error("--publish needs --repo (the CHANGELOG of the repository gives the notes)")
        repo = Path(arguments.repo).resolve() if arguments.repo else Path(".").resolve()
    else:
        if not arguments.component or not arguments.repo:
            parser.error("a component and --repo are needed")
        repo = Path(arguments.repo).resolve()
        package, version, digest = build(arguments.component, repo, Path(arguments.out).resolve())
    print(f"{package.name}  {digest}")
    signature = sign_package(package, arguments.component, version, digest, signer, arguments.sign)
    if signature:
        print(f"{signature.name}  signed")
    elif arguments.publish:
        raise SystemExit("not publishing an unsigned package: the helper of the machine would refuse it (give the signer and the key)")
    if arguments.publish:
        publish(arguments.component, repo, package, version, signature_files(package) if signature else None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
