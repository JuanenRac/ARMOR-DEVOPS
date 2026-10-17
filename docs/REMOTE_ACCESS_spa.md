# Usar A.R.M.O.R. desde fuera de casa - paso a paso

La regla: **una sola puerta** y **un nombre, nunca una dirección**. El broker MQTT y los nodos no se publican nunca en Internet.

## 1. Elige la puerta

* **A. Una VPN (recomendado)**: WireGuard o Tailscale en la máquina que ejecuta el servidor. Desde fuera el móvil entra en la VPN y todo funciona como en casa (también el panel de cada nodo). Si tu operador no te da una dirección pública propia (CGNAT), Tailscale funciona sin abrir nada.
* **B. HTTPS**: un proxy inverso con certificado real (el perfil `tls` de este repositorio) en un puerto del router. Cómodo desde cualquier navegador; pon la política «operate» para que administrar quede para la casa o la VPN.

## 2. Un nombre que siga a tu dirección

Tu dirección pública es fija o cambia de vez en cuando. En ambos casos usa un **nombre** (DuckDNS, No-IP, el DNS dinámico del router o un dominio propio) y algo que lo actualice cuando la dirección cambie (el cliente del router, o `ddclient`/el script de DuckDNS en la máquina). Pon un TTL corto (60 a 300 s). El móvil, Studio y la VPN usan siempre el nombre.

## 3. En el router

Reenvía **un** puerto a la máquina del servidor: `443/TCP` para B (y `80/TCP` si el certificado es real, para su comprobación), o `51820/UDP` para WireGuard en A. Nunca `1883`, `8883` ni el puerto de un nodo.

## 4. En el servidor (Docker)

En `.env`:

```
ARMOR_TLS_HOST=casa.duckdns.org          # tu nombre
ARMOR_TLS_ISSUER=tu@correo.com           # pide el certificado a Let's Encrypt y lo renueva
ARMOR_TLS_PORT=443
ARMOR_TLS_HTTP_PORT=80
ARMOR_TLS_BIND=0.0.0.0
ARMOR_PUBLIC_ORIGIN=https://casa.duckdns.org
ARMOR_TRUST_PROXY=uniquelocal            # así el servidor ve la dirección real de cada visitante
ARMOR_TOTP_REQUIRED=remote               # segundo factor desde fuera (configúralo antes desde dentro)
ARMOR_REMOTE_POLICY=operate              # desde fuera: mirar y manejar la alarma; administrar solo desde casa o la VPN
```

y `docker compose --profile tls up -d`. En el banco CM5 los mismos ajustes están en `armor.network.env` (Studio > Configuración > Seguridad los escribe por ti).

## 5. En Studio

Configuración > Seguridad: activa el segundo factor (aplicación autenticadora) en cada cuenta, guarda los códigos de recuperación y mira las sesiones abiertas. Como administrador, indica el proxy de confianza, las redes que cuentan como la casa, la política y la duración de las sesiones desde fuera.

## 6. La VPN, el nombre y los paneles de los nodos, desde Studio (sin comandos)

Con el agente de mantenimiento instalado (`install_cm5.sh --with-maintenance`) y WireGuard en la máquina (`sudo apt install wireguard-tools qrencode`), un administrador lo hace todo en Studio > Configuración > Seguridad > Acceso desde fuera de casa:

1. **VPN:** escribe el nombre o dirección que usará el móvil (por ejemplo `casa.duckdns.org`), deja el puerto y la red de la casa y pulsa *Configurar la VPN*. Te dice qué puerto UDP redirigir en el router a la máquina.
2. **Un móvil o un portátil:** en *Añadir un dispositivo* ponle un nombre (`movil-ana`), pulsa *Crear* y escanea el código QR con la app WireGuard. El código lleva una clave privada: ciérralo después y no se lo des a nadie. Puedes mostrarlo otra vez o quitar el dispositivo más adelante.
3. **Un nombre que sigue a tu casa:** elige DuckDNS, Cloudflare o una dirección a la que llamar, escribe sus datos y pulsa *Guardar y comprobar ahora*. La máquina lo comprueba cada cinco minutos y llama al proveedor solo cuando la dirección cambió.
4. **El panel de un nodo desde fuera:** registra el nodo (su id y su dirección dentro de casa). Si el nodo usa HTTPS pulsa *Ver su certificado*, compara la huella con la del propio panel del nodo (Acerca de) y pulsa *Confiar en este certificado*. Después *Abrir panel* funciona desde fuera, a través del servidor, y el nodo nunca se publica.

Lo mismo se puede hacer desde un terminal con `armor_wireguard.sh` y `armor_ddns.sh` (la cabecera de cada uno lista sus órdenes; `plan` muestra lo que se escribiría antes de escribir nada).


## 7. En el móvil

A.R.M.O.R. Control: escribe el nombre como servidor (`https://casa.duckdns.org`), entra (el código de la aplicación se pide como segundo paso) y revisa Más > Seguridad.

## 8. Compruébalo

Desde el móvil **con datos móviles**, en Studio o en la app, pulsa «Comprobar cómo me ve el servidor»: debe decir **desde fuera** y mostrar tu dirección real. Si dice «desde casa», el proxy no pasa la dirección: arregla `ARMOR_TRUST_PROXY` antes de fiarte de nada.

## Nunca

Reenvíes el puerto del broker, el de un nodo, ni «solo un momento»; uses la dirección en vez del nombre; dejes las contraseñas por defecto; ni te saltes el segundo factor en un administrador que entra desde fuera.
