<p align="center">
  <img src="images/ARMOR_BANNER.svg" alt="ARMOR-DEVOPS banner" width="100%">
</p>

# 🚀 ARMOR-DEVOPS

<p align="center">
  <a href="README.md">🇺🇸 English</a> |
  <a href="README_spa.md">🇪🇸 Español</a> |
  <a href="README_fra.md">🇫🇷 Français</a> |
  <a href="README_ita.md">🇮🇹 Italiano</a> |
  <a href="README_deu.md">🇩🇪 Deutsch</a> |
  <a href="README_zho.md">🇨🇳 简体中文</a> |
  <a href="README_jpn.md">🇯🇵 日本語</a> |
  🇵🇹 <b>Português</b>
</p>

### Implementação, a bancada de testes do CM5, as suas atualizações a partir do GitHub e a manutenção da instalação

<p align="center">
  <img src="https://img.shields.io/badge/License-GPL%203.0-blue.svg" alt="GPL 3.0">
  <img src="https://img.shields.io/badge/Deploy-Docker%20Compose-2496ed.svg" alt="Deploy">
  <img src="https://img.shields.io/badge/Bench-systemd-FFB020.svg" alt="Bench">
  <img src="https://img.shields.io/badge/Version-0.6.3-0f6cbd.svg" alt="Version">
  <img src="https://img.shields.io/badge/Maturity-established-2EA44F.svg" alt="Maturity">
</p>

---

**Verificação de honestidade - o que funciona hoje:** O instalador da bancada do CM5 foi executado num CM5 real que aloja outro software, que se manteve saudável, e a bancada corre em uso diário com o servidor, o Studio, o nó de rede, os serviços de observação e de voz, o broker e os dois assistentes abaixo; nela foram feitas atualizações dos seus componentes a partir do GitHub (através do Studio). A topologia Docker Compose e o seu perfil TLS opcional foram construídos e executados a sério com o Docker Engine no WSL (`scripts/test_compose.sh`), mas **não no Jetson**. Os scripts de cópia de segurança e restauro têm um teste de ida e volta que passa, e os dois assistentes têm os seus próprios testes. O que **não** está provado: uma instalação limpa numa máquina que nunca viu o projeto e toda a topologia Docker no seu destino.

---

## 📋 Num relance

| | |
|---|---|
| Versão | `0.6.3` |
| Maturidade | Estabelecido |
| Tecnologia | Docker Compose / Bash / YAML |
| Em hardware real | Faz correr a bancada de testes do CM5 em uso diário, num CM5 real que aloja outro software; ainda não no Jetson |

## 🎯 Visão geral

* **Bancada de testes do CM5:** `scripts/deploy_cm5.sh` compila numa cópia limpa, envia um arquivo e executa `scripts/install_cm5.sh`, que cria o seu próprio utilizador, o seu próprio diretório e unidades systemd em portas próprias para o servidor e o Studio e, com opções, o broker MQTT, o nó de rede, o serviço de observação, a porta de ligação de voz, o agente de administração, o assistente de manutenção e a cópia de segurança diária. Nunca toca no que mais a máquina executa.
* **O assistente de manutenção** (`armor_maintenance_agent.py`): as atualizações dos componentes da própria instalação a partir do GitHub (descarrega o pacote da versão, verifica o seu SHA-256 e troca-o com reversão), as do sistema operativo e uma consola root opcional, tudo comandado a partir do separador *Atualizações* do Studio; a consola está desligada salvo se for ativada.
* **O agente de administração** (`armor_admin_agent.py`): a única parte com privilégios, com uma lista fechada de serviços, ficheiros de definições e contas do broker, de modo que o Studio nunca precisa de root.
* **Pacotes de cada versão:** `scripts/package_component.py` constrói o pacote de um componente (Studio, servidor, rede, serviço de observação, porta de ligação de voz, DevOps), escreve o seu SHA-256 ao lado e publica-o como versão do GitHub.
* **Topologia Compose:** um broker Mosquitto não anónimo com uma identidade por nó e uma ACL (incluindo os nós de alarme e as zonas Zigbee que o servidor lhes diz), o servidor e o Studio atrás de um nginx que faz proxy de `/api/`; só o Studio é publicado, em loopback. Contentores reforçados, imagens fixadas, uma rede interna do núcleo e volumes com nome para o estado.
* **TLS:** um perfil `tls` opcional do Compose põe o Caddy, com a sua própria autoridade certificadora local, à frente do Studio, e é fornecida uma configuração do Mosquitto sobre TLS ([detalhes](docs/BACKUP_AND_TLS.md)).
* **Uma firewall de anfitrião para a máquina central** (`scripts/firewall_core.sh`): a porta do broker só a partir da rede de campo, as do servidor e do Studio só a partir da rede dos clientes (quando indicada), numa tabela própria que não menciona mais nada.
* **Segredos:** `scripts/generate_secrets.sh` cria segredos aleatórios e não imprime nenhum; `scripts/check-required-env.sh` recusa valores em falta, de exemplo, curtos ou repetidos.
* **Cópia de segurança e restauro:** `scripts/backup_data.sh` faz um arquivo cifrado com AES-256, verificado e com soma de verificação dos dados do servidor (sem provas salvo se pedidas); `scripts/restore_data.sh` lista-o ou restaura-o sem nunca sobrescrever dados existentes.
* **Uma VPN e um nome para a casa, configurados a partir do Studio:** `armor_wireguard.sh` monta uma VPN WireGuard com poucos comandos (chaves na máquina, uma configuração por telemóvel com código QR, encaminhamento para os nós se quiser) e `armor_ddns.sh` mantém um nome DuckDNS, Cloudflare ou outro a apontar para a casa quando o operador muda o endereço; o agente de manutenção oferece ambos ao Studio e ao telemóvel, por isso ninguém tem de escrever um comando, e um guia passo a passo em oito idiomas cobre o router.**Pacotes assinados:** o assistente de manutenção só instala um pacote do servidor, do Studio ou de qualquer outro programa se levar uma assinatura Ed25519 válida da chave de releases do projeto (verificada em Python puro, sem software adicional); uma assinatura em falta, errada ou adulterada deixa a máquina como estava. Existe uma exceção de emergência apenas como definição no ficheiro da própria máquina.
* **Uma porta cifrada opcional para o broker (MQTT sobre TLS):** `scripts/armor_mqtt_tls.sh` cria uma autoridade de certificação para a instalação (a chave fica na máquina, modo `0600`), um certificado do broker para os nomes e endereços da máquina e um segundo listener do Mosquitto na 8883 ao lado do normal, que nunca toca; é idempotente e tem `status`, `export-ca`, `server-tls` e `remove` (os ficheiros são postos de parte, nunca apagados). Testado com OpenSSL, com handshakes reais, e num Mosquitto 2.0 real ([guia](docs/MQTT_TLS_por.md)).
* **Relatórios de saúde permitidos:** as regras do broker deixam cada nó escrever o seu `armor/health/<nó>` e o servidor ler `armor/health/#`; `mqtt_identity.sh add` escreve a linha para cada tipo de nó e `mqtt_identity.sh health-report <papel> <nó>` acrescenta-a a um nó instalado antes (idempotente, as regras anteriores ficam guardadas).

## 🧩 Papel no A.R.M.O.R.

O ARMOR-DEVOPS é como tudo o resto chega a uma máquina e se mantém atualizado. Instala o servidor, o Studio, o nó de rede, os serviços de observação e de voz e o broker na bancada de testes do CM5, faz os pacotes de cada versão que o separador *Atualizações* do [ARMOR-STUDIO](https://github.com/JuanenRac/ARMOR-STUDIO) instala a partir do GitHub, e guarda os dois pequenos assistentes que deixam o Studio atualizar a instalação e gerir os seus serviços sem nunca correr como root.

## 📂 Estrutura do repositório

```text
ARMOR-DEVOPS/
├── docker-compose.yml, docker-compose.tls.yml, .env.example, mosquitto/ (broker, TLS profile, ACL example)
├── caddy/     Caddyfile (TLS)
├── scripts/   deploy_cm5, install_cm5, package_component, armor_admin_agent, armor_maintenance_agent, generate_secrets, check-required-env, backup_data, restore_data, firewall_core, mqtt_identity, armor_mqtt_tls (the optional encrypted door of the broker), tests of the agents, the backup, the firewall and the Compose topology
│   └── (package_component.py packs a program the way the maintenance helper installs it; the packages are assets of the GitHub releases, not files of this repository)
└── docs/      DEPLOYMENT_BOUNDARY, CM5_TEST_BENCH, BACKUP_AND_TLS, MQTT_TLS
```

## 🛠️ Ambiente de desenvolvimento

**Requisitos:** Docker Engine with Compose (for the container topology), a CM5 or any Debian-based machine reachable by SSH (for the test bench), Bash, `ssh` and `tar` on the machine that deploys

```bash
scripts/generate_secrets.sh          # .env and secrets/ (Git-ignored)
scripts/check-required-env.sh
docker compose config --quiet && docker compose up --build
scripts/deploy_cm5.sh --host <cm5> --user <user> --key <key> --apply   # the test bench
scripts/backup_data.sh --data-dir <data> --out-dir <backups> --passphrase-file <file>
```

Veja a [fronteira de implementação](docs/DEPLOYMENT_BOUNDARY.md).

## 🔗 Projetos relacionados

O **A.R.M.O.R.** (Autonomous Radar & Multimodal Observation Range) é um sistema de segurança perimetral feito de repositórios independentes. Cada um tem a sua própria versão, os seus próprios testes e o seu próprio README; esta é a família:

* **[ARMOR-COMMON](https://github.com/JuanenRac/ARMOR-COMMON)** - Contratos de mensagens, validadores, vetores de conformidade e tipos gerados
* **[ARMOR-RADAR](https://github.com/JuanenRac/ARMOR-RADAR)** - Firmware de nó de campo para ESP32-S3 com três radares e o seu próprio painel web
* **[ARMOR-SOLAR](https://github.com/JuanenRac/ARMOR-SOLAR)** - Protocolos de inversores e baterias solares e as mensagens de um nó de ligação
* **[ARMOR-ELECTRICAL](https://github.com/JuanenRac/ARMOR-ELECTRICAL)** - Nó elétrico: contadores, a mensagem das leituras da rede e as regras de comutação
* **[ARMOR-ALARM](https://github.com/JuanenRac/ARMOR-ALARM)** - Nó e central de alarme: zonas, armar, atrasos, sirene e PIN, com o servidor ou sem ele
* **[ARMOR-HMI](https://github.com/JuanenRac/ARMOR-HMI)** - Painel tátil: o estado do sistema num ecrã de parede, armar e reconhecer, e a casa do assistente de voz
* **[ARMOR-NETWORK](https://github.com/JuanenRac/ARMOR-NETWORK)** - A rede local: os seus dispositivos, a internet e o que muda
* **[ARMOR-SERVER](https://github.com/JuanenRac/ARMOR-SERVER)** - Coordenador central: telemetria, alarmes, dispositivos, leituras solares e câmaras
* **[ARMOR-STUDIO](https://github.com/JuanenRac/ARMOR-STUDIO)** - Consola web: câmaras, radar, alarmes, energia solar e o desenhador de local 2D/3D
* **[ARMOR-ANDROID-CONTROL](https://github.com/JuanenRac/ARMOR-ANDROID-CONTROL)** - Cliente Android de operador com um radar 2D/3D em direto
* **[ARMOR-SERVER-AI](https://github.com/JuanenRac/ARMOR-SERVER-AI)** - Política de inferência visual que explica as suas decisões e nunca atua
* **[ARMOR-VISION](https://github.com/JuanenRac/ARMOR-VISION)** - Zonas de câmara, máscaras e regras de deteção para o Jetson Orin NX
* **[ARMOR-VOICE-AI](https://github.com/JuanenRac/ARMOR-VOICE-AI)** - Intenções de voz offline com uma confirmação que não se pode falsificar
* **[ARMOR-HARDWARE](https://github.com/JuanenRac/ARMOR-HARDWARE)** - Caixas, eletrónica e a matriz de aceitação de bancada
* **ARMOR-DEVOPS** (este repositório) - Implementação, a bancada de testes CM5, cópias de segurança e TLS
* **[ARMOR-SIMULATOR](https://github.com/JuanenRac/ARMOR-SIMULATOR)** - Simulador de telemetria offline com falhas repetíveis
* **[ARMOR-UPDATER](https://github.com/JuanenRac/ARMOR-UPDATER)** - Deteta, instala e atualiza os próprios repositórios do ecossistema
* **[ARMOR-DOCS](https://github.com/JuanenRac/ARMOR-DOCS)** - Arquitetura, linha de base de segurança e a matriz de capacidades

## 📚 Documentação e comunidade

Onde ler mais:

* [Matriz de capacidades: o que está provado e o que não](https://github.com/JuanenRac/ARMOR-DOCS/blob/main/docs/CAPABILITY_MATRIX.md)
* [Catálogo de projetos: versões e como os repositórios dependem uns dos outros](https://github.com/JuanenRac/ARMOR-DOCS/blob/main/docs/PROJECT_CATALOG.md)
* [Registo de alterações deste repositório](CHANGELOG.md)
* [Licença (GPL-3.0-or-later)](LICENSE)
* Perguntas, ideias e relatórios: electrohobby3d@gmail.com

## 👤 AUTOR

**JuanenRac (Electro Hobby 3D)** · electrohobby3d@gmail.com

## 📜 LICENÇA

GPL-3.0-or-later - veja [LICENSE](LICENSE).
