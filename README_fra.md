<p align="center">
  <img src="images/ARMOR_BANNER.svg" alt="ARMOR-DEVOPS banner" width="100%">
</p>

# 🚀 ARMOR-DEVOPS

<p align="center">
  <a href="README.md">🇺🇸 English</a> |
  <a href="README_spa.md">🇪🇸 Español</a> |
  🇫🇷 <b>Français</b> |
  <a href="README_ita.md">🇮🇹 Italiano</a> |
  <a href="README_deu.md">🇩🇪 Deutsch</a> |
  <a href="README_zho.md">🇨🇳 简体中文</a> |
  <a href="README_jpn.md">🇯🇵 日本語</a>
</p>

### Topologie de déploiement et banc d'essai CM5 isolé

<p align="center">
  <img src="https://img.shields.io/badge/License-GPL%203.0-blue.svg" alt="GPL 3.0">
  <img src="https://img.shields.io/badge/Deploy-Docker%20Compose-2496ed.svg" alt="Deploy">
  <img src="https://img.shields.io/badge/Bench-systemd-FFB020.svg" alt="Bench">
  <img src="https://img.shields.io/badge/Maturity-functional-00E5FF.svg" alt="Maturity">
</p>

---

**Vérification d'honnêteté - ce qui fonctionne aujourd'hui:** L'installateur du banc CM5 a été exécuté sur une vraie CM5 qui héberge d'autres logiciels, restés en bonne santé. La topologie Docker Compose et son profil TLS facultatif ont été construits et exécutés pour de vrai avec Docker Engine dans WSL (`scripts/test_compose.sh`, 12 contrôles, qui ont trouvé et corrigé trois défauts), mais **pas sur le Jetson**. Les scripts de sauvegarde et de restauration ont un test aller-retour réussi.

---

## 🎯 Présentation

* **Un pare-feu de la machine centrale** (`scripts/firewall_core.sh`) : le port du broker seulement depuis le réseau de terrain, ceux du serveur et de Studio seulement depuis le réseau des clients (s'il est donné), dans une table à part qui ne mentionne rien d'autre et accepte le reste ; `apply --rollback-after` retire de nouveau les règles si vous ne les confirmez pas, une erreur ne peut donc pas vous enfermer dehors. Les règles et les refus sont testés (36 contrôles, rien n'est chargé) ; il n'a été chargé sur aucune machine, et les VLAN eux-mêmes restent un plan pour le routeur et le commutateur.
* **Banc d'essai CM5 :** `scripts/deploy_cm5.sh` construit dans une copie propre, envoie une archive et exécute `scripts/install_cm5.sh`, qui crée son propre utilisateur, son propre répertoire et deux unités systemd sur leurs propres ports (trois avec `--with-mqtt` : le Mosquitto propre d'A.R.M.O.R. sur le port 18883, vérifié sur une vraie CM5), avec des limites de ressources, et ne touche jamais un autre projet ([détails](docs/CM5_TEST_BENCH.md)).
* **Topologie Compose :** un broker Mosquitto non anonyme avec une identité par nœud, le serveur, et Studio derrière un nginx qui relaie `/api/` ; seul Studio est publié, sur le bouclage. Conteneurs durcis, réseau interne pour le cœur et volumes nommés pour l'état.
* **Appareils et relevés sur le broker du banc :** le serveur peut écouter et commander `armor/device/#` et lire `armor/node/+/info`, `armor/solar/#` et `armor/electrical/#` ; `scripts/mqtt_identity.sh add device NAME` donne à un appareil ses propres sujets et `add bridge NAME` à un pont Zigbee2MQTT ou Shelly tous les sujets. `scripts/mqtt_identity.sh electrical-switching NODE_ID on` est la seule chose qui permet au serveur de commander le commutateur d'un nœud électrique (désactivé par défaut ; `off` le retire).
* **Secrets :** `scripts/generate_secrets.sh` crée des secrets aléatoires sans en afficher ; `scripts/check-required-env.sh` refuse les valeurs absentes, d'exemple, courtes ou répétées.
* **Sauvegarde et restauration :** `scripts/backup_data.sh` crée une archive chiffrée AES-256, vérifiée et avec somme de contrôle des données du serveur (sans les preuves sauf demande) ; `scripts/restore_data.sh` la liste ou la restaure sans jamais écraser de données existantes. La clé des caméras n'est volontairement **pas** dans l'archive.
* **TLS :** un profil Compose `tls` facultatif place Caddy, avec sa propre autorité de certification locale, devant Studio ([détails](docs/BACKUP_AND_TLS.md)).

## 📂 Structure du dépôt

```text
ARMOR-DEVOPS/
├── docker-compose.yml, .env.example, mosquitto/
├── caddy/     Caddyfile (TLS)
├── scripts/   deploy_cm5, install_cm5, generate_secrets, check-required-env, validate-compose, backup_data, restore_data, test_backup, test_compose, firewall_core, test_firewall, mqtt_identity
└── docs/      DEPLOYMENT_BOUNDARY, CM5_TEST_BENCH, BACKUP_AND_TLS
```

## 🛠️ Environnement de développement

```bash
scripts/generate_secrets.sh          # .env and secrets/ (Git-ignored)
scripts/check-required-env.sh
docker compose config --quiet && docker compose up --build
scripts/deploy_cm5.sh --host <cm5> --user <user> --key <key> --apply   # the test bench
scripts/backup_data.sh --data-dir <data> --out-dir <backups> --passphrase-file <file>
```

Voir la [frontière de déploiement](docs/DEPLOYMENT_BOUNDARY.md).

## 🔗 Projets liés

**A.R.M.O.R.** (Autonomous Radar & Multimodal Observation Range) est un système de sécurité périmétrique composé de dépôts indépendants. Chacun a sa propre version, ses propres tests et son propre README ; voici la famille :

* **[ARMOR-COMMON](../ARMOR-COMMON)** - Contrats de messages, validateurs, vecteurs de conformité et types générés
* **[ARMOR-RADAR](../ARMOR-RADAR)** - Firmware du nœud de terrain pour ESP32-S3 avec trois radars et son propre panneau web
* **[ARMOR-SOLAR](../ARMOR-SOLAR)** - Protocoles des onduleurs et batteries solaires et messages d'un nœud passerelle
* **[ARMOR-ELECTRICAL](../ARMOR-ELECTRICAL)** - Nœud électrique : compteurs, le message des mesures du réseau et les règles de commutation
* **[ARMOR-NETWORK](../ARMOR-NETWORK)** - Le réseau local : ses appareils, internet et ce qui change
* **[ARMOR-SERVER](../ARMOR-SERVER)** - Coordinateur central : télémétrie, alarmes, appareils, relevés solaires et caméras
* **[ARMOR-STUDIO](../ARMOR-STUDIO)** - Console web : caméras, radar, alarmes, énergie solaire et concepteur de site 2D/3D
* **[ARMOR-ANDROID-CONTROL](../ARMOR-ANDROID-CONTROL)** - Client Android de l'opérateur avec radar 2D/3D en direct
* **[ARMOR-SERVER-AI](../ARMOR-SERVER-AI)** - Politique d'inférence visuelle qui explique ses décisions et n'agit jamais
* **[ARMOR-VOICE-AI](../ARMOR-VOICE-AI)** - Intentions vocales hors ligne avec une confirmation impossible à falsifier
* **[ARMOR-HARDWARE](../ARMOR-HARDWARE)** - Boîtiers, électronique et matrice d'acceptation sur banc
* **ARMOR-DEVOPS** (ce dépôt) - Déploiement, banc d'essai CM5, sauvegarde et TLS
* **[ARMOR-SIMULATOR](../ARMOR-SIMULATOR)** - Simulateur de télémétrie hors ligne avec des pannes reproductibles
* **[ARMOR-DOCS](../ARMOR-DOCS)** - Architecture, base de sécurité et matrice des capacités

## 📚 Documentation et communauté

Pour en savoir plus :

* [Matrice des capacités : ce qui est prouvé et ce qui ne l'est pas](../ARMOR-DOCS/docs/CAPABILITY_MATRIX.md)
* [Catalogue des projets : versions et dépendances entre les dépôts](../ARMOR-DOCS/docs/PROJECT_CATALOG.md)
* [Historique des modifications de ce dépôt](CHANGELOG.md)
* [Licence (GPL-3.0-or-later)](LICENSE)
* Questions, idées et rapports : electrohobby3d@gmail.com

## 👤 AUTEUR

**JuanenRac (Electro Hobby 3D)** · electrohobby3d@gmail.com

## 📜 LICENCE

GPL-3.0-or-later - voir [LICENSE](LICENSE).
