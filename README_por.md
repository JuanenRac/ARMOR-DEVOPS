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
  <a href="README_por.md">🇵🇹 Português</a>
</p>


### Topologia de implementação e a bancada de testes CM5 isolada

<p align="center">
  <img src="https://img.shields.io/badge/License-GPL%203.0-blue.svg" alt="GPL 3.0">
  <img src="https://img.shields.io/badge/Deploy-Docker%20Compose-2496ed.svg" alt="Deploy">
  <img src="https://img.shields.io/badge/Bench-systemd-FFB020.svg" alt="Bench">
  <img src="https://img.shields.io/badge/Maturity-functional-00E5FF.svg" alt="Maturity">
</p>

---

**Verificação de honestidade - o que funciona hoje:** O instalador da bancada CM5 foi executado num CM5 real que aloja outro software, o qual se manteve saudável. A topologia Docker Compose e o seu perfil TLS opcional foram construídos e executados a sério com o Docker Engine no WSL (`scripts/test_compose.sh`, 12 verificações, que encontraram e corrigiram três falhas), mas **não no Jetson**. Os scripts de cópia de segurança e restauro têm um teste de ida e volta aprovado.

---

## 🎯 Visão geral

* **Uma firewall de anfitrião para a máquina central** (`scripts/firewall_core.sh`): a porta do broker só a partir da rede de campo, as portas do servidor e do Studio só a partir da rede dos clientes (quando se indica), numa tabela própria que não menciona mais nada e aceita o resto; `apply --rollback-after` remove as regras de novo a menos que as confirme, para que um erro não o deixe de fora. As regras e as recusas estão testadas (36 verificações, nada se carrega); ainda não foi carregada em nenhuma máquina, e as próprias VLAN continuam a ser um desenho para o router e o comutador.
* **Bancada de testes CM5:** `scripts/deploy_cm5.sh` constrói numa cópia limpa, envia um arquivo e executa `scripts/install_cm5.sh`, que cria o seu próprio utilizador, a sua própria pasta e duas unidades systemd nas suas próprias portas (três com `--with-mqtt`: o Mosquitto próprio do A.R.M.O.R. na porta 18883, verificado num CM5 real), com limites de recursos, e nunca toca noutro projeto ([detalhes](docs/CM5_TEST_BENCH.md)).
* **Topologia Compose:** um broker Mosquitto não anónimo com uma identidade por nó, o servidor, e o Studio atrás de um nginx que faz proxy de `/api/`; só o Studio se publica, no loopback. Contentores reforçados, uma rede interna do núcleo e volumes com nome para o estado.
* **Dispositivos e leituras no broker da bancada:** o servidor pode escutar e comandar `armor/device/#` e ler `armor/node/+/info`, `armor/solar/#` e `armor/electrical/#`; `scripts/mqtt_identity.sh add device NAME` dá a um dispositivo os seus próprios tópicos e `add bridge NAME` a uma ponte Zigbee2MQTT ou Shelly todos eles. `scripts/mqtt_identity.sh electrical-switching NODE_ID on` é a única coisa que deixa o servidor comandar o interruptor de um nó elétrico (desativado por omissão; `off` retira-o).
* **Segredos:** `scripts/generate_secrets.sh` cria segredos aleatórios e não imprime nenhum; `scripts/check-required-env.sh` recusa valores em falta, de exemplo, curtos ou repetidos.
* **Cópia de segurança e restauro:** `scripts/backup_data.sh` faz um arquivo cifrado com AES-256, verificado e com soma de controlo dos dados do servidor (provas excluídas a menos que se peça); `scripts/restore_data.sh` lista-o ou restaura-o sem nunca sobrescrever dados existentes. A chave das câmaras deliberadamente **não** está no arquivo.
* **TLS:** um perfil `tls` opcional do Compose põe o Caddy, com a sua própria autoridade de certificação local, à frente do Studio ([detalhes](docs/BACKUP_AND_TLS.md)).

## 📂 Estrutura do repositório

```text
ARMOR-DEVOPS/
├── docker-compose.yml, .env.example, mosquitto/
├── caddy/     Caddyfile (TLS)
├── scripts/   deploy_cm5, install_cm5, generate_secrets, check-required-env, validate-compose, backup_data, restore_data, test_backup, test_compose, firewall_core, test_firewall, mqtt_identity
└── docs/      DEPLOYMENT_BOUNDARY, CM5_TEST_BENCH, BACKUP_AND_TLS
```

## 🛠️ Ambiente de desenvolvimento

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
* **[ARMOR-HMI](https://github.com/JuanenRac/ARMOR-HMI)** - Painel tátil: o estado do sistema num ecrã de parede, armar e reconhecer, e a casa do assistente de voz
* **[ARMOR-NETWORK](https://github.com/JuanenRac/ARMOR-NETWORK)** - A rede local: os seus dispositivos, a internet e o que muda
* **[ARMOR-SERVER](https://github.com/JuanenRac/ARMOR-SERVER)** - Coordenador central: telemetria, alarmes, dispositivos, leituras solares e câmaras
* **[ARMOR-STUDIO](https://github.com/JuanenRac/ARMOR-STUDIO)** - Consola web: câmaras, radar, alarmes, energia solar e o desenhador de local 2D/3D
* **[ARMOR-ANDROID-CONTROL](https://github.com/JuanenRac/ARMOR-ANDROID-CONTROL)** - Cliente Android de operador com um radar 2D/3D em direto
* **[ARMOR-SERVER-AI](https://github.com/JuanenRac/ARMOR-SERVER-AI)** - Política de inferência visual que explica as suas decisões e nunca atua
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
