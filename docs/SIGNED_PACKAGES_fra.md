# Paquets signés : comment la machine décide ce qu'elle installe

L'assistant de maintenance de la machine (`armor_maintenance_agent.py`) met à jour les programmes A.R.M.O.R. (`server`, `studio`, `network`, `ai`, `voice`, `devops`) à partir des releases de leurs dépôts sur GitHub. Avant de décompresser quoi que ce soit, il vérifie trois choses, dans cet ordre :

1. **Le hash :** le paquet doit donner le SHA-256 indiqué dans `armor-<composant>-<version>.tgz.sha256`. Cela détecte un téléchargement tronqué.
2. **La signature :** `armor-<composant>-<version>.tgz.sig` contient la signature Ed25519 (64 octets, soit 128 chiffres hexadécimaux) du texte

   `armor-pkg/1|<composant>|<version>|<sha256>`

   faite avec la clé privée des releases. L'assistant la vérifie avec la clé publique intégrée à son code (`PACKAGE_PUBLIC_KEY`), la même que celle à laquelle fait confiance le firmware des nœuds. Une release sans `.sig`, ou avec une signature qui ne se vérifie pas, est refusée (`missing_signature`, `bad_signature`) et le système reste inchangé : rien n'est décompressé, rien n'est redémarré.
3. **L'archive :** pas de noms absolus, pas de `..`, pas de liens ni de périphériques.

Celui qui peut seulement modifier le contenu d'une release sur GitHub (compte volé, dépendance malveillante des outils de publication) peut publier un paquet et son hash, mais pas sa signature : la clé privée n'est jamais sur GitHub. Le texte commence par `armor-pkg/1` et non par le `armor-fw/1` du firmware, donc une signature de firmware ne peut jamais passer pour une signature de paquet ; il contient aussi le composant et la version, donc un paquet signé ne peut pas se faire passer pour un autre programme ni pour une version plus récente.

La vérification est en Python pur (RFC 8032) : elle n'exige ni OpenSSL ni module supplémentaire sur la machine.

## Publier

```
python scripts/package_component.py server --repo ../ARMOR-SERVER --sign --publish
```

La commande écrit `.tgz`, `.sha256` et `.sig` et envoie les trois. Le signataire est `~/.armor/sign.mjs` (ou `--signer` / `ARMOR_PACKAGE_SIGNER`) ; il lit la clé dans `ARMOR_FIRMWARE_KEY` ou `~/.armor/firmware_ed25519.pem`. La clé n'est jamais copiée dans un dépôt. `--sign` échoue s'il n'y a ni signataire ni clé ; sans lui, le paquet est signé quand ils sont présents. Une clé différente de celle qu'accepte l'assistant n'est jamais utilisée. `--publish` refuse d'envoyer un paquet non signé.

Pour signer un paquet déjà publié, téléchargez-le avec son `.sha256` et lancez :

```
python scripts/package_component.py --sign-existing armor-server-0.5.7.tgz --upload
```

Le nom donne le composant et la version ; `--upload` ajoute la `.sig` à la release `v<version>` de son dépôt (nécessite `gh`).

## Dérogation d'urgence

S'il faut installer un paquet sans signature (clé perdue, par exemple), écrivez cette ligne dans le `armor.maint.env` de la machine (dans `$PREFIX/etc/`) puis retirez-la :

```
ARMOR_MAINT_ALLOW_UNSIGNED=1
```

Elle est relue dans ce fichier à chaque installation ; elle ne peut donc être activée ni par l'API HTTP ni par l'environnement du processus. L'assistant écrit un `WARNING` dans le journal de la tâche et dans le sien à chaque usage, et l'aperçu indique `unsigned_allowed`.

## Changer la clé

Créez une nouvelle paire et placez la nouvelle clé publique dans `PACKAGE_PUBLIC_KEY` et dans le firmware (`fw_trust.hpp`). Publiez un paquet `devops` signé avec l'**ancienne** clé (les machines l'installent et font ensuite confiance à la nouvelle), puis signez les suivants avec la nouvelle.

## Tests

`scripts/test_maintenance_agent.py` couvre une signature valide, un paquet altéré, un `.sig` absent, une signature d'une autre clé, du bruit, la dérogation (uniquement depuis le fichier), le vecteur de test de la RFC 8032 et le fait que la clé de l'assistant est celle de `fw_trust.hpp`. Ils utilisent des clés jetables, jamais la vraie.

Le packager refuse d'empaqueter une compilation périmée : pour `server` et `studio`, la version de `package.json` (et, pour Studio, celle de `dist/version.json`) doit être celle de `armor.project.json`, et `dist/` ne doit pas être plus ancien que les sources dont il est issu. Recompilez d'abord (`npm run build`).
