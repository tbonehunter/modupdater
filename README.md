# SMAPI Mod Updater

A cross-platform GUI tool that streamlines updating [Stardew Valley](https://www.stardewvalley.net/) mods from [Nexus Mods](https://www.nexusmods.com/stardewvalley). Parses SMAPI's update log, opens download pages, and automatically installs downloaded updates into your Mods folder.

## The Problem

SMAPI tells you which mods have updates available, but actually updating them means manually visiting each mod page on Nexus, downloading the file, extracting it, and copying it into the right folder — for every single mod. With 20+ mods, this is tedious and error-prone.

## What This Tool Does

1. **Parses SMAPI's log** to find which mods need updating
2. **Opens all the Nexus download pages** in your browser (Files tab, ready to click "Download")
3. **Watches your Downloads folder** for new mod archives arriving
4. **Matches each download** to the correct mod by reading `manifest.json` inside the zip
5. **Backs up the old version** before installing (single previous version, stored in `Mods/.backups/`)
6. **Extracts the new version** into the correct folder, preserving your existing folder structure

You still click "Slow Download" on each Nexus page (Nexus Premium not required), but everything else is automated.

## Features

- **Cross-platform** — works on Windows, macOS, and Linux
- **Auto-detects** your Stardew Valley installation, SMAPI log, Mods folder, and Downloads folder
- **Multiple game instances** — switch between different Stardew installs via a dropdown
- **Multi-mod archives** — handles zips containing multiple mod folders (e.g., a SMAPI mod + Content Patcher pack)
- **Existing download scan** — finds matching mods already in your Downloads folder so you don't re-download
- **Version verification** — only installs the expected version, skips old downloads sitting in your folder
- **Comment-tolerant manifest parsing** — handles SMAPI-style `/* */` and `//` comments in manifest.json
- **One-click backup** — automatically backs up the previous version before installing
- **Session log** — records what was done for easy troubleshooting

## Requirements

- Python 3.8+
- [SMAPI](https://smapi.io/) installed and run at least once (so the log file exists)

## Installation

### Clone and Run (simplest)

```bash
git clone https://github.com/tbonehunter/modupdater.git
cd modupdater/smapi_mod_updater
pip install -r requirements.txt
python main.py
```

### Install as Package

```bash
git clone https://github.com/tbonehunter/modupdater.git
cd modupdater
pip install .
smapi-mod-updater
```

## Usage

1. **Launch the game with SMAPI** at least once so it generates an update log
2. **Run the updater** — it auto-detects your setup and shows which mods need updating
3. **Uncheck any mods** you want to skip (all are selected by default)
4. **Click "Open Download Pages"** — your browser opens the Nexus Files tab for each mod
5. **Click "Slow Download" on each page** in your browser
6. **Click "Watch & Install"** — the tool monitors your Downloads folder and installs each mod as it arrives

If you've already downloaded some mods, just click "Watch & Install" directly — it scans existing files in your Downloads folder first.

## Configuration

On first run, the tool creates `smapi_updater_config.json` next to the script with auto-detected paths. Use the **Settings** button to:

- Override the SMAPI log file location
- Override the Downloads folder
- Add game instances that weren't auto-detected

The **Game** dropdown at the top switches between multiple Stardew Valley installations. The **Reload** button re-reads the SMAPI log for the current instance.

## How It Works

The tool reads SMAPI's `SMAPI-latest.txt` log file, which contains lines like:

```
[SMAPI] You can update 3 mods:
[SMAPI]    Automate 2.6.1: https://www.nexusmods.com/stardewvalley/mods/1063 (you have 2.6.0)
```

When a zip file appears in Downloads, the tool opens it, reads `manifest.json` to identify the mod (via `UpdateKeys` and `UniqueID`), verifies the version matches, backs up the existing mod folder, and extracts the new version in its place.

For multi-mod archives (like StonerValley which contains both a SMAPI mod and a Content Patcher pack), the tool finds and extracts all sub-mods, matching each to its correct existing folder by `UniqueID`.

## Project Structure

```
smapi_mod_updater/
├── main.py              # Entry point
├── gui.py               # CustomTkinter GUI
├── log_parser.py        # SMAPI log parsing
├── browser_launcher.py  # Opens Nexus download pages
├── download_watcher.py  # Watches Downloads folder, matches and installs
├── backup_manager.py    # Backup, extract, and restore logic
├── config_manager.py    # Config auto-detect, load, save
├── platform_utils.py    # OS-specific path detection
├── session_logger.py    # Per-session log file
└── requirements.txt     # Python dependencies
```

## Known Limitations

- **Nexus free tier only** — you must click "Slow Download" manually on each mod page. Nexus Premium API downloads are not supported.
- **Zip archives only** — `.rar` and `.7z` are not currently supported (most Stardew mods use zip).
- **SMAPI log must be current** — run SMAPI at least once after your last update session so the log reflects what still needs updating.

## License

MIT

## Credits

Built by [Nortek LLC](https://nortekllc.com). Developed collaboratively with Claude (Anthropic).
