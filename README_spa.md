<p align="center">
  <img src="images/ARMOR_BANNER.svg" alt="ARMOR-DEVOPS banner" width="100%">
</p>

# 🚀 ARMOR-DEVOPS

<p align="center">
  <a href="README.md">🇺🇸 English</a> |
  🇪🇸 <b>Español</b> |
  <a href="README_fra.md">🇫🇷 Français</a> |
  <a href="README_ita.md">🇮🇹 Italiano</a> |
  <a href="README_deu.md">🇩🇪 Deutsch</a> |
  <a href="README_zho.md">🇨🇳 简体中文</a> |
  <a href="README_jpn.md">🇯🇵 日本語</a>
</p>

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

## 🎯 Descripción general

* **Un cortafuegos de la máquina central** (`scripts/firewall_core.sh`): el puerto del broker solo desde la red de campo, los del servidor y Studio solo desde la red de los clientes (si se indica), en una tabla propia que no menciona nada más y acepta el resto; `apply --rollback-after` quita las reglas de nuevo si no las confirmas, así que un error no te deja fuera. Las reglas y los rechazos están probados (36 comprobaciones, no se carga nada); no se ha cargado en ninguna máquina todavía, y las VLAN en sí siguen siendo un diseño para el router y el switch.
* **Banco de pruebas CM5:** `scripts/deploy_cm5.sh` compila en una copia limpia, envía un archivo y ejecuta `scripts/install_cm5.sh`, que crea su propio usuario, su propio directorio y dos unidades systemd en puertos propios (tres con `--with-mqtt`: el Mosquitto propio de A.R.M.O.R. en el puerto 18883, comprobado en una CM5 real), con límites de recursos, y nunca toca otro proyecto ([detalles](docs/CM5_TEST_BENCH.md)).
* **Topología Compose:** un broker Mosquitto no anónimo con una identidad por nodo, el servidor y Studio tras un nginx que hace de proxy de `/api/`; solo se publica Studio, en loopback. Contenedores endurecidos, red interna y volúmenes con nombre para el estado.
* **Dispositivos y lecturas en el broker del banco:** el servidor puede escuchar y ordenar `armor/device/#` y leer `armor/node/+/info`, `armor/solar/#` y `armor/electrical/#`; `scripts/mqtt_identity.sh add device NAME` da a un dispositivo sus propios temas y `add bridge NAME` a un puente Zigbee2MQTT o Shelly todos ellos. `scripts/mqtt_identity.sh electrical-switching NODE_ID on` es lo único que permite al servidor ordenar el conmutador de un nodo eléctrico (desactivado por defecto; `off` lo retira). `add alarm-node ID` da a un nodo de alarma su `armor/alarm/ID/state` y `result` y nada más, y `scripts/mqtt_identity.sh alarm-commands NODE_ID on` es lo único que permite al servidor armarlo y desarmarlo (apagado por defecto; `off` lo quita); el servidor lee `armor/alarm/#`.
* **Secretos:** `scripts/generate_secrets.sh` crea secretos aleatorios sin imprimir ninguno; `scripts/check-required-env.sh` rechaza valores ausentes, de ejemplo, cortos o repetidos.
* **Copia de seguridad y restauración:** `scripts/backup_data.sh` crea un archivo cifrado con AES-256, verificado y con suma de comprobación de los datos del servidor (sin evidencias salvo que se pida); `scripts/restore_data.sh` lo lista o lo restaura sin sobrescribir nunca datos existentes. La clave de cámaras **no** va en el archivo, a propósito.
* **TLS:** un perfil `tls` opcional de Compose pone Caddy, con su propia autoridad de certificados local, delante de Studio ([detalles](docs/BACKUP_AND_TLS.md)).
* **Todos los servicios del banco:** `install_cm5.sh` instala también, bajo petición, el servicio de observación (`--with-ai`), el servicio de voz (`--with-voice`), el agente de administración que permite a Studio arrancar, parar y reiniciar servicios y editar los archivos de configuración con una lista cerrada de acciones (`--with-admin`) y la copia de seguridad cifrada diaria (`--with-backup`); una ejecución posterior recuerda lo instalado antes.

## 📂 Estructura del repositorio

```text
ARMOR-DEVOPS/
├── docker-compose.yml, .env.example, mosquitto/
├── caddy/     Caddyfile (TLS)
├── scripts/   deploy_cm5, install_cm5, generate_secrets, check-required-env, validate-compose, backup_data, restore_data, test_backup, test_compose, firewall_core, test_firewall, mqtt_identity
└── docs/      DEPLOYMENT_BOUNDARY, CM5_TEST_BENCH, BACKUP_AND_TLS
```

## 🛠️ Entorno de desarrollo

```bash
scripts/generate_secrets.sh          # .env and secrets/ (Git-ignored)
scripts/check-required-env.sh
docker compose config --quiet && docker compose up --build
scripts/deploy_cm5.sh --host <cm5> --user <user> --key <key> --apply   # the test bench
scripts/backup_data.sh --data-dir <data> --out-dir <backups> --passphrase-file <file>
```

Véase el [límite de despliegue](docs/DEPLOYMENT_BOUNDARY.md).

## 🔗 Proyectos relacionados

**A.R.M.O.R.** (Autonomous Radar & Multimodal Observation Range) es un sistema de seguridad perimetral hecho de repositorios independientes. Cada uno tiene su propia versión, sus propias pruebas y su propio README; esta es la familia:

* **[ARMOR-COMMON](https://github.com/JuanenRac/ARMOR-COMMON)** - Contratos de mensajes, validadores, vectores de conformidad y tipos generados
* **[ARMOR-RADAR](https://github.com/JuanenRac/ARMOR-RADAR)** - Firmware del nodo de campo para ESP32-S3 con tres radares y su propio panel web
* **[ARMOR-SOLAR](https://github.com/JuanenRac/ARMOR-SOLAR)** - Protocolos de inversores y baterías solares y los mensajes de un nodo pasarela
* **[ARMOR-ELECTRICAL](https://github.com/JuanenRac/ARMOR-ELECTRICAL)** - Nodo eléctrico: contadores, el mensaje de las lecturas de la red y las reglas para maniobrar
* **[ARMOR-ALARM](https://github.com/JuanenRac/ARMOR-ALARM)** - Nodo y central de alarma: zonas, armado, retardos, sirena y PIN, con el servidor o sin él
* **[ARMOR-HMI](https://github.com/JuanenRac/ARMOR-HMI)** - Panel táctil: el estado del sistema en una pantalla de pared, armar y reconocer alarmas, y el hogar del asistente de voz
* **[ARMOR-NETWORK](https://github.com/JuanenRac/ARMOR-NETWORK)** - La red local: sus dispositivos, internet y lo que cambia
* **[ARMOR-SERVER](https://github.com/JuanenRac/ARMOR-SERVER)** - Coordinador central: telemetría, alarmas, dispositivos, lecturas solares y cámaras
* **[ARMOR-STUDIO](https://github.com/JuanenRac/ARMOR-STUDIO)** - Consola web: cámaras, radar, alarmas, energía solar y el diseñador de sitio 2D/3D
* **[ARMOR-ANDROID-CONTROL](https://github.com/JuanenRac/ARMOR-ANDROID-CONTROL)** - Cliente Android del operador con radar 2D/3D en vivo
* **[ARMOR-SERVER-AI](https://github.com/JuanenRac/ARMOR-SERVER-AI)** - Política de inferencia visual que explica sus decisiones y nunca actúa
* **[ARMOR-VOICE-AI](https://github.com/JuanenRac/ARMOR-VOICE-AI)** - Intenciones de voz sin conexión con una confirmación imposible de falsificar
* **[ARMOR-HARDWARE](https://github.com/JuanenRac/ARMOR-HARDWARE)** - Cajas, electrónica y la matriz de aceptación en banco
* **ARMOR-DEVOPS** (este repositorio) - Despliegue, el banco de pruebas de la CM5, copias de seguridad y TLS
* **[ARMOR-SIMULATOR](https://github.com/JuanenRac/ARMOR-SIMULATOR)** - Simulador de telemetría sin conexión con fallos repetibles
* **[ARMOR-UPDATER](https://github.com/JuanenRac/ARMOR-UPDATER)** - Detecta, instala y actualiza los propios repositorios del ecosistema
* **[ARMOR-DOCS](https://github.com/JuanenRac/ARMOR-DOCS)** - Arquitectura, base de seguridad y la matriz de capacidades

## 📚 Documentación y comunidad

Dónde leer más:

* [Matriz de capacidades: qué está probado y qué no](https://github.com/JuanenRac/ARMOR-DOCS/blob/main/docs/CAPABILITY_MATRIX.md)
* [Catálogo de proyectos: versiones y cómo dependen unos de otros](https://github.com/JuanenRac/ARMOR-DOCS/blob/main/docs/PROJECT_CATALOG.md)
* [Historial de cambios de este repositorio](CHANGELOG.md)
* [Licencia (GPL-3.0-or-later)](LICENSE)
* Preguntas, ideas e informes: electrohobby3d@gmail.com

## 👤 AUTOR

**JuanenRac (Electro Hobby 3D)** · electrohobby3d@gmail.com

## 📜 LICENCIA

GPL-3.0-or-later - véase [LICENSE](LICENSE).
