# Un certificado para la dirección de la máquina en la red local

Este es el camino hacia un `https://192.168.0.180` en el que confían un teléfono o un navegador, con una autoridad propia de la instalación y sin ningún nombre en el DNS público. Es **opcional y está apagado**: el perfil `tls` (un nombre, la autoridad propia de Caddy, véase HTTPS_PAIRING.md) y el perfil `lan-ca` siguen funcionando como están. El puerto 18080 del servidor **nunca se abre a Internet**: se llega a él desde la red local o a través de la VPN, y nada de esta guía lo cambia.

## Qué crea

`scripts/armor_lan_cert.py` crea, una sola vez, una **autoridad local** y, para la dirección que le des, un **segundo certificado** firmado por esa autoridad:

* `~/.armor/lan-ca/ca.crt`: el certificado de la autoridad (público: es lo que se instala en teléfonos y ordenadores).
* `~/.armor/lan-ca/ca.key`: la clave privada de la autoridad. Se queda en esa carpeta (modo 0700, la clave 0600), nunca se imprime, el programa nunca la copia y nunca forma parte de un repositorio ni de un paquete.
* `leaf.crt`, `leaf.key`, `fullchain.pem`: el certificado de la dirección (una dirección IPv4 privada, más los nombres `.lan` / `.local` que añadas, más 127.0.0.1) y su clave.

La autoridad está limitada por una restricción de nombres dentro de su propio certificado: solo puede avalar direcciones privadas y nombres `.lan` / `.local`, de modo que una copia robada de su clave no puede suplantar un sitio de Internet ante un dispositivo que confíe en ella. El programa rechaza una dirección pública.

## Los pasos

1. **Mira primero.** `python3 scripts/armor_lan_cert.py plan --ip 192.168.0.180 --name armor.lan` dice qué se crearía y no cambia nada.
2. **Enciéndelo y créalo.** `python3 scripts/armor_lan_cert.py setup --ip 192.168.0.180 --name armor.lan --enable`. Sin `--enable` (o sin `"enabled": true` en `~/.armor/lan-ca/lan-ca.json`) se niega: lo predeterminado es apagado. Si lo ejecutas de nuevo, conserva la autoridad y el certificado mientras la dirección sea la misma y queden más de `renew_days` días; si la dirección cambia, crea un certificado nuevo con la misma autoridad, así que los dispositivos no se tocan.
3. **Dale el certificado al proxy.** Usa la variante `caddy/Caddyfile.lan-issued`, que sirve `/lan-certs/leaf.crt` y `/lan-certs/leaf.key`: `ARMOR_LAN_CADDYFILE=./caddy/Caddyfile.lan-issued ARMOR_LAN_CERT_DIR=$HOME/.armor/lan-ca docker compose --profile lan-ca up -d`. La carpeta se monta de solo lectura; sin esas dos variables el proxy sigue usando la autoridad propia de Caddy.
4. **Instala la autoridad una vez en cada dispositivo.** `python3 scripts/armor_lan_cert.py export-ca --out armor-lan-ca.crt` escribe el certificado público. Android: Ajustes > Seguridad > Cifrado y credenciales > Instalar un certificado > Certificado de CA. iPhone: abre el archivo, instala el perfil y luego Ajustes > General > Información > Ajustes de confianza de certificados y actívalo. Windows: haz doble clic y instálalo en «Entidades de certificación raíz de confianza». Linux: cópialo en `/usr/local/share/ca-certificates/` y ejecuta `update-ca-certificates`.
5. **Compruébalo.** `python3 scripts/armor_lan_cert.py fingerprint` imprime el SHA-256 de la autoridad (lo que fija el panel de pared); con `--spki`, la huella de su clave pública (lo que fija la app del teléfono). Compárala con lo que muestre el dispositivo antes de confiar.

## El archivo de ajustes

`~/.armor/lan-ca/lan-ca.json` (todo opcional; un valor fuera de rango o desconocido es un error, nunca una suposición): `enabled` (false), `ca_days` (3650), `leaf_days` (397; los navegadores y teléfonos rechazan más de 398 días para algunos certificados), `renew_days` (30), `curve` (`prime256v1` o `secp384r1`) y `name_constraints` (true). `ARMOR_LAN_CA_DIR` mueve la carpeta.

## Qué conviene saber

* Quien tenga `ca.key` puede emitir certificados que los dispositivos que confían en la autoridad aceptan, para direcciones privadas: guarda la carpeta para ti, haz copia de seguridad como de cualquier otro secreto y no la pongas nunca en un repositorio.
* `remove` aparta la carpeta (`lan-ca.removed-<hora>`); no se borra nada. Los dispositivos que instalaron la autoridad antigua deben quitarla.
* Nada de esto se ha ejecutado en la CM5: las pruebas crean una autoridad y un certificado en una carpeta desechable con openssl y comprueban que la cadena se verifica para la dirección y no para otra.
