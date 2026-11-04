# Bench tests

The software of these checks is done and tested on a computer; what is left needs a real board, a real phone or the CM5. Nothing here has been run on hardware yet.

| Check | Connect | Run | Expected |
|---|---|---|---|
| Broker with TLS | the CM5 | `docker compose -f docker-compose.yml -f docker-compose.tls.yml up -d`, then read the broker log | no "Permission denied" on `/run/secrets/mqtt_tls_key` |
| Server health | the CM5 | `docker compose build server`, `docker compose up -d`, then `docker inspect` the health state | `healthy` |
| Pinned images | the CM5 | build once, then pin the Caddy and base image digests | the same build repeats with the pinned digests |
| Remote mode | the CM5 | try the VPN and DNS rules of the remote mode | each rule behaves as documented |
| Live bench without Docker | a runner or any machine with Node, Python and the server and simulator checkouts | `python scripts/bench_live.py --server ../ARMOR-SERVER --simulator ../ARMOR-SIMULATOR`; the workflow `bench-live.yml` does it every night | 31 checks pass: the REST routes answer or refuse by token, the events socket carries every simulated node; no broker, so the MQTT path is not exercised |
| Virtual bench | a Docker host | `docker compose --profile bench up -d --build`, then watch the nodes `bench-1` to `bench-3` in Studio | the three nodes appear and report every second; the image has not been built on a real host yet |
| Upgrade rollback | the CM5 | install one release, then `install_cm5.sh --apply` with a release whose server fails to start | `current` points to the first release again, both services answer `/healthz` and the installer says it went back |
