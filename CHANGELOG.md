# Changelog

All notable changes to this project are documented here.

## [0.2.5] - Another way in: a public address behind a router

- `install_cm5.sh --also-reach http://PUBLIC:2601=http://PUBLIC:2600` (repeatable) adds a second Studio address and server address to the ones the browser is allowed to use: the server's list of allowed origins and Studio's policy get both. The pairs are remembered in `armor.reach` and kept by the next installs; `--forget-reach` drops them. The address is checked before anything is written.
- `deploy_cm5.sh` passes `--also-reach` and `--forget-reach` on, and has `--port` (the SSH port, for a router that forwards a public port to it) and `--public-host` (the address the browser uses, when it is not the one the deploy connects to; before, both were the same).
- The bench guide says how to reach the installation from the Internet, and that this is plain HTTP: the password crosses the Internet in clear unless the TLS profile or a VPN is in front.

## [0.2.4] - MQTT access for devices

- The broker's rules let the server listen on and command the topics under `armor/device/`; an install made before devices existed gets the rule added on the next `install_cm5.sh --with-mqtt` run.
- `scripts/mqtt_identity.sh add device NAME` gives one smart device access to its own topics only (`armor/device/NAME/#`); `add bridge NAME` gives a bridge (Zigbee2MQTT with `base_topic` set to `armor/device`, a Shelly gateway) all of `armor/device/#`. `remove` accepts both.

## [0.2.3] - FFmpeg on the bench and a Compose that was run

- The installer points the server at FFmpeg when it is installed. `scripts/test_compose.sh` builds and runs the Compose topology (broker, server, Studio and the TLS profile) with 12 checks; it found and fixed three faults.

## [0.2.2] - A.R.M.O.R.'s own MQTT broker on the bench

- **Compose run for real** (Docker Engine in WSL, `scripts/test_compose.sh`, 12 checks) and three faults fixed that a YAML check could not see: the broker could not start with every capability dropped (it needs `CHOWN`, `SETUID`, `SETGID` to drop to its own user), it could not read its password and ACL files (they are now world-readable on purpose: a salted hash and an access list), and Caddy could not even execute with all capabilities dropped (it needs `NET_BIND_SERVICE`). The TLS certificate is now issued for `ARMOR_TLS_HOST` because a hostless site cannot answer a request by IP address.
- `install_cm5.sh --with-mqtt` runs Mosquitto as a third systemd unit (`armor-mosquitto`) on its own port (18883), with its own passwords and ACL, never the system broker and never the standard port 1883 that other software may use. An upgrade keeps an existing broker.
- `scripts/mqtt_identity.sh` adds or removes a field-node or alarm-consumer identity with the least privilege each needs, printing the generated password once.
- The installer points the server at FFmpeg when it is installed (live video, captures and recordings; the server unit gets more memory then) and says so when it is not.
- Verified on a real CM5: anonymous connections are refused, a node's telemetry reaches the server over MQTT and raises an alert, and the alarm is delivered to a consumer on `armor/server/alert`.

## [0.2.1] - Backup, restore and TLS

- `scripts/backup_data.sh` and `restore_data.sh`: AES-256 encrypted, verified and checksummed backups of the server data; restore never overwrites existing data. `scripts/test_backup.sh` covers the round trip, a wrong passphrase, a damaged archive and restoring over existing data.
- Compose: optional `tls` profile (Caddy with a local certificate authority), alarm variables for the server, and an ACL rule for `armor/server/alert`.
- [BACKUP_AND_TLS](docs/BACKUP_AND_TLS.md) documents what is worth backing up, that the camera key is not in the data directory, and how to enable TLS.
- Corrected the README: the Compose topology is written but has not been validated with Docker here (none is installed on the development PC) nor run.

## [0.2.0]

- Isolated CM5 test bench: deploy and install scripts with their own user, directory, ports and limits.
- Hardened Compose topology with an authenticated broker, secrets generation and required-env check.
