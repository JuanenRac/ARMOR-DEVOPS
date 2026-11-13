# Opening port 18080 to the Internet - what to check first

The server can take requests from the Internet when you forward port 18080 on the router. Nothing is opened by this project: the router is yours. The server only hardens itself. The broker (MQTT) and the nodes are never published.

## Before forwarding the port

* The control token has at least 32 random characters and the Studio password at least 12 (`public_access_unsafe` lists `control_token_short` / `password_short` otherwise).
* TLS is on: the server's own certificate (`TLS_CERT_PATH`, `TLS_KEY_PATH`) or a reverse proxy that is named in `ARMOR_TRUST_PROXY` and speaks https; the cookie is Secure (`tls_missing`, `cookie_not_secure`).
* Two-step sign-in is on for every administrator and `ARMOR_TOTP_REQUIRED` is `remote` or `always`.
* `ARMOR_REMOTE_POLICY` is `operate` or `view` unless you really need to administer from outside.
* `GET /api/v1/remote/check` from a phone on mobile data shows the address, `remote` and the protocol `https`.

## Turning it on

In Studio, Configuration > Security, switch on `network.public_access` (off by default; it asks for a new proof of identity). While it is off every request from outside the house answers `403 public_access_off`. Failed sign-ins are counted by address: `ARMOR_PUBLIC_LOGIN_ATTEMPTS` (5) inside `ARMOR_PUBLIC_LOGIN_WINDOW_S` seconds (900) close the address with `429 public_login_locked`.

## Afterwards

Read the audit trail for `public_access` refusals and denied `studio.login` entries, keep the router firmware up to date, and switch the option off again when you stop needing it. This mode has been tried against a simulated server only, never against your router or the Internet.
