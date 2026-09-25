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
`.sha256`. Add `--with-media` to include recorded evidence. The script never deletes older backups:
rotate them yourself, for example with a cron entry that runs it nightly.

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
