# Pacchetti firmati: come la macchina decide cosa installa

L'assistente di manutenzione della macchina (`armor_maintenance_agent.py`) aggiorna i programmi A.R.M.O.R. (`server`, `studio`, `network`, `ai`, `voice`, `devops`) dalle release dei loro repository su GitHub. Prima di estrarre qualsiasi cosa controlla tre elementi, in quest'ordine:

1. **L'hash:** il pacchetto deve avere lo SHA-256 indicato in `armor-<componente>-<versione>.tgz.sha256`. Così si scopre un download interrotto.
2. **La firma:** `armor-<componente>-<versione>.tgz.sig2` contiene la firma Ed25519 (64 byte come 128 cifre esadecimali) del manifesto

   `armor-fw/1|<componente>|package|<versione>|<sha256>`

   fatta con la chiave privata delle release, la stessa che firma il firmware dei nodi: è lo stesso manifesto delle immagini di firmware, con `package` al posto della scheda. L'assistente la verifica con la chiave pubblica che fa parte del suo codice (`PACKAGE_PUBLIC_KEY`) e, mentre la chiave viene cambiata, con una seconda (vedi sotto). Una release senza `.sig2`, o con una che non si verifica, viene rifiutata (`missing_signature`, `bad_signature`) e il sistema resta com'è: non si decomprime nulla, non si riavvia nulla.
3. **L'archivio:** niente nomi assoluti, niente `..`, niente link o dispositivi.

Chi può solo cambiare il contenuto di una release su GitHub (un account rubato, una dipendenza malevola degli strumenti di pubblicazione) può pubblicare un pacchetto e il suo hash, ma non la firma: la chiave privata non è mai su GitHub. Il manifesto lega la firma al componente e alla versione, quindi un pacchetto firmato del passato o di un altro componente non può passare per il più recente, e la firma di un'immagine di firmware (altro progetto, scheda vera) non vale mai come firma di pacchetto. La vecchia `.sig` (testo `armor-pkg/1|<componente>|<versione>|<sha256>`) non basta più: è accettata solo se il `armor.maint.env` della macchina dice `ARMOR_MAINT_SIGNATURE=either`, per il tempo necessario a firmare i pacchetti pubblicati prima.

La verifica è Python puro (RFC 8032): non servono OpenSSL né moduli aggiuntivi sulla macchina.

## Pubblicare

```
python scripts/package_component.py server --repo ../ARMOR-SERVER --sign --publish
```

Scrive `.tgz`, `.sha256`, `.sig2` (il manifesto) e `.sig` (il vecchio testo, che un assistente non ancora aggiornato controlla ancora) e li carica. Il firmatario è `~/.armor/sign.mjs` (o `--signer` / `ARMOR_PACKAGE_SIGNER`); legge la chiave da `ARMOR_FIRMWARE_KEY` o da `~/.armor/firmware_ed25519.pem`. La chiave non viene mai copiata in un repository. `--sign` fallisce se mancano il firmatario o la chiave; senza, il pacchetto viene firmato quando ci sono. Una chiave diversa da quella accettata dall'assistente non viene mai usata. `--publish` rifiuta di caricare un pacchetto non firmato.

Per firmare un pacchetto già pubblicato, scaricalo insieme al suo `.sha256` ed esegui:

```
python scripts/package_component.py --sign-existing armor-server-0.5.7.tgz --upload
```

Il nome indica il componente e la versione; `--upload` aggiunge la `.sig2` e la `.sig` alla release `v<versione>` del suo repository (richiede `gh`).

## Pubblicazione da GitHub Actions

Il pacchetto di questo repository è costruito dal workflow `package-build.yml` (avviato a mano, `dry_run` attivo per impostazione predefinita): impacchetta due volte gli script del pacchetto `devops` su due runner, si ferma se i due pacchetti non sono identici byte per byte e carica `armor-devops-<versione>.tgz` con `SHA256SUMS` e un'attestazione. Non contiene alcuna chiave. Per firmare e pubblicare la release sulla macchina del manutentore, dall'artefatto di un'esecuzione verde:

```
gh attestation verify armor-devops-<version>.tgz --repo JuanenRac/ARMOR-DEVOPS
python scripts/package_component.py --sign-existing armor-devops-<version>.tgz --upload
```

La release contiene quindi `armor-devops-<versione>.tgz`, `.sha256`, `.sig` e `.sig2`, di cui l'assistente di manutenzione ha bisogno; una release senza di essi fa dire alla macchina che il repository non ha release.

## Eccezione d'emergenza

Se un pacchetto deve essere installato senza firma (ad esempio con la chiave persa), scrivi questa riga nel `armor.maint.env` della macchina (in `$PREFIX/etc/`) e toglila dopo:

```
ARMOR_MAINT_ALLOW_UNSIGNED=1
```

Viene riletta da quel file a ogni installazione, quindi non si può attivare né con l'API HTTP né con l'ambiente del processo. L'assistente scrive un `WARNING` nel registro del lavoro e nel proprio a ogni uso, e il riepilogo riporta `unsigned_allowed`.

## Impostazioni della macchina

Due impostazioni sulla firma, lette da `armor.maint.env` a ogni installazione (mai dall'API HTTP né dall'ambiente del processo):

```
ARMOR_MAINT_SIGNATURE=manifest
ARMOR_MAINT_NEXT_KEY=
```

`ARMOR_MAINT_SIGNATURE` vale `manifest` (predefinito: conta solo la `.sig2`) o `either` (conta anche la vecchia `.sig`). `ARMOR_MAINT_NEXT_KEY` è vuota o è la seconda chiave pubblica, 64 cifre esadecimali, di cui ci si fida oltre a quella incorporata durante una rotazione; non ci si fida mai di più di due chiavi. Il riepilogo dell'assistente mostra `signature_mode` e `trusted_fingerprints` (le prime 16 cifre dello SHA-256 di ogni chiave, mai le chiavi), così chi cura la macchina vede di quali chiavi si fida. Una modifica qui cambia il modo in cui la macchina decide cosa installa: si fa sulla macchina, come root, come l'eccezione di emergenza.

## Cambiare la chiave

Crea una coppia nuova. Prima scrivi la nuova chiave pubblica come `ARMOR_MAINT_NEXT_KEY` nel `armor.maint.env` di ogni macchina (oppure pubblica un pacchetto `devops`, firmato con la chiave **vecchia**, il cui `PACKAGE_PUBLIC_KEY` è la nuova). Da allora firma i pacchetti con la nuova: le macchine si fidano di entrambe finché quella riga c'è. Quando tutte hanno la nuova chiave incorporata, togli la riga. Il firmware dei nodi si fida di una sola chiave (`fw_trust.hpp`): cambiala come dice la pagina del firmware firmato.

## Test

`scripts/test_maintenance_agent.py` copre una firma di manifesto valida, che lega componente, versione e hash, che una firma di firmware, il vecchio testo e l'hash nudo non passano per manifesto, un pacchetto manomesso, una `.sig2` assente, una firma di un'altra chiave, spazzatura, la vecchia `.sig` da sola (rifiutata, accettata solo con `either`), le due chiavi di una rotazione (e che una terza non è mai di fiducia), l'eccezione (solo dal file), il vettore di test della RFC 8032 e che la chiave dell'assistente è quella di `fw_trust.hpp`. Usano chiavi usa e getta, mai quella vera.

Il pacchettizzatore rifiuta di impacchettare una build obsoleta: per `server` e `studio` la versione in `package.json` (e, per Studio, in `dist/version.json`) deve essere quella di `armor.project.json`, e `dist/` non deve essere più vecchio dei sorgenti da cui è stato compilato. Ricompila prima (`npm run build`).
