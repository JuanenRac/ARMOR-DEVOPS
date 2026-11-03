# Mises à jour de sécurité automatiques de la machine

L'assistant de maintenance (`armor_maintenance_agent.py`, installé avec `--with-maintenance`) garde le système de la machine à jour avec `unattended-upgrades`, limité à la **source de sécurité** de la distribution : pas de mises à jour ordinaires, pas de versions intermédiaires, pas de nettoyage de noyaux. Il est **activé par défaut** et chaque partie est un réglage de Studio (Configuration > Mises à jour > Mises à jour de sécurité automatiques).

## Ce qu'il fait

* Écrit `/etc/apt/apt.conf.d/52armor-security-updates` à partir des réglages et ne laisse jamais le paquet redémarrer la machine : `Automatic-Reboot` vaut toujours `false`. C'est l'assistant qui décide du redémarrage.
* Tient un registre de ce qui a été appliqué (lu dans le journal de `unattended-upgrades` ; Studio montre les dernières exécutions).
* Après chaque exécution, vérifie que chaque service A.R.M.O.R. installé est actif ; un service arrêté est redémarré une fois et Studio montre ce qui était en panne. Rien n'est fait en silence : le journal de l'assistant contient un avertissement.

## Le redémarrage

Certaines mises à jour demandent un redémarrage. Le réglage « Quand une mise à jour demande un redémarrage » a deux valeurs : **Jamais seule** (Studio signale qu'un redémarrage attend et vous redémarrez quand cela convient) et **Seule, uniquement dans la fenêtre et quand rien n'est armé** (par défaut, fenêtre 03:00-05:00 heure locale). Dans le second cas, l'assistant ne redémarre que si tout ceci est vrai : la fenêtre a commencé, aucune autre opération n'est en cours et le serveur répond que ni le système ni aucune centrale d'alarme n'est armé. Si le serveur ne répond pas, c'est comme armé et la machine attend. Studio montre pourquoi elle n'a pas encore redémarré.

## Risques

Un redémarrage que vous n'avez pas demandé coupe serveur, broker et Studio pendant une ou deux minutes : un système d'alarme armé ne signale rien pendant ce temps (les centrales protègent la maison seules, mais personne n'est prévenu). C'est pourquoi la valeur par défaut ne redémarre jamais tant que quelque chose est armé, et pourquoi « Jamais seule » existe. Une mise à jour de sécurité peut aussi, rarement, casser un service : la vérification après chaque exécution le redémarre et le montre, mais une personne doit regarder.

## Comment la désactiver

Dans Studio : désactivez « Installer automatiquement les mises à jour de sécurité ». Sur la machine, si Studio est injoignable : mettez `"enabled": false` dans `$PREFIX/data/maintenance/auto_security_updates.json` (sous `"settings"`) et redémarrez `armor-maintenance` ; l'assistant écrit alors `APT::Periodic::Unattended-Upgrade "0"`. Retirer seulement le fichier apt ne suffit pas : l'assistant le réécrit au démarrage.

## Tests

`scripts/test_maintenance_agent.py` couvre la configuration de sécurité seule, la validation des réglages, la fenêtre qui passe minuit, le registre de ce qui a été appliqué, la vérification des services et chaque raison de ne pas redémarrer (armé, inconnu, hors fenêtre, politique, occupé). Rien n'y touche une vraie machine.
