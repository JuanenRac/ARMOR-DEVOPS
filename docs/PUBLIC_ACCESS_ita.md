# Aprire la porta 18080 a Internet - cosa controllare prima

Il server può accettare richieste da Internet se inoltri la porta 18080 sul router. Questo progetto non apre nulla: il router è tuo. Il server si limita a irrobustirsi. Il broker (MQTT) e i nodi non vengono mai pubblicati.

## Prima di inoltrare la porta

* Il token di controllo ha almeno 32 caratteri casuali e la password di Studio almeno 12 (altrimenti `public_access_unsafe` elenca `control_token_short` / `password_short`).
* TLS è attivo: il certificato proprio del server (`TLS_CERT_PATH`, `TLS_KEY_PATH`) o un reverse proxy indicato in `ARMOR_TRUST_PROXY` che parla https; il cookie è Secure (`tls_missing`, `cookie_not_secure`).
* L'accesso in due passaggi è attivo per tutti gli amministratori e `ARMOR_TOTP_REQUIRED` è `remote` o `always`.
* `ARMOR_REMOTE_POLICY` è `operate` o `view`, a meno che tu non debba davvero amministrare da fuori.
* `GET /api/v1/remote/check` da un telefono con dati mobili mostra l'indirizzo, `remote` e il protocollo `https`.

## Attivarlo

In Studio, Configurazione > Sicurezza, attiva `network.public_access` (disattivata per impostazione predefinita; chiede una nuova prova di identità). Finché è disattivata, ogni richiesta da fuori casa riceve `403 public_access_off`. Gli accessi falliti si contano per indirizzo: `ARMOR_PUBLIC_LOGIN_ATTEMPTS` (5) entro `ARMOR_PUBLIC_LOGIN_WINDOW_S` secondi (900) chiudono l'indirizzo con `429 public_login_locked`.

## Dopo

Controlla il registro di audit (rifiuti `public_access` e `studio.login` negati), tieni aggiornato il router e disattiva l'opzione quando non serve più. Questa modalità è stata provata solo con un server simulato, mai con il tuo router né con Internet.
