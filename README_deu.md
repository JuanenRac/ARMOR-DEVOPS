<p align="center">
  <img src="images/ARMOR_BANNER.svg" alt="ARMOR-DEVOPS-Banner" width="100%">
</p>

# 🚀 ARMOR-DEVOPS

<p align="center">
  <a href="README.md">🇺🇸 English</a> |
  <a href="README_spa.md">🇪🇸 Español</a> |
  <a href="README_fra.md">🇫🇷 Français</a> |
  <a href="README_ita.md">🇮🇹 Italiano</a> |
  🇩🇪 <b>Deutsch</b> |
  <a href="README_zho.md">🇨🇳 简体中文</a> |
  <a href="README_jpn.md">🇯🇵 日本語</a> |
  <a href="README_por.md">🇵🇹 Português</a>
</p>

### Bereitstellung, der CM5-Testaufbau, seine Updates von GitHub und die Wartung der Anlage

<p align="center">
  <img src="https://img.shields.io/badge/License-GPL%203.0--or--later-blue.svg" alt="GPL 3.0 oder neuer">
  <img src="https://img.shields.io/badge/Deploy-Docker%20Compose-2496ed.svg" alt="Deploy">
  <img src="https://img.shields.io/badge/Bench-systemd-FFB020.svg" alt="Bench">
  <img src="https://img.shields.io/badge/Version-0.6.8-0f6cbd.svg" alt="Version">
  <img src="https://img.shields.io/badge/Maturity-established-2EA44F.svg" alt="Reifegrad">
</p>

---

**Ehrlichkeitsprüfung - was heute läuft:** Der Installer des CM5-Testaufbaus wurde auf einem echten CM5 ausgeführt, der andere Software beherbergt und gesund blieb, und der Aufbau läuft im täglichen Einsatz mit dem Server, Studio, dem Netzwerkknoten, den Beobachtungs- und Sprachdiensten, dem Broker und den zwei Helfern unten; Updates seiner Komponenten von GitHub (über Studio) wurden darauf durchgeführt. Die Docker-Compose-Topologie und ihr optionales TLS-Profil wurden mit Docker Engine in WSL wirklich gebaut und ausgeführt (`scripts/test_compose.sh`), aber **nicht auf dem Jetson**. Die Sicherungs- und Wiederherstellungsskripte haben einen bestandenen Hin-und-zurück-Test, und die beiden Helfer haben eigene Tests. **Nicht** bewiesen: eine saubere Installation auf einer Maschine, die das Projekt noch nie gesehen hat, und die ganze Docker-Topologie auf ihrem Ziel.

---

## 📋 Auf einen Blick

| | |
|---|---|
| Version | `0.6.8` |
| Reifegrad | Etabliert |
| Rolle | Bereitstellungs-Kit: Installer für den CM5-Prüfstand, Release-Pakete, zwei Helfer, Compose-Topologie |
| Technik | Bash, Python 3 (Standardbibliothek), Docker Compose, Mosquitto, Caddy, nginx, systemd |
| Tests | Ein Testskript je Teil (`scripts/test_*.sh` und `test_*.py`); die Compose-Topologie wird mit Docker in WSL gebaut und ausgeführt |
| Vertrag | Ports des Prüfstands: Server 18080, Studio 18081, MQTT 18883 (nie 1883), Sprache 18090 |
| Läuft auf | Ein CM5 oder jede Debian-basierte Maschine per SSH; Docker Engine mit Compose für die Container-Topologie |
| Auf echter Hardware | Betreibt den CM5-Testaufbau im täglichen Einsatz, auf einem echten CM5, der andere Software beherbergt; noch nicht auf dem Jetson |
| Lizenz | GPL-3.0-or-later |

**Springe zu:** [Überblick](#-überblick) · [Architektur](#-architektur) · [Sicherheit](#-sicherheit-und-schutz) · [Schnittstellen](#-schnittstellen) · [Konfiguration](#-konfiguration) · [Schnellstart](#-schnellstart) · [Tests](#-tests) · [Probleme](#-fehlerbehebung) · [Struktur](#-struktur-des-repositorys) · [Verwandte](#-verwandte-projekte)

## 🚦 Projektstatus

Jede Zeile ist ein Teil dieses Repositorys, und die Ampel sagt, wie weit er heute ist. Sie beruht auf dem, was das Repository zeigen kann (Tests, Builds, Läufe), nicht auf dem, was geplant ist.

🟢 Fertig und überprüft · 🟡 Funktioniert, mit bekannten Grenzen · 🟠 Teilweise fertig oder noch nicht überprüft · 🔴 Nicht gemacht oder funktioniert nicht

| Bereich | Stand | Was das hier bedeutet |
|---|---|---|
| Software | 🟡 | Der Installer des CM5-Prüfstands lief auf einem echten CM5, auf dem andere Software läuft und gesund blieb; eine saubere Installation auf einem Rechner, der das Projekt nie gesehen hat, ist nicht belegt. |
| Tests | 🟡 | Die Skripte für Sicherung und Wiederherstellung haben einen bestandenen Hin-und-zurück-Test, die beiden Helfer haben eigene Tests, und die Docker-Topologie mit ihrem optionalen TLS-Profil wurde mit Docker Engine in WSL gebaut und ausgeführt; die gesamte Topologie lief nicht auf ihrem Ziel. |
| Hardware | 🟡 | Er betreibt den CM5-Prüfstand im täglichen Einsatz; auf dem Jetson lief nichts. |
| Aktualisierungen | 🟢 | Aktualisierungen der Komponenten von GitHub über Studio wurden auf dem CM5-Prüfstand durchgeführt. |
| Dokumentation | 🟢 | Acht Sprachen und das Änderungsprotokoll sind aktuell. |

## 🎯 Überblick

* **CM5-Testaufbau:** `scripts/deploy_cm5.sh` baut in einer sauberen Kopie, sendet ein Archiv und führt `scripts/install_cm5.sh` aus, das einen eigenen Benutzer, ein eigenes Verzeichnis und systemd-Einheiten auf eigenen Ports für Server und Studio anlegt und, mit Optionen, den MQTT-Broker, den Netzwerkknoten, den Beobachtungsdienst, das Sprach-Gateway, den Administrationsagenten, den Wartungshelfer und die tägliche Sicherung. Es berührt nie, was die Maschine sonst ausführt.
* **Der Wartungshelfer** (`armor_maintenance_agent.py`): die Updates der eigenen Komponenten der Anlage von GitHub (er lädt das Release-Paket, prüft seinen SHA-256 und tauscht es mit Rückfall ein), die des Betriebssystems und eine optionale Root-Konsole, alles vom Reiter *Updates* in Studio aus gesteuert; die Konsole ist aus, solange sie nicht eingeschaltet wird. Es behält die sechs neuesten beiseitegelegten Kopien und weniger, wenn die Platte fast voll ist (`ARMOR_MAINT_MIN_FREE_MB` in seiner Einstellungsdatei: standardmäßig 500, 0 schaltet es ab).
* **Der Administrationsagent** (`armor_admin_agent.py`): der einzige privilegierte Teil, mit einer geschlossenen Liste von Diensten, Einstellungsdateien und Broker-Konten, sodass Studio nie Root braucht.
* **Pakete jeder Version:** `scripts/package_component.py` baut das Paket einer Komponente (Studio, Server, Netzwerk, Beobachtungsdienst, Sprach-Gateway, DevOps), schreibt seinen SHA-256 daneben und veröffentlicht es als GitHub-Release.
* **Compose-Topologie:** ein nicht anonymer Mosquitto-Broker mit einer Identität je Knoten und einer ACL (einschließlich der Alarmknoten und der Zigbee-Zonen, die der Server ihnen sagt), der Server und Studio hinter einem nginx, der `/api/` weiterleitet; nur Studio wird veröffentlicht, auf Loopback. Gehärtete Container, festgelegte Images, ein internes Kernnetz und benannte Volumes für den Zustand.
* **TLS:** ein optionales `tls`-Compose-Profil stellt Caddy mit eigener lokaler Zertifizierungsstelle vor Studio, und eine Mosquitto-Konfiguration über TLS wird mitgeliefert ([Details](docs/BACKUP_AND_TLS.md)).
* **Eine Host-Firewall für die Kernmaschine** (`scripts/firewall_core.sh`): der Broker-Port nur aus dem Feldnetz, die Ports von Server und Studio nur aus dem Netz der Clients (wenn angegeben), in einer eigenen Tabelle, die nichts anderes erwähnt.
* **Geheimnisse:** `scripts/generate_secrets.sh` erzeugt zufällige Geheimnisse und gibt keines aus; `scripts/check-required-env.sh` lehnt fehlende, Platzhalter-, zu kurze oder wiederholte Werte ab.
* **Sicherung und Wiederherstellung:** `scripts/backup_data.sh` erzeugt ein AES-256-verschlüsseltes, verifiziertes Archiv der Serverdaten mit Prüfsumme (Beweise nur auf Wunsch); `scripts/restore_data.sh` listet es auf oder stellt es wieder her, ohne je vorhandene Daten zu überschreiben.
* **Ein VPN und ein Name für das Haus, aus Studio eingerichtet:** `armor_wireguard.sh` baut mit wenigen Befehlen ein WireGuard-VPN (Schlüssel auf der Maschine, je Handy eine Konfiguration mit QR-Code, bei Bedarf Routing zu den Knoten) und `armor_ddns.sh` hält einen Namen bei DuckDNS, Cloudflare oder anderswo auf das Haus gerichtet, wenn der Anbieter die Adresse ändert; der Wartungsagent bietet beides Studio und dem Handy an, sodass niemand einen Befehl tippen muss, und eine Schritt-für-Schritt-Anleitung in acht Sprachen deckt den Router ab.
* **Signierte Pakete:** der Wartungsassistent installiert ein Paket des Servers, von Studio oder eines anderen Programms nur mit gültiger Ed25519-Signatur des Release-Schlüssels des Projekts (in reinem Python geprüft, ohne Zusatzsoftware); eine fehlende, falsche oder manipulierte Signatur lässt den Rechner unverändert. Eine Notfall-Ausnahme gibt es nur als Einstellung in der Datei des Rechners selbst.
* **Eine optionale verschlüsselte Tür zum Broker (MQTT über TLS):** `scripts/armor_mqtt_tls.sh` erstellt eine Zertifizierungsstelle für die Anlage (ihr Schlüssel bleibt auf dem Rechner, Modus `0600`), ein Broker-Zertifikat für die Namen und Adressen des Rechners und einen zweiten Mosquitto-Listener auf 8883 neben dem normalen, den es nie anfasst; es ist idempotent und bietet `status`, `export-ca`, `server-tls` und `remove` (Dateien werden beiseitegelegt, nie gelöscht). Getestet mit OpenSSL, auch mit echten Handshakes, und auf einem echten Mosquitto 2.0 ([Anleitung](docs/MQTT_TLS_deu.md)).
* **Zustandsberichte erlaubt:** Die Regeln des Brokers lassen jeden Knoten sein eigenes `armor/health/<Knoten>` schreiben und den Server `armor/health/#` lesen; `mqtt_identity.sh add` schreibt die Zeile für jede Knotenart, und `mqtt_identity.sh health-report <Rolle> <Knoten>` fügt sie einem früher installierten Knoten hinzu (idempotent, die vorherigen Regeln bleiben erhalten).
* **Broker-Regeln für die Knotensteuerung:** Nur die Identität des Servers darf auf `armor/control/+/command` veröffentlichen (das schließt `armor/control/all/command` ein); jeder Knoten liest sein eigenes Befehlsthema und das Rundsendethema und schreibt seine eigene Antwort auf `armor/control/<Knoten>/result`, mehr nicht. So kann kein Knoten einen anderen steuern, und das gestohlene Passwort eines Knotens kann die anderen nicht neu starten. `mqtt_identity.sh node-control` fügt einem früher installierten Knoten die drei Zeilen hinzu, und der ACL-Test prüft jede Knotenart.

## 🧩 Rolle in A.R.M.O.R.

ARMOR-DEVOPS ist der Weg, auf dem alles andere auf eine Maschine kommt und aktuell bleibt. Es installiert Server, Studio, den Netzwerkknoten, die Beobachtungs- und Sprachdienste und den Broker am CM5-Testaufbau, erstellt die Pakete jeder Version, die der Reiter *Updates* von [ARMOR-STUDIO](https://github.com/JuanenRac/ARMOR-STUDIO) von GitHub installiert, und hält die zwei kleinen Helfer, mit denen Studio die Anlage aktualisieren und ihre Dienste verwalten kann, ohne je als Root zu laufen.

| Er spricht mit | Wie | Wozu |
|---|---|---|
| ARMOR-STUDIO | sein Tab *Updates* fragt den Wartungshelfer über einen lokalen Socket | es braucht nie root |
| GitHub Releases | `package_component.py` veröffentlicht das Paket mit SHA-256 und Signatur | die zu installierenden Komponenten |
| ARMOR-SERVER, ARMOR-NETWORK, ARMOR-SERVER-AI, ARMOR-VOICE-AI | als eigene systemd-Einheiten installiert | die Dienste des Prüfstands |
| ARMOR-UPDATER | getrennt | das Werkzeug dessen, der eine Kopie der Familie auf einem PC hält; dieses Repository ist für den CM5 und die Compose-Topologie |

## 🏛️ Architektur

<p align="center">
  <img src="images/architecture.svg" alt="ARMOR-DEVOPS architecture: where the packages come from, the deployment kit with its installer, helpers and Compose topology, and the bench and broker it sets up" width="100%">
</p>

## 🔒 Sicherheit und Schutz

| Bedrohung | Abwehr |
|---|---|
| Störung anderer Software auf dem CM5 | Eigener Benutzer, eigenes Verzeichnis und eigene Ports (Server 18080, Studio 18081, MQTT 18883 und Sprache 18090, alle zwischen 1024 und 65535 und verschieden, nie der Standard 1883); die System-Firewall wird nicht berührt |
| Ein offener oder nicht authentifizierter Broker | `allow_anonymous false`, eine Passwortdatei und eine ACL (Geheimnisse in `/run/secrets`), eine Identität je Knoten; nur der Server darf `armor/control/+/command` veröffentlichen; jeder Knoten liest seinen Befehl und den Rundruf und schreibt nur sein `armor/control/<Knoten>/result` und `armor/health/<Knoten>`; der Server liest `armor/health/#` |
| Versehentliches Lauschen im Netz | Compose veröffentlicht Broker und Studio nur auf `127.0.0.1`, außer `ARMOR_MQTT_BIND`, `ARMOR_STUDIO_BIND` (und `ARMOR_TLS_BIND` für Caddy) sagen etwas anderes |
| MQTT und Studio im Klartext | Optional: ein zweiter Mosquitto-Listener auf 8883 neben dem einfachen (`armor_mqtt_tls.sh`: eigene Stelle, Schlüssel im Modus `0600`, Zertifikat für die Namen der Maschine, idempotent, rührt den einfachen nie an) und ein Compose-Profil `tls` mit Caddy und eigener lokaler Stelle |
| Der Zentralrechner für alle offen | `firewall_core.sh` schreibt eine eigene Tabelle (`/etc/armor/firewall.nft`, mit Rückgängig-Einheit): der Broker-Port nur aus dem Feldnetz, die von Server und Studio nur aus dem Client-Netz; `check` prüft sie mit `nft -c` |
| Schwache oder ausgegebene Geheimnisse | `generate_secrets.sh` erzeugt zufällige Geheimnisse und gibt keines aus; `check-required-env.sh` weist fehlende, Platzhalter-, kurze oder wiederholte Werte ab |
| Eine gestohlene Sicherung | `backup_data.sh` erzeugt ein AES-256-verschlüsseltes, geprüftes Archiv mit Prüfsumme (Beweise nur auf Wunsch); `restore_data.sh` listet es auf oder stellt es wieder her, ohne je vorhandene Daten zu überschreiben |
| Ein gefälschtes Update einer Komponente | Der Wartungshelfer lädt das Release-Paket, prüft seinen SHA-256 und die Ed25519-Signatur des Release-Schlüssels des Projekts (in reinem Python) und tauscht es mit Rückgängig-Möglichkeit ein; eine fehlende, falsche oder manipulierte Signatur lässt die Maschine unverändert |
| Root aus Studio erreichbar | Nie nötig: Der Administrationsagent (`armor_admin_agent.py`) hat eine geschlossene Liste von Diensten, Einstellungsdateien und Broker-Konten; die Root-Konsole des Wartungshelfers ist aus, solange sie nicht eingeschaltet wird |

Die Container sind gehärtet, die Images fixiert, das Netz `core` ist intern und der Zustand liegt in benannten Volumes. Die zwei Helfer nutzen lokale Unix-Sockets, ihre Tests brauchen also Linux. Eine saubere Installation auf einer Maschine, die das Projekt nie sah, und die ganze Docker-Topologie auf ihrem Ziel sind nicht belegt; eine unabhängige Prüfung gab es nicht.

## 🔌 Schnittstellen

| Route | Authentifizierung | Was sie tut |
|---|---|---|
| `scripts/deploy_cm5.sh --host <cm5> --user <user> --key <key> --apply` | - | baut in einer sauberen Kopie, sendet ein Archiv per SSH und führt `install_cm5.sh` aus |
| `scripts/install_cm5.sh --public-host HOST [--apply]` | - | legt Benutzer, Verzeichnis und systemd-Einheiten an; `--server-port`, `--studio-port`, `--mqtt-port` und `--also-reach` passen es an; ohne `--apply` zeigt es nur den Plan |
| `scripts/package_component.py` | - | packt Studio, den Server, den Netzwerkknoten, den Beobachtungsdienst, das Sprach-Gateway oder DevOps so, wie der Wartungshelfer es installiert, schreibt den SHA-256 und veröffentlicht es als GitHub-Release |
| `scripts/generate_secrets.sh`  `scripts/check-required-env.sh` | - | `.env` und `secrets/` (von Git ignoriert); die Prüfung weist fehlende, Platzhalter-, kurze oder wiederholte Werte ab |
| `scripts/backup_data.sh --data-dir <d> --out-dir <o> --passphrase-file <f>` | - | das verschlüsselte, geprüfte Archiv der Serverdaten |
| `scripts/restore_data.sh` | - | listet ein Archiv oder stellt es her, ohne vorhandene Daten zu überschreiben |
| `scripts/firewall_core.sh apply, check --field <net> [--clients <net>]` | - | die Firewall-Tabelle des Zentralrechners; `check` prüft sie (`FIREWALL_CHECK=SKIP`, wenn `nft` fehlt) |
| `scripts/mqtt_identity.sh add`  `health-report <role> <node>`  `node-control` | - | schreibt die Broker-Zeile jeder Knotenart; ergänzt Gesundheitsberichte und Steuerung bei früher installierten Knoten (idempotent) |
| `scripts/armor_mqtt_tls.sh`  `armor_wireguard.sh`  `armor_ddns.sh`  `armor_tls_check.sh` | - | die verschlüsselte Tür des Brokers (`status`, `export-ca`, `server-tls`...), das WireGuard-VPN mit QR je Telefon, ein DuckDNS-, Cloudflare- oder anderer Name für das Haus und die Prüfung des Fernzugriffs; Studio bietet sie ohne Befehl an |

Die zwei Helfer (`armor_admin_agent.py`, `armor_maintenance_agent.py`) lauschen auf lokalen Unix-Sockets und laufen daher nicht unter Windows. Die Compose-Datei startet den Broker (Mosquitto), den Server und Studio (nginx, das `/api/` weiterleitet), und ein Profil `tls` ergänzt Caddy; nur Studio wird veröffentlicht, standardmäßig auf Loopback (`127.0.0.1:8088`, TLS auf 8443). Die Pakete jedes Releases sind Assets der GitHub-Releases, keine Dateien dieses Repositorys.

## ⚙️ Konfiguration

| Einstellung | Standard | Was sie tut |
|---|---|---|
| `install_cm5.sh` | 18080  18081  18883  18090 | `--server-port`, `--studio-port`, `--mqtt-port` (der installierte bleibt, wenn er nicht wiederholt wird) und der Sprach-Port; alle zwischen 1024 und 65535 und verschieden; die Broker-Adresse geht nach `PREFIX/etc/armor.mqtt.env` |
| `ARMOR_MQTT_BIND`  `ARMOR_STUDIO_BIND` | 127.0.0.1 | wo Compose Broker und Studio veröffentlicht |
| `ARMOR_PUBLIC_ORIGIN` | http://127.0.0.1:8088 | der Ursprung, unter dem Studio erreichbar ist |
| `ARMOR_TLS_BIND`  `ARMOR_TLS_PORT`  `ARMOR_TLS_HTTP_PORT` | 8443 | Caddy des Profils `tls` |
| `.env`  `.env.example` | - | von `generate_secrets.sh` erzeugt, von Git ignoriert; das Beispiel listet jede Variable |

Die Root-Konsole des Wartungshelfers ist eine Einstellung in der eigenen Datei der Maschine und standardmäßig aus; Firewall und TLS sind Optionen des Installers, keine Voreinstellungen. Einzelheiten in [docs/CM5_TEST_BENCH.md](docs/CM5_TEST_BENCH.md).

## 🚀 Schnellstart

**Voraussetzungen:** Docker Engine mit Compose (für die Container-Topologie), ein CM5 oder jede Debian-basierte Maschine per SSH (für den Prüfstand), Bash, `ssh` und `tar` auf der deployenden Maschine.

```bash
scripts/generate_secrets.sh                                                            # `.env` und `secrets/` (von Git ignoriert)
scripts/check-required-env.sh
docker compose config --quiet && docker compose up --build                             # die Container-Topologie
scripts/deploy_cm5.sh --host <cm5> --user <user> --key <key> --apply                   # der Prüfstand
scripts/backup_data.sh --data-dir <data> --out-dir <backups> --passphrase-file <file>  # eine verschlüsselte Sicherung
```

Siehe die [Grenze der Bereitstellung](docs/DEPLOYMENT_BOUNDARY.md) und den [Prüfstand](docs/CM5_TEST_BENCH.md).

## 🧪 Tests

| Bereich | Was er abdeckt |
|---|---|
| `test_admin_agent.py`  `.sh` | die geschlossene Liste des Administrationsagenten (braucht Linux: Unix-Sockets) |
| `test_maintenance_agent.py`  `.sh` | der Wartungshelfer: Download, SHA-256, Signatur, Tausch und Rückgängig (braucht Linux) |
| `test_package_component.py`  `test_registry.py`  `test_remote_access.py` | die Pakete, die Komponentenliste und die Fernzugriffs-Helfer |
| `test_backup.sh`  `test_env_and_restore.sh` | der Hin- und Rückweg von Sicherung und Wiederherstellung, die Geheimnisse und die Umgebungsprüfung |
| `test_compose.sh`  `validate-compose.sh` | die Compose-Topologie und ihr TLS-Profil, mit Docker Engine in WSL gebaut und ausgeführt |
| `test_firewall.sh`  `test_install_plan.sh`  `test_mqtt_identity.sh`  `test_mqtt_tls.sh`  `test_tls_check.sh`  `test_wireguard.sh`  `test_ddns.sh` | die Firewall, der Plan des Installers, die Broker-Identitäten, MQTT über TLS, die TLS-Prüfung, das VPN und der dynamische Name |

Die Python-Tests laufen mit `python -m unittest discover -s scripts -p "test_*.py"`; unter Windows können die drei, die Unix-Sockets brauchen, nicht laufen. Die Skripte brauchen Bash, WSL, Docker oder root und müssen unter Linux laufen. Eine einzige Testzahl gibt es noch nicht: Project status sagt, was gelaufen ist. GitHub Actions führt bei jedem Push und Pull Request die A.R.M.O.R.-Basis aus: die Prüfung von Manifest, Version, Änderungsprotokoll und README-Parität, dann den eigenen Build und die eigenen Tests des Projekts.

## 🏗️ Build und Veröffentlichung

Es wird nichts kompiliert: Es sind Skripte, eine Compose-Datei und Python-Helfer. `scripts/package_component.py` baut das Paket einer Komponente und schreibt den SHA-256 daneben; die Pakete sind Assets der GitHub-Releases, keine Dateien dieses Repositorys. Die Version steht in `armor.project.json` und im README-Badge (aus dem Manifest gelesen); jede Version hat ihren Eintrag in [CHANGELOG.md](CHANGELOG.md).

## 🩺 Fehlerbehebung

| Du siehst | Weil | Tu |
|---|---|---|
| `ports must be numbers between 1024 and 65535`  `the server and studio ports must differ` | ein Port von `install_cm5.sh` liegt außerhalb des Bereichs oder ist doppelt | verschiedene Ports zwischen 1024 und 65535 verwenden (nie den Standard 1883) |
| `--also-reach must look like http://HOST:PORT=http://HOST:PORT` | die zusätzliche Adresse ist nicht als Studio-Adresse = Serveradresse geschrieben | `--also-reach http://<Host>:<Studio-Port>=http://<Host>:<Server-Port>` schreiben |
| `FIREWALL_CHECK=SKIP nft is not installed here` | `nft` fehlt, `firewall_core.sh check` kann die Tabelle nicht prüfen | nftables auf der Maschine installieren und erneut prüfen |
| `AttributeError: module 'socketserver' has no attribute 'UnixStreamServer'` | die Tests der zwei Helfer laufen unter Windows | unter Linux (oder WSL) ausführen |

## 📂 Struktur des Repositorys

<p align="center">
  <img src="images/repository-structure.svg" alt="Repository structure of ARMOR-DEVOPS" width="100%">
</p>

<details>
<summary>Textversion des Baums</summary>

```text
ARMOR-DEVOPS/
├── scripts/
│   ├── deploy_cm5.sh install_cm5.sh                      auf den Prüfstand bringen, installieren
│   ├── package_component.py                              das Paket jedes Releases
│   ├── armor_admin_agent.py armor_maintenance_agent.py   die zwei Helfer von Studio
│   ├── generate_secrets.sh check-required-env.sh         zufällige Geheimnisse; weist schwache ab
│   ├── backup_data.sh restore_data.sh                    verschlüsselte Sicherung und Wiederherstellung
│   ├── firewall_core.sh mqtt_identity.sh                 Firewall und Broker-Identitäten
│   ├── armor_mqtt_tls.sh armor_tls_check.sh              MQTT über TLS und seine Prüfung
│   ├── armor_ddns.sh armor_wireguard.sh                  ein Name für das Haus und ein VPN
│   └── test_*.py test_*.sh validate-compose.sh           die Tests der Helfer und Skripte
├── docker-compose.yml docker-compose.tls.yml             Broker, Server, Studio; TLS-Profil
├── mosquitto/                                            mosquitto.conf, TLS-Konfig, acl.example
├── caddy/                                                Caddyfile: HTTPS vor Studio
├── docs/                                                 DEPLOYMENT_BOUNDARY, CM5_TEST_BENCH, BENCH_TESTS, BACKUP_AND_TLS, MQTT_TLS, HTTPS_PAIRING, REMOTE_ACCESS, SIGNED_PACKAGES (vier auch in acht Sprachen)
├── tools/                                                die gemeinsamen CI-Prüfungen und Werkzeuge
├── images/                                               Banner, Symbol und die Bilder des READMEs
├── .github/                                              CI-Workflow, Dashboard-Hinweis, Vorlagen für Issues und Pull Requests
├── armor.project.json                                    Manifest: Version, Rolle, Reife
├── CHANGELOG.md                                          was sich in jeder Version geändert hat
├── run.sh run.bat                                        Start, gemeinsamer Ablauf
├── build.sh build.bat                                    Bauen und Testen, gemeinsamer Ablauf
├── build-test.sh build-test.bat                          Bauen, Testen und Verpacken
├── test.sh test.bat                                      nur die Tests, nie die Version
└── SECURITY.md SUPPORT.md CONTRIBUTING.md CODE_OF_CONDUCT.md LICENSE
```

</details>

## 🗺️ Roadmap und bekannte Grenzen

**Bekannte Grenzen heute**

* Eine saubere Installation auf einer Maschine, die das Projekt nie sah, ist nicht belegt.
* Die ganze Docker-Topologie wurde mit Docker Engine in WSL gebaut und ausgeführt, aber nicht auf ihrem Ziel, dem Jetson.
* Es gibt keine einzige Testzahl, und die Tests der zwei Helfer brauchen Linux.
* Keine unabhängige Sicherheitsprüfung.

**Als Nächstes**

* Eine saubere Installation auf einer neuen Maschine und die Docker-Topologie auf dem Jetson.

## 🌍 Sprachen

README und Texte gibt es auf Englisch, Spanisch, Französisch, Italienisch, Deutsch, Chinesisch, Japanisch und europäischem Portugiesisch.

## 🔗 Verwandte Projekte

**A.R.M.O.R.** (Autonomous Radar & Multimodal Observation Range) ist ein Perimeter-Sicherheitssystem aus unabhängigen Repositorys. Jedes hat eine eigene Version, eigene Tests und ein eigenes README; hier ist die Familie:

* **[ARMOR-COMMON](https://github.com/JuanenRac/ARMOR-COMMON)** - Nachrichtenverträge, Validierer, Konformitätsvektoren und generierte Typen
* **[ARMOR-NODE-RADAR](https://github.com/JuanenRac/ARMOR-NODE-RADAR)** - Feldknoten-Firmware für ESP32-S3 mit drei Radaren und eigenem Web-Panel
* **[ARMOR-NODE-SOLAR](https://github.com/JuanenRac/ARMOR-NODE-SOLAR)** - Protokolle für Solar-Wechselrichter und -Batterien und die Nachrichten eines Gateway-Knotens
* **[ARMOR-NODE-ELECTRICAL](https://github.com/JuanenRac/ARMOR-NODE-ELECTRICAL)** - Elektroknoten: Zähler, die Nachricht der Netzmesswerte und die Regeln fürs Schalten
* **[ARMOR-NODE-ALARM](https://github.com/JuanenRac/ARMOR-NODE-ALARM)** - Alarmknoten und Alarmzentrale: Zonen, Scharfschalten, Verzögerungen, Sirene und PIN, mit dem Server oder ohne ihn
* **[ARMOR-NODE-HMI](https://github.com/JuanenRac/ARMOR-NODE-HMI)** - Touch-Panel: der Systemzustand auf einem Wandbildschirm, Scharf- und Quittieren sowie das Zuhause des Sprachassistenten
* **[ARMOR-NETWORK](https://github.com/JuanenRac/ARMOR-NETWORK)** - Das lokale Netzwerk: seine Geräte, das Internet und was sich ändert
* **[ARMOR-SERVER](https://github.com/JuanenRac/ARMOR-SERVER)** - Zentraler Koordinator: Telemetrie, Alarme, Geräte, Solarmesswerte und Kameras
* **[ARMOR-STUDIO](https://github.com/JuanenRac/ARMOR-STUDIO)** - Web-Konsole: Kameras, Radar, Alarme, Solarenergie und 2D/3D-Standortdesigner
* **[ARMOR-ANDROID-CONTROL](https://github.com/JuanenRac/ARMOR-ANDROID-CONTROL)** - Android-Bedienclient mit Live-Radar in 2D/3D
* **[ARMOR-IOS-CONTROL](https://github.com/JuanenRac/ARMOR-IOS-CONTROL)** - iPhone-Bedienclient
* **[ARMOR-SERVER-AI](https://github.com/JuanenRac/ARMOR-SERVER-AI)** - Visuelle Inferenzrichtlinie, die ihre Entscheidungen erklärt und nie handelt
* **[ARMOR-VISION](https://github.com/JuanenRac/ARMOR-VISION)** - Kamerazonen, Masken und Erkennungsregeln für den Jetson Orin NX
* **[ARMOR-VOICE-AI](https://github.com/JuanenRac/ARMOR-VOICE-AI)** - Offline-Sprachabsichten mit einer nicht fälschbaren Bestätigung
* **[ARMOR-HARDWARE](https://github.com/JuanenRac/ARMOR-HARDWARE)** - Gehäuse, Elektronik und die Abnahmematrix am Prüfstand
* **ARMOR-DEVOPS** (dieses Repository) - Bereitstellung, CM5-Prüfstand, Backup und TLS
* **[ARMOR-SIMULATOR](https://github.com/JuanenRac/ARMOR-SIMULATOR)** - Offline-Telemetriesimulator mit wiederholbaren Fehlern
* **[ARMOR-UPDATER](https://github.com/JuanenRac/ARMOR-UPDATER)** - Erkennt, installiert und aktualisiert die eigenen Repositorys des Ökosystems
* **[ARMOR-DOCS](https://github.com/JuanenRac/ARMOR-DOCS)** - Architektur, Sicherheitsgrundlage und die Fähigkeitsmatrix

## 📚 Dokumentation

* [DEPLOYMENT_BOUNDARY](docs/DEPLOYMENT_BOUNDARY.md): was dieses Repository bereitstellt und was nicht
* [CM5_TEST_BENCH](docs/CM5_TEST_BENCH.md): der Installer, die Einheiten, die Ports und die Helfer des Prüfstands
* [BENCH_TESTS](docs/BENCH_TESTS.md): wie der Prüfstand getestet wird
* [BACKUP_AND_TLS](docs/BACKUP_AND_TLS.md): Sicherung und Wiederherstellung sowie das TLS-Profil von Compose
* [MQTT_TLS](docs/MQTT_TLS.md): die verschlüsselte Tür des Brokers (auch in acht Sprachen)
* [HTTPS_PAIRING](docs/HTTPS_PAIRING.md): dem Zertifikat eines Knotens vertrauen (auch in acht Sprachen)
* [REMOTE_ACCESS](docs/REMOTE_ACCESS.md): VPN, ein Name für das Haus und der Router, Schritt für Schritt (auch in acht Sprachen)
* [SIGNED_PACKAGES](docs/SIGNED_PACKAGES.md): die Signatur der Pakete (auch in acht Sprachen)
* [Fähigkeitsmatrix: was belegt ist und was nicht](https://github.com/JuanenRac/ARMOR-DOCS/blob/main/docs/CAPABILITY_MATRIX.md)
* [Projektkatalog: Versionen und wie die Repositorys voneinander abhängen](https://github.com/JuanenRac/ARMOR-DOCS/blob/main/docs/PROJECT_CATALOG.md)
* [Änderungsverlauf dieses Repositorys](CHANGELOG.md)

## 🤝 Mitwirken und Community

* Führe vor einem Pull Request `python -I tools/armor_ci_validate.py` und die Tests aus: Beide müssen bestehen. Siehe [CONTRIBUTING.md](CONTRIBUTING.md) und den [Verhaltenskodex](CODE_OF_CONDUCT.md).
* Das README gibt es in acht Sprachen, und es wird aus den Quellen in ARMOR-DOCS erzeugt: Eine Textänderung erfolgt dort.
* Eine Änderung an einer Nachricht zwischen Komponenten beginnt in ARMOR-COMMON.
* Beschreibe nichts als auf einer Platine funktionierend, was nur gebaut wurde.
* Melde eine Schwachstelle privat: [SECURITY.md](SECURITY.md). Fragen, Ideen und Meldungen: electrohobby3d@gmail.com ([SUPPORT.md](SUPPORT.md)).

## 👤 AUTOR

**JuanenRac (Electro Hobby 3D)** · electrohobby3d@gmail.com

## 📜 LIZENZ

GPL-3.0-or-later - siehe [LICENSE](LICENSE).
