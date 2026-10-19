# Signed packages: how the machine decides what it installs

The maintenance helper of the machine (`armor_maintenance_agent.py`) updates the A.R.M.O.R. programs (`server`, `studio`, `network`, `ai`, `voice`, `devops`) from the releases of their repositories on GitHub. Before it unpacks anything it checks three things, in this order:

1. **The hash:** the package must hash (SHA-256) to the value in `armor-<component>-<version>.tgz.sha256`. This catches a truncated download.
2. **The signature:** `armor-<component>-<version>.tgz.sig` holds the Ed25519 signature (64 bytes as 128 hexadecimal digits) of the text

   `armor-pkg/1|<component>|<version>|<sha256>`

   made with the private key of the releases. The helper verifies it with the public key that is part of its code (`PACKAGE_PUBLIC_KEY`), the same key the firmware of the nodes trusts. A release without a `.sig`, or with one that does not verify, is refused (`missing_signature`, `bad_signature`) and the system stays unchanged: nothing is unpacked, nothing is restarted.
3. **The archive:** no absolute names, no `..`, no links or devices.

Whoever can only change what a release holds on GitHub (a stolen account, a malicious dependency of the release tooling) can publish a package and its matching hash, but not its signature: the private key is never on GitHub. The text starts with `armor-pkg/1`, not with the `armor-fw/1` of the firmware, so a firmware signature can never be presented as a package signature; and it holds the component and the version, so a signed package cannot be passed off as another program or as a newer release.

The check is pure Python (RFC 8032): it needs no OpenSSL and no extra module on the machine.

## Publishing

```
python scripts/package_component.py server --repo ../ARMOR-SERVER --sign --publish
```

It writes `.tgz`, `.sha256` and `.sig` and uploads the three. The signer is `~/.armor/sign.mjs` (or `--signer` / `ARMOR_PACKAGE_SIGNER`); it reads the key from `ARMOR_FIRMWARE_KEY` or `~/.armor/firmware_ed25519.pem`. The key is never copied into a repository. `--sign` fails when there is no signer or key; without it the package is signed when they are there. A key other than the one the helper trusts is never used. `--publish` refuses to upload an unsigned package.

To sign a package that is already published, download it next to its `.sha256` and run:

```
python scripts/package_component.py --sign-existing armor-server-0.5.7.tgz --upload
```

The name gives the component and the version; `--upload` adds the `.sig` to the release `v<version>` of its repository (needs `gh`).

## Emergency override

If a package must be installed without a signature (a lost key, for example), write this line in the machine's `armor.maint.env` (in `$PREFIX/etc/`) and remove it afterwards:

```
ARMOR_MAINT_ALLOW_UNSIGNED=1
```

It is read from that file every time something is installed, so it can not be set through the HTTP API or the process environment. The helper writes a `WARNING` in the job log and in its own log each time it is used, and the overview reports `unsigned_allowed`.

## Changing the key

Make a new pair and put the new public key in `PACKAGE_PUBLIC_KEY` and in the firmware (`fw_trust.hpp`). Release a `devops` package signed with the **old** key (the machines install it and from then on trust the new one), then sign the following packages with the new key.

## Tests

`scripts/test_maintenance_agent.py` covers a valid signature, a tampered package, a missing `.sig`, a signature by another key, garbage, the override (only from the file), the RFC 8032 test vector, and that the key in the helper is the one in `fw_trust.hpp`. They use throwaway keys, never the real one.

The packager refuses to pack a stale build: for `server` and `studio` the version in `package.json` (and, for Studio, in `dist/version.json`) must be the one in `armor.project.json`, and `dist/` must not be older than the sources it was built from. Build again (`npm run build`) first.
