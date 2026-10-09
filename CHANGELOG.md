# Changelog

All notable changes to this project are documented here.

## [0.4.1] - A second install keeps the HTTPS it found

- `install_cm5.sh` used to rewrite the network settings with `http://` addresses and check the health of the services over plain HTTP, so running it again on an installation that already served HTTPS dropped the certificate lines and then failed its own check. It now keeps `TLS_CERT_PATH`, `TLS_KEY_PATH` and `ARMOR_COOKIE_SECURE` when they are there, writes the `https://` addresses and checks the health over HTTPS (the certificate is not verified against the loopback address). The observation service still asks the server over `http://127.0.0.1`: on an HTTPS installation it has to be pointed at the certificate's host name by hand.
- The voice option's help says fifteen commands instead of four.

## [0.4.0] - The observation service on the bench

- **`install_cm5.sh --with-ai`** (and `deploy_cm5.sh --with-ai`, which carries the package): installs ARMOR-SERVER-AI as the unit `armor-server-ai`, as the service user with the same hardening as the others, its code belonging to root. One token, made once and kept in `armor.ai.env`, shared by the unit and the server (which loads it and opens only the four `/api/v1/ai` routes with it). An install that has it keeps it; the admin agent lists the unit.

## [0.3.9] - The voice gateway on the bench

- **`install_cm5.sh --with-voice`** (and `deploy_cm5.sh --with-voice`, which carries the package): installs ARMOR-VOICE-AI as the unit `armor-voice`, on `127.0.0.1:18090` only, running as the service user with the same hardening as the others; its code belongs to root. Two secrets in two files, made once and kept: `armor.voice.env` (the token the server uses to ask it, which the server unit loads together with `ARMOR_VOICE_URL`) and `armor.voice.secret` (the key that signs the confirmations, which only the gateway loads). An install that has it keeps it. The admin agent lists the unit, so Studio can start, stop and restart it.

## [0.3.8] - deploy_cm5.sh can install the admin agent

- **Real bug found when installing it on the bench:** the deployment archive did not carry `armor_admin_agent.py`, so `--with-admin` stopped with *cannot stat* after copying the release. The archive now includes it.

- **`deploy_cm5.sh --with-admin`** is passed on to the installer, so the admin agent can be installed from the computer that has the source in the same step as a release. Once installed the installer remembers it and keeps it in later deployments; the unit is enabled and starts at every boot.

## [0.3.7] - An admin agent, so Studio can restart services and add MQTT accounts

- **`scripts/armor_admin_agent.py` and `install_cm5.sh --with-admin`:** the server runs as an unprivileged user with no sudo, on purpose; this small separate program, as root, is the only privileged part. It listens on a Unix socket that only the group `armor` can open (and wants a token from a file only root and that group read) and can do only a closed list of things: start, stop, restart or reload the A.R.M.O.R. units; read and write five settings files at fixed paths (size limit, format check, a copy of the old file kept); and make or remove broker accounts by running `mqtt_identity.sh`. Its own files belong to root and cannot be changed by the service user. `scripts/test_admin_agent.sh` tests it with a temporary prefix and stand-ins for systemctl and the identity script.

## [0.3.6] - mqtt_identity.sh's own fix did not fix the real owner

- **`passwd`/`acl` ended up `root:root` the first time anyone added or removed an identity, crashing the broker in a restart loop:** `mosquitto_passwd`/the script's own ACL edits create a new file and do not preserve the previous owner, so each operation's own `chown` was the only thing keeping it readable by the `armor` user the service runs as. That chown set `armor:armor` - `mosquitto_passwd` itself warns this is wrong ("File owner is not root. Future versions will refuse to load this file") and the broker still starts today only because current versions tolerate it. Found on a real test bench: 300+ silent restarts, nobody noticed until MQTT was reported as "not active". Both files are now `root:armor 0640` everywhere they are touched (install_cm5.sh's first install, and all four places mqtt_identity.sh rewrites them), matching what mosquitto_passwd itself expects.

## [0.3.5] - A backup existed, but nothing ever ran it

- **`install_cm5.sh --with-backup`:** `scripts/backup_data.sh` (encrypted, self-verifying) had no schedule behind it - without a cron job or systemd timer set up by hand, a test bench had no actual backup happening at all. The flag now installs the script under `/opt/armor/bin`, generates its own random passphrase file (kept across upgrades, like the other secrets), and enables a daily `armor-backup.timer` (random delay up to 30 minutes, catches up if the machine was off at the scheduled time). Off by default, kept on upgrade once enabled, same pattern as `--with-mqtt`.

## [0.3.4]

- A GitHub Actions CI baseline (`.github/workflows/ci.yml`): validates the manifest, the version, CHANGELOG.md's heading, the seven README translations' structure and its own local Markdown links, then runs this project's real build/test through `tools/armor_project_tool.py build-test .` (vendored from ARMOR-COMMON, alongside `tools/armor_ci_validate.py` and `tools/_armor_readme_parity.py`, which do the manifest/docs checking).

## [0.3.3] - The network nodes

- `mqtt_identity.sh add network-node ID`: the identity of an ARMOR-NETWORK node, which writes `armor/network/ID/state` and nothing else and reads nothing; `remove` knows it. The broker's rules for the server (`install_cm5.sh`, on a new install and, once, on an existing one, and `mosquitto/acl.example`) let it read `armor/network/#`. `scripts/test_mqtt_identity.sh` checks the identity and its removal.

## [0.3.2] - The switch of an electrical node is not reachable until it is turned on

- `mqtt_identity.sh add electrical-node ID` now gives the node `armor/electrical/ID/state` and `.../result` (not the whole `ID/#`) and it still reads nothing.
- **`mqtt_identity.sh electrical-switching ID on|off`:** the only thing that writes the two lines that make a node's switch reachable, the node may read `armor/electrical/ID/command` and the server may write it; without both the broker itself refuses a command, whatever the server says. Idempotent, keeps `acl.before-switching`, and `off` takes both away. It is in no install.
- **A fix:** `remove` did not know `electrical-node-*` identities, so one could never be removed; it does now, and takes the server's command line for that node with it.
- `scripts/test_mqtt_identity.sh` (in `check_all.sh`) runs the script against a stand-in broker directory: nothing is reachable by default, `on` reaches only that node, is idempotent, `off` and `remove` take it all away, and bad input changes nothing.

## [0.3.1] - The server may read the electrical nodes

- **A fix found in review:** the broker's ACL for `armor-server` (written by `install_cm5.sh` on a new install and added, once, on an existing one) lets it read `armor/electrical/#` next to `armor/solar/#`. Without it the broker refused the server's subscription to the electrical nodes' messages, so nothing an electrical node published would have reached Studio. `mosquitto/acl.example` now shows the server's rules for the info, solar and electrical topics too.

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
