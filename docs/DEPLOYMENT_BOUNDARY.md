# Deployment boundary

The compose file is the topology of the whole system on one Docker host. It is
intentionally conservative:

* **Studio is published** on `127.0.0.1:8088`, and **the broker's port** on `127.0.0.1:1883` unless `ARMOR_MQTT_BIND` holds the address of the interface of the field network (set it
  there for the nodes to reach the broker; never `0.0.0.0` on a machine that also faces the internet). Studio's nginx proxies `/api/` to the server, so the browser only ever talks to one
  origin and the session cookie stays same-origin. Put a TLS reverse proxy or a VPN in front of it (and set `ARMOR_COOKIE_SECURE=1`) before any remote access.
* **The server has no published port but does have a way out**: it is on the core network (where Studio and the broker reach it) and on the edge network, because it must reach Telegram,
  the webhook, the cameras of the LAN, the releases of GitHub that update the nodes and the router it inspects. Remove it from the edge network to cut all of that off, knowing what stops
  working. VLAN policy is still mapped in the network infrastructure and the host firewall, not in an unreviewed container.
* **Every container is hardened**: read-only root filesystem, `no-new-privileges`, all
  capabilities dropped (Studio, the broker and the TLS proxy add back only what they need to start).
* **Secrets never enter the repository or an image.** `scripts/generate_secrets.sh` creates
  `.env` and the two broker files in `secrets/` (all Git-ignored) with random values and
  prints none. `scripts/check-required-env.sh` refuses missing, placeholder or short values and
  requires the ingest, control and operator tokens to differ. In production, provide them
  through an approved secret store.
* **The broker is not anonymous.** One user per field node, and the ACL lets a node write only its
  own telemetry and health (its last will is a health message) and read only its own commands. Only
  `armor-server` reads every node and sends commands. The listener is plain MQTT, on the core network and on the port published above;
  add TLS before a node connects across an untrusted segment.
* **State lives in four named volumes** (`server-data` holds the camera vault, evidence and audit
  log; `broker-data` the broker's persistence; `proxy-data` and `proxy-config` the TLS proxy's, and `proxy-data` holds the **private key of Caddy's local certificate authority**: protect and
  back it up like the secrets). Back them up; keep `ARMOR_CAMERA_CONFIG_KEY` separately from the volume.

`scripts/validate-compose.sh` runs `docker compose config` (Docker is required and is not installed on the development PC); it validates the topology, not a
running system. For a bench without Docker see [CM5 test bench](CM5_TEST_BENCH.md).

## The host firewall

`scripts/firewall_core.sh` puts the network design (`ARMOR-DOCS/docs/SECURITY_BASELINE.md`) into rules for the core machine, in a table of its own:

    firewall_core.sh print --field 192.168.0.0/24 --clients 192.168.10.0/24        # what it would load
    sudo firewall_core.sh apply --field 192.168.0.0/24 --rollback-after 120         # load it; it undoes itself in 120 s ...
    sudo firewall_core.sh confirm                                                   # ... unless you say it is good
    sudo firewall_core.sh apply --field 192.168.0.0/24 --clients 192.168.10.0/24 --persist   # and at every boot
    sudo firewall_core.sh revert

The broker (18883) accepts only the **field** network and this machine; the server (18080) and Studio (18081) accept only the **clients'** network and this machine when `--clients` is given (without it they stay as open as
they were, protected by the login). Nothing else is mentioned and the policy is *accept*, so SSH, another project's ports and DNS are untouched. It acts on the machine's input: services installed natively are covered,
a port published by Docker is not (keep those on loopback behind Caddy). A remote way in through a router's port forwarding arrives from the router's or the Internet's address: give `--clients` only if that address is
in it, or leave `--clients` out. **Never forward the broker's port.** The rules have been tested as text only (`scripts/test_firewall.sh`); they have not been loaded on a machine.
