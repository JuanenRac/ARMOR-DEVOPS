# Chiffrer la liaison avec le broker (MQTT sur TLS) - facultatif, pas à pas

Langues : [English](MQTT_TLS.md) · [Español](MQTT_TLS_spa.md) · [Deutsch](MQTT_TLS_deu.md) · [Italiano](MQTT_TLS_ita.md) · [日本語](MQTT_TLS_jpn.md) · [中文](MQTT_TLS_zho.md) · [Português](MQTT_TLS_por.md)

**C'est désactivé.** Aujourd'hui, les nœuds parlent MQTT non chiffré au broker sur le réseau de la maison (port `18883`), et rien ne change si vous ne suivez pas ce guide. L'activer ajoute une **seconde porte** (`8883`, TLS) à côté de la normale ; la normale reste jusqu'à ce que vous décidiez de la retirer.

Le certificat ne vient pas d'Internet : l'installation crée **sa propre autorité de certification** sur la machine qui exécute le broker. Un nœud (ou le serveur) à qui l'on dit d'utiliser `mqtts://` ne fait confiance qu'à **cette autorité** et vérifie que le certificat du broker a été établi pour le nom ou l'adresse auxquels il s'est connecté. Tout le reste - une autre autorité, un certificat pour une autre adresse - est refusé.

## 1. Sur la machine qui exécute le broker

```bash
scripts/armor_mqtt_tls.sh plan --name casa.local --ip 192.168.0.180      # ce qu'il ferait ; ne change rien
sudo scripts/armor_mqtt_tls.sh setup --name casa.local --ip 192.168.0.180
sudo scripts/armor_mqtt_tls.sh status
```

* Le certificat garantit les noms et adresses de la machine (son nom d'hôte, `localhost`, `127.0.0.1`, ses adresses IPv4) plus chaque `--name` et `--ip` donné. **Un nœud se connecte à l'une d'elles** (`mqtts://192.168.0.180:8883`) : indiquez l'adresse que les nœuds utiliseront.
* La **clé privée de l'autorité** est créée sur la machine et reste dans `etc/mqtt-ca` (dossier `0700`, clé `0600`, root seulement). Elle n'est jamais dans un dépôt, jamais à côté du broker et ne quitte jamais la machine. Le broker ne reçoit que sa propre clé.
* `setup` redémarre le broker (un nouveau listener demande un redémarrage) : les nœuds se reconnectent en quelques secondes. Le port non chiffré n'est pas touché.
* Relancer `setup` ne change rien de ce qui est encore bon. Il crée un **nouveau certificat de broker avec la même autorité** quand les adresses changent ou qu'il reste moins de 30 jours (le certificat du broker dure deux ans). L'autorité étant la même, **il n'y a pas à toucher aux nœuds**. L'autorité dure dix ans.
* Si le pare-feu de l'hôte de ce dépôt est utilisé, il ne connaît que le port non chiffré : autorisez vous-même `8883/tcp` depuis le réseau de terrain.

## 2. Dans chaque nœud

Ouvrez le panneau du nœud, page **Broker** :

1. Écrivez l'adresse sous la forme `mqtts://192.168.0.180:8883` (elle doit être l'une de celles que le certificat garantit).
2. Cochez **Chiffrer la liaison avec le broker (TLS)**.
3. Collez le certificat de l'autorité dans la zone. Obtenez-le avec `sudo scripts/armor_mqtt_tls.sh export-ca` (il est public : un seul bloc de `-----BEGIN CERTIFICATE-----` à `-----END CERTIFICATE-----`, environ 600 octets ; 2 Ko au plus). Ce qui n'est pas un seul certificat au format PEM est refusé.
4. Enregistrez et redémarrez.

Le compte du nœud sur le broker (utilisateur et mot de passe) ne change pas. Avec le chiffrement activé, le nœud attend d'avoir l'heure avant de se connecter (jusqu'à deux minutes), car un certificat a des dates. Les brokers de secours enregistrés doivent aussi être en `mqtts://` tant que l'interrupteur est activé, et sont vérifiés avec la même autorité. **Désactivé** (par défaut), le nœud se comporte exactement comme avant.

## 3. Le serveur de cette machine

```bash
sudo scripts/armor_mqtt_tls.sh server-tls on      # ARMOR_MQTT_URL=mqtts://localhost:8883 et ARMOR_MQTT_CA_FILE dans le fichier d'environnement
sudo systemctl restart armor-server
```

À la main : `ARMOR_MQTT_URL=mqtts://localhost:8883` et `ARMOR_MQTT_CA_FILE=/chemin/vers/ca.pem`. Le serveur refuse de démarrer si le fichier n'est pas un certificat valide, ou si `ARMOR_MQTT_CA_FILE` est défini avec une adresse `mqtt://` (la liaison resterait non chiffrée alors que vous croiriez le contraire). Studio affiche l'état dans **Configuration > Broker** : si la liaison est chiffrée et l'empreinte de l'autorité, à comparer avec `sudo scripts/armor_mqtt_tls.sh status`. `server-tls off` revient au port non chiffré.

## 4. Le désactiver

Décochez l'interrupteur dans chaque nœud (et remettez l'adresse `mqtt://`), lancez `server-tls off` puis `sudo scripts/armor_mqtt_tls.sh remove`. Rien n'est supprimé : les fichiers du broker et la configuration sont mis de côté à côté des anciens, et l'autorité est conservée (`--forget-ca` la met aussi de côté) afin qu'un `setup` ultérieur garde les nœuds qui lui font déjà confiance.

## Ce que cela fait et ne fait pas

* Cela chiffre et authentifie le broker auprès des nœuds et du serveur. Cela ne demande **pas** aux nœuds un certificat propre : ils s'identifient toujours avec leur compte.
* Cela protège le réseau de la maison contre qui écoute ou se fait passer pour le broker. Ce n'est pas une raison de publier le broker : `8883` n'est jamais redirigé vers Internet (voir `REMOTE_ACCESS.md`).
* Vérifié avec OpenSSL et Mosquitto 2.0 sur un ordinateur (le certificat, le second listener, la poignée de main, l'épinglage d'une seule autorité, le refus d'une autre autorité et d'une autre adresse, et la connexion du serveur). **Pas encore vérifié sur la carte d'un nœud** : la poignée de main coûte un peu de temps et de mémoire sur un microcontrôleur.
