# Signierte Pakete: wie der Rechner entscheidet, was er installiert

Der Wartungshelfer des Rechners (`armor_maintenance_agent.py`) aktualisiert die A.R.M.O.R.-Programme (`server`, `studio`, `network`, `ai`, `voice`, `devops`) aus den Releases ihrer Repositories auf GitHub. Bevor er etwas entpackt, prüft er drei Dinge in dieser Reihenfolge:

1. **Der Hash:** Das Paket muss den SHA-256-Wert aus `armor-<Komponente>-<Version>.tgz.sha256` ergeben. So fällt ein abgebrochener Download auf.
2. **Die Signatur:** `armor-<Komponente>-<Version>.tgz.sig` enthält die Ed25519-Signatur (64 Bytes als 128 Hexadezimalziffern) des Textes

   `armor-pkg/1|<Komponente>|<Version>|<sha256>`

   erstellt mit dem privaten Schlüssel der Releases. Der Helfer prüft sie mit dem öffentlichen Schlüssel in seinem Code (`PACKAGE_PUBLIC_KEY`), dem gleichen, dem auch die Firmware der Knoten vertraut. Ein Release ohne `.sig` oder mit einer nicht verifizierbaren Signatur wird abgelehnt (`missing_signature`, `bad_signature`), und das System bleibt unverändert: nichts wird entpackt, nichts neu gestartet.
3. **Das Archiv:** keine absoluten Namen, kein `..`, keine Links oder Geräte.

Wer nur ändern kann, was ein Release auf GitHub enthält (ein gestohlenes Konto, eine bösartige Abhängigkeit der Release-Werkzeuge), kann ein Paket und den passenden Hash veröffentlichen, aber nicht dessen Signatur: Der private Schlüssel liegt nie auf GitHub. Der Text beginnt mit `armor-pkg/1`, nicht mit dem `armor-fw/1` der Firmware; eine Firmware-Signatur kann daher nie als Paketsignatur gelten. Er enthält außerdem Komponente und Version, sodass ein signiertes Paket nicht als anderes Programm oder neuere Version ausgegeben werden kann.

Die Prüfung ist reines Python (RFC 8032): Auf dem Rechner werden weder OpenSSL noch zusätzliche Module benötigt.

## Veröffentlichen

```
python scripts/package_component.py server --repo ../ARMOR-SERVER --sign --publish
```

Das schreibt `.tgz`, `.sha256` und `.sig` und lädt alle drei hoch. Der Signierer ist `~/.armor/sign.mjs` (oder `--signer` / `ARMOR_PACKAGE_SIGNER`); er liest den Schlüssel aus `ARMOR_FIRMWARE_KEY` oder `~/.armor/firmware_ed25519.pem`. Der Schlüssel wird nie in ein Repository kopiert. `--sign` schlägt fehl, wenn Signierer oder Schlüssel fehlen; ohne es wird signiert, sobald beide vorhanden sind. Ein anderer als der vom Helfer akzeptierte Schlüssel wird nie benutzt. `--publish` weigert sich, ein unsigniertes Paket hochzuladen.

Um ein bereits veröffentlichtes Paket zu signieren, laden Sie es samt `.sha256` herunter und führen Sie aus:

```
python scripts/package_component.py --sign-existing armor-server-0.5.7.tgz --upload
```

Der Name liefert Komponente und Version; `--upload` fügt die `.sig` dem Release `v<Version>` seines Repositorys hinzu (benötigt `gh`).

## Notfall-Ausnahme

Muss ein Paket ohne Signatur installiert werden (etwa bei verlorenem Schlüssel), tragen Sie diese Zeile in die `armor.maint.env` des Rechners ein (in `$PREFIX/etc/`) und entfernen Sie sie danach:

```
ARMOR_MAINT_ALLOW_UNSIGNED=1
```

Sie wird bei jeder Installation neu aus dieser Datei gelesen und lässt sich daher weder über die HTTP-API noch über die Prozessumgebung setzen. Bei jeder Nutzung schreibt der Helfer eine `WARNING` ins Protokoll des Auftrags und in sein eigenes, und die Übersicht meldet `unsigned_allowed`.

## Schlüssel wechseln

Erzeugen Sie ein neues Paar und tragen Sie den neuen öffentlichen Schlüssel in `PACKAGE_PUBLIC_KEY` und in die Firmware (`fw_trust.hpp`) ein. Veröffentlichen Sie ein `devops`-Paket, das mit dem **alten** Schlüssel signiert ist (die Rechner installieren es und vertrauen danach dem neuen), und signieren Sie die folgenden mit dem neuen.

## Tests

`scripts/test_maintenance_agent.py` deckt ab: gültige Signatur, manipuliertes Paket, fehlende `.sig`, Signatur eines anderen Schlüssels, Datenmüll, die Ausnahme (nur aus der Datei), den RFC-8032-Testvektor und dass der Schlüssel im Helfer der aus `fw_trust.hpp` ist. Sie verwenden Wegwerfschlüssel, nie den echten.

Der Paketierer weigert sich, einen veralteten Build zu packen: Bei `server` und `studio` muss die Version in `package.json` (bei Studio auch in `dist/version.json`) die aus `armor.project.json` sein, und `dist/` darf nicht älter sein als der Quellcode, aus dem es gebaut wurde. Zuerst neu bauen (`npm run build`).
