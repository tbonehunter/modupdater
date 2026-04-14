<!-- MacOS_build.md -->
# macOS Build Instructions

## Prerequisites

- Python 3.10+ installed (via [python.org](https://www.python.org/downloads/) or Homebrew: `brew install python`)
- Tkinter support (included with python.org installer; for Homebrew: `brew install python-tk`)

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

## Subsequent Builds

If the venv already exists, skip creation:

```bash
cd /path/to/Updater
source .venv/bin/activate
python build_exe.py
```

## Output

The build produces a zip in `dist/`, e.g. `dist/SMAPI Mod Updater 1.2.0 (macos-arm64).zip` or `dist/SMAPI Mod Updater 1.2.0 (macos-x86_64).zip` depending on architecture.
