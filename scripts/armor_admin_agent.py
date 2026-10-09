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
# It uses nothing but the Python standard library.
#
#   armor_admin_agent.py --socket /run/armor-admin.sock        # as root, by the systemd unit armor-admin.service
from __future__ import annotations

import argparse
import hmac
import http.server
import json
import os
import re
import socketserver
import subprocess
import sys
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
    "voice": ("armor-voice", "The voice gateway: written and spoken commands (a closed list of four)"),
}
for pair in filter(None, os.environ.get("ARMOR_ADMIN_EXTRA_SERVICES", "").split(",")):
    key, _, unit = pair.partition("=")
    if re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,31}", key) and re.fullmatch(r"[A-Za-z0-9@_.-]{1,64}", unit):
        SERVICES[key] = (unit, "Extra service")
ACTIONS = {"start": ["start"], "stop": ["stop"], "restart": ["restart"], "reload": ["reload-or-restart"]}
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
ROLES = {"node", "solar-node", "electrical-node", "network-node", "consumer", "device", "bridge"}
NAME = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")
USER = re.compile(r"(field-node|solar-node|electrical-node|network-node|alarm|device|bridge)-[a-z0-9][a-z0-9_-]{0,63}")


class Refused(Exception):
    def __init__(self, status: int, code: str) -> None:
        super().__init__(code)
        self.status, self.code = status, code


def run(command: list[str], timeout: float = 30.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)


# ---- services -----------------------------------------------------------------------------------------------------------------------------------

def service_state(service_id: str) -> dict[str, object]:
    unit, description = SERVICES[service_id]
    shown = run([SYSTEMCTL, "show", unit, "--no-pager", "--property=LoadState,ActiveState,SubState,UnitFileState,MainPID,ActiveEnterTimestamp"])
    fields = dict(line.split("=", 1) for line in shown.stdout.splitlines() if "=" in line)
    return {
        "id": service_id, "unit": unit, "description": description,
        "installed": fields.get("LoadState", "not-found") != "not-found",
        "active": fields.get("ActiveState", "unknown"), "sub": fields.get("SubState", ""),
        "enabled": fields.get("UnitFileState", ""), "pid": int(fields.get("MainPID", "0") or 0), "since": fields.get("ActiveEnterTimestamp", ""),
    }


def service_action(service_id: str, action: str) -> dict[str, object]:
    if service_id not in SERVICES:
        raise Refused(404, "unknown_service")
    if action not in ACTIONS:
        raise Refused(422, "unknown_action")
    unit = SERVICES[service_id][0]
    command = [SYSTEMCTL] + (["--no-block"] if unit in NO_BLOCK and action != "start" else []) + ACTIONS[action] + [unit]
    done = run(command, timeout=60.0)
    if done.returncode != 0:
        raise Refused(502, "systemctl_failed")
    return {"ok": True, "service": service_id, "action": action}


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
    return {"id": file_id, "path": str(path), "format": fmt, "description": description, "units": list(units), "exists": True, "content": content, "mtime": mtime}


def write_file(file_id: str, content: str, expect_mtime: float | None) -> dict[str, object]:
    path = file_path(file_id)
    fmt = FILES[file_id][1]
    check_content(fmt, content)
    existing = path.exists()
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


def add_account(role: str, name: str) -> dict[str, object]:
    if role not in ROLES:
        raise Refused(422, "unknown_role")
    if not NAME.fullmatch(name):
        raise Refused(422, "invalid_name")
    done = identity(["add", role, name])
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
        length = int(self.headers.get("Content-Length") or 0)
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
            if method == "GET" and parts == ["services"]:
                self.reply(200, {"services": [service_state(key) for key in SERVICES]})
            elif method == "POST" and len(parts) == 3 and parts[0] == "services":
                self.reply(200, service_action(parts[1], parts[2]))
            elif method == "GET" and parts == ["files"]:
                self.reply(200, {"files": [{k: v for k, v in read_file(key).items() if k != "content"} for key in FILES]})
            elif method == "GET" and len(parts) == 2 and parts[0] == "files":
                self.reply(200, read_file(parts[1]))
            elif method == "PUT" and len(parts) == 2 and parts[0] == "files":
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
                data = self.body()
                self.reply(200, add_account(str(data.get("role", "")), str(data.get("name", ""))))
            elif method == "DELETE" and len(parts) == 3 and parts[:2] == ["mqtt", "accounts"]:
                self.reply(200, remove_account(parts[2]))
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
    serve(arguments.socket, token, arguments.group)
    return 0


if __name__ == "__main__":
    sys.exit(main())
