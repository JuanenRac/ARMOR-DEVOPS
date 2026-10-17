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
  <img src="https://img.shields.io/badge/License-GPL%203.0-blue.svg" alt="GPL 3.0">
  <img src="https://img.shields.io/badge/Deploy-Docker%20Compose-2496ed.svg" alt="Deploy">
  <img src="https://img.shields.io/badge/Bench-systemd-FFB020.svg" alt="Bench">
  <img src="https://img.shields.io/badge/Version-0.5.9-0f6cbd.svg" alt="Version">
  <img src="https://img.shields.io/badge/Maturity-established-2EA44F.svg" alt="Maturity">
</p>

---

**Honesty check - what runs today:** The CM5 bench installer has been run on a real CM5 that hosts other software, which stayed healthy, and the bench runs in daily use with the server, Studio, the network node, the observation and voice services, the broker and the two helpers below; updates of its components from GitHub (through Studio) have been done on it. The Docker Compose topology and its optional TLS profile have been built and run for real with Docker Engine in WSL (`scripts/test_compose.sh`), but **not on the Jetson**. The backup and restore scripts have a passing round-trip test, and the two helpers have their own tests. What is **not** proven: a clean install on a machine that has never seen the project, and the whole Docker topology on its target.

---

## 📋 At a glance

| | |
|---|---|
| Version | `0.5.9` |
| Maturity | Established |
| Stack | Docker Compose / Bash / YAML |
| On real hardware | Runs the CM5 test bench in daily use, on a real CM5 that hosts other software; not yet on the Jetson |

## 🎯 Overview

* **CM5 test bench:** `scripts/deploy_cm5.sh` builds in a clean copy, sends one archive and runs `scripts/install_cm5.sh`, which creates its own user, its own directory and systemd units on their own ports for the server and Studio, and, with options, the MQTT broker, the network node, the observation service, the voice gateway, the administration agent, the maintenance helper and the daily backup. It never touches what else the machine runs.
* **The maintenance helper** (`armor_maintenance_agent.py`): the updates of the installation's own components from GitHub (it downloads the release package, checks its SHA-256 and swaps it in with a rollback), the operating system's updates and an optional root console, all driven from Studio's *Updates* tab; the console is off unless turned on.
* **The administration agent** (`armor_admin_agent.py`): the one privileged part, with a closed list of services, settings files and broker accounts, so Studio never needs root.
* **Packages of each release:** `scripts/package_component.py` builds the package of a component (Studio, server, network, observation service, voice gateway, DevOps), writes its SHA-256 next to it and publishes it as a GitHub release.
* **Compose topology:** a non-anonymous Mosquitto broker with one identity per node and an ACL (including the alarm nodes and the Zigbee zones the server tells them), the server, and Studio behind an nginx that proxies `/api/`; only Studio is published, on loopback. Hardened containers, pinned images, an internal core network and named volumes for state.
* **TLS:** an optional `tls` Compose profile puts Caddy, with its own local certificate authority, in front of Studio, and a Mosquitto configuration over TLS is provided ([details](docs/BACKUP_AND_TLS.md)).
* **A host firewall for the core machine** (`scripts/firewall_core.sh`): the broker's port only from the field network, the server's and Studio's ports only from the clients' network (when it is given), in a table of its own that mentions nothing else.
* **Secrets:** `scripts/generate_secrets.sh` creates random secrets and prints none; `scripts/check-required-env.sh` refuses missing, placeholder, short or repeated values.
* **Backup and restore:** `scripts/backup_data.sh` makes an AES-256 encrypted, verified and checksummed archive of the server data (evidence excluded unless asked); `scripts/restore_data.sh` lists it or restores it without ever overwriting existing data.
* **A VPN and a name for the house, set up from Studio:** `armor_wireguard.sh` makes a WireGuard VPN in a few commands (keys on the machine, one device configuration per phone with a QR code, routing to the nodes if wanted) and `armor_ddns.sh` keeps a DuckDNS, Cloudflare or other name pointing at the house when the provider changes the address; the maintenance agent offers both to Studio and the phone, so nobody has to type a command, and a step-by-step guide in eight languages covers the router.**Signed packages:** the maintenance helper installs a package of the server, Studio or any other program only if it carries a valid Ed25519 signature of the project's release key (verified in pure Python, no extra software); a missing, wrong or tampered signature leaves the machine unchanged. An emergency override exists only as a setting in the machine's own file.

## 🧩 Role in A.R.M.O.R.

ARMOR-DEVOPS is how everything else gets onto a machine and stays up to date. It installs the server, Studio, the network node, the observation and voice services and the broker on the CM5 test bench, makes the packages of each release that [ARMOR-STUDIO](https://github.com/JuanenRac/ARMOR-STUDIO)'s *Updates* tab installs from GitHub, and holds the two small helpers that let Studio update the installation and manage its services without ever running as root.

## 📂 Repository Structure

```text
ARMOR-DEVOPS/
├── docker-compose.yml, docker-compose.tls.yml, .env.example, mosquitto/ (broker, TLS profile, ACL example)
├── caddy/     Caddyfile (TLS)
├── scripts/   deploy_cm5, install_cm5, package_component, armor_admin_agent, armor_maintenance_agent, generate_secrets, check-required-env, backup_data, restore_data, firewall_core, mqtt_identity, tests of the agents, the backup, the firewall and the Compose topology
│   └── (package_component.py packs a program the way the maintenance helper installs it; the packages are assets of the GitHub releases, not files of this repository)
└── docs/      DEPLOYMENT_BOUNDARY, CM5_TEST_BENCH, BACKUP_AND_TLS
```

## 🛠️ Development Environment

**Requirements:** Docker Engine with Compose (for the container topology), a CM5 or any Debian-based machine reachable by SSH (for the test bench), Bash, `ssh` and `tar` on the machine that deploys

```bash
scripts/generate_secrets.sh          # .env and secrets/ (Git-ignored)
scripts/check-required-env.sh
docker compose config --quiet && docker compose up --build
scripts/deploy_cm5.sh --host <cm5> --user <user> --key <key> --apply   # the test bench
scripts/backup_data.sh --data-dir <data> --out-dir <backups> --passphrase-file <file>
```

See the [deployment boundary](docs/DEPLOYMENT_BOUNDARY.md).

## 🔗 Related Projects

**A.R.M.O.R.** (Autonomous Radar & Multimodal Observation Range) is a perimeter-security system made of independent repositories. Each one has its own version, its own tests and its own README; this is the family:

* **[ARMOR-COMMON](https://github.com/JuanenRac/ARMOR-COMMON)** - Message contracts, validators, conformance vectors and generated types
* **[ARMOR-RADAR](https://github.com/JuanenRac/ARMOR-RADAR)** - Field-node firmware for ESP32-S3 with three radars and its own web panel
* **[ARMOR-SOLAR](https://github.com/JuanenRac/ARMOR-SOLAR)** - Solar inverter and battery protocols and the messages of a gateway node
* **[ARMOR-ELECTRICAL](https://github.com/JuanenRac/ARMOR-ELECTRICAL)** - Electrical node: meters, the message of the network's readings and the rules for switching
* **[ARMOR-ALARM](https://github.com/JuanenRac/ARMOR-ALARM)** - Alarm node and panel: zones, arming, delays, siren and PIN, with the server or without it
* **[ARMOR-HMI](https://github.com/JuanenRac/ARMOR-HMI)** - Touch panel: the state of the system on a wall screen, arming and acknowledging, and the home of the voice assistant
* **[ARMOR-NETWORK](https://github.com/JuanenRac/ARMOR-NETWORK)** - The local network: its devices, the internet and what changes
* **[ARMOR-SERVER](https://github.com/JuanenRac/ARMOR-SERVER)** - Central coordinator: telemetry, alarms, devices, solar readings and cameras
* **[ARMOR-STUDIO](https://github.com/JuanenRac/ARMOR-STUDIO)** - Web console: cameras, radar, alarms, solar energy and the 2D/3D site designer
* **[ARMOR-ANDROID-CONTROL](https://github.com/JuanenRac/ARMOR-ANDROID-CONTROL)** - Android operator client with a live 2D/3D radar
* **[ARMOR-SERVER-AI](https://github.com/JuanenRac/ARMOR-SERVER-AI)** - Visual inference policy that explains its decisions and never actuates
* **[ARMOR-VISION](https://github.com/JuanenRac/ARMOR-VISION)** - Camera zones, masks and detection rules for the Jetson Orin NX
* **[ARMOR-VOICE-AI](https://github.com/JuanenRac/ARMOR-VOICE-AI)** - Offline voice intents with a confirmation that cannot be forged
* **[ARMOR-HARDWARE](https://github.com/JuanenRac/ARMOR-HARDWARE)** - Enclosures, electronics and the bench acceptance matrix
* **ARMOR-DEVOPS** (this repository) - Deployment, the CM5 test bench, backup and TLS
* **[ARMOR-SIMULATOR](https://github.com/JuanenRac/ARMOR-SIMULATOR)** - Offline telemetry simulator with repeatable faults
* **[ARMOR-UPDATER](https://github.com/JuanenRac/ARMOR-UPDATER)** - Detects, installs and updates the ecosystem's own repositories
* **[ARMOR-DOCS](https://github.com/JuanenRac/ARMOR-DOCS)** - Architecture, security baseline and the capability matrix

## 📚 Documentation & Community

Where to read more:

* [Capability matrix: what is proven and what is not](https://github.com/JuanenRac/ARMOR-DOCS/blob/main/docs/CAPABILITY_MATRIX.md)
* [Project catalogue: versions and how the repositories depend on each other](https://github.com/JuanenRac/ARMOR-DOCS/blob/main/docs/PROJECT_CATALOG.md)
* [Changelog of this repository](CHANGELOG.md)
* [License (GPL-3.0-or-later)](LICENSE)
* Questions, ideas and reports: electrohobby3d@gmail.com

## 👤 AUTHOR

**JuanenRac (Electro Hobby 3D)** · electrohobby3d@gmail.com

## 📜 LICENSE

GPL-3.0-or-later - see [LICENSE](LICENSE).
