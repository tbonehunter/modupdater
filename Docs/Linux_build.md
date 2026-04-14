<!-- Linux_install.md -->
# Linux Build Instructions (via WSL)

## Prerequisites

From inside WSL (Ubuntu):

```bash
sudo apt update && sudo apt install -y python3-venv python3-full python3-tk
```

## Build

1. Navigate to the project directory:

```bash
cd '/mnt/c/Users/HP/Documents/Stardew Modding/Stan'\''s Mods/Finished Mods/Updater'
```

2. Create a venv on the native Linux filesystem, install dependencies, and build:

```bash
python3 -m venv ~/updater-venv && source ~/updater-venv/bin/activate && pip install -r smapi_mod_updater/requirements.txt && pip install pyinstaller && python build_exe.py
```

> **Note:** The venv must live on the Linux filesystem (e.g. `~/updater-venv`), not on the Windows NTFS mount (`/mnt/c/...`), or pip will fail with `externally-managed-environment`.

## Subsequent Builds

If the venv already exists, skip creation:

```bash
cd '/mnt/c/Users/HP/Documents/Stardew Modding/Stan'\''s Mods/Finished Mods/Updater'
source ~/updater-venv/bin/activate
python build_exe.py
```

## Output

The build produces a zip in `dist/`, e.g. `dist/SMAPIModUpdater-1.2.0-linux-x86_64.zip`.
