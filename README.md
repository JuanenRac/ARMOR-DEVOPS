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

**Honesty check - what runs today:** The CM5 bench installer has been run on a real CM5 that hosts other software, which stayed healthy. The Docker Compose topology is **validated with `docker compose config` but has not been run**.

---

## 1. 🛠️ OVERVIEW

* **CM5 test bench:** `scripts/deploy_cm5.sh` builds in a clean copy, sends one archive and runs `scripts/install_cm5.sh`, which creates its own user, its own directory and two systemd units on their own ports, with resource limits, and never touches another project ([details](docs/CM5_TEST_BENCH.md)).
* **Compose topology:** a non-anonymous Mosquitto broker with one identity per node, the server, and Studio behind an nginx that proxies `/api/`; only Studio is published, on loopback. Hardened containers, an internal core network and named volumes for state.
* **Secrets:** `scripts/generate_secrets.sh` creates random secrets and prints none; `scripts/check-required-env.sh` refuses missing, placeholder, short or repeated values.

---

## 2. 🔧 BUILD & RUN

```bash
scripts/generate_secrets.sh          # .env and secrets/ (Git-ignored)
scripts/check-required-env.sh
docker compose config --quiet && docker compose up --build
scripts/deploy_cm5.sh --host <cm5> --user <user> --key <key> --apply   # the test bench
```

See the [deployment boundary](docs/DEPLOYMENT_BOUNDARY.md).

---

## 📂 DIRECTORY STRUCTURE

```text
ARMOR-DEVOPS/
├── docker-compose.yml, .env.example, mosquitto/
├── scripts/   deploy_cm5.sh, install_cm5.sh, generate_secrets.sh, check-required-env.sh, validate-compose.sh
└── docs/      DEPLOYMENT_BOUNDARY.md, CM5_TEST_BENCH.md
```

---

## 👤 AUTHOR

**JuanenRac (Electro Hobby 3D)** · electrohobby3d@gmail.com

## 📜 LICENSE

GPL-3.0-or-later - see [LICENSE](LICENSE).
