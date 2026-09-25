# Changelog

All notable changes to this project are documented here.

## [0.4.0] - A.R.M.O.R.'s own MQTT broker on the bench

- `install_cm5.sh --with-mqtt` runs Mosquitto as a third systemd unit (`armor-mosquitto`) on its own port (18883), with its own passwords and ACL, never the system broker and never the standard port 1883 that other software may use. An upgrade keeps an existing broker.
- `scripts/mqtt_identity.sh` adds or removes a field-node or alarm-consumer identity with the least privilege each needs, printing the generated password once.
- The installer points the server at FFmpeg when it is installed (live video, captures and recordings; the server unit gets more memory then) and says so when it is not.
- Verified on a real CM5: anonymous connections are refused, a node's telemetry reaches the server over MQTT and raises an alert, and the alarm is delivered to a consumer on `armor/server/alert`.

## [0.3.0] - Backup, restore and TLS

- `scripts/backup_data.sh` and `restore_data.sh`: AES-256 encrypted, verified and checksummed backups of the server data; restore never overwrites existing data. `scripts/test_backup.sh` covers the round trip, a wrong passphrase, a damaged archive and restoring over existing data.
- Compose: optional `tls` profile (Caddy with a local certificate authority), alarm variables for the server, and an ACL rule for `armor/server/alert`.
- [BACKUP_AND_TLS](docs/BACKUP_AND_TLS.md) documents what is worth backing up, that the camera key is not in the data directory, and how to enable TLS.
- Corrected the README: the Compose topology is written but has not been validated with Docker here (none is installed on the development PC) nor run.

## [0.2.0] - 2026-09-25

- Isolated CM5 test bench: deploy and install scripts with their own user, directory, ports and limits.
- Hardened Compose topology with an authenticated broker, secrets generation and required-env check.
