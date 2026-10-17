# Usare A.R.M.O.R. da fuori casa - passo dopo passo

La regola: **una sola porta** e **un nome, mai un indirizzo**. Il broker MQTT e i nodi non si pubblicano mai su Internet.

## 1. Scegli la porta

* **A. Una VPN (consigliato)**: WireGuard o Tailscale sulla macchina che esegue il server. Da fuori il telefono entra nella VPN e tutto funziona come a casa (anche il pannello di ogni nodo). Se il tuo operatore non ti dà un indirizzo pubblico tuo (CGNAT), Tailscale funziona senza aprire nulla.
* **B. HTTPS**: un reverse proxy con certificato vero (il profilo `tls` di questo repository) su una porta del router. Comodo da qualsiasi browser; imposta la politica «operate» perché l'amministrazione resti per la casa o la VPN.

## 2. Un nome che segue il tuo indirizzo

Il tuo indirizzo pubblico è fisso o cambia ogni tanto. In entrambi i casi usa un **nome** (DuckDNS, No-IP, il DNS dinamico del router o un dominio tuo) e qualcosa che lo aggiorni quando l'indirizzo cambia (il client del router, o `ddclient`/lo script di DuckDNS sulla macchina). Metti un TTL breve (da 60 a 300 s). Telefono, Studio e VPN usano sempre il nome.

## 3. Nel router

Inoltra **una** porta alla macchina del server: `443/TCP` per B (e `80/TCP` se il certificato è vero, per il suo controllo), oppure `51820/UDP` per WireGuard in A. Mai `1883`, `8883` né la porta di un nodo.

## 4. Sul server (Docker)

In `.env`:

```
ARMOR_TLS_HOST=casa.duckdns.org          # il tuo nome
ARMOR_TLS_ISSUER=tu@example.com          # chiede il certificato a Let's Encrypt e lo rinnova
ARMOR_TLS_PORT=443
ARMOR_TLS_HTTP_PORT=80
ARMOR_TLS_BIND=0.0.0.0
ARMOR_PUBLIC_ORIGIN=https://casa.duckdns.org
ARMOR_TRUST_PROXY=uniquelocal            # così il server vede l'indirizzo reale di ogni visitatore
ARMOR_TOTP_REQUIRED=remote               # secondo fattore da fuori (configuralo prima da dentro)
ARMOR_REMOTE_POLICY=operate              # da fuori: guardare e usare l'allarme; amministrare solo da casa o dalla VPN
```

poi `docker compose --profile tls up -d`. Sul banco CM5 le stesse impostazioni sono in `armor.network.env` (Studio > Configurazione > Sicurezza le scrive per te).

## 5. In Studio

Configurazione > Sicurezza: attiva il secondo fattore (app di autenticazione) su ogni account, salva i codici di recupero e guarda le sessioni aperte. Da amministratore, indica il proxy attendibile, le reti che contano come la casa, la politica e la durata delle sessioni da fuori.

## 6. Sul telefono

A.R.M.O.R. Control: scrivi il nome come server (`https://casa.duckdns.org`), accedi (il codice dell'app viene chiesto come secondo passaggio) e controlla Altro > Sicurezza.

## 7. Verifica

Dal telefono **con dati mobili**, in Studio o nell'app, premi «Controlla come mi vede il server»: deve dire **da fuori** e mostrare il tuo indirizzo reale. Se dice «da casa», il proxy non passa l'indirizzo: correggi `ARMOR_TRUST_PROXY` prima di fidarti di qualsiasi cosa.

## Mai

Inoltrare la porta del broker o di un nodo, nemmeno «solo un momento»; usare l'indirizzo invece del nome; lasciare le password predefinite; saltare il secondo fattore per un amministratore che accede da fuori.
