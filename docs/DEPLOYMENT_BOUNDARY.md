# Deployment boundary

The compose file is the topology of the whole system on one Docker host. It is
intentionally conservative:

* **Only Studio is published**, on `127.0.0.1:8088`. Studio's nginx proxies `/api/` to the
  server, so the browser only ever talks to one origin and the session cookie stays
  same-origin. Put a TLS reverse proxy or a VPN in front of it (and set
  `ARMOR_COOKIE_SECURE=1`) before any remote access.
* **The core network is internal**: the broker and the server have no route out and no
  published port. Field nodes reach the broker through the network infrastructure, with VLAN
  policy mapped there and not in an unreviewed container.
* **Every container is hardened**: read-only root filesystem, `no-new-privileges`, all
  capabilities dropped (Studio adds back only what nginx needs to start).
* **Secrets never enter the repository or an image.** `scripts/generate_secrets.sh` creates
  `.env` and the two broker files in `secrets/` (all Git-ignored) with random values and
  prints none. `scripts/check-required-env.sh` refuses missing, placeholder or short values and
  requires the ingest, control and operator tokens to differ. In production, provide them
  through an approved secret store.
* **The broker is not anonymous.** One user per field node, and the ACL lets a node write only its
  own telemetry and health (its last will is a health message) and read only its own commands. Only
  `armor-server` reads every node and sends commands. The listener is plain MQTT inside the
  internal network; add TLS before a node connects across an untrusted segment.
* **State lives in two named volumes** (`server-data` holds the camera vault, evidence and audit
  log; `broker-data` the broker's persistence). Back them up; keep `ARMOR_CAMERA_CONFIG_KEY`
  separately from the volume.

`scripts/validate-compose.sh` runs `docker compose config` (Docker is required and is not installed on the development PC); it validates the topology, not a
running system. For a bench without Docker see [CM5 test bench](CM5_TEST_BENCH.md).
