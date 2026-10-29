<p align="center">
  <img src="images/ARMOR_BANNER.svg" alt="Banner de ARMOR-DEVOPS" width="100%">
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
  <img src="https://img.shields.io/badge/License-GPL%203.0--or--later-blue.svg" alt="GPL 3.0 o posterior">
  <img src="https://img.shields.io/badge/Deploy-Docker%20Compose-2496ed.svg" alt="Deploy">
  <img src="https://img.shields.io/badge/Bench-systemd-FFB020.svg" alt="Bench">
  <img src="https://img.shields.io/badge/Version-0.6.7-0f6cbd.svg" alt="Versión">
  <img src="https://img.shields.io/badge/Maturity-established-2EA44F.svg" alt="Madurez">
</p>

---

**Comprobación de honestidad - qué funciona hoy:** El instalador del banco de la CM5 se ha ejecutado en una CM5 real que aloja otro software, que siguió sano, y el banco corre en uso diario con el servidor, Studio, el nodo de red, los servicios de observación y de voz, el broker y los dos ayudantes de abajo; en él se han hecho actualizaciones de sus componentes desde GitHub (a través de Studio). La topología Docker Compose y su perfil TLS opcional se han construido y ejecutado de verdad con Docker Engine en WSL (`scripts/test_compose.sh`), pero **no en la Jetson**. Los scripts de copia de seguridad y restauración tienen una prueba de ida y vuelta que pasa, y los dos ayudantes tienen sus propios tests. Lo que **no** está probado: una instalación limpia en una máquina que nunca ha visto el proyecto y toda la topología Docker en su destino.

---

## 📋 De un vistazo

| | |
|---|---|
| Versión | `0.6.7` |
| Madurez | Establecido |
| Función | Kit de despliegue: instalador del banco de la CM5, paquetes de versión, dos ayudantes, topología Compose |
| Tecnología | Bash, Python 3 (biblioteca estándar), Docker Compose, Mosquitto, Caddy, nginx, systemd |
| Pruebas | Un script de prueba para cada parte (`scripts/test_*.sh` y `test_*.py`); la topología Compose se construye y ejecuta con Docker en WSL |
| Contrato | Puertos del banco: servidor 18080, Studio 18081, MQTT 18883 (nunca 1883), voz 18090 |
| Funciona en | Una CM5 o cualquier máquina basada en Debian accesible por SSH; Docker Engine con Compose para la topología de contenedores |
| En hardware real | Gobierna el banco de pruebas de la CM5 en uso diario, en una CM5 real que aloja otro software; aún no en la Jetson |
| Licencia | GPL-3.0-or-later |

**Ir a:** [Resumen](#-resumen) · [Arquitectura](#-arquitectura) · [Seguridad](#-seguridad-y-protección) · [Interfaces](#-interfaces) · [Configuración](#-configuración) · [Inicio rápido](#-inicio-rápido) · [Pruebas](#-pruebas) · [Problemas](#-resolución-de-problemas) · [Estructura](#-estructura-del-repositorio) · [Relacionados](#-proyectos-relacionados)

## 🚦 Estado del proyecto

Cada línea es una parte de este repositorio y la luz dice hasta dónde llega hoy. Está escrito con lo que el repositorio puede demostrar (pruebas, compilaciones, ejecuciones), no con lo que está planeado.

🟢 Hecho y verificado · 🟡 Funciona, con límites conocidos · 🟠 Parcial o sin verificar todavía · 🔴 No hecho o no funciona

| Área | Estado | Qué significa aquí |
|---|---|---|
| Software | 🟡 | El instalador del banco CM5 se ha ejecutado en una CM5 real que aloja otro software, que siguió sano; una instalación limpia en una máquina que nunca ha visto el proyecto no está probada. |
| Pruebas | 🟡 | Los scripts de copia y restauración tienen una prueba de ida y vuelta que pasa, los dos ayudantes tienen sus propias pruebas, y la topología Docker con su perfil TLS opcional se construyó y ejecutó con Docker Engine en WSL; la topología completa no ha funcionado en su destino. |
| Hardware | 🟡 | Gestiona el banco de pruebas CM5 en uso diario; nada ha funcionado en la Jetson. |
| Actualizaciones | 🟢 | Las actualizaciones de los componentes desde GitHub, a través de Studio, se han hecho en el banco de pruebas CM5. |
| Documentación | 🟢 | Ocho idiomas y el historial de cambios están al día. |

## 🎯 Resumen

* **Banco de pruebas de la CM5:** `scripts/deploy_cm5.sh` compila en una copia limpia, envía un archivo y ejecuta `scripts/install_cm5.sh`, que crea su propio usuario, su propio directorio y unidades systemd en sus propios puertos para el servidor y Studio y, con opciones, el broker MQTT, el nodo de red, el servicio de observación, la pasarela de voz, el agente de administración, el ayudante de mantenimiento y la copia de seguridad diaria. Nunca toca lo demás que corre la máquina.
* **El ayudante de mantenimiento** (`armor_maintenance_agent.py`): las actualizaciones de los componentes de la propia instalación desde GitHub (descarga el paquete de la versión, comprueba su SHA-256 y lo cambia con vuelta atrás), las del sistema operativo y una consola root opcional, todo gobernado desde la pestaña *Actualizaciones* de Studio; la consola está apagada salvo que se active. Conserva las seis copias más recientes que aparta, y menos cuando el disco está casi lleno (`ARMOR_MAINT_MIN_FREE_MB` en su archivo de ajustes: 500 por defecto, 0 lo desactiva).
* **El agente de administración** (`armor_admin_agent.py`): la única parte con privilegios, con una lista cerrada de servicios, ficheros de ajustes y cuentas del broker, de modo que Studio nunca necesita root.
* **Paquetes de cada versión:** `scripts/package_component.py` construye el paquete de un componente (Studio, servidor, red, servicio de observación, pasarela de voz, DevOps), escribe su SHA-256 al lado y lo publica como versión de GitHub.
* **Topología Compose:** un broker Mosquitto no anónimo con una identidad por nodo y una ACL (incluidos los nodos de alarma y las zonas Zigbee que les dice el servidor), el servidor y Studio tras un nginx que hace de proxy de `/api/`; solo Studio se publica, en loopback. Contenedores endurecidos, imágenes fijadas, una red interna del núcleo y volúmenes con nombre para el estado.
* **TLS:** un perfil `tls` opcional de Compose pone Caddy, con su propia autoridad certificadora local, delante de Studio, y se ofrece una configuración de Mosquitto sobre TLS ([detalles](docs/BACKUP_AND_TLS.md)).
* **Un cortafuegos de host para la máquina central** (`scripts/firewall_core.sh`): el puerto del broker solo desde la red de campo, los del servidor y Studio solo desde la red de los clientes (cuando se da), en una tabla propia que no menciona nada más.
* **Secretos:** `scripts/generate_secrets.sh` crea secretos aleatorios y no imprime ninguno; `scripts/check-required-env.sh` rechaza valores ausentes, de ejemplo, cortos o repetidos.
* **Copia de seguridad y restauración:** `scripts/backup_data.sh` hace un archivo cifrado con AES-256, verificado y con suma de comprobación de los datos del servidor (sin evidencias salvo que se pidan); `scripts/restore_data.sh` lo lista o lo restaura sin sobrescribir nunca datos existentes.
* **Una VPN y un nombre para la casa, configurados desde Studio:** `armor_wireguard.sh` monta una VPN WireGuard con unos pocos comandos (claves en la máquina, una configuración por móvil con código QR, enrutado a los nodos si se quiere) y `armor_ddns.sh` mantiene un nombre de DuckDNS, Cloudflare u otro apuntando a la casa cuando el operador cambia la dirección; el agente de mantenimiento ofrece ambos a Studio y al móvil, así que nadie tiene que escribir un comando, y una guía paso a paso en ocho idiomas cubre el router.
* **Paquetes firmados:** el asistente de mantenimiento solo instala un paquete del servidor, de Studio o de cualquier otro programa si lleva una firma Ed25519 válida de la clave de releases del proyecto (verificada en Python puro, sin software adicional); una firma ausente, incorrecta o manipulada deja la máquina como estaba. Existe una excepción de emergencia, solo como ajuste en el fichero de la propia máquina.
* **Una puerta cifrada opcional al broker (MQTT sobre TLS):** `scripts/armor_mqtt_tls.sh` crea una autoridad de certificación para la instalación (su clave se queda en la máquina, modo `0600`), un certificado del broker para los nombres y direcciones de la máquina y un segundo listener de Mosquitto en el 8883 junto al normal, que nunca toca; es idempotente y tiene `status`, `export-ca`, `server-tls` y `remove` (los ficheros se apartan, nunca se borran). Probado con OpenSSL, con handshakes reales, y en un Mosquitto 2.0 real ([guía](docs/MQTT_TLS_spa.md)).
* **Informes de salud permitidos:** las reglas del broker dejan a cada nodo escribir su `armor/health/<nodo>` y al servidor leer `armor/health/#`; `mqtt_identity.sh add` escribe la línea para cada tipo de nodo y `mqtt_identity.sh health-report <rol> <nodo>` la añade a un nodo instalado antes (idempotente, se guardan las reglas anteriores).
* **Reglas del broker para el control de nodos:** solo la identidad del servidor puede publicar en `armor/control/+/command` (que cubre `armor/control/all/command`); cada nodo lee su propio tema de órdenes y el de difusión y escribe su propia respuesta en `armor/control/<nodo>/result`, y nada más, así que ningún nodo puede dar órdenes a otro y la contraseña robada de un nodo no puede reiniciar a los demás. `mqtt_identity.sh node-control` añade las tres líneas a un nodo instalado antes, y la prueba de las ACL comprueba cada tipo de nodo.

## 🧩 Papel en A.R.M.O.R.

ARMOR-DEVOPS es cómo todo lo demás llega a una máquina y se mantiene al día. Instala el servidor, Studio, el nodo de red, los servicios de observación y de voz y el broker en el banco de pruebas de la CM5, hace los paquetes de cada versión que la pestaña *Actualizaciones* de [ARMOR-STUDIO](https://github.com/JuanenRac/ARMOR-STUDIO) instala desde GitHub, y guarda los dos pequeños ayudantes que dejan a Studio actualizar la instalación y gestionar sus servicios sin ejecutarse nunca como root.

| Habla con | Cómo | Para qué |
|---|---|---|
| ARMOR-STUDIO | su pestaña *Actualizaciones* le pide al ayudante de mantenimiento por un socket local | nunca necesita root |
| GitHub Releases | `package_component.py` publica el paquete con su SHA-256 y firma | los componentes que instalar |
| ARMOR-SERVER, ARMOR-NETWORK, ARMOR-SERVER-AI, ARMOR-VOICE-AI | instalados como unidades systemd propias | los servicios del banco |
| ARMOR-UPDATER | aparte | la herramienta de quien guarda una copia de la familia en un PC; este repositorio es para la CM5 y la topología Compose |

## 🏛️ Arquitectura

<p align="center">
  <img src="images/architecture.svg" alt="ARMOR-DEVOPS architecture: where the packages come from, the deployment kit with its installer, helpers and Compose topology, and the bench and broker it sets up" width="100%">
</p>

## 🔒 Seguridad y protección

| Amenaza | Defensa |
|---|---|
| Interferir con otro software de la CM5 | Usuario, directorio y puertos propios (servidor 18080, Studio 18081, MQTT 18883 y voz 18090, todos entre 1024 y 65535 y distintos, nunca el estándar 1883); no toca el cortafuegos del sistema |
| Un broker abierto o sin autenticar | `allow_anonymous false`, un fichero de contraseñas y una ACL (secretos montados en `/run/secrets`), una identidad por nodo; solo el servidor puede publicar `armor/control/+/command`; cada nodo lee su orden y la de difusión y escribe solo su `armor/control/<nodo>/result` y `armor/health/<nodo>`; el servidor lee `armor/health/#` |
| Escucha accidental en la red | Compose publica el broker y Studio solo en `127.0.0.1` salvo que `ARMOR_MQTT_BIND`, `ARMOR_STUDIO_BIND` (y `ARMOR_TLS_BIND` para Caddy) digan otra cosa |
| MQTT y Studio en claro | Opcional: un segundo oyente de Mosquitto en el 8883 junto al llano (`armor_mqtt_tls.sh`: autoridad propia, clave en modo `0600`, certificado para los nombres de la máquina, idempotente, nunca toca el llano) y un perfil `tls` de Compose con Caddy y su autoridad local |
| La máquina central abierta a todos | `firewall_core.sh` escribe una tabla propia (`/etc/armor/firewall.nft`, con una unidad de vuelta atrás): el puerto del broker solo desde la red de campo, los del servidor y Studio solo desde la red de clientes; `check` lo verifica con `nft -c` |
| Secretos débiles o impresos | `generate_secrets.sh` crea secretos aleatorios y no imprime ninguno; `check-required-env.sh` rechaza valores ausentes, de plantilla, cortos o repetidos |
| Una copia de seguridad robada | `backup_data.sh` hace un archivo cifrado AES-256, verificado y con suma (la evidencia queda fuera salvo que se pida); `restore_data.sh` lo lista o restaura sin pisar nunca datos existentes |
| Una actualización falsa de un componente | El ayudante de mantenimiento descarga el paquete de la versión, comprueba su SHA-256 y la firma Ed25519 de la clave de publicación del proyecto (verificada en Python puro) y lo cambia con vuelta atrás; una firma ausente, errónea o manipulada deja la máquina sin cambios |
| Root al alcance de Studio | Nunca hace falta: el agente de administración (`armor_admin_agent.py`) tiene una lista cerrada de servicios, ficheros de ajustes y cuentas del broker; la consola de root del ayudante de mantenimiento está apagada salvo que se encienda |

Los contenedores están endurecidos, las imágenes fijadas, la red `core` es interna y el estado va en volúmenes con nombre. Los dos ayudantes usan sockets Unix locales, así que sus pruebas necesitan Linux. No está probada una instalación limpia en una máquina que nunca vio el proyecto ni la topología Docker completa en su destino; no ha habido revisión independiente.

## 🔌 Interfaces

| Ruta | Autenticación | Qué hace |
|---|---|---|
| `scripts/deploy_cm5.sh --host <cm5> --user <user> --key <key> --apply` | - | construye en una copia limpia, envía un archivo por SSH y ejecuta `install_cm5.sh` |
| `scripts/install_cm5.sh --public-host HOST [--apply]` | - | crea el usuario, el directorio y las unidades systemd; `--server-port`, `--studio-port`, `--mqtt-port` y `--also-reach` lo ajustan; sin `--apply` solo muestra el plan |
| `scripts/package_component.py` | - | empaqueta Studio, el servidor, el nodo de red, el servicio de observación, la pasarela de voz o DevOps como los instala el ayudante de mantenimiento, escribe su SHA-256 y lo publica como versión de GitHub |
| `scripts/generate_secrets.sh`  `scripts/check-required-env.sh` | - | `.env` y `secrets/` (ignorados por Git); la comprobación rechaza valores ausentes, de plantilla, cortos o repetidos |
| `scripts/backup_data.sh --data-dir <d> --out-dir <o> --passphrase-file <f>` | - | el archivo cifrado y verificado de los datos del servidor |
| `scripts/restore_data.sh` | - | lista un archivo o lo restaura sin pisar datos existentes |
| `scripts/firewall_core.sh apply, check --field <net> [--clients <net>]` | - | la tabla de cortafuegos del equipo central; `check` la verifica (`FIREWALL_CHECK=SKIP` si `nft` no está instalado) |
| `scripts/mqtt_identity.sh add`  `health-report <role> <node>`  `node-control` | - | escribe la línea del broker de cada tipo de nodo; añade informes de salud y control a un nodo instalado antes (idempotente) |
| `scripts/armor_mqtt_tls.sh`  `armor_wireguard.sh`  `armor_ddns.sh`  `armor_tls_check.sh` | - | la puerta cifrada del broker (`status`, `export-ca`, `server-tls`...), la VPN WireGuard con un QR por teléfono, un nombre DuckDNS, Cloudflare u otro para la casa y la comprobación del acceso remoto; Studio las ofrece sin teclear una orden |

Los dos ayudantes (`armor_admin_agent.py`, `armor_maintenance_agent.py`) escuchan en sockets Unix locales y por eso no funcionan en Windows. El fichero Compose arranca el broker (Mosquitto), el servidor y Studio (nginx, que hace de proxy de `/api/`), y un perfil `tls` añade Caddy; solo se publica Studio, en loopback por defecto (`127.0.0.1:8088`, TLS en el 8443). Los paquetes de cada versión son archivos de las versiones de GitHub, no ficheros de este repositorio.

## ⚙️ Configuración

| Ajuste | Por defecto | Qué hace |
|---|---|---|
| `install_cm5.sh` | 18080  18081  18883  18090 | `--server-port`, `--studio-port`, `--mqtt-port` (se conserva el instalado si no se repite) y el puerto de voz; todos entre 1024 y 65535 y distintos; la dirección del broker va a `PREFIX/etc/armor.mqtt.env` |
| `ARMOR_MQTT_BIND`  `ARMOR_STUDIO_BIND` | 127.0.0.1 | dónde publica Compose el broker y Studio |
| `ARMOR_PUBLIC_ORIGIN` | http://127.0.0.1:8088 | el origen por el que se llega a Studio |
| `ARMOR_TLS_BIND`  `ARMOR_TLS_PORT`  `ARMOR_TLS_HTTP_PORT` | 8443 | Caddy del perfil `tls` |
| `.env`  `.env.example` | - | lo crea `generate_secrets.sh`, ignorado por Git; el ejemplo lista cada variable |

La consola de root del ayudante de mantenimiento es un ajuste del propio fichero de la máquina y está apagada por defecto; el cortafuegos y el TLS son opciones del instalador, no valores por defecto. Detalles en [docs/CM5_TEST_BENCH.md](docs/CM5_TEST_BENCH.md).

## 🚀 Inicio rápido

**Requisitos:** Docker Engine con Compose (para la topología de contenedores), una CM5 o cualquier máquina basada en Debian accesible por SSH (para el banco de pruebas), Bash, `ssh` y `tar` en la máquina que despliega.

```bash
scripts/generate_secrets.sh                                                            # `.env` y `secrets/` (ignorados por Git)
scripts/check-required-env.sh
docker compose config --quiet && docker compose up --build                             # la topología de contenedores
scripts/deploy_cm5.sh --host <cm5> --user <user> --key <key> --apply                   # el banco de pruebas
scripts/backup_data.sh --data-dir <data> --out-dir <backups> --passphrase-file <file>  # una copia cifrada
```

Mira el [límite del despliegue](docs/DEPLOYMENT_BOUNDARY.md) y el [banco de pruebas](docs/CM5_TEST_BENCH.md).

## 🧪 Pruebas

| Área | Qué cubre |
|---|---|
| `test_admin_agent.py`  `.sh` | la lista cerrada del agente de administración (necesita Linux: sockets Unix) |
| `test_maintenance_agent.py`  `.sh` | el ayudante de mantenimiento: descarga, SHA-256, firma, cambio y vuelta atrás (necesita Linux) |
| `test_package_component.py`  `test_registry.py`  `test_remote_access.py` | los paquetes, la lista de componentes y los ayudantes de acceso remoto |
| `test_backup.sh`  `test_env_and_restore.sh` | la ida y vuelta de copia y restauración, los secretos y la comprobación del entorno |
| `test_compose.sh`  `validate-compose.sh` | la topología Compose y su perfil TLS, construidos y ejecutados con Docker Engine en WSL |
| `test_firewall.sh`  `test_install_plan.sh`  `test_mqtt_identity.sh`  `test_mqtt_tls.sh`  `test_tls_check.sh`  `test_wireguard.sh`  `test_ddns.sh` | el cortafuegos, el plan del instalador, las identidades del broker, MQTT sobre TLS, la comprobación TLS, la VPN y el nombre dinámico |

Las pruebas de Python se ejecutan con `python -m unittest discover -s scripts -p "test_*.py"`; en Windows las tres que necesitan sockets Unix no pueden correr. Los scripts necesitan Bash, WSL, Docker o root y hay que ejecutarlos en Linux. Todavía no hay una cifra única de pruebas: Project status dice qué se ha ejecutado. GitHub Actions ejecuta la base de A.R.M.O.R. en cada push y pull request: la validación del manifiesto, la versión, el registro de cambios y la paridad de los README, y luego la compilación y las pruebas del propio proyecto.

## 🏗️ Compilación y publicación

No se compila nada: son scripts, un fichero Compose y ayudantes en Python. `scripts/package_component.py` construye el paquete de un componente y escribe su SHA-256 al lado; los paquetes son archivos de las versiones de GitHub, no ficheros de este repositorio. La versión vive en `armor.project.json` y en la insignia del README (leída del manifiesto); cada versión tiene su entrada en [CHANGELOG.md](CHANGELOG.md).

## 🩺 Resolución de problemas

| Ves | Porque | Haz |
|---|---|---|
| `ports must be numbers between 1024 and 65535`  `the server and studio ports must differ` | un puerto de `install_cm5.sh` está fuera de rango o repetido | usa puertos distintos entre 1024 y 65535 (nunca el estándar 1883) |
| `--also-reach must look like http://HOST:PORT=http://HOST:PORT` | la dirección adicional no está escrita como dirección de Studio = dirección del servidor | escribe `--also-reach http://<host>:<puerto-studio>=http://<host>:<puerto-servidor>` |
| `FIREWALL_CHECK=SKIP nft is not installed here` | falta `nft`, así que `firewall_core.sh check` no puede verificar la tabla | instala nftables en la máquina y vuelve a comprobar |
| `AttributeError: module 'socketserver' has no attribute 'UnixStreamServer'` | las pruebas de los dos ayudantes se ejecutan en Windows | ejecútalas en Linux (o WSL) |

## 📂 Estructura del repositorio

<p align="center">
  <img src="images/repository-structure.svg" alt="Repository structure of ARMOR-DEVOPS" width="100%">
</p>

<details>
<summary>Versión en texto del árbol</summary>

```text
ARMOR-DEVOPS/
├── scripts/
│   ├── deploy_cm5.sh install_cm5.sh                      despliega en el banco, lo instala
│   ├── package_component.py                              el paquete de cada versión
│   ├── armor_admin_agent.py armor_maintenance_agent.py   los dos ayudantes de Studio
│   ├── generate_secrets.sh check-required-env.sh         secretos aleatorios; rechaza los débiles
│   ├── backup_data.sh restore_data.sh                    copia cifrada y restauración
│   ├── firewall_core.sh mqtt_identity.sh                 cortafuegos e identidades del broker
│   ├── armor_mqtt_tls.sh armor_tls_check.sh              MQTT sobre TLS y su comprobación
│   ├── armor_ddns.sh armor_wireguard.sh                  un nombre para la casa y una VPN
│   └── test_*.py test_*.sh validate-compose.sh           las pruebas de los ayudantes y scripts
├── docker-compose.yml docker-compose.tls.yml             broker, servidor, Studio; perfil TLS
├── mosquitto/                                            mosquitto.conf, config TLS, acl.example
├── caddy/                                                Caddyfile: HTTPS delante de Studio
├── docs/                                                 DEPLOYMENT_BOUNDARY, CM5_TEST_BENCH, BENCH_TESTS, BACKUP_AND_TLS, MQTT_TLS, HTTPS_PAIRING, REMOTE_ACCESS, SIGNED_PACKAGES (cuatro también en ocho idiomas)
├── tools/                                                las comprobaciones de CI y las herramientas compartidas
├── images/                                               banner, icono y las imágenes del README
├── .github/                                              flujo de CI, aviso al panel, plantillas de incidencias y pull requests
├── armor.project.json                                    manifiesto: versión, función, madurez
├── CHANGELOG.md                                          qué cambió en cada versión
├── run.sh run.bat                                        arrancar, flujo compartido
├── build.sh build.bat                                    construir y probar, flujo compartido
├── build-test.sh build-test.bat                          construir, probar y empaquetar
├── test.sh test.bat                                      solo las pruebas, nunca la versión
└── SECURITY.md SUPPORT.md CONTRIBUTING.md CODE_OF_CONDUCT.md LICENSE
```

</details>

## 🗺️ Hoja de ruta y límites conocidos

**Límites conocidos hoy**

* No está probada una instalación limpia en una máquina que nunca vio el proyecto.
* La topología Docker completa se ha construido y ejecutado con Docker Engine en WSL, pero no en su destino, la Jetson.
* No hay una cifra única de pruebas, y las pruebas de los dos ayudantes necesitan Linux.
* Sin revisión de seguridad independiente.

**Lo siguiente**

* Una instalación limpia en una máquina nueva y la topología Docker en la Jetson.

## 🌍 Idiomas

El README y los textos existen en inglés, español, francés, italiano, alemán, chino, japonés y portugués de Portugal.

## 🔗 Proyectos relacionados

**A.R.M.O.R.** (Autonomous Radar & Multimodal Observation Range) es un sistema de seguridad perimetral hecho de repositorios independientes. Cada uno tiene su propia versión, sus propias pruebas y su propio README; esta es la familia:

* **[ARMOR-COMMON](https://github.com/JuanenRac/ARMOR-COMMON)** - Contratos de mensajes, validadores, vectores de conformidad y tipos generados
* **[ARMOR-NODE-RADAR](https://github.com/JuanenRac/ARMOR-NODE-RADAR)** - Firmware de nodo de campo para ESP32-S3 con tres radares y su propio panel web
* **[ARMOR-NODE-SOLAR](https://github.com/JuanenRac/ARMOR-NODE-SOLAR)** - Protocolos de inversores y baterías solares y los mensajes de un nodo pasarela
* **[ARMOR-NODE-ELECTRICAL](https://github.com/JuanenRac/ARMOR-NODE-ELECTRICAL)** - Nodo eléctrico: medidores, el mensaje de las lecturas de la red y las reglas de maniobra
* **[ARMOR-NODE-ALARM](https://github.com/JuanenRac/ARMOR-NODE-ALARM)** - Nodo y panel de alarma: zonas, armado, retardos, sirena y PIN, con el servidor o sin él
* **[ARMOR-NODE-HMI](https://github.com/JuanenRac/ARMOR-NODE-HMI)** - Panel táctil: el estado del sistema en una pantalla de pared, armar y reconocer, y el hogar del asistente de voz
* **[ARMOR-NETWORK](https://github.com/JuanenRac/ARMOR-NETWORK)** - La red local: sus dispositivos, internet y lo que cambia
* **[ARMOR-SERVER](https://github.com/JuanenRac/ARMOR-SERVER)** - Coordinador central: telemetría, alarmas, dispositivos, lecturas solares y cámaras
* **[ARMOR-STUDIO](https://github.com/JuanenRac/ARMOR-STUDIO)** - Consola web: cámaras, radar, alarmas, energía solar y el diseñador 2D/3D del emplazamiento
* **[ARMOR-ANDROID-CONTROL](https://github.com/JuanenRac/ARMOR-ANDROID-CONTROL)** - Cliente de operador Android con radar 2D/3D en vivo
* **[ARMOR-IOS-CONTROL](https://github.com/JuanenRac/ARMOR-IOS-CONTROL)** - Cliente de operador para iPhone
* **[ARMOR-SERVER-AI](https://github.com/JuanenRac/ARMOR-SERVER-AI)** - Política de inferencia visual que explica sus decisiones y nunca actúa
* **[ARMOR-VISION](https://github.com/JuanenRac/ARMOR-VISION)** - Zonas de cámara, máscaras y reglas de detección para la Jetson Orin NX
* **[ARMOR-VOICE-AI](https://github.com/JuanenRac/ARMOR-VOICE-AI)** - Intenciones de voz sin conexión con una confirmación que no se puede falsificar
* **[ARMOR-HARDWARE](https://github.com/JuanenRac/ARMOR-HARDWARE)** - Cajas, electrónica y la matriz de aceptación en banco
* **ARMOR-DEVOPS** (este repositorio) - Despliegue, el banco de pruebas de la CM5, copias de seguridad y TLS
* **[ARMOR-SIMULATOR](https://github.com/JuanenRac/ARMOR-SIMULATOR)** - Simulador de telemetría sin conexión con fallos repetibles
* **[ARMOR-UPDATER](https://github.com/JuanenRac/ARMOR-UPDATER)** - Detecta, instala y actualiza los repositorios del propio ecosistema
* **[ARMOR-DOCS](https://github.com/JuanenRac/ARMOR-DOCS)** - Arquitectura, base de seguridad y la matriz de capacidades

## 📚 Documentación

* [DEPLOYMENT_BOUNDARY](docs/DEPLOYMENT_BOUNDARY.md): qué despliega este repositorio y qué no
* [CM5_TEST_BENCH](docs/CM5_TEST_BENCH.md): el instalador, las unidades, los puertos y los ayudantes del banco
* [BENCH_TESTS](docs/BENCH_TESTS.md): cómo se prueba el banco
* [BACKUP_AND_TLS](docs/BACKUP_AND_TLS.md): copia y restauración, y el perfil TLS de Compose
* [MQTT_TLS](docs/MQTT_TLS.md): la puerta cifrada del broker (también en ocho idiomas)
* [HTTPS_PAIRING](docs/HTTPS_PAIRING.md): confiar en el certificado de un nodo (también en ocho idiomas)
* [REMOTE_ACCESS](docs/REMOTE_ACCESS.md): VPN, un nombre para la casa y el router, paso a paso (también en ocho idiomas)
* [SIGNED_PACKAGES](docs/SIGNED_PACKAGES.md): la firma de los paquetes (también en ocho idiomas)
* [Matriz de capacidades: qué está demostrado y qué no](https://github.com/JuanenRac/ARMOR-DOCS/blob/main/docs/CAPABILITY_MATRIX.md)
* [Catálogo de proyectos: versiones y cómo dependen unos repositorios de otros](https://github.com/JuanenRac/ARMOR-DOCS/blob/main/docs/PROJECT_CATALOG.md)
* [Registro de cambios de este repositorio](CHANGELOG.md)

## 🤝 Contribuir y comunidad

* Antes de un pull request ejecuta `python -I tools/armor_ci_validate.py` y las pruebas: ambos deben pasar. Mira [CONTRIBUTING.md](CONTRIBUTING.md) y el [código de conducta](CODE_OF_CONDUCT.md).
* El README existe en ocho idiomas y se genera desde las fuentes de ARMOR-DOCS: un cambio de texto se hace allí.
* Un cambio en un mensaje entre componentes empieza en ARMOR-COMMON.
* No describas como funcionando en una placa lo que solo se ha compilado.
* Informa de una vulnerabilidad en privado: [SECURITY.md](SECURITY.md). Preguntas, ideas e informes: electrohobby3d@gmail.com ([SUPPORT.md](SUPPORT.md)).

## 👤 AUTOR

**JuanenRac (Electro Hobby 3D)** · electrohobby3d@gmail.com

## 📜 LICENCIA

GPL-3.0-or-later - véase [LICENSE](LICENSE).
