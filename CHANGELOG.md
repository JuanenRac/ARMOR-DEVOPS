# Changelog

All notable changes to this project are documented here.

## [0.3.0] - Backup, restore and TLS

- `scripts/backup_data.sh` and `restore_data.sh`: AES-256 encrypted, verified and checksummed backups of the server data; restore never overwrites existing data. `scripts/test_backup.sh` covers the round trip, a wrong passphrase, a damaged archive and restoring over existing data.
- Compose: optional `tls` profile (Caddy with a local certificate authority), alarm variables for the server, and an ACL rule for `armor/server/alert`.
- [BACKUP_AND_TLS](docs/BACKUP_AND_TLS.md) documents what is worth backing up, that the camera key is not in the data directory, and how to enable TLS.
- Corrected the README: the Compose topology is written but has not been validated with Docker here (none is installed on the development PC) nor run.

## [0.2.0] - 2026-09-25

- Isolated CM5 test bench: deploy and install scripts with their own user, directory, ports and limits.
- Hardened Compose topology with an authenticated broker, secrets generation and required-env check.
