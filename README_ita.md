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
  <a href="README_jpn.md">🇯🇵 日本語</a> |
  <a href="README_por.md">🇵🇹 Português</a>
</p>

### Distribuzione, il banco di prova CM5, i suoi aggiornamenti da GitHub e la manutenzione dell'impianto

<p align="center">
  <img src="https://img.shields.io/badge/License-GPL%203.0-blue.svg" alt="GPL 3.0">
  <img src="https://img.shields.io/badge/Deploy-Docker%20Compose-2496ed.svg" alt="Deploy">
  <img src="https://img.shields.io/badge/Bench-systemd-FFB020.svg" alt="Bench">
  <img src="https://img.shields.io/badge/Version-0.6.6-0f6cbd.svg" alt="Version">
  <img src="https://img.shields.io/badge/Maturity-established-2EA44F.svg" alt="Maturity">
</p>

---

**Controllo di onestà - cosa funziona oggi:** L'installatore del banco CM5 è stato eseguito su una vera CM5 che ospita altro software, rimasto sano, e il banco funziona in uso quotidiano con il server, Studio, il nodo di rete, i servizi di osservazione e di voce, il broker e i due assistenti qui sotto; vi sono stati fatti aggiornamenti dei suoi componenti da GitHub (tramite Studio). La topologia Docker Compose e il suo profilo TLS opzionale sono stati costruiti ed eseguiti davvero con Docker Engine in WSL (`scripts/test_compose.sh`), ma **non sul Jetson**. Gli script di backup e ripristino hanno un test di andata e ritorno che passa, e i due assistenti hanno i propri test. Ciò che **non** è provato: un'installazione pulita su una macchina che non ha mai visto il progetto e l'intera topologia Docker sulla sua destinazione.

---

## 📋 In breve

| | |
|---|---|
| Versione | `0.6.6` |
| Maturità | Consolidato |
| Tecnologia | Docker Compose / Bash / YAML |
| Su hardware reale | Governa il banco di prova CM5 in uso quotidiano, su una vera CM5 che ospita altro software; non ancora sul Jetson |

## 🎯 Panoramica

* **Banco di prova CM5:** `scripts/deploy_cm5.sh` compila in una copia pulita, invia un archivio ed esegue `scripts/install_cm5.sh`, che crea il proprio utente, la propria directory e unità systemd su porte proprie per il server e Studio e, con opzioni, il broker MQTT, il nodo di rete, il servizio di osservazione, il gateway vocale, l'agente di amministrazione, l'assistente di manutenzione e il backup giornaliero. Non tocca mai ciò che la macchina esegue per altro.
* **L'assistente di manutenzione** (`armor_maintenance_agent.py`): gli aggiornamenti dei componenti dell'impianto da GitHub (scarica il pacchetto della versione, controlla il suo SHA-256 e lo sostituisce con ripristino), quelli del sistema operativo e una console root facoltativa, tutto guidato dalla scheda *Aggiornamenti* di Studio; la console è spenta salvo attivazione. Conserva le sei copie più recenti che mette da parte, e meno quando il disco è quasi pieno (`ARMOR_MAINT_MIN_FREE_MB` nel suo file di impostazioni: 500 per impostazione predefinita, 0 lo disattiva).
* **L'agente di amministrazione** (`armor_admin_agent.py`): l'unica parte privilegiata, con un elenco chiuso di servizi, file di impostazioni e account del broker, così Studio non ha mai bisogno di root.
* **Pacchetti di ogni versione:** `scripts/package_component.py` costruisce il pacchetto di un componente (Studio, server, rete, servizio di osservazione, gateway vocale, DevOps), scrive il suo SHA-256 accanto e lo pubblica come release GitHub.
* **Topologia Compose:** un broker Mosquitto non anonimo con un'identità per nodo e una ACL (compresi i nodi d'allarme e le zone Zigbee che il server dice loro), il server e Studio dietro un nginx che fa da proxy di `/api/`; solo Studio è pubblicato, su loopback. Container rinforzati, immagini fissate, una rete interna del nucleo e volumi con nome per lo stato.
* **TLS:** un profilo `tls` facoltativo di Compose mette Caddy, con la propria autorità di certificazione locale, davanti a Studio, ed è fornita una configurazione Mosquitto su TLS ([dettagli](docs/BACKUP_AND_TLS.md)).
* **Un firewall di host per la macchina centrale** (`scripts/firewall_core.sh`): la porta del broker solo dalla rete di campo, quelle del server e di Studio solo dalla rete dei client (quando data), in una tabella propria che non menziona nient'altro.
* **Segreti:** `scripts/generate_secrets.sh` crea segreti casuali e non ne stampa nessuno; `scripts/check-required-env.sh` rifiuta valori mancanti, di esempio, corti o ripetuti.
* **Backup e ripristino:** `scripts/backup_data.sh` produce un archivio cifrato AES-256, verificato e con checksum dei dati del server (prove escluse salvo richiesta); `scripts/restore_data.sh` lo elenca o lo ripristina senza mai sovrascrivere dati esistenti.
* **Una VPN e un nome per la casa, configurati da Studio:** `armor_wireguard.sh` crea una VPN WireGuard con pochi comandi (chiavi sulla macchina, una configurazione per telefono con codice QR, instradamento verso i nodi se serve) e `armor_ddns.sh` mantiene un nome DuckDNS, Cloudflare o altro puntato alla casa quando l'operatore cambia l'indirizzo; l'agente di manutenzione offre entrambi a Studio e al telefono, quindi nessuno deve digitare un comando, e una guida passo passo in otto lingue copre il router.**Pacchetti firmati:** l'assistente di manutenzione installa un pacchetto del server, di Studio o di un altro programma solo se porta una firma Ed25519 valida della chiave di rilascio del progetto (verificata in puro Python, senza software aggiuntivo); una firma assente, errata o manomessa lascia la macchina invariata. Una deroga d'emergenza esiste solo come impostazione nel file della macchina stessa.
* **Una porta cifrata facoltativa verso il broker (MQTT su TLS):** `scripts/armor_mqtt_tls.sh` crea un'autorità di certificazione per l'installazione (la sua chiave resta sulla macchina, modo `0600`), un certificato del broker per i nomi e gli indirizzi della macchina e un secondo listener Mosquitto sull'8883 accanto a quello normale, che non tocca mai; è idempotente e ha `status`, `export-ca`, `server-tls` e `remove` (i file vengono messi da parte, mai cancellati). Provato con OpenSSL, con veri handshake, e su un vero Mosquitto 2.0 ([guida](docs/MQTT_TLS_ita.md)).
* **Rapporti di salute consentiti:** le regole del broker lasciano a ogni nodo scrivere il proprio `armor/health/<nodo>` e al server leggere `armor/health/#`; `mqtt_identity.sh add` scrive la riga per ogni tipo di nodo e `mqtt_identity.sh health-report <ruolo> <nodo>` la aggiunge a un nodo installato prima (idempotente, le regole precedenti vengono conservate).
* **Regole del broker per il controllo dei nodi:** solo l'identità del server può pubblicare su `armor/control/+/command` (che copre `armor/control/all/command`); ogni nodo legge il proprio argomento di ordini e quello di diffusione e scrive la propria risposta su `armor/control/<nodo>/result`, e nient'altro, così nessun nodo può comandarne un altro e la password rubata di un nodo non può riavviare gli altri. `mqtt_identity.sh node-control` aggiunge le tre righe a un nodo installato prima, e il test delle ACL controlla ogni tipo di nodo.

## 🧩 Ruolo in A.R.M.O.R.

ARMOR-DEVOPS è il modo in cui tutto il resto arriva su una macchina e resta aggiornato. Installa il server, Studio, il nodo di rete, i servizi di osservazione e di voce e il broker sul banco di prova CM5, fa i pacchetti di ogni versione che la scheda *Aggiornamenti* di [ARMOR-STUDIO](https://github.com/JuanenRac/ARMOR-STUDIO) installa da GitHub, e tiene i due piccoli assistenti che permettono a Studio di aggiornare l'impianto e gestire i suoi servizi senza mai girare come root.

## 📂 Struttura del repository

```text
ARMOR-DEVOPS/
├── docker-compose.yml, docker-compose.tls.yml, .env.example, mosquitto/ (broker, TLS profile, ACL example)
├── caddy/     Caddyfile (TLS)
├── scripts/   deploy_cm5, install_cm5, package_component, armor_admin_agent, armor_maintenance_agent, generate_secrets, check-required-env, backup_data, restore_data, firewall_core, mqtt_identity, armor_mqtt_tls (the optional encrypted door of the broker), tests of the agents, the backup, the firewall and the Compose topology
│   └── (package_component.py packs a program the way the maintenance helper installs it; the packages are assets of the GitHub releases, not files of this repository)
└── docs/      DEPLOYMENT_BOUNDARY, CM5_TEST_BENCH, BACKUP_AND_TLS, MQTT_TLS
```

## 🛠️ Ambiente di sviluppo

**Requisiti:** Docker Engine con Compose (per la topologia a container), un CM5 o qualsiasi macchina basata su Debian raggiungibile via SSH (per il banco di prova), Bash, `ssh` e `tar` sulla macchina che distribuisce

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

* **[ARMOR-COMMON](https://github.com/JuanenRac/ARMOR-COMMON)** - Contratti dei messaggi, validatori, vettori di conformità e tipi generati
* **[ARMOR-RADAR](https://github.com/JuanenRac/ARMOR-RADAR)** - Firmware del nodo di campo per ESP32-S3 con tre radar e un proprio pannello web
* **[ARMOR-SOLAR](https://github.com/JuanenRac/ARMOR-SOLAR)** - Protocolli di inverter e batterie solari e messaggi di un nodo gateway
* **[ARMOR-ELECTRICAL](https://github.com/JuanenRac/ARMOR-ELECTRICAL)** - Nodo elettrico: contatori, il messaggio delle letture della rete e le regole di manovra
* **[ARMOR-ALARM](https://github.com/JuanenRac/ARMOR-ALARM)** - Nodo e centrale d'allarme: zone, inserimento, ritardi, sirena e PIN, con il server o senza
* **[ARMOR-HMI](https://github.com/JuanenRac/ARMOR-HMI)** - Pannello touch: lo stato del sistema su uno schermo a parete, attivare e riconoscere gli allarmi, e la casa dell'assistente vocale
* **[ARMOR-NETWORK](https://github.com/JuanenRac/ARMOR-NETWORK)** - La rete locale: i suoi dispositivi, internet e ciò che cambia
* **[ARMOR-SERVER](https://github.com/JuanenRac/ARMOR-SERVER)** - Coordinatore centrale: telemetria, allarmi, dispositivi, letture solari e telecamere
* **[ARMOR-STUDIO](https://github.com/JuanenRac/ARMOR-STUDIO)** - Console web: telecamere, radar, allarmi, energia solare e progettista del sito 2D/3D
* **[ARMOR-ANDROID-CONTROL](https://github.com/JuanenRac/ARMOR-ANDROID-CONTROL)** - Client Android dell'operatore con radar 2D/3D in tempo reale
* **[ARMOR-SERVER-AI](https://github.com/JuanenRac/ARMOR-SERVER-AI)** - Politica di inferenza visiva che spiega le sue decisioni e non agisce mai
* **[ARMOR-VISION](https://github.com/JuanenRac/ARMOR-VISION)** - Zone delle telecamere, maschere e regole di rilevamento per la Jetson Orin NX
* **[ARMOR-VOICE-AI](https://github.com/JuanenRac/ARMOR-VOICE-AI)** - Intenti vocali offline con una conferma impossibile da falsificare
* **[ARMOR-HARDWARE](https://github.com/JuanenRac/ARMOR-HARDWARE)** - Contenitori, elettronica e matrice di accettazione da banco
* **ARMOR-DEVOPS** (questo repository) - Distribuzione, banco di prova CM5, backup e TLS
* **[ARMOR-SIMULATOR](https://github.com/JuanenRac/ARMOR-SIMULATOR)** - Simulatore di telemetria offline con guasti ripetibili
* **[ARMOR-UPDATER](https://github.com/JuanenRac/ARMOR-UPDATER)** - Rileva, installa e aggiorna i repository stessi dell'ecosistema
* **[ARMOR-DOCS](https://github.com/JuanenRac/ARMOR-DOCS)** - Architettura, base di sicurezza e matrice delle capacità

## 📚 Documentazione e comunità

Dove leggere di più:

* [Matrice delle capacità: cosa è provato e cosa no](https://github.com/JuanenRac/ARMOR-DOCS/blob/main/docs/CAPABILITY_MATRIX.md)
* [Catalogo dei progetti: versioni e dipendenze tra i repository](https://github.com/JuanenRac/ARMOR-DOCS/blob/main/docs/PROJECT_CATALOG.md)
* [Cronologia delle modifiche di questo repository](CHANGELOG.md)
* [Licenza (GPL-3.0-or-later)](LICENSE)
* Domande, idee e segnalazioni: electrohobby3d@gmail.com

## 👤 AUTORE

**JuanenRac (Electro Hobby 3D)** · electrohobby3d@gmail.com

## 📜 LICENZA

GPL-3.0-or-later - vedi [LICENSE](LICENSE).
