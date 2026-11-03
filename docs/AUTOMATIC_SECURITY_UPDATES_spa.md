# Actualizaciones automáticas de seguridad de la máquina

El ayudante de mantenimiento (`armor_maintenance_agent.py`, instalado con `--with-maintenance`) mantiene seguro el sistema operativo de la máquina con `unattended-upgrades`, limitado a la **fuente de seguridad** de la distribución: sin actualizaciones ordinarias, sin versiones puntuales, sin limpieza de kernels. Está **activado por defecto** y cada parte es un ajuste en Studio (Configuración > Actualizaciones > Actualizaciones automáticas de seguridad).

## Qué hace

* Escribe `/etc/apt/apt.conf.d/52armor-security-updates` a partir de los ajustes y nunca deja que el paquete reinicie la máquina: `Automatic-Reboot` es siempre `false`. El ayudante decide el reinicio.
* Guarda un registro de lo aplicado (leído del log de `unattended-upgrades`; Studio muestra las últimas ejecuciones).
* Tras cada ejecución comprueba que cada servicio instalado de A.R.M.O.R. está activo; uno que no lo esté se reinicia una vez y Studio muestra lo que estaba caído. Nada se hace en silencio: el diario del ayudante lleva un aviso.

## El reinicio

Algunas actualizaciones piden reiniciar. El ajuste «Cuando una actualización necesita reiniciar» tiene dos valores: **Nunca sola** (Studio avisa de que hay un reinicio pendiente y reinicias cuando convenga) y **Sola, solo dentro de la ventana y cuando nada esté armado** (por defecto, ventana 03:00-05:00 hora local). En el segundo caso el ayudante reinicia solo si se cumple todo esto: la ventana ha empezado, no hay otra operación en marcha y el servidor responde que ni el sistema ni ninguna central de alarma está armada. Si el servidor no responde, cuenta como armado y la máquina espera. Studio muestra por qué aún no ha reiniciado.

## Riesgos

Un reinicio que no pediste deja sin servidor, broker ni Studio uno o dos minutos: un sistema de alarma armado no informa en ese tiempo (las centrales siguen protegiendo la casa por su cuenta, pero nadie se entera). Por eso el valor por defecto nunca reinicia mientras algo esté armado, y por eso existe «Nunca sola». Una actualización de seguridad también puede, rara vez, romper un servicio: la comprobación tras cada ejecución lo reinicia y lo muestra, pero una persona debe mirarlo.

## Cómo desactivarlo

En Studio: apaga «Instalar las actualizaciones de seguridad automáticamente». En la máquina, si no se llega a Studio: pon `"enabled": false` en `$PREFIX/data/maintenance/auto_security_updates.json` (dentro de `"settings"`) y reinicia `armor-maintenance`; el ayudante escribe entonces `APT::Periodic::Unattended-Upgrade "0"`. Quitar solo el archivo de apt no basta: el ayudante lo vuelve a escribir al arrancar.

## Pruebas

`scripts/test_maintenance_agent.py` cubre la configuración solo de seguridad, la validación de los ajustes, la ventana que cruza la medianoche, el registro de lo aplicado, la comprobación de los servicios y cada motivo para no reiniciar (armado, desconocido, fuera de ventana, política, ocupado). Nada de eso toca una máquina real.
