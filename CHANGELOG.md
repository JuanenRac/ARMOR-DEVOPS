# Changelog

All notable changes to this project are documented here.

## [0.3.0] - A host firewall for the core machine

- **`scripts/firewall_core.sh`** turns the network design into rules for the machine that runs the server, the broker and Studio: the broker's port is reachable only from the **field** network (`--field`, required) and from the machine itself, and, when `--clients` is given, the server's and Studio's ports only from the **clients'** network. The rules live in one table of their own (`inet armor_core`) that mentions only A.R.M.O.R.'s ports and has an *accept* policy: SSH, another project's ports and everything else are left as they were. The ports are the ones `install_cm5.sh` uses and can be changed.
- **A mistake cannot shut you out:** `apply --rollback-after 120` removes the rules again after that many seconds unless `confirm` is run; `apply --persist` loads them at every boot; `revert` removes the table and the boot unit; `print` and `check` change nothing. Networks, ports and names are validated (IPv4 only, no shell text gets through).
- **`scripts/test_firewall.sh`** (36 checks): the rules printed for the standard case, without clients, with other ports and a trusted interface and several networks; that no rule sets a drop policy or mentions another port; and every refusal (a missing field network, a bad network, a bad port, two services on one port, a tampered interface name, an unknown option). `nft -c` also checks the syntax when nft is installed (it is not on the development machine, so that step was skipped).
- **Not done:** loading the rules on the CM5 (Monday's bench), and the VLANs themselves, which are the router's and the switch's job. The rules act on the machine's input, so they cover services installed natively (`install_cm5.sh`); a port that Docker publishes is forwarded, not input, and stays on loopback behind Caddy as `docker-compose.yml` has it.
- `mqtt_identity.sh add electrical-node ID`: the identity of an ARMOR-ELECTRICAL node, which writes `armor/electrical/ID/#` and nothing else and reads nothing.

## [0.2.9] - An identity for the solar nodes

- `mqtt_identity.sh add solar-node <id>` makes the broker identity of an ARMOR-SOLAR node (`solar-node-<id>`): it may write `armor/solar/<id>/#` and nothing else, and it reads nothing. `remove` knows the new kind.

## [0.2.8] - A plainer rule for the install prefix

- `install_cm5.sh` accepts as `--prefix` only one directory directly under `/opt` (before it refused a list of names), and still refuses an existing directory that is not an A.R.M.O.R. install. The usage lines in the scripts and the bench guide use placeholders for the account and key names.

## [0.2.7] - The server may read the nodes' information and the solar topic

- The broker's access list for the server (`install_cm5.sh`, and `mqtt_identity.sh` when it makes one) lets it read `armor/node/+/info` (it could not, so a node's panel address never arrived over MQTT) and `armor/solar/#`; an installation made earlier gets both on the next run.

## [0.2.6] - Broker access for the node's panel information and pins

- `mqtt_identity.sh add node` now also lets a node write `armor/node/<id>/info` (where its panel is) next to its telemetry and health. `mqtt_identity.sh upgrade-node <id>` adds that and `armor/device/<id>/#` (the pins the node lends to the server) to a node created earlier, idempotently, keeping the previous ACL as `acl.before-upgrade`. The ACL example shows both.

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
