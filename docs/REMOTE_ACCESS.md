# Using A.R.M.O.R. from outside the house - step by step

Languages: [Español](REMOTE_ACCESS_spa.md) · [Deutsch](REMOTE_ACCESS_deu.md) · [Français](REMOTE_ACCESS_fra.md) · [Italiano](REMOTE_ACCESS_ita.md) · [日本語](REMOTE_ACCESS_jpn.md) · [中文](REMOTE_ACCESS_zho.md) · [Português](REMOTE_ACCESS_por.md)

The rule: **one door only**, and a **name, never an address**. The MQTT broker and the nodes are never published to the Internet.

## 1. Choose the door

* **A. A VPN (recommended)**: WireGuard or Tailscale on the machine that runs the server. From outside, the phone joins the VPN and then everything works as at home (also the panel of each node). If your provider gives you no public address of your own (CGNAT), Tailscale works without opening anything.
* **B. HTTPS**: a reverse proxy with a real certificate (the `tls` profile of this repository) on one port of the router. Handy from any browser; set the policy "operate" so that administering stays for the house or the VPN.

## 2. A name that follows your address

Your public address is either fixed or changes now and then. Either way, use a **name** (DuckDNS, No-IP, the dynamic DNS of the router, or your own domain) and something that updates it when the address changes (the router's client, or `ddclient`/DuckDNS' script on the machine). Put a short TTL (60 to 300 s) on the record. The phone, Studio and the VPN always use the name.

## 3. In the router

Forward **one** port to the machine that runs the server: `443/TCP` for B (and `80/TCP` if the certificate is a real one, for its check), or `51820/UDP` for WireGuard in A. Never `1883`, `8883` or the port of a node.

## 4. On the server (Docker)

In `.env`:

```
ARMOR_TLS_HOST=casa.duckdns.org          # your name
ARMOR_TLS_ISSUER=you@example.com         # asks Let's Encrypt for the certificate and renews it
ARMOR_TLS_PORT=443
ARMOR_TLS_HTTP_PORT=80
ARMOR_TLS_BIND=0.0.0.0
ARMOR_PUBLIC_ORIGIN=https://casa.duckdns.org
ARMOR_TRUST_PROXY=uniquelocal            # the server then sees the real address of each visitor
ARMOR_TOTP_REQUIRED=remote               # second factor from outside (set it up from inside first)
ARMOR_REMOTE_POLICY=operate              # from outside: look and operate the alarm; administering only from the house or the VPN
```

then `docker compose --profile tls up -d`. On the CM5 bench the same settings are in `armor.network.env` (Studio > Configuration > Security writes them for you).

## 5. In Studio

Configuration > Security: turn on the second factor (authenticator app) for every account, save the recovery codes, and look at the open sessions. As an administrator, set the trusted proxy, the networks that count as the house, the policy and the lifetime of the sessions from outside.

## 6. The VPN, the name and the panels of the nodes, from Studio (no commands)

With the maintenance agent installed (`install_cm5.sh --with-maintenance`) and WireGuard on the machine (`sudo apt install wireguard-tools qrencode`), an administrator does it all in Studio > Configuration > Security > Access from outside the house:

1. **VPN:** type the name or address the phone will use (such as `casa.duckdns.org`), keep the port and the network of the house, and press *Set up the VPN*. It tells you which UDP port to forward on the router to the machine.
2. **A phone or a laptop:** under *Add a device* give it a name (`phone-ana`), press *Create* and scan the QR code with the WireGuard app. The code holds a private key: close it afterwards and give it to nobody else. You can show it again or remove the device later.
3. **A name that follows your house:** choose DuckDNS, Cloudflare or an address to call, type its data and press *Save and check now*. The machine checks every five minutes and calls the provider only when the address changed.
4. **The panel of a node from outside:** register the node (its id and its address inside the house). For a node with HTTPS press *Look at its certificate*, compare the fingerprint with the one in the node's own panel (About) and press *Trust this certificate*. *Open panel* then works from outside, through the server, and the node is never published.

The same can be done from a terminal with `armor_wireguard.sh` and `armor_ddns.sh` (the header of each one lists its commands; `plan` shows what would be written before anything is).


## 7. On the phone

A.R.M.O.R. Control: type the name as the server (`https://casa.duckdns.org`), sign in (the code of the app is asked as a second step) and check More > Security.

## 8. Check it

From the phone **on mobile data**, in Studio or the app, press "Check how the server sees me": it must say **from outside** and show your real address. If it says "from the house", the proxy is not passing the address: fix `ARMOR_TRUST_PROXY` before trusting anything.

## Never

Forward the broker's port, a node's port, or "just for a moment"; use the address instead of the name; leave the default passwords; skip the second factor for an administrator who signs in from outside.
