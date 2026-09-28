<!-- MacOS_build.md -->
# macOS Build Instructions

## Prerequisites

- Python 3.10+ installed (via [python.org](https://www.python.org/downloads/) or Homebrew: `brew install python`)
- Xcode Command Line Tools, needed to compile `watchdog`'s native macOS file-watching backend: `xcode-select --install`

## Build

1. Open Terminal and navigate to the project directory:

```bash
cd /path/to/Updater
```

2. Create a virtual environment, install dependencies, and build:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r smapi_mod_updater/requirements.txt
pip install pyinstaller
python build_exe.py
```

If `pip` isn't recognized, try `pip3` instead.

## Subsequent Builds

If the venv already exists, skip creation:

```bash
cd /path/to/Updater
source .venv/bin/activate
python build_exe.py
```

## Output

The build produces a zip in `dist/`, e.g. `dist/SMAPI Mod Updater 2.0.0 (macOS).zip`. Running the executable starts a local web server and opens the tool in your default browser.

> **Apple Silicon vs. Intel:** PyInstaller cannot cross-compile between architectures — a build made on an Apple Silicon (arm64) Mac only runs on arm64, and a build made on an Intel (x86_64) Mac only runs on x86_64. The archive name doesn't currently distinguish architecture, so if you build on both, rename each zip (e.g. append `-arm64` / `-x86_64`) before uploading, or the second build will silently overwrite the first in `dist/`.
