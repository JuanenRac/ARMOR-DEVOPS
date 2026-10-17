# Paquetes firmados: cómo decide la máquina qué instala

El ayudante de mantenimiento de la máquina (`armor_maintenance_agent.py`) actualiza los programas de A.R.M.O.R. (`server`, `studio`, `network`, `ai`, `voice`, `devops`) desde las releases de sus repositorios en GitHub. Antes de desempaquetar nada comprueba tres cosas, en este orden:

1. **El hash:** el paquete debe dar el SHA-256 que indica `armor-<componente>-<versión>.tgz.sha256`. Así se detecta una descarga cortada.
2. **La firma:** `armor-<componente>-<versión>.tgz.sig` contiene la firma Ed25519 (64 bytes como 128 dígitos hexadecimales) del texto

   `armor-pkg/1|<componente>|<versión>|<sha256>`

   hecha con la clave privada de las releases. El ayudante la verifica con la clave pública que lleva en su código (`PACKAGE_PUBLIC_KEY`), la misma en la que confía el firmware de los nodos. Una release sin `.sig`, o con una que no verifica, se rechaza (`missing_signature`, `bad_signature`) y el sistema queda como estaba: no se desempaqueta ni se reinicia nada.
3. **El archivo:** sin nombres absolutos, sin `..`, sin enlaces ni dispositivos.

Quien solo pueda cambiar lo que contiene una release en GitHub (una cuenta robada, una dependencia maliciosa de las herramientas de publicación) puede publicar un paquete y su hash, pero no su firma: la clave privada nunca está en GitHub. El texto empieza por `armor-pkg/1`, no por el `armor-fw/1` del firmware, así que una firma de firmware nunca puede pasar por firma de paquete; y lleva el componente y la versión, así que un paquete firmado no puede hacerse pasar por otro programa ni por una versión más nueva.

La comprobación es Python puro (RFC 8032): no necesita OpenSSL ni ningún módulo adicional en la máquina.

## Publicar

```
python scripts/package_component.py server --repo ../ARMOR-SERVER --sign --publish
```

Escribe `.tgz`, `.sha256` y `.sig` y sube los tres. El firmador es `~/.armor/sign.mjs` (o `--signer` / `ARMOR_PACKAGE_SIGNER`); lee la clave de `ARMOR_FIRMWARE_KEY` o de `~/.armor/firmware_ed25519.pem`. La clave no se copia nunca a un repositorio. `--sign` falla si no hay firmador o clave; sin él, el paquete se firma cuando están. Nunca se usa una clave distinta de la que el ayudante acepta. `--publish` se niega a subir un paquete sin firma.

Para firmar un paquete ya publicado, descárgalo junto a su `.sha256` y ejecuta:

```
python scripts/package_component.py --sign-existing armor-server-0.5.7.tgz --upload
```

El nombre indica el componente y la versión; `--upload` añade la `.sig` a la release `v<versión>` de su repositorio (necesita `gh`).

## Excepción de emergencia

Si hay que instalar un paquete sin firma (por ejemplo, con la clave perdida), escribe esta línea en el `armor.maint.env` de la máquina (en `$PREFIX/etc/`) y quítala después:

```
ARMOR_MAINT_ALLOW_UNSIGNED=1
```

Se lee de ese archivo cada vez que se instala algo, así que no se puede activar por la API HTTP ni por el entorno del proceso. El ayudante escribe un `WARNING` en el registro del trabajo y en el suyo cada vez que se usa, y el resumen indica `unsigned_allowed`.

## Cambiar la clave

Crea un par nuevo y pon la clave pública nueva en `PACKAGE_PUBLIC_KEY` y en el firmware (`fw_trust.hpp`). Publica un paquete `devops` firmado con la clave **antigua** (las máquinas lo instalan y desde entonces confían en la nueva) y firma los siguientes con la nueva.

## Pruebas

`scripts/test_maintenance_agent.py` cubre una firma válida, un paquete manipulado, un `.sig` ausente, una firma de otra clave, basura, la excepción (solo desde el archivo), el vector de prueba de la RFC 8032 y que la clave del ayudante es la de `fw_trust.hpp`. Usan claves desechables, nunca la real.
