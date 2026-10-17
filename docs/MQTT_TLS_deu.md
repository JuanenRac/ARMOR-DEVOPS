# Die Verbindung zum Broker verschlüsseln (MQTT über TLS) - optional, Schritt für Schritt

Sprachen: [English](MQTT_TLS.md) · [Español](MQTT_TLS_spa.md) · [Français](MQTT_TLS_fra.md) · [Italiano](MQTT_TLS_ita.md) · [日本語](MQTT_TLS_jpn.md) · [中文](MQTT_TLS_zho.md) · [Português](MQTT_TLS_por.md)

**Es ist ausgeschaltet.** Heute sprechen die Knoten unverschlüsseltes MQTT mit dem Broker im Hausnetz (Port `18883`), und ohne diese Anleitung ändert sich nichts. Das Einschalten fügt neben der normalen eine **zweite Tür** hinzu (`8883`, TLS); die normale bleibt, bis Sie sich entscheiden, sie zu entfernen.

Das Zertifikat kommt nicht aus dem Internet: Die Anlage erstellt auf dem Rechner, auf dem der Broker läuft, **ihre eigene Zertifizierungsstelle**. Ein Knoten (oder der Server), der `mqtts://` verwenden soll, vertraut **nur dieser Stelle** und prüft, ob das Zertifikat des Brokers für den Namen oder die Adresse ausgestellt wurde, mit der er sich verbunden hat. Alles andere - eine andere Stelle, ein Zertifikat für eine andere Adresse - wird abgelehnt.

## 1. Auf dem Rechner, auf dem der Broker läuft

```bash
scripts/armor_mqtt_tls.sh plan --name casa.local --ip 192.168.0.180      # was es tun würde; ändert nichts
sudo scripts/armor_mqtt_tls.sh setup --name casa.local --ip 192.168.0.180
sudo scripts/armor_mqtt_tls.sh status
```

* Das Zertifikat gilt für die Namen und Adressen des Rechners (Rechnername, `localhost`, `127.0.0.1`, seine IPv4-Adressen) plus jedes angegebene `--name` und `--ip`. **Ein Knoten verbindet sich mit einer davon** (`mqtts://192.168.0.180:8883`): Geben Sie die Adresse an, die die Knoten verwenden werden.
* Der **private Schlüssel der Zertifizierungsstelle** wird auf dem Rechner erzeugt und bleibt in `etc/mqtt-ca` (Ordner `0700`, Schlüssel `0600`, nur root). Er liegt nie in einem Repository, nie neben dem Broker und verlässt den Rechner nie. Der Broker erhält nur seinen eigenen Schlüssel.
* `setup` startet den Broker neu (ein neuer Listener braucht einen Neustart): Die Knoten verbinden sich in wenigen Sekunden neu. Der unverschlüsselte Port bleibt unberührt.
* Wiederholtes `setup` ändert nichts, was noch gut ist. Es erstellt ein **neues Broker-Zertifikat mit derselben Zertifizierungsstelle**, wenn sich die Adressen ändern oder weniger als 30 Tage übrig sind (das Broker-Zertifikat gilt zwei Jahre). Weil die Stelle dieselbe ist, **müssen die Knoten nicht angefasst werden**. Die Zertifizierungsstelle gilt zehn Jahre.
* Wenn die Host-Firewall dieses Repositorys verwendet wird: Sie kennt nur den unverschlüsselten Port, erlauben Sie `8883/tcp` aus dem Feldnetz selbst.

## 2. In jedem Knoten

Öffnen Sie das Panel des Knotens, Seite **Broker**:

1. Schreiben Sie die Adresse als `mqtts://192.168.0.180:8883` (sie muss eine der Adressen sein, für die das Zertifikat gilt).
2. Aktivieren Sie **Verbindung zum Broker verschlüsseln (TLS)**.
3. Fügen Sie das Zertifikat der Zertifizierungsstelle in das Feld ein. Sie erhalten es mit `sudo scripts/armor_mqtt_tls.sh export-ca` (es ist öffentlich: ein einzelner Block von `-----BEGIN CERTIFICATE-----` bis `-----END CERTIFICATE-----`, etwa 600 Bytes; höchstens 2 KB). Alles, was nicht genau ein Zertifikat im PEM-Format ist, wird abgelehnt.
4. Speichern und neu starten.

Das Konto des Knotens am Broker (Benutzer und Passwort) ändert sich nicht. Bei eingeschalteter Verschlüsselung wartet der Knoten auf seine Uhrzeit, bevor er sich verbindet (bis zu zwei Minuten), weil ein Zertifikat Datumsangaben hat. Die gespeicherten Ersatz-Broker müssen bei eingeschaltetem Schalter ebenfalls `mqtts://` sein und werden gegen dieselbe Zertifizierungsstelle geprüft. **Ausgeschaltet** (Standard) verhält sich der Knoten genau wie zuvor.

## 3. Der Server dieses Rechners

```bash
sudo scripts/armor_mqtt_tls.sh server-tls on      # ARMOR_MQTT_URL=mqtts://localhost:8883 und ARMOR_MQTT_CA_FILE in der Umgebungsdatei
sudo systemctl restart armor-server
```

Von Hand: `ARMOR_MQTT_URL=mqtts://localhost:8883` und `ARMOR_MQTT_CA_FILE=/pfad/zu/ca.pem`. Der Server startet nicht, wenn die Datei kein gültiges Zertifikat ist oder wenn `ARMOR_MQTT_CA_FILE` mit einer `mqtt://`-Adresse gesetzt ist (die Verbindung bliebe unverschlüsselt, während Sie das Gegenteil glauben). Studio zeigt den Zustand unter **Konfiguration > Broker**: ob die Verbindung verschlüsselt ist, und den Fingerabdruck der Zertifizierungsstelle zum Vergleich mit `sudo scripts/armor_mqtt_tls.sh status`. `server-tls off` kehrt zum unverschlüsselten Port zurück.

## 4. Ausschalten

Schalter in jedem Knoten ausschalten (und die `mqtt://`-Adresse zurücksetzen), `server-tls off` ausführen und dann `sudo scripts/armor_mqtt_tls.sh remove`. Es wird nichts gelöscht: Die Dateien des Brokers und die Konfiguration werden neben den alten beiseitegelegt, und die Zertifizierungsstelle bleibt erhalten (`--forget-ca` legt sie ebenfalls beiseite), damit ein späteres `setup` die Knoten, die ihr schon vertrauen, weiter funktionieren lässt.

## Was das leistet und was nicht

* Es verschlüsselt und authentifiziert den Broker gegenüber den Knoten und dem Server. Es verlangt von den Knoten **kein** eigenes Zertifikat: Sie identifizieren sich weiterhin mit ihrem Konto.
* Es schützt das Hausnetz davor, dass jemand mithört oder sich als Broker ausgibt. Es ist kein Grund, den Broker zu veröffentlichen: `8883` wird nie ins Internet weitergeleitet (siehe `REMOTE_ACCESS.md`).
* Geprüft mit OpenSSL und Mosquitto 2.0 auf einem Computer (das Zertifikat, der zweite Listener, der Handshake, das Festlegen auf genau eine Zertifizierungsstelle, die Ablehnung einer anderen Stelle und einer anderen Adresse sowie die Verbindung des Servers). **Auf der Platine eines Knotens noch nicht geprüft**: Der Handshake kostet auf einem Mikrocontroller etwas Zeit und Speicher.
