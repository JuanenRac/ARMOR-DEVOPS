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
#                 It also demands the Ed25519 signature of the release (see "signed packages" below) before it unpacks anything.
#   * SYSTEM    - the operating system's own updates (apt): what can be upgraded, the upgrade with its progress, whether it needs a reboot, and the reboot.
#   * CONSOLE   - OFF unless ARMOR_MAINT_CONSOLE=1 is set on purpose in its environment file: one command at a time as root, with a time limit, its output kept for
#                 whoever asked, and nothing hidden - the server writes every command in the audit trail and asks an administrator for the password again before the first.
# It listens on a Unix socket that only the group `armor` can open, and also wants a token (ARMOR_MAINT_TOKEN). Standard library only.
#
#   armor_maintenance_agent.py --socket /run/armor-maint.sock        # as root, by the systemd unit armor-maintenance.service
from __future__ import annotations

import argparse
import base64
import datetime
import hashlib
import hmac
import http.server
import json
import os
import re
import shutil
import signal
import socket
import socketserver
import ssl
import struct
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

AGENT_VERSION = "0.1.7"
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
# Below this free space (MB) on the disk of the folder, the copies set aside are removed oldest first, down to the newest one, even when fewer than KEEP_OLD are left (the setting
# ARMOR_MAINT_MIN_FREE_MB of armor.maint.env, 0 to turn it off; 500 when it is not written).
MIN_FREE_MB_DEFAULT = 500
DISK_USAGE = shutil.disk_usage
MAINT_ENV = Path(os.environ.get("ARMOR_MAINT_ENV", str(PREFIX / "etc" / "armor.maint.env")))
# Trying a new server before it replaces the running one (blue/green): ARMOR_MAINT_STAGING=on in armor.maint.env starts it from its new release folder on a free port of the loopback, with an empty data
# folder and without the broker, and asks /healthz before `current` is switched; off (the default) switches and checks afterwards, as always. ARMOR_MAINT_STAGING_WAIT_S is how long it may take (5 to 120, 30 by default).
STAGING_WAIT_DEFAULT = 30
NODE_BINARY = os.environ.get("ARMOR_NODE", "node")

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


def http_get(url: str, accept: str = "application/vnd.github+json", timeout: float = 20.0, local_tls: bool = False) -> bytes:
    request = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": "armor-maintenance", **({"Authorization": f"Bearer {GITHUB_TOKEN}"} if GITHUB_TOKEN else {})})
    # local_tls: the health check of this machine's own server, which may serve https with its own certificate (nothing leaves the machine, nothing secret is sent).
    context = ssl._create_unverified_context() if local_tls and url.startswith("https://") else None   # noqa: S323
    with urllib.request.urlopen(request, timeout=timeout, context=context) as response:     # noqa: S310 - the address is fixed to GitHub (or a test server)
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
                  "notes": str(data.get("body", ""))[:30000]}
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
            done = sum(100 if item["state"] in ("done", "skipped") else int(item["percent"]) if item["state"] == "running" else 0 for item in self.steps)  # type: ignore[misc,call-overload]
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
        raise Refused(500, "history_not_cleared") from None
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
    url = assets.get(asset + ".sha256")                                       # type: ignore[union-attr,attr-defined]
    if not url:
        raise Refused(422, "no_checksum")
    text = http_get(str(url), accept="application/octet-stream").decode("utf-8", "replace")
    match = re.match(r"\s*([0-9a-fA-F]{64})", text)
    if not match:
        raise Refused(422, "no_checksum")
    return match.group(1).lower()

# ---- signed packages ----------------------------------------------------------------------------------------------------------------------------
# Every package a release carries has a `<package>.sig2` next to it: the Ed25519 signature (64 bytes as 128 hexadecimal digits) of the manifest
#   armor-fw/1|<component>|package|<version>|<sha256 of the package>
# the same manifest the firmware images are signed with (their board is `package` here, which no node ever has), made with the private key of the releases, which is never on GitHub.
# The helper verifies it with the public key below BEFORE it unpacks anything, so somebody who can only change what a release holds on GitHub cannot make this machine install his
# code. The manifest binds the package to its component and its version, so a signed package of the past, or of another component, can not be presented as the newest one, and the
# signature of a firmware image (another project and a real board) can never pass as a package signature. The public key is the same one the firmware trusts (core/fw_trust.hpp).
# The check is pure Python (RFC 8032), because the standard library has no Ed25519.
# Two keys are trusted at most, so that the key can be changed without a machine falling out of step: the one in PACKAGE_PUBLIC_KEY and, during a rotation, a second one written as
# ARMOR_MAINT_NEXT_KEY=<64 hex digits> in the machine's environment file (see docs/SIGNED_PACKAGES.md). Their fingerprints are in the overview.
# The older `<package>.sig` (text `armor-pkg/1|<component>|<version>|<sha256>`) is accepted only when ARMOR_MAINT_SIGNATURE=either is written in the same file; by default
# (`manifest`) a package with no valid `.sig2` is refused.
# The only way round all of it is ARMOR_MAINT_ALLOW_UNSIGNED=1 written in the machine's environment file (armor.maint.env): never an API call, and never the process environment.
PACKAGE_PUBLIC_KEY = "664478b12a8799ab18970f58e974f14a6d0bf5623f0a22c65c3aaa32997054d2"
_P = 2 ** 255 - 19
_Q = 2 ** 252 + 27742317777372353535851937790883648493
_D = -121665 * pow(121666, _P - 2, _P) % _P
_I = pow(2, (_P - 1) // 4, _P)


def _recover_x(y: int, sign: int) -> int | None:
    if y >= _P:
        return None
    x2 = (y * y - 1) * pow(_D * y * y + 1, _P - 2, _P) % _P
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (_P + 3) // 8, _P)
    if (x * x - x2) % _P:
        x = x * _I % _P
    if (x * x - x2) % _P:
        return None
    return _P - x if (x & 1) != sign else x


_BASE_Y = 4 * pow(5, _P - 2, _P) % _P
_BASE_X = _recover_x(_BASE_Y, 0) or 0
_BASE = (_BASE_X, _BASE_Y, 1, _BASE_X * _BASE_Y % _P)


def _add(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    A, B = (a[1] - a[0]) * (b[1] - b[0]) % _P, (a[1] + a[0]) * (b[1] + b[0]) % _P
    C, D = 2 * a[3] * b[3] * _D % _P, 2 * a[2] * b[2] % _P
    E, F, G, H = B - A, D - C, D + C, B + A
    return E * F % _P, G * H % _P, F * G % _P, E * H % _P


def _multiply(scalar: int, point: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    result = (0, 1, 1, 0)
    while scalar:
        if scalar & 1:
            result = _add(result, point)
        point = _add(point, point)
        scalar >>= 1
    return result


def _encode(point: tuple[int, int, int, int]) -> bytes:
    zinv = pow(point[2], _P - 2, _P)
    x, y = point[0] * zinv % _P, point[1] * zinv % _P
    return (y | ((x & 1) << 255)).to_bytes(32, "little")


def _decode(data: bytes) -> tuple[int, int, int, int] | None:
    number = int.from_bytes(data, "little")
    y, sign = number & ((1 << 255) - 1), number >> 255
    x = _recover_x(y, sign)
    return None if x is None else (x, y, 1, x * y % _P)


def ed25519_verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
    """True only for a valid Ed25519 signature (RFC 8032) of `message` by `public_key`."""
    if len(public_key) != 32 or len(signature) != 64:
        return False
    point_a, point_r = _decode(public_key), _decode(signature[:32])
    scalar = int.from_bytes(signature[32:], "little")
    if point_a is None or point_r is None or scalar >= _Q:
        return False
    k = int.from_bytes(hashlib.sha512(signature[:32] + public_key + message).digest(), "little") % _Q
    return _encode(_multiply(scalar, _BASE)) == _encode(_add(point_r, _multiply(k, point_a)))


def package_message(component: str, version: str, sha256_hex: str) -> bytes:
    """The text the older signature (.sig) covers."""
    return f"armor-pkg/1|{component}|{version}|{sha256_hex}".encode("utf-8")


def manifest_message(component: str, version: str, sha256_hex: str) -> bytes:
    """The manifest the signature of a package (.sig2) covers: the one of the firmware images, with `package` where the board goes."""
    return f"armor-fw/1|{component}|package|{version}|{sha256_hex}".encode("utf-8")


def key_fingerprint(public_key_hex: str) -> str:
    """The first 16 hexadecimal digits of the SHA-256 of a public key: what is shown to a person instead of the key."""
    return hashlib.sha256(bytes.fromhex(public_key_hex)).hexdigest()[:16]


def trusted_keys() -> list[str]:
    """The public keys a package may be signed with: the built-in one and, during a rotation, the second one of the environment file. Never more than two."""
    keys = [PACKAGE_PUBLIC_KEY]
    extra = read_settings(MAINT_ENV).get("ARMOR_MAINT_NEXT_KEY", "").strip().lower()
    if re.fullmatch(r"[0-9a-f]{64}", extra) and extra not in keys:
        keys.append(extra)
    return keys


def _signature_ok(message: bytes, signature_text: str, public_key_hex: str | None) -> bool:
    text = signature_text.strip()
    if not re.fullmatch(r"[0-9a-fA-F]{128}", text):
        return False
    return any(ed25519_verify(bytes.fromhex(key), message, bytes.fromhex(text)) for key in ([public_key_hex] if public_key_hex else trusted_keys()))


def _parts_ok(component: str, version: str, sha256_hex: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{64}", sha256_hex)) and not any(re.search(r"[|\s]", part) or not part for part in (component, version))


def package_signature_ok(component: str, version: str, sha256_hex: str, signature_text: str, public_key_hex: str | None = None) -> bool:
    """The older signature (.sig, text armor-pkg/1)."""
    return _parts_ok(component, version, sha256_hex) and _signature_ok(package_message(component, version, sha256_hex), signature_text, public_key_hex)


def manifest_signature_ok(component: str, version: str, sha256_hex: str, signature_text: str, public_key_hex: str | None = None) -> bool:
    """The signature of the manifest of a package (.sig2, text armor-fw/1 with `package` as the board)."""
    return _parts_ok(component, version, sha256_hex) and _signature_ok(manifest_message(component, version, sha256_hex), signature_text, public_key_hex)


def signature_mode() -> str:
    """`manifest` (default: only the manifest signature counts) or `either` (the older .sig is accepted too); read from the machine's environment file, like the emergency override."""
    return "either" if read_settings(MAINT_ENV).get("ARMOR_MAINT_SIGNATURE", "").strip().lower() == "either" else "manifest"


def unsigned_allowed() -> bool:
    """The emergency override: read from the machine's environment file at the moment of use, so it cannot be set through the API or the process environment."""
    return read_settings(MAINT_ENV).get("ARMOR_MAINT_ALLOW_UNSIGNED") == "1"


def safe_extract(archive: Path, destination: Path) -> None:
    """Unpack a tarball only if nothing in it can land outside the folder: no absolute names, no .., no links and no devices."""
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar.getmembers():
            name = member.name
            if name.startswith("/") or ".." in Path(name).parts or not (member.isfile() or member.isdir()):
                raise Refused(422, "unsafe_archive")
        tar.extractall(destination)                                           # noqa: S202 - every member was checked above


def check_signature(job: Job, component: str, version: str, assets: dict[str, str], asset: str, digest: str) -> None:
    """Refuses (nothing is unpacked) unless the release carries a valid signature of this package, or the override is written in the environment file."""
    override = unsigned_allowed()
    legacy = signature_mode() == "either"
    failure = ""
    verified = ""

    def fetch(suffix: str) -> str | None:
        url = assets.get(asset + suffix)
        if not url:
            return None
        try:
            return http_get(url, accept="application/octet-stream").decode("ascii", "replace")
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            return ""

    manifest = fetch(".sig2")
    if manifest is not None and manifest_signature_ok(component, version, digest, manifest):
        verified = "signature of the release verified"
    elif legacy:
        older = fetch(".sig")
        if older is not None and package_signature_ok(component, version, digest, older):
            verified = "signature of the release verified (the older .sig, accepted because ARMOR_MAINT_SIGNATURE=either)"
        elif manifest is None and older is None:
            failure = "missing_signature"
        else:
            failure = "bad_signature"
    elif manifest is None:
        failure = "missing_signature"
    else:
        failure = "bad_signature"
    if not failure:
        job.say(verified)
        return
    if override:
        job.say(f"WARNING: {failure} for {asset} - installing anyway because ARMOR_MAINT_ALLOW_UNSIGNED=1 is set in {MAINT_ENV}; remove it as soon as possible")
        print(f"WARNING: unsigned install of {asset} ({failure}) allowed by ARMOR_MAINT_ALLOW_UNSIGNED=1", file=sys.stderr, flush=True)
        return
    job.say(f"{asset}: {failure}; nothing was unpacked")
    raise Refused(422, failure)


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
    check_signature(job, component, version, assets, asset, digest)       # type: ignore[arg-type]
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
                if b'"ok":true' in http_get(HEALTH_URL, accept="application/json", timeout=3.0, local_tls=True).replace(b" ", b""):
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


def lock_fingerprint(path: Path) -> bytes:
    """What a package-lock.json says about the dependencies, without the version of the project itself: that number changes in every release and is no reason to run `npm ci` again."""
    raw = path.read_bytes()
    try:
        lock = json.loads(raw)
        lock.pop("version", None)
        root = lock.get("packages", {}).get("")
        if isinstance(root, dict):
            root.pop("version", None)
        return hashlib.sha256(json.dumps(lock, sort_keys=True).encode("utf-8")).digest()
    except (ValueError, AttributeError):
        return hashlib.sha256(raw).digest()


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


def prune_old(folder: Path, prefix: str = "", protect: tuple[Path, ...] = ()) -> None:
    """Keep the newest KEEP_OLD folders that start with `prefix`; anything else in the folder - what the installer set aside - is never touched.
    The newest is the one with the latest NAME (they are named by the time they were made): the time of modification cannot be trusted, because a release folder is a copy of
    the one before and a copy keeps the old time, so the folder just made looked the oldest of all and was the one removed. A folder in `protect` (the one `current` points to) is never removed."""
    try:
        keep = {path.resolve() for path in protect}
        entries = sorted((entry for entry in folder.iterdir() if entry.is_dir() and entry.name.startswith(prefix)), key=lambda entry: entry.name)
        for entry in entries[:-KEEP_OLD]:
            if entry.resolve() not in keep:
                shutil.rmtree(entry, ignore_errors=True)
        # A disk that is nearly full cannot afford six copies: the oldest go until there is room again, and the newest one that is not in use always stays.
        floor = min_free_bytes()
        if floor > 0:
            left = [entry for entry in entries[-KEEP_OLD:] if entry.exists() and entry.resolve() not in keep]
            while len(left) > 1 and DISK_USAGE(folder).free < floor:
                shutil.rmtree(left.pop(0), ignore_errors=True)
    except OSError:
        pass


def min_free_bytes() -> int:
    """The free space under which the copies set aside are removed beyond the usual number (ARMOR_MAINT_MIN_FREE_MB in the settings file; a value that is not a whole number counts as the default)."""
    value = read_settings(MAINT_ENV).get("ARMOR_MAINT_MIN_FREE_MB", "")
    megabytes = int(value) if re.fullmatch(r"\d{1,7}", value) else MIN_FREE_MB_DEFAULT
    return megabytes * 1024 * 1024


def staging_enabled() -> bool:
    """Is the new server tried out before the switch? Only the exact word `on` turns it on; anything else keeps the old behaviour."""
    return read_settings(MAINT_ENV).get("ARMOR_MAINT_STAGING", "off").strip().lower() == "on"


def staging_wait() -> float:
    value = read_settings(MAINT_ENV).get("ARMOR_MAINT_STAGING_WAIT_S", "")
    return float(min(120, max(5, int(value)))) if re.fullmatch(r"\d{1,4}", value) else float(STAGING_WAIT_DEFAULT)


def free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def staging_environment(data_dir: Path, port: int) -> dict[str, str]:
    """What the server being tried gets: the settings of the real one (secrets, limits), but its own port on the loopback over plain http, an empty data folder and no broker, so it can
    neither touch the data nor take the place of the running server on the broker (two clients with the same name would throw each other out)."""
    env = {key: os.environ[key] for key in ("PATH", "LANG", "TZ") if key in os.environ}
    for name in ("armor.env", "armor.network.env"):
        env.update(read_settings(PREFIX / "etc" / name))
    for key in ("TLS_CERT_PATH", "TLS_KEY_PATH", "ARMOR_COOKIE_SECURE", "ARMOR_MQTT_URL", "ARMOR_MQTT_USERNAME", "ARMOR_MQTT_PASSWORD", "ARMOR_MQTT_CA_FILE", "ARMOR_MQTT_CLIENT_ID",
                "ARMOR_ADMIN_URL", "ARMOR_ADMIN_TOKEN", "ARMOR_MAINT_TOKEN", "ARMOR_MAINT_SOCKET"):
        env.pop(key, None)
    env.update({"ARMOR_PORT": str(port), "ARMOR_HOST": "127.0.0.1", "ARMOR_DATA_DIR": str(data_dir), "HOME": str(data_dir)})
    return env


def stage_server(job: Job, release_folder: Path) -> None:
    """Start the server of the new release folder next to the running one and ask it whether it is well; the running one is not touched. Raises Refused when it is not."""
    job.step("stage", "running", 5)
    port = free_loopback_port()
    wait = staging_wait()
    with tempfile.TemporaryDirectory(prefix="armor-staging-") as scratch:
        data_dir = Path(scratch) / "data"
        data_dir.mkdir()
        log_path = Path(scratch) / "staging.log"
        extra: dict[str, object] = {}
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            extra["user"] = "armor"                                          # the same account the real server runs as, never root
            os.chmod(scratch, 0o755)
            own(data_dir, "armor")
            os.chmod(log_path.parent, 0o777)
        job.say(f"trying the new server on 127.0.0.1:{port} before switching (up to {int(wait)} s)")
        try:
            with log_path.open("wb") as log:
                process = subprocess.Popen([NODE_BINARY, str(release_folder / "server" / "dist" / "server.mjs")], cwd=release_folder / "server", env=staging_environment(data_dir, port),
                                           stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, **extra)  # type: ignore[call-overload]
        except OSError as error:
            job.say(f"the new server could not be started: {error.strerror or type(error).__name__}")
            raise Refused(500, "staging_failed") from error
        ok = False
        try:
            deadline = time.time() + wait
            while time.time() < deadline and process.poll() is None:
                try:
                    if b'"ok":true' in http_get(f"http://127.0.0.1:{port}/healthz", accept="application/json", timeout=2.0).replace(b" ", b""):
                        ok = True
                        break
                except (urllib.error.URLError, OSError, TimeoutError):
                    pass
                time.sleep(0.5)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
        if not ok:
            tail = [line for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()][-3:]
            for line in tail:
                job.say("server: " + line[:200])
            job.say("the new server did not answer: the running one stays, nothing was switched")
            raise Refused(500, "staging_failed")
    job.step("stage", "done")


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
        if (source / "package-lock.json").exists() and old_lock.exists() and lock_fingerprint(old_lock) != lock_fingerprint(source / "package-lock.json"):
            job.say("the dependencies changed: npm ci --omit=dev")
            npm_home = DATA_DIR / "npm-home"
            npm_home.mkdir(parents=True, exist_ok=True)
            # The unit runs with ProtectHome=true, so the home of root cannot be used: npm gets its own writable home and cache.
            npm_env = {**os.environ, "HOME": str(npm_home), "npm_config_cache": str(npm_home / "cache"), "npm_config_update_notifier": "false", "npm_config_fund": "false", "npm_config_audit": "false"}
            done = subprocess.run(["npm", "ci", "--omit=dev"], cwd=target / "server", capture_output=True, text=True, timeout=900, check=False, env=npm_env)
            if done.returncode != 0:
                tail = [line for line in (done.stderr or done.stdout or "").splitlines() if line.strip()][-3:]
                for line in tail:
                    job.say("npm: " + line[:200])
                raise Refused(500, "npm_failed")
    else:
        shutil.rmtree(target / "studio" / "dist", ignore_errors=True)
        shutil.copytree(source / "dist", target / "studio" / "dist")
        if (source / "tools" / "serve.mjs").exists():
            (target / "studio" / "tools").mkdir(parents=True, exist_ok=True)
            put_file(source / "tools" / "serve.mjs", target / "studio" / "tools" / "serve.mjs")
    own(target, "armor")
    job.step("install", "done")
    if part == "server":
        if staging_enabled():
            try:
                stage_server(job, target)
            except Refused:
                shutil.rmtree(target, ignore_errors=True)               # the new folder is of no use, and `current` was never touched
                raise
        else:
            job.step("stage", "skipped")
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
    prune_old(PREFIX / "releases", protect=(target, PREFIX / "current"))
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
        for name in ("armor_admin_agent.py", "armor_maintenance_agent.py", "mqtt_identity.sh", "armor_server.acl", "backup_data.sh", "armor_wireguard.sh", "armor_ddns.sh", "armor_mqtt_tls.sh", "VERSION"):
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
    prune_old(PREFIX / "releases-old", f"maint-{component}-")
    return {"backup": backup.name}


def update_job(components: list[str], force: bool) -> Job:
    steps = [(f"{component}.{part}", f"{component}: {text}") for component in components for part, text in
             (("download", "download"), ("verify", "check the hash"), ("install", "install"), *((("stage", "try it before switching"),) if component == "server" else ()),
              ("restart", "restart"), ("check", "check it works"))]
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
                        for part in ("download", "verify", "install", *(("stage",) if component == "server" else ()), "restart", "check"):
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
    if float(_ATTENTION["at"]) and _time.monotonic() - float(_ATTENTION["at"]) < 60:  # type: ignore[arg-type]
        return {"kept_back": list(_ATTENTION["kept_back"]), "broken": list(_ATTENTION["broken"])}  # type: ignore[arg-type,call-overload]
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
                command = [APT_GET, "-y", "-o", "Dpkg::Options::=--force-confold", "-o", "Dpkg::Options::=--force-confdef", "-o", f"APT::Status-Fd={write_end}", "full-upgrade" if mode == "full" else "upgrade"]
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=apt_environment(), pass_fds=(write_end,))
                os.close(write_end)

                def follow_status() -> None:
                    said = -10   # the last multiple of ten the log has said about the download
                    with os.fdopen(read_end, "r") as status:
                        for line in status:
                            parts = line.strip().split(":", 3)
                            if len(parts) == 4 and parts[0] in ("dlstatus", "pmstatus"):
                                try:
                                    percent = int(float(parts[2]))
                                except ValueError:
                                    continue
                                job.step("download" if parts[0] == "dlstatus" else "install", "running", percent)
                                if parts[0] == "dlstatus" and percent >= said + 10:
                                    said = percent - percent % 10
                                    job.say(f"downloading: {percent}%")   # the log shows the download moving, not only the first line
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
    busy = [job for job in JOBS.values() if job.state == "running"]
    if busy:
        raise Refused(409, "busy")   # a restart in the middle of an upgrade of the system leaves it half installed
    subprocess.run(["systemd-run", "--on-active=5", SYSTEMCTL, "reboot"], capture_output=True, check=False)
    return {"ok": True, "in_s": 5}


# ---- automatic security updates of the system ---------------------------------------------------------------------------------------------------
# `unattended-upgrades` limited to the security source of the distribution (nothing else: no "updates", no point releases, no Raspberry Pi archive), switched on or off and
# tuned from Studio (GET and POST /v1/system/auto-updates). The helper writes /etc/apt/apt.conf.d/52armor-security-updates from the settings and never lets the package reboot the
# machine by itself (`Automatic-Reboot "false"`): when a reboot is needed the HELPER decides, and by default it reboots only inside a window of the night AND only when the server
# says that nothing is armed (an unknown answer counts as armed). It keeps a record of what was applied (read from the log of unattended-upgrades) and, after each run, checks that
# the services of A.R.M.O.R. are still active (it restarts one that is not, once, and says so). A reboot of an alarm system that nobody asked for is a risk: docs/DEPLOYMENT_BOUNDARY.md.
AUTO_CONF_NAME = "52armor-security-updates"
APT_CONF_DIR = Path(os.environ.get("ARMOR_APT_CONF_DIR", "/etc/apt/apt.conf.d"))
UU_BIN = os.environ.get("ARMOR_UU_BIN", "/usr/bin/unattended-upgrade")
UU_LOG = Path(os.environ.get("ARMOR_UU_LOG", "/var/log/unattended-upgrades/unattended-upgrades.log"))
REBOOT_REQUIRED = Path(os.environ.get("ARMOR_REBOOT_REQUIRED", "/var/run/reboot-required"))
ARMED_URL = os.environ.get("ARMOR_MAINT_ARMED_URL", "http://127.0.0.1:18080/api/v1/maintenance/armed")
AUTO_TICK_SECONDS = 300
AUTO_REBOOT_POLICIES = ("never", "disarmed")
AUTO_DEFAULTS: dict[str, object] = {"enabled": True, "reboot": "disarmed", "window_start": "03:00", "window_end": "05:00"}
AUTO_NOW = datetime.datetime.now
TIME_OF_DAY = re.compile(r"([01][0-9]|2[0-3]):[0-5][0-9]")


def auto_state_path() -> Path:
    return DATA_DIR / "auto_security_updates.json"


def read_auto_file() -> dict[str, object]:
    try:
        data = json.loads(auto_state_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def write_auto_file(data: dict[str, object]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temporary = auto_state_path().with_suffix(".tmp")
    temporary.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
    temporary.replace(auto_state_path())


def clean_auto_settings(candidate: object) -> dict[str, object]:
    """The settings as they will be used: a value that is not valid falls back to the default (switched on, reboot only when disarmed, between 03:00 and 05:00)."""
    given = candidate if isinstance(candidate, dict) else {}
    settings = dict(AUTO_DEFAULTS)
    if isinstance(given.get("enabled"), bool):
        settings["enabled"] = given["enabled"]
    if given.get("reboot") in AUTO_REBOOT_POLICIES:
        settings["reboot"] = given["reboot"]
    for key in ("window_start", "window_end"):
        value = given.get(key)
        if isinstance(value, str) and TIME_OF_DAY.fullmatch(value):
            settings[key] = value
    return settings


def auto_settings() -> dict[str, object]:
    return clean_auto_settings(read_auto_file().get("settings"))


def render_auto_conf(settings: dict[str, object]) -> str:
    """The apt configuration that makes unattended-upgrades install security updates and nothing else, and never reboot on its own."""
    run = "1" if settings.get("enabled") else "0"
    return "\n".join([
        "// Written by the A.R.M.O.R. maintenance helper from the settings of Studio (System > Updates). Do not edit: the next change in Studio replaces it.",
        "// Security updates only. The helper, not this package, decides when the machine reboots (never while the system is armed).",
        "#clear Unattended-Upgrade::Allowed-Origins;",
        "#clear Unattended-Upgrade::Origins-Pattern;",
        "Unattended-Upgrade::Origins-Pattern {",
        '        "origin=Debian,codename=${distro_codename}-security,label=Debian-Security";',
        '        "origin=Debian,codename=${distro_codename},label=Debian-Security";',
        '        "origin=Ubuntu,archive=${distro_codename}-security,label=Ubuntu";',
        "};",
        'Unattended-Upgrade::Automatic-Reboot "false";',
        'Unattended-Upgrade::Remove-Unused-Kernel-Packages "false";',
        'Unattended-Upgrade::Remove-Unused-Dependencies "false";',
        'Unattended-Upgrade::MinimalSteps "true";',
        'APT::Periodic::Update-Package-Lists "1";',
        f'APT::Periodic::Unattended-Upgrade "{run}";',
        ""])


def write_auto_conf(settings: dict[str, object]) -> bool:
    """Writes the apt configuration; False when the folder is not there (apt is not configured the usual way) so nothing is written."""
    if not APT_CONF_DIR.is_dir():
        return False
    target = APT_CONF_DIR / AUTO_CONF_NAME
    temporary = target.with_suffix(".tmp")
    temporary.write_text(render_auto_conf(settings), encoding="utf-8")
    temporary.replace(target)
    return True


def parse_uu_log(text: str, limit: int = 20) -> list[dict[str, object]]:
    """What unattended-upgrades applied, newest first, from its log: `Packages that will be upgraded: a b c` is the list of a run, `All upgrades installed` says it finished."""
    runs: list[dict[str, object]] = []
    pending: dict[str, object] | None = None
    for line in text.splitlines():
        stamp = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
        listed = re.search(r"Packages that will be upgraded: (.*)$", line)
        if stamp and listed:
            names = [item for item in listed.group(1).split() if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.+:_-]{0,99}", item)]
            pending = {"at": stamp.group(1), "packages": names[:100], "state": "started"}
            runs.append(pending)
        elif pending is not None and "All upgrades installed" in line:
            pending["state"] = "installed"
        elif pending is not None and re.search(r"(ERROR|Installing the upgrades failed|An error occurred)", line):
            pending["state"] = "failed"
    return runs[::-1][:limit]


def armed_state() -> bool | None:
    """True or False as the server says it; None when it can not be known (then the helper behaves as if the system were armed)."""
    token = os.environ.get("ARMOR_MAINT_TOKEN", "")
    try:
        request = urllib.request.Request(ARMED_URL, headers={"X-Armor-Maint-Token": token, "User-Agent": "armor-maintenance"})
        with urllib.request.urlopen(request, timeout=5) as response:          # noqa: S310 - the address is the local server (or a test server)
            data = json.loads(response.read(4096).decode("utf-8", "replace"))
        return data["armed"] if isinstance(data.get("armed"), bool) else None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError, AttributeError):
        return None


def in_window(now: datetime.datetime, start: str, end: str) -> bool:
    """Whether the time of day is inside the window; a window that ends before it starts goes over midnight; the same time twice is the whole day."""
    minutes = now.hour * 60 + now.minute
    first, last = (int(start[:2]) * 60 + int(start[3:])), (int(end[:2]) * 60 + int(end[3:]))
    if first == last:
        return True
    return first <= minutes < last if first < last else (minutes >= first or minutes < last)


def installed_services() -> list[str]:
    return [str(COMPONENTS[key]["service"]) for key in ORDER if COMPONENTS[key].get("service") and installed_version(key)]


def unit_active(unit: str) -> bool:
    return subprocess.run([SYSTEMCTL, "is-active", unit], capture_output=True, text=True, check=False).stdout.strip() == "active"


def check_services_after_run() -> dict[str, object]:
    """After an automatic update: every installed service of A.R.M.O.R. must be active. One that is not is restarted once; what had to be restarted and what stays down is recorded."""
    down = [unit for unit in installed_services() if not unit_active(unit)]
    restarted: list[str] = []
    for unit in down:
        subprocess.run([SYSTEMCTL, "restart", unit], capture_output=True, check=False)
        restarted.append(unit)
    still = [unit for unit in down if not unit_active(unit)]
    return {"checked": int(time.time()), "ok": not still, "restarted": restarted, "down": still}


def auto_view() -> dict[str, object]:
    """What Studio shows: the settings, whether the package is there, what was applied, how the last check went and why the machine has not rebooted."""
    data = read_auto_file()
    settings = auto_settings()
    try:
        log_text = UU_LOG.read_text(encoding="utf-8", errors="replace")[-400_000:]
    except OSError:
        log_text = ""
    raw_runtime = data.get("runtime")
    runtime: dict[str, object] = raw_runtime if isinstance(raw_runtime, dict) else {}
    return {"settings": settings, "package": os.path.exists(UU_BIN), "applied": parse_uu_log(log_text, 10), "reboot_required": REBOOT_REQUIRED.exists(),
            "reboot_note": runtime.get("reboot_note", ""), "last_reboot": runtime.get("last_reboot", 0), "health": runtime.get("health", {}), "conf_written": (APT_CONF_DIR / AUTO_CONF_NAME).exists()}


def set_auto_settings(change: dict[str, object]) -> dict[str, object]:
    """A change from Studio: only the keys it names; a value that is not valid is refused (not guessed), the apt configuration is rewritten at once."""
    current = auto_settings()
    for key, value in change.items():
        if key not in AUTO_DEFAULTS:
            raise Refused(422, "unknown_setting")
        if key == "enabled" and not isinstance(value, bool):
            raise Refused(422, "bad_enabled")
        if key == "reboot" and value not in AUTO_REBOOT_POLICIES:
            raise Refused(422, "bad_reboot")
        if key in ("window_start", "window_end") and not (isinstance(value, str) and TIME_OF_DAY.fullmatch(value)):
            raise Refused(422, "bad_window")
        current[key] = value
    data = read_auto_file()
    data["settings"] = current
    write_auto_file(data)
    if not write_auto_conf(current):
        raise Refused(500, "apt_conf_unwritable")
    return auto_view()


def auto_provision() -> None:
    """At start-up: the apt configuration is written from the stored settings (the first time, from the defaults: switched on, security only), so a machine that was installed
    with the helper is covered without anybody having to open Studio. Does nothing when apt has no configuration folder."""
    try:
        write_auto_conf(auto_settings())
    except OSError as error:
        print(f"WARNING: the automatic security updates could not be configured ({error})", file=sys.stderr, flush=True)


def auto_tick() -> None:
    """One look, every few minutes: what was applied since the last one gets its services checked; a pending reboot is done only when the policy, the window and the server allow it."""
    settings = auto_settings()
    data = read_auto_file()
    raw_runtime = data.get("runtime")
    runtime: dict[str, object] = dict(raw_runtime) if isinstance(raw_runtime, dict) else {}
    if not settings["enabled"]:
        runtime["reboot_note"] = ""
        data["runtime"] = runtime
        write_auto_file(data)
        return
    try:
        newest = str(parse_uu_log(UU_LOG.read_text(encoding="utf-8", errors="replace")[-400_000:], 1)[0]["at"])
    except (OSError, IndexError):
        newest = ""
    if newest and newest != runtime.get("seen"):
        runtime["seen"] = newest
        runtime["health"] = check_services_after_run()
        if not runtime["health"]["ok"]:                                     # type: ignore[index]
            print(f"WARNING: after the automatic security updates of {newest} these services are down: {runtime['health']['down']}", file=sys.stderr, flush=True)    # type: ignore[index]
    note = ""
    if REBOOT_REQUIRED.exists():
        if settings["reboot"] == "never":
            note = "policy_never"
        elif not in_window(AUTO_NOW(), str(settings["window_start"]), str(settings["window_end"])):
            note = "outside_window"
        elif any(job.state == "running" for job in JOBS.values()):
            note = "busy"
        else:
            armed = armed_state()
            if armed is None:
                note = "armed_unknown"
            elif armed:
                note = "armed"
            else:
                try:
                    reboot_machine()
                    runtime["last_reboot"] = int(time.time())
                    note = "rebooting"
                    print("automatic security updates: rebooting because the system is disarmed and it is the window of the night", file=sys.stderr, flush=True)
                except Refused as refusal:
                    note = refusal.code
    runtime["reboot_note"] = note
    data["runtime"] = runtime
    write_auto_file(data)


def auto_loop() -> None:
    while True:
        try:
            auto_tick()
        except Exception as error:                                       # a bug here must never take the helper down
            print(f"automatic security updates: {type(error).__name__}: {error}", file=sys.stderr, flush=True)
        time.sleep(AUTO_TICK_SECONDS)


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
    return {"agent": AGENT_VERSION, "components": [component_state(key, force) for key in ORDER], "os": os_state(), "console": CONSOLE_ENABLED, "unsigned_allowed": unsigned_allowed(), "signature_mode": signature_mode(), "auto_updates": auto_view(), "trusted_fingerprints": [key_fingerprint(key) for key in trusted_keys()], "running": [item["id"] for item in running],
            "history": history()}


# ---- the way in from outside the house: the VPN and the dynamic DNS name ---------------------------------------------------------------------------------
# The two helper scripts do the work (armor_wireguard.sh, armor_ddns.sh); this is the closed door through which Studio and the phone ask for it: every value is checked here
# once more and handed over as a list of arguments, never through a shell.
WIREGUARD = PREFIX / "bin" / "armor_wireguard.sh"
DDNS = PREFIX / "bin" / "armor_ddns.sh"
# The certificate authority of the installation's own HTTPS (Caddy's `tls internal`): where its root certificate is looked for when the setting ARMOR_TLS_CA_FILE (in armor.maint.env or armor.network.env)
# does not say, from the most to the least likely. Only the public certificate is ever read; the key of the authority is never touched.
TLS_CA_CANDIDATES = (
    "/var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt",      # Caddy installed from the package
    "/root/.local/share/caddy/pki/authorities/local/root.crt",
    "/data/caddy/pki/authorities/local/root.crt",                             # the Caddy image, in its volume
)
OPENSSL = os.environ.get("ARMOR_OPENSSL", "openssl")
PEER_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$")
HOST_NAME = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9.-]{0,251}[A-Za-z0-9])?(:[0-9]{1,5})?$")
CIDR = re.compile(r"^[0-9]{1,3}(\.[0-9]{1,3}){3}/[0-9]{1,2}$")
IFACE_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,15}$")


def tls_ca_file() -> Path | None:
    """The root certificate of the installation's authority: the setting when it names a file, else the first of the usual places that exists."""
    def usable(path: Path) -> bool:
        try:
            return path.is_file()
        except OSError:       # a folder this user may not enter is not a place where the file is
            return False
    for settings in (MAINT_ENV, PREFIX / "etc" / "armor.network.env"):
        named = read_settings(settings).get("ARMOR_TLS_CA_FILE", "")
        if named and Path(named).is_absolute() and usable(Path(named)):
            return Path(named)
    for guess in TLS_CA_CANDIDATES:
        if usable(Path(guess)):
            return Path(guess)
    try:
        found = sorted(Path("/var/lib/docker/volumes").glob("*proxy-data*/_data/caddy/pki/authorities/local/root.crt"))
    except OSError:
        found = []
    return found[0] if found else None


def tls_ca_info() -> dict[str, object]:
    """The pin of the authority's public key (SHA-256 of its SubjectPublicKeyInfo, base64: what the phone pins), its name and the day it ends. Nothing secret is in it."""
    path = tls_ca_file()
    if path is None:
        return {"present": False}
    try:
        text = subprocess.run([OPENSSL, "x509", "-in", str(path), "-noout", "-subject", "-enddate"], capture_output=True, text=True, timeout=15, check=False)
        key = subprocess.run([OPENSSL, "x509", "-in", str(path), "-noout", "-pubkey"], capture_output=True, text=True, timeout=15, check=False)
        der = subprocess.run([OPENSSL, "pkey", "-pubin", "-outform", "DER"], input=key.stdout.encode("utf-8"), capture_output=True, timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return {"present": True, "error": "openssl_failed"}
    if text.returncode != 0 or key.returncode != 0 or der.returncode != 0 or not der.stdout:
        return {"present": True, "error": "unreadable_certificate"}
    fields = dict(line.split("=", 1) for line in text.stdout.splitlines() if "=" in line)
    return {"present": True, "pin": base64.b64encode(hashlib.sha256(der.stdout).digest()).decode("ascii"), "subject": fields.get("subject", "").strip()[:200], "not_after": fields.get("notAfter", "").strip()[:40]}


def read_settings(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator and re.fullmatch(r"[A-Z_]+", key):
                values[key] = value.strip().strip("'")
    except OSError:
        pass
    return values


def run_helper(script: Path, arguments: list[str], timeout: float = 90.0) -> subprocess.CompletedProcess[str]:
    if not script.is_file():
        raise Refused(501, "helper_missing")
    return subprocess.run(["bash", str(script), *arguments, "--prefix", str(PREFIX)], capture_output=True, text=True, timeout=timeout, check=False)


def helper_failed(result: subprocess.CompletedProcess[str]) -> Refused:
    # the scripts say what was wrong in one line of English; nothing else (never a key or a token) is passed on
    line = next((item for item in reversed((result.stderr or "").strip().splitlines()) if item.strip()), "")
    reason = re.sub(r"^armor_(wireguard|ddns): ", "", line)[:300]
    return Refused(422 if result.returncode == 2 else 502, reason or "failed")


def remote_state() -> dict[str, object]:
    state_dir = PREFIX / "etc" / "wireguard"
    settings = read_settings(state_dir / "settings")
    peers: list[dict[str, str]] = []
    folder = state_dir / "peers"
    if folder.is_dir():
        for item in sorted(folder.glob("*.env")):
            values = read_settings(item)
            if values.get("NAME") and values.get("ADDRESS"):
                peers.append({"name": values["NAME"], "address": values["ADDRESS"], "full_tunnel": "yes" if values.get("FULL_TUNNEL") == "1" else "no"})
    running = False
    if settings:
        running = systemctl("is-active", "wg-quick@armor-wg0", timeout=10).stdout.strip() == "active"
    ddns = read_settings(Path(os.environ.get("ARMOR_DDNS_ENV", str(PREFIX / "etc" / "armor.ddns.env"))))
    last = ""
    try:
        last = (PREFIX / "data" / "ddns.last").read_text(encoding="utf-8").strip()
    except OSError:
        pass
    wireguard: dict[str, object] = {"tool": shutil.which("wg") is not None, "script": WIREGUARD.is_file(), "configured": bool(settings), "running": running, "qr": shutil.which("qrencode") is not None, "peers": peers}
    if settings:
        wireguard.update({"endpoint": f"{settings.get('ENDPOINT_HOST', '')}:{settings.get('PORT_PUBLIC', '')}", "subnet": settings.get("SUBNET", ""), "port": settings.get("PORT", ""), "lan": settings.get("LAN", ""), "route_lan": settings.get("ROUTE_LAN", "")})
    dynamic: dict[str, object] = {"script": DDNS.is_file(), "configured": bool(ddns.get("PROVIDER"))}
    if ddns.get("PROVIDER"):
        dynamic.update({"provider": ddns.get("PROVIDER", ""), "name": ddns.get("DOMAIN") or ddns.get("RECORD") or "", "last_address": last})
    return {"wireguard": wireguard, "ddns": dynamic}


def wireguard_setup(data: dict[str, object]) -> dict[str, object]:
    endpoint = data.get("endpoint")
    if not isinstance(endpoint, str) or not HOST_NAME.fullmatch(endpoint):
        raise Refused(422, "bad_endpoint")
    arguments = ["setup", "--endpoint", endpoint]
    for key, flag, pattern in (("lan", "--lan", CIDR), ("subnet", "--subnet", CIDR), ("route_lan", "--route-lan", IFACE_NAME)):
        value = data.get(key)
        if value in (None, ""):
            continue
        if not isinstance(value, str) or not pattern.fullmatch(value):
            raise Refused(422, f"bad_{key}")
        arguments += [flag, value]
    port = data.get("port")
    if port not in (None, ""):
        if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
            raise Refused(422, "bad_port")
        arguments += ["--port", str(port)]
    result = run_helper(WIREGUARD, arguments)
    if result.returncode != 0:
        raise helper_failed(result)
    return {"ok": True, **remote_state()}


def peer_config(name: str) -> dict[str, object]:
    result = run_helper(WIREGUARD, ["show", name])
    if result.returncode != 0:
        raise helper_failed(result)
    match = re.search(r"^----[^\n]*----\n(.*?)\n----\n", result.stdout, re.S | re.M)
    if not match:
        raise Refused(502, "no_configuration")
    config = match.group(1)
    svg = ""
    if shutil.which("qrencode"):
        picture = subprocess.run(["qrencode", "-t", "SVG", "-o", "-"], input=config, capture_output=True, text=True, timeout=15, check=False)
        if picture.returncode == 0 and ("<svg" in picture.stdout[:400]):
            svg = picture.stdout
    return {"name": name, "config": config, "qr_svg": svg or None}


def ddns_setup(data: dict[str, object]) -> dict[str, object]:
    provider = data.get("provider")
    if provider not in ("duckdns", "cloudflare", "url"):
        raise Refused(422, "bad_provider")
    arguments = ["setup", "--provider", str(provider)]
    for key, flag in (("domain", "--domain"), ("token", "--token"), ("zone", "--zone"), ("record_name", "--record-name"), ("url", "--url")):
        value = data.get(key)
        if value in (None, ""):
            continue
        if not isinstance(value, str) or len(value) > 1000 or any(character in value for character in "\r\n\0"):
            raise Refused(422, f"bad_{key}")
        arguments += [flag, value]
    result = run_helper(DDNS, arguments, timeout=60)
    if result.returncode != 0:
        raise helper_failed(result)
    return {"ok": True, **remote_state()}


# ---- Who may change the sensitive settings: the user of the caller (SO_PEERCRED) and a one-time code (TOTP) ------------------------------------------------------------------
# The socket is open to the group `armor` and wants the token, which every service of that group could read. For what changes the machine (the console, the reboot, the system
# upgrade, the automatic updates, the remote access) two more checks can be switched on, each by what the administrator writes in armor.maint.env, and both are off until then so
# nothing is locked out by an update of this file:
#   ARMOR_MAINT_PEER_UIDS=998,0   the user numbers the kernel reports for the process on the other end of the socket (SO_PEERCRED); any other user is refused (403 peer_not_allowed)
#   ARMOR_MAINT_TOTP_FILE=...     the file with the base32 secret of the administrator's authenticator (made by `--totp-enroll`, mode 0600); when it exists, a sensitive call
#                                 must bring a current six-digit code in X-Armor-Maint-Totp (401 totp_required / totp_invalid); a code is good once (no replay)
SENSITIVE_ROUTES = {
    ("POST", ("console", "run")), ("POST", ("system", "reboot")), ("POST", ("system", "upgrade")), ("POST", ("system", "auto-updates")),
    ("POST", ("remote", "wireguard", "setup")), ("POST", ("remote", "ddns", "setup")),
}
TOTP_STEP_S = 30
TOTP_WINDOW = 1            # steps either side of now, for a clock that is a little off
_totp_last_counter = [0]
_totp_lock = threading.Lock()


def peer_uids() -> list[int] | None:
    """The user numbers allowed to make sensitive calls (ARMOR_MAINT_PEER_UIDS, comma separated); None when the check is off."""
    text = os.environ.get("ARMOR_MAINT_PEER_UIDS", "").strip()
    if not text:
        return None
    return [int(item) for item in text.split(",") if item.strip().isdigit()]


def peer_credentials(connection: object) -> tuple[int, int, int] | None:
    """(pid, uid, gid) of the process on the other end of a Unix socket, as the kernel says; None where the system cannot say."""
    option = getattr(socket, "SO_PEERCRED", None)
    getsockopt = getattr(connection, "getsockopt", None)
    if option is None or getsockopt is None:
        return None
    try:
        pid, uid, gid = struct.unpack("3i", getsockopt(socket.SOL_SOCKET, option, struct.calcsize("3i")))
    except (OSError, struct.error):
        return None
    return pid, uid, gid


def totp_file() -> Path:
    return Path(os.environ.get("ARMOR_MAINT_TOTP_FILE", str(PREFIX / "etc" / "maint.totp")))


def totp_code(secret_base32: str, counter: int, digits: int = 6) -> str:
    """The code of RFC 6238 (HMAC-SHA1) for one time step."""
    key = base64.b32decode(secret_base32.strip().replace(" ", "").upper() + "=" * (-len(secret_base32.strip().replace(" ", "")) % 8))
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
    return str(value).zfill(digits)


def totp_accepts(secret_base32: str, code: str, now: float | None = None) -> bool:
    """Whether `code` is the code of the current step or one next to it, and has not been used. A good code is spent."""
    if not (isinstance(code, str) and len(code) == 6 and code.isdigit()):
        return False
    counter = int((time.time() if now is None else now) // TOTP_STEP_S)
    with _totp_lock:
        for step in range(counter - TOTP_WINDOW, counter + TOTP_WINDOW + 1):
            if step > _totp_last_counter[0] and hmac.compare_digest(totp_code(secret_base32, step), code):
                _totp_last_counter[0] = step
                return True
    return False


def totp_enroll() -> str:
    """Makes the secret of the authenticator (20 random bytes, base32), writes it with mode 0600 and gives it back to be shown once to the administrator."""
    secret = base64.b32encode(os.urandom(20)).decode("ascii")
    path = totp_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="ascii") as handle:
        handle.write(secret + chr(10))
    return secret


def guard_sensitive(method: str, parts: list[str], credentials: tuple[int, int, int] | None, code: str) -> None:
    """Refuses a sensitive call that does not come from an allowed user or without a current code, when those checks are on; does nothing for any other call."""
    if (method, tuple(parts)) not in SENSITIVE_ROUTES:
        return
    allowed = peer_uids()
    if allowed is not None and (credentials is None or credentials[1] not in allowed):
        raise Refused(403, "peer_not_allowed")
    path = totp_file()
    if path.is_file():
        if not code:
            raise Refused(401, "totp_required")
        if not totp_accepts(path.read_text(encoding="ascii").strip(), code):
            raise Refused(401, "totp_invalid")


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
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise Refused(400, "bad_length") from None
        if length < 0:
            raise Refused(400, "bad_length")
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
            guard_sensitive(method, parts, peer_credentials(self.request), self.headers.get("X-Armor-Maint-Totp", ""))
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
            elif method == "GET" and parts == ["system", "auto-updates"]:
                self.reply(200, auto_view())
            elif method == "POST" and parts == ["system", "auto-updates"]:
                self.reply(200, set_auto_settings(self.body()))
            elif method == "POST" and parts == ["history", "clear"]:
                self.reply(200, {"ok": True, "cleared": clear_history()})
            elif method == "GET" and len(parts) == 2 and parts[0] == "jobs":
                job = JOBS.get(parts[1])
                if not job:
                    raise Refused(404, "no_such_job")
                self.reply(200, job.view(int(arguments.get("since", "0") or 0)))
            elif method == "POST" and parts == ["console", "run"]:
                data = self.body()
                self.reply(202, console_run(str(data.get("command", "")), str(data.get("cwd", "/root")), float(data.get("timeout", 120) or 120)))  # type: ignore[arg-type]
            elif method == "GET" and len(parts) == 3 and parts[:2] == ["console", "jobs"]:
                console_job = CONSOLE_JOBS.get(parts[2])
                if not console_job:
                    raise Refused(404, "no_such_job")
                self.reply(200, console_job.view(int(arguments.get("since", "0") or 0)))
            elif method == "POST" and len(parts) == 4 and parts[:2] == ["console", "jobs"] and parts[3] == "cancel":
                console_job = CONSOLE_JOBS.get(parts[2])
                if not console_job:
                    raise Refused(404, "no_such_job")
                console_job.cancel()
                self.reply(200, {"ok": True})
            elif method == "GET" and parts == ["remote"]:
                self.reply(200, remote_state())
            elif method == "GET" and parts == ["tls", "ca"]:
                self.reply(200, tls_ca_info())
            elif method == "POST" and parts == ["remote", "wireguard", "setup"]:
                self.reply(200, wireguard_setup(self.body()))
            elif method == "POST" and parts == ["remote", "wireguard", "peers"]:
                data = self.body()
                name = data.get("name")
                if not isinstance(name, str) or not PEER_NAME.fullmatch(name):
                    raise Refused(422, "bad_name")
                result = run_helper(WIREGUARD, ["add-peer", name] + (["--full-tunnel"] if data.get("full_tunnel") is True else []))
                if result.returncode != 0:
                    raise helper_failed(result)
                self.reply(201, peer_config(name))
            elif method == "GET" and len(parts) == 4 and parts[:3] == ["remote", "wireguard", "peers"]:
                if not PEER_NAME.fullmatch(parts[3]):
                    raise Refused(422, "bad_name")
                self.reply(200, peer_config(parts[3]))
            elif method == "POST" and len(parts) == 5 and parts[:3] == ["remote", "wireguard", "peers"] and parts[4] == "remove":
                if not PEER_NAME.fullmatch(parts[3]):
                    raise Refused(422, "bad_name")
                result = run_helper(WIREGUARD, ["remove-peer", parts[3]])
                if result.returncode != 0:
                    raise helper_failed(result)
                self.reply(200, {"ok": True})
            elif method == "POST" and parts == ["remote", "ddns", "setup"]:
                self.reply(200, ddns_setup(self.body()))
            elif method == "POST" and parts == ["remote", "ddns", "update"]:
                result = run_helper(DDNS, ["update", "--force"], timeout=60)
                if result.returncode != 0:
                    raise helper_failed(result)
                self.reply(200, {"ok": True, **remote_state()})
            elif method == "POST" and parts == ["remote", "ddns", "remove"]:
                result = run_helper(DDNS, ["remove"], timeout=60)
                if result.returncode != 0:
                    raise helper_failed(result)
                self.reply(200, {"ok": True, **remote_state()})
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
    auto_provision()
    threading.Thread(target=auto_loop, daemon=True).start()
    try:
        server.serve_forever()
    finally:
        server.server_close()
        path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Maintenance helper of A.R.M.O.R. Studio: updates from GitHub, the system's updates and the root console")
    parser.add_argument("--socket", default="/run/armor-maint.sock")
    parser.add_argument("--group", default="armor", help="the group allowed to open the socket")
    parser.add_argument("--totp-enroll", action="store_true", help="make the secret of the administrator's authenticator (written with mode 0600), show it once and exit")
    arguments = parser.parse_args()
    if arguments.totp_enroll:
        print(totp_enroll())
        return 0
    token = os.environ.get("ARMOR_MAINT_TOKEN", "")
    if len(token) < 24:
        print("ARMOR_MAINT_TOKEN must be set (at least 24 characters)", file=sys.stderr)
        return 2
    serve(arguments.socket, token, arguments.group)
    return 0


if __name__ == "__main__":
    sys.exit(main())
