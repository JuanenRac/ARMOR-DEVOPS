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
  <a href="README_jpn.md">🇯🇵 日本語</a> |
  <a href="README_por.md">🇵🇹 Português</a>
</p>

### Despliegue, el banco de pruebas de la CM5, sus actualizaciones desde GitHub y el mantenimiento de la instalación

<p align="center">
  <img src="https://img.shields.io/badge/License-GPL%203.0-blue.svg" alt="GPL 3.0">
  <img src="https://img.shields.io/badge/Deploy-Docker%20Compose-2496ed.svg" alt="Deploy">
  <img src="https://img.shields.io/badge/Bench-systemd-FFB020.svg" alt="Bench">
  <img src="https://img.shields.io/badge/Version-0.5.5-0f6cbd.svg" alt="Version">
  <img src="https://img.shields.io/badge/Maturity-functional-00E5FF.svg" alt="Maturity">
</p>

---

**Comprobación de honestidad - qué funciona hoy:** El instalador del banco de la CM5 se ha ejecutado en una CM5 real que aloja otro software, que siguió sano, y el banco corre en uso diario con el servidor, Studio, el nodo de red, los servicios de observación y de voz, el broker y los dos ayudantes de abajo; en él se han hecho actualizaciones de sus componentes desde GitHub (a través de Studio). La topología Docker Compose y su perfil TLS opcional se han construido y ejecutado de verdad con Docker Engine en WSL (`scripts/test_compose.sh`), pero **no en la Jetson**. Los scripts de copia de seguridad y restauración tienen una prueba de ida y vuelta que pasa, y los dos ayudantes tienen sus propios tests. Lo que **no** está probado: una instalación limpia en una máquina que nunca ha visto el proyecto y toda la topología Docker en su destino.

---

## 📋 De un vistazo

| | |
|---|---|
| Versión | `0.5.5` |
| Madurez | Funcional |
| Tecnología | Docker Compose / Bash / YAML |
| En hardware real | Gobierna el banco de pruebas de la CM5 en uso diario, en una CM5 real que aloja otro software; aún no en la Jetson |

## 🎯 Descripción general

* **Banco de pruebas de la CM5:** `scripts/deploy_cm5.sh` compila en una copia limpia, envía un archivo y ejecuta `scripts/install_cm5.sh`, que crea su propio usuario, su propio directorio y unidades systemd en sus propios puertos para el servidor y Studio y, con opciones, el broker MQTT, el nodo de red, el servicio de observación, la pasarela de voz, el agente de administración, el ayudante de mantenimiento y la copia de seguridad diaria. Nunca toca lo demás que corre la máquina.
* **El ayudante de mantenimiento** (`armor_maintenance_agent.py`): las actualizaciones de los componentes de la propia instalación desde GitHub (descarga el paquete de la versión, comprueba su SHA-256 y lo cambia con vuelta atrás), las del sistema operativo y una consola root opcional, todo gobernado desde la pestaña *Actualizaciones* de Studio; la consola está apagada salvo que se active.
* **El agente de administración** (`armor_admin_agent.py`): la única parte con privilegios, con una lista cerrada de servicios, ficheros de ajustes y cuentas del broker, de modo que Studio nunca necesita root.
* **Paquetes de cada versión:** `scripts/package_component.py` construye el paquete de un componente (Studio, servidor, red, servicio de observación, pasarela de voz, DevOps), escribe su SHA-256 al lado y lo publica como versión de GitHub.
* **Topología Compose:** un broker Mosquitto no anónimo con una identidad por nodo y una ACL (incluidos los nodos de alarma y las zonas Zigbee que les dice el servidor), el servidor y Studio tras un nginx que hace de proxy de `/api/`; solo Studio se publica, en loopback. Contenedores endurecidos, imágenes fijadas, una red interna del núcleo y volúmenes con nombre para el estado.
* **TLS:** un perfil `tls` opcional de Compose pone Caddy, con su propia autoridad certificadora local, delante de Studio, y se ofrece una configuración de Mosquitto sobre TLS ([detalles](docs/BACKUP_AND_TLS.md)).
* **Un cortafuegos de host para la máquina central** (`scripts/firewall_core.sh`): el puerto del broker solo desde la red de campo, los del servidor y Studio solo desde la red de los clientes (cuando se da), en una tabla propia que no menciona nada más.
* **Secretos:** `scripts/generate_secrets.sh` crea secretos aleatorios y no imprime ninguno; `scripts/check-required-env.sh` rechaza valores ausentes, de ejemplo, cortos o repetidos.
* **Copia de seguridad y restauración:** `scripts/backup_data.sh` hace un archivo cifrado con AES-256, verificado y con suma de comprobación de los datos del servidor (sin evidencias salvo que se pidan); `scripts/restore_data.sh` lo lista o lo restaura sin sobrescribir nunca datos existentes.

## 🧩 Papel en A.R.M.O.R.

ARMOR-DEVOPS es cómo todo lo demás llega a una máquina y se mantiene al día. Instala el servidor, Studio, el nodo de red, los servicios de observación y de voz y el broker en el banco de pruebas de la CM5, hace los paquetes de cada versión que la pestaña *Actualizaciones* de [ARMOR-STUDIO](https://github.com/JuanenRac/ARMOR-STUDIO) instala desde GitHub, y guarda los dos pequeños ayudantes que dejan a Studio actualizar la instalación y gestionar sus servicios sin ejecutarse nunca como root.

## 📂 Estructura del repositorio

```text
ARMOR-DEVOPS/
├── docker-compose.yml, docker-compose.tls.yml, .env.example, mosquitto/ (broker, TLS profile, ACL example)
├── caddy/     Caddyfile (TLS)
├── scripts/   deploy_cm5, install_cm5, package_component, armor_admin_agent, armor_maintenance_agent, generate_secrets, check-required-env, backup_data, restore_data, firewall_core, mqtt_identity, tests of the agents, the backup, the firewall and the Compose topology
│   └── (package_component.py packs a program the way the maintenance helper installs it; the packages are assets of the GitHub releases, not files of this repository)
└── docs/      DEPLOYMENT_BOUNDARY, CM5_TEST_BENCH, BACKUP_AND_TLS
```

## 🛠️ Entorno de desarrollo

**Requisitos:** Docker Engine with Compose (for the container topology), a CM5 or any Debian-based machine reachable by SSH (for the test bench), Bash, `ssh` and `tar` on the machine that deploys

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
* **[ARMOR-VISION](https://github.com/JuanenRac/ARMOR-VISION)** - Zonas de cámara, máscaras y reglas de detección para la Jetson Orin NX
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
