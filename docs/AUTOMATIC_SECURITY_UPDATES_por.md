# Atualizações de segurança automáticas da máquina

O auxiliar de manutenção (`armor_maintenance_agent.py`, instalado com `--with-maintenance`) mantém seguro o sistema operativo da máquina com o `unattended-upgrades`, limitado à **fonte de segurança** da distribuição: sem atualizações normais, sem versões intermédias, sem limpeza de kernels. Está **ativado por predefinição** e cada parte é uma definição do Studio (Configuração > Atualizações > Atualizações de segurança automáticas).

## O que faz

* Escreve `/etc/apt/apt.conf.d/52armor-security-updates` a partir das definições e nunca deixa o pacote reiniciar a máquina: `Automatic-Reboot` é sempre `false`. O reinício é decidido pelo auxiliar.
* Guarda um registo do que foi aplicado (lido do log do `unattended-upgrades`; o Studio mostra as últimas execuções).
* Depois de cada execução verifica que cada serviço instalado do A.R.M.O.R. está ativo; um que não esteja é reiniciado uma vez e o Studio mostra o que estava em baixo. Nada é feito em silêncio: o diário do auxiliar leva um aviso.

## O reinício

Algumas atualizações pedem um reinício. A definição «Quando uma atualização precisa de reiniciar» tem dois valores: **Nunca sozinha** (o Studio avisa de que há um reinício pendente e reinicia quando convier) e **Sozinha, só dentro da janela e quando nada estiver armado** (predefinição, janela 03:00-05:00 hora local). No segundo caso o auxiliar só reinicia se tudo isto se verificar: a janela começou, não há outra operação em curso e o servidor responde que nem o sistema nem nenhuma central de alarme está armada. Se o servidor não responder, conta como armado e a máquina espera. O Studio mostra porque ainda não reiniciou.

## Riscos

Um reinício que não pediu deixa sem servidor, broker e Studio um ou dois minutos: um sistema de alarme armado não comunica nada nesse tempo (as centrais continuam a proteger a casa sozinhas, mas ninguém é avisado). Por isso a predefinição nunca reinicia enquanto algo estiver armado, e por isso existe «Nunca sozinha». Uma atualização de segurança também pode, raramente, estragar um serviço: a verificação depois de cada execução reinicia-o e mostra-o, mas uma pessoa deve ver.

## Como desativar

No Studio: desligue «Instalar automaticamente as atualizações de segurança». Na máquina, se não chegar ao Studio: ponha `"enabled": false` em `$PREFIX/data/maintenance/auto_security_updates.json` (dentro de `"settings"`) e reinicie o `armor-maintenance`; o auxiliar escreve então `APT::Periodic::Unattended-Upgrade "0"`. Retirar só o ficheiro do apt não basta: o auxiliar volta a escrevê-lo ao arrancar.

## Testes

O `scripts/test_maintenance_agent.py` cobre a configuração só de segurança, a validação das definições, a janela que passa a meia-noite, o registo do que foi aplicado, a verificação dos serviços e cada motivo para não reiniciar (armado, desconhecido, fora da janela, política, ocupado). Nada disso toca numa máquina real.
