# Who may change the sensitive settings of the maintenance helper

The maintenance helper (`scripts/armor_maintenance_agent.py`) listens on a Unix socket that the group `armor` can open and wants a token. Every service of that group can read the token, so for what changes the machine two more checks can be switched on. Both are **off until the administrator writes them** in `armor.maint.env`, so an update never locks anybody out.

The calls they protect: `POST /v1/console/run`, `POST /v1/system/reboot`, `POST /v1/system/upgrade`, `POST /v1/system/auto-updates`, `POST /v1/remote/wireguard/setup` and `POST /v1/remote/ddns/setup`. Reading and the updates of the programs are not affected.

| Setting | What it does |
|---|---|
| `ARMOR_MAINT_PEER_UIDS=998,0` | The kernel tells the helper the user number of the process on the other end of the socket (`SO_PEERCRED`); a user that is not in the list gets `403 peer_not_allowed`. Empty: not checked. |
| `ARMOR_MAINT_TOTP_FILE` (default `<prefix>/etc/maint.totp`) | When the file exists, a sensitive call must bring a current six-digit code in the header `X-Armor-Maint-Totp` (`401 totp_required`, `401 totp_invalid`). A code is good once. |

Make the secret of the authenticator with `armor_maintenance_agent.py --totp-enroll` (as root): it writes the file with mode 0600 and shows the secret once, to be added to an authenticator app (SHA-1, six digits, 30 seconds). Delete the file to turn the code off again.

The tests are in `scripts/test_maintenance_guard.py`.

## Secrets of the .env files never leave the admin agent

The admin agent (`scripts/armor_admin_agent.py`) answers a read of `server.env`, `mqtt.env` or `network.env` with the value of every secret key replaced by `********` and the login or token of an address (`mqtt://user:secret@host`, `?token=...`) removed, and marks the answer `masked: true`. A file saved with `********` where a secret was gets the value it had from the file on disk; a mask for a key that is no longer in the file is refused (`masked_value_without_original:<KEY>`). The server and the console therefore never hold the originals. The rules and their vectors are `env_masking.json` of the shared repository (this repository keeps a copy in `scripts/env_masking.json`, and `scripts/test_admin_agent.py` compares it and runs every vector).
