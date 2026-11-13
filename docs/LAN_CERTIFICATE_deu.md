# Ein Zertifikat für die Adresse des Rechners im lokalen Netzwerk

Dies ist der Weg zu einem `https://192.168.0.180`, dem ein Telefon oder ein Browser vertraut, mit einer eigenen Zertifizierungsstelle der Installation und ohne Namen im öffentlichen DNS. Er ist **optional und ausgeschaltet**: Das Profil `tls` (ein Name, die eigene Stelle von Caddy, siehe HTTPS_PAIRING.md) und das Profil `lan-ca` funktionieren weiter wie bisher. Port 18080 des Servers ist aus dem lokalen Netzwerk oder über das VPN erreichbar, und nichts in dieser Anleitung öffnet ihn ins Internet. Wenn Sie ihn im Router weiterleiten wollen, folgen Sie zuerst PUBLIC_ACCESS.md: Der gehärtete öffentliche Modus (`network.public_access`, standardmäßig aus) erlaubt erst Anfragen von außen.

## Was erzeugt wird

`scripts/armor_lan_cert.py` erzeugt einmalig eine **lokale Zertifizierungsstelle** und für die angegebene Adresse ein **zweites Zertifikat**, das von dieser Stelle signiert ist:

* `~/.armor/lan-ca/ca.crt`: das Zertifikat der Stelle (öffentlich: Es wird auf Telefonen und Computern installiert).
* `~/.armor/lan-ca/ca.key`: der private Schlüssel der Stelle. Er bleibt in diesem Ordner (Modus 0700, der Schlüssel 0600), wird nie ausgegeben, nie vom Programm kopiert und ist nie Teil eines Repositorys oder Pakets.
* `leaf.crt`, `leaf.key`, `fullchain.pem`: das Zertifikat für die Adresse (eine private IPv4-Adresse, dazu die `.lan`- / `.local`-Namen, die Sie hinzufügen, und 127.0.0.1) und sein Schlüssel.

Die Stelle ist durch eine Namensbeschränkung in ihrem eigenen Zertifikat begrenzt: Sie kann nur für private Adressen und `.lan`- / `.local`-Namen bürgen, sodass eine gestohlene Kopie ihres Schlüssels sich gegenüber einem Gerät, das ihr vertraut, nicht als Seite im Internet ausgeben kann. Das Programm lehnt eine öffentliche Adresse ab.

## Die Schritte

1. **Erst ansehen.** `python3 scripts/armor_lan_cert.py plan --ip 192.168.0.180 --name armor.lan` sagt, was erzeugt würde, und ändert nichts.
2. **Einschalten und erzeugen.** `python3 scripts/armor_lan_cert.py setup --ip 192.168.0.180 --name armor.lan --enable`. Ohne `--enable` (oder `"enabled": true` in `~/.armor/lan-ca/lan-ca.json`) verweigert es: Die Voreinstellung ist aus. Ein erneuter Lauf behält Stelle und Zertifikat, solange die Adresse gleich ist und mehr als `renew_days` Tage übrig sind; ändert sich die Adresse, entsteht ein neues Zertifikat mit derselben Stelle, sodass die Geräte unberührt bleiben.
3. **Dem Proxy das Zertifikat geben.** Verwenden Sie die Variante `caddy/Caddyfile.lan-issued`, die `/lan-certs/leaf.crt` und `/lan-certs/leaf.key` ausliefert: `ARMOR_LAN_CADDYFILE=./caddy/Caddyfile.lan-issued ARMOR_LAN_CERT_DIR=$HOME/.armor/lan-ca docker compose --profile lan-ca up -d`. Der Ordner wird schreibgeschützt eingebunden; ohne diese beiden Variablen nutzt der Proxy weiter die eigene Stelle von Caddy.
4. **Die Stelle einmal auf jedem Gerät installieren.** `python3 scripts/armor_lan_cert.py export-ca --out armor-lan-ca.crt` schreibt das öffentliche Zertifikat. Android: Einstellungen > Sicherheit > Verschlüsselung und Anmeldedaten > Zertifikat installieren > CA-Zertifikat. iPhone: Datei öffnen, Profil installieren, dann Einstellungen > Allgemein > Info > Zertifikatsvertrauenseinstellungen und einschalten. Windows: Doppelklick und in „Vertrauenswürdige Stammzertifizierungsstellen“ installieren. Linux: nach `/usr/local/share/ca-certificates/` kopieren und `update-ca-certificates` ausführen.
5. **Prüfen.** `python3 scripts/armor_lan_cert.py fingerprint` gibt den SHA-256 der Stelle aus (was das Wandpanel festlegt); mit `--spki` den Pin ihres öffentlichen Schlüssels (was die Telefon-App festlegt). Vergleichen Sie ihn mit der Anzeige des Geräts, bevor Sie vertrauen.

## Die Einstellungsdatei

`~/.armor/lan-ca/lan-ca.json` (alles optional; ein Wert außerhalb des Bereichs oder ein unbekannter ist ein Fehler, nie eine Vermutung): `enabled` (false), `ca_days` (3650), `leaf_days` (397; Browser und Telefone lehnen bei manchen Zertifikaten mehr als 398 Tage ab), `renew_days` (30), `curve` (`prime256v1` oder `secp384r1`) und `name_constraints` (true). `ARMOR_LAN_CA_DIR` verschiebt den Ordner.

## Was man wissen sollte

* Wer `ca.key` besitzt, kann Zertifikate für private Adressen ausstellen, die die Geräte akzeptieren, die der Stelle vertrauen: Behalten Sie den Ordner für sich, sichern Sie ihn wie jedes andere Geheimnis und legen Sie ihn nie in ein Repository.
* `remove` legt den Ordner beiseite (`lan-ca.removed-<Zeit>`); nichts wird gelöscht. Geräte, die die alte Stelle installiert haben, sollten sie entfernen.
* Nichts davon lief auf dem CM5: Die Tests erzeugen mit openssl in einem Wegwerfordner eine Stelle und ein Zertifikat und prüfen, dass die Kette für die Adresse gilt und nicht für eine andere.

## Aus Studio

Ist der Admin-Agent installiert, kann ein Administrator die Zertifizierungsstelle in Studio (Konfiguration > Sicherheit) anlegen, erneuern und ersetzen, immer mit dem Einmalcode des Wartungs-Authenticators: `POST /v1/lan-ca` des Agenten mit `action` `setup` (Stelle und Zertifikat für die Adresse; schaltet die Option ein), `renew` (ein neues Zertifikat unter derselben Stelle) oder `rotate` (die Stelle wird beiseitegelegt und eine neue erstellt: Jedes Gerät muss sie neu installieren). `GET /v1/lan-ca` nennt die verbleibenden Tage von Stelle und Zertifikat und listet in `expiring` die auf, die höchstens `renew_days` vor dem Ende stehen; Studio zeigt sie als Warnung. Der Agent liest, sendet oder druckt den Schlüssel der Stelle nie; Laufzeiten und `renew_days` bleiben in `lan-ca.json`.
