# CM5 test bench

A Raspberry Pi CM5 that already runs other software can host A.R.M.O.R. as a
**completely separate project**, so ARMOR can be tried on real ARM64 hardware without
touching anything else on the machine. This is a test bench, not the Jetson deployment.

## What the installer guarantees

`scripts/install_cm5.sh` (sent and run by `scripts/deploy_cm5.sh`):

* creates its own system user `armor` (no login shell, no sudo) and keeps everything under `/opt/armor`;
* installs two systemd units, `armor-server` and `armor-studio`, on their **own ports**
  (18080 and 18081 by default) and refuses to start if either port is already in use by
  something else;
* refuses a prefix that is not one directory directly under `/opt` (never a place inside another project), or an existing directory that is not already an A.R.M.O.R. install;
* limits what the bench can take from the machine (`Nice`, `CPUWeight`, `IOWeight`,
  `MemoryMax`, `TasksMax`) and hardens the units (`ProtectSystem=strict`, `NoNewPrivileges`,
  empty capability set and restricted address families);
* never edits, restarts or reads another project's files, opens a firewall port or installs a package;
* keeps secrets in `/opt/armor/etc/armor.env` (mode 0640, `root:armor`), generated once and
  kept across upgrades, and never prints them;
* keeps the four newest releases and moves older ones aside instead of deleting them.

## Deploy

From the computer that has the source:

```bash
scripts/deploy_cm5.sh --host 192.168.0.180 --user <ssh user> --key <ssh key>          # dry run: prints the plan
scripts/deploy_cm5.sh --host 192.168.0.180 --user <ssh user> --key <ssh key> --apply  # install or upgrade
```

The script builds ARMOR-SERVER and ARMOR-STUDIO in a **clean temporary copy** (never in your
working trees, where a running dev server can lock files), runs their type checks and tests
there, sends one archive and runs the installer over SSH.

Then open `http://<host>:18081`. The Studio user is `admin`; its password is
`ARMOR_STUDIO_PASSWORD` in `/opt/armor/etc/armor.env` on the bench (root can read it).
Studio starts against the server the deployment publishes at `/armor-config.json`.

## Administering it from Studio

The server runs as the unprivileged user `armor` with no sudo and a read-only system, on purpose. To let an administrator start, stop and restart the services, edit their
settings files and add the MQTT accounts of new nodes from Studio (Configuration > Services, MQTT broker, Settings files), install with `--with-admin`:

```bash
sudo scripts/install_cm5.sh --public-host 192.168.0.180 --apply --with-mqtt --with-admin
```

That adds one more unit, `armor-admin`, which runs as root and is the only privileged part. It listens on `/run/armor-admin.sock`, which only the group `armor` can open, and also
wants the token in `/opt/armor/etc/armor.admin.env`. It can do only a closed list of things: start, stop, restart or reload the units `armor-server`, `armor-studio`, `armor-mosquitto`
and `armor-network`; read and write the settings files `armor.env`, `armor.mqtt.env`, `armor.network.env`, `armor.reach` and the broker's `mosquitto.conf` and `acl` (a size limit, a check of
the format and a copy of the old file); and make or remove broker accounts by running `mqtt_identity.sh`. The hashed password file of the broker is never offered, and its own files
(`/opt/armor/bin`) belong to root, so the service user cannot change what runs as root. Without `--with-admin` nothing of this exists and the Studio screens say so.

## Reaching it from the Internet

A browser is only allowed to sign in through the addresses the installation was told about: the server's list of allowed origins
(CORS) and Studio's content-security policy both hold them. Opening Studio through the router's public address without telling the
installer ends in *Could not sign in*, whatever the password. With the router forwarding, for example, public port 2601 to 18081
(Studio) and 2600 to 18080 (server):

```bash
scripts/deploy_cm5.sh --host 192.168.0.180 --user <ssh user> --key <ssh key> --apply \
  --also-reach http://<public address>:2601=http://<public address>:2600
```

Then open `http://<public address>:2601` and type `http://<public address>:2600` as the server. The pair is remembered by later
installs (`--forget-reach` drops it). If the SSH port is also forwarded, add `--port <public ssh port> --public-host 192.168.0.180`.

**This is plain HTTP.** The password and the session travel across the Internet in clear. Put the TLS profile (Caddy) or a VPN in
front before leaving it open, and never forward the broker's port (18883): only the two web ports are meant to be reached.

## What is not on the bench

FFmpeg (so live video, snapshots and recordings answer *not configured*) and an MQTT broker are
not installed: installing packages on a shared machine is a decision for its owner. Both are
optional in the server. To try them, install FFmpeg and set `ARMOR_FFMPEG_PATH` in the units'
environment, and point `ARMOR_MQTT_URL` at a broker.

## Removing it

Stop and disable `armor-server` and `armor-studio`, remove their unit files and move `/opt/armor`
aside. Nothing else on the machine refers to them.
