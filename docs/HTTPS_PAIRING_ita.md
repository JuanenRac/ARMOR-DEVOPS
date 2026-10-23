# HTTPS per i telefoni: l'autorità propria della casa e l'abbinamento

L'app Android mantiene `http` non cifrato per la rete locale finché non c'è altro. Questa guida è la strada verso una casa raggiunta ovunque in `https`, con un'autorità propria che il telefono ricorda, in modo che l'app possa un giorno rifiutare `http`.

## Il profilo predefinito

Il profilo `tls` di questo repository mette Caddy davanti a Studio e al server. Il suo valore predefinito è quello sicuro: l'**autorità locale propria** di Caddy (`tls internal`), un certificato per `ARMOR_TLS_HOST`, HSTS di cinque minuti, solo `https`. Nulla di tutto ciò richiede internet. Per un nome su internet metti un indirizzo e-mail in `ARMOR_TLS_ISSUER` e Caddy chiede il certificato a Let's Encrypt (vedi `REMOTE_ACCESS_ita.md`): il telefono si fida allora del certificato da solo e non c'è nulla da abbinare.

## I passi

1. **Nome.** Scegli il nome con cui i telefoni raggiungono la casa (il nome DNS dinamico da fuori, o un nome della rete locale) e mettilo in `ARMOR_TLS_HOST` (`ARMOR_TLS_PORT=443` se il router inoltra la 443).
2. **Avvialo.** `docker compose --profile tls up -d` (o Caddy del pacchetto con lo stesso `Caddyfile`). Il server funziona con `ARMOR_TRUST_PROXY=1` e `ARMOR_PUBLIC_ORIGIN=https://<nome>`.
3. **Verificalo.** `scripts/armor_tls_check.sh <nome> 443 <root.crt>` dice se il server risponde, se la catena è valida per il nome, se restano più di 14 giorni e quale chiave fisserebbe un telefono, e stampa la riga `armor-pin:<nome>:<pin>`. Il certificato radice è `pki/authorities/local/root.crt` nei dati di Caddy (l'assistente di manutenzione lo trova; `ARMOR_TLS_CA_FILE` lo indica se è altrove).
4. **Abbina ogni telefono.** In Studio, Configurazione > Sicurezza > accesso da fuori > *Abbinare il telefono all'HTTPS della casa*: scrivi il nome, premi il pulsante, copia il testo. Nell'app, Altro > Sicurezza, incollalo. L'app accetterà allora solo quell'autorità per la casa; una chiave diversa viene rifiutata e segnalata.
5. **Prova tutto** su ogni telefono, con il Wi-Fi di casa e con i dati mobili: accesso, telecamere, inserimento, allarmi, push.
6. **Solo allora** il proprietario può vietare `http` non cifrato nell'app (`cleartext=false`) in una nuova versione. Finché tutti i telefoni non sono abbinati e provati, lascia com'è.

## Da sapere

* Il pin è lo SHA-256 della chiave **pubblica** dell'autorità: non è un segreto, ma chi lo dà a un telefono decide di chi si fida; per questo è mostrato solo agli amministratori e va confrontato con ciò che mostra l'app.
* Caddy rinnova da solo il certificato della casa. L'autorità dura circa dieci anni; se viene sostituita (una nuova cartella dati di Caddy) il pin cambia e si abbina di nuovo.
* La chiave dell'autorità non lascia mai la macchina e A.R.M.O.R. non la legge mai.
* Un telefono abbinato che incontra una chiave diversa rifiuta di connettersi: è lo scopo. Per abbinarlo di nuovo, dimentica il pin nell'app (Altro > Sicurezza) e incolla il nuovo testo.

## La prova sulla macchina (per il proprietario)

`scripts/armor_tls_check.sh` passa sulla CM5; il testo di abbinamento è lo stesso in Studio e nell'uscita dello script; un telefono abbinato sul Wi-Fi di casa si connette anche con i dati mobili; dopo `systemctl restart caddy` (o il container) non c'è nulla da abbinare di nuovo.
