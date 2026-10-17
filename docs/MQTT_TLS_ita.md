# Cifrare il collegamento con il broker (MQTT su TLS) - facoltativo, passo per passo

Lingue: [English](MQTT_TLS.md) · [Español](MQTT_TLS_spa.md) · [Deutsch](MQTT_TLS_deu.md) · [Français](MQTT_TLS_fra.md) · [日本語](MQTT_TLS_jpn.md) · [中文](MQTT_TLS_zho.md) · [Português](MQTT_TLS_por.md)

**È disattivato.** Oggi i nodi parlano MQTT non cifrato con il broker nella rete di casa (porta `18883`), e nulla cambia se non segui questa guida. Attivarlo aggiunge una **seconda porta** (`8883`, TLS) accanto a quella normale; quella normale resta finché non decidi di toglierla.

Il certificato non arriva da Internet: l'installazione crea **la propria autorità di certificazione** sulla macchina che esegue il broker. Un nodo (o il server) a cui si dice di usare `mqtts://` si fida **solo di quell'autorità** e controlla che il certificato del broker sia stato fatto per il nome o l'indirizzo a cui si è collegato. Tutto il resto - un'altra autorità, un certificato per un altro indirizzo - viene rifiutato.

## 1. Sulla macchina che esegue il broker

```bash
scripts/armor_mqtt_tls.sh plan --name casa.local --ip 192.168.0.180      # cosa farebbe; non cambia nulla
sudo scripts/armor_mqtt_tls.sh setup --name casa.local --ip 192.168.0.180
sudo scripts/armor_mqtt_tls.sh status
```

* Il certificato garantisce i nomi e gli indirizzi della macchina (il suo nome host, `localhost`, `127.0.0.1`, i suoi indirizzi IPv4) più ogni `--name` e `--ip` indicato. **Un nodo si collega a uno di essi** (`mqtts://192.168.0.180:8883`): indica l'indirizzo che useranno i nodi.
* La **chiave privata dell'autorità** viene creata sulla macchina e resta in `etc/mqtt-ca` (cartella `0700`, chiave `0600`, solo root). Non è mai in un repository, mai accanto al broker e non lascia mai la macchina. Il broker riceve solo la propria chiave.
* `setup` riavvia il broker (un nuovo listener richiede il riavvio): i nodi si ricollegano in pochi secondi. La porta non cifrata non viene toccata.
* Eseguire di nuovo `setup` non cambia nulla di ciò che è ancora valido. Crea un **nuovo certificato del broker con la stessa autorità** quando cambiano gli indirizzi o mancano meno di 30 giorni (il certificato del broker dura due anni). Poiché l'autorità è la stessa, **i nodi non vanno toccati**. L'autorità dura dieci anni.
* Se si usa il firewall dell'host di questo repository, esso conosce solo la porta non cifrata: consenti tu stesso `8883/tcp` dalla rete di campo.

## 2. In ogni nodo

Apri il pannello del nodo, pagina **Broker**:

1. Scrivi l'indirizzo come `mqtts://192.168.0.180:8883` (deve essere uno di quelli che il certificato garantisce).
2. Spunta **Cifra il collegamento al broker (TLS)**.
3. Incolla il certificato dell'autorità nella casella. Ottienilo con `sudo scripts/armor_mqtt_tls.sh export-ca` (è pubblico: un unico blocco da `-----BEGIN CERTIFICATE-----` a `-----END CERTIFICATE-----`, circa 600 byte; al massimo 2 KB). Ciò che non è un solo certificato in PEM viene rifiutato.
4. Salva e riavvia.

L'account del nodo sul broker (utente e password) non cambia. Con la cifratura attiva, il nodo aspetta di avere l'ora prima di collegarsi (fino a due minuti), perché un certificato ha delle date. Anche i broker di riserva salvati devono essere `mqtts://` finché l'interruttore è attivo, e vengono verificati con la stessa autorità. **Disattivata** (predefinito), il nodo si comporta esattamente come prima.

## 3. Il server di questa macchina

```bash
sudo scripts/armor_mqtt_tls.sh server-tls on      # ARMOR_MQTT_URL=mqtts://localhost:8883 e ARMOR_MQTT_CA_FILE nel file di ambiente
sudo systemctl restart armor-server
```

A mano: `ARMOR_MQTT_URL=mqtts://localhost:8883` e `ARMOR_MQTT_CA_FILE=/percorso/di/ca.pem`. Il server si rifiuta di partire se il file non è un certificato valido, o se `ARMOR_MQTT_CA_FILE` è impostato con un indirizzo `mqtt://` (il collegamento resterebbe non cifrato mentre credi il contrario). Studio mostra lo stato in **Configurazione > Broker**: se il collegamento è cifrato e l'impronta dell'autorità, da confrontare con `sudo scripts/armor_mqtt_tls.sh status`. `server-tls off` torna alla porta non cifrata.

## 4. Disattivarlo

Togli la spunta all'interruttore in ogni nodo (e rimetti l'indirizzo `mqtt://`), esegui `server-tls off` e poi `sudo scripts/armor_mqtt_tls.sh remove`. Non viene cancellato nulla: i file del broker e la configurazione vengono messi da parte accanto ai vecchi, e l'autorità viene conservata (`--forget-ca` mette da parte anche quella) così che un `setup` successivo mantenga i nodi che già si fidano di essa.

## Cosa fa e cosa non fa

* Cifra e autentica il broker verso i nodi e il server. **Non** chiede ai nodi un certificato proprio: continuano a identificarsi con il loro account.
* Protegge la rete di casa da chi ascolta o si finge il broker. Non è un motivo per pubblicare il broker: `8883` non viene mai inoltrata a Internet (vedi `REMOTE_ACCESS.md`).
* Verificato con OpenSSL e con Mosquitto 2.0 su un computer (il certificato, il secondo listener, l'handshake, il vincolo a una sola autorità, il rifiuto di un'altra autorità e di un altro indirizzo, e la connessione del server). **Non ancora verificato sulla scheda di un nodo**: l'handshake costa un po' di tempo e di memoria su un microcontrollore.
