# HTTPS pour les téléphones : l'autorité propre de la maison et l'appairage

L'application Android garde `http` en clair pour le réseau local tant qu'il n'y a rien d'autre. Ce guide est le chemin vers une maison jointe partout en `https`, avec une autorité propre dont le téléphone se souvient, pour que l'application puisse un jour refuser `http`.

## Le profil par défaut

Le profil `tls` de ce dépôt place Caddy devant Studio et le serveur. Son défaut est le plus sûr : l'**autorité locale propre** de Caddy (`tls internal`), un certificat pour `ARMOR_TLS_HOST`, HSTS de cinq minutes, `https` seulement. Rien de tout cela n'a besoin d'internet. Pour un nom sur internet, mettez une adresse e-mail dans `ARMOR_TLS_ISSUER` et Caddy demande le certificat à Let's Encrypt (voir `REMOTE_ACCESS_fra.md`) : le téléphone fait alors confiance au certificat de lui-même et il n'y a rien à appairer.

## Les étapes

1. **Nom.** Choisissez le nom par lequel les téléphones joignent la maison (le nom DNS dynamique depuis l'extérieur, ou un nom du réseau local) et mettez-le dans `ARMOR_TLS_HOST` (`ARMOR_TLS_PORT=443` si le routeur redirige le 443).
2. **Démarrez-le.** `docker compose --profile tls up -d` (ou Caddy du paquet avec le même `Caddyfile`). Le serveur tourne avec `ARMOR_TRUST_PROXY=1` et `ARMOR_PUBLIC_ORIGIN=https://<nom>`.
3. **Vérifiez.** `scripts/armor_tls_check.sh <nom> 443 <root.crt>` dit si le serveur répond, si la chaîne est valide pour le nom, s'il reste plus de 14 jours et quelle clé un téléphone épinglerait, et affiche la ligne `armor-pin:<nom>:<pin>`. Le certificat racine est `pki/authorities/local/root.crt` dans les données de Caddy (l'assistant de maintenance le trouve ; `ARMOR_TLS_CA_FILE` le nomme s'il est ailleurs).
4. **Appairez chaque téléphone.** Dans Studio, Configuration > Sécurité > accès depuis l'extérieur > *Appairer le téléphone avec le HTTPS de la maison* : saisissez le nom, appuyez sur le bouton, copiez le texte. Dans l'application, Plus > Sécurité, collez-le. L'application n'acceptera alors que cette autorité pour la maison ; une clé différente est refusée et signalée.
5. **Essayez tout** sur chaque téléphone, sur le Wi-Fi de la maison et en données mobiles : connexion, caméras, armement, alarmes, push.
6. **Alors seulement** le propriétaire peut interdire `http` en clair dans l'application (`cleartext=false`) dans une nouvelle version. Tant que tous les téléphones ne sont pas appairés et essayés, laissez comme c'est.

## À savoir

* Le pin est le SHA-256 de la clé **publique** de l'autorité : ce n'est pas un secret, mais qui le donne à un téléphone décide en qui il a confiance ; il n'est donc montré qu'aux administrateurs et doit être comparé à ce que montre l'application.
* Caddy renouvelle seul le certificat de la maison. L'autorité dure environ dix ans ; si elle est remplacée (un nouveau dossier de données de Caddy), le pin change et il faut réappairer.
* La clé de l'autorité ne quitte jamais la machine et A.R.M.O.R. ne la lit jamais.
* Un téléphone appairé qui rencontre une clé différente refuse de se connecter : c'est le but. Pour le réappairer, oubliez le pin dans l'application (Plus > Sécurité) et collez le nouveau texte.

## L'essai sur la machine (pour le propriétaire)

`scripts/armor_tls_check.sh` réussit sur la CM5 ; le texte d'appairage est le même dans Studio et dans la sortie du script ; un téléphone appairé sur le Wi-Fi de la maison se connecte aussi en données mobiles ; après `systemctl restart caddy` (ou le conteneur) il n'y a rien à réappairer.
