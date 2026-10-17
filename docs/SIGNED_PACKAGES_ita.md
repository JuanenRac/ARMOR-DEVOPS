# Pacchetti firmati: come la macchina decide cosa installa

L'assistente di manutenzione della macchina (`armor_maintenance_agent.py`) aggiorna i programmi A.R.M.O.R. (`server`, `studio`, `network`, `ai`, `voice`, `devops`) dalle release dei loro repository su GitHub. Prima di estrarre qualsiasi cosa controlla tre elementi, in quest'ordine:

1. **L'hash:** il pacchetto deve avere lo SHA-256 indicato in `armor-<componente>-<versione>.tgz.sha256`. Così si scopre un download interrotto.
2. **La firma:** `armor-<componente>-<versione>.tgz.sig` contiene la firma Ed25519 (64 byte come 128 cifre esadecimali) del testo

   `armor-pkg/1|<componente>|<versione>|<sha256>`

   fatta con la chiave privata delle release. L'assistente la verifica con la chiave pubblica incorporata nel suo codice (`PACKAGE_PUBLIC_KEY`), la stessa di cui si fida il firmware dei nodi. Una release senza `.sig`, o con una firma che non si verifica, viene rifiutata (`missing_signature`, `bad_signature`) e il sistema resta invariato: nulla viene estratto o riavviato.
3. **L'archivio:** niente nomi assoluti, niente `..`, niente link o dispositivi.

Chi può solo cambiare il contenuto di una release su GitHub (un account rubato, una dipendenza malevola degli strumenti di pubblicazione) può pubblicare un pacchetto e il suo hash, ma non la firma: la chiave privata non è mai su GitHub. Il testo inizia con `armor-pkg/1`, non con l'`armor-fw/1` del firmware, quindi una firma del firmware non può mai passare per firma di pacchetto; contiene inoltre componente e versione, perciò un pacchetto firmato non può spacciarsi per un altro programma o per una versione più recente.

La verifica è Python puro (RFC 8032): non servono OpenSSL né moduli aggiuntivi sulla macchina.

## Pubblicare

```
python scripts/package_component.py server --repo ../ARMOR-SERVER --sign --publish
```

Scrive `.tgz`, `.sha256` e `.sig` e carica tutti e tre. Il firmatario è `~/.armor/sign.mjs` (o `--signer` / `ARMOR_PACKAGE_SIGNER`); legge la chiave da `ARMOR_FIRMWARE_KEY` o da `~/.armor/firmware_ed25519.pem`. La chiave non viene mai copiata in un repository. `--sign` fallisce se mancano firmatario o chiave; senza, il pacchetto viene firmato quando ci sono. Una chiave diversa da quella accettata dall'assistente non viene mai usata. `--publish` rifiuta di caricare un pacchetto non firmato.

Per firmare un pacchetto già pubblicato, scaricalo insieme al suo `.sha256` ed esegui:

```
python scripts/package_component.py --sign-existing armor-server-0.5.7.tgz --upload
```

Il nome dà componente e versione; `--upload` aggiunge la `.sig` alla release `v<versione>` del suo repository (richiede `gh`).

## Eccezione d'emergenza

Se un pacchetto deve essere installato senza firma (ad esempio con la chiave persa), scrivi questa riga nel `armor.maint.env` della macchina (in `$PREFIX/etc/`) e toglila dopo:

```
ARMOR_MAINT_ALLOW_UNSIGNED=1
```

Viene riletta da quel file a ogni installazione, quindi non si può attivare né con l'API HTTP né con l'ambiente del processo. L'assistente scrive un `WARNING` nel registro del lavoro e nel proprio a ogni uso, e il riepilogo riporta `unsigned_allowed`.

## Cambiare la chiave

Crea una nuova coppia e metti la nuova chiave pubblica in `PACKAGE_PUBLIC_KEY` e nel firmware (`fw_trust.hpp`). Pubblica un pacchetto `devops` firmato con la chiave **vecchia** (le macchine lo installano e da allora si fidano della nuova), poi firma i successivi con la nuova.

## Test

`scripts/test_maintenance_agent.py` copre una firma valida, un pacchetto manomesso, un `.sig` mancante, una firma di un'altra chiave, dati spazzatura, l'eccezione (solo dal file), il vettore di prova della RFC 8032 e che la chiave dell'assistente sia quella di `fw_trust.hpp`. Usano chiavi usa e getta, mai quella vera.
