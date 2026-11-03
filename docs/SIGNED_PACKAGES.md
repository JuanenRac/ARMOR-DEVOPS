# Signed packages: how the machine decides what it installs

The maintenance helper of the machine (`armor_maintenance_agent.py`) updates the A.R.M.O.R. programs (`server`, `studio`, `network`, `ai`, `voice`, `devops`) from the releases of their repositories on GitHub. Before it unpacks anything it checks three things, in this order:

1. **The hash:** the package must hash (SHA-256) to the value in `armor-<component>-<version>.tgz.sha256`. This catches a truncated download.
2. **The signature:** `armor-<component>-<version>.tgz.sig2` holds the Ed25519 signature (64 bytes as 128 hexadecimal digits) of the manifest

   `armor-fw/1|<component>|package|<version>|<sha256>`

   made with the private key of the releases, the one that signs the firmware of the nodes: it is the same manifest as the firmware images, with `package` where the board goes. The helper verifies it with the public key that is part of its code (`PACKAGE_PUBLIC_KEY`) and, while the key is being changed, with a second one (see below). A release without a `.sig2`, or with one that does not verify, is refused (`missing_signature`, `bad_signature`) and the system stays unchanged: nothing is unpacked, nothing is restarted.
3. **The archive:** no absolute names, no `..`, no links or devices.

Whoever can only change what a release holds on GitHub (a stolen account, a malicious dependency of the release tooling) can publish a package and its matching hash, but not its signature: the private key is never on GitHub. The manifest binds the signature to the component and the version, so a signed package of the past or of another component can not be presented as the newest one, and the signature of a firmware image (another project, a real board) can never pass as a package signature. The older `.sig` (text `armor-pkg/1|<component>|<version>|<sha256>`) is no longer enough: it is accepted only when the `armor.maint.env` of the machine says `ARMOR_MAINT_SIGNATURE=either`, for the time it takes to sign the packages that were published before.

The check is pure Python (RFC 8032): it needs no OpenSSL and no extra module on the machine.

## Publishing

```
python scripts/package_component.py server --repo ../ARMOR-SERVER --sign --publish
```

It writes `.tgz`, `.sha256`, `.sig2` (the manifest) and `.sig` (the older text, which a helper that has not been updated yet still checks) and uploads them. The signer is `~/.armor/sign.mjs` (or `--signer` / `ARMOR_PACKAGE_SIGNER`); it reads the key from `ARMOR_FIRMWARE_KEY` or `~/.armor/firmware_ed25519.pem`. The key is never copied into a repository. `--sign` fails when there is no signer or key; without it the package is signed when they are there. A key other than the one the helper trusts is never used. `--publish` refuses to upload an unsigned package.

To sign a package that is already published, download it next to its `.sha256` and run:

```
python scripts/package_component.py --sign-existing armor-server-0.5.7.tgz --upload
```

The name gives the component and the version; `--upload` adds the `.sig2` and the `.sig` to the release `v<version>` of its repository (needs `gh`).

## Emergency override

If a package must be installed without a signature (a lost key, for example), write this line in the machine's `armor.maint.env` (in `$PREFIX/etc/`) and remove it afterwards:

```
ARMOR_MAINT_ALLOW_UNSIGNED=1
```

It is read from that file every time something is installed, so it can not be set through the HTTP API or the process environment. The helper writes a `WARNING` in the job log and in its own log each time it is used, and the overview reports `unsigned_allowed`.

## Settings of the machine

Two settings about the signature, read from `armor.maint.env` every time something is installed (never from the HTTP API or the process environment):

```
ARMOR_MAINT_SIGNATURE=manifest
ARMOR_MAINT_NEXT_KEY=
```

`ARMOR_MAINT_SIGNATURE` is `manifest` (the default: only the `.sig2` counts) or `either` (the older `.sig` counts too). `ARMOR_MAINT_NEXT_KEY` is empty or the second public key, 64 hexadecimal digits, trusted besides the built-in one during a rotation; no more than two keys are ever trusted. The overview of the helper shows `signature_mode` and `trusted_fingerprints` (the first 16 digits of the SHA-256 of each key, never the keys), so that whoever looks after the machine can see which keys it trusts. A change here is a change in how the machine decides what it installs: it is made on the machine, as root, like the emergency override.

## Changing the key

Make a new pair. First write the new public key as `ARMOR_MAINT_NEXT_KEY` in the `armor.maint.env` of every machine (or release a `devops` package, signed with the **old** key, whose `PACKAGE_PUBLIC_KEY` is the new one). From then on sign the packages with the new key: the machines trust both while that line is there. When every machine has the new key built in, remove the line. The firmware of the nodes trusts one key (`fw_trust.hpp`): change it as the page of the signed firmware says.

## Tests

`scripts/test_maintenance_agent.py` covers a valid manifest signature, that it binds the component, the version and the hash, that a firmware signature, the older text and the bare hash do not pass as a manifest, a tampered package, a missing `.sig2`, a signature by another key, garbage, the older `.sig` alone (refused, accepted only with `either`), the two keys of a rotation (and that a third one is never trusted), the override (only from the file), the RFC 8032 test vector, and that the key in the helper is the one in `fw_trust.hpp`. They use throwaway keys, never the real one.

The packager refuses to pack a stale build: for `server` and `studio` the version in `package.json` (and, for Studio, in `dist/version.json`) must be the one in `armor.project.json`, and `dist/` must not be older than the sources it was built from. Build again (`npm run build`) first.
