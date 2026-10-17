# Utiliser A.R.M.O.R. depuis l'extérieur - pas à pas

La règle : **une seule porte** et **un nom, jamais une adresse**. Le broker MQTT et les nœuds ne sont jamais publiés sur Internet.

## 1. Choisir la porte

* **A. Un VPN (recommandé)** : WireGuard ou Tailscale sur la machine qui exécute le serveur. De l'extérieur, le téléphone rejoint le VPN et tout fonctionne comme à la maison (le panneau de chaque nœud aussi). Si votre fournisseur ne vous donne pas d'adresse publique à vous (CGNAT), Tailscale fonctionne sans rien ouvrir.
* **B. HTTPS** : un proxy inverse avec un vrai certificat (le profil `tls` de ce dépôt) sur un port du routeur. Pratique depuis n'importe quel navigateur ; mettez la politique « operate » pour que l'administration reste réservée à la maison ou au VPN.

## 2. Un nom qui suit votre adresse

Votre adresse publique est fixe ou change de temps en temps. Dans les deux cas, utilisez un **nom** (DuckDNS, No-IP, le DNS dynamique du routeur ou un domaine à vous) et quelque chose qui le met à jour quand l'adresse change (le client du routeur, ou `ddclient`/le script de DuckDNS sur la machine). Mettez un TTL court (60 à 300 s). Le téléphone, Studio et le VPN utilisent toujours le nom.

## 3. Dans le routeur

Redirigez **un** port vers la machine du serveur : `443/TCP` pour B (et `80/TCP` si le certificat est réel, pour sa vérification), ou `51820/UDP` pour WireGuard en A. Jamais `1883`, `8883` ni le port d'un nœud.

## 4. Sur le serveur (Docker)

Dans `.env` :

```
ARMOR_TLS_HOST=casa.duckdns.org          # votre nom
ARMOR_TLS_ISSUER=vous@example.com        # demande le certificat à Let's Encrypt et le renouvelle
ARMOR_TLS_PORT=443
ARMOR_TLS_HTTP_PORT=80
ARMOR_TLS_BIND=0.0.0.0
ARMOR_PUBLIC_ORIGIN=https://casa.duckdns.org
ARMOR_TRUST_PROXY=uniquelocal            # le serveur voit ainsi l'adresse réelle de chaque visiteur
ARMOR_TOTP_REQUIRED=remote               # second facteur depuis l'extérieur (à configurer d'abord depuis l'intérieur)
ARMOR_REMOTE_POLICY=operate              # depuis l'extérieur : regarder et manœuvrer l'alarme ; administrer seulement depuis la maison ou le VPN
```

puis `docker compose --profile tls up -d`. Sur le banc CM5, les mêmes réglages sont dans `armor.network.env` (Studio > Configuration > Sécurité les écrit pour vous).

## 5. Dans Studio

Configuration > Sécurité : activez le second facteur (application d'authentification) pour chaque compte, gardez les codes de récupération et regardez les sessions ouvertes. En administrateur, indiquez le proxy de confiance, les réseaux qui comptent comme la maison, la politique et la durée des sessions depuis l'extérieur.

## 6. Le VPN, le nom et les panneaux des nœuds, depuis Studio (sans commande)

Avec l'agent de maintenance installé (`install_cm5.sh --with-maintenance`) et WireGuard sur la machine (`sudo apt install wireguard-tools qrencode`), un administrateur fait tout dans Studio > Configuration > Sécurité > Accès depuis l'extérieur :

1. **VPN :** saisissez le nom ou l'adresse que le téléphone utilisera (par exemple `casa.duckdns.org`), gardez le port et le réseau de la maison et appuyez sur *Configurer le VPN*. Il indique quel port UDP rediriger sur le routeur vers la machine.
2. **Un téléphone ou un portable :** sous *Ajouter un appareil*, donnez-lui un nom (`tel-ana`), appuyez sur *Créer* et scannez le code QR avec l'application WireGuard. Le code contient une clé privée : fermez-le ensuite et ne le donnez à personne. Vous pourrez le réafficher ou retirer l'appareil plus tard.
3. **Un nom qui suit votre maison :** choisissez DuckDNS, Cloudflare ou une adresse à appeler, saisissez ses données et appuyez sur *Enregistrer et vérifier maintenant*. La machine vérifie toutes les cinq minutes et n'appelle le fournisseur que si l'adresse a changé.
4. **Le panneau d'un nœud depuis l'extérieur :** enregistrez le nœud (son identifiant et son adresse dans la maison). Pour un nœud en HTTPS, appuyez sur *Voir son certificat*, comparez l'empreinte avec celle du panneau du nœud (À propos) puis appuyez sur *Faire confiance à ce certificat*. *Ouvrir le panneau* fonctionne ensuite depuis l'extérieur, via le serveur, et le nœud n'est jamais publié.

On peut faire la même chose dans un terminal avec `armor_wireguard.sh` et `armor_ddns.sh` (l'en-tête de chacun liste ses commandes ; `plan` montre ce qui serait écrit avant d'écrire quoi que ce soit).


## 7. Sur le téléphone

A.R.M.O.R. Control : saisissez le nom comme serveur (`https://casa.duckdns.org`), connectez-vous (le code de l'application est demandé en seconde étape) et vérifiez Plus > Sécurité.

## 8. Vérifier

Depuis le téléphone **en données mobiles**, dans Studio ou l'application, appuyez sur « Vérifier comment le serveur me voit » : il doit dire **depuis l'extérieur** et montrer votre vraie adresse. S'il dit « depuis la maison », le proxy ne transmet pas l'adresse : corrigez `ARMOR_TRUST_PROXY` avant de vous fier à quoi que ce soit.

## Jamais

Rediriger le port du broker ou d'un nœud, même « un instant » ; utiliser l'adresse au lieu du nom ; laisser les mots de passe par défaut ; sauter le second facteur pour un administrateur qui se connecte de l'extérieur.
