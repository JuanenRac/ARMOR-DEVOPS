<p align="center">
  <img src="images/ARMOR_BANNER.svg" alt="ARMOR-DEVOPS banner" width="100%">
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
  <img src="https://img.shields.io/badge/License-GPL%203.0-blue.svg" alt="GPL 3.0">
  <img src="https://img.shields.io/badge/Deploy-Docker%20Compose-2496ed.svg" alt="Deploy">
  <img src="https://img.shields.io/badge/Bench-systemd-FFB020.svg" alt="Bench">
  <img src="https://img.shields.io/badge/Version-0.6.6-0f6cbd.svg" alt="Version">
  <img src="https://img.shields.io/badge/Maturity-established-2EA44F.svg" alt="Maturity">
</p>

---

**Ehrlichkeitsprüfung - was heute läuft:** Der Installer des CM5-Testaufbaus wurde auf einem echten CM5 ausgeführt, der andere Software beherbergt und gesund blieb, und der Aufbau läuft im täglichen Einsatz mit dem Server, Studio, dem Netzwerkknoten, den Beobachtungs- und Sprachdiensten, dem Broker und den zwei Helfern unten; Updates seiner Komponenten von GitHub (über Studio) wurden darauf durchgeführt. Die Docker-Compose-Topologie und ihr optionales TLS-Profil wurden mit Docker Engine in WSL wirklich gebaut und ausgeführt (`scripts/test_compose.sh`), aber **nicht auf dem Jetson**. Die Sicherungs- und Wiederherstellungsskripte haben einen bestandenen Hin-und-zurück-Test, und die beiden Helfer haben eigene Tests. **Nicht** bewiesen: eine saubere Installation auf einer Maschine, die das Projekt noch nie gesehen hat, und die ganze Docker-Topologie auf ihrem Ziel.

---

## 📋 Auf einen Blick

| | |
|---|---|
| Version | `0.6.6` |
| Reifegrad | Etabliert |
| Technik | Docker Compose / Bash / YAML |
| Auf echter Hardware | Betreibt den CM5-Testaufbau im täglichen Einsatz, auf einem echten CM5, der andere Software beherbergt; noch nicht auf dem Jetson |

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
* **Ein VPN und ein Name für das Haus, aus Studio eingerichtet:** `armor_wireguard.sh` baut mit wenigen Befehlen ein WireGuard-VPN (Schlüssel auf der Maschine, je Handy eine Konfiguration mit QR-Code, bei Bedarf Routing zu den Knoten) und `armor_ddns.sh` hält einen Namen bei DuckDNS, Cloudflare oder anderswo auf das Haus gerichtet, wenn der Anbieter die Adresse ändert; der Wartungsagent bietet beides Studio und dem Handy an, sodass niemand einen Befehl tippen muss, und eine Schritt-für-Schritt-Anleitung in acht Sprachen deckt den Router ab.**Signierte Pakete:** der Wartungsassistent installiert ein Paket des Servers, von Studio oder eines anderen Programms nur mit gültiger Ed25519-Signatur des Release-Schlüssels des Projekts (in reinem Python geprüft, ohne Zusatzsoftware); eine fehlende, falsche oder manipulierte Signatur lässt den Rechner unverändert. Eine Notfall-Ausnahme gibt es nur als Einstellung in der Datei des Rechners selbst.
* **Eine optionale verschlüsselte Tür zum Broker (MQTT über TLS):** `scripts/armor_mqtt_tls.sh` erstellt eine Zertifizierungsstelle für die Anlage (ihr Schlüssel bleibt auf dem Rechner, Modus `0600`), ein Broker-Zertifikat für die Namen und Adressen des Rechners und einen zweiten Mosquitto-Listener auf 8883 neben dem normalen, den es nie anfasst; es ist idempotent und bietet `status`, `export-ca`, `server-tls` und `remove` (Dateien werden beiseitegelegt, nie gelöscht). Getestet mit OpenSSL, auch mit echten Handshakes, und auf einem echten Mosquitto 2.0 ([Anleitung](docs/MQTT_TLS_deu.md)).
* **Zustandsberichte erlaubt:** Die Regeln des Brokers lassen jeden Knoten sein eigenes `armor/health/<Knoten>` schreiben und den Server `armor/health/#` lesen; `mqtt_identity.sh add` schreibt die Zeile für jede Knotenart, und `mqtt_identity.sh health-report <Rolle> <Knoten>` fügt sie einem früher installierten Knoten hinzu (idempotent, die vorherigen Regeln bleiben erhalten).
* **Broker-Regeln für die Knotensteuerung:** Nur die Identität des Servers darf auf `armor/control/+/command` veröffentlichen (das schließt `armor/control/all/command` ein); jeder Knoten liest sein eigenes Befehlsthema und das Rundsendethema und schreibt seine eigene Antwort auf `armor/control/<Knoten>/result`, mehr nicht. So kann kein Knoten einen anderen steuern, und das gestohlene Passwort eines Knotens kann die anderen nicht neu starten. `mqtt_identity.sh node-control` fügt einem früher installierten Knoten die drei Zeilen hinzu, und der ACL-Test prüft jede Knotenart.

## 🧩 Rolle in A.R.M.O.R.

ARMOR-DEVOPS ist der Weg, auf dem alles andere auf eine Maschine kommt und aktuell bleibt. Es installiert Server, Studio, den Netzwerkknoten, die Beobachtungs- und Sprachdienste und den Broker am CM5-Testaufbau, erstellt die Pakete jeder Version, die der Reiter *Updates* von [ARMOR-STUDIO](https://github.com/JuanenRac/ARMOR-STUDIO) von GitHub installiert, und hält die zwei kleinen Helfer, mit denen Studio die Anlage aktualisieren und ihre Dienste verwalten kann, ohne je als Root zu laufen.

## 📂 Struktur des Repositorys

```text
ARMOR-DEVOPS/
├── docker-compose.yml, docker-compose.tls.yml, .env.example, mosquitto/ (broker, TLS profile, ACL example)
├── caddy/     Caddyfile (TLS)
├── scripts/   deploy_cm5, install_cm5, package_component, armor_admin_agent, armor_maintenance_agent, generate_secrets, check-required-env, backup_data, restore_data, firewall_core, mqtt_identity, armor_mqtt_tls (the optional encrypted door of the broker), tests of the agents, the backup, the firewall and the Compose topology
│   └── (package_component.py packs a program the way the maintenance helper installs it; the packages are assets of the GitHub releases, not files of this repository)
└── docs/      DEPLOYMENT_BOUNDARY, CM5_TEST_BENCH, BACKUP_AND_TLS, MQTT_TLS
```

## 🛠️ Entwicklungsumgebung

**Voraussetzungen:** Docker Engine mit Compose (für die Container-Topologie), ein CM5 oder ein beliebiger Debian-basierter Rechner per SSH erreichbar (für den Prüfstand), Bash, `ssh` und `tar` auf dem Rechner, der ausrollt

```bash
scripts/generate_secrets.sh          # .env and secrets/ (Git-ignored)
scripts/check-required-env.sh
docker compose config --quiet && docker compose up --build
scripts/deploy_cm5.sh --host <cm5> --user <user> --key <key> --apply   # the test bench
scripts/backup_data.sh --data-dir <data> --out-dir <backups> --passphrase-file <file>
```

Siehe die [Bereitstellungsgrenze](docs/DEPLOYMENT_BOUNDARY.md).

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
* **[ARMOR-UPDATER](https://github.com/JuanenRac/ARMOR-UPDATER)** - Erkennt, installiert und aktualisiert die eigenen Repositories des Ökosystems
* **[ARMOR-DOCS](https://github.com/JuanenRac/ARMOR-DOCS)** - Architektur, Sicherheitsgrundlage und die Fähigkeitsmatrix

## 📚 Dokumentation und Community

Hier gibt es mehr zu lesen:

* [Fähigkeitsmatrix: was belegt ist und was nicht](https://github.com/JuanenRac/ARMOR-DOCS/blob/main/docs/CAPABILITY_MATRIX.md)
* [Projektkatalog: Versionen und wie die Repositorys voneinander abhängen](https://github.com/JuanenRac/ARMOR-DOCS/blob/main/docs/PROJECT_CATALOG.md)
* [Änderungsverlauf dieses Repositorys](CHANGELOG.md)
* [Lizenz (GPL-3.0-or-later)](LICENSE)
* Fragen, Ideen und Meldungen: electrohobby3d@gmail.com

## 👤 AUTOR

**JuanenRac (Electro Hobby 3D)** · electrohobby3d@gmail.com

## 📜 LIZENZ

GPL-3.0-or-later - siehe [LICENSE](LICENSE).
