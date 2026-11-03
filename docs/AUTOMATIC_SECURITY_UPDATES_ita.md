# Aggiornamenti di sicurezza automatici della macchina

L'assistente di manutenzione (`armor_maintenance_agent.py`, installato con `--with-maintenance`) mantiene sicuro il sistema operativo della macchina con `unattended-upgrades`, limitato alla **fonte di sicurezza** della distribuzione: niente aggiornamenti ordinari, niente versioni intermedie, niente pulizia dei kernel. È **attivo per impostazione predefinita** e ogni parte è un'impostazione di Studio (Configurazione > Aggiornamenti > Aggiornamenti di sicurezza automatici).

## Cosa fa

* Scrive `/etc/apt/apt.conf.d/52armor-security-updates` dalle impostazioni e non lascia mai che il pacchetto riavvii la macchina: `Automatic-Reboot` è sempre `false`. Il riavvio lo decide l'assistente.
* Tiene un registro di ciò che è stato applicato (letto dal log di `unattended-upgrades`; Studio mostra le ultime esecuzioni).
* Dopo ogni esecuzione verifica che ogni servizio A.R.M.O.R. installato sia attivo; uno fermo viene riavviato una volta e Studio mostra cosa era giù. Nulla avviene in silenzio: il giornale dell'assistente riporta un avviso.

## Il riavvio

Alcuni aggiornamenti chiedono il riavvio. L'impostazione «Quando un aggiornamento richiede il riavvio» ha due valori: **Mai da sola** (Studio segnala che un riavvio è in attesa e riavvii tu quando conviene) e **Da sola, solo nella finestra e quando nulla è armato** (predefinito, finestra 03:00-05:00 ora locale). Nel secondo caso l'assistente riavvia solo se è vero tutto questo: la finestra è iniziata, nessun'altra operazione è in corso e il server risponde che né il sistema né alcuna centrale d'allarme è armata. Se il server non risponde, conta come armato e la macchina aspetta. Studio mostra perché non ha ancora riavviato.

## Rischi

Un riavvio non richiesto lascia senza server, broker e Studio per uno o due minuti: un sistema d'allarme armato non segnala nulla in quel tempo (le centrali proteggono la casa da sole, ma nessuno lo sa). Per questo il valore predefinito non riavvia mai finché qualcosa è armato, e per questo esiste «Mai da sola». Un aggiornamento di sicurezza può anche, raramente, rompere un servizio: il controllo dopo ogni esecuzione lo riavvia e lo mostra, ma una persona deve guardare.

## Come disattivarlo

In Studio: spegni «Installa automaticamente gli aggiornamenti di sicurezza». Sulla macchina, se Studio non è raggiungibile: imposta `"enabled": false` in `$PREFIX/data/maintenance/auto_security_updates.json` (dentro `"settings"`) e riavvia `armor-maintenance`; l'assistente scrive allora `APT::Periodic::Unattended-Upgrade "0"`. Togliere solo il file di apt non basta: l'assistente lo riscrive all'avvio.

## Test

`scripts/test_maintenance_agent.py` copre la configurazione di sola sicurezza, la validazione delle impostazioni, la finestra che attraversa la mezzanotte, il registro di ciò che è stato applicato, il controllo dei servizi e ogni motivo per non riavviare (armato, sconosciuto, fuori finestra, criterio, occupato). Nulla tocca una macchina reale.
