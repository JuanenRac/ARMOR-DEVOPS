# Backup, restore and TLS

## What is worth backing up

The server keeps everything under its data directory (`ARMOR_DATA_DIR`, `/data` in Compose,
`/opt/armor/data` on the CM5 bench):

| File | Holds |
|---|---|
| `cameras.json` | Camera registry; passwords are AES-256-GCM encrypted |
| `state.json` | Security mode and last observation of every node |
| `rules.json` | Alert dwell time and ignore zones |
| `events.log` (+ `.1` to `.3`) | Event history |
| `audit.log` (+ rotations) | Audit trail |
| `media/` | Snapshots and recordings (large; excluded by default) |

**The camera key is not in the data directory.** `cameras.json` is unreadable without
`ARMOR_CAMERA_CONFIG_KEY`, which lives in the environment file. Keep a copy of the key somewhere
other than the backup (a password manager), or the cameras have to be entered again.

## Backup

```bash
printf '%s\n' 'a long passphrase kept somewhere safe' > /root/armor-backup.pass && chmod 600 /root/armor-backup.pass
scripts/backup_data.sh --data-dir /opt/armor/data --out-dir /var/backups/armor --passphrase-file /root/armor-backup.pass
```

The archive is AES-256 encrypted (PBKDF2), verified by decrypting it again, and accompanied by a
`.sha256`. Add `--with-media` to include recorded evidence. By default the script
never deletes older backups; `--keep N` keeps only the N newest archives of the output folder
(and their `.sha256`) once the new one is verified, and `--copy-to DIR` also copies the archive to
a mounted share or an external disk and checks the copy against its checksum. With `--require-mount` the copy is refused (and nothing is backed up) unless `DIR` is a mounted
disk of its own, so an unplugged USB disk never fills the system card, and it is refused when the disk
lacks room for the archive; the copy is flushed to the disk before the script reports success. Run it nightly
from a cron entry or a systemd timer.

Other copies and Docker volumes: `--copy-ssh HOST:/DIR` sends the archive and its `.sha256` to another machine with `scp` and checks them there with `sha256sum`; `--copy-rclone REMOTE:PATH` sends them to an rclone remote and checks them with `rclone check`; a copy that fails or does not match is an error and the verified archive stays in the output folder. `--compose-volume NAME` (repeat it) adds the contents of a named Docker volume, read once, read-only and without network by a throw-away container, under `armor-volumes/` in the archive; if a volume cannot be read nothing is backed up. `restore_data.sh --apply --volumes-to DIR` puts those tar files in `DIR`.

## Restore

```bash
scripts/restore_data.sh --file armor-data-….tar.gz.enc --data-dir /opt/armor/data --passphrase-file /root/armor-backup.pass          # lists only
sudo systemctl stop armor-server
scripts/restore_data.sh --file armor-data-….tar.gz.enc --data-dir /opt/armor/data --passphrase-file /root/armor-backup.pass --apply
sudo systemctl start armor-server
```

A wrong passphrase, a damaged archive or an archive with unsafe paths is refused. An existing data
directory is never overwritten: it is renamed to `data.before-restore-<time>` first. After restoring,
check the ownership of the directory matches the service user. `scripts/test_backup.sh` exercises
backup, wrong passphrase, dry run, restore over existing data and a damaged archive.

## TLS

Studio and the API travel over plain HTTP by default, which is acceptable on a bench LAN and not
beyond it. With Compose, the `tls` profile adds Caddy in front of Studio:

```bash
docker compose --profile tls up --build
```

Caddy listens on `ARMOR_TLS_BIND:8443` (loopback by default) with a certificate from its own local
authority, issued for `ARMOR_TLS_HOST` (default `localhost`): browse to `https://<that name>:8443`, not to an
IP address. Install the authority's root certificate (in the `proxy-data` volume, `pki/authorities/local/root.crt`)
on every device that opens Studio, then set in `.env`:

```
ARMOR_PUBLIC_ORIGIN=https://<host>:8443
ARMOR_COOKIE_SECURE=1
```

`ARMOR_COOKIE_SECURE=1` makes the session cookie HTTPS-only, so set it only when every access goes
through the TLS address. The profile has been started and answered over HTTPS with `scripts/test_compose.sh`
(Docker Engine in WSL); Caddy logs an error that it could not install its root certificate in the container's own
trust store, which is harmless. Whether a given browser trusts the authority once you install it has not been verified.

For a name on the Internet (DuckDNS, No-IP or your own domain) the local authority is not what you want: put your e-mail address in `ARMOR_TLS_ISSUER` and Caddy asks Let's Encrypt for a real certificate by itself and renews it, so phones and browsers trust it without installing anything. That needs ports 80 and 443 of this host reachable from the Internet (`ARMOR_TLS_PORT=443`, `ARMOR_TLS_HTTP_PORT=80`). The whole procedure, with the dynamic DNS name, is in `REMOTE_ACCESS.md`; the pairing of the local authority is in `HTTPS_PAIRING.md`.

## HTTPS on the local network with a pinned authority (profile `lan-ca`)

For a house network without a name on the Internet there is a second, optional profile, separate from `tls`: `docker compose --profile lan-ca up -d`. It starts `proxy_lan`, which serves Studio and the API only on port 443 (there is no port 80 and no redirect, so nothing answers in plain text) with a certificate for `ARMOR_LAN_HOST` issued by the internal authority of Caddy, kept in the volume `lan-ca-data` and never leaving the machine. It listens on `ARMOR_LAN_BIND` (loopback by default; put the address of the machine on the network when a firewall protects it).

The devices do not have to trust that authority in their system. The wall panel and the phone app pin its fingerprint: `scripts/armor_ca_fingerprint.sh` prints the SHA-256 of the root certificate (64 hexadecimal digits, upper case) from the running container, or from a copy of `root.crt`. Only the public certificate is read. The profile `tls` and its port are not changed by this one. Both already pin what they are given: the wall panel a fingerprint or the end of the chain, the phone app the key of the authority (`--spki` prints that, `--pem` prints the certificate itself); this profile only provides the authority and these values. It has not been tried with a real wall panel or phone.
