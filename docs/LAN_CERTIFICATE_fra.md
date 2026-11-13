# Un certificat pour l'adresse de la machine sur le réseau local

Voici le chemin vers un `https://192.168.0.180` auquel un téléphone ou un navigateur fait confiance, avec une autorité propre à l'installation et sans aucun nom dans le DNS public. C'est **facultatif et désactivé** : le profil `tls` (un nom, l'autorité propre de Caddy, voir HTTPS_PAIRING.md) et le profil `lan-ca` continuent de fonctionner tels quels. Le port 18080 du serveur s'atteint depuis le réseau local ou par le VPN, et rien dans ce guide ne l'ouvre sur Internet. Si vous décidez de le rediriger sur le routeur, suivez d'abord PUBLIC_ACCESS.md : le mode public durci (`network.public_access`, désactivé par défaut) est ce qui autorise les requêtes de l'extérieur.

## Ce qui est créé

`scripts/armor_lan_cert.py` crée, une seule fois, une **autorité locale** et, pour l'adresse donnée, un **second certificat** signé par cette autorité :

* `~/.armor/lan-ca/ca.crt` : le certificat de l'autorité (public : c'est ce qu'on installe sur les téléphones et les ordinateurs).
* `~/.armor/lan-ca/ca.key` : la clé privée de l'autorité. Elle reste dans ce dossier (mode 0700, la clé 0600), n'est jamais affichée, jamais copiée par le programme et ne fait jamais partie d'un dépôt ni d'un paquet.
* `leaf.crt`, `leaf.key`, `fullchain.pem` : le certificat de l'adresse (une adresse IPv4 privée, plus les noms `.lan` / `.local` que vous ajoutez, plus 127.0.0.1) et sa clé.

L'autorité est limitée par une contrainte de noms dans son propre certificat : elle ne peut se porter garante que d'adresses privées et de noms `.lan` / `.local`, si bien qu'une copie volée de sa clé ne peut pas usurper un site d'Internet auprès d'un appareil qui lui fait confiance. Le programme refuse une adresse publique.

## Les étapes

1. **Regarder d'abord.** `python3 scripts/armor_lan_cert.py plan --ip 192.168.0.180 --name armor.lan` dit ce qui serait créé et ne change rien.
2. **L'activer et le créer.** `python3 scripts/armor_lan_cert.py setup --ip 192.168.0.180 --name armor.lan --enable`. Sans `--enable` (ou `"enabled": true` dans `~/.armor/lan-ca/lan-ca.json`) il refuse : par défaut, c'est désactivé. Relancé, il garde l'autorité et le certificat tant que l'adresse est la même et qu'il reste plus de `renew_days` jours ; si l'adresse change, il crée un nouveau certificat avec la même autorité, donc les appareils ne sont pas touchés.
3. **Donner le certificat au proxy.** Utilisez la variante `caddy/Caddyfile.lan-issued`, qui sert `/lan-certs/leaf.crt` et `/lan-certs/leaf.key` : `ARMOR_LAN_CADDYFILE=./caddy/Caddyfile.lan-issued ARMOR_LAN_CERT_DIR=$HOME/.armor/lan-ca docker compose --profile lan-ca up -d`. Le dossier est monté en lecture seule ; sans ces deux variables, le proxy continue d'utiliser l'autorité propre de Caddy.
4. **Installer l'autorité une fois sur chaque appareil.** `python3 scripts/armor_lan_cert.py export-ca --out armor-lan-ca.crt` écrit le certificat public. Android : Paramètres > Sécurité > Chiffrement et identifiants > Installer un certificat > Certificat d'autorité. iPhone : ouvrez le fichier, installez le profil, puis Réglages > Général > Informations > Réglages de confiance du certificat et activez-le. Windows : double-clic et installation dans « Autorités de certification racines de confiance ». Linux : copiez-le dans `/usr/local/share/ca-certificates/` et lancez `update-ca-certificates`.
5. **Vérifier.** `python3 scripts/armor_lan_cert.py fingerprint` affiche le SHA-256 de l'autorité (ce que fixe le panneau mural) ; avec `--spki`, l'empreinte de sa clé publique (ce que fixe l'application du téléphone). Comparez-la avec ce que montre l'appareil avant de faire confiance.

## Le fichier de réglages

`~/.armor/lan-ca/lan-ca.json` (tout est facultatif ; une valeur hors limites ou inconnue est une erreur, jamais une supposition) : `enabled` (false), `ca_days` (3650), `leaf_days` (397 ; navigateurs et téléphones refusent plus de 398 jours pour certains certificats), `renew_days` (30), `curve` (`prime256v1` ou `secp384r1`) et `name_constraints` (true). `ARMOR_LAN_CA_DIR` déplace le dossier.

## À savoir

* Quiconque détient `ca.key` peut émettre des certificats, pour des adresses privées, que les appareils faisant confiance à l'autorité acceptent : gardez le dossier pour vous, sauvegardez-le comme tout autre secret et ne le mettez jamais dans un dépôt.
* `remove` met le dossier de côté (`lan-ca.removed-<heure>`) ; rien n'est supprimé. Les appareils qui ont installé l'ancienne autorité doivent la retirer.
* Rien de cela n'a tourné sur le CM5 : les tests créent une autorité et un certificat dans un dossier jetable avec openssl et vérifient que la chaîne est valide pour l'adresse et pas pour une autre.

## Depuis Studio

Avec l'agent d'administration installé, un administrateur peut créer, renouveler et remplacer l'autorité depuis Studio (Configuration > Sécurité), toujours avec le code à usage unique de l'authentificateur de maintenance : `POST /v1/lan-ca` de l'agent avec `action` valant `setup` (autorité et certificat pour l'adresse ; active l'option), `renew` (un nouveau certificat sous la même autorité) ou `rotate` (l'autorité est mise de côté et une nouvelle est créée : chaque appareil doit l'installer de nouveau). `GET /v1/lan-ca` indique les jours restants de l'autorité et du certificat et liste dans `expiring` ceux qui sont à `renew_days` de leur fin, que Studio affiche comme un avertissement. L'agent ne lit, n'envoie et n'imprime jamais la clé de l'autorité ; les durées et `renew_days` restent dans `lan-ca.json`.
