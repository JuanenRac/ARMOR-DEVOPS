# Un certificato per l'indirizzo della macchina nella rete locale

Questa è la strada verso un `https://192.168.0.180` di cui un telefono o un browser si fidano, con un'autorità propria dell'installazione e nessun nome nel DNS pubblico. È **facoltativa e spenta**: il profilo `tls` (un nome, l'autorità propria di Caddy, vedi HTTPS_PAIRING.md) e il profilo `lan-ca` continuano a funzionare come sono. La porta 18080 del server **non viene mai aperta su Internet**: vi si arriva dalla rete locale o tramite la VPN, e nulla in questa guida lo cambia.

## Che cosa crea

`scripts/armor_lan_cert.py` crea, una sola volta, un'**autorità locale** e, per l'indirizzo indicato, un **secondo certificato** firmato da quell'autorità:

* `~/.armor/lan-ca/ca.crt`: il certificato dell'autorità (pubblico: è ciò che si installa su telefoni e computer).
* `~/.armor/lan-ca/ca.key`: la chiave privata dell'autorità. Resta in quella cartella (modo 0700, la chiave 0600), non viene mai stampata, il programma non la copia mai e non fa mai parte di un repository o di un pacchetto.
* `leaf.crt`, `leaf.key`, `fullchain.pem`: il certificato per l'indirizzo (un indirizzo IPv4 privato, più i nomi `.lan` / `.local` che aggiungi, più 127.0.0.1) e la sua chiave.

L'autorità è limitata da un vincolo sui nomi dentro il proprio certificato: può garantire solo indirizzi privati e nomi `.lan` / `.local`, quindi una copia rubata della sua chiave non può spacciarsi per un sito di Internet presso un dispositivo che si fida di essa. Il programma rifiuta un indirizzo pubblico.

## I passaggi

1. **Prima guarda.** `python3 scripts/armor_lan_cert.py plan --ip 192.168.0.180 --name armor.lan` dice che cosa verrebbe creato e non cambia nulla.
2. **Accendilo e crealo.** `python3 scripts/armor_lan_cert.py setup --ip 192.168.0.180 --name armor.lan --enable`. Senza `--enable` (o `"enabled": true` in `~/.armor/lan-ca/lan-ca.json`) rifiuta: il valore predefinito è spento. Rieseguito, mantiene l'autorità e il certificato finché l'indirizzo è lo stesso e restano più di `renew_days` giorni; se l'indirizzo cambia, crea un nuovo certificato con la stessa autorità, quindi i dispositivi non vengono toccati.
3. **Dai il certificato al proxy.** Usa la variante `caddy/Caddyfile.lan-issued`, che serve `/lan-certs/leaf.crt` e `/lan-certs/leaf.key`: `ARMOR_LAN_CADDYFILE=./caddy/Caddyfile.lan-issued ARMOR_LAN_CERT_DIR=$HOME/.armor/lan-ca docker compose --profile lan-ca up -d`. La cartella è montata in sola lettura; senza queste due variabili il proxy continua a usare l'autorità propria di Caddy.
4. **Installa l'autorità una volta su ogni dispositivo.** `python3 scripts/armor_lan_cert.py export-ca --out armor-lan-ca.crt` scrive il certificato pubblico. Android: Impostazioni > Sicurezza > Crittografia e credenziali > Installa un certificato > Certificato CA. iPhone: apri il file, installa il profilo, poi Impostazioni > Generali > Info > Attendibilità certificati e attivalo. Windows: doppio clic e installazione in «Autorità di certificazione radice attendibili». Linux: copialo in `/usr/local/share/ca-certificates/` ed esegui `update-ca-certificates`.
5. **Verifica.** `python3 scripts/armor_lan_cert.py fingerprint` stampa lo SHA-256 dell'autorità (ciò che fissa il pannello a parete); con `--spki`, il pin della sua chiave pubblica (ciò che fissa l'app del telefono). Confrontalo con ciò che mostra il dispositivo prima di fidarti.

## Il file delle impostazioni

`~/.armor/lan-ca/lan-ca.json` (tutto facoltativo; un valore fuori intervallo o sconosciuto è un errore, mai un'ipotesi): `enabled` (false), `ca_days` (3650), `leaf_days` (397; browser e telefoni rifiutano più di 398 giorni per alcuni certificati), `renew_days` (30), `curve` (`prime256v1` o `secp384r1`) e `name_constraints` (true). `ARMOR_LAN_CA_DIR` sposta la cartella.

## Da sapere

* Chi possiede `ca.key` può emettere certificati, per indirizzi privati, che i dispositivi che si fidano dell'autorità accettano: tieni la cartella per te, fanne una copia come per ogni altro segreto e non metterla mai in un repository.
* `remove` mette da parte la cartella (`lan-ca.removed-<ora>`); non viene cancellato nulla. I dispositivi che hanno installato la vecchia autorità dovrebbero rimuoverla.
* Nulla di tutto ciò è stato eseguito sulla CM5: i test creano un'autorità e un certificato in una cartella usa e getta con openssl e verificano che la catena sia valida per l'indirizzo e non per un altro.
