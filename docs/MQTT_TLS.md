# Encrypting the link to the broker (MQTT over TLS) - optional, step by step

Languages: [Español](MQTT_TLS_spa.md) · [Deutsch](MQTT_TLS_deu.md) · [Français](MQTT_TLS_fra.md) · [Italiano](MQTT_TLS_ita.md) · [日本語](MQTT_TLS_jpn.md) · [中文](MQTT_TLS_zho.md) · [Português](MQTT_TLS_por.md)

**It is off.** Today the nodes talk plain MQTT to the broker on the house network (port `18883`), and nothing changes unless you follow this guide. Turning it on adds a **second door** (`8883`, TLS) next to the plain one; the plain one stays until you decide to remove it.

The certificate is not from the Internet: the installation makes **its own certificate authority** on the machine that runs the broker. A node (or the server) that is told to use `mqtts://` trusts **that authority only**, and checks that the broker's certificate was made for the name or the address it connected to. Anything else - another authority, a certificate for another address - is refused.

## 1. On the machine that runs the broker

```bash
scripts/armor_mqtt_tls.sh plan --name casa.local --ip 192.168.0.180      # what it would do; changes nothing
sudo scripts/armor_mqtt_tls.sh setup --name casa.local --ip 192.168.0.180
sudo scripts/armor_mqtt_tls.sh status
```

* The certificate vouches for the names and addresses of the machine (its host name, `localhost`, `127.0.0.1`, its IPv4 addresses) plus every `--name` and `--ip` you give. **A node connects to one of them** (`mqtts://192.168.0.180:8883`): give the address the nodes will use.
* The **private key of the authority** is made on the machine and stays in `etc/mqtt-ca` (folder `0700`, key `0600`, root only). It is never in a repository, never next to the broker and never leaves the machine. The broker gets only its own key.
* The broker is restarted by `setup` (a new listener needs a restart): the nodes reconnect in a few seconds. The plain port is not touched.
* Running `setup` again changes nothing that is still good. It makes a **new broker certificate with the same authority** when the addresses change or less than 30 days are left (the broker certificate lasts two years). Because the authority is the same, **the nodes do not have to be touched**. The authority lasts ten years.
* If the host firewall of this repository is used, it only knows the plain port: allow `8883/tcp` from the field network yourself.

## 2. In each node

Open the panel of the node, **Broker** page:

1. Write the address as `mqtts://192.168.0.180:8883` (the address must be one of those the certificate vouches for).
2. Tick **Encrypt the link to the broker (TLS)**.
3. Paste the certificate of the authority in the box. Get it with `sudo scripts/armor_mqtt_tls.sh export-ca` (it is public: a single block from `-----BEGIN CERTIFICATE-----` to `-----END CERTIFICATE-----`, about 600 bytes; at most 2 KB). Anything that is not one certificate in PEM is refused.
4. Save and restart.

The node's account on the broker (user and password) does not change. With the encryption on, the node waits for its clock before it connects (up to two minutes), because a certificate has dates. The saved backup brokers must be `mqtts://` too while the switch is on, and they are checked against the same authority. **Off** (the default), the node behaves exactly as before.

## 3. The server of this machine

```bash
sudo scripts/armor_mqtt_tls.sh server-tls on      # ARMOR_MQTT_URL=mqtts://localhost:8883 and ARMOR_MQTT_CA_FILE in the environment file
sudo systemctl restart armor-server
```

By hand: `ARMOR_MQTT_URL=mqtts://localhost:8883` and `ARMOR_MQTT_CA_FILE=/path/to/ca.pem`. The server refuses to start if the file is not one valid certificate, or if `ARMOR_MQTT_CA_FILE` is set with an `mqtt://` address (the link would stay unencrypted while you believed otherwise). Studio shows the state in **Configuration > Broker**: whether the link is encrypted and the fingerprint of the authority, to compare with `sudo scripts/armor_mqtt_tls.sh status`. `server-tls off` goes back to the plain port.

## 4. Turning it off

Untick the switch in each node (and put the `mqtt://` address back), run `server-tls off` and then `sudo scripts/armor_mqtt_tls.sh remove`. Nothing is deleted: the broker's files and the configuration are put aside next to the old ones, and the authority is kept (`--forget-ca` puts it aside too) so that a later `setup` keeps the nodes that already trust it.

## What this does and does not do

* It encrypts and authenticates the broker to the nodes and the server. It does **not** ask the nodes for a certificate of their own: they still identify themselves with their account.
* It protects the house network against someone listening or pretending to be the broker. It is not a reason to publish the broker: `8883` is never forwarded to the Internet (see `REMOTE_ACCESS.md`).
* Checked with OpenSSL and with Mosquitto 2.0 on a computer (the certificate, the second listener, the handshake, the pinning of one authority, the refusal of another authority and of another address, and the server's connection). **Not yet checked on a node's board**: the handshake costs a little time and memory on a microcontroller.
