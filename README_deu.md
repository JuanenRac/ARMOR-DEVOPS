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
  <a href="README_jpn.md">🇯🇵 日本語</a>
</p>

### Bereitstellungstopologie und der isolierte CM5-Prüfstand

<p align="center">
  <img src="https://img.shields.io/badge/License-GPL%203.0-blue.svg" alt="GPL 3.0">
  <img src="https://img.shields.io/badge/Deploy-Docker%20Compose-2496ed.svg" alt="Deploy">
  <img src="https://img.shields.io/badge/Bench-systemd-FFB020.svg" alt="Bench">
  <img src="https://img.shields.io/badge/Maturity-functional-00E5FF.svg" alt="Maturity">
</p>

---

**Ehrlichkeitsprüfung - was heute läuft:** Der Installer des CM5-Prüfstands wurde auf einer echten CM5 ausgeführt, die andere Software hostet und gesund blieb. Die Docker-Compose-Topologie und ihr optionales TLS-Profil wurden mit der Docker Engine in WSL wirklich gebaut und ausgeführt (`scripts/test_compose.sh`, 12 Prüfungen, die drei Fehler fanden und behoben), aber **nicht auf dem Jetson**. Die Backup- und Wiederherstellungsskripte haben einen bestandenen Rundlauftest.

---

## 🎯 Überblick

* **Eine Host-Firewall für den zentralen Rechner** (`scripts/firewall_core.sh`): der Port des Brokers nur aus dem Feldnetz, die Ports von Server und Studio nur aus dem Netz der Clients (wenn angegeben), in einer eigenen Tabelle, die nichts anderes erwähnt und den Rest annimmt; `apply --rollback-after` entfernt die Regeln wieder, wenn Sie sie nicht bestätigen, ein Fehler sperrt Sie also nicht aus. Regeln und Ablehnungen sind getestet (36 Prüfungen, nichts wird geladen); sie wurde noch auf keinem Rechner geladen, und die VLANs selbst sind weiter ein Entwurf für Router und Switch.
* **CM5-Prüfstand:** `scripts/deploy_cm5.sh` baut in einer sauberen Kopie, sendet ein Archiv und führt `scripts/install_cm5.sh` aus, das einen eigenen Benutzer, ein eigenes Verzeichnis und zwei systemd-Units auf eigenen Ports anlegt (drei mit `--with-mqtt`: das eigene Mosquitto von A.R.M.O.R. auf Port 18883, auf einer echten CM5 geprüft), mit Ressourcenlimits, und nie ein anderes Projekt anfasst ([Details](docs/CM5_TEST_BENCH.md)).
* **Compose-Topologie:** ein nicht anonymer Mosquitto-Broker mit einer Identität je Knoten, der Server und Studio hinter einem nginx, der `/api/` weiterreicht; nur Studio wird veröffentlicht, auf Loopback. Gehärtete Container, ein internes Kernnetz und benannte Volumes für den Zustand.
* **Geräte und Messwerte am Broker des Prüfstands:** der Server darf `armor/device/#` hören und ansteuern und `armor/node/+/info` sowie `armor/solar/#` lesen; `scripts/mqtt_identity.sh add device NAME` gibt einem Gerät eigene Topics und `add bridge NAME` einer Zigbee2MQTT- oder Shelly-Brücke alle.
* **Geheimnisse:** `scripts/generate_secrets.sh` erzeugt zufällige Geheimnisse und druckt keines; `scripts/check-required-env.sh` lehnt fehlende, Platzhalter-, kurze oder wiederholte Werte ab.
* **Backup und Wiederherstellung:** `scripts/backup_data.sh` erstellt ein AES-256-verschlüsseltes, verifiziertes und mit Prüfsumme versehenes Archiv der Serverdaten (Beweise nur auf Wunsch); `scripts/restore_data.sh` listet es auf oder stellt es wieder her, ohne je vorhandene Daten zu überschreiben. Der Kameraschlüssel ist absichtlich **nicht** im Archiv.
* **TLS:** ein optionales Compose-Profil `tls` stellt Caddy mit eigener lokaler Zertifizierungsstelle vor Studio ([Details](docs/BACKUP_AND_TLS.md)).

## 📂 Struktur des Repositorys

```text
ARMOR-DEVOPS/
├── docker-compose.yml, .env.example, mosquitto/
├── caddy/     Caddyfile (TLS)
├── scripts/   deploy_cm5, install_cm5, generate_secrets, check-required-env, validate-compose, backup_data, restore_data, test_backup, test_compose, mqtt_identity
└── docs/      DEPLOYMENT_BOUNDARY, CM5_TEST_BENCH, BACKUP_AND_TLS
```

## 🛠️ Entwicklungsumgebung

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

* **[ARMOR-COMMON](../ARMOR-COMMON)** - Nachrichtenverträge, Validierer, Konformitätsvektoren und generierte Typen
* **[ARMOR-RADAR](../ARMOR-RADAR)** - Feldknoten-Firmware für ESP32-S3 mit drei Radaren und eigenem Web-Panel
* **[ARMOR-SOLAR](../ARMOR-SOLAR)** - Protokolle für Solar-Wechselrichter und -Batterien und die Nachrichten eines Gateway-Knotens
* **[ARMOR-ELECTRICAL](../ARMOR-ELECTRICAL)** - Elektroknoten: Zähler, die Nachricht der Netzmesswerte und die Regeln fürs Schalten
* **[ARMOR-SERVER](../ARMOR-SERVER)** - Zentraler Koordinator: Telemetrie, Alarme, Geräte, Solarmesswerte und Kameras
* **[ARMOR-STUDIO](../ARMOR-STUDIO)** - Web-Konsole: Kameras, Radar, Alarme, Solarenergie und 2D/3D-Standortdesigner
* **[ARMOR-ANDROID-CONTROL](../ARMOR-ANDROID-CONTROL)** - Android-Bedienclient mit Live-Radar in 2D/3D
* **[ARMOR-SERVER-AI](../ARMOR-SERVER-AI)** - Visuelle Inferenzrichtlinie, die ihre Entscheidungen erklärt und nie handelt
* **[ARMOR-VOICE-AI](../ARMOR-VOICE-AI)** - Offline-Sprachabsichten mit einer nicht fälschbaren Bestätigung
* **[ARMOR-HARDWARE](../ARMOR-HARDWARE)** - Gehäuse, Elektronik und die Abnahmematrix am Prüfstand
* **ARMOR-DEVOPS** (dieses Repository) - Bereitstellung, CM5-Prüfstand, Backup und TLS
* **[ARMOR-SIMULATOR](../ARMOR-SIMULATOR)** - Offline-Telemetriesimulator mit wiederholbaren Fehlern
* **[ARMOR-DOCS](../ARMOR-DOCS)** - Architektur, Sicherheitsgrundlage und die Fähigkeitsmatrix

## 📚 Dokumentation und Community

Hier gibt es mehr zu lesen:

* [Fähigkeitsmatrix: was belegt ist und was nicht](../ARMOR-DOCS/docs/CAPABILITY_MATRIX.md)
* [Projektkatalog: Versionen und wie die Repositorys voneinander abhängen](../ARMOR-DOCS/docs/PROJECT_CATALOG.md)
* [Änderungsverlauf dieses Repositorys](CHANGELOG.md)
* [Lizenz (GPL-3.0-or-later)](LICENSE)
* Fragen, Ideen und Meldungen: electrohobby3d@gmail.com

## 👤 AUTOR

**JuanenRac (Electro Hobby 3D)** · electrohobby3d@gmail.com

## 📜 LIZENZ

GPL-3.0-or-later - siehe [LICENSE](LICENSE).
