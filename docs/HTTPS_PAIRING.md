# HTTPS for the phones: the house's own authority, and pairing

The Android app keeps plain `http` for the local network only as long as nothing else exists. This guide is the way to a house that is reached over `https` everywhere, with an authority of its own that the phone remembers, so that the app can one day refuse plain `http`.

## The default profile

The `tls` profile of this repository puts Caddy in front of Studio and the server. Its default is the safe one: Caddy's **own local authority** (`tls internal`), a certificate for `ARMOR_TLS_HOST`, HSTS of five minutes, `https` only. Nothing in it needs the internet. For a name on the internet put an e-mail address in `ARMOR_TLS_ISSUER` and Caddy asks Let's Encrypt (see `REMOTE_ACCESS.md`): then the phone trusts the certificate by itself and there is nothing to pair.

## The steps

1. **Name.** Choose the name the phones use for the house (the dynamic DNS name from outside, or a name of the local network) and put it in `ARMOR_TLS_HOST` (`ARMOR_TLS_PORT=443` if the router forwards 443).
2. **Start it.** `docker compose --profile tls up -d` (or Caddy from the package with the same `Caddyfile`). The server runs with `ARMOR_TRUST_PROXY=1` and `ARMOR_PUBLIC_ORIGIN=https://<name>`.
3. **Check it.** `scripts/armor_tls_check.sh <name> 443 <root.crt>` says whether the server answers, whether the chain is valid for the name, whether more than 14 days are left and which key a phone would pin, and prints the line `armor-pin:<name>:<pin>`. The root certificate is `pki/authorities/local/root.crt` in Caddy's data (the maintenance helper finds it; `ARMOR_TLS_CA_FILE` names it when it is elsewhere).
4. **Pair each phone.** In Studio, Configuration > Security > way in from outside > *Pair the phone with the HTTPS of the house*: type the name, press the button, copy the text. In the app, More > Security, paste it. The app then accepts only that authority for the house; a different key is refused and said.
5. **Try everything** on each phone, on the home Wi-Fi and on mobile data: sign in, cameras, arming, alarms, push.
6. **Only then** the owner may forbid plain `http` in the app (`cleartext=false`) in a new build. Until every phone is paired and tried, leave it as it is.

## What to know

* The pin is the SHA-256 of the **public** key of the authority: it is no secret, but whoever gives it to a phone decides whom the phone trusts, so it is shown to administrators only and should be compared with what the app shows.
* Caddy renews the certificate of the house by itself. The authority lasts about ten years; if it is replaced (a new Caddy data folder) the pin changes and the phones are paired again.
* The key of the authority never leaves the machine and is never read by A.R.M.O.R.
* A phone that was paired and meets a different key refuses to connect: that is the point. To pair it again, forget the pin in the app (More > Security) and paste the new text.

## The test on the machine (for the owner)

`scripts/armor_tls_check.sh` passes on the CM5; the pairing text is the same in Studio and in the output of the script; a phone paired on the home Wi-Fi also connects from mobile data; after `systemctl restart caddy` (or the container) nothing needs pairing again.
