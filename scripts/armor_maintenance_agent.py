#!/usr/bin/env python3
# =============================================================================
# A.R.M.O.R. - ARMOR-DEVOPS/scripts/armor_maintenance_agent.py
# The maintenance helper of the machine: it keeps the A.R.M.O.R. programs and the operating system up to date from GitHub, and gives an administrator a root console
# for the day something is wrong and there is no other way in.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D)
# GPL-3.0-or-later - see LICENSE
# =============================================================================
# Why it is apart from armor_admin_agent.py: that one has a closed list of what it can touch, no network and a read-only system, on purpose. Updating needs the
# network and write access to the programs and the system, and the console needs everything, so they live in their own program, with their own unit, socket and token:
#   * UPDATES   - what is installed (server, Studio, the Python services, the helper scripts) against the newest release of each repository on GitHub; an update downloads
#                 the release asset, checks its SHA-256 with the hash the release publishes, keeps a copy of what it replaces, puts the new one in, restarts the service,
#                 asks it whether it is well and, if it is not, puts the old one back. One at a time, with steps, a percentage and a log that can be followed.
#   * SYSTEM    - the operating system's own updates (apt): what can be upgraded, the upgrade with its progress, whether it needs a reboot, and the reboot.
#   * CONSOLE   - OFF unless ARMOR_MAINT_CONSOLE=1 is set on purpose in its environment file: one command at a time as root, with a time limit, its output kept for
#                 whoever asked, and nothing hidden - the server writes every command in the audit trail and asks an administrator for the password again before the first.
# It listens on a Unix socket that only the group `armor` can open, and also wants a token (ARMOR_MAINT_TOKEN). Standard library only.
#
#   armor_maintenance_agent.py --socket /run/armor-maint.sock        # as root, by the systemd unit armor-maintenance.service
from __future__ import annotations

import argparse
import hashlib
import hmac
import http.server
import json
import os
import re
import shutil
import signal
import socketserver
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

AGENT_VERSION = "0.1.1"
PREFIX = Path(os.environ.get("ARMOR_PREFIX", "/opt/armor"))
SYSTEMCTL = os.environ.get("ARMOR_SYSTEMCTL", "systemctl")
APT_GET = os.environ.get("ARMOR_APT_GET", "apt-get")
DPKG = os.environ.get("ARMOR_DPKG", "dpkg")
APT = os.environ.get("ARMOR_APT", "apt")
GITHUB_API = os.environ.get("ARMOR_GITHUB_API", "https://api.github.com").rstrip("/")
GITHUB_OWNER = os.environ.get("ARMOR_GITHUB_OWNER", "JuanenRac")
GITHUB_TOKEN = os.environ.get("ARMOR_GITHUB_TOKEN", "")
HEALTH_URL = os.environ.get("ARMOR_HEALTH_URL", "http://127.0.0.1:18080/healthz")
CONSOLE_ENABLED = os.environ.get("ARMOR_MAINT_CONSOLE", "") == "1"
DATA_DIR = Path(os.environ.get("ARMOR_MAINT_DATA", str(PREFIX / "data" / "maintenance")))
CACHE_SECONDS = 600
MAX_DOWNLOAD = 300 * 1024 * 1024
MAX_LOG_LINES = 2000
MAX_CONSOLE_BYTES = 256 * 1024
KEEP_OLD = 6

# id -> what it is. `kind` says how it is put in; `service` is restarted afterwards (None: nothing to restart).
COMPONENTS: dict[str, dict[str, object]] = {
    "server": {"repo": "ARMOR-SERVER", "kind": "release-dir", "part": "server", "service": "armor-server", "description": "The A.R.M.O.R. server: sensors, alarms, cameras, history"},
    "studio": {"repo": "ARMOR-STUDIO", "kind": "release-dir", "part": "studio", "service": "armor-studio", "description": "Studio, the console"},
    "network": {"repo": "ARMOR-NETWORK", "kind": "python", "target": "apps/ARMOR-NETWORK", "service": "armor-network", "description": "The network watcher"},
    "ai": {"repo": "ARMOR-SERVER-AI", "kind": "python-package", "target": "ai/armor_server_ai", "package": "armor_server_ai", "service": "armor-server-ai", "description": "The observation service"},
    "voice": {"repo": "ARMOR-VOICE-AI", "kind": "python-package", "target": "voice/armor_voice_ai", "package": "armor_voice_ai", "service": "armor-voice", "description": "The voice gateway"},
    "devops": {"repo": "ARMOR-DEVOPS", "kind": "scripts", "target": "bin", "service": "armor-admin", "description": "The helper scripts: the admin agent, the broker accounts and the backup"},
}
ORDER = ["server", "studio", "network", "ai", "voice", "devops"]


class Refused(Exception):
    def __init__(self, status: int, code: str) -> None:
        super().__init__(code)
        self.status, self.code = status, code


# ---- versions -----------------------------------------------------------------------------------------------------------------------------------

def version_key(version: str) -> tuple[int, ...]:
    """A version as numbers, four of them (a three-part version is the same with a zero at the end): 0.8.0 is 0.8.0.0."""
    numbers = [int(part) for part in re.findall(r"\d+", version)[:4]]
    return tuple(numbers + [0] * (4 - len(numbers)))


def clean_version(text: str) -> str:
    match = re.search(r"\d+\.\d+\.\d+(?:\.\d+)?", text)
    return match.group(0) if match else ""


def read_json(path: Path) -> dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def installed_version(component: str) -> str:
    info = COMPONENTS[component]
    kind = info["kind"]
    try:
        if kind == "release-dir":
            current = PREFIX / "current"
            if info["part"] == "server":
                return clean_version(str(read_json(current / "server" / "package.json").get("version", "")))
            return clean_version(str(read_json(current / "studio" / "dist" / "version.json").get("version", "")))
        if kind == "python":
            return clean_version(str(read_json(PREFIX / str(info["target"]) / "armor.project.json").get("version", "")))
        if kind == "python-package":
            text = (PREFIX / str(info["target"]) / "__init__.py").read_text(encoding="utf-8")
            match = re.search(r'__version__\s*=\s*"([^"]+)"', text)
            return clean_version(match.group(1)) if match else ""
        if kind == "scripts":
            return clean_version((PREFIX / str(info["target"]) / "VERSION").read_text(encoding="utf-8"))
    except OSError:
        return ""
    return ""


# ---- GitHub ---------------------------------------------------------------------------------------------------------------------------------------

_cache: dict[str, tuple[float, dict[str, object]]] = {}


def http_get(url: str, accept: str = "application/vnd.github+json", timeout: float = 20.0) -> bytes:
    request = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": "armor-maintenance", **({"Authorization": f"Bearer {GITHUB_TOKEN}"} if GITHUB_TOKEN else {})})
    with urllib.request.urlopen(request, timeout=timeout) as response:                      # noqa: S310 - the address is fixed to GitHub (or a test server)
        return response.read(2 * 1024 * 1024)


def latest_release(component: str, force: bool = False) -> dict[str, object]:
    """The newest release of a component's repository: its version, when it was published and the assets it carries (name -> address)."""
    repo = str(COMPONENTS[component]["repo"])
    cached = _cache.get(repo)
    if cached and not force and time.time() - cached[0] < CACHE_SECONDS:
        return cached[1]
    try:
        data = json.loads(http_get(f"{GITHUB_API}/repos/{GITHUB_OWNER}/{repo}/releases/latest").decode("utf-8"))
    except urllib.error.HTTPError as error:
        result: dict[str, object] = {"error": "no_release" if error.code == 404 else f"github_{error.code}"}
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        result = {"error": "github_unreachable"}
    else:
        assets = {str(asset.get("name")): str(asset.get("browser_download_url")) for asset in data.get("assets", []) if isinstance(asset, dict)}
        result = {"version": clean_version(str(data.get("tag_name", ""))), "tag": str(data.get("tag_name", "")), "published": str(data.get("published_at", "")), "assets": assets,
                  "notes": str(data.get("body", ""))[:6000]}
        if not result["version"]:
            result = {"error": "no_release"}
    _cache[repo] = (time.time(), result)
    return result


def component_state(component: str, force: bool = False) -> dict[str, object]:
    info = COMPONENTS[component]
    installed = installed_version(component)
    release = latest_release(component, force)
    latest = str(release.get("version", ""))
    if "error" in release:
        status = "unknown"
    elif not installed:
        status = "not_installed"
    elif version_key(latest) > version_key(installed):
        status = "update_available"
    elif version_key(latest) < version_key(installed):
        status = "ahead"
    else:
        status = "up_to_date"
    has_asset = f"armor-{component}-{latest}.tgz" in (release.get("assets") or {}) if latest else False   # type: ignore[operator]
    return {"id": component, "repo": info["repo"], "description": info["description"], "service": info["service"], "installed": installed, "latest": latest, "status": status,
            "published": release.get("published", ""), "error": release.get("error", ""), "installable": has_asset, "notes": release.get("notes", "")}


# ---- jobs -----------------------------------------------------------------------------------------------------------------------------------------

class Job:
    """A piece of maintenance work that runs in the background: its steps with a state each, a percentage and a log that a client follows by line number."""

    def __init__(self, kind: str, steps: list[tuple[str, str]], label: str = "") -> None:
        self.id = f"{int(time.time())}-{os.urandom(3).hex()}"
        self.kind, self.label = kind, label
        self.steps = [{"id": step_id, "label": text, "state": "waiting", "percent": 0} for step_id, text in steps]
        self.state = "running"
        self.percent = 0
        self.log: list[str] = []
        self.started = time.time()
        self.finished = 0.0
        self.error = ""
        self.result: dict[str, object] = {}
        self.lock = threading.Lock()

    def say(self, line: str) -> None:
        with self.lock:
            self.log.append(f"{time.strftime('%H:%M:%S')} {line}"[:600])
            if len(self.log) > MAX_LOG_LINES:
                del self.log[: len(self.log) - MAX_LOG_LINES]
                self.log.insert(0, "... (older lines left out)")

    def step(self, step_id: str, state: str, percent: int | None = None) -> None:
        with self.lock:
            for item in self.steps:
                if item["id"] == step_id:
                    item["state"] = state
                    if percent is not None:
                        item["percent"] = percent
                    elif state == "done":
                        item["percent"] = 100
            done = sum(100 if item["state"] in ("done", "skipped") else int(item["percent"]) if item["state"] == "running" else 0 for item in self.steps)
            self.percent = int(done / max(1, len(self.steps)))

    def finish(self, error: str = "") -> None:
        with self.lock:
            self.state = "failed" if error else "done"
            self.error = error
            self.finished = time.time()
            if not error:
                self.percent = 100

    def view(self, since: int = 0) -> dict[str, object]:
        with self.lock:
            return {"id": self.id, "kind": self.kind, "label": self.label, "state": self.state, "percent": self.percent, "steps": [dict(item) for item in self.steps], "error": self.error,
                    "started": self.started, "finished": self.finished, "log": self.log[since:], "log_total": len(self.log), "result": self.result}


JOBS: dict[str, Job] = {}
WORK = threading.Lock()                     # one change to the machine at a time


def remember(job: Job) -> None:
    JOBS[job.id] = job
    if len(JOBS) > 40:
        for key in sorted(JOBS, key=lambda item: JOBS[item].started)[: len(JOBS) - 40]:
            if JOBS[key].state != "running":
                JOBS.pop(key, None)


def history_path() -> Path:
    return DATA_DIR / "history.json"


def record_history(job: Job) -> None:
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        entries = json.loads(history_path().read_text(encoding="utf-8")) if history_path().exists() else []
        entries.append({"id": job.id, "kind": job.kind, "label": job.label, "state": job.state, "error": job.error, "started": job.started, "finished": job.finished, "result": job.result})
        history_path().write_text(json.dumps(entries[-200:]), encoding="utf-8")
    except (OSError, ValueError):
        pass


def history() -> list[dict[str, object]]:
    try:
        data = json.loads(history_path().read_text(encoding="utf-8"))
        return data[-60:][::-1] if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def clear_history() -> int:
    """Forget the list of the last operations (what the machine did stays as it is); returns how many were forgotten."""
    count = len(history())
    try:
        history_path().unlink(missing_ok=True)
    except OSError:
        raise Refused(500, "history_not_cleared")
    return count


# ---- downloading and unpacking ------------------------------------------------------------------------------------------------------------------

def download(job: Job, step: str, url: str, destination: Path) -> str:
    """Download to a file with the progress shown in the step; returns the SHA-256 of what came."""
    request = urllib.request.Request(url, headers={"User-Agent": "armor-maintenance", **({"Authorization": f"Bearer {GITHUB_TOKEN}"} if GITHUB_TOKEN and "api.github.com" in url else {})})
    digest = hashlib.sha256()
    with urllib.request.urlopen(request, timeout=30) as response, open(destination, "wb") as out:      # noqa: S310
        total = int(response.headers.get("Content-Length") or 0)
        got = 0
        last = 0.0
        while True:
            chunk = response.read(64 * 1024)
            if not chunk:
                break
            got += len(chunk)
            if got > MAX_DOWNLOAD:
                raise Refused(413, "download_too_large")
            digest.update(chunk)
            out.write(chunk)
            if time.time() - last > 0.25:
                last = time.time()
                job.step(step, "running", min(99, int(got * 100 / total)) if total else 50)
    job.say(f"downloaded {got // 1024} KiB")
    return digest.hexdigest()


def expected_hash(release: dict[str, object], asset: str) -> str:
    assets = release.get("assets") or {}
    url = assets.get(asset + ".sha256")                                       # type: ignore[union-attr]
    if not url:
        raise Refused(422, "no_checksum")
    text = http_get(str(url), accept="application/octet-stream").decode("utf-8", "replace")
    match = re.match(r"\s*([0-9a-fA-F]{64})", text)
    if not match:
        raise Refused(422, "no_checksum")
    return match.group(1).lower()


def safe_extract(archive: Path, destination: Path) -> None:
    """Unpack a tarball only if nothing in it can land outside the folder: no absolute names, no .., no links and no devices."""
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar.getmembers():
            name = member.name
            if name.startswith("/") or ".." in Path(name).parts or not (member.isfile() or member.isdir()):
                raise Refused(422, "unsafe_archive")
        tar.extractall(destination)                                           # noqa: S202 - every member was checked above


def fetch_asset(job: Job, component: str, release: dict[str, object], workdir: Path) -> Path:
    version = str(release["version"])
    asset = f"armor-{component}-{version}.tgz"
    assets = release.get("assets") or {}
    if asset not in assets:                                                   # type: ignore[operator]
        raise Refused(422, "no_asset")
    job.step("download", "running", 0)
    job.say(f"downloading {asset}")
    archive = workdir / asset
    digest = download(job, "download", str(assets[asset]), archive)           # type: ignore[index]
    job.step("download", "done")
    job.step("verify", "running", 0)
    wanted = expected_hash(release, asset)
    if digest != wanted:
        raise Refused(422, "checksum_mismatch")
    job.say(f"SHA-256 matches the one the release publishes ({digest[:12]}...)")
    job.step("verify", "done")
    staged = workdir / "staged"
    staged.mkdir()
    safe_extract(archive, staged)
    return staged


# ---- putting a component in ---------------------------------------------------------------------------------------------------------------------

def systemctl(*arguments: str, timeout: float = 90.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run([SYSTEMCTL, *arguments], capture_output=True, text=True, timeout=timeout, check=False)


def healthy(component: str, unit: str, wait: float = 40.0) -> bool:
    """Is the service well after the restart? The server answers /healthz; the others must stay active for a few seconds."""
    deadline = time.time() + wait
    time.sleep(2.0)
    while time.time() < deadline:
        if component == "server":
            try:
                if b'"ok":true' in http_get(HEALTH_URL, accept="application/json", timeout=3.0).replace(b" ", b""):
                    return True
            except (urllib.error.URLError, OSError, TimeoutError):
                pass
        else:
            active = systemctl("is-active", unit).stdout.strip()
            if active == "active":
                time.sleep(2.0)
                return systemctl("is-active", unit).stdout.strip() == "active"
        time.sleep(1.0)
    return False


def link_or_copy(source: str, destination: str) -> str:
    """A hard link when the files are on the same disk (a new release folder costs nothing), a copy when they are not."""
    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)
    return destination


def put_file(source: Path, destination: Path) -> None:
    """Copy a file over another one of the NEW release folder. Its files are hard links to the ones of the release it came from, so writing into them would change the old release too:
    the link is taken away first and the new file is made in its place."""
    destination.unlink(missing_ok=True)
    shutil.copy2(source, destination)


def own(path: Path, owner: str) -> None:
    subprocess.run(["chown", "-R", f"{owner}:{owner}", str(path)], capture_output=True, check=False)


def prune_old(folder: Path) -> None:
    try:
        entries = sorted((entry for entry in folder.iterdir() if entry.is_dir()), key=lambda entry: entry.name)   # the names are the times they were made
        for entry in entries[:-KEEP_OLD]:
            shutil.rmtree(entry, ignore_errors=True)
    except OSError:
        pass


def install_release_dir(job: Job, component: str, staged: Path, version: str) -> dict[str, object]:
    """Server or Studio: a new release folder is made from the current one with that one part replaced; `current` points to it once it is ready."""
    part = str(COMPONENTS[component]["part"])
    unit = str(COMPONENTS[component]["service"])
    current = (PREFIX / "current").resolve()
    stamp = time.strftime("%Y%m%d-%H%M%S")
    target = PREFIX / "releases" / stamp
    job.step("install", "running", 5)
    job.say(f"making the release folder {target.name} from {current.name}")
    shutil.copytree(current, target, symlinks=True, copy_function=link_or_copy)
    source = staged / part
    if not source.is_dir():
        raise Refused(422, "bad_archive")
    job.step("install", "running", 40)
    if part == "server":
        shutil.rmtree(target / "server" / "dist", ignore_errors=True)
        shutil.copytree(source / "dist", target / "server" / "dist")
        for name in ("package.json", "package-lock.json"):
            if (source / name).exists():
                put_file(source / name, target / "server" / name)
        old_lock = (current / "server" / "package-lock.json")
        if (source / "package-lock.json").exists() and old_lock.exists() and hashlib.sha256(old_lock.read_bytes()).digest() != hashlib.sha256((source / "package-lock.json").read_bytes()).digest():
            job.say("the dependencies changed: npm ci --omit=dev")
            done = subprocess.run(["npm", "ci", "--omit=dev"], cwd=target / "server", capture_output=True, text=True, timeout=900, check=False)
            if done.returncode != 0:
                raise Refused(500, "npm_failed")
    else:
        shutil.rmtree(target / "studio" / "dist", ignore_errors=True)
        shutil.copytree(source / "dist", target / "studio" / "dist")
        if (source / "tools" / "serve.mjs").exists():
            (target / "studio" / "tools").mkdir(parents=True, exist_ok=True)
            put_file(source / "tools" / "serve.mjs", target / "studio" / "tools" / "serve.mjs")
    own(target, "armor")
    job.step("install", "done")
    job.step("restart", "running", 10)
    previous = os.readlink(PREFIX / "current")
    job.say("switching `current` and restarting " + unit)
    link = PREFIX / "current.new"
    link.unlink(missing_ok=True)
    link.symlink_to(target)
    os.replace(link, PREFIX / "current")
    systemctl("restart", unit)
    job.step("restart", "done")
    job.step("check", "running", 20)
    if not healthy(component, unit):
        job.say("it does not answer: putting the previous release back")
        back = PREFIX / "current.new"
        back.unlink(missing_ok=True)
        back.symlink_to(previous)
        os.replace(back, PREFIX / "current")
        systemctl("restart", unit)
        raise Refused(500, "unhealthy_rolled_back")
    job.step("check", "done")
    prune_old(PREFIX / "releases")
    return {"previous": previous, "release": target.name}


def replace_tree(job: Job, component: str, staged: Path) -> dict[str, object]:
    """A Python service or the helper scripts: a copy of what is there is kept, the new files go in, the service is restarted and looked at."""
    info = COMPONENTS[component]
    unit = str(info["service"])
    kind = str(info["kind"])
    target = PREFIX / str(info["target"])
    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup = PREFIX / "releases-old" / f"maint-{component}-{stamp}"
    job.step("install", "running", 10)
    backup.mkdir(parents=True, exist_ok=True)
    if kind == "python-package":
        package = staged / "src" / str(info["package"])
        if not package.is_dir():
            raise Refused(422, "bad_archive")
        if target.exists():
            shutil.copytree(target, backup / target.name)
            shutil.rmtree(target)
        shutil.copytree(package, target)
    elif kind == "python":
        for name in ("src", "armor.project.json", "pyproject.toml"):
            source = staged / name
            if not source.exists():
                continue
            destination = target / name
            if destination.exists():
                (backup / name).parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(destination), str(backup / name))
            if source.is_dir():
                shutil.copytree(source, destination)
            else:
                shutil.copy2(source, destination)
        own(target, "armor")
    else:                                                                     # scripts
        scripts = staged / "scripts"
        if not scripts.is_dir():
            raise Refused(422, "bad_archive")
        for name in ("armor_admin_agent.py", "armor_maintenance_agent.py", "mqtt_identity.sh", "backup_data.sh", "VERSION"):
            source = scripts / name
            if not source.exists():
                continue
            destination = target / name
            if destination.exists():
                shutil.copy2(destination, backup / name)
            shutil.copy2(source, destination)
            destination.chmod(0o755 if name.endswith((".py", ".sh")) else 0o644)
    job.step("install", "done")
    job.step("restart", "running", 10)
    if component == "devops":
        job.say("the helper scripts are in; the services that run them restart in a moment")
        subprocess.run(["systemd-run", "--on-active=4", SYSTEMCTL, "restart", unit, "armor-maintenance"], capture_output=True, check=False)
        job.step("restart", "done")
        job.step("check", "skipped")
        return {"backup": backup.name}
    systemctl("restart", unit)
    job.step("restart", "done")
    job.step("check", "running", 20)
    if not healthy(component, unit, wait=25.0):
        job.say("the service is not well: putting what was there back")
        if kind == "python-package":
            shutil.rmtree(target, ignore_errors=True)
            shutil.copytree(backup / target.name, target)
        else:
            for name in ("src", "armor.project.json", "pyproject.toml"):
                if (backup / name).exists():
                    destination = target / name
                    if destination.is_dir():
                        shutil.rmtree(destination)
                    shutil.move(str(backup / name), str(destination))
        systemctl("restart", unit)
        raise Refused(500, "unhealthy_rolled_back")
    job.step("check", "done")
    prune_old(PREFIX / "releases-old")
    return {"backup": backup.name}


def update_job(components: list[str], force: bool) -> Job:
    steps = [(f"{component}.{part}", f"{component}: {text}") for component in components for part, text in
             (("download", "download"), ("verify", "check the hash"), ("install", "install"), ("restart", "restart"), ("check", "check it works"))]
    job = Job("update", steps, label=", ".join(components))
    remember(job)

    def work() -> None:
        with WORK:
            failed = ""
            results: dict[str, object] = {}
            for component in components:
                prefix = f"{component}."
                job.say(f"--- {component} ---")
                try:
                    release = latest_release(component, force=True)
                    if "error" in release:
                        raise Refused(502, str(release["error"]))
                    installed = installed_version(component)
                    if installed and version_key(str(release["version"])) <= version_key(installed) and not force:
                        job.say(f"{component} is already at {installed}")
                        for part in ("download", "verify", "install", "restart", "check"):
                            job.step(prefix + part, "skipped")
                        continue
                    with tempfile.TemporaryDirectory(prefix="armor-maint-") as work_dir:
                        scoped = ScopedJob(job, prefix)
                        staged = fetch_asset(scoped, component, release, Path(work_dir))  # type: ignore[arg-type]
                        info = COMPONENTS[component]
                        results[component] = (install_release_dir(scoped, component, staged, str(release["version"])) if info["kind"] == "release-dir"  # type: ignore[arg-type]
                                              else replace_tree(scoped, component, staged))  # type: ignore[arg-type]
                    job.say(f"{component} is now at {release['version']}")
                except Refused as refusal:
                    job.say(f"{component} failed: {refusal.code}")
                    for item in job.steps:
                        if str(item["id"]).startswith(prefix) and item["state"] == "running":
                            item["state"] = "failed"
                    failed = f"{component}: {refusal.code}"
                    break
                except Exception as error:                                    # a bug here must be seen in the log, not take the helper down
                    job.say(f"{component} failed: {type(error).__name__}: {error}")
                    failed = f"{component}: internal_error"
                    break
            job.result = {"components": results}
            job.finish(failed)
            record_history(job)

    threading.Thread(target=work, daemon=True).start()
    return job


class ScopedJob:
    """The job as one component sees it: its steps are named `<component>.<step>`."""

    def __init__(self, job: Job, prefix: str) -> None:
        self.job, self.prefix = job, prefix

    def say(self, line: str) -> None:
        self.job.say(line)

    def step(self, step_id: str, state: str, percent: int | None = None) -> None:
        self.job.step(self.prefix + step_id, state, percent)


def rollback_job(component: str) -> Job:
    job = Job("rollback", [(f"{component}.restore", f"{component}: put the previous one back"), (f"{component}.check", f"{component}: check it works")], label=component)
    remember(job)

    def work() -> None:
        with WORK:
            try:
                info = COMPONENTS[component]
                unit = str(info["service"])
                job.step(f"{component}.restore", "running", 20)
                if info["kind"] == "release-dir":
                    releases = sorted((entry for entry in (PREFIX / "releases").iterdir() if entry.is_dir()), key=lambda entry: entry.name)   # named by the time they were made
                    current = (PREFIX / "current").resolve()
                    older = [entry for entry in releases if entry.name < current.name]
                    if not older:
                        raise Refused(404, "nothing_to_go_back_to")
                    link = PREFIX / "current.new"
                    link.unlink(missing_ok=True)
                    link.symlink_to(older[-1])
                    os.replace(link, PREFIX / "current")
                    job.say(f"`current` points to {older[-1].name} again")
                else:
                    backups = sorted((entry for entry in (PREFIX / "releases-old").glob(f"maint-{component}-*") if entry.is_dir()), key=lambda entry: entry.name)
                    if not backups:
                        raise Refused(404, "nothing_to_go_back_to")
                    backup = backups[-1]
                    target = PREFIX / str(info["target"])
                    if info["kind"] == "python-package":
                        shutil.rmtree(target, ignore_errors=True)
                        shutil.copytree(backup / target.name, target)
                    else:
                        for entry in backup.iterdir():
                            destination = (target / entry.name)
                            if destination.is_dir():
                                shutil.rmtree(destination)
                            if entry.is_dir():
                                shutil.copytree(entry, destination)
                            else:
                                shutil.copy2(entry, destination)
                    job.say(f"restored from {backup.name}")
                job.step(f"{component}.restore", "done")
                systemctl("restart", unit)
                job.step(f"{component}.check", "running", 30)
                if not healthy(component, unit, wait=25.0):
                    raise Refused(500, "unhealthy")
                job.step(f"{component}.check", "done")
                job.finish()
            except Refused as refusal:
                job.say(f"failed: {refusal.code}")
                job.finish(refusal.code)
            except Exception as error:
                job.say(f"failed: {type(error).__name__}: {error}")
                job.finish("internal_error")
            record_history(job)

    threading.Thread(target=work, daemon=True).start()
    return job


# ---- the operating system -----------------------------------------------------------------------------------------------------------------------

def apt_environment() -> dict[str, str]:
    return {**os.environ, "DEBIAN_FRONTEND": "noninteractive", "LANG": "C", "LC_ALL": "C"}


def upgradable() -> list[dict[str, str]]:
    done = subprocess.run([APT, "list", "--upgradable"], capture_output=True, text=True, timeout=120, env=apt_environment(), check=False)
    packages = []
    for line in done.stdout.splitlines():
        match = re.match(r"^([^/\s]+)/(\S+)\s+(\S+)\s+(\S+)(?:\s+\[upgradable from: (\S+)\])?", line)
        if match:
            packages.append({"name": match.group(1), "to": match.group(3), "from": match.group(5) or ""})
    return packages


_ATTENTION: dict[str, object] = {"at": 0.0, "kept_back": [], "broken": []}


def system_attention() -> dict[str, list[str]]:
    """What a plain upgrade cannot settle: the packages it keeps back (a new kernel, for one, needs others installed or removed) and the packages left half-installed or half-configured.
    Reading the first one simulates an upgrade (a second or two), so the answer is kept for a minute."""
    import time as _time
    if float(_ATTENTION["at"]) and _time.monotonic() - float(_ATTENTION["at"]) < 60:
        return {"kept_back": list(_ATTENTION["kept_back"]), "broken": list(_ATTENTION["broken"])}  # type: ignore[arg-type]
    kept: list[str] = []
    try:
        simulated = subprocess.run([APT_GET, "-s", "upgrade"], capture_output=True, text=True, timeout=120, env=apt_environment(), check=False)
        reading = False
        for line in simulated.stdout.splitlines():
            if line.startswith("The following packages have been kept back"):
                reading = True
                continue
            if reading:
                if line.startswith("  "):
                    kept.extend(line.split())
                else:
                    reading = False
    except (OSError, subprocess.SubprocessError):
        pass
    broken: list[str] = []
    try:
        audit = subprocess.run([DPKG, "--audit"], capture_output=True, text=True, timeout=60, env=apt_environment(), check=False)
        for line in audit.stdout.splitlines():
            if line.startswith(" ") and line.strip():
                broken.append(line.split()[0])
    except (OSError, subprocess.SubprocessError):
        pass
    _ATTENTION.update({"at": _time.monotonic(), "kept_back": kept, "broken": broken})
    return {"kept_back": kept[:50], "broken": broken[:50]}


def os_state() -> dict[str, object]:
    release: dict[str, str] = {}
    try:
        for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("=")
            release[key] = value.strip().strip('"')
    except OSError:
        pass
    kernel = subprocess.run(["uname", "-r"], capture_output=True, text=True, check=False).stdout.strip()
    try:
        uptime = float(Path("/proc/uptime").read_text().split()[0])
    except (OSError, ValueError):
        uptime = 0.0
    attention = system_attention()
    return {"name": release.get("PRETTY_NAME", ""), "kernel": kernel, "uptime_s": int(uptime), "reboot_required": Path("/var/run/reboot-required").exists(),
            "packages": upgradable()[:200], "kept_back": attention["kept_back"], "broken": attention["broken"]}


def system_check_job() -> Job:
    job = Job("system-check", [("refresh", "look for updates of the system")], label="apt update")
    remember(job)

    def work() -> None:
        with WORK:
            try:
                job.step("refresh", "running", 10)
                process = subprocess.Popen([APT_GET, "update"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=apt_environment())
                assert process.stdout is not None
                for line in process.stdout:
                    job.say(line.rstrip())
                    job.step("refresh", "running", 60)
                code = process.wait(timeout=600)
                if code != 0:
                    raise Refused(502, "apt_update_failed")
                packages = upgradable()
                job.result = {"upgradable": len(packages)}
                job.say(f"{len(packages)} packages can be upgraded")
                job.step("refresh", "done")
                job.finish()
            except Refused as refusal:
                job.finish(refusal.code)
            except Exception as error:
                job.say(f"failed: {type(error).__name__}: {error}")
                job.finish("internal_error")
            record_history(job)

    threading.Thread(target=work, daemon=True).start()
    return job


UPGRADE_MODES = ("upgrade", "full", "repair")


def system_upgrade_job(mode: str = "upgrade") -> Job:
    """`upgrade` installs newer versions of what is installed and keeps back what needs anything else; `full` (apt full-upgrade) also installs and removes what the new versions need - the way
    a new kernel gets in; `repair` finishes the packages left half-installed (dpkg --configure -a) and fixes broken dependencies (apt-get -f install)."""
    if mode not in UPGRADE_MODES:
        raise Refused(422, "bad_mode")
    steps = [("configure", "finish the half-installed packages"), ("fix", "fix the broken dependencies")] if mode == "repair" else [("refresh", "update the list"), ("download", "download the packages"), ("install", "install them")]
    job = Job("system-upgrade", steps, label={"upgrade": "apt upgrade", "full": "apt full-upgrade", "repair": "apt repair"}[mode])
    remember(job)

    def work() -> None:
        with WORK:
            try:
                if mode == "repair":
                    repair(job)
                    job.result = {"reboot_required": Path("/var/run/reboot-required").exists()}
                    _ATTENTION["at"] = 0.0
                    job.finish()
                    record_history(job)
                    return
                job.step("refresh", "running", 20)
                refresh = subprocess.run([APT_GET, "update"], capture_output=True, text=True, timeout=600, env=apt_environment(), check=False)
                job.say("apt-get update " + ("done" if refresh.returncode == 0 else "failed"))
                if refresh.returncode != 0:
                    raise Refused(502, "apt_update_failed")
                job.step("refresh", "done")
                before = upgradable()
                job.say(f"{len(before)} packages to upgrade")
                read_end, write_end = os.pipe()
                command = [APT_GET, "-y", "-o", "Dpkg::Options::=--force-confold", "-o", "Dpkg::Options::=--force-confdef", f"-o", f"APT::Status-Fd={write_end}", "full-upgrade" if mode == "full" else "upgrade"]
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=apt_environment(), pass_fds=(write_end,))
                os.close(write_end)

                def follow_status() -> None:
                    with os.fdopen(read_end, "r") as status:
                        for line in status:
                            parts = line.strip().split(":", 3)
                            if len(parts) == 4 and parts[0] in ("dlstatus", "pmstatus"):
                                try:
                                    percent = int(float(parts[2]))
                                except ValueError:
                                    continue
                                job.step("download" if parts[0] == "dlstatus" else "install", "running", percent)
                                if parts[0] == "pmstatus" and percent == 0:
                                    job.step("download", "done")

                threading.Thread(target=follow_status, daemon=True).start()
                assert process.stdout is not None
                for line in process.stdout:
                    text = line.rstrip()
                    if text:
                        job.say(text)
                code = process.wait(timeout=3 * 3600)
                if code != 0:
                    raise Refused(502, "apt_upgrade_failed")
                job.step("download", "done")
                job.step("install", "done")
                job.result = {"upgraded": len(before), "reboot_required": Path("/var/run/reboot-required").exists()}
                _ATTENTION["at"] = 0.0
                job.finish()
            except Refused as refusal:
                job.say(f"failed: {refusal.code}")
                job.finish(refusal.code)
            except Exception as error:
                job.say(f"failed: {type(error).__name__}: {error}")
                job.finish("internal_error")
            record_history(job)

    threading.Thread(target=work, daemon=True).start()
    return job


def stream(job: Job, command: list[str], timeout: int = 3 * 3600) -> int:
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=apt_environment())
    assert process.stdout is not None
    for line in process.stdout:
        text = line.rstrip()
        if text:
            job.say(text)
    return process.wait(timeout=timeout)


def repair(job: Job) -> None:
    """Finish what an interrupted or failed installation left behind, then let apt settle the dependencies. Both steps run even if the first one fails: the second often fixes it."""
    job.step("configure", "running", 30)
    job.say("dpkg --configure -a")
    first = stream(job, [DPKG, "--configure", "-a", "--force-confold", "--force-confdef"])
    job.step("configure", "done" if first == 0 else "failed", 100)
    job.step("fix", "running", 30)
    job.say("apt-get -f install")
    second = stream(job, [APT_GET, "-y", "-f", "-o", "Dpkg::Options::=--force-confold", "-o", "Dpkg::Options::=--force-confdef", "install"])
    job.step("fix", "done" if second == 0 else "failed", 100)
    if second != 0:
        raise Refused(502, "apt_repair_failed")


def reboot_machine() -> dict[str, object]:
    subprocess.run(["systemd-run", "--on-active=5", SYSTEMCTL, "reboot"], capture_output=True, check=False)
    return {"ok": True, "in_s": 5}


# ---- the console --------------------------------------------------------------------------------------------------------------------------------

class ConsoleJob:
    """One command run as root, in a shell of its own with the folder the person was in; the output is kept (bounded) for whoever follows it."""

    def __init__(self, command: str, cwd: str, timeout: float) -> None:
        self.id = f"c{int(time.time())}-{os.urandom(3).hex()}"
        self.command, self.timeout = command, timeout
        self.output = bytearray()
        self.state = "running"
        self.code: int | None = None
        self.cwd = cwd
        self.started = time.time()
        self.finished = 0.0
        self.truncated = False
        self.lock = threading.Lock()
        script = f'cd -- "$ARMOR_CWD" 2>/dev/null || cd /\n{command}\n__armor_rc=$?\nprintf "\\n__ARMOR_PWD__%s\\n" "$(pwd)"\nexit $__armor_rc\n'
        self.process = subprocess.Popen(["/bin/bash", "-c", script], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env={**os.environ, "ARMOR_CWD": cwd, "TERM": "dumb", "LANG": os.environ.get("LANG", "C.UTF-8")},
                                        start_new_session=True)
        threading.Thread(target=self.read, daemon=True).start()
        threading.Thread(target=self.watch, daemon=True).start()

    def read(self) -> None:
        assert self.process.stdout is not None
        while True:
            chunk = self.process.stdout.read1(4096)                           # type: ignore[attr-defined]
            if not chunk:
                break
            with self.lock:
                if len(self.output) + len(chunk) > MAX_CONSOLE_BYTES:
                    self.truncated = True
                    chunk = chunk[: max(0, MAX_CONSOLE_BYTES - len(self.output))]
                self.output.extend(chunk)
        self.code = self.process.wait()
        with self.lock:
            marker = self.output.rfind(b"\n__ARMOR_PWD__")
            if marker >= 0:
                folder = self.output[marker + len(b"\n__ARMOR_PWD__"):].split(b"\n", 1)[0].decode("utf-8", "replace")
                if folder.startswith("/"):
                    self.cwd = folder
                del self.output[marker:]
            self.state = "done" if self.state == "running" else self.state
            self.finished = time.time()

    def watch(self) -> None:
        deadline = self.started + self.timeout
        while self.process.poll() is None:
            if time.time() > deadline:
                with self.lock:
                    self.state = "timeout"
                self.cancel()
                return
            time.sleep(0.25)

    def cancel(self) -> None:
        try:
            os.killpg(self.process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass

    def view(self, since: int = 0) -> dict[str, object]:
        with self.lock:
            data = bytes(self.output[since:])
            return {"id": self.id, "command": self.command, "state": self.state, "code": self.code, "cwd": self.cwd, "output": data.decode("utf-8", "replace"), "offset": since + len(data),
                    "truncated": self.truncated, "started": self.started, "finished": self.finished}


CONSOLE_JOBS: dict[str, ConsoleJob] = {}


def console_run(command: str, cwd: str, timeout: float) -> dict[str, object]:
    if not CONSOLE_ENABLED:
        raise Refused(403, "console_disabled")
    if not command.strip() or len(command) > 4000 or "\x00" in command:
        raise Refused(422, "invalid_command")
    if sum(1 for job in CONSOLE_JOBS.values() if job.state == "running") >= 4:
        raise Refused(429, "too_many_running")
    folder = cwd if cwd.startswith("/") and len(cwd) < 400 and "\n" not in cwd else "/root"
    job = ConsoleJob(command, folder, min(3600.0, max(1.0, timeout)))
    CONSOLE_JOBS[job.id] = job
    if len(CONSOLE_JOBS) > 30:
        for key in sorted(CONSOLE_JOBS, key=lambda item: CONSOLE_JOBS[item].started)[: len(CONSOLE_JOBS) - 30]:
            if CONSOLE_JOBS[key].state != "running":
                CONSOLE_JOBS.pop(key, None)
    return job.view()


# ---- the server of the socket ---------------------------------------------------------------------------------------------------------------------

def overview(force: bool) -> dict[str, object]:
    running = [job.view(0) for job in JOBS.values() if job.state == "running"]
    return {"agent": AGENT_VERSION, "components": [component_state(key, force) for key in ORDER], "os": os_state(), "console": CONSOLE_ENABLED, "running": [item["id"] for item in running],
            "history": history()}


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "armor-maint"
    token = ""

    def log_message(self, format: str, *args: object) -> None:
        return

    def address_string(self) -> str:
        return "unix"

    def reply(self, status: int, body: object) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def body(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length") or 0)
        if length > 64 * 1024:
            raise Refused(413, "body_too_large")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8") or "{}")
        except ValueError as error:
            raise Refused(400, "invalid_json") from error
        if not isinstance(data, dict):
            raise Refused(400, "invalid_json")
        return data

    def route(self, method: str) -> None:
        try:
            given = self.headers.get("X-Armor-Maint-Token", "")
            if not self.token or not hmac.compare_digest(given.encode(), self.token.encode()):
                raise Refused(401, "unauthorized")
            path, _, query = self.path.partition("?")
            parts = [part for part in path.split("/") if part]
            if parts[:1] != ["v1"]:
                raise Refused(404, "not_found")
            parts = parts[1:]
            arguments = dict(pair.split("=", 1) for pair in query.split("&") if "=" in pair)
            if method == "GET" and parts == ["overview"]:
                self.reply(200, overview(arguments.get("force") == "1"))
            elif method == "POST" and parts == ["updates"]:
                data = self.body()
                wanted = data.get("components")
                if not isinstance(wanted, list) or not wanted or any(item not in COMPONENTS for item in wanted):
                    raise Refused(422, "unknown_component")
                if any(job.state == "running" for job in JOBS.values()):
                    raise Refused(409, "busy")
                chosen = [key for key in ORDER if key in wanted]
                self.reply(202, update_job(chosen, data.get("force") is True).view())
            elif method == "POST" and len(parts) == 3 and parts[0] == "updates" and parts[2] == "rollback":
                if parts[1] not in COMPONENTS:
                    raise Refused(404, "unknown_component")
                if any(job.state == "running" for job in JOBS.values()):
                    raise Refused(409, "busy")
                self.reply(202, rollback_job(parts[1]).view())
            elif method == "POST" and parts == ["system", "check"]:
                if any(job.state == "running" for job in JOBS.values()):
                    raise Refused(409, "busy")
                self.reply(202, system_check_job().view())
            elif method == "POST" and parts == ["system", "upgrade"]:
                if any(job.state == "running" for job in JOBS.values()):
                    raise Refused(409, "busy")
                data = self.body()
                mode = data.get("mode") if isinstance(data.get("mode"), str) else "upgrade"
                self.reply(202, system_upgrade_job(str(mode)).view())
            elif method == "POST" and parts == ["system", "reboot"]:
                self.reply(202, reboot_machine())
            elif method == "POST" and parts == ["history", "clear"]:
                self.reply(200, {"ok": True, "cleared": clear_history()})
            elif method == "GET" and len(parts) == 2 and parts[0] == "jobs":
                job = JOBS.get(parts[1])
                if not job:
                    raise Refused(404, "no_such_job")
                self.reply(200, job.view(int(arguments.get("since", "0") or 0)))
            elif method == "POST" and parts == ["console", "run"]:
                data = self.body()
                self.reply(202, console_run(str(data.get("command", "")), str(data.get("cwd", "/root")), float(data.get("timeout", 120) or 120)))
            elif method == "GET" and len(parts) == 3 and parts[:2] == ["console", "jobs"]:
                job = CONSOLE_JOBS.get(parts[2])
                if not job:
                    raise Refused(404, "no_such_job")
                self.reply(200, job.view(int(arguments.get("since", "0") or 0)))
            elif method == "POST" and len(parts) == 4 and parts[:2] == ["console", "jobs"] and parts[3] == "cancel":
                job = CONSOLE_JOBS.get(parts[2])
                if not job:
                    raise Refused(404, "no_such_job")
                job.cancel()
                self.reply(200, {"ok": True})
            elif method == "GET" and parts == ["console"]:
                self.reply(200, {"enabled": CONSOLE_ENABLED})
            else:
                raise Refused(404, "not_found")
        except Refused as refusal:
            self.reply(refusal.status, {"error": refusal.code})
        except subprocess.TimeoutExpired:
            self.reply(504, {"error": "timeout"})
        except Exception:                                  # a bug here must never take the machine's services down with it
            self.reply(500, {"error": "internal_error"})

    def do_GET(self) -> None: self.route("GET")
    def do_POST(self) -> None: self.route("POST")


class UnixServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True

    def get_request(self):                                  # type: ignore[no-untyped-def]
        request, _ = super().get_request()
        return request, ("unix", 0)


def serve(socket_path: str, token: str, group: str | None) -> None:
    path = Path(socket_path)
    if path.exists():
        path.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)
    Handler.token = token
    server = UnixServer(socket_path, Handler)
    os.chmod(socket_path, 0o660)
    if group:
        import grp
        os.chown(socket_path, 0, grp.getgrnam(group).gr_gid)
    print(f"armor-maintenance {AGENT_VERSION} listening on {socket_path} (console {'ON' if CONSOLE_ENABLED else 'off'})", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Maintenance helper of A.R.M.O.R. Studio: updates from GitHub, the system's updates and the root console")
    parser.add_argument("--socket", default="/run/armor-maint.sock")
    parser.add_argument("--group", default="armor", help="the group allowed to open the socket")
    arguments = parser.parse_args()
    token = os.environ.get("ARMOR_MAINT_TOKEN", "")
    if len(token) < 24:
        print("ARMOR_MAINT_TOKEN must be set (at least 24 characters)", file=sys.stderr)
        return 2
    serve(arguments.socket, token, arguments.group)
    return 0


if __name__ == "__main__":
    sys.exit(main())
