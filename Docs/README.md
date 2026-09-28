# SMAPI Mod Updater

A cross-platform tool that streamlines updating [Stardew Valley](https://www.stardewvalley.net/) mods from [Nexus Mods](https://www.nexusmods.com/stardewvalley). Parses SMAPI's update log, opens download pages, and automatically installs downloaded updates into your Mods folder — preserving your subfolder organization. The interface runs as a local web page in your default browser, so there's no platform-specific GUI toolkit to install or for it to break.

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

- **Cross-platform** — works on Windows, macOS, Linux, and Steam Deck, with no native GUI toolkit to break between platforms
- **Subfolder preservation** — if you organize mods into subfolders (e.g., `Mods/Pathoschild/Automate/`), updates are installed back into the same location at any nesting depth
- **Auto-detects** your Stardew Valley installation, SMAPI log, Mods folder, and Downloads folder — including automatic SteamOS/Proton detection for Steam Deck users
- **Reload button** — re-reads the SMAPI log at any time, e.g. after running the game again
- **Multi-mod archives** — handles zips containing multiple mod folders (e.g., a SMAPI mod + Content Patcher pack)
- **Existing download scan** — finds matching mods already in your Downloads folder so you don't re-download
- **Version verification** — only installs the expected version, skips old downloads sitting in your folder
- **Comment-tolerant manifest parsing** — handles SMAPI-style `/* */` and `//` comments in manifest.json
- **One-click backup** — automatically backs up the previous version before installing
- **Configurable backup safety net** — choose what happens if a mod's backup can't be made: skip that mod (default, safest), install anyway without a backup, or get asked each time it happens
- **Smart page opening** — "Open Download Pages" skips mods already installed in the current session, and skips mods that already have a matching archive sitting in your Downloads folder instead of opening another duplicate tab
- **Session log** — records what was done for easy troubleshooting

## Requirements

- **SMAPI** — installed and run at least once so the log file exists. Get it from [smapi.io](https://smapi.io/).

For the **pre-built downloads** (Options A and B below), that's all you need — no Python required.

For **running from source** (Options C and D), you also need **Python 3.8 or newer** — download from [python.org](https://www.python.org/downloads/). During installation on Windows, **check "Add Python to PATH"**.

## Installation and Launch

### Option A: Windows Executable (recommended for Windows)

The simplest option — no Python installation required.

**Step 1:** Download the latest **Windows** zip from the [Nexus Mods page](https://www.nexusmods.com/stardewvalley/mods/43712) or the [GitHub Releases page](https://github.com/tbonehunter/modupdater/releases).

**Step 2:** Extract the zip to a convenient location (e.g., your Desktop or a Stardew modding folder).

**Step 3:** Double-click `SMAPIModUpdater.exe` to launch.

A console window opens alongside your browser — that's normal. The tool starts a small local web server and opens it in your default browser automatically. To stop the updater, click **Quit** in the page, or close the console window. To run it again in the future, just double-click the exe.

### Option B: macOS / Linux Executable (recommended for Mac and Linux)

No Python installation required.

**Step 1:** Download the latest archive for your platform from the [GitHub Releases page](https://github.com/tbonehunter/modupdater/releases):
- **macOS** — `SMAPI Mod Updater x.x.x (macOS).zip`
- **Linux** — `SMAPI Mod Updater x.x.x (Linux).zip`

**Step 2:** Extract the archive:
- **macOS** — double-click the zip in Finder, or: `unzip "SMAPI Mod Updater*.zip"`
- **Linux** — `unzip "SMAPI Mod Updater*.zip"`

**Step 3:** Run the executable:
```bash
cd SMAPIModUpdater
chmod +x SMAPIModUpdater
./SMAPIModUpdater
```

Your terminal stays attached and your default browser opens to the tool automatically. Close the terminal (or click **Quit** in the page) to stop it.

**macOS Gatekeeper note:** Since the app is not signed with an Apple Developer certificate, macOS will block it the first time. To allow it:
- Right-click (or Control-click) `SMAPIModUpdater` → **Open**, then click **Open** in the dialog, **or**
- Run this once in Terminal: `xattr -cr SMAPIModUpdater/`

### Option C: Clone and Run (any platform, from source)

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

That's it — it opens in your default browser automatically. Each time you want to run the updater in the future, just repeat Step 2 and Step 4.

### Option D: Install as a Python Package

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

Note: if you see a warning about the Scripts directory not being on PATH, you can either add it to PATH or just use Option C instead.

## Usage

1. **Launch Stardew Valley with SMAPI** at least once so it generates a fresh update log, then close the game
2. **Run the updater** (double-click the exe / run `./SMAPIModUpdater` / `python main.py`) — it starts a local server, opens your default browser to it, and auto-detects your setup to show which mods need updating
3. **Uncheck any mods** you want to skip (all are selected by default)
4. **Click "Open Download Pages"** — your browser opens the Nexus Files tab for each mod that isn't already downloaded
5. **Click "Slow Download" on each Nexus page** in your browser
6. **Click "Watch & Install"** — the tool monitors your Downloads folder and installs each mod as it arrives

If you've already downloaded some mods, just click "Watch & Install" directly — it scans existing files in your Downloads folder first and installs anything that matches.

The "Open Download Pages" button skips mods that have already been installed in the current session, and skips mods that already have a matching archive sitting in Downloads — so it's safe to click again if you need to open pages for the remaining mods.

When you're done, click **Quit** in the page to stop the updater cleanly. Closing just the browser tab doesn't stop it — the console/terminal window it's running in is still there as a fallback if you forget.

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

On first run, the tool creates `smapi_updater_config.json` with auto-detected paths. The Mods folder path is read directly from SMAPI's log (its "Mods go here:" line), so it always matches what SMAPI itself is using. Use the **Settings** button in the page to:

- Override the SMAPI log file location
- Override the Downloads folder
- Choose what happens if a mod's backup fails: **skip that mod's update** (default, safest), **install anyway without a backup**, or **ask each time** — the last option pauses that one mod and shows an inline prompt in the page, without holding up any other mods being watched at the same time

The **Mods** bar at the top shows the detected Mods folder. Click **Reload** to re-read the SMAPI log, e.g. after running the game again.

## SteamOS / Steam Deck Setup

Stardew Valley on SteamOS typically runs through **Proton**, which means SMAPI (a Windows program) writes its log with a Windows-style path (e.g. `Z:\home\deck\...`) instead of a native Linux path. The updater handles this automatically:

1. **Download and run the Linux build** (Option B above) in **Desktop Mode**. This matters more than it used to: the entire interface now runs through a browser, not just the "Open Download Pages" step, so Game Mode (which usually lacks a working browser/display association) won't work for any part of the tool.
2. On launch, the tool detects SteamOS and searches your Steam library's `compatdata` folders for SMAPI's log:
   - **Exactly one install found** — configured automatically, no action needed.
   - **Multiple installs found** (e.g. internal storage + SD card) — the page shows a picker for you to choose which one to use.
   - **None found** — run the game through Steam at least once so SMAPI generates a log, then click **Reload**.

### Manual setup (if auto-detection doesn't find your log)

Because the game runs through a Proton layer, the log lives in a deeply nested folder:

```
/home/deck/.steam/steam/steamapps/compatdata/[UniqueAppID]/pfx/drive_c/users/steamuser/AppData/Roaming/StardewValley/ErrorLogs/
```

The `[UniqueAppID]` is specific to your instance of the modded game, and most people won't know it offhand. If you don't, you can still find the log by browsing to:

```
/home/deck/.steam/steam/steamapps/compatdata/
```

...and searching for `SMAPI-latest.txt` (or `SMAPI-crash.txt` if SMAPI didn't shut down cleanly).

Once you've found the log file, right-click it and choose **Copy Location**. Then open the SMAPI Mod Updater, go to **Settings**, paste the file location into the **SMAPI Log File** field, and **Save**.

## How It Works

The tool reads SMAPI's `SMAPI-latest.txt` log file, which contains lines like:

```
[SMAPI] You can update 3 mods:
[SMAPI]    Automate 2.6.1: https://www.nexusmods.com/stardewvalley/mods/1063 (you have 2.6.0)
```

When a zip file appears in Downloads, the tool opens it, reads `manifest.json` to identify the mod (via `UpdateKeys` and `UniqueID`), verifies the version matches, backs up the existing mod folder, and extracts the new version in its place.

The mod search is recursive — it walks the entire Mods directory tree to find installed mods by their `UniqueID` (primary) or Nexus mod ID (fallback), recording the full relative path so the update goes back to exactly the same subfolder.

For multi-mod archives (like StonerValley which contains both a SMAPI mod and a Content Patcher pack), the tool finds and extracts all sub-mods, matching each to its correct existing folder by `UniqueID`.

The interface itself is a small local Flask web server, started on launch and opened in your default browser. Live updates (progress, log lines, mod status) reach the page over Server-Sent Events, so the page reflects what's happening in the background even though the actual work — parsing, watching, backing up, extracting — all still happens in plain Python, unchanged from how it always worked.

## Project Structure

```
modupdater/                          ← repo root
├── .gitignore
├── pyproject.toml                   # For pip install (optional)
├── Docs/                            # README and per-platform build instructions
│   ├── README.md
│   ├── Windows_build.md
│   ├── Linux_build.md
│   └── MacOS_build.md
├── build_exe.py                     # Builds standalone executable (cross-platform)
├── SMAPIModUpdater.spec             # PyInstaller build configuration (cross-platform)
└── smapi_mod_updater/               ← the actual tool
    ├── __init__.py
    ├── main.py                      # Entry point — starts the server, opens the browser
    ├── web_server.py                # Flask routes, Server-Sent Events, app state
    ├── templates/index.html         # The page itself
    ├── static/app.js                # Front-end logic
    ├── static/style.css             # Front-end styling
    ├── log_parser.py                # SMAPI log parsing
    ├── browser_launcher.py          # Opens Nexus download pages
    ├── download_watcher.py          # Watches Downloads folder, matches and installs
    ├── backup_manager.py            # Backup, extract, and restore logic
    ├── config_manager.py            # Config auto-detect, load, save
    ├── platform_utils.py            # OS-specific path detection, SteamOS/Proton detection
    ├── session_logger.py            # Per-session log file
    └── requirements.txt             # Python dependencies
```

## Building the Executable

PyInstaller cannot cross-compile — each platform's build must be run on that platform (or, for Linux, via WSL on Windows). See the platform-specific guides for exact steps:

- [Docs/Windows_build.md](Windows_build.md)
- [Docs/Linux_build.md](Linux_build.md)
- [Docs/MacOS_build.md](MacOS_build.md)

Each produces `dist/SMAPIModUpdater/` containing the executable (plus the bundled `templates/`/`static/` files it needs to serve the page), and a platform-appropriate zip archive ready for Nexus upload. The build script automatically includes a `manifest.json` and the README in the archive.

> **Note:** PyInstaller cannot cross-compile. A Linux binary must be built on Linux, a macOS binary on macOS.

## Changelog

### v2.0.0
- **Replaced the native GUI with a browser-based interface** — the tool now runs a small local web server and opens itself in your default browser instead of a CustomTkinter window. This removes the Tcl/Tk dependency entirely, which is what caused packaging failures on some platforms in the first place.
- **Fixed a backup failure caused by Windows read-only file attributes** — `shutil.rmtree` can't delete a read-only file or folder on Windows no matter how many times it's retried; a delay-and-retry alone never fixed it. Backups and extraction now clear the read-only attribute before retrying a failed delete.
- **Fixed a related failure where a leftover backup folder could block the next one** — if an old backup for a mod couldn't be fully removed (e.g. due to the read-only issue above), the next backup attempt for that mod would fail with no clear explanation. Old backups are now removed with the same retry-and-clear logic as everything else.
- **"Open Download Pages" now skips mods already sitting in Downloads** — instead of opening another Nexus tab (and creating another "(1)", "(2)"-style duplicate download) for a mod you've already downloaded, the tool checks for a matching archive first and skips the browser if it finds one.
- **New Settings option for backup failures** — choose whether a failed backup should skip that mod's update (the original, safest behavior and still the default), install anyway without a backup, or prompt you in the page each time it happens.
- **Quit button** — since there's no window to close anymore, the page has an explicit Quit button that stops the server; the console/terminal window it launches from remains as a fallback for anyone who just closes the browser tab.

### v1.2.2
- **Fixed "Open Download Pages" crash on some Linux distros** — the bundled app was leaking its own `LD_LIBRARY_PATH` to the `xdg-open` subprocess, causing tools like `kde-open` to load the bundled (older) OpenSSL libraries instead of the system ones and fail with a symbol version error

### v1.2.1
- **SteamOS/Proton support** — automatically translates Proton's Windows-style log paths to their real Linux location, so Steam Deck users don't need to manually resolve `Z:\` / `C:\` paths
- **SteamOS auto-detection** — detects SteamOS on launch and scans Steam library `compatdata` folders for the SMAPI log; auto-configures it when exactly one install is found, or shows a picker dialog when there are several
- **More reliable browser launching on Linux** — opening Nexus download pages now reports a real error instead of a false "Opened" message when the browser fails to launch (e.g. no display session)

### v1.2.0
- **macOS and Linux standalone executables** — no Python installation required
- **GitHub Actions CI** — automated cross-platform builds on tagged releases
- **Cross-platform build script** — `build_exe.py` now detects the OS and produces the correct archive format

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
- **Runs a local web server** (`127.0.0.1`, a free port starting at 5317) — needs a browser installed. If one doesn't open automatically, the console window prints the address to open manually.

## License

MIT

## Credits

Designed by tbonehunter. Developed collaboratively with Claude (Anthropic) writing much of the python script.
