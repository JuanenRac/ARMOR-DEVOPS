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

**Comprobación de honestidad - qué funciona hoy:** El instalador del banco CM5 se ha ejecutado en una CM5 real que aloja otro software, y este siguió sano. La topología de Docker Compose y su perfil TLS opcional se han construido y ejecutado de verdad con Docker Engine en WSL (`scripts/test_compose.sh`, 12 comprobaciones, que encontró y arregló tres fallos), pero **no en la Jetson**. Los scripts de copia de seguridad y restauración tienen una prueba de ida y vuelta que pasa.

---

## 1. 🛠️ DESCRIPCIÓN

* **Banco de pruebas CM5:** `scripts/deploy_cm5.sh` compila en una copia limpia, envía un archivo y ejecuta `scripts/install_cm5.sh`, que crea su propio usuario, su propio directorio y dos unidades systemd en puertos propios (tres con `--with-mqtt`: el Mosquitto propio de A.R.M.O.R. en el puerto 18883, comprobado en una CM5 real), con límites de recursos, y nunca toca otro proyecto ([detalles](docs/CM5_TEST_BENCH.md)).
* **Topología Compose:** un broker Mosquitto no anónimo con una identidad por nodo, el servidor y Studio tras un nginx que hace de proxy de `/api/`; solo se publica Studio, en loopback. Contenedores endurecidos, red interna y volúmenes con nombre para el estado.
* **Dispositivos en el broker del banco:** el servidor puede escuchar y ordenar `armor/device/#`; `scripts/mqtt_identity.sh add device NOMBRE` da a un dispositivo sus propios topics y `add bridge NOMBRE` a un puente Zigbee2MQTT o Shelly todos ellos.
* **Secretos:** `scripts/generate_secrets.sh` crea secretos aleatorios sin imprimir ninguno; `scripts/check-required-env.sh` rechaza valores ausentes, de ejemplo, cortos o repetidos.
* **Copia de seguridad y restauración:** `scripts/backup_data.sh` crea un archivo cifrado con AES-256, verificado y con suma de comprobación de los datos del servidor (sin evidencias salvo que se pida); `scripts/restore_data.sh` lo lista o lo restaura sin sobrescribir nunca datos existentes. La clave de cámaras **no** va en el archivo, a propósito.
* **TLS:** un perfil `tls` opcional de Compose pone Caddy, con su propia autoridad de certificados local, delante de Studio ([detalles](docs/BACKUP_AND_TLS.md)).

---

## 2. 🔧 COMPILAR Y EJECUTAR

```bash
scripts/generate_secrets.sh          # .env y secrets/ (ignorados por Git)
scripts/check-required-env.sh
docker compose config --quiet && docker compose up --build
scripts/deploy_cm5.sh --host <cm5> --user <usuario> --key <clave> --apply   # el banco de pruebas
scripts/backup_data.sh --data-dir <datos> --out-dir <copias> --passphrase-file <fichero>
```

Véase el [límite de despliegue](docs/DEPLOYMENT_BOUNDARY.md).

---

## 📂 ESTRUCTURA DE DIRECTORIOS

```text
ARMOR-DEVOPS/
├── docker-compose.yml, .env.example, mosquitto/
├── caddy/     Caddyfile (TLS)
├── scripts/   deploy_cm5, install_cm5, generate_secrets, check-required-env, validate-compose, backup_data, restore_data, test_backup, test_compose, mqtt_identity
└── docs/      DEPLOYMENT_BOUNDARY, CM5_TEST_BENCH, BACKUP_AND_TLS
```

---

## 👤 AUTOR

**JuanenRac (Electro Hobby 3D)** · electrohobby3d@gmail.com

## 📜 LICENCIA

GPL-3.0-or-later - véase [LICENSE](LICENSE).
