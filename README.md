# WoTQuartermaster

A work-in-progress, portable Windows second-monitor companion for World of Tanks PC. The initial goal is to recommend tank progression, spending, upgrades, crew/equipment and map positions according to the player's chosen playstyle.

## Current development baseline

- Connector 0.0.8: live garage, catalogue, battle results and battle context (map/team/vehicle), exported locally.
- Replay importer 0.0.7: local replay import, deduplication and reconciliation.
- Desktop application 0.1.0: verified initial Windows alpha. Version 0.2.0 adds component updating and is built through GitHub Actions.

The Connector has been tested in World of Tanks EU 2.4.2.0; compatibility with other client builds is not guaranteed. Battle context was verified on two battles on the same map and team. These are development components, not a finished advisor.

## Desktop alpha

See the [releases page](https://github.com/itsr0b0tninja/WoTQuartermaster/releases) for the Windows executable. Place `WoTQuartermaster.exe` in the portable project folder beside your existing `data/` directory, or select that directory in Settings. Keep the tested Connector 0.0.8 installed; the desktop app does not modify the game. Open the app on a second monitor and start World of Tanks. The app displays garage resources, detects live battle context and selects the extracted minimap automatically. The map atlas can also be browsed manually. Settings, SQLite cache and logs are stored locally; the one-file executable uses temporary runtime extraction. No Python installation is required.

The recommendation engines and automatic replay imports are not yet implemented. The desktop alpha is for testing the foundation, not a complete advisor.

## Integrated updater (0.2.0)

Once the 0.2.0 alpha is available on the releases page, close the desktop app and replace only `WoTQuartermaster.exe`. Preserve your data folder and settings.ini. Open Updates to check the GitHub component manifest. Downloads are verified by size and SHA-256, and desktop installation requires confirmation and the game to be closed. A separate local helper backs up the previous executable, replaces it and restarts the application; startup confirmation is used for rollback. The real self-update cycle will be tested with 0.2.1.

The Connector is prepared with an INI for the saved data path under `components/connector/`; copy the prepared files into the indicated mods version directory yourself with the game closed. The replay importer can be downloaded independently but is not executed automatically. The tactics component is not available yet. The current desktop accepts the tested Connector 0.0.8 only. No game or account data is uploaded.

## Connector installation (development build)

The [compiled Connector v0.0.8 pre-release](https://github.com/itsr0b0tninja/WoTQuartermaster/releases/tag/connector-v0.0.8) includes the mod, an editable INI and a SHA-256 checksum. No Python installation is required to use the compiled mod. Edit the INI to point to your existing absolute data directory, close the game and copy both files into the active mods version folder.

For developers who wish to build locally, download both TXT files from [connector/](connector/) into the same directory, preferably the WoTQuartermaster base folder. Run using CPython 2.7.18:

```bat
C:\Python27\python.exe Build_WoT_Connector_v0.0.8.txt
```

The helper creates `wot_companion_connector.wotmod`, a `data` directory and, if absent, `connector.ini`. If using an existing data directory, edit the INI in a text editor to point to that existing absolute path. See [connector.ini.example](connector/connector.ini.example). The directory must exist.

With the game closed, copy the .wotmod and connector.ini to the active version's `mods/<game-version>/` directory (for example `mods/2.4.2.0/`). Replace the previous Connector, not other mods. Keep your personal data and INI local. Start the game and verify the Connector writes to `data/connector/`.

Compiled development releases are built through GitHub Actions from the tested source. The CI-produced binary has passed archive checks but has not yet been tested in-game.

## Replay importer

Python 3.12+; standard library only. Download the TXT file from [replay/](replay/) and use explicit paths:

```bat
py -3.12 WoT_Quartermaster_Replay_Parser_v0.0.7.txt --replays "C:\Games\World_of_Tanks_EU\replays" --data "D:\WoTQuartermaster\data"
```

Change the example paths for your installation. Add `--watch` for continuous local scanning. Enable battle replay recording in the game if you want to import new replays. The importer writes local history and does not require a Wargaming login.

## Project boundaries

The first release is a second-monitor advisor, not a statistics dashboard. The Connector is intended to collect local data, not control the game. Tactical guidance is intended to use static map information, not hidden enemy data. Advanced analytics and in-game advice are deferred. Follow the game's current mod rules.

No personal garage data, account identifiers, replays, exported game catalogue or game assets are included in this repository. Keep generated data out of Git. This is an independent project, not affiliated with Wargaming.
