# HTTPS para los teléfonos: la autoridad propia de la casa y el emparejado

La app Android conserva `http` sin cifrar para la red local mientras no haya otra cosa. Esta guía es el camino hacia una casa a la que se llega por `https` en todas partes, con una autoridad propia que el teléfono recuerda, para que la app pueda algún día rechazar `http`.

## El perfil por defecto

El perfil `tls` de este repositorio pone Caddy delante de Studio y del servidor. Su valor por defecto es el seguro: la **autoridad local propia** de Caddy (`tls internal`), un certificado para `ARMOR_TLS_HOST`, HSTS de cinco minutos, solo `https`. Nada de esto necesita internet. Para un nombre de internet pon un correo en `ARMOR_TLS_ISSUER` y Caddy pide el certificado a Let's Encrypt (véase `REMOTE_ACCESS_spa.md`): entonces el teléfono se fía del certificado por sí solo y no hay nada que emparejar.

## Los pasos

1. **Nombre.** Elige el nombre con el que los teléfonos llegan a la casa (el nombre de DNS dinámico desde fuera, o un nombre de la red local) y ponlo en `ARMOR_TLS_HOST` (`ARMOR_TLS_PORT=443` si el router reenvía el 443).
2. **Arráncalo.** `docker compose --profile tls up -d` (o Caddy del paquete con el mismo `Caddyfile`). El servidor funciona con `ARMOR_TRUST_PROXY=1` y `ARMOR_PUBLIC_ORIGIN=https://<nombre>`.
3. **Compruébalo.** `scripts/armor_tls_check.sh <nombre> 443 <root.crt>` dice si el servidor responde, si la cadena es válida para el nombre, si quedan más de 14 días y qué clave fijaría un teléfono, e imprime la línea `armor-pin:<nombre>:<pin>`. El certificado raíz es `pki/authorities/local/root.crt` en los datos de Caddy (el asistente de mantenimiento lo encuentra; `ARMOR_TLS_CA_FILE` lo nombra si está en otro sitio).
4. **Empareja cada teléfono.** En Studio, Configuración > Seguridad > acceso desde fuera > *Emparejar el teléfono con el HTTPS de la casa*: escribe el nombre, pulsa el botón y copia el texto. En la app, Más > Seguridad, pégalo. La app aceptará entonces solo esa autoridad para la casa; una clave distinta se rechaza y se dice.
5. **Prueba todo** en cada teléfono, con la wifi de casa y con datos móviles: inicio de sesión, cámaras, armado, alarmas, push.
6. **Solo entonces** el dueño puede prohibir `http` sin cifrar en la app (`cleartext=false`) en una compilación nueva. Mientras no estén emparejados y probados todos los teléfonos, déjalo como está.

## Qué conviene saber

* El pin es el SHA-256 de la clave **pública** de la autoridad: no es un secreto, pero quien se lo da a un teléfono decide en quién confía, así que solo se muestra a los administradores y conviene compararlo con lo que muestra la app.
* Caddy renueva solo el certificado de la casa. La autoridad dura unos diez años; si se sustituye (una carpeta de datos nueva de Caddy) el pin cambia y hay que emparejar de nuevo.
* La clave de la autoridad no sale de la máquina y A.R.M.O.R. nunca la lee.
* Un teléfono emparejado que encuentra una clave distinta se niega a conectar: es lo que se busca. Para emparejarlo otra vez, olvida el pin en la app (Más > Seguridad) y pega el texto nuevo.

## La prueba en la máquina (para el dueño)

`scripts/armor_tls_check.sh` pasa en la CM5; el texto de emparejado es el mismo en Studio y en la salida del script; un teléfono emparejado con la wifi de casa también conecta con datos móviles; tras `systemctl restart caddy` (o el contenedor) no hay que emparejar de nuevo.
