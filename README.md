<p align="center">
  <img src="images/ARMOR_BANNER.svg" alt="ARMOR-DEVOPS banner" width="100%">
</p>

# 🚀 ARMOR-DEVOPS

<p align="center">
  🇺🇸 <b>English</b> |
  <a href="README_spa.md">🇪🇸 Español</a> |
  <a href="README_fra.md">🇫🇷 Français</a> |
  <a href="README_ita.md">🇮🇹 Italiano</a> |
  <a href="README_deu.md">🇩🇪 Deutsch</a> |
  <a href="README_zho.md">🇨🇳 简体中文</a> |
  <a href="README_jpn.md">🇯🇵 日本語</a> |
  <a href="README_por.md">🇵🇹 Português</a>
</p>

### Deployment, the CM5 test bench, its updates from GitHub and the upkeep of the installation

<p align="center">
  <img src="https://img.shields.io/badge/License-GPL%203.0--or--later-blue.svg" alt="GPL 3.0 or later">
  <img src="https://img.shields.io/badge/Deploy-Docker%20Compose-2496ed.svg" alt="Deploy">
  <img src="https://img.shields.io/badge/Bench-systemd-FFB020.svg" alt="Bench">
  <img src="https://img.shields.io/badge/Version-0.6.8-0f6cbd.svg" alt="Version">
  <img src="https://img.shields.io/badge/Maturity-established-2EA44F.svg" alt="Maturity">
</p>

---

**Honesty check - what runs today:** The CM5 bench installer has been run on a real CM5 that hosts other software, which stayed healthy, and the bench runs in daily use with the server, Studio, the network node, the observation and voice services, the broker and the two helpers below; updates of its components from GitHub (through Studio) have been done on it. The Docker Compose topology and its optional TLS profile have been built and run for real with Docker Engine in WSL (`scripts/test_compose.sh`), but **not on the Jetson**. The backup and restore scripts have a passing round-trip test, and the two helpers have their own tests. What is **not** proven: a clean install on a machine that has never seen the project, and the whole Docker topology on its target.

---

## 📋 At a glance

| | |
|---|---|
| Version | `0.6.8` |
| Maturity | Established |
| Role | Deployment kit: CM5 test bench installer, release packages, two helpers, Compose topology |
| Stack | Bash, Python 3 (standard library), Docker Compose, Mosquitto, Caddy, nginx, systemd |
| Tests | A test script for each part (`scripts/test_*.sh` and `test_*.py`); the Compose topology is built and run with Docker in WSL |
| Contract | Ports of the bench: server 18080, Studio 18081, MQTT 18883 (never 1883), voice 18090 |
| Runs on | A CM5 or any Debian-based machine reachable by SSH; Docker Engine with Compose for the container topology |
| On real hardware | Runs the CM5 test bench in daily use, on a real CM5 that hosts other software; not yet on the Jetson |
| License | GPL-3.0-or-later |

**Jump to:** [Overview](#-overview) · [Architecture](#-architecture) · [Security](#-security--safety) · [Interfaces](#-interfaces) · [Configuration](#-configuration) · [Quick start](#-quick-start) · [Testing](#-testing) · [Troubleshooting](#-troubleshooting) · [Structure](#-repository-structure) · [Related](#-related-projects)

## 🚦 Project status

Each line is one part of this repository and the light says how far it is today. It is written from what the repository can show (tests, builds, runs), not from what is planned.

🟢 Done and verified · 🟡 Works, with known limits · 🟠 Partly done or not verified yet · 🔴 Not done or not working

| Area | State | What it means here |
|---|---|---|
| Software | 🟡 | The CM5 bench installer has run on a real CM5 that hosts other software, which stayed healthy; a clean install on a machine that has never seen the project is not proven. |
| Tests | 🟡 | The backup and restore scripts have a passing round-trip test, the two helpers have their own tests, and the Docker topology with its optional TLS profile was built and run with Docker Engine in WSL; the whole topology has not run on its target. |
| Hardware | 🟡 | It runs the CM5 test bench in daily use; nothing has run on the Jetson. |
| Updates | 🟢 | Updates of the components from GitHub, through Studio, have been done on the CM5 test bench. |
| Documentation | 🟢 | Eight languages and the changelog are up to date. |

## 🎯 Overview

* **CM5 test bench:** `scripts/deploy_cm5.sh` builds in a clean copy, sends one archive and runs `scripts/install_cm5.sh`, which creates its own user, its own directory and systemd units on their own ports for the server and Studio, and, with options, the MQTT broker, the network node, the observation service, the voice gateway, the administration agent, the maintenance helper and the daily backup. It never touches what else the machine runs.
* **The maintenance helper** (`armor_maintenance_agent.py`): the updates of the installation's own components from GitHub (it downloads the release package, checks its SHA-256 and swaps it in with a rollback), the operating system's updates and an optional root console, all driven from Studio's *Updates* tab; the console is off unless turned on. It keeps the six newest copies it sets aside, and fewer when the disk is nearly full (`ARMOR_MAINT_MIN_FREE_MB` in its settings file: 500 by default, 0 turns it off).
* **The administration agent** (`armor_admin_agent.py`): the one privileged part, with a closed list of services, settings files and broker accounts, so Studio never needs root.
* **Packages of each release:** `scripts/package_component.py` builds the package of a component (Studio, server, network, observation service, voice gateway, DevOps), writes its SHA-256 next to it and publishes it as a GitHub release.
* **Compose topology:** a non-anonymous Mosquitto broker with one identity per node and an ACL (including the alarm nodes and the Zigbee zones the server tells them), the server, and Studio behind an nginx that proxies `/api/`; only Studio is published, on loopback. Hardened containers, pinned images, an internal core network and named volumes for state.
* **TLS:** an optional `tls` Compose profile puts Caddy, with its own local certificate authority, in front of Studio, and a Mosquitto configuration over TLS is provided ([details](docs/BACKUP_AND_TLS.md)).
* **A host firewall for the core machine** (`scripts/firewall_core.sh`): the broker's port only from the field network, the server's and Studio's ports only from the clients' network (when it is given), in a table of its own that mentions nothing else.
* **Secrets:** `scripts/generate_secrets.sh` creates random secrets and prints none; `scripts/check-required-env.sh` refuses missing, placeholder, short or repeated values.
* **Backup and restore:** `scripts/backup_data.sh` makes an AES-256 encrypted, verified and checksummed archive of the server data (evidence excluded unless asked); `scripts/restore_data.sh` lists it or restores it without ever overwriting existing data.
* **A VPN and a name for the house, set up from Studio:** `armor_wireguard.sh` makes a WireGuard VPN in a few commands (keys on the machine, one device configuration per phone with a QR code, routing to the nodes if wanted) and `armor_ddns.sh` keeps a DuckDNS, Cloudflare or other name pointing at the house when the provider changes the address; the maintenance agent offers both to Studio and the phone, so nobody has to type a command, and a step-by-step guide in eight languages covers the router.
* **Signed packages:** the maintenance helper installs a package of the server, Studio or any other program only if it carries a valid Ed25519 signature of the project's release key (verified in pure Python, no extra software); a missing, wrong or tampered signature leaves the machine unchanged. An emergency override exists only as a setting in the machine's own file.
* **An optional encrypted door to the broker (MQTT over TLS):** `scripts/armor_mqtt_tls.sh` makes a certificate authority for the installation (its key stays on the machine, mode `0600`), a broker certificate for the machine's names and addresses and a second Mosquitto listener on 8883 next to the plain one, which it never touches; it is idempotent and has `status`, `export-ca`, `server-tls` and `remove` (files are put aside, never deleted). Tested with OpenSSL, including real handshakes, and on a real Mosquitto 2.0 ([guide](docs/MQTT_TLS.md)).
* **Health reports allowed:** the broker's rules let each node write its own `armor/health/<node>` and the server read `armor/health/#`; `mqtt_identity.sh add` writes the line for every kind of node and `mqtt_identity.sh health-report <role> <node>` adds it to a node installed earlier (idempotent, the previous rules are kept).
* **Broker rules for node control:** only the server's identity may publish `armor/control/+/command` (which covers `armor/control/all/command`); each node reads its own command topic and the broadcast one and writes its own answer on `armor/control/<node>/result`, and nothing more, so no node can command another and a stolen node password cannot restart the others. `mqtt_identity.sh node-control` adds the three lines to a node installed before, and the ACL test checks every kind of node.

## 🧩 Role in A.R.M.O.R.

ARMOR-DEVOPS is how everything else gets onto a machine and stays up to date. It installs the server, Studio, the network node, the observation and voice services and the broker on the CM5 test bench, makes the packages of each release that [ARMOR-STUDIO](https://github.com/JuanenRac/ARMOR-STUDIO)'s *Updates* tab installs from GitHub, and holds the two small helpers that let Studio update the installation and manage its services without ever running as root.

| It talks to | How | What for |
|---|---|---|
| ARMOR-STUDIO | its *Updates* tab asks the maintenance helper over a local socket | it never needs root |
| GitHub Releases | `package_component.py` publishes the package with its SHA-256 and signature | the components to install |
| ARMOR-SERVER, ARMOR-NETWORK, ARMOR-SERVER-AI, ARMOR-VOICE-AI | installed as systemd units of their own | the services of the bench |
| ARMOR-UPDATER | separate | the tool of a person who keeps a copy of the family on a PC; this repository is for the CM5 and the Compose topology |

## 🏛️ Architecture

<p align="center">
  <img src="images/architecture.svg" alt="ARMOR-DEVOPS architecture: where the packages come from, the deployment kit with its installer, helpers and Compose topology, and the bench and broker it sets up" width="100%">
</p>

## 🔒 Security & Safety

| Threat | Defence |
|---|---|
| Interfering with other software on the CM5 | Its own user, directory and ports (server 18080, Studio 18081, MQTT 18883 and voice 18090, all between 1024 and 65535 and all different, never the standard 1883); the system firewall is not touched |
| An open or unauthenticated broker | `allow_anonymous false`, a password file and an ACL (secrets mounted in `/run/secrets`), one identity per node; only the server may publish `armor/control/+/command`; each node reads its own command and the broadcast one and writes only its own `armor/control/<node>/result` and `armor/health/<node>`; the server reads `armor/health/#` |
| Accidental listening on the network | Compose publishes the broker and Studio only on `127.0.0.1` unless `ARMOR_MQTT_BIND`, `ARMOR_STUDIO_BIND` (and `ARMOR_TLS_BIND` for Caddy) say otherwise |
| MQTT and Studio in clear | Optional: a second Mosquitto listener on 8883 next to the plain one (`armor_mqtt_tls.sh`: its own authority, key in mode `0600`, certificate for the machine's names, idempotent, never touches the plain one) and a `tls` Compose profile with Caddy and its own local authority |
| The core machine open to everyone | `firewall_core.sh` writes a table of its own (`/etc/armor/firewall.nft`, with a rollback unit): the broker's port only from the field network, the server's and Studio's only from the clients' network; `check` verifies it with `nft -c` |
| Weak or printed secrets | `generate_secrets.sh` creates random secrets and prints none; `check-required-env.sh` refuses missing, placeholder, short or repeated values |
| A stolen backup | `backup_data.sh` makes an AES-256 encrypted, verified and checksummed archive (evidence excluded unless asked); `restore_data.sh` lists it or restores it without ever overwriting existing data |
| A fake update of a component | The maintenance helper downloads the release package, checks its SHA-256 and the Ed25519 signature of the project's release key (verified in pure Python), and swaps it in with a rollback; a missing, wrong or tampered signature leaves the machine unchanged |
| Root reachable from Studio | Never needed: the administration agent (`armor_admin_agent.py`) has a closed list of services, settings files and broker accounts; the root console of the maintenance helper is off unless turned on |

Containers are hardened, images pinned, the `core` network internal and the state in named volumes. The two helpers use local Unix sockets, so their tests need Linux. A clean install on a machine that has never seen the project and the whole Docker topology on its target are not proven; there has been no independent review.

## 🔌 Interfaces

| Route | Auth | What it does |
|---|---|---|
| `scripts/deploy_cm5.sh --host <cm5> --user <user> --key <key> --apply` | - | builds in a clean copy, sends one archive over SSH and runs `install_cm5.sh` |
| `scripts/install_cm5.sh --public-host HOST [--apply]` | - | creates the user, directory and systemd units; `--server-port`, `--studio-port`, `--mqtt-port` and `--also-reach` adjust it; without `--apply` it only shows the plan |
| `scripts/package_component.py` | - | packs Studio, the server, the network node, the observation service, the voice gateway or DevOps the way the maintenance helper installs it, writes its SHA-256 and publishes it as a GitHub release |
| `scripts/generate_secrets.sh`  `scripts/check-required-env.sh` | - | `.env` and `secrets/` (ignored by Git); the check refuses missing, placeholder, short or repeated values |
| `scripts/backup_data.sh --data-dir <d> --out-dir <o> --passphrase-file <f>` | - | the encrypted, verified archive of the server data |
| `scripts/restore_data.sh` | - | lists an archive or restores it without overwriting existing data |
| `scripts/firewall_core.sh apply, check --field <net> [--clients <net>]` | - | the firewall table of the core machine; `check` verifies it (`FIREWALL_CHECK=SKIP` when `nft` is not installed) |
| `scripts/mqtt_identity.sh add`  `health-report <role> <node>`  `node-control` | - | writes the broker line of every kind of node; adds health reports and node control to a node installed earlier (idempotent) |
| `scripts/armor_mqtt_tls.sh`  `armor_wireguard.sh`  `armor_ddns.sh`  `armor_tls_check.sh` | - | the encrypted door of the broker (`status`, `export-ca`, `server-tls`...), the WireGuard VPN with a QR per phone, a DuckDNS, Cloudflare or other name for the house, and the check of remote access; Studio offers them without typing a command |

The two helpers (`armor_admin_agent.py`, `armor_maintenance_agent.py`) listen on local Unix sockets and so do not run on Windows. The Compose file starts the broker (Mosquitto), the server and Studio (nginx, which proxies `/api/`), and a `tls` profile adds Caddy; only Studio is published, on loopback by default (`127.0.0.1:8088`, TLS on 8443). The packages of each release are assets of the GitHub releases, not files of this repository. The log of a system update says `downloading: N%` every ten percent, so a slow link does not look like a stuck update, and an update installs the dependencies again (`npm ci`) only when what the lock file says about them changed, not just because the project has a new version.

## ⚙️ Configuration

| Setting | Default | What it does |
|---|---|---|
| `install_cm5.sh` | 18080  18081  18883  18090 | `--server-port`, `--studio-port`, `--mqtt-port` (the installed one is kept if it is not repeated) and the voice port; all between 1024 and 65535 and different; the broker address goes to `PREFIX/etc/armor.mqtt.env` |
| `ARMOR_MQTT_BIND`  `ARMOR_STUDIO_BIND` | 127.0.0.1 | where Compose publishes the broker and Studio |
| `ARMOR_PUBLIC_ORIGIN` | http://127.0.0.1:8088 | the origin Studio is reached by |
| `ARMOR_TLS_BIND`  `ARMOR_TLS_PORT`  `ARMOR_TLS_HTTP_PORT` | 8443 | Caddy of the `tls` profile |
| `.env`  `.env.example` | - | created by `generate_secrets.sh`, ignored by Git; the example lists every variable |

The root console of the maintenance helper is a setting of the machine's own file and is off by default; the firewall and TLS are options of the installer, not defaults. Details in [docs/CM5_TEST_BENCH.md](docs/CM5_TEST_BENCH.md).

## 🚀 Quick start

**Requirements:** Docker Engine with Compose (for the container topology), a CM5 or any Debian-based machine reachable by SSH (for the test bench), Bash, `ssh` and `tar` on the machine that deploys.

```bash
scripts/generate_secrets.sh                                                            # `.env` and `secrets/` (ignored by Git)
scripts/check-required-env.sh
docker compose config --quiet && docker compose up --build                             # the container topology
scripts/deploy_cm5.sh --host <cm5> --user <user> --key <key> --apply                   # the test bench
scripts/backup_data.sh --data-dir <data> --out-dir <backups> --passphrase-file <file>  # an encrypted backup
```

See the [deployment boundary](docs/DEPLOYMENT_BOUNDARY.md) and the [test bench](docs/CM5_TEST_BENCH.md).

## 🧪 Testing

| Area | What it covers |
|---|---|
| `test_admin_agent.py`  `.sh` | the closed list of the administration agent (needs Linux: Unix sockets) |
| `test_maintenance_agent.py`  `.sh` | the maintenance helper: download, SHA-256, signature, swap and rollback (needs Linux) |
| `test_package_component.py`  `test_registry.py`  `test_remote_access.py` | the packages, the list of components and the remote-access helpers |
| `test_backup.sh`  `test_env_and_restore.sh` | the backup and restore round trip, the secrets and the environment check |
| `test_compose.sh`  `validate-compose.sh` | the Compose topology and its TLS profile, built and run with Docker Engine in WSL |
| `test_firewall.sh`  `test_install_plan.sh`  `test_mqtt_identity.sh`  `test_mqtt_tls.sh`  `test_tls_check.sh`  `test_wireguard.sh`  `test_ddns.sh` | the firewall, the installer's plan, the broker identities, MQTT over TLS, the TLS check, the VPN and the dynamic name |

The Python tests run with `python -m unittest discover -s scripts -p "test_*.py"`; on Windows the three that need Unix sockets cannot run. The scripts need Bash, WSL, Docker or root, and have to be run on Linux. There is no single count of tests yet: Project status says what has been run. GitHub Actions runs the A.R.M.O.R. baseline on every push and pull request: the validation of the manifest, version, changelog and README parity, then the project's own build and tests.

## 🏗️ Build & Release

Nothing is compiled: it is scripts, a Compose file and Python helpers. `scripts/package_component.py` builds the package of a component and writes its SHA-256 next to it; the packages are assets of the GitHub releases, not files of this repository. The version lives in `armor.project.json` and in the README badge (read from the manifest); each version has its entry in [CHANGELOG.md](CHANGELOG.md).

## 🩺 Troubleshooting

| You see | Because | Do |
|---|---|---|
| `ports must be numbers between 1024 and 65535`  `the server and studio ports must differ` | a port of `install_cm5.sh` is out of range or repeated | use different ports between 1024 and 65535 (never the standard 1883) |
| `--also-reach must look like http://HOST:PORT=http://HOST:PORT` | the extra address is not written as Studio address = server address | write `--also-reach http://<host>:<studio-port>=http://<host>:<server-port>` |
| `FIREWALL_CHECK=SKIP nft is not installed here` | `nft` is missing, so `firewall_core.sh check` cannot verify the table | install nftables on the machine, then check again |
| `AttributeError: module 'socketserver' has no attribute 'UnixStreamServer'` | the tests of the two helpers are being run on Windows | run them on Linux (or WSL) |

## 📂 Repository Structure

<p align="center">
  <img src="images/repository-structure.svg" alt="Repository structure of ARMOR-DEVOPS" width="100%">
</p>

<details>
<summary>Text version of the tree</summary>

```text
ARMOR-DEVOPS/
├── scripts/
│   ├── deploy_cm5.sh install_cm5.sh                      deploy to the bench, install it
│   ├── package_component.py                              the package of each release
│   ├── armor_admin_agent.py armor_maintenance_agent.py   the two helpers of Studio
│   ├── generate_secrets.sh check-required-env.sh         random secrets; refuse weak ones
│   ├── backup_data.sh restore_data.sh                    encrypted backup and restore
│   ├── firewall_core.sh mqtt_identity.sh                 firewall and broker identities
│   ├── armor_mqtt_tls.sh armor_tls_check.sh              MQTT over TLS and its check
│   ├── armor_ddns.sh armor_wireguard.sh                  a name for the house and a VPN
│   └── test_*.py test_*.sh validate-compose.sh           the tests of the helpers and scripts
├── docker-compose.yml docker-compose.tls.yml             broker, server, Studio; TLS profile
├── mosquitto/                                            mosquitto.conf, TLS config, acl.example
├── caddy/                                                Caddyfile: HTTPS in front of Studio
├── docs/                                                 DEPLOYMENT_BOUNDARY, CM5_TEST_BENCH, BENCH_TESTS, BACKUP_AND_TLS, MQTT_TLS, HTTPS_PAIRING, REMOTE_ACCESS, SIGNED_PACKAGES (the last four also in eight languages)
├── tools/                                                the shared CI checks and project tooling
├── images/                                               banner, icon and the pictures of the README
├── .github/                                              CI workflow, dashboard notice, issue and pull-request templates
├── armor.project.json                                    manifest: version, role, maturity
├── CHANGELOG.md                                          what changed in each version
├── run.sh run.bat                                        start, shared workflow
├── build.sh build.bat                                    build and test, shared workflow
├── build-test.sh build-test.bat                          build, test and package
├── test.sh test.bat                                      only the tests, never the version
└── SECURITY.md SUPPORT.md CONTRIBUTING.md CODE_OF_CONDUCT.md LICENSE
```

</details>

## 🗺️ Roadmap & Known limits

**Known limits today**

* A clean install on a machine that has never seen the project is not proven.
* The whole Docker topology has been built and run with Docker Engine in WSL, but not on its target, the Jetson.
* There is no single count of tests, and the tests of the two helpers need Linux.
* No independent security review.

**Next**

* A clean install on a new machine, and the Docker topology on the Jetson.

## 🌍 Languages

README and texts exist in English, Spanish, French, Italian, German, Chinese, Japanese and European Portuguese.

## 🔗 Related Projects

**A.R.M.O.R.** (Autonomous Radar & Multimodal Observation Range) is a perimeter-security system made of independent repositories. Each one has its own version, its own tests and its own README; this is the family:

* **[ARMOR-COMMON](https://github.com/JuanenRac/ARMOR-COMMON)** - Message contracts, validators, conformance vectors and generated types
* **[ARMOR-NODE-RADAR](https://github.com/JuanenRac/ARMOR-NODE-RADAR)** - Field-node firmware for ESP32-S3 with three radars and its own web panel
* **[ARMOR-NODE-SOLAR](https://github.com/JuanenRac/ARMOR-NODE-SOLAR)** - Solar inverter and battery protocols and the messages of a gateway node
* **[ARMOR-NODE-ELECTRICAL](https://github.com/JuanenRac/ARMOR-NODE-ELECTRICAL)** - Electrical node: meters, the message of the network's readings and the rules for switching
* **[ARMOR-NODE-ALARM](https://github.com/JuanenRac/ARMOR-NODE-ALARM)** - Alarm node and panel: zones, arming, delays, siren and PIN, with the server or without it
* **[ARMOR-NODE-HMI](https://github.com/JuanenRac/ARMOR-NODE-HMI)** - Touch panel: the state of the system on a wall screen, arming and acknowledging, and the home of the voice assistant
* **[ARMOR-NETWORK](https://github.com/JuanenRac/ARMOR-NETWORK)** - The local network: its devices, the internet and what changes
* **[ARMOR-SERVER](https://github.com/JuanenRac/ARMOR-SERVER)** - Central coordinator: telemetry, alarms, devices, solar readings and cameras
* **[ARMOR-STUDIO](https://github.com/JuanenRac/ARMOR-STUDIO)** - Web console: cameras, radar, alarms, solar energy and the 2D/3D site designer
* **[ARMOR-ANDROID-CONTROL](https://github.com/JuanenRac/ARMOR-ANDROID-CONTROL)** - Android operator client with a live 2D/3D radar
* **[ARMOR-IOS-CONTROL](https://github.com/JuanenRac/ARMOR-IOS-CONTROL)** - iPhone operator client
* **[ARMOR-SERVER-AI](https://github.com/JuanenRac/ARMOR-SERVER-AI)** - Visual inference policy that explains its decisions and never actuates
* **[ARMOR-VISION](https://github.com/JuanenRac/ARMOR-VISION)** - Camera zones, masks and detection rules for the Jetson Orin NX
* **[ARMOR-VOICE-AI](https://github.com/JuanenRac/ARMOR-VOICE-AI)** - Offline voice intents with a confirmation that cannot be forged
* **[ARMOR-HARDWARE](https://github.com/JuanenRac/ARMOR-HARDWARE)** - Enclosures, electronics and the bench acceptance matrix
* **ARMOR-DEVOPS** (this repository) - Deployment, the CM5 test bench, backup and TLS
* **[ARMOR-SIMULATOR](https://github.com/JuanenRac/ARMOR-SIMULATOR)** - Offline telemetry simulator with repeatable faults
* **[ARMOR-UPDATER](https://github.com/JuanenRac/ARMOR-UPDATER)** - Detects, installs and updates the ecosystem's own repositories
* **[ARMOR-DOCS](https://github.com/JuanenRac/ARMOR-DOCS)** - Architecture, security baseline and the capability matrix

## 📚 Documentation

* [DEPLOYMENT_BOUNDARY](docs/DEPLOYMENT_BOUNDARY.md): what this repository deploys and what it does not
* [CM5_TEST_BENCH](docs/CM5_TEST_BENCH.md): the installer, the units, the ports and the helpers on the bench
* [BENCH_TESTS](docs/BENCH_TESTS.md): how the bench is tested
* [BACKUP_AND_TLS](docs/BACKUP_AND_TLS.md): backup and restore, and the TLS profile of Compose
* [MQTT_TLS](docs/MQTT_TLS.md): the encrypted door of the broker (also in eight languages)
* [HTTPS_PAIRING](docs/HTTPS_PAIRING.md): trusting the certificate of a node (also in eight languages)
* [REMOTE_ACCESS](docs/REMOTE_ACCESS.md): VPN, a name for the house and the router, step by step (also in eight languages)
* [SIGNED_PACKAGES](docs/SIGNED_PACKAGES.md): the signature of the packages (also in eight languages)
* [Capability matrix: what is proven and what is not](https://github.com/JuanenRac/ARMOR-DOCS/blob/main/docs/CAPABILITY_MATRIX.md)
* [Project catalogue: versions and how the repositories depend on each other](https://github.com/JuanenRac/ARMOR-DOCS/blob/main/docs/PROJECT_CATALOG.md)
* [Changelog of this repository](CHANGELOG.md)

## 🤝 Contributing & Community

* Before a pull request run `python -I tools/armor_ci_validate.py` and the tests: both must pass. See [CONTRIBUTING.md](CONTRIBUTING.md) and the [code of conduct](CODE_OF_CONDUCT.md).
* The README exists in eight languages and is generated from the sources in ARMOR-DOCS: a change to the text is made there.
* A change to a message between components starts in ARMOR-COMMON.
* Do not describe as working on a board what has only been built.
* Report a vulnerability privately: [SECURITY.md](SECURITY.md). Questions, ideas and reports: electrohobby3d@gmail.com ([SUPPORT.md](SUPPORT.md)).

## 👤 AUTHOR

**JuanenRac (Electro Hobby 3D)** · electrohobby3d@gmail.com

## 📜 LICENSE

GPL-3.0-or-later - see [LICENSE](LICENSE).
