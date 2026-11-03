# Automatic security updates of the machine

The maintenance helper (`armor_maintenance_agent.py`, installed with `--with-maintenance`) keeps the operating system of the machine safe with `unattended-upgrades`, limited to the **security source** of the distribution: no ordinary updates, no point releases, no kernel clean-up. It is **on by default** and every part of it is a setting in Studio (Configuration > Updates > Automatic security updates).

## What it does

* Writes `/etc/apt/apt.conf.d/52armor-security-updates` from the settings, and never lets the package reboot the machine: `Automatic-Reboot` is always `false`. The helper decides about the reboot.
* Keeps a record of what was applied (read from the log of `unattended-upgrades`; Studio shows the last runs).
* After each run it checks that every installed A.R.M.O.R. service is active; one that is not is restarted once, and Studio shows what was down. Nothing is done silently: the journal of the helper carries a warning.

## The reboot

Some updates ask for a reboot. The setting "When an update needs a reboot" has two values: **Never by itself** (Studio says that a reboot is waiting and you reboot when it suits) and **By itself, only inside the window and when nothing is armed** (the default, window 03:00-05:00 local time). In the second case the helper reboots only if all of this is true: the window has begun, no other operation is running, and the server answers that neither the system nor any alarm panel is armed. If the server does not answer, it counts as armed and the machine waits. Studio shows why it has not rebooted yet.

## Risks

A reboot you did not ask for takes the server, the broker and Studio down for a minute or two: an alarm system that is armed does not report in that time (the panels keep protecting the house on their own, but nobody is told). That is why the default never reboots while anything is armed, and why "Never by itself" exists. A security update can also, rarely, break a service: the check after each run restarts it and shows it, but a person should look.

## How to turn it off

In Studio: switch off "Install security updates automatically". On the machine, if Studio cannot be reached: set `"enabled": false` in `$PREFIX/data/maintenance/auto_security_updates.json` (inside `"settings"`) and restart `armor-maintenance`; the helper then writes `APT::Periodic::Unattended-Upgrade "0"`. Removing only the apt file is not enough: the helper writes it again when it starts.

## Tests

`scripts/test_maintenance_agent.py` covers the security-only configuration, the validation of the settings, the window across midnight, the log of what was applied, the check of the services, and every reason not to reboot (armed, unknown, outside the window, policy, busy). Nothing in it touches a real machine.
