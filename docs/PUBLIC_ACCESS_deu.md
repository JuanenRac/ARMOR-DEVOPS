# Port 18080 ins Internet öffnen - was vorher zu prüfen ist

Der Server kann Anfragen aus dem Internet annehmen, wenn Sie den Port 18080 im Router weiterleiten. Dieses Projekt öffnet nichts: Der Router gehört Ihnen. Der Server härtet sich nur selbst. Der Broker (MQTT) und die Knoten werden nie veröffentlicht.

## Vor dem Weiterleiten des Ports

* Das Control-Token hat mindestens 32 zufällige Zeichen und das Studio-Passwort mindestens 12 (sonst nennt `public_access_unsafe` `control_token_short` / `password_short`).
* TLS ist aktiv: das eigene Zertifikat des Servers (`TLS_CERT_PATH`, `TLS_KEY_PATH`) oder ein Reverse-Proxy, der in `ARMOR_TRUST_PROXY` benannt ist und https spricht; das Cookie ist Secure (`tls_missing`, `cookie_not_secure`).
* Die Anmeldung in zwei Schritten ist für alle Administratoren aktiv und `ARMOR_TOTP_REQUIRED` ist `remote` oder `always`.
* `ARMOR_REMOTE_POLICY` ist `operate` oder `view`, außer Sie müssen wirklich von außen administrieren.
* `GET /api/v1/remote/check` von einem Telefon im Mobilfunknetz zeigt die Adresse, `remote` und das Protokoll `https`.

## Einschalten

In Studio unter Konfiguration > Sicherheit `network.public_access` einschalten (standardmäßig aus; verlangt einen neuen Identitätsnachweis). Solange sie aus ist, beantwortet jede Anfrage von außerhalb des Hauses `403 public_access_off`. Fehlgeschlagene Anmeldungen werden pro Adresse gezählt: `ARMOR_PUBLIC_LOGIN_ATTEMPTS` (5) innerhalb von `ARMOR_PUBLIC_LOGIN_WINDOW_S` Sekunden (900) sperren die Adresse mit `429 public_login_locked`.

## Danach

Prüfen Sie das Audit-Protokoll (`public_access`-Ablehnungen und abgelehnte `studio.login`), halten Sie die Router-Firmware aktuell und schalten Sie die Option wieder aus, wenn Sie sie nicht mehr brauchen. Dieser Modus wurde nur mit einem simulierten Server getestet, nie mit Ihrem Router oder dem Internet.
