# Cifrar el enlace con el broker (MQTT sobre TLS) - opcional, paso a paso

Idiomas: [English](MQTT_TLS.md) · [Deutsch](MQTT_TLS_deu.md) · [Français](MQTT_TLS_fra.md) · [Italiano](MQTT_TLS_ita.md) · [日本語](MQTT_TLS_jpn.md) · [中文](MQTT_TLS_zho.md) · [Português](MQTT_TLS_por.md)

**Está desactivado.** Hoy los nodos hablan MQTT sin cifrar con el broker dentro de la red de la casa (puerto `18883`), y nada cambia si no sigues esta guía. Activarlo añade una **segunda puerta** (`8883`, TLS) junto a la normal; la normal sigue ahí hasta que decidas quitarla.

El certificado no viene de Internet: la instalación crea **su propia autoridad de certificación** en la máquina que ejecuta el broker. Un nodo (o el servidor) al que se le dice que use `mqtts://` confía **solo en esa autoridad** y comprueba que el certificado del broker se hizo para el nombre o la dirección a la que se conectó. Cualquier otra cosa - otra autoridad, un certificado para otra dirección - se rechaza.

## 1. En la máquina que ejecuta el broker

```bash
scripts/armor_mqtt_tls.sh plan --name casa.local --ip 192.168.0.180      # lo que haría; no cambia nada
sudo scripts/armor_mqtt_tls.sh setup --name casa.local --ip 192.168.0.180
sudo scripts/armor_mqtt_tls.sh status
```

* El certificado responde por los nombres y direcciones de la máquina (su nombre de equipo, `localhost`, `127.0.0.1`, sus direcciones IPv4) más cada `--name` y `--ip` que indiques. **Un nodo se conecta a una de ellas** (`mqtts://192.168.0.180:8883`): indica la dirección que usarán los nodos.
* La **clave privada de la autoridad** se crea en la máquina y se queda en `etc/mqtt-ca` (carpeta `0700`, clave `0600`, solo root). Nunca está en un repositorio, nunca junto al broker y nunca sale de la máquina. El broker recibe únicamente su propia clave.
* `setup` reinicia el broker (un listener nuevo necesita reinicio): los nodos se reconectan en unos segundos. El puerto sin cifrar no se toca.
* Ejecutar `setup` otra vez no cambia nada que siga siendo válido. Crea un **certificado de broker nuevo con la misma autoridad** cuando cambian las direcciones o quedan menos de 30 días (el certificado del broker dura dos años). Como la autoridad es la misma, **no hay que tocar los nodos**. La autoridad dura diez años.
* Si usas el cortafuegos de este repositorio, solo conoce el puerto sin cifrar: permite tú mismo `8883/tcp` desde la red de campo.

## 2. En cada nodo

Abre el panel del nodo, página **Broker**:

1. Escribe la dirección como `mqtts://192.168.0.180:8883` (debe ser una de las que el certificado respalda).
2. Marca **Cifrar el enlace con el broker (TLS)**.
3. Pega el certificado de la autoridad en la caja. Obtenlo con `sudo scripts/armor_mqtt_tls.sh export-ca` (es público: un único bloque de `-----BEGIN CERTIFICATE-----` a `-----END CERTIFICATE-----`, unos 600 bytes; 2 KB como máximo). Lo que no sea un único certificado en PEM se rechaza.
4. Guarda y reinicia.

La cuenta del nodo en el broker (usuario y contraseña) no cambia. Con el cifrado activado, el nodo espera a tener la hora antes de conectar (hasta dos minutos), porque un certificado tiene fechas. Los brokers de respaldo guardados también deben ser `mqtts://` mientras el interruptor esté activado, y se comprueban con la misma autoridad. **Desactivado** (por defecto), el nodo se comporta exactamente como antes.

## 3. El servidor de esta máquina

```bash
sudo scripts/armor_mqtt_tls.sh server-tls on      # ARMOR_MQTT_URL=mqtts://localhost:8883 y ARMOR_MQTT_CA_FILE en el fichero de entorno
sudo systemctl restart armor-server
```

A mano: `ARMOR_MQTT_URL=mqtts://localhost:8883` y `ARMOR_MQTT_CA_FILE=/ruta/a/ca.pem`. El servidor se niega a arrancar si el fichero no es un certificado válido, o si `ARMOR_MQTT_CA_FILE` está definido con una dirección `mqtt://` (el enlace seguiría sin cifrar mientras crees lo contrario). Studio muestra el estado en **Configuración > Broker**: si el enlace está cifrado y la huella de la autoridad, para compararla con `sudo scripts/armor_mqtt_tls.sh status`. `server-tls off` vuelve al puerto sin cifrar.

## 4. Desactivarlo

Desmarca el interruptor en cada nodo (y devuelve la dirección `mqtt://`), ejecuta `server-tls off` y luego `sudo scripts/armor_mqtt_tls.sh remove`. No se borra nada: los ficheros del broker y la configuración se apartan junto a los antiguos, y la autoridad se conserva (`--forget-ca` la aparta también) para que un `setup` posterior mantenga a los nodos que ya confían en ella.

## Qué hace y qué no hace

* Cifra y autentica al broker ante los nodos y el servidor. **No** pide a los nodos un certificado propio: siguen identificándose con su cuenta.
* Protege la red de la casa frente a quien escuche o se haga pasar por el broker. No es una razón para publicar el broker: `8883` nunca se reenvía a Internet (ver `REMOTE_ACCESS.md`).
* Comprobado con OpenSSL y con Mosquitto 2.0 en un ordenador (el certificado, el segundo listener, el handshake, el anclaje de una sola autoridad, el rechazo de otra autoridad y de otra dirección, y la conexión del servidor). **Aún no comprobado en la placa de un nodo**: el handshake cuesta algo de tiempo y memoria en un microcontrolador.
