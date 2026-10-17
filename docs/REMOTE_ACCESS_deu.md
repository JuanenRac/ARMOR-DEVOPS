# A.R.M.O.R. von außerhalb des Hauses nutzen - Schritt für Schritt

Die Regel: **nur eine Tür** und **ein Name, nie eine Adresse**. Der MQTT-Broker und die Knoten werden nie im Internet veröffentlicht.

## 1. Die Tür wählen

* **A. Ein VPN (empfohlen)**: WireGuard oder Tailscale auf dem Rechner mit dem Server. Von außen tritt das Handy dem VPN bei und alles funktioniert wie zu Hause (auch das Panel jedes Knotens). Hat Ihr Anbieter keine eigene öffentliche Adresse (CGNAT), funktioniert Tailscale ohne etwas zu öffnen.
* **B. HTTPS**: ein Reverse-Proxy mit echtem Zertifikat (das `tls`-Profil dieses Repositorys) an einem Port des Routers. Bequem aus jedem Browser; setzen Sie die Richtlinie „operate“, damit das Verwalten dem Haus oder dem VPN vorbehalten bleibt.

## 2. Ein Name, der Ihrer Adresse folgt

Ihre öffentliche Adresse ist fest oder ändert sich gelegentlich. In beiden Fällen nutzen Sie einen **Namen** (DuckDNS, No-IP, das dynamische DNS des Routers oder eine eigene Domain) und etwas, das ihn bei Änderung aktualisiert (der Router-Client oder `ddclient`/das DuckDNS-Skript auf dem Rechner). Setzen Sie eine kurze TTL (60 bis 300 s). Handy, Studio und VPN verwenden immer den Namen.

## 3. Im Router

Leiten Sie **einen** Port zum Server-Rechner weiter: `443/TCP` für B (und `80/TCP`, wenn das Zertifikat echt ist, für dessen Prüfung) oder `51820/UDP` für WireGuard bei A. Nie `1883`, `8883` oder den Port eines Knotens.

## 4. Auf dem Server (Docker)

In `.env`:

```
ARMOR_TLS_HOST=casa.duckdns.org          # Ihr Name
ARMOR_TLS_ISSUER=sie@example.com         # holt das Zertifikat bei Let's Encrypt und erneuert es
ARMOR_TLS_PORT=443
ARMOR_TLS_HTTP_PORT=80
ARMOR_TLS_BIND=0.0.0.0
ARMOR_PUBLIC_ORIGIN=https://casa.duckdns.org
ARMOR_TRUST_PROXY=uniquelocal            # so sieht der Server die echte Adresse jedes Besuchers
ARMOR_TOTP_REQUIRED=remote               # zweiter Faktor von außen (vorher von innen einrichten)
ARMOR_REMOTE_POLICY=operate              # von außen: ansehen und Alarm bedienen; Verwalten nur aus dem Haus oder per VPN
```

dann `docker compose --profile tls up -d`. Am CM5-Prüfstand stehen dieselben Einstellungen in `armor.network.env` (Studio > Konfiguration > Sicherheit schreibt sie für Sie).

## 5. In Studio

Konfiguration > Sicherheit: Schalten Sie den zweiten Faktor (Authenticator-App) für jedes Konto ein, speichern Sie die Wiederherstellungscodes und sehen Sie die offenen Sitzungen an. Als Administrator legen Sie den vertrauenswürdigen Proxy, die als Haus geltenden Netze, die Richtlinie und die Dauer der Sitzungen von außen fest.

## 6. Auf dem Handy

A.R.M.O.R. Control: Geben Sie den Namen als Server ein (`https://casa.duckdns.org`), melden Sie sich an (der Code der App wird als zweiter Schritt verlangt) und prüfen Sie Mehr > Sicherheit.

## 7. Prüfen

Drücken Sie vom Handy **mit Mobilfunk** in Studio oder der App „Prüfen, wie der Server mich sieht“: Es muss **von außerhalb** sagen und Ihre echte Adresse zeigen. Sagt es „aus dem Haus“, gibt der Proxy die Adresse nicht weiter: Korrigieren Sie `ARMOR_TRUST_PROXY`, bevor Sie irgendetwas vertrauen.

## Niemals

Den Port des Brokers oder eines Knotens weiterleiten, auch nicht „nur kurz“; die Adresse statt des Namens verwenden; Standardpasswörter lassen; den zweiten Faktor bei einem Administrator überspringen, der sich von außen anmeldet.
