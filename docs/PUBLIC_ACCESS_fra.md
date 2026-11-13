# Ouvrir le port 18080 sur Internet - ce qu'il faut vérifier d'abord

Le serveur peut accepter des requêtes d'Internet si vous redirigez le port 18080 sur le routeur. Ce projet n'ouvre rien : le routeur est à vous. Le serveur ne fait que se durcir. Le broker (MQTT) et les nœuds ne sont jamais publiés.

## Avant de rediriger le port

* Le jeton de contrôle a au moins 32 caractères aléatoires et le mot de passe de Studio au moins 12 (sinon `public_access_unsafe` liste `control_token_short` / `password_short`).
* TLS est actif : le certificat propre du serveur (`TLS_CERT_PATH`, `TLS_KEY_PATH`) ou un proxy inverse nommé dans `ARMOR_TRUST_PROXY` qui parle https ; le cookie est Secure (`tls_missing`, `cookie_not_secure`).
* La connexion en deux étapes est active pour tous les administrateurs et `ARMOR_TOTP_REQUIRED` vaut `remote` ou `always`.
* `ARMOR_REMOTE_POLICY` vaut `operate` ou `view`, sauf si vous devez vraiment administrer de l'extérieur.
* `GET /api/v1/remote/check` depuis un téléphone en données mobiles montre l'adresse, `remote` et le protocole `https`.

## L'activer

Dans Studio, Configuration > Sécurité, activez `network.public_access` (désactivé par défaut ; il demande une nouvelle preuve d'identité). Tant qu'il est désactivé, toute requête venue de l'extérieur de la maison reçoit `403 public_access_off`. Les connexions échouées sont comptées par adresse : `ARMOR_PUBLIC_LOGIN_ATTEMPTS` (5) en `ARMOR_PUBLIC_LOGIN_WINDOW_S` secondes (900) ferment l'adresse avec `429 public_login_locked`.

## Ensuite

Consultez le journal d'audit (refus `public_access` et `studio.login` refusés), gardez le routeur à jour et désactivez l'option quand vous n'en avez plus besoin. Ce mode n'a été essayé qu'avec un serveur simulé, jamais avec votre routeur ni Internet.
