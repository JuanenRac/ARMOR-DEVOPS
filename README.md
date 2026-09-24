<p align="center">
  <img src="images/ARMOR_BANNER.svg" alt="ARMOR-DEVOPS banner" width="100%">
</p>

# 🚀 ARMOR-DEVOPS

<p align="center">🇺🇸 <b>English</b> | <a href="README_spa.md">🇪🇸 Español</a></p>

### Deployment topology and the isolated CM5 test bench

<p align="center">
  <img src="https://img.shields.io/badge/License-GPL%203.0-blue.svg" alt="GPL 3.0">
  <img src="https://img.shields.io/badge/Deploy-Docker%20Compose-2496ed.svg" alt="Deploy">
  <img src="https://img.shields.io/badge/Bench-systemd-FFB020.svg" alt="Bench">
  <img src="https://img.shields.io/badge/Maturity-functional-00E5FF.svg" alt="Maturity">
</p>

---

**Honesty check - what runs today:** The CM5 bench installer has been run on a real CM5 that hosts other software, which stayed healthy. The Docker Compose topology (and its optional TLS profile) is written and parsed as YAML, but **Docker is not installed on the development PC, so it has been neither validated with `docker compose config` nor run**. The backup and restore scripts have a passing round-trip test.

---

## 1. 🛠️ OVERVIEW

* **CM5 test bench:** `scripts/deploy_cm5.sh` builds in a clean copy, sends one archive and runs `scripts/install_cm5.sh`, which creates its own user, its own directory and two systemd units on their own ports, with resource limits, and never touches another project ([details](docs/CM5_TEST_BENCH.md)).
* **Compose topology:** a non-anonymous Mosquitto broker with one identity per node, the server, and Studio behind an nginx that proxies `/api/`; only Studio is published, on loopback. Hardened containers, an internal core network and named volumes for state.
* **Secrets:** `scripts/generate_secrets.sh` creates random secrets and prints none; `scripts/check-required-env.sh` refuses missing, placeholder, short or repeated values.
* **Backup and restore:** `scripts/backup_data.sh` makes an AES-256 encrypted, verified and checksummed archive of the server data (evidence excluded unless asked); `scripts/restore_data.sh` lists it or restores it without ever overwriting existing data. The camera key is deliberately **not** in the archive.
* **TLS:** an optional `tls` Compose profile puts Caddy, with its own local certificate authority, in front of Studio ([details](docs/BACKUP_AND_TLS.md)).

---

## 2. 🔧 BUILD & RUN

```bash
scripts/generate_secrets.sh          # .env and secrets/ (Git-ignored)
scripts/check-required-env.sh
docker compose config --quiet && docker compose up --build
scripts/deploy_cm5.sh --host <cm5> --user <user> --key <key> --apply   # the test bench
scripts/backup_data.sh --data-dir <data> --out-dir <backups> --passphrase-file <file>
```

See the [deployment boundary](docs/DEPLOYMENT_BOUNDARY.md).

---

## 📂 DIRECTORY STRUCTURE

```text
ARMOR-DEVOPS/
├── docker-compose.yml, .env.example, mosquitto/
├── caddy/     Caddyfile (TLS)
├── scripts/   deploy_cm5, install_cm5, generate_secrets, check-required-env, validate-compose, backup_data, restore_data, test_backup
└── docs/      DEPLOYMENT_BOUNDARY, CM5_TEST_BENCH, BACKUP_AND_TLS
```

---

## 👤 AUTHOR

**JuanenRac (Electro Hobby 3D)** · electrohobby3d@gmail.com

## 📜 LICENSE

GPL-3.0-or-later - see [LICENSE](LICENSE).
