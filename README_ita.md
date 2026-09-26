<p align="center">
  <img src="images/ARMOR_BANNER.svg" alt="ARMOR-DEVOPS banner" width="100%">
</p>

# 🚀 ARMOR-DEVOPS

<p align="center">
  <a href="README.md">🇺🇸 English</a> |
  <a href="README_spa.md">🇪🇸 Español</a> |
  <a href="README_fra.md">🇫🇷 Français</a> |
  🇮🇹 <b>Italiano</b> |
  <a href="README_deu.md">🇩🇪 Deutsch</a> |
  <a href="README_zho.md">🇨🇳 简体中文</a> |
  <a href="README_jpn.md">🇯🇵 日本語</a>
</p>

### Topologia di distribuzione e banco di prova CM5 isolato

<p align="center">
  <img src="https://img.shields.io/badge/License-GPL%203.0-blue.svg" alt="GPL 3.0">
  <img src="https://img.shields.io/badge/Deploy-Docker%20Compose-2496ed.svg" alt="Deploy">
  <img src="https://img.shields.io/badge/Bench-systemd-FFB020.svg" alt="Bench">
  <img src="https://img.shields.io/badge/Maturity-functional-00E5FF.svg" alt="Maturity">
</p>

---

**Controllo di onestà - cosa funziona oggi:** L'installatore del banco CM5 è stato eseguito su una vera CM5 che ospita altro software, rimasto in salute. La topologia Docker Compose e il suo profilo TLS opzionale sono stati costruiti ed eseguiti davvero con Docker Engine in WSL (`scripts/test_compose.sh`, 12 controlli, che hanno trovato e corretto tre difetti), ma **non sul Jetson**. Gli script di backup e ripristino hanno un test di andata e ritorno superato.

---

## 🎯 Panoramica

* **Un firewall della macchina centrale** (`scripts/firewall_core.sh`): la porta del broker solo dalla rete di campo, quelle del server e di Studio solo dalla rete dei client (se indicata), in una tabella propria che non nomina altro e accetta il resto; `apply --rollback-after` toglie di nuovo le regole se non le confermi, così un errore non ti chiude fuori. Le regole e i rifiuti sono testati (36 controlli, non si carica nulla); non è stato caricato su nessuna macchina e le VLAN restano un progetto per router e switch.
* **Banco di prova CM5:** `scripts/deploy_cm5.sh` costruisce in una copia pulita, invia un archivio ed esegue `scripts/install_cm5.sh`, che crea un proprio utente, una propria cartella e due unità systemd su porte proprie (tre con `--with-mqtt`: il Mosquitto proprio di A.R.M.O.R. sulla porta 18883, verificato su una vera CM5), con limiti di risorse, e non tocca mai un altro progetto ([dettagli](docs/CM5_TEST_BENCH.md)).
* **Topologia Compose:** un broker Mosquitto non anonimo con un'identità per nodo, il server e Studio dietro un nginx che inoltra `/api/`; solo Studio è pubblicato, sul loopback. Container rinforzati, una rete interna per il nucleo e volumi con nome per lo stato.
* **Dispositivi e letture sul broker del banco:** il server può ascoltare e comandare `armor/device/#` e leggere `armor/node/+/info`, `armor/solar/#` e `armor/electrical/#`; `scripts/mqtt_identity.sh add device NAME` dà a un dispositivo i propri topic e `add bridge NAME` a un bridge Zigbee2MQTT o Shelly tutti.
* **Segreti:** `scripts/generate_secrets.sh` crea segreti casuali senza stamparne nessuno; `scripts/check-required-env.sh` rifiuta valori mancanti, di esempio, corti o ripetuti.
* **Backup e ripristino:** `scripts/backup_data.sh` crea un archivio cifrato AES-256, verificato e con checksum dei dati del server (senza le prove salvo richiesta); `scripts/restore_data.sh` lo elenca o lo ripristina senza mai sovrascrivere dati esistenti. La chiave delle telecamere volutamente **non** è nell'archivio.
* **TLS:** un profilo Compose `tls` opzionale mette Caddy, con una propria autorità di certificazione locale, davanti a Studio ([dettagli](docs/BACKUP_AND_TLS.md)).

## 📂 Struttura del repository

```text
ARMOR-DEVOPS/
├── docker-compose.yml, .env.example, mosquitto/
├── caddy/     Caddyfile (TLS)
├── scripts/   deploy_cm5, install_cm5, generate_secrets, check-required-env, validate-compose, backup_data, restore_data, test_backup, test_compose, firewall_core, test_firewall, mqtt_identity
└── docs/      DEPLOYMENT_BOUNDARY, CM5_TEST_BENCH, BACKUP_AND_TLS
```

## 🛠️ Ambiente di sviluppo

```bash
scripts/generate_secrets.sh          # .env and secrets/ (Git-ignored)
scripts/check-required-env.sh
docker compose config --quiet && docker compose up --build
scripts/deploy_cm5.sh --host <cm5> --user <user> --key <key> --apply   # the test bench
scripts/backup_data.sh --data-dir <data> --out-dir <backups> --passphrase-file <file>
```

Vedi il [confine di distribuzione](docs/DEPLOYMENT_BOUNDARY.md).

## 🔗 Progetti correlati

**A.R.M.O.R.** (Autonomous Radar & Multimodal Observation Range) è un sistema di sicurezza perimetrale fatto di repository indipendenti. Ognuno ha la propria versione, i propri test e il proprio README; ecco la famiglia:

* **[ARMOR-COMMON](../ARMOR-COMMON)** - Contratti dei messaggi, validatori, vettori di conformità e tipi generati
* **[ARMOR-RADAR](../ARMOR-RADAR)** - Firmware del nodo di campo per ESP32-S3 con tre radar e un proprio pannello web
* **[ARMOR-SOLAR](../ARMOR-SOLAR)** - Protocolli di inverter e batterie solari e messaggi di un nodo gateway
* **[ARMOR-ELECTRICAL](../ARMOR-ELECTRICAL)** - Nodo elettrico: contatori, il messaggio delle letture della rete e le regole di manovra
* **[ARMOR-SERVER](../ARMOR-SERVER)** - Coordinatore centrale: telemetria, allarmi, dispositivi, letture solari e telecamere
* **[ARMOR-STUDIO](../ARMOR-STUDIO)** - Console web: telecamere, radar, allarmi, energia solare e progettista del sito 2D/3D
* **[ARMOR-ANDROID-CONTROL](../ARMOR-ANDROID-CONTROL)** - Client Android dell'operatore con radar 2D/3D in tempo reale
* **[ARMOR-SERVER-AI](../ARMOR-SERVER-AI)** - Politica di inferenza visiva che spiega le sue decisioni e non agisce mai
* **[ARMOR-VOICE-AI](../ARMOR-VOICE-AI)** - Intenti vocali offline con una conferma impossibile da falsificare
* **[ARMOR-HARDWARE](../ARMOR-HARDWARE)** - Contenitori, elettronica e matrice di accettazione da banco
* **ARMOR-DEVOPS** (questo repository) - Distribuzione, banco di prova CM5, backup e TLS
* **[ARMOR-SIMULATOR](../ARMOR-SIMULATOR)** - Simulatore di telemetria offline con guasti ripetibili
* **[ARMOR-DOCS](../ARMOR-DOCS)** - Architettura, base di sicurezza e matrice delle capacità

## 📚 Documentazione e comunità

Dove leggere di più:

* [Matrice delle capacità: cosa è provato e cosa no](../ARMOR-DOCS/docs/CAPABILITY_MATRIX.md)
* [Catalogo dei progetti: versioni e dipendenze tra i repository](../ARMOR-DOCS/docs/PROJECT_CATALOG.md)
* [Cronologia delle modifiche di questo repository](CHANGELOG.md)
* [Licenza (GPL-3.0-or-later)](LICENSE)
* Domande, idee e segnalazioni: electrohobby3d@gmail.com

## 👤 AUTORE

**JuanenRac (Electro Hobby 3D)** · electrohobby3d@gmail.com

## 📜 LICENZA

GPL-3.0-or-later - vedi [LICENSE](LICENSE).
