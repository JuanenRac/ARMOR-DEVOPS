# Automatische Sicherheitsupdates der Maschine

Der Wartungshelfer (`armor_maintenance_agent.py`, installiert mit `--with-maintenance`) hält das Betriebssystem der Maschine mit `unattended-upgrades` sicher, beschränkt auf die **Sicherheitsquelle** der Distribution: keine gewöhnlichen Updates, keine Zwischenversionen, kein Aufräumen von Kernels. Er ist **standardmäßig an**, und jeder Teil ist eine Einstellung in Studio (Konfiguration > Updates > Automatische Sicherheitsupdates).

## Was er tut

* Schreibt `/etc/apt/apt.conf.d/52armor-security-updates` aus den Einstellungen und lässt das Paket die Maschine nie neu starten: `Automatic-Reboot` ist immer `false`. Über den Neustart entscheidet der Helfer.
* Führt Buch über das Angewendete (aus dem Log von `unattended-upgrades`; Studio zeigt die letzten Läufe).
* Prüft nach jedem Lauf, dass jeder installierte A.R.M.O.R.-Dienst aktiv ist; ein inaktiver wird einmal neu gestartet, und Studio zeigt, was ausgefallen war. Nichts geschieht stillschweigend: Das Journal des Helfers enthält eine Warnung.

## Der Neustart

Manche Updates verlangen einen Neustart. Die Einstellung „Wenn ein Update einen Neustart braucht“ hat zwei Werte: **Nie von selbst** (Studio meldet, dass ein Neustart aussteht, und Sie starten bei Gelegenheit neu) und **Von selbst, nur im Zeitfenster und wenn nichts scharf ist** (Standard, Fenster 03:00-05:00 Ortszeit). Im zweiten Fall startet der Helfer nur neu, wenn alles zutrifft: Das Fenster hat begonnen, kein anderer Vorgang läuft, und der Server antwortet, dass weder das System noch eine Alarmzentrale scharf ist. Antwortet der Server nicht, gilt es als scharf, und die Maschine wartet. Studio zeigt, warum noch nicht neu gestartet wurde.

## Risiken

Ein Neustart, den Sie nicht angefordert haben, legt Server, Broker und Studio ein bis zwei Minuten lahm: Eine scharfe Alarmanlage meldet in dieser Zeit nichts (die Zentralen schützen das Haus allein weiter, aber niemand erfährt davon). Deshalb startet der Standard nie neu, solange etwas scharf ist, und deshalb gibt es „Nie von selbst“. Ein Sicherheitsupdate kann selten auch einen Dienst beschädigen: Die Prüfung nach jedem Lauf startet ihn neu und zeigt es, aber eine Person sollte nachsehen.

## So schalten Sie es aus

In Studio: „Sicherheitsupdates automatisch installieren“ ausschalten. Auf der Maschine, wenn Studio nicht erreichbar ist: `"enabled": false` in `$PREFIX/data/maintenance/auto_security_updates.json` setzen (unter `"settings"`) und `armor-maintenance` neu starten; der Helfer schreibt dann `APT::Periodic::Unattended-Upgrade "0"`. Nur die apt-Datei zu entfernen genügt nicht: Der Helfer schreibt sie beim Start neu.

## Tests

`scripts/test_maintenance_agent.py` deckt die reine Sicherheitskonfiguration, die Prüfung der Einstellungen, das Zeitfenster über Mitternacht, das Protokoll des Angewendeten, die Prüfung der Dienste und jeden Grund, nicht neu zu starten (scharf, unbekannt, außerhalb des Fensters, Richtlinie, beschäftigt). Nichts davon berührt eine echte Maschine.
