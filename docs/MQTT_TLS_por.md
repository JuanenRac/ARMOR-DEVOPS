# Cifrar a ligação ao broker (MQTT sobre TLS) - opcional, passo a passo

Idiomas: [English](MQTT_TLS.md) · [Español](MQTT_TLS_spa.md) · [Deutsch](MQTT_TLS_deu.md) · [Français](MQTT_TLS_fra.md) · [Italiano](MQTT_TLS_ita.md) · [日本語](MQTT_TLS_jpn.md) · [中文](MQTT_TLS_zho.md)

**Está desativado.** Hoje os nós falam MQTT sem cifra com o broker na rede da casa (porta `18883`), e nada muda se não seguir este guia. Ativá-lo acrescenta uma **segunda porta** (`8883`, TLS) ao lado da normal; a normal fica até decidir retirá-la.

O certificado não vem da Internet: a instalação cria **a sua própria autoridade de certificação** na máquina que executa o broker. Um nó (ou o servidor) a quem se diz para usar `mqtts://` confia **apenas nessa autoridade** e verifica que o certificado do broker foi feito para o nome ou o endereço a que se ligou. Tudo o resto - outra autoridade, um certificado para outro endereço - é recusado.

## 1. Na máquina que executa o broker

```bash
scripts/armor_mqtt_tls.sh plan --name casa.local --ip 192.168.0.180      # o que faria; não altera nada
sudo scripts/armor_mqtt_tls.sh setup --name casa.local --ip 192.168.0.180
sudo scripts/armor_mqtt_tls.sh status
```

* O certificado garante os nomes e endereços da máquina (o seu nome de anfitrião, `localhost`, `127.0.0.1`, os seus endereços IPv4) mais cada `--name` e `--ip` indicado. **Um nó liga-se a um deles** (`mqtts://192.168.0.180:8883`): indique o endereço que os nós vão usar.
* A **chave privada da autoridade** é criada na máquina e fica em `etc/mqtt-ca` (pasta `0700`, chave `0600`, só root). Nunca está num repositório, nunca junto ao broker e nunca sai da máquina. O broker recebe apenas a sua própria chave.
* O `setup` reinicia o broker (um novo listener exige reinício): os nós voltam a ligar-se em poucos segundos. A porta sem cifra não é tocada.
* Executar o `setup` outra vez não altera nada do que ainda está bom. Cria um **novo certificado do broker com a mesma autoridade** quando os endereços mudam ou faltam menos de 30 dias (o certificado do broker dura dois anos). Como a autoridade é a mesma, **não é preciso mexer nos nós**. A autoridade dura dez anos.
* Se a firewall do anfitrião deste repositório for usada, ela só conhece a porta sem cifra: permita manualmente `8883/tcp` a partir da rede de campo.

## 2. Em cada nó

Abra o painel do nó, página **Broker**:

1. Escreva o endereço como `mqtts://192.168.0.180:8883` (tem de ser um dos que o certificado garante).
2. Assinale **Cifrar a ligação ao broker (TLS)**.
3. Cole o certificado da autoridade na caixa. Obtenha-o com `sudo scripts/armor_mqtt_tls.sh export-ca` (é público: um único bloco de `-----BEGIN CERTIFICATE-----` a `-----END CERTIFICATE-----`, cerca de 600 bytes; no máximo 2 KB). O que não for um único certificado em PEM é recusado.
4. Guarde e reinicie.

A conta do nó no broker (utilizador e palavra-passe) não muda. Com a cifra ativada, o nó espera ter a hora antes de se ligar (até dois minutos), porque um certificado tem datas. Os brokers de reserva guardados também têm de ser `mqtts://` enquanto o interruptor estiver ativo, e são verificados com a mesma autoridade. **Desativado** (predefinição), o nó comporta-se exatamente como antes.

## 3. O servidor desta máquina

```bash
sudo scripts/armor_mqtt_tls.sh server-tls on      # ARMOR_MQTT_URL=mqtts://localhost:8883 e ARMOR_MQTT_CA_FILE no ficheiro de ambiente
sudo systemctl restart armor-server
```

À mão: `ARMOR_MQTT_URL=mqtts://localhost:8883` e `ARMOR_MQTT_CA_FILE=/caminho/para/ca.pem`. O servidor recusa-se a arrancar se o ficheiro não for um certificado válido, ou se `ARMOR_MQTT_CA_FILE` estiver definido com um endereço `mqtt://` (a ligação continuaria sem cifra enquanto acredita no contrário). O Studio mostra o estado em **Configuração > Broker**: se a ligação está cifrada e a impressão digital da autoridade, para comparar com `sudo scripts/armor_mqtt_tls.sh status`. `server-tls off` volta à porta sem cifra.

## 4. Desativá-lo

Desassinale o interruptor em cada nó (e ponha de volta o endereço `mqtt://`), execute `server-tls off` e depois `sudo scripts/armor_mqtt_tls.sh remove`. Não se apaga nada: os ficheiros do broker e a configuração são postos de parte junto aos antigos, e a autoridade é mantida (`--forget-ca` põe-na também de parte) para que um `setup` posterior mantenha os nós que já confiam nela.

## O que faz e o que não faz

* Cifra e autentica o broker perante os nós e o servidor. **Não** pede aos nós um certificado próprio: continuam a identificar-se com a sua conta.
* Protege a rede da casa de quem escuta ou finge ser o broker. Não é motivo para publicar o broker: a `8883` nunca é redirecionada para a Internet (ver `REMOTE_ACCESS.md`).
* Verificado com OpenSSL e com o Mosquitto 2.0 num computador (o certificado, o segundo listener, o handshake, a fixação de uma só autoridade, a recusa de outra autoridade e de outro endereço, e a ligação do servidor). **Ainda não verificado na placa de um nó**: o handshake custa algum tempo e memória num microcontrolador.
