#!/usr/bin/env python3
"""ARMOR-DEVOPS - the installation's own certificate authority for the LAN, and a second certificate for the address of the machine on the local network.

Optional and OFF until the settings file says `"enabled": true` (or `setup --enable` writes it). The proxy of the `tls` profile keeps working as it is; this is the way to an
`https://192.168.0.180` that a phone or a browser trusts after the owner installs the authority ONCE, without any Internet authority and without a name in the public DNS.

  armor_lan_cert.py plan   --ip ADDRESS [--name HOST]...            what would be made; changes nothing
  armor_lan_cert.py setup  --ip ADDRESS [--name HOST]... [--enable] [--force]
                                                                    the authority (once) and a certificate for the address; --enable switches the feature on in the settings file
  armor_lan_cert.py status                                          the files, the dates and the fingerprints (never a key)
  armor_lan_cert.py fingerprint [--spki]                            SHA-256 of the authority's certificate (what a wall panel pins), or of its public key (what the phone app pins)
  armor_lan_cert.py export-ca [--out FILE]                          the certificate of the authority (PEM, public) to install on the phones and computers
  armor_lan_cert.py remove                                          the keys and certificates are put aside in a folder of their own, never deleted

Where things live: `~/.armor/lan-ca/` (ARMOR_LAN_CA_DIR overrides it), folder 0700, every private key 0600. The private keys are never printed, never copied by this program and never
part of a repository or a package. The authority may certify only private addresses and `.lan` / `.local` names (a name constraint inside its own certificate), so a stolen copy of its key cannot
impersonate a site on the Internet for a device that trusts it. The address given must be a private one: this program refuses a public address.

Settings (`lan-ca.json` in the folder; the values below are the defaults):
  enabled false | ca_days 3650 | leaf_days 397 | renew_days 30 | curve "prime256v1" | name_constraints true
Nothing here has been run on the CM5.
Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.
"""
from __future__ import annotations

import argparse
import base64
import calendar
import hashlib
import ipaddress
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

DEFAULTS = {"enabled": False, "ca_days": 3650, "leaf_days": 397, "renew_days": 30, "curve": "prime256v1", "name_constraints": True}
LIMITS = {"ca_days": (30, 7300), "leaf_days": (1, 825), "renew_days": (1, 365)}
CURVES = ("prime256v1", "secp384r1")
PRIVATE_BLOCKS = ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "169.254.0.0/16", "127.0.0.0/8")
NAME = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9.-]{0,251}[A-Za-z0-9])?$")


class LanCertError(Exception):
    """Something the person has to put right; the message says what."""


def base_dir() -> Path:
    given = os.environ.get("ARMOR_LAN_CA_DIR", "").strip()
    return Path(given) if given else Path.home() / ".armor" / "lan-ca"


def read_settings(folder: Path) -> dict:
    """The settings file over the defaults; a value out of range or of the wrong kind is an error, not a guess."""
    settings = dict(DEFAULTS)
    path = folder / "lan-ca.json"
    if not path.is_file():
        return settings
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise LanCertError(f"{path} is not readable JSON ({error.__class__.__name__})") from None
    if not isinstance(data, dict):
        raise LanCertError(f"{path} must hold one JSON object")
    for key, value in data.items():
        if key not in DEFAULTS:
            raise LanCertError(f"{path}: unknown setting '{key}'")
        if isinstance(DEFAULTS[key], bool):
            if not isinstance(value, bool):
                raise LanCertError(f"{path}: '{key}' must be true or false")
        elif key == "curve":
            if value not in CURVES:
                raise LanCertError(f"{path}: 'curve' must be one of {', '.join(CURVES)}")
        else:
            low, high = LIMITS[key]
            if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
                raise LanCertError(f"{path}: '{key}' must be a whole number from {low} to {high}")
        settings[key] = value
    return settings


def write_settings(folder: Path, settings: dict) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    restrict(folder, 0o700)
    path = folder / "lan-ca.json"
    path.write_text(json.dumps(settings, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def restrict(path: Path, mode: int) -> None:
    try:
        os.chmod(path, mode)
    except OSError:
        pass   # a file system that has no modes (a Windows test machine): nothing to restrict


def private_address(text: str) -> ipaddress.IPv4Address:
    try:
        address = ipaddress.ip_address(text)
    except ValueError:
        raise LanCertError(f"'{text}' is not an IP address") from None
    if not isinstance(address, ipaddress.IPv4Address):
        raise LanCertError("only IPv4 addresses of the local network are supported")
    if not any(address in ipaddress.ip_network(block) for block in PRIVATE_BLOCKS):
        raise LanCertError(f"{address} is not a private address of the local network: this authority never certifies a public one")
    return address


def valid_names(names: list[str]) -> list[str]:
    out = []
    for name in names:
        if not NAME.match(name):
            raise LanCertError(f"'{name}' is not a valid name")
        if not (name.endswith(".lan") or name.endswith(".local") or name == "localhost"):
            raise LanCertError(f"'{name}': the authority certifies only names ending in .lan or .local")
        out.append(name)
    return out


def openssl() -> str:
    found = shutil.which("openssl")
    if not found:
        raise LanCertError("openssl is not installed")
    return found


def run(arguments: list[str], cwd: Path | None = None, data: bytes | None = None) -> bytes:
    result = subprocess.run([openssl(), *arguments], cwd=cwd, input=data, capture_output=True, check=False)
    if result.returncode != 0:
        # The message of openssl may quote a path but never a key; it is shortened anyway.
        raise LanCertError("openssl failed: " + result.stderr.decode("utf-8", "replace").strip().splitlines()[-1][:160] if result.stderr.strip() else "openssl failed")
    return result.stdout


def req(arguments: list[str]) -> bytes:
    """`openssl req` with a configuration of its own: it does not depend on (or fail for lack of) the default openssl.cnf of the machine."""
    with tempfile.TemporaryDirectory() as scratch:
        config = Path(scratch) / "req.cnf"
        config.write_text("[req]\ndistinguished_name=dn\nprompt=no\n[dn]\nCN=armor\n", encoding="utf-8")
        return run(["req", "-config", str(config), *arguments])


def constraints() -> str:
    permitted = [f"permitted;IP:{ipaddress.ip_network(block).network_address}/{ipaddress.ip_network(block).netmask}" for block in PRIVATE_BLOCKS]
    permitted += ["permitted;DNS:.lan", "permitted;DNS:.local", "permitted;DNS:localhost"]
    return ",".join(permitted)


def make_authority(folder: Path, settings: dict) -> None:
    extensions = ["basicConstraints=critical,CA:TRUE,pathlen:0", "keyUsage=critical,keyCertSign,cRLSign", "subjectKeyIdentifier=hash"]
    if settings["name_constraints"]:
        extensions.append("nameConstraints=critical," + constraints())
    key = folder / "ca.key"
    run(["ecparam", "-name", settings["curve"], "-genkey", "-noout", "-out", str(key)])
    restrict(key, 0o600)
    arguments = ["-x509", "-new", "-key", str(key), "-sha256", "-days", str(settings["ca_days"]), "-subj", "/O=A.R.M.O.R./CN=A.R.M.O.R. local authority", "-out", str(folder / "ca.crt")]
    for extension in extensions:
        arguments += ["-addext", extension]
    req(arguments)


def make_leaf(folder: Path, settings: dict, address: ipaddress.IPv4Address, names: list[str]) -> None:
    key = folder / "leaf.key"
    run(["ecparam", "-name", settings["curve"], "-genkey", "-noout", "-out", str(key)])
    restrict(key, 0o600)
    alt = [f"IP:{address}", "IP:127.0.0.1"] + [f"DNS:{name}" for name in names]
    extension_text = "basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature\nextendedKeyUsage=serverAuth\nsubjectAltName=" + ",".join(alt) + "\nsubjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid\n"
    with tempfile.TemporaryDirectory() as scratch:
        scratch_path = Path(scratch)
        (scratch_path / "leaf.ext").write_text(extension_text, encoding="utf-8")
        req(["-new", "-key", str(key), "-subj", f"/O=A.R.M.O.R./CN={address}", "-out", str(scratch_path / "leaf.csr")])
        run(["x509", "-req", "-in", str(scratch_path / "leaf.csr"), "-CA", str(folder / "ca.crt"), "-CAkey", str(folder / "ca.key"), "-CAcreateserial", "-CAserial", str(scratch_path / "ca.srl"),
             "-sha256", "-days", str(settings["leaf_days"]), "-extfile", str(scratch_path / "leaf.ext"), "-out", str(folder / "leaf.crt")])
    (folder / "fullchain.pem").write_text((folder / "leaf.crt").read_text(encoding="utf-8") + (folder / "ca.crt").read_text(encoding="utf-8"), encoding="utf-8")


def days_left(certificate: Path) -> int:
    text = run(["x509", "-in", str(certificate), "-noout", "-enddate"]).decode().strip()
    end = calendar.timegm(time.strptime(text.split("=", 1)[1].replace("  ", " ").replace(" GMT", ""), "%b %d %H:%M:%S %Y"))
    return int((end - time.time()) // 86400)


def fingerprint(certificate: Path, spki: bool) -> str:
    if spki:
        der = run(["pkey", "-pubin", "-outform", "DER"], data=run(["x509", "-in", str(certificate), "-noout", "-pubkey"]))
        return base64.b64encode(hashlib.sha256(der).digest()).decode()
    der = run(["x509", "-in", str(certificate), "-outform", "DER"])
    return hashlib.sha256(der).hexdigest().upper()


def require_enabled(settings: dict) -> None:
    if not settings["enabled"]:
        raise LanCertError("the local authority is switched off (\"enabled\": false in lan-ca.json); run setup with --enable to switch it on")


def command_plan(args: argparse.Namespace) -> int:
    folder = base_dir()
    settings = read_settings(folder)
    address = private_address(args.ip)
    names = valid_names(args.name)
    print(f"folder: {folder}")
    print(f"switch: {'on' if settings['enabled'] else 'off (setup needs --enable)'}")
    print(f"authority: {'exists, kept' if (folder / 'ca.key').exists() else 'would be made'} ({settings['curve']}, {settings['ca_days']} days, name constraints {'on' if settings['name_constraints'] else 'off'})")
    print(f"certificate: for {address}" + "".join(f", {n}" for n in names) + f" ({settings['leaf_days']} days)")
    return 0


def command_setup(args: argparse.Namespace) -> int:
    folder = base_dir()
    settings = read_settings(folder)
    address = private_address(args.ip)
    names = valid_names(args.name)
    if args.enable and not settings["enabled"]:
        settings["enabled"] = True
        write_settings(folder, settings)
    require_enabled(settings)
    folder.mkdir(parents=True, exist_ok=True)
    restrict(folder, 0o700)
    if not (folder / "ca.key").exists():
        make_authority(folder, settings)
        print("authority: made")
    else:
        print("authority: kept")
    current = folder / "leaf.crt"
    if current.exists() and not args.force and days_left(current) > settings["renew_days"] and has_address(current, address, names):
        print(f"certificate: kept ({days_left(current)} days left)")
    else:
        make_leaf(folder, settings, address, names)
        print(f"certificate: made for {address}")
    print(f"authority fingerprint (SHA-256): {fingerprint(folder / 'ca.crt', False)}")
    print(f"files: {folder / 'leaf.crt'}, {folder / 'leaf.key'}, {folder / 'fullchain.pem'}, {folder / 'ca.crt'} (the authority's key stays in {folder / 'ca.key'}; no key is printed)")
    return 0


def has_address(certificate: Path, address: ipaddress.IPv4Address, names: list[str]) -> bool:
    text = run(["x509", "-in", str(certificate), "-noout", "-ext", "subjectAltName"]).decode()
    return f"IP Address:{address}" in text and all(f"DNS:{name}" in text for name in names)


def command_status(_: argparse.Namespace) -> int:
    folder = base_dir()
    settings = read_settings(folder)
    print(f"switch: {'on' if settings['enabled'] else 'off'}")
    print(f"renew_days: {settings['renew_days']}")
    for label, name in (("authority", "ca.crt"), ("certificate", "leaf.crt")):
        path = folder / name
        if path.is_file():
            print(f"{label}: {days_left(path)} days left, SHA-256 {fingerprint(path, False)}")
        else:
            print(f"{label}: none")
    return 0


def command_fingerprint(args: argparse.Namespace) -> int:
    path = base_dir() / "ca.crt"
    if not path.is_file():
        raise LanCertError("there is no authority yet (run setup)")
    print(fingerprint(path, args.spki))
    return 0


def command_export(args: argparse.Namespace) -> int:
    path = base_dir() / "ca.crt"
    if not path.is_file():
        raise LanCertError("there is no authority yet (run setup)")
    pem = path.read_text(encoding="utf-8")
    if "PRIVATE" in pem:
        raise LanCertError("ca.crt holds a private key: refusing to export it")
    if args.out:
        Path(args.out).write_text(pem, encoding="utf-8")
        print(f"written: {args.out}")
    else:
        sys.stdout.write(pem)
    return 0


def command_remove(_: argparse.Namespace) -> int:
    folder = base_dir()
    if not folder.is_dir():
        print("nothing to remove")
        return 0
    aside = folder.with_name(folder.name + ".removed-" + time.strftime("%Y%m%d%H%M%S"))
    folder.rename(aside)
    print(f"put aside (not deleted): {aside}")
    return 0


def parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser(prog="armor_lan_cert", description="The local authority and the certificate for the address of the machine on the local network.")
    sub = top.add_subparsers(dest="command", required=True)
    for name, function in (("plan", command_plan), ("setup", command_setup)):
        item = sub.add_parser(name)
        item.add_argument("--ip", required=True)
        item.add_argument("--name", action="append", default=[])
        if name == "setup":
            item.add_argument("--enable", action="store_true")
            item.add_argument("--force", action="store_true")
        item.set_defaults(function=function)
    sub.add_parser("status").set_defaults(function=command_status)
    item = sub.add_parser("fingerprint")
    item.add_argument("--spki", action="store_true")
    item.set_defaults(function=command_fingerprint)
    item = sub.add_parser("export-ca")
    item.add_argument("--out")
    item.set_defaults(function=command_export)
    sub.add_parser("remove").set_defaults(function=command_remove)
    return top


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return args.function(args)
    except LanCertError as error:
        print(f"armor_lan_cert: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
