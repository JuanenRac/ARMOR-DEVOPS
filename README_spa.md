<p align="center">
  <img src="images/ARMOR_BANNER.svg" alt="ARMOR-DEVOPS banner" width="100%">
</p>

# 🚀 ARMOR-DEVOPS

<p align="center"><a href="README.md">🇺🇸 English</a> | 🇪🇸 <b>Español</b></p>

### Topología de despliegue y el banco de pruebas aislado en CM5

<p align="center">
  <img src="https://img.shields.io/badge/License-GPL%203.0-blue.svg" alt="GPL 3.0">
  <img src="https://img.shields.io/badge/Deploy-Docker%20Compose-2496ed.svg" alt="Deploy">
  <img src="https://img.shields.io/badge/Bench-systemd-FFB020.svg" alt="Bench">
  <img src="https://img.shields.io/badge/Maturity-functional-00E5FF.svg" alt="Maturity">
</p>

---

**Comprobación de honestidad - qué funciona hoy:** El instalador del banco CM5 se ha ejecutado en una CM5 real que aloja otro software, y este siguió sano. La topología de Docker Compose está **validada con `docker compose config` pero no se ha ejecutado**.

---

## 1. 🛠️ DESCRIPCIÓN

* **Banco de pruebas CM5:** `scripts/deploy_cm5.sh` compila en una copia limpia, envía un archivo y ejecuta `scripts/install_cm5.sh`, que crea su propio usuario, su propio directorio y dos unidades systemd en puertos propios, con límites de recursos, y nunca toca otro proyecto ([detalles](docs/CM5_TEST_BENCH.md)).
* **Topología Compose:** un broker Mosquitto no anónimo con una identidad por nodo, el servidor y Studio tras un nginx que hace de proxy de `/api/`; solo se publica Studio, en loopback. Contenedores endurecidos, red interna y volúmenes con nombre para el estado.
* **Secretos:** `scripts/generate_secrets.sh` crea secretos aleatorios sin imprimir ninguno; `scripts/check-required-env.sh` rechaza valores ausentes, de ejemplo, cortos o repetidos.

---

## 2. 🔧 COMPILAR Y EJECUTAR

```bash
scripts/generate_secrets.sh          # .env y secrets/ (ignorados por Git)
scripts/check-required-env.sh
docker compose config --quiet && docker compose up --build
scripts/deploy_cm5.sh --host <cm5> --user <usuario> --key <clave> --apply   # el banco de pruebas
```

Véase el [límite de despliegue](docs/DEPLOYMENT_BOUNDARY.md).

---

## 📂 ESTRUCTURA DE DIRECTORIOS

```text
ARMOR-DEVOPS/
├── docker-compose.yml, .env.example, mosquitto/
├── scripts/   deploy_cm5.sh, install_cm5.sh, generate_secrets.sh, check-required-env.sh, validate-compose.sh
└── docs/      DEPLOYMENT_BOUNDARY.md, CM5_TEST_BENCH.md
```

---

## 👤 AUTOR

**JuanenRac (Electro Hobby 3D)** · electrohobby3d@gmail.com

## 📜 LICENCIA

GPL-3.0-or-later - véase [LICENSE](LICENSE).
