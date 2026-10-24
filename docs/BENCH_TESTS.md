# Bench tests

The software of these checks is done and tested on a computer; what is left needs a real board, a real phone or the CM5. Nothing here has been run on hardware yet.

| Check | Connect | Run | Expected |
|---|---|---|---|
| Broker with TLS | the CM5 | `docker compose -f docker-compose.yml -f docker-compose.tls.yml up -d`, then read the broker log | no "Permission denied" on `/run/secrets/mqtt_tls_key` |
| Server health | the CM5 | `docker compose build server`, `docker compose up -d`, then `docker inspect` the health state | `healthy` |
| Pinned images | the CM5 | build once, then pin the Caddy and base image digests | the same build repeats with the pinned digests |
| Remote mode | the CM5 | try the VPN and DNS rules of the remote mode | each rule behaves as documented |
