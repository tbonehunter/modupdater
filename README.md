# SMAPI Mod Updater

A cross-platform GUI tool that streamlines updating [Stardew Valley](https://www.stardewvalley.net/) mods from [Nexus Mods](https://www.nexusmods.com/stardewvalley). Parses SMAPI's update log, opens download pages, and automatically installs downloaded updates into your Mods folder — preserving your subfolder organization.

## The Problem

SMAPI tells you which mods have updates available, but actually updating them means manually visiting each mod page on Nexus, downloading the file, extracting it, and copying it into the right folder — for every single mod. With 20+ mods, this is tedious and error-prone. And if you organize your mods into subfolders, you have to move them back into place after every update.

## What This Tool Does

1. **Parses SMAPI's log** to find which mods need updating
2. **Opens all the Nexus download pages** in your browser (Files tab, ready to click "Download")
3. **Watches your Downloads folder** for new mod archives arriving
4. **Matches each download** to the correct mod by reading `manifest.json` inside the zip
5. **Backs up the old version** before installing (single previous version, stored in `Mods/.backups/`)
6. **Extracts the new version** into the correct folder, preserving your existing folder structure and subfolder organization

You still click "Slow Download" on each Nexus page (Nexus Premium not required), but everything else is automated.

## Features

- **Cross-platform** — works on Windows, macOS, and Linux
- **Subfolder preservation** — if you organize mods into subfolders (e.g., `Mods/Pathoschild/Automate/`), updates are installed back into the same location at any nesting depth
- **Auto-detects** your Stardew Valley installation, SMAPI log, Mods folder, and Downloads folder
- **Multiple game instances** — switch between different Stardew installs via a dropdown
- **Multi-mod archives** — handles zips containing multiple mod folders (e.g., a SMAPI mod + Content Patcher pack)
- **Existing download scan** — finds matching mods already in your Downloads folder so you don't re-download
- **Version verification** — only installs the expected version, skips old downloads sitting in your folder
- **Comment-tolerant manifest parsing** — handles SMAPI-style `/* */` and `//` comments in manifest.json
- **One-click backup** — automatically backs up the previous version before installing
- **Smart page opening** — "Open Download Pages" skips mods already installed in the current session
- **Session log** — records what was done for easy troubleshooting

## Requirements

- **SMAPI** — installed and run at least once so the log file exists. Get it from [smapi.io](https://smapi.io/).

For the **Windows download** (Option A below), that's all you need — no Python required.

For **Mac/Linux** or if you prefer running from source (Options B and C), you also need **Python 3.8 or newer** — download from [python.org](https://www.python.org/downloads/). During installation on Windows, **check "Add Python to PATH"**.

## Installation and Launch

### Option A: Windows Executable (recommended for Windows)

The simplest option — no Python installation required.

**Step 1:** Download the latest zip from the [Nexus Mods page](https://www.nexusmods.com/stardewvalley/mods/43712) or the [GitHub Releases page](https://github.com/tbonehunter/modupdater/releases).

**Step 2:** Extract the zip to a convenient location (e.g., your Desktop or a Stardew modding folder).

**Step 3:** Double-click `SMAPIModUpdater.exe` to launch.

That's it. To run it again in the future, just double-click the exe.

### Option B: Clone and Run (Mac/Linux, or Windows from source)

**Step 1:** Download the code.

If you have Git installed:
```bash
git clone https://github.com/tbonehunter/modupdater.git
```

Or download the ZIP from the [GitHub repo page](https://github.com/tbonehunter/modupdater) (green "Code" button → "Download ZIP") and extract it somewhere convenient.

**Step 2:** Open a terminal and navigate into the `smapi_mod_updater` folder:

```bash
cd modupdater/smapi_mod_updater
```

If you downloaded the ZIP and extracted it, the path will depend on where you put it. For example on Windows:

```
cd C:\Users\YourName\Downloads\modupdater-main\smapi_mod_updater
```

**Step 3:** Install the required Python libraries (one-time setup):

```bash
pip install -r requirements.txt
```

If `pip` isn't recognized, try `pip3` or `python -m pip` instead.

**Step 4:** Launch the updater:

```bash
python main.py
```

That's it — the GUI window will appear. Each time you want to run the updater in the future, just repeat Step 2 and Step 4.

### Option C: Install as a Python Package

This installs the tool as a system command so you can run it from anywhere.

```bash
git clone https://github.com/tbonehunter/modupdater.git
cd modupdater
pip install .
```

Then launch from any terminal with:

```bash
smapi-mod-updater
```

Note: if you see a warning about the Scripts directory not being on PATH, you can either add it to PATH or just use Option B instead.

## Usage

1. **Launch Stardew Valley with SMAPI** at least once so it generates a fresh update log, then close the game
2. **Run the updater** (`python main.py` or double-click the exe) — it auto-detects your setup and shows which mods need updating
3. **Uncheck any mods** you want to skip (all are selected by default)
4. **Click "Open Download Pages"** — your browser opens the Nexus Files tab for each mod
5. **Click "Slow Download" on each Nexus page** in your browser
6. **Click "Watch & Install"** — the tool monitors your Downloads folder and installs each mod as it arrives

If you've already downloaded some mods, just click "Watch & Install" directly — it scans existing files in your Downloads folder first and installs anything that matches.

The "Open Download Pages" button skips mods that have already been installed in the current session, so you can click it again if you need to open pages for the remaining mods.

## Subfolder Organization

Many modders organize their Mods folder into subfolders by author or category:

```
Mods/
├── Pathoschild/
│   ├── Automate/
│   ├── ChestsAnywhere/
│   └── ContentPatcher/
├── CJB/
│   ├── CJBItemSpawner/
│   └── CJBShowItemSellPrice/
├── Utilities/
│   └── SpaceCore/
└── [CP] StonerValley/
```

The updater recursively searches your entire Mods folder to find where each mod is currently installed, then puts the update back in the same location — no matter how deeply nested. A mod at `Mods/Utilities/Frameworks/SpaceCore/` will be updated in place, not dumped at the Mods root.

For new mods that don't have an existing installation, they are installed at the Mods root. You can then move them into your preferred subfolder structure.

## Configuration

On first run, the tool creates `smapi_updater_config.json` with auto-detected paths. Use the **Settings** button to:

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

The mod search is recursive — it walks the entire Mods directory tree to find installed mods by their `UniqueID` (primary) or Nexus mod ID (fallback), recording the full relative path so the update goes back to exactly the same subfolder.

For multi-mod archives (like StonerValley which contains both a SMAPI mod and a Content Patcher pack), the tool finds and extracts all sub-mods, matching each to its correct existing folder by `UniqueID`.

## Project Structure

```
modupdater/                          ← repo root
├── .gitignore
├── pyproject.toml                   # For pip install (optional)
├── README.md
├── build_exe.py                     # Builds the Windows executable
├── SMAPIModUpdater.spec             # PyInstaller build configuration
└── smapi_mod_updater/               ← the actual tool
    ├── __init__.py
    ├── main.py                      # Entry point
    ├── gui.py                       # CustomTkinter GUI
    ├── log_parser.py                # SMAPI log parsing
    ├── browser_launcher.py          # Opens Nexus download pages
    ├── download_watcher.py          # Watches Downloads folder, matches and installs
    ├── backup_manager.py            # Backup, extract, and restore logic
    ├── config_manager.py            # Config auto-detect, load, save
    ├── platform_utils.py            # OS-specific path detection
    ├── session_logger.py            # Per-session log file
    └── requirements.txt             # Python dependencies
```

## Building the Windows Executable

If you want to build the exe yourself (for development or to verify the build):

```bash
pip install pyinstaller
cd modupdater
python build_exe.py
```

This creates `dist/SMAPIModUpdater/` containing the executable, and a zip file ready for Nexus upload. The build script automatically includes a `manifest.json` and the README in the zip.

## Changelog

### v1.1.0
- **Subfolder preservation** — mods organized into subfolders are now updated in place at any nesting depth
- **Recursive mod search** — finds installed mods anywhere in the Mods directory tree
- **Settings persistence fix** — exe version now correctly saves settings between sessions
- **Scrollable settings dialog** — settings window properly displays all fields and buttons
- **Visible buttons** — fixed button transparency issue in settings dialog

### v1.0.0
- Initial release
- SMAPI log parsing with timestamp-aware format handling
- Browser tab opening for Nexus download pages
- Download watching with filesystem events (watchdog) and polling fallback
- Automatic backup and install with version verification
- Multi-mod archive support
- Existing download scan
- Comment-tolerant manifest parsing
- Cross-platform support (Windows exe, Mac/Linux from source)

## Known Limitations

- **Nexus free tier only** — you must click "Slow Download" manually on each mod page. Nexus Premium API downloads are not supported.
- **Zip archives only** — `.rar` and `.7z` are not currently supported (most Stardew mods use zip).
- **SMAPI log must be current** — run SMAPI at least once after your last update session so the log reflects what still needs updating.

## License

MIT

## Credits

Designed by tbonehunter. Developed collaboratively with Claude (Anthropic) writing much of the python script.
