# WoTQuartermaster

A work-in-progress, portable Windows second-monitor companion for World of Tanks PC. The initial goal is to recommend tank progression, spending, upgrades, crew/equipment and map positions according to the player's chosen playstyle.

## Current development baseline

- Connector 0.0.8: live garage, catalogue, battle results and battle context (map/team/vehicle), exported locally.
- Replay importer 0.0.7: local replay import, deduplication and reconciliation.
- Desktop application: not yet released.

The Connector has been tested in World of Tanks EU 2.4.2.0; compatibility with other client builds is not guaranteed. Battle context was verified on two battles on the same map and team. These are development components, not a finished advisor.

## Connector installation (development build)

A precompiled mod is not yet published. To build locally, download both TXT files from [connector/](connector/) into the same directory, preferably the WoTQuartermaster base folder. Run using CPython 2.7.18:

```bat
C:\Python27\python.exe Build_WoT_Connector_v0.0.8.txt
```

The helper creates `wot_companion_connector.wotmod`, a `data` directory and, if absent, `connector.ini`. If using an existing data directory, edit the INI in a text editor to point to that existing absolute path. See [connector.ini.example](connector/connector.ini.example). The directory must exist.

With the game closed, copy the .wotmod and connector.ini to the active version's `mods/<game-version>/` directory (for example `mods/2.4.2.0/`). Replace the previous Connector, not other mods. Keep your personal data and INI local. Start the game and verify the Connector writes to `data/connector/`.

A compiled distribution is planned so normal users will not need Python 2.7.

## Replay importer

Python 3.12+; standard library only. Download the TXT file from [replay/](replay/) and use explicit paths:

```bat
py -3.12 WoT_Quartermaster_Replay_Parser_v0.0.7.txt --replays "C:\Games\World_of_Tanks_EU\replays" --data "D:\WoTQuartermaster\data"
```

Change the example paths for your installation. Add `--watch` for continuous local scanning. Enable battle replay recording in the game if you want to import new replays. The importer writes local history and does not require a Wargaming login.

## Project boundaries

The first release is a second-monitor advisor, not a statistics dashboard. The Connector is intended to collect local data, not control the game. Tactical guidance is intended to use static map information, not hidden enemy data. Advanced analytics and in-game advice are deferred. Follow the game's current mod rules.

No personal garage data, account identifiers, replays, exported game catalogue or game assets are included in this repository. Keep generated data out of Git. This is an independent project, not affiliated with Wargaming.
