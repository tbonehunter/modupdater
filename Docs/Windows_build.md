<!-- Windows_build.md -->
# Windows Build Instructions

## Prerequisites

- Python 3.10+ installed (from [python.org](https://www.python.org/downloads/) or Microsoft Store)
- Ensure "Add Python to PATH" was checked during install

## Build

1. Open a terminal (PowerShell or Command Prompt) and navigate to the project directory:

```powershell
cd "C:\Users\HP\Documents\Stardew Modding\Stan's Mods\Finished Mods\Updater"
```

2. Create a virtual environment, install dependencies, and build:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r smapi_mod_updater\requirements.txt
pip install pyinstaller
python build_exe.py
```

## Subsequent Builds

If the venv already exists, skip creation:

```powershell
cd "C:\Users\HP\Documents\Stardew Modding\Stan's Mods\Finished Mods\Updater"
.venv\Scripts\activate
python build_exe.py
```

## Output

The build produces a zip in `dist\`, e.g. `dist\SMAPI Mod Updater 1.2.0 (windows-x86_64).zip`.
