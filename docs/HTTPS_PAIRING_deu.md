# HTTPS für die Telefone: die eigene Zertifizierungsstelle des Hauses und das Koppeln

Die Android-App behält unverschlüsseltes `http` für das lokale Netz, solange es nichts anderes gibt. Diese Anleitung ist der Weg zu einem Haus, das überall über `https` erreicht wird, mit einer eigenen Zertifizierungsstelle, die sich das Telefon merkt, damit die App eines Tages `http` ablehnen kann.

## Das Standardprofil

Das Profil `tls` dieses Repositorys setzt Caddy vor Studio und den Server. Sein Standard ist der sichere: die **eigene lokale Zertifizierungsstelle** von Caddy (`tls internal`), ein Zertifikat für `ARMOR_TLS_HOST`, HSTS von fünf Minuten, nur `https`. Nichts davon braucht das Internet. Für einen Namen im Internet tragen Sie eine E-Mail-Adresse in `ARMOR_TLS_ISSUER` ein, und Caddy holt das Zertifikat bei Let's Encrypt (siehe `REMOTE_ACCESS_deu.md`): Dann vertraut das Telefon dem Zertifikat von selbst und es gibt nichts zu koppeln.

## Die Schritte

1. **Name.** Wählen Sie den Namen, unter dem die Telefone das Haus erreichen (der DynDNS-Name von außen oder ein Name des lokalen Netzes), und tragen Sie ihn in `ARMOR_TLS_HOST` ein (`ARMOR_TLS_PORT=443`, wenn der Router 443 weiterleitet).
2. **Starten.** `docker compose --profile tls up -d` (oder Caddy aus dem Paket mit demselben `Caddyfile`). Der Server läuft mit `ARMOR_TRUST_PROXY=1` und `ARMOR_PUBLIC_ORIGIN=https://<Name>`.
3. **Prüfen.** `scripts/armor_tls_check.sh <Name> 443 <root.crt>` sagt, ob der Server antwortet, ob die Kette für den Namen gültig ist, ob mehr als 14 Tage bleiben und welchen Schlüssel ein Telefon festhalten würde, und gibt die Zeile `armor-pin:<Name>:<pin>` aus. Das Wurzelzertifikat ist `pki/authorities/local/root.crt` in den Daten von Caddy (der Wartungsassistent findet es; `ARMOR_TLS_CA_FILE` nennt es, wenn es woanders liegt).
4. **Jedes Telefon koppeln.** In Studio, Konfiguration > Sicherheit > Zugang von außen > *Telefon mit dem HTTPS des Hauses koppeln*: Namen eingeben, Schaltfläche drücken, Text kopieren. In der App unter Mehr > Sicherheit einfügen. Die App akzeptiert dann für das Haus nur diese Zertifizierungsstelle; ein anderer Schlüssel wird abgelehnt und gemeldet.
5. **Alles ausprobieren** auf jedem Telefon, im WLAN des Hauses und mit mobilen Daten: Anmeldung, Kameras, Scharfschalten, Alarme, Push.
6. **Erst dann** darf der Besitzer in einem neuen Build unverschlüsseltes `http` in der App verbieten (`cleartext=false`). Solange nicht alle Telefone gekoppelt und erprobt sind, lassen Sie es, wie es ist.

## Gut zu wissen

* Der Pin ist der SHA-256 des **öffentlichen** Schlüssels der Zertifizierungsstelle: kein Geheimnis, aber wer ihn einem Telefon gibt, bestimmt, wem es vertraut; deshalb wird er nur Administratoren gezeigt und sollte mit dem verglichen werden, was die App zeigt.
* Caddy erneuert das Zertifikat des Hauses selbst. Die Zertifizierungsstelle hält etwa zehn Jahre; wird sie ersetzt (ein neuer Datenordner von Caddy), ändert sich der Pin und die Telefone werden erneut gekoppelt.
* Der Schlüssel der Zertifizierungsstelle verlässt den Rechner nie und wird von A.R.M.O.R. nie gelesen.
* Ein gekoppeltes Telefon, das auf einen anderen Schlüssel trifft, verweigert die Verbindung: Das ist der Zweck. Zum erneuten Koppeln den Pin in der App vergessen (Mehr > Sicherheit) und den neuen Text einfügen.

## Der Test auf dem Rechner (für den Besitzer)

`scripts/armor_tls_check.sh` besteht auf der CM5; der Kopplungstext ist in Studio und in der Ausgabe des Skripts derselbe; ein im Haus-WLAN gekoppeltes Telefon verbindet sich auch mit mobilen Daten; nach `systemctl restart caddy` (oder dem Container) muss nichts neu gekoppelt werden.
