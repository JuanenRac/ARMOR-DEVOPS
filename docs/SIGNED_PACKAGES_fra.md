# Paquets signés : comment la machine décide ce qu'elle installe

L'assistant de maintenance de la machine (`armor_maintenance_agent.py`) met à jour les programmes A.R.M.O.R. (`server`, `studio`, `network`, `ai`, `voice`, `devops`) à partir des releases de leurs dépôts sur GitHub. Avant de décompresser quoi que ce soit, il vérifie trois choses, dans cet ordre :

1. **Le hash :** le paquet doit donner le SHA-256 indiqué dans `armor-<composant>-<version>.tgz.sha256`. Cela détecte un téléchargement tronqué.
2. **La signature :** `armor-<composant>-<version>.tgz.sig2` contient la signature Ed25519 (64 octets en 128 chiffres hexadécimaux) du manifeste

   `armor-fw/1|<composant>|package|<version>|<sha256>`

   faite avec la clé privée des releases, celle qui signe le firmware des nœuds : c'est le même manifeste que celui des images de firmware, avec `package` à la place de la carte. L'assistant la vérifie avec la clé publique qui fait partie de son code (`PACKAGE_PUBLIC_KEY`) et, pendant un changement de clé, avec une seconde (voir plus bas). Une release sans `.sig2`, ou avec une qui ne se vérifie pas, est refusée (`missing_signature`, `bad_signature`) et le système reste inchangé : rien n'est décompressé, rien n'est redémarré.
3. **L'archive :** pas de noms absolus, pas de `..`, pas de liens ni de périphériques.

Celui qui peut seulement modifier le contenu d'une release sur GitHub (compte volé, dépendance malveillante des outils de publication) peut publier un paquet et son hash, mais pas sa signature : la clé privée n'est jamais sur GitHub. Le manifeste lie la signature au composant et à la version : un paquet signé du passé ou d'un autre composant ne peut donc pas passer pour le plus récent, et la signature d'une image de firmware (autre projet, vraie carte) ne passe jamais pour une signature de paquet. L'ancienne `.sig` (texte `armor-pkg/1|<composant>|<version>|<sha256>`) ne suffit plus : elle n'est acceptée que si le `armor.maint.env` de la machine dit `ARMOR_MAINT_SIGNATURE=either`, le temps de signer les paquets publiés avant.

La vérification est en Python pur (RFC 8032) : elle n'exige ni OpenSSL ni module supplémentaire sur la machine.

## Publier

```
python scripts/package_component.py server --repo ../ARMOR-SERVER --sign --publish
```

Il écrit `.tgz`, `.sha256`, `.sig2` (le manifeste) et `.sig` (l'ancien texte, qu'un assistant pas encore mis à jour vérifie encore) et les envoie. Le signeur est `~/.armor/sign.mjs` (ou `--signer` / `ARMOR_PACKAGE_SIGNER`) ; il lit la clé dans `ARMOR_FIRMWARE_KEY` ou `~/.armor/firmware_ed25519.pem`. La clé n'est jamais copiée dans un dépôt. `--sign` échoue s'il n'y a pas de signeur ou de clé ; sans lui, le paquet est signé quand ils sont là. Une clé autre que celle que l'assistant accepte n'est jamais utilisée. `--publish` refuse d'envoyer un paquet non signé.

Pour signer un paquet déjà publié, téléchargez-le avec son `.sha256` et lancez :

```
python scripts/package_component.py --sign-existing armor-server-0.5.7.tgz --upload
```

Le nom donne le composant et la version ; `--upload` ajoute la `.sig2` et la `.sig` à la release `v<version>` de son dépôt (nécessite `gh`).

## Dérogation d'urgence

S'il faut installer un paquet sans signature (clé perdue, par exemple), écrivez cette ligne dans le `armor.maint.env` de la machine (dans `$PREFIX/etc/`) puis retirez-la :

```
ARMOR_MAINT_ALLOW_UNSIGNED=1
```

Elle est relue dans ce fichier à chaque installation ; elle ne peut donc être activée ni par l'API HTTP ni par l'environnement du processus. L'assistant écrit un `WARNING` dans le journal de la tâche et dans le sien à chaque usage, et l'aperçu indique `unsigned_allowed`.

## Réglages de la machine

Deux réglages sur la signature, lus dans `armor.maint.env` à chaque installation (jamais depuis l'API HTTP ni l'environnement du processus) :

```
ARMOR_MAINT_SIGNATURE=manifest
ARMOR_MAINT_NEXT_KEY=
```

`ARMOR_MAINT_SIGNATURE` vaut `manifest` (par défaut : seule la `.sig2` compte) ou `either` (l'ancienne `.sig` compte aussi). `ARMOR_MAINT_NEXT_KEY` est vide ou la seconde clé publique, 64 chiffres hexadécimaux, à laquelle on fait confiance en plus de celle intégrée pendant une rotation ; on ne fait jamais confiance à plus de deux clés. L'aperçu de l'assistant montre `signature_mode` et `trusted_fingerprints` (les 16 premiers chiffres du SHA-256 de chaque clé, jamais les clés), pour que celui qui s'occupe de la machine voie à quelles clés elle se fie. Un changement ici change la façon dont la machine décide ce qu'elle installe : il se fait sur la machine, en root, comme l'exception d'urgence.

## Changer la clé

Créez une nouvelle paire. D'abord, écrivez la nouvelle clé publique comme `ARMOR_MAINT_NEXT_KEY` dans le `armor.maint.env` de chaque machine (ou publiez un paquet `devops`, signé avec l'**ancienne** clé, dont `PACKAGE_PUBLIC_KEY` est la nouvelle). Ensuite, signez les paquets avec la nouvelle clé : les machines se fient aux deux tant que cette ligne est là. Quand toutes ont la nouvelle clé intégrée, retirez la ligne. Le firmware des nœuds se fie à une seule clé (`fw_trust.hpp`) : changez-la comme le dit la page du firmware signé.

## Tests

`scripts/test_maintenance_agent.py` couvre une signature de manifeste valide, qu'elle lie le composant, la version et le hash, qu'une signature de firmware, l'ancien texte et le hash seul ne passent pas pour un manifeste, un paquet falsifié, une `.sig2` absente, une signature d'une autre clé, du bruit, l'ancienne `.sig` seule (refusée, acceptée seulement avec `either`), les deux clés d'une rotation (et qu'une troisième n'est jamais de confiance), l'exception (seulement depuis le fichier), le vecteur de test de la RFC 8032 et que la clé de l'assistant est celle de `fw_trust.hpp`. Elles utilisent des clés jetables, jamais la vraie.

Le packager refuse d'empaqueter une compilation périmée : pour `server` et `studio`, la version de `package.json` (et, pour Studio, celle de `dist/version.json`) doit être celle de `armor.project.json`, et `dist/` ne doit pas être plus ancien que les sources dont il est issu. Recompilez d'abord (`npm run build`).
