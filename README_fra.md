<p align="center">
  <img src="images/ARMOR_BANNER.svg" alt="Bannière d'ARMOR-DEVOPS" width="100%">
</p>

# 🚀 ARMOR-DEVOPS

<p align="center">
  <a href="README.md">🇺🇸 English</a> |
  <a href="README_spa.md">🇪🇸 Español</a> |
  🇫🇷 <b>Français</b> |
  <a href="README_ita.md">🇮🇹 Italiano</a> |
  <a href="README_deu.md">🇩🇪 Deutsch</a> |
  <a href="README_zho.md">🇨🇳 简体中文</a> |
  <a href="README_jpn.md">🇯🇵 日本語</a> |
  <a href="README_por.md">🇵🇹 Português</a>
</p>

### Déploiement, le banc de test CM5, ses mises à jour depuis GitHub et l'entretien de l'installation

<p align="center">
  <img src="https://img.shields.io/badge/License-GPL%203.0--or--later-blue.svg" alt="GPL 3.0 ou ultérieure">
  <img src="https://img.shields.io/badge/Deploy-Docker%20Compose-2496ed.svg" alt="Deploy">
  <img src="https://img.shields.io/badge/Bench-systemd-FFB020.svg" alt="Bench">
  <img src="https://img.shields.io/badge/Version-0.6.8-0f6cbd.svg" alt="Version">
  <img src="https://img.shields.io/badge/Maturity-established-2EA44F.svg" alt="Maturité">
</p>

---

**Vérification d'honnêteté - ce qui fonctionne aujourd'hui :** L'installateur du banc CM5 a été exécuté sur un vrai CM5 qui héberge d'autres logiciels, restés sains, et le banc fonctionne en usage quotidien avec le serveur, Studio, le nœud réseau, les services d'observation et de voix, le broker et les deux assistants ci-dessous ; des mises à jour de ses composants depuis GitHub (via Studio) y ont été faites. La topologie Docker Compose et son profil TLS facultatif ont été construits et exécutés pour de vrai avec Docker Engine dans WSL (`scripts/test_compose.sh`), mais **pas sur le Jetson**. Les scripts de sauvegarde et de restauration ont un test aller-retour qui passe, et les deux assistants ont leurs propres tests. Ce qui n'est **pas** prouvé : une installation propre sur une machine qui n'a jamais vu le projet et toute la topologie Docker sur sa cible.

---

## 📋 En un coup d'œil

| | |
|---|---|
| Version | `0.6.8` |
| Maturité | Établi |
| Rôle | Kit de déploiement : installateur du banc CM5, paquets de version, deux assistants, topologie Compose |
| Technologie | Bash, Python 3 (bibliothèque standard), Docker Compose, Mosquitto, Caddy, nginx, systemd |
| Tests | Un script de test pour chaque partie (`scripts/test_*.sh` et `test_*.py`) ; la topologie Compose est construite et exécutée avec Docker sous WSL |
| Contrat | Ports du banc : serveur 18080, Studio 18081, MQTT 18883 (jamais 1883), voix 18090 |
| Fonctionne sur | Un CM5 ou toute machine Debian joignable par SSH ; Docker Engine avec Compose pour la topologie de conteneurs |
| Sur matériel réel | Fait tourner le banc de test CM5 en usage quotidien, sur un vrai CM5 qui héberge d'autres logiciels ; pas encore sur le Jetson |
| Licence | GPL-3.0-or-later |

**Aller à :** [Présentation](#-présentation) · [Architecture](#-architecture) · [Sécurité](#-sécurité-et-protection) · [Interfaces](#-interfaces) · [Configuration](#-configuration) · [Démarrage rapide](#-démarrage-rapide) · [Tests](#-tests) · [Dépannage](#-dépannage) · [Structure](#-structure-du-dépôt) · [Liés](#-projets-liés)

## 🚦 État du projet

Chaque ligne est une partie de ce dépôt et le feu dit où elle en est aujourd'hui. Elle est écrite d'après ce que le dépôt peut montrer (tests, compilations, exécutions), pas d'après ce qui est prévu.

🟢 Fait et vérifié · 🟡 Fonctionne, avec des limites connues · 🟠 À moitié fait ou pas encore vérifié · 🔴 Pas fait ou ne fonctionne pas

| Domaine | État | Ce que cela veut dire ici |
|---|---|---|
| Logiciel | 🟡 | L'installateur du banc CM5 a tourné sur un vrai CM5 qui héberge d'autres logiciels, restés en bonne santé ; une installation propre sur une machine qui n'a jamais vu le projet n'est pas prouvée. |
| Tests | 🟡 | Les scripts de sauvegarde et de restauration ont un test aller-retour qui réussit, les deux assistants ont leurs propres tests, et la topologie Docker avec son profil TLS optionnel a été construite et exécutée avec Docker Engine sous WSL ; la topologie complète n'a pas tourné sur sa cible. |
| Matériel | 🟡 | Il fait tourner le banc d'essai CM5 au quotidien ; rien n'a tourné sur le Jetson. |
| Mises à jour | 🟢 | Les mises à jour des composants depuis GitHub, via Studio, ont été faites sur le banc d'essai CM5. |
| Documentation | 🟢 | Huit langues et le journal des modifications sont à jour. |

## 🎯 Présentation

* **Banc de test CM5 :** `scripts/deploy_cm5.sh` compile dans une copie propre, envoie une archive et lance `scripts/install_cm5.sh`, qui crée son propre utilisateur, son propre répertoire et des unités systemd sur leurs propres ports pour le serveur et Studio et, avec des options, le broker MQTT, le nœud réseau, le service d'observation, la passerelle vocale, l'agent d'administration, l'assistant de maintenance et la sauvegarde quotidienne. Il ne touche jamais à ce que la machine exécute par ailleurs.
* **L'assistant de maintenance** (`armor_maintenance_agent.py`) : les mises à jour des composants de l'installation depuis GitHub (il télécharge le paquet de la version, vérifie son SHA-256 et le remplace avec retour arrière), celles du système d'exploitation et une console root facultative, le tout piloté depuis l'onglet *Mises à jour* de Studio ; la console est désactivée sauf activation. Il garde les six copies les plus récentes qu'il met de côté, et moins quand le disque est presque plein (`ARMOR_MAINT_MIN_FREE_MB` dans son fichier de réglages : 500 par défaut, 0 le désactive).
* **L'agent d'administration** (`armor_admin_agent.py`) : la seule partie privilégiée, avec une liste fermée de services, de fichiers de réglages et de comptes du broker, si bien que Studio n'a jamais besoin de root.
* **Paquets de chaque version :** `scripts/package_component.py` construit le paquet d'un composant (Studio, serveur, réseau, service d'observation, passerelle vocale, DevOps), écrit son SHA-256 à côté et le publie comme version GitHub.
* **Topologie Compose :** un broker Mosquitto non anonyme avec une identité par nœud et une ACL (y compris les nœuds d'alarme et les zones Zigbee que leur dit le serveur), le serveur et Studio derrière un nginx qui fait proxy de `/api/` ; seul Studio est publié, sur la boucle locale. Conteneurs durcis, images épinglées, un réseau interne du cœur et des volumes nommés pour l'état.
* **TLS :** un profil `tls` facultatif de Compose place Caddy, avec sa propre autorité de certification locale, devant Studio, et une configuration Mosquitto sur TLS est fournie ([détails](docs/BACKUP_AND_TLS.md)).
* **Un pare-feu d'hôte pour la machine centrale** (`scripts/firewall_core.sh`) : le port du broker seulement depuis le réseau de terrain, ceux du serveur et de Studio seulement depuis le réseau des clients (quand il est donné), dans une table à part qui ne mentionne rien d'autre.
* **Secrets :** `scripts/generate_secrets.sh` crée des secrets aléatoires et n'en imprime aucun ; `scripts/check-required-env.sh` refuse les valeurs absentes, d'exemple, courtes ou répétées.
* **Sauvegarde et restauration :** `scripts/backup_data.sh` produit une archive chiffrée AES-256, vérifiée et avec somme de contrôle des données du serveur (preuves exclues sauf demande) ; `scripts/restore_data.sh` la liste ou la restaure sans jamais écraser de données existantes.
* **Un VPN et un nom pour la maison, configurés depuis Studio :** `armor_wireguard.sh` monte un VPN WireGuard en quelques commandes (clés sur la machine, une configuration par téléphone avec code QR, routage vers les nœuds si voulu) et `armor_ddns.sh` garde un nom DuckDNS, Cloudflare ou autre pointé sur la maison quand le fournisseur change l'adresse ; l'agent de maintenance propose les deux à Studio et au téléphone, personne n'a donc à taper une commande, et un guide pas à pas en huit langues couvre le routeur.
* **Paquets signés :** l'assistant de maintenance n'installe un paquet du serveur, de Studio ou d'un autre programme que s'il porte une signature Ed25519 valide de la clé de release du projet (vérifiée en Python pur, sans logiciel supplémentaire) ; une signature absente, fausse ou altérée laisse la machine inchangée. Une dérogation d'urgence n'existe que comme réglage dans le fichier de la machine elle-même.
* **Une porte chiffrée facultative vers le broker (MQTT sur TLS) :** `scripts/armor_mqtt_tls.sh` crée une autorité de certification pour l'installation (sa clé reste sur la machine, mode `0600`), un certificat de broker pour les noms et adresses de la machine et un second listener Mosquitto sur le 8883 à côté du normal, qu'il ne touche jamais ; il est idempotent et offre `status`, `export-ca`, `server-tls` et `remove` (les fichiers sont mis de côté, jamais supprimés). Testé avec OpenSSL, avec de vraies poignées de main, et sur un vrai Mosquitto 2.0 ([guide](docs/MQTT_TLS_fra.md)).
* **Rapports de santé autorisés :** les règles du broker laissent chaque nœud écrire son propre `armor/health/<nœud>` et le serveur lire `armor/health/#` ; `mqtt_identity.sh add` écrit la ligne pour chaque type de nœud et `mqtt_identity.sh health-report <rôle> <nœud>` l'ajoute à un nœud installé avant (idempotent, les règles précédentes sont conservées).
* **Règles du broker pour la commande des nœuds :** seule l'identité du serveur peut publier sur `armor/control/+/command` (qui couvre `armor/control/all/command`) ; chaque nœud lit son propre sujet d'ordres et celui de diffusion et écrit sa propre réponse sur `armor/control/<nœud>/result`, rien de plus, de sorte qu'aucun nœud ne peut commander un autre et que le mot de passe volé d'un nœud ne peut pas redémarrer les autres. `mqtt_identity.sh node-control` ajoute les trois lignes à un nœud installé avant, et le test des ACL vérifie chaque type de nœud.

## 🧩 Rôle dans A.R.M.O.R.

ARMOR-DEVOPS est la façon dont tout le reste arrive sur une machine et reste à jour. Il installe le serveur, Studio, le nœud réseau, les services d'observation et de voix et le broker sur le banc de test CM5, fait les paquets de chaque version que l'onglet *Mises à jour* d'[ARMOR-STUDIO](https://github.com/JuanenRac/ARMOR-STUDIO) installe depuis GitHub, et garde les deux petits assistants qui permettent à Studio de mettre à jour l'installation et de gérer ses services sans jamais tourner en root.

| Il parle à | Comment | Pour quoi faire |
|---|---|---|
| ARMOR-STUDIO | son onglet *Mises à jour* interroge l'assistant de maintenance par un socket local | il n'a jamais besoin de root |
| GitHub Releases | `package_component.py` publie le paquet avec son SHA-256 et sa signature | les composants à installer |
| ARMOR-SERVER, ARMOR-NETWORK, ARMOR-SERVER-AI, ARMOR-VOICE-AI | installés comme unités systemd propres | les services du banc |
| ARMOR-UPDATER | séparé | l'outil de qui garde une copie de la famille sur un PC ; ce dépôt est pour le CM5 et la topologie Compose |

## 🏛️ Architecture

<p align="center">
  <img src="images/architecture.svg" alt="ARMOR-DEVOPS architecture: where the packages come from, the deployment kit with its installer, helpers and Compose topology, and the bench and broker it sets up" width="100%">
</p>

## 🔒 Sécurité et protection

| Menace | Défense |
|---|---|
| Gêner d'autres logiciels du CM5 | Utilisateur, répertoire et ports propres (serveur 18080, Studio 18081, MQTT 18883 et voix 18090, tous entre 1024 et 65535 et différents, jamais le standard 1883) ; le pare-feu du système n'est pas touché |
| Un broker ouvert ou non authentifié | `allow_anonymous false`, un fichier de mots de passe et une ACL (secrets montés dans `/run/secrets`), une identité par nœud ; seul le serveur peut publier `armor/control/+/command` ; chaque nœud lit son ordre et celui de diffusion et n'écrit que son `armor/control/<nœud>/result` et `armor/health/<nœud>` ; le serveur lit `armor/health/#` |
| Écoute accidentelle sur le réseau | Compose ne publie le broker et Studio que sur `127.0.0.1` sauf si `ARMOR_MQTT_BIND`, `ARMOR_STUDIO_BIND` (et `ARMOR_TLS_BIND` pour Caddy) disent autre chose |
| MQTT et Studio en clair | Facultatif : un second écouteur Mosquitto sur 8883 à côté du simple (`armor_mqtt_tls.sh` : autorité propre, clé en mode `0600`, certificat pour les noms de la machine, idempotent, ne touche jamais le simple) et un profil `tls` de Compose avec Caddy et son autorité locale |
| La machine centrale ouverte à tous | `firewall_core.sh` écrit une table propre (`/etc/armor/firewall.nft`, avec une unité de retour arrière) : le port du broker seulement depuis le réseau de terrain, ceux du serveur et de Studio seulement depuis le réseau des clients ; `check` la vérifie avec `nft -c` |
| Secrets faibles ou imprimés | `generate_secrets.sh` crée des secrets aléatoires et n'en imprime aucun ; `check-required-env.sh` refuse les valeurs absentes, de modèle, courtes ou répétées |
| Une sauvegarde volée | `backup_data.sh` fait une archive chiffrée AES-256, vérifiée et avec somme de contrôle (preuves exclues sauf demande) ; `restore_data.sh` la liste ou la restaure sans jamais écraser de données existantes |
| Une fausse mise à jour d'un composant | L'assistant de maintenance télécharge le paquet de version, vérifie son SHA-256 et la signature Ed25519 de la clé de publication du projet (en Python pur) et le remplace avec retour arrière ; une signature absente, fausse ou altérée laisse la machine inchangée |
| Root accessible depuis Studio | Jamais nécessaire : l'agent d'administration (`armor_admin_agent.py`) a une liste fermée de services, fichiers de réglages et comptes du broker ; la console root de l'assistant de maintenance est éteinte sauf activation |

Les conteneurs sont durcis, les images épinglées, le réseau `core` interne et l'état dans des volumes nommés. Les deux assistants utilisent des sockets Unix locaux, leurs tests demandent donc Linux. Une installation propre sur une machine qui n'a jamais vu le projet et toute la topologie Docker sur sa cible ne sont pas éprouvées ; il n'y a pas eu de revue indépendante.

## 🔌 Interfaces

| Route | Authentification | Ce qu'elle fait |
|---|---|---|
| `scripts/deploy_cm5.sh --host <cm5> --user <user> --key <key> --apply` | - | construit dans une copie propre, envoie une archive par SSH et lance `install_cm5.sh` |
| `scripts/install_cm5.sh --public-host HOST [--apply]` | - | crée l'utilisateur, le répertoire et les unités systemd ; `--server-port`, `--studio-port`, `--mqtt-port` et `--also-reach` l'ajustent ; sans `--apply` il n'affiche que le plan |
| `scripts/package_component.py` | - | empaquette Studio, le serveur, le nœud réseau, le service d'observation, la passerelle vocale ou DevOps comme l'assistant de maintenance l'installe, écrit son SHA-256 et le publie comme version GitHub |
| `scripts/generate_secrets.sh`  `scripts/check-required-env.sh` | - | `.env` et `secrets/` (ignorés par Git) ; le contrôle refuse les valeurs absentes, de modèle, courtes ou répétées |
| `scripts/backup_data.sh --data-dir <d> --out-dir <o> --passphrase-file <f>` | - | l'archive chiffrée et vérifiée des données du serveur |
| `scripts/restore_data.sh` | - | liste une archive ou la restaure sans écraser de données existantes |
| `scripts/firewall_core.sh apply, check --field <net> [--clients <net>]` | - | la table de pare-feu de la machine centrale ; `check` la vérifie (`FIREWALL_CHECK=SKIP` si `nft` n'est pas installé) |
| `scripts/mqtt_identity.sh add`  `health-report <role> <node>`  `node-control` | - | écrit la ligne du broker de chaque type de nœud ; ajoute rapports de santé et contrôle à un nœud installé avant (idempotent) |
| `scripts/armor_mqtt_tls.sh`  `armor_wireguard.sh`  `armor_ddns.sh`  `armor_tls_check.sh` | - | la porte chiffrée du broker (`status`, `export-ca`, `server-tls`...), le VPN WireGuard avec un QR par téléphone, un nom DuckDNS, Cloudflare ou autre pour la maison et le contrôle de l'accès à distance ; Studio les propose sans taper de commande |

Les deux assistants (`armor_admin_agent.py`, `armor_maintenance_agent.py`) écoutent sur des sockets Unix locaux et ne tournent donc pas sous Windows. Le fichier Compose démarre le broker (Mosquitto), le serveur et Studio (nginx, qui relaie `/api/`), et un profil `tls` ajoute Caddy ; seul Studio est publié, en boucle locale par défaut (`127.0.0.1:8088`, TLS sur 8443). Les paquets de chaque version sont des ressources des versions GitHub, pas des fichiers de ce dépôt. Le journal d'une mise à jour du système indique `downloading: N%` tous les dix pour cent, pour qu'une liaison lente ne ressemble pas à une mise à jour bloquée, et une mise à jour ne réinstalle les dépendances (`npm ci`) que si ce que le fichier de verrouillage en dit a changé, pas simplement parce que le projet a une nouvelle version.

## ⚙️ Configuration

| Réglage | Par défaut | Ce qu'il fait |
|---|---|---|
| `install_cm5.sh` | 18080  18081  18883  18090 | `--server-port`, `--studio-port`, `--mqtt-port` (celui installé est conservé s'il n'est pas répété) et le port voix ; tous entre 1024 et 65535 et différents ; l'adresse du broker va dans `PREFIX/etc/armor.mqtt.env` |
| `ARMOR_MQTT_BIND`  `ARMOR_STUDIO_BIND` | 127.0.0.1 | où Compose publie le broker et Studio |
| `ARMOR_PUBLIC_ORIGIN` | http://127.0.0.1:8088 | l'origine par laquelle on joint Studio |
| `ARMOR_TLS_BIND`  `ARMOR_TLS_PORT`  `ARMOR_TLS_HTTP_PORT` | 8443 | Caddy du profil `tls` |
| `.env`  `.env.example` | - | créé par `generate_secrets.sh`, ignoré par Git ; l'exemple liste chaque variable |

La console root de l'assistant de maintenance est un réglage du propre fichier de la machine et est éteinte par défaut ; le pare-feu et le TLS sont des options de l'installateur, pas des valeurs par défaut. Détails dans [docs/CM5_TEST_BENCH.md](docs/CM5_TEST_BENCH.md).

## 🚀 Démarrage rapide

**Prérequis :** Docker Engine avec Compose (pour la topologie de conteneurs), un CM5 ou toute machine Debian joignable par SSH (pour le banc d'essai), Bash, `ssh` et `tar` sur la machine qui déploie.

```bash
scripts/generate_secrets.sh                                                            # `.env` et `secrets/` (ignorés par Git)
scripts/check-required-env.sh
docker compose config --quiet && docker compose up --build                             # la topologie de conteneurs
scripts/deploy_cm5.sh --host <cm5> --user <user> --key <key> --apply                   # le banc d'essai
scripts/backup_data.sh --data-dir <data> --out-dir <backups> --passphrase-file <file>  # une sauvegarde chiffrée
```

Voir la [frontière du déploiement](docs/DEPLOYMENT_BOUNDARY.md) et le [banc d'essai](docs/CM5_TEST_BENCH.md).

## 🧪 Tests

| Domaine | Ce qu'il couvre |
|---|---|
| `test_admin_agent.py`  `.sh` | la liste fermée de l'agent d'administration (demande Linux : sockets Unix) |
| `test_maintenance_agent.py`  `.sh` | l'assistant de maintenance : téléchargement, SHA-256, signature, remplacement et retour arrière (demande Linux) |
| `test_package_component.py`  `test_registry.py`  `test_remote_access.py` | les paquets, la liste des composants et les assistants d'accès à distance |
| `test_backup.sh`  `test_env_and_restore.sh` | l'aller-retour sauvegarde et restauration, les secrets et le contrôle de l'environnement |
| `test_compose.sh`  `validate-compose.sh` | la topologie Compose et son profil TLS, construites et exécutées avec Docker Engine sous WSL |
| `test_firewall.sh`  `test_install_plan.sh`  `test_mqtt_identity.sh`  `test_mqtt_tls.sh`  `test_tls_check.sh`  `test_wireguard.sh`  `test_ddns.sh` | le pare-feu, le plan de l'installateur, les identités du broker, MQTT sur TLS, le contrôle TLS, le VPN et le nom dynamique |

Les tests Python se lancent avec `python -m unittest discover -s scripts -p "test_*.py"` ; sous Windows les trois qui demandent des sockets Unix ne peuvent pas tourner. Les scripts demandent Bash, WSL, Docker ou root et doivent être lancés sous Linux. Il n'y a pas encore de nombre unique de tests : Project status dit ce qui a été exécuté. GitHub Actions exécute la base A.R.M.O.R. à chaque push et pull request : la validation du manifeste, de la version, du journal des modifications et de la parité des README, puis le build et les tests propres au projet.

## 🏗️ Compilation et publication

Rien n'est compilé : ce sont des scripts, un fichier Compose et des assistants Python. `scripts/package_component.py` construit le paquet d'un composant et écrit son SHA-256 à côté ; les paquets sont des ressources des versions GitHub, pas des fichiers de ce dépôt. La version se trouve dans `armor.project.json` et dans le badge du README (lu depuis le manifeste) ; chaque version a son entrée dans [CHANGELOG.md](CHANGELOG.md).

## 🩺 Dépannage

| Vous voyez | Parce que | Faites |
|---|---|---|
| `ports must be numbers between 1024 and 65535`  `the server and studio ports must differ` | un port de `install_cm5.sh` est hors plage ou répété | utilisez des ports différents entre 1024 et 65535 (jamais le standard 1883) |
| `--also-reach must look like http://HOST:PORT=http://HOST:PORT` | l'adresse supplémentaire n'est pas écrite comme adresse de Studio = adresse du serveur | écrivez `--also-reach http://<hôte>:<port-studio>=http://<hôte>:<port-serveur>` |
| `FIREWALL_CHECK=SKIP nft is not installed here` | `nft` manque, `firewall_core.sh check` ne peut donc pas vérifier la table | installez nftables sur la machine, puis vérifiez de nouveau |
| `AttributeError: module 'socketserver' has no attribute 'UnixStreamServer'` | les tests des deux assistants sont lancés sous Windows | lancez-les sous Linux (ou WSL) |

## 📂 Structure du dépôt

<p align="center">
  <img src="images/repository-structure.svg" alt="Repository structure of ARMOR-DEVOPS" width="100%">
</p>

<details>
<summary>Version texte de l'arborescence</summary>

```text
ARMOR-DEVOPS/
├── scripts/
│   ├── deploy_cm5.sh install_cm5.sh                      déploie sur le banc, l'installe
│   ├── package_component.py                              le paquet de chaque version
│   ├── armor_admin_agent.py armor_maintenance_agent.py   les deux assistants de Studio
│   ├── generate_secrets.sh check-required-env.sh         secrets aléatoires ; refuse les faibles
│   ├── backup_data.sh restore_data.sh                    sauvegarde chiffrée et restauration
│   ├── firewall_core.sh mqtt_identity.sh                 pare-feu et identités du broker
│   ├── armor_mqtt_tls.sh armor_tls_check.sh              MQTT sur TLS et sa vérification
│   ├── armor_ddns.sh armor_wireguard.sh                  un nom pour la maison et un VPN
│   └── test_*.py test_*.sh validate-compose.sh           les tests des assistants et scripts
├── docker-compose.yml docker-compose.tls.yml             broker, serveur, Studio ; profil TLS
├── mosquitto/                                            mosquitto.conf, config TLS, acl.example
├── caddy/                                                Caddyfile : HTTPS devant Studio
├── docs/                                                 DEPLOYMENT_BOUNDARY, CM5_TEST_BENCH, BENCH_TESTS, BACKUP_AND_TLS, MQTT_TLS, HTTPS_PAIRING, REMOTE_ACCESS, SIGNED_PACKAGES (quatre aussi en huit langues)
├── tools/                                                les vérifications CI et les outils partagés
├── images/                                               bannière, icône et images du README
├── .github/                                              workflow CI, avis au tableau de bord, modèles d'issues et de pull requests
├── armor.project.json                                    manifeste : version, rôle, maturité
├── CHANGELOG.md                                          ce qui a changé à chaque version
├── run.sh run.bat                                        démarrer, flux partagé
├── build.sh build.bat                                    construire et tester, flux partagé
├── build-test.sh build-test.bat                          construire, tester, empaqueter
├── test.sh test.bat                                      seulement les tests, jamais la version
└── SECURITY.md SUPPORT.md CONTRIBUTING.md CODE_OF_CONDUCT.md LICENSE
```

</details>

## 🗺️ Feuille de route et limites connues

**Limites connues aujourd'hui**

* Une installation propre sur une machine qui n'a jamais vu le projet n'est pas éprouvée.
* Toute la topologie Docker a été construite et exécutée avec Docker Engine sous WSL, mais pas sur sa cible, le Jetson.
* Il n'y a pas de nombre unique de tests, et les tests des deux assistants demandent Linux.
* Pas de revue de sécurité indépendante.

**Prochainement**

* Une installation propre sur une nouvelle machine, et la topologie Docker sur le Jetson.

## 🌍 Langues

Le README et les textes existent en anglais, espagnol, français, italien, allemand, chinois, japonais et portugais européen.

## 🔗 Projets liés

**A.R.M.O.R.** (Autonomous Radar & Multimodal Observation Range) est un système de sécurité périmétrique composé de dépôts indépendants. Chacun a sa propre version, ses propres tests et son propre README ; voici la famille :

* **[ARMOR-COMMON](https://github.com/JuanenRac/ARMOR-COMMON)** - Contrats de messages, validateurs, vecteurs de conformité et types générés
* **[ARMOR-NODE-RADAR](https://github.com/JuanenRac/ARMOR-NODE-RADAR)** - Firmware du nœud de terrain pour ESP32-S3 avec trois radars et son propre panneau web
* **[ARMOR-NODE-SOLAR](https://github.com/JuanenRac/ARMOR-NODE-SOLAR)** - Protocoles des onduleurs et batteries solaires et messages d'un nœud passerelle
* **[ARMOR-NODE-ELECTRICAL](https://github.com/JuanenRac/ARMOR-NODE-ELECTRICAL)** - Nœud électrique : compteurs, le message des mesures du réseau et les règles de commutation
* **[ARMOR-NODE-ALARM](https://github.com/JuanenRac/ARMOR-NODE-ALARM)** - Nœud et centrale d'alarme : zones, armement, temporisations, sirène et PIN, avec ou sans le serveur
* **[ARMOR-NODE-HMI](https://github.com/JuanenRac/ARMOR-NODE-HMI)** - Panneau tactile : l'état du système sur un écran mural, armer et acquitter, et la maison de l'assistant vocal
* **[ARMOR-NETWORK](https://github.com/JuanenRac/ARMOR-NETWORK)** - Le réseau local : ses appareils, internet et ce qui change
* **[ARMOR-SERVER](https://github.com/JuanenRac/ARMOR-SERVER)** - Coordinateur central : télémétrie, alarmes, appareils, relevés solaires et caméras
* **[ARMOR-STUDIO](https://github.com/JuanenRac/ARMOR-STUDIO)** - Console web : caméras, radar, alarmes, énergie solaire et concepteur de site 2D/3D
* **[ARMOR-ANDROID-CONTROL](https://github.com/JuanenRac/ARMOR-ANDROID-CONTROL)** - Client Android de l'opérateur avec radar 2D/3D en direct
* **[ARMOR-IOS-CONTROL](https://github.com/JuanenRac/ARMOR-IOS-CONTROL)** - Client opérateur iPhone
* **[ARMOR-SERVER-AI](https://github.com/JuanenRac/ARMOR-SERVER-AI)** - Politique d'inférence visuelle qui explique ses décisions et n'agit jamais
* **[ARMOR-VISION](https://github.com/JuanenRac/ARMOR-VISION)** - Zones de caméra, masques et règles de détection pour la Jetson Orin NX
* **[ARMOR-VOICE-AI](https://github.com/JuanenRac/ARMOR-VOICE-AI)** - Intentions vocales hors ligne avec une confirmation impossible à falsifier
* **[ARMOR-HARDWARE](https://github.com/JuanenRac/ARMOR-HARDWARE)** - Boîtiers, électronique et matrice d'acceptation sur banc
* **ARMOR-DEVOPS** (ce dépôt) - Déploiement, banc d'essai CM5, sauvegarde et TLS
* **[ARMOR-SIMULATOR](https://github.com/JuanenRac/ARMOR-SIMULATOR)** - Simulateur de télémétrie hors ligne avec des pannes reproductibles
* **[ARMOR-UPDATER](https://github.com/JuanenRac/ARMOR-UPDATER)** - Détecte, installe et met à jour les propres dépôts de l'écosystème
* **[ARMOR-DOCS](https://github.com/JuanenRac/ARMOR-DOCS)** - Architecture, base de sécurité et matrice des capacités

## 📚 Documentation

* [DEPLOYMENT_BOUNDARY](docs/DEPLOYMENT_BOUNDARY.md) : ce que ce dépôt déploie et ce qu'il ne déploie pas
* [CM5_TEST_BENCH](docs/CM5_TEST_BENCH.md) : l'installateur, les unités, les ports et les assistants du banc
* [BENCH_TESTS](docs/BENCH_TESTS.md) : comment le banc est testé
* [BACKUP_AND_TLS](docs/BACKUP_AND_TLS.md) : sauvegarde et restauration, et profil TLS de Compose
* [MQTT_TLS](docs/MQTT_TLS.md) : la porte chiffrée du broker (aussi en huit langues)
* [HTTPS_PAIRING](docs/HTTPS_PAIRING.md) : faire confiance au certificat d'un nœud (aussi en huit langues)
* [REMOTE_ACCESS](docs/REMOTE_ACCESS.md) : VPN, un nom pour la maison et le routeur, pas à pas (aussi en huit langues)
* [SIGNED_PACKAGES](docs/SIGNED_PACKAGES.md) : la signature des paquets (aussi en huit langues)
* [Matrice des capacités : ce qui est prouvé et ce qui ne l'est pas](https://github.com/JuanenRac/ARMOR-DOCS/blob/main/docs/CAPABILITY_MATRIX.md)
* [Catalogue des projets : versions et dépendances entre les dépôts](https://github.com/JuanenRac/ARMOR-DOCS/blob/main/docs/PROJECT_CATALOG.md)
* [Historique des modifications de ce dépôt](CHANGELOG.md)

## 🤝 Contribuer et communauté

* Avant une pull request, exécutez `python -I tools/armor_ci_validate.py` et les tests : les deux doivent réussir. Voir [CONTRIBUTING.md](CONTRIBUTING.md) et le [code de conduite](CODE_OF_CONDUCT.md).
* Le README existe en huit langues et est généré à partir des sources d'ARMOR-DOCS : une modification du texte se fait là-bas.
* Une modification d'un message entre composants commence dans ARMOR-COMMON.
* Ne décrivez pas comme fonctionnant sur une carte ce qui a seulement été compilé.
* Signalez une vulnérabilité en privé : [SECURITY.md](SECURITY.md). Questions, idées et rapports : electrohobby3d@gmail.com ([SUPPORT.md](SUPPORT.md)).

## 👤 AUTEUR

**JuanenRac (Electro Hobby 3D)** · electrohobby3d@gmail.com

## 📜 LICENCE

GPL-3.0-or-later - voir [LICENSE](LICENSE).
