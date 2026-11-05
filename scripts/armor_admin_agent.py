#!/usr/bin/env python3
# =============================================================================
# A.R.M.O.R. - ARMOR-DEVOPS/scripts/armor_admin_agent.py
# The one small program on the machine that is allowed to do the few privileged things Studio needs: start, stop and restart the A.R.M.O.R.
# services, edit their configuration files, and add or remove the accounts of the A.R.M.O.R. MQTT broker.
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D)
# GPL-3.0-or-later - see LICENSE
# =============================================================================
# Why it exists: the A.R.M.O.R. server runs as the unprivileged user `armor`, with NoNewPrivileges and a read-only system, on purpose - it has no sudo and
# must not get any. Studio (for an administrator) still has to be able to restart a service or add the account of a new node, so the privileged part lives
# here, apart, with a closed list of what it can touch:
#   * only the units in SERVICES, with only start / stop / restart / reload;
#   * only the files in FILES, each at its own fixed path (a client never sends a path), with a size limit, a format check and a copy kept of the old one;
#   * only the broker accounts that mqtt_identity.sh knows how to make (it does the work, as it always did), never the password file itself.
# It listens on a Unix socket that only the group `armor` can open, and also wants a token (ARMOR_ADMIN_TOKEN, from a file only root and that group read).
# Writing the broker rules and the .env files is the most powerful thing it does, so it can be locked with ARMOR_ADMIN_SENSITIVE (open = as always, the
# default; second_token = a second, different secret is also needed; read_only = never from a request).
# It uses nothing but the Python standard library.
#
#   armor_admin_agent.py --socket /run/armor-admin.sock        # as root, by the systemd unit armor-admin.service
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import http.server
import json
import os
import re
import socketserver
import struct
import subprocess
import sys
import threading
import tempfile
import time
from pathlib import Path

PREFIX = Path(os.environ.get("ARMOR_PREFIX", "/opt/armor"))
SYSTEMCTL = os.environ.get("ARMOR_SYSTEMCTL", "systemctl")
SCRIPT_DIR = Path(__file__).resolve().parent
IDENTITY_SCRIPT = Path(os.environ.get("ARMOR_MQTT_IDENTITY", str(SCRIPT_DIR / "mqtt_identity.sh")))
MAX_FILE_BYTES = 64 * 1024
KEEP_BACKUPS = 5

# id -> (unit, what it is). More can be added with ARMOR_ADMIN_EXTRA_SERVICES="id=unit,id2=unit2" but never from a request.
SERVICES: dict[str, tuple[str, str]] = {
    "server": ("armor-server", "The A.R.M.O.R. server: sensors, alarms, cameras, history"),
    "studio": ("armor-studio", "Studio: the console you are looking at"),
    "mosquitto": ("armor-mosquitto", "The MQTT broker the nodes and the server talk through"),
    "network": ("armor-network", "The network watcher of this machine"),
    "ai": ("armor-server-ai", "The observation service: movement on the cameras, weighed with the radars (it recommends, the server decides)"),
    "voice": ("armor-voice", "The voice gateway: written and spoken commands (a closed list of fifteen)"),
}
for pair in filter(None, os.environ.get("ARMOR_ADMIN_EXTRA_SERVICES", "").split(",")):
    key, _, unit = pair.partition("=")
    if re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,31}", key) and re.fullmatch(r"[A-Za-z0-9@_.-]{1,64}", unit):
        SERVICES[key] = (unit, "Extra service")
ACTIONS = {"start": ["start"], "stop": ["stop"], "restart": ["restart"], "reload": ["reload-or-restart"]}
# Pausing freezes the main process with SIGSTOP and resuming lets it go on with SIGCONT: nothing is lost, it just stops answering. The server and Studio
# cannot be paused - a paused console cannot be used to resume itself.
ACTIONS["pause"] = ["kill", "--signal=SIGSTOP", "--kill-whom=main"]
ACTIONS["resume"] = ["kill", "--signal=SIGCONT", "--kill-whom=main"]
NEVER_PAUSE = {"server", "studio"}
# Stopping or restarting the server cuts the request that asked for it: do not wait for the answer.
NO_BLOCK = {"armor-server", "armor-studio"}

# id -> (path relative to the prefix, format, the units to restart afterwards, what it is)
FILES: dict[str, tuple[str, str, tuple[str, ...], str]] = {
    "server.env": ("etc/armor.env", "env", ("server",), "Server settings: logins, tokens, ports, which addresses may log in"),
    "mqtt.env": ("etc/armor.mqtt.env", "env", ("server",), "How the server logs in to the MQTT broker"),
    "network.env": ("etc/armor.network.env", "env", ("server", "studio", "network"), "Shared by the server, Studio and the network watcher: addresses and TLS"),
    "reach.txt": ("etc/armor.reach", "reach", ("server", "studio"), "Other addresses the console may be opened from: one pair per line, the Studio address = the server address"),
    "mosquitto.conf": ("etc/mosquitto/mosquitto.conf", "conf", ("mosquitto",), "MQTT broker: port, authentication, storage and log"),
    "mosquitto.acl": ("etc/mosquitto/acl", "acl", ("mosquitto",), "MQTT broker: who may read and write which topic"),
}
SECRET_KEY = re.compile(r"(PASSWORD|SECRET|TOKEN|KEY|PASS)", re.IGNORECASE)
# What a compromised server must not be able to rewrite on its own: the broker rules and the .env files (and, because it edits the rules, the broker accounts).
SENSITIVE_MODES = ("open", "second_token", "read_only")
SENSITIVE_HEADER = "X-Armor-Admin-Sensitive-Token"
MIN_SECRET = 24


def is_sensitive_file(file_id: str) -> bool:
    return file_id in FILES and FILES[file_id][1] in ("env", "acl")


class Sensitive:
    """How writes to the broker rules and the .env files are protected. Set at start-up from the environment, never from a request."""
    mode = "open"
    token = ""


def configure_sensitive(mode: str, token: str, main_token: str = "") -> str | None:
    """Sets the protection; returns the reason it is unusable (None when fine). An unknown mode or a bad second secret never falls back to open."""
    if mode not in SENSITIVE_MODES:
        return "unknown_mode"
    if mode == "second_token" and (len(token) < MIN_SECRET or hmac.compare_digest(token.encode(), main_token.encode())):
        return "second_token_missing_or_equal"
    Sensitive.mode, Sensitive.token = mode, token if mode == "second_token" else ""
    return None


def sensitive_status() -> dict[str, object]:
    return {"mode": Sensitive.mode, "protected": Sensitive.mode != "open", "files": [key for key in FILES if is_sensitive_file(key)],
            "warning": "open" if Sensitive.mode == "open" else ""}


def require_sensitive(given: str) -> None:
    if Sensitive.mode == "read_only":
        raise Refused(403, "sensitive_read_only")
    if Sensitive.mode == "second_token" and not (Sensitive.token and hmac.compare_digest(given.encode(), Sensitive.token.encode())):
        raise Refused(403, "sensitive_token_required")


ROLES = {"node", "solar-node", "electrical-node", "network-node", "alarm-node", "consumer", "device", "bridge"}
NAME = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")
USER = re.compile(r"(field-node|solar-node|electrical-node|network-node|alarm-node|alarm|device|bridge)-[a-z0-9][a-z0-9_-]{0,63}")


class Refused(Exception):
    def __init__(self, status: int, code: str) -> None:
        super().__init__(code)
        self.status, self.code = status, code


def run(command: list[str], timeout: float = 30.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)


# ---- services -----------------------------------------------------------------------------------------------------------------------------------

def is_stopped_by_signal(pid: int) -> bool:
    """True when the process is frozen (state T in /proc/<pid>/stat): a paused service is still "active" for systemd."""
    if pid <= 0:
        return False
    try:
        text = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return text[text.rfind(")") + 2:text.rfind(")") + 3] == "T"


def service_state(service_id: str) -> dict[str, object]:
    unit, description = SERVICES[service_id]
    shown = run([SYSTEMCTL, "show", unit, "--no-pager", "--property=LoadState,ActiveState,SubState,UnitFileState,MainPID,ActiveEnterTimestamp"])
    fields = dict(line.split("=", 1) for line in shown.stdout.splitlines() if "=" in line)
    pid = int(fields.get("MainPID", "0") or 0)
    return {
        "id": service_id, "unit": unit, "description": description,
        "installed": fields.get("LoadState", "not-found") != "not-found",
        "active": fields.get("ActiveState", "unknown"), "sub": fields.get("SubState", ""),
        "enabled": fields.get("UnitFileState", ""), "pid": pid, "since": fields.get("ActiveEnterTimestamp", ""), "paused": is_stopped_by_signal(pid),
    }


def service_action(service_id: str, action: str) -> dict[str, object]:
    if service_id not in SERVICES:
        raise Refused(404, "unknown_service")
    if action not in ACTIONS:
        raise Refused(422, "unknown_action")
    if action == "pause" and service_id in NEVER_PAUSE:
        raise Refused(422, "cannot_pause")
    unit = SERVICES[service_id][0]
    command = [SYSTEMCTL] + (["--no-block"] if unit in NO_BLOCK and action != "start" else []) + ACTIONS[action] + [unit]
    done = run(command, timeout=60.0)
    if done.returncode != 0:
        raise Refused(502, "systemctl_failed")
    return {"ok": True, "service": service_id, "action": action}


# ---- hiding the secrets of the .env files -------------------------------------------------------------------------------------------------------
# What this agent returns of an .env file never holds a secret: the value of every secret key is replaced by a mask, and an address that carries a
# login (mqtt://user:secret@host, https://host/hook?token=...) loses its secret. When the file is saved with a mask where a secret was, the value it had
# is put back from the file on disk, so the server and the console never hold the originals. The same rules and vectors as ARMOR-COMMON's
# env_masking.json (scripts/test_admin_agent.py compares them with the copy in scripts/env_masking.json).
ENV_MASK = "********"
ENV_SECRET_KEY = re.compile(r"(PASSWORD|SECRET|TOKEN|KEY|PASS|WEBHOOK_ID)", re.IGNORECASE)
ENV_LINE = re.compile(r"^(\s*)([A-Za-z_][A-Za-z0-9_]*)=(.*?)(\r?)$")
ENV_LOGIN = re.compile(r"(://[^/\s:@]+:)[^@/\s]+@")
ENV_LOGIN_EDITED = re.compile(r"(://[^/\s:@]+:)\*\*\*@")
ENV_LOGIN_PASSWORD = re.compile(r"://[^/\s:@]+:([^@/\s]+)@")
ENV_QUERY = re.compile(r"([?&](?:token|key|secret|password|pass)=)[^&\s]+", re.IGNORECASE)
ENV_QUERY_EDITED = re.compile(r"([?&])(token|key|secret|password|pass)=\*\*\*", re.IGNORECASE)


def hide_login(value: str) -> str:
    return ENV_QUERY.sub(lambda m: m.group(1) + "***", ENV_LOGIN.sub(lambda m: m.group(1) + "***@", value, count=1))


def restore_login(edited: str, before: str) -> str:
    found = ENV_LOGIN_PASSWORD.search(before)
    out = edited
    if found is not None:
        password = found.group(1)
        out = ENV_LOGIN_EDITED.sub(lambda m: m.group(1) + password + "@", out, count=1)

    def query(match: "re.Match[str]") -> str:
        original = re.search(r"[?&]" + re.escape(match.group(2)) + r"=([^&\s]+)", before, re.IGNORECASE)
        return match.group(0) if original is None else match.group(1) + match.group(2) + "=" + original.group(1)

    return ENV_QUERY_EDITED.sub(query, out)


def mask_env(content: str) -> str:
    out = []
    for line in content.split("\n"):
        match = ENV_LINE.match(line)
        if match is None or match.group(3) == "":
            out.append(line)
        elif ENV_SECRET_KEY.search(match.group(2)):
            out.append(f"{match.group(1)}{match.group(2)}={ENV_MASK}{match.group(4)}")
        else:
            hidden = hide_login(match.group(3))
            out.append(line if hidden == match.group(3) else f"{match.group(1)}{match.group(2)}={hidden}{match.group(4)}")
    return "\n".join(out)


def unmask_env(edited: str, current: str) -> dict[str, str]:
    """The edited text with every hidden value given back the value it had, or ``{"missing": KEY}`` for a mask whose key is not in the file any more."""
    known: dict[str, str] = {}
    for line in current.split("\n"):
        match = ENV_LINE.match(line)
        if match:
            known[match.group(2)] = match.group(3)
    missing = ""
    out = []
    for line in edited.split("\n"):
        match = ENV_LINE.match(line)
        if match is None:
            out.append(line)
            continue
        lead, key, value, ending = match.groups()
        before = known.get(key)
        if value != ENV_MASK and before is not None and hide_login(before) != before and "***" in value:
            out.append(f"{lead}{key}={restore_login(value, before)}{ending}")
        elif value != ENV_MASK:
            out.append(line)
        elif before is None:
            missing = key
            out.append(line)
        else:
            out.append(f"{lead}{key}={before}{ending}")
    return {"missing": missing} if missing else {"content": "\n".join(out)}


# ---- files --------------------------------------------------------------------------------------------------------------------------------------

def file_path(file_id: str) -> Path:
    if file_id not in FILES:
        raise Refused(404, "unknown_file")
    return PREFIX / FILES[file_id][0]


def check_content(fmt: str, content: str) -> None:
    raw = content.encode("utf-8")
    if len(raw) > MAX_FILE_BYTES:
        raise Refused(413, "file_too_large")
    if "\x00" in content:
        raise Refused(422, "invalid_content")
    for number, line in enumerate(content.splitlines(), start=1):
        if len(line) > 1024:
            raise Refused(422, f"line_too_long:{number}")
        text = line.strip()
        if text == "" or text.startswith("#"):
            continue
        if fmt == "env" and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", text):
            raise Refused(422, f"invalid_line:{number}")
        if fmt == "acl" and not re.match(r"(user|topic|pattern)\s", text):
            raise Refused(422, f"invalid_line:{number}")
        if fmt == "reach" and not re.fullmatch(r"https?://[A-Za-z0-9.-]+(:[0-9]{1,5})?=https?://[A-Za-z0-9.-]+(:[0-9]{1,5})?", text):
            raise Refused(422, f"invalid_line:{number}")
        if fmt == "conf" and not re.match(r"[A-Za-z_][A-Za-z0-9_]*(\s|$)", text):
            raise Refused(422, f"invalid_line:{number}")


def read_file(file_id: str) -> dict[str, object]:
    path = file_path(file_id)
    _, fmt, units, description = FILES[file_id]
    try:
        content = path.read_text(encoding="utf-8")
        mtime = path.stat().st_mtime
    except FileNotFoundError:
        return {"id": file_id, "path": str(path), "format": fmt, "description": description, "units": list(units), "exists": False, "content": "", "mtime": 0}
    answer: dict[str, object] = {"id": file_id, "path": str(path), "format": fmt, "description": description, "units": list(units), "exists": True, "content": content, "mtime": mtime}
    if fmt == "env":        # the secrets never leave this program; a save with a mask where one was gets the value back below
        answer["content"] = mask_env(content)
        answer["masked"] = True
    return answer


def write_file(file_id: str, content: str, expect_mtime: float | None) -> dict[str, object]:
    path = file_path(file_id)
    fmt = FILES[file_id][1]
    existing = path.exists()
    if fmt == "env" and ENV_MASK in content:
        given = unmask_env(content, path.read_text(encoding="utf-8") if existing else "")
        if "missing" in given:
            raise Refused(422, f"masked_value_without_original:{given['missing']}")
        content = given["content"]
    check_content(fmt, content)
    if existing and expect_mtime is not None and abs(path.stat().st_mtime - expect_mtime) > 0.5:
        raise Refused(409, "file_changed")      # somebody else wrote it since it was read
    path.parent.mkdir(parents=True, exist_ok=True)
    if existing:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        backup = path.with_name(f"{path.name}.bak-{stamp}")
        backup.write_bytes(path.read_bytes())
        os.chmod(backup, 0o600)
        old = sorted(path.parent.glob(f"{path.name}.bak-*"))
        for stale in old[:-KEEP_BACKUPS]:
            stale.unlink(missing_ok=True)
        info = path.stat()
        owner, group, mode = info.st_uid, info.st_gid, info.st_mode & 0o7777
    else:
        owner, group, mode = os.getuid(), os.getgid(), 0o640
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="") as stream:
            stream.write(content)
        if hasattr(os, "chown"):
            try:
                os.chown(temporary, owner, group)
            except PermissionError:
                pass
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return {"ok": True, "id": file_id, "mtime": path.stat().st_mtime}


# ---- the broker's accounts ----------------------------------------------------------------------------------------------------------------------

def parse_accounts(acl_text: str) -> list[dict[str, object]]:
    accounts: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for line in acl_text.splitlines():
        text = line.strip()
        if text.startswith("user "):
            current = {"user": text[5:].strip(), "topics": []}
            accounts.append(current)
        elif text == "":
            current = None
        elif current is not None and text.startswith(("topic ", "pattern ")):
            cast = current["topics"]
            assert isinstance(cast, list)
            cast.append(text)
    for account in accounts:
        user = str(account["user"])
        match = USER.fullmatch(user)
        account["role"] = match.group(1) if match else "other"
        account["manageable"] = bool(match)
        account["name"] = user[len(match.group(1)) + 1:] if match else user
    return accounts


def list_accounts() -> dict[str, object]:
    acl = PREFIX / "etc/mosquitto/acl"
    try:
        return {"accounts": parse_accounts(acl.read_text(encoding="utf-8"))}
    except FileNotFoundError:
        return {"accounts": [], "installed": False}


def identity(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ, ARMOR_PREFIX=str(PREFIX))
    return subprocess.run(["bash", str(IDENTITY_SCRIPT), *arguments], capture_output=True, text=True, timeout=60, check=False, env=environment)


def add_account(role: str, name: str, rotate: bool = False) -> dict[str, object]:
    """A new identity, or with `rotate` a new password for one that exists (one step: the old password works until the new one is written, and the ACL is not touched)."""
    if role not in ROLES:
        raise Refused(422, "unknown_role")
    if not NAME.fullmatch(name):
        raise Refused(422, "invalid_name")
    done = identity(["rotate" if rotate else "add", role, name])
    if done.returncode != 0:
        message = (done.stderr or done.stdout).strip().splitlines()[-1:] or [""]
        raise Refused(409 if "already exists" in message[0] else 502, "identity_failed")
    values = dict(line.split(": ", 1) for line in done.stdout.splitlines() if ": " in line)
    return {"ok": True, "user": values.get("user", ""), "password": values.get("password", "")}


def remove_account(user: str) -> dict[str, object]:
    if not USER.fullmatch(user):
        raise Refused(422, "invalid_user")
    done = identity(["remove", user])
    if done.returncode != 0:
        raise Refused(502, "identity_failed")
    return {"ok": True, "user": user}


# ---- local approval: the one-time code of the administrator's authenticator ----------------------------------------------------------------------
# Changing the broker rules from here (the ACL file, and the two switches below) can need a six-digit code of RFC 6238 (TOTP). The secret is the file of the maintenance
# agent (ARMOR_MAINT_TOTP_FILE, default etc/maint.totp, made by `armor_maintenance_agent.py --totp-enroll`), so the administrator has one authenticator for both. While that
# file does not exist the check is off for the ACL file (nothing is locked out by an update of this program); the two switches are new and refuse to work until it exists.
# A code is good once in this program (it is not shared with the maintenance agent: a code spent there can be tried here inside its 90 seconds).
TOTP_HEADER = "X-Armor-Maint-Totp"
TOTP_STEP_S = 30
TOTP_WINDOW = 1
_totp_last_counter = [0]
_totp_lock = threading.Lock()


def totp_file() -> Path:
    return Path(os.environ.get("ARMOR_MAINT_TOTP_FILE", str(PREFIX / "etc" / "maint.totp")))


def totp_code(secret_base32: str, counter: int, digits: int = 6) -> str:
    """The code of RFC 6238 (HMAC-SHA1) for one time step."""
    text = secret_base32.strip().replace(" ", "").upper()
    key = base64.b32decode(text + "=" * (-len(text) % 8))
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    return str((struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % (10 ** digits)).zfill(digits)


def totp_accepts(secret_base32: str, code: str, now: float | None = None) -> bool:
    """Whether `code` is the code of the current step or one next to it and has not been used. A good code is spent."""
    if not (isinstance(code, str) and len(code) == 6 and code.isdigit()):
        return False
    counter = int((time.time() if now is None else now) // TOTP_STEP_S)
    with _totp_lock:
        for step in range(counter - TOTP_WINDOW, counter + TOTP_WINDOW + 1):
            if step > _totp_last_counter[0] and hmac.compare_digest(totp_code(secret_base32, step), code):
                _totp_last_counter[0] = step
                return True
    return False


def require_approval(code: str, enrolled_required: bool = False) -> None:
    """Refuses a change of the broker rules without a current code when the authenticator is set up; with `enrolled_required` it refuses too while it is not."""
    path = totp_file()
    if not path.is_file():
        if enrolled_required:
            raise Refused(403, "totp_not_enrolled")
        return
    if not code:
        raise Refused(401, "totp_required")
    if not totp_accepts(path.read_text(encoding="ascii").strip(), code):
        raise Refused(401, "totp_invalid")


# ---- the two switches of the broker rules that no install turns on ------------------------------------------------------------------------------
# `battery-write NODE on|off` lets the server send an order to write to the batteries of one solar node; `alarm-state-relay on|off` lets the server publish again, signed,
# the state of the alarm panels. Both are lines of the broker rules that mqtt_identity.sh writes; here they are asked for one at a time, always with a code.
RELAYS = ("battery-write", "alarm-state-relay")
SERVER_BATTERY_LINE = re.compile(r"topic write armor/solar/([a-z0-9][a-z0-9_-]{0,63})/maintenance/command")


def relay_status() -> dict[str, object]:
    """Which of the two switches are on, read from the block of the server in the broker rules."""
    try:
        text = (PREFIX / "etc/mosquitto/acl").read_text(encoding="utf-8")
    except FileNotFoundError:
        return {"installed": False, "battery_write": [], "alarm_state_relay": False}
    inside = False
    battery: list[str] = []
    alarm = False
    for line in text.splitlines():
        if line.startswith("user "):
            inside = line.strip() == "user armor-server"
        elif inside:
            found = SERVER_BATTERY_LINE.fullmatch(line.strip())
            if found:
                battery.append(found.group(1))
            elif line.strip() == "topic write armor/alarm/+/state":
                alarm = True
    return {"installed": True, "battery_write": sorted(set(battery)), "alarm_state_relay": alarm,
            "approval": "totp" if totp_file().is_file() else "not_enrolled"}


def set_relay(kind: str, node: str, state: str) -> dict[str, object]:
    if kind not in RELAYS:
        raise Refused(404, "not_found")
    if state not in ("on", "off"):
        raise Refused(422, "invalid_state")
    if kind == "battery-write" and not NAME.fullmatch(node):
        raise Refused(422, "invalid_name")
    done = identity([kind, node, state] if kind == "battery-write" else [kind, state])
    if done.returncode != 0:
        message = (done.stderr or done.stdout).strip().splitlines()[-1:] or [""]
        raise Refused(409 if "does not exist" in message[0] else 502, "identity_failed")
    return {"ok": True, "relay": kind, "node": node if kind == "battery-write" else "", "state": state, **relay_status()}


# ---- the socket ---------------------------------------------------------------------------------------------------------------------------------

class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "armor-admin"
    token = ""

    def log_message(self, format: str, *args: object) -> None:       # the audit trail is the server's; stay quiet on the console
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
        if length > MAX_FILE_BYTES + 4096:
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
            given = self.headers.get("X-Armor-Admin-Token", "")
            if not self.token or not hmac.compare_digest(given.encode(), self.token.encode()):
                raise Refused(401, "unauthorized")
            parts = [part for part in self.path.split("?", 1)[0].split("/") if part]
            if parts[:1] != ["v1"]:
                raise Refused(404, "not_found")
            parts = parts[1:]
            sensitive_given = self.headers.get(SENSITIVE_HEADER, "")
            if method == "GET" and parts == ["status"]:
                self.reply(200, {"sensitive_writes": sensitive_status()})
            elif method == "GET" and parts == ["services"]:
                self.reply(200, {"services": [service_state(key) for key in SERVICES]})
            elif method == "POST" and len(parts) == 3 and parts[0] == "services":
                self.reply(200, service_action(parts[1], parts[2]))
            elif method == "GET" and parts == ["files"]:
                self.reply(200, {"files": [{k: v for k, v in read_file(key).items() if k != "content"} for key in FILES]})
            elif method == "GET" and len(parts) == 2 and parts[0] == "files":
                self.reply(200, read_file(parts[1]))
            elif method == "PUT" and len(parts) == 2 and parts[0] == "files":
                if is_sensitive_file(parts[1]):
                    require_sensitive(sensitive_given)
                if FILES[parts[1]][1] == "acl":
                    require_approval(self.headers.get(TOTP_HEADER, ""))
                data = self.body()
                content = data.get("content")
                if not isinstance(content, str):
                    raise Refused(422, "invalid_content")
                expect = data.get("expect_mtime")
                result = write_file(parts[1], content, float(expect) if isinstance(expect, (int, float)) else None)
                restarted: list[str] = []
                if data.get("restart") is True:
                    for service_id in FILES[parts[1]][2]:
                        service_action(service_id, "restart")
                        restarted.append(service_id)
                self.reply(200, {**result, "restarted": restarted})
            elif method == "GET" and parts == ["mqtt", "accounts"]:
                self.reply(200, list_accounts())
            elif method == "POST" and parts == ["mqtt", "accounts"]:
                require_sensitive(sensitive_given)
                data = self.body()
                self.reply(200, add_account(str(data.get("role", "")), str(data.get("name", "")), data.get("rotate") is True))
            elif method == "DELETE" and len(parts) == 3 and parts[:2] == ["mqtt", "accounts"]:
                require_sensitive(sensitive_given)
                self.reply(200, remove_account(parts[2]))
            elif method == "GET" and parts == ["mqtt", "relays"]:
                self.reply(200, relay_status())
            elif method == "POST" and len(parts) == 3 and parts[:2] == ["mqtt", "relays"] and parts[2] in RELAYS:
                require_sensitive(sensitive_given)
                require_approval(self.headers.get(TOTP_HEADER, ""), enrolled_required=True)
                data = self.body()
                self.reply(200, set_relay(parts[2], str(data.get("node", "")), str(data.get("state", ""))))
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
    def do_PUT(self) -> None: self.route("PUT")
    def do_DELETE(self) -> None: self.route("DELETE")


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
    print(f"armor-admin listening on {socket_path}", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Privileged helper of A.R.M.O.R. Studio's administration screens")
    parser.add_argument("--socket", default="/run/armor-admin.sock")
    parser.add_argument("--group", default="armor", help="the group allowed to open the socket")
    arguments = parser.parse_args()
    token = os.environ.get("ARMOR_ADMIN_TOKEN", "")
    if len(token) < 24:
        print("ARMOR_ADMIN_TOKEN must be set (at least 24 characters)", file=sys.stderr)
        return 2
    mode = os.environ.get("ARMOR_ADMIN_SENSITIVE", "open").strip().lower() or "open"
    problem = configure_sensitive(mode, os.environ.get("ARMOR_ADMIN_SENSITIVE_TOKEN", ""), token)
    if problem:
        print(f"ARMOR_ADMIN_SENSITIVE is not usable ({problem}): use open, read_only, or second_token with ARMOR_ADMIN_SENSITIVE_TOKEN (at least {MIN_SECRET} characters, different from ARMOR_ADMIN_TOKEN)", file=sys.stderr)
        return 2
    if mode == "open":
        print("WARNING: the broker rules and the .env files can be rewritten with the admin token alone; a compromised server could open the broker. "
              "Set ARMOR_ADMIN_SENSITIVE=second_token (with ARMOR_ADMIN_SENSITIVE_TOKEN) or read_only to lock them.", file=sys.stderr, flush=True)
    serve(arguments.socket, token, arguments.group)
    return 0


if __name__ == "__main__":
    sys.exit(main())
