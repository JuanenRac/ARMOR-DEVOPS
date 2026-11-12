# Signierte Pakete: wie der Rechner entscheidet, was er installiert

Der Wartungshelfer des Rechners (`armor_maintenance_agent.py`) aktualisiert die A.R.M.O.R.-Programme (`server`, `studio`, `network`, `ai`, `voice`, `devops`) aus den Releases ihrer Repositories auf GitHub. Bevor er etwas entpackt, prüft er drei Dinge in dieser Reihenfolge:

1. **Der Hash:** Das Paket muss den SHA-256-Wert aus `armor-<Komponente>-<Version>.tgz.sha256` ergeben. So fällt ein abgebrochener Download auf.
2. **Die Signatur:** `armor-<Komponente>-<Version>.tgz.sig2` enthält die Ed25519-Signatur (64 Bytes als 128 Hexadezimalziffern) des Manifests

   `armor-fw/1|<Komponente>|package|<Version>|<sha256>`

   erstellt mit dem privaten Schlüssel der Releases, demselben, der die Firmware der Knoten signiert: Es ist dasselbe Manifest wie bei den Firmware-Images, mit `package` an der Stelle der Platine. Der Helfer prüft es mit dem öffentlichen Schlüssel, der Teil seines Codes ist (`PACKAGE_PUBLIC_KEY`), und, solange der Schlüssel gewechselt wird, mit einem zweiten (siehe unten). Ein Release ohne `.sig2` oder mit einer, die nicht stimmt, wird abgelehnt (`missing_signature`, `bad_signature`), und das System bleibt unverändert: Nichts wird entpackt, nichts neu gestartet.
3. **Das Archiv:** keine absoluten Namen, kein `..`, keine Links oder Geräte.

Wer nur ändern kann, was ein Release auf GitHub enthält (ein gestohlenes Konto, eine bösartige Abhängigkeit der Release-Werkzeuge), kann ein Paket und den passenden Hash veröffentlichen, aber nicht dessen Signatur: Der private Schlüssel liegt nie auf GitHub. Das Manifest bindet die Signatur an Komponente und Version; ein signiertes Paket aus der Vergangenheit oder einer anderen Komponente kann also nicht als das neueste ausgegeben werden, und die Signatur eines Firmware-Images (anderes Projekt, echte Platine) gilt nie als Paketsignatur. Die ältere `.sig` (Text `armor-pkg/1|<Komponente>|<Version>|<sha256>`) genügt nicht mehr: Sie wird nur akzeptiert, wenn die `armor.maint.env` der Maschine `ARMOR_MAINT_SIGNATURE=either` enthält, solange man braucht, um die früher veröffentlichten Pakete zu signieren.

Die Prüfung ist reines Python (RFC 8032): Auf dem Rechner werden weder OpenSSL noch zusätzliche Module benötigt.

## Veröffentlichen

```
python scripts/package_component.py server --repo ../ARMOR-SERVER --sign --publish
```

Es schreibt `.tgz`, `.sha256`, `.sig2` (das Manifest) und `.sig` (der ältere Text, den ein noch nicht aktualisierter Helfer weiter prüft) und lädt sie hoch. Der Signierer ist `~/.armor/sign.mjs` (oder `--signer` / `ARMOR_PACKAGE_SIGNER`); er liest den Schlüssel aus `ARMOR_FIRMWARE_KEY` oder `~/.armor/firmware_ed25519.pem`. Der Schlüssel wird nie in ein Repository kopiert. `--sign` schlägt fehl, wenn Signierer oder Schlüssel fehlen; ohne die Option wird signiert, wenn beides da ist. Ein anderer als der vom Helfer anerkannte Schlüssel wird nie benutzt. `--publish` weigert sich, ein unsigniertes Paket hochzuladen.

Um ein bereits veröffentlichtes Paket zu signieren, laden Sie es samt `.sha256` herunter und führen Sie aus:

```
python scripts/package_component.py --sign-existing armor-server-0.5.7.tgz --upload
```

Der Name gibt Komponente und Version an; `--upload` fügt `.sig2` und `.sig` dem Release `v<Version>` seines Repositorys hinzu (braucht `gh`).

## Veröffentlichung über GitHub Actions

Das Paket dieses Repositories baut der Workflow `package-build.yml` (von Hand gestartet, `dry_run` standardmäßig an): Er packt die Skripte des Pakets `devops` zweimal auf zwei Runnern, bricht ab, wenn die beiden Pakete nicht byteidentisch sind, und lädt `armor-devops-<Version>.tgz` mit `SHA256SUMS` und einer Attestierung hoch. Er enthält keinen Schlüssel. Zum Signieren und Veröffentlichen der Release auf dem Rechner des Maintainers, aus dem Artefakt eines grünen Laufs:

```
gh attestation verify armor-devops-<version>.tgz --repo JuanenRac/ARMOR-DEVOPS
python scripts/package_component.py --sign-existing armor-devops-<version>.tgz --upload
```

Die Release enthält dann `armor-devops-<Version>.tgz`, `.sha256`, `.sig` und `.sig2`, die der Wartungshelfer braucht; eine Release ohne sie lässt die Maschine melden, das Repository habe keine Release.

## Notfall-Ausnahme

Muss ein Paket ohne Signatur installiert werden (etwa bei verlorenem Schlüssel), tragen Sie diese Zeile in die `armor.maint.env` des Rechners ein (in `$PREFIX/etc/`) und entfernen Sie sie danach:

```
ARMOR_MAINT_ALLOW_UNSIGNED=1
```

Sie wird bei jeder Installation neu aus dieser Datei gelesen und lässt sich daher weder über die HTTP-API noch über die Prozessumgebung setzen. Bei jeder Nutzung schreibt der Helfer eine `WARNING` ins Protokoll des Auftrags und in sein eigenes, und die Übersicht meldet `unsigned_allowed`.

## Einstellungen der Maschine

Zwei Einstellungen zur Signatur, die bei jeder Installation aus `armor.maint.env` gelesen werden (nie aus der HTTP-API oder der Prozessumgebung):

```
ARMOR_MAINT_SIGNATURE=manifest
ARMOR_MAINT_NEXT_KEY=
```

`ARMOR_MAINT_SIGNATURE` ist `manifest` (Standard: nur die `.sig2` zählt) oder `either` (die ältere `.sig` zählt auch). `ARMOR_MAINT_NEXT_KEY` ist leer oder der zweite öffentliche Schlüssel, 64 Hexadezimalziffern, dem während eines Wechsels zusätzlich zum eingebauten vertraut wird; mehr als zwei Schlüsseln wird nie vertraut. Die Übersicht des Helfers zeigt `signature_mode` und `trusted_fingerprints` (die ersten 16 Ziffern des SHA-256 jedes Schlüssels, nie die Schlüssel), damit, wer die Maschine betreut, sehen kann, welchen Schlüsseln sie vertraut. Eine Änderung hier ändert, wie die Maschine entscheidet, was sie installiert: Sie wird auf der Maschine als root vorgenommen, wie die Notfall-Ausnahme.

## Den Schlüssel wechseln

Ein neues Paar erzeugen. Zuerst den neuen öffentlichen Schlüssel als `ARMOR_MAINT_NEXT_KEY` in die `armor.maint.env` jeder Maschine schreiben (oder ein `devops`-Paket veröffentlichen, signiert mit dem **alten** Schlüssel, dessen `PACKAGE_PUBLIC_KEY` der neue ist). Danach die Pakete mit dem neuen Schlüssel signieren: Die Maschinen vertrauen beiden, solange die Zeile da ist. Wenn jede Maschine den neuen Schlüssel eingebaut hat, die Zeile entfernen. Die Firmware der Knoten vertraut einem Schlüssel (`fw_trust.hpp`): Ändern Sie ihn, wie die Seite der signierten Firmware es beschreibt.

## Tests

`scripts/test_maintenance_agent.py` deckt ab: eine gültige Manifest-Signatur, dass sie Komponente, Version und Hash bindet, dass eine Firmware-Signatur, der ältere Text und der bloße Hash nicht als Manifest gelten, ein manipuliertes Paket, eine fehlende `.sig2`, eine Signatur eines anderen Schlüssels, Unsinn, die ältere `.sig` allein (abgelehnt, nur mit `either` akzeptiert), die zwei Schlüssel eines Wechsels (und dass einem dritten nie vertraut wird), die Ausnahme (nur aus der Datei), den Testvektor der RFC 8032 und dass der Schlüssel im Helfer der in `fw_trust.hpp` ist. Sie benutzen Wegwerf-Schlüssel, nie den echten.

Der Paketierer weigert sich, einen veralteten Build zu packen: Bei `server` und `studio` muss die Version in `package.json` (bei Studio auch in `dist/version.json`) die aus `armor.project.json` sein, und `dist/` darf nicht älter sein als der Quellcode, aus dem es gebaut wurde. Zuerst neu bauen (`npm run build`).
