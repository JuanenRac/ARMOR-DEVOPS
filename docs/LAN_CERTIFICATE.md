# A certificate for the address of the machine on the local network

This is the way to an `https://192.168.0.180` that a phone or a browser trusts, with an authority of the installation's own and no name in the public DNS. It is **optional and off**: the `tls` profile (a name, Caddy's own authority, see HTTPS_PAIRING.md) and the `lan-ca` profile keep working as they are. Port 18080 of the server is **never opened to the Internet**: it is reached from the local network or through the VPN, and nothing in this guide changes that.

## What it makes

`scripts/armor_lan_cert.py` makes, once, a **local authority** and, for the address you give it, a **second certificate** signed by that authority:

* `~/.armor/lan-ca/ca.crt` - the authority's certificate (public: this is what is installed on the phones and computers).
* `~/.armor/lan-ca/ca.key` - the authority's private key. It stays in that folder (mode 0700, the key 0600), is never printed, never copied by the program and never part of a repository or a package.
* `leaf.crt`, `leaf.key`, `fullchain.pem` - the certificate for the address (a private IPv4 address, plus the `.lan` / `.local` names you add, plus 127.0.0.1) and its key.

The authority is limited by a name constraint inside its own certificate: it can vouch only for private addresses and `.lan` / `.local` names, so a stolen copy of its key cannot impersonate a site on the Internet for a device that trusts it. The program refuses a public address.

## The steps

1. **Look first.** `python3 scripts/armor_lan_cert.py plan --ip 192.168.0.180 --name armor.lan` says what would be made and changes nothing.
2. **Switch it on and make it.** `python3 scripts/armor_lan_cert.py setup --ip 192.168.0.180 --name armor.lan --enable`. Without `--enable` (or `"enabled": true` in `~/.armor/lan-ca/lan-ca.json`) it refuses: the default is off. Running it again keeps the authority and the certificate while the address is the same and more than `renew_days` are left; if the address changes it makes a new certificate with the same authority, so the devices are not touched.
3. **Give the proxy the certificate.** In `caddy/Caddyfile.lan` replace `tls internal` by `tls /path/to/leaf.crt /path/to/leaf.key` (the folder is read by the proxy, never written), and start it with `docker compose --profile lan-ca up -d`.
4. **Install the authority once on each device.** `python3 scripts/armor_lan_cert.py export-ca --out armor-lan-ca.crt` writes the public certificate. Android: Settings > Security > Encryption and credentials > Install a certificate > CA certificate. iPhone: open the file, install the profile, then Settings > General > About > Certificate Trust Settings and switch it on. Windows: double-click it and install it into "Trusted Root Certification Authorities". Linux: copy it into `/usr/local/share/ca-certificates/` and run `update-ca-certificates`.
5. **Check it.** `python3 scripts/armor_lan_cert.py fingerprint` prints the SHA-256 of the authority (what the wall panel pins); with `--spki`, the pin of its public key (what the phone app pins). Compare it with what the device shows before trusting it.

## The settings file

`~/.armor/lan-ca/lan-ca.json` (all optional; a value out of range or unknown is an error, never a guess): `enabled` (false), `ca_days` (3650), `leaf_days` (397; browsers and phones refuse more than 398 days for some certificates), `renew_days` (30), `curve` (`prime256v1`, or `secp384r1`) and `name_constraints` (true). `ARMOR_LAN_CA_DIR` moves the folder.

## What to know

* Whoever holds `ca.key` can issue certificates that the devices trusting the authority accept, for private addresses: keep the folder to yourself, back it up like any other secret, and never put it in a repository.
* `remove` puts the folder aside (`lan-ca.removed-<time>`); nothing is deleted. Devices that installed the old authority should remove it.
* Nothing here has run on the CM5: the tests make an authority and a certificate in a throwaway folder with openssl and check that the chain verifies for the address and not for another.
