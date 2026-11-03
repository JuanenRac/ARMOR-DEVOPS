# Paquetes firmados: cómo decide la máquina qué instala

El ayudante de mantenimiento de la máquina (`armor_maintenance_agent.py`) actualiza los programas de A.R.M.O.R. (`server`, `studio`, `network`, `ai`, `voice`, `devops`) desde las releases de sus repositorios en GitHub. Antes de desempaquetar nada comprueba tres cosas, en este orden:

1. **El hash:** el paquete debe dar el SHA-256 que indica `armor-<componente>-<versión>.tgz.sha256`. Así se detecta una descarga cortada.
2. **La firma:** `armor-<componente>-<versión>.tgz.sig2` contiene la firma Ed25519 (64 bytes como 128 dígitos hexadecimales) del manifiesto

   `armor-fw/1|<componente>|package|<versión>|<sha256>`

   hecha con la clave privada de las releases, la misma que firma el firmware de los nodos: es el mismo manifiesto que el de las imágenes de firmware, con `package` donde va la placa. El ayudante la verifica con la clave pública que lleva en su código (`PACKAGE_PUBLIC_KEY`) y, mientras se cambia la clave, con una segunda (ver abajo). Una release sin `.sig2`, o con una que no verifica, se rechaza (`missing_signature`, `bad_signature`) y el sistema queda como estaba: no se desempaqueta nada, no se reinicia nada.
3. **El archivo:** sin nombres absolutos, sin `..`, sin enlaces ni dispositivos.

Quien solo pueda cambiar lo que contiene una release en GitHub (una cuenta robada, una dependencia maliciosa de las herramientas de publicación) puede publicar un paquete y su hash, pero no su firma: la clave privada nunca está en GitHub. El manifiesto liga la firma al componente y a la versión, así que un paquete firmado del pasado o de otro componente no puede presentarse como el más nuevo, y la firma de una imagen de firmware (otro proyecto, una placa real) nunca pasa por firma de paquete. La `.sig` antigua (texto `armor-pkg/1|<componente>|<versión>|<sha256>`) ya no basta: solo se acepta si el `armor.maint.env` de la máquina dice `ARMOR_MAINT_SIGNATURE=either`, el tiempo que lleve firmar los paquetes publicados antes.

La comprobación es Python puro (RFC 8032): no necesita OpenSSL ni ningún módulo adicional en la máquina.

## Publicar

```
python scripts/package_component.py server --repo ../ARMOR-SERVER --sign --publish
```

Escribe `.tgz`, `.sha256`, `.sig2` (el manifiesto) y `.sig` (el texto antiguo, que un ayudante aún sin actualizar sigue comprobando) y los sube. El firmador es `~/.armor/sign.mjs` (o `--signer` / `ARMOR_PACKAGE_SIGNER`); lee la clave de `ARMOR_FIRMWARE_KEY` o de `~/.armor/firmware_ed25519.pem`. La clave no se copia nunca a un repositorio. `--sign` falla si no hay firmador o clave; sin él, el paquete se firma cuando están. Una clave distinta de la que el ayudante acepta no se usa nunca. `--publish` se niega a subir un paquete sin firma.

Para firmar un paquete ya publicado, descárgalo junto a su `.sha256` y ejecuta:

```
python scripts/package_component.py --sign-existing armor-server-0.5.7.tgz --upload
```

El nombre indica el componente y la versión; `--upload` añade la `.sig2` y la `.sig` a la release `v<versión>` de su repositorio (necesita `gh`).

## Excepción de emergencia

Si hay que instalar un paquete sin firma (por ejemplo, con la clave perdida), escribe esta línea en el `armor.maint.env` de la máquina (en `$PREFIX/etc/`) y quítala después:

```
ARMOR_MAINT_ALLOW_UNSIGNED=1
```

Se lee de ese archivo cada vez que se instala algo, así que no se puede activar por la API HTTP ni por el entorno del proceso. El ayudante escribe un `WARNING` en el registro del trabajo y en el suyo cada vez que se usa, y el resumen indica `unsigned_allowed`.

## Ajustes de la máquina

Dos ajustes sobre la firma, que se leen de `armor.maint.env` cada vez que se instala algo (nunca de la API HTTP ni del entorno del proceso):

```
ARMOR_MAINT_SIGNATURE=manifest
ARMOR_MAINT_NEXT_KEY=
```

`ARMOR_MAINT_SIGNATURE` es `manifest` (por defecto: solo cuenta la `.sig2`) o `either` (cuenta también la `.sig` antigua). `ARMOR_MAINT_NEXT_KEY` está vacía o es la segunda clave pública, 64 dígitos hexadecimales, en la que se confía además de la incorporada durante una rotación; nunca se confía en más de dos claves. El resumen del ayudante muestra `signature_mode` y `trusted_fingerprints` (los 16 primeros dígitos del SHA-256 de cada clave, nunca las claves), para que quien cuida la máquina vea en qué claves confía. Un cambio aquí cambia cómo decide la máquina qué instala: se hace en la máquina, como root, igual que la excepción de emergencia.

## Cambiar la clave

Crea un par nuevo. Primero escribe la clave pública nueva como `ARMOR_MAINT_NEXT_KEY` en el `armor.maint.env` de cada máquina (o publica un paquete `devops`, firmado con la clave **antigua**, cuya `PACKAGE_PUBLIC_KEY` sea la nueva). Desde entonces firma los paquetes con la clave nueva: las máquinas confían en las dos mientras esa línea esté. Cuando todas tengan la clave nueva incorporada, quita la línea. El firmware de los nodos confía en una sola clave (`fw_trust.hpp`): cámbiala como dice la página del firmware firmado.

## Pruebas

`scripts/test_maintenance_agent.py` cubre una firma de manifiesto válida, que liga el componente, la versión y el hash, que una firma de firmware, el texto antiguo y el hash suelto no pasan por manifiesto, un paquete manipulado, un `.sig2` ausente, una firma de otra clave, basura, la `.sig` antigua sola (rechazada, aceptada solo con `either`), las dos claves de una rotación (y que una tercera nunca es de confianza), la excepción (solo desde el archivo), el vector de prueba de la RFC 8032 y que la clave del ayudante es la de `fw_trust.hpp`. Usan claves desechables, nunca la real.

El empaquetador se niega a empaquetar una compilación obsoleta: para `server` y `studio`, la versión de `package.json` (y, en Studio, la de `dist/version.json`) debe ser la de `armor.project.json`, y `dist/` no puede ser más antiguo que el código fuente con el que se compiló. Compila de nuevo (`npm run build`) antes.
