# build_exe.py - Build the Windows executable and Nexus-ready zip
"""
Builds the SMAPI Mod Updater into a standalone Windows executable
and packages it into a zip file ready for Nexus Mods upload.

Run from the repo root:
    python build_exe.py

Requires PyInstaller:
    pip install pyinstaller

Output:
    dist/SMAPIModUpdater/           - The built executable and dependencies
    dist/SMAPI Mod Updater x.x.x.zip  - Nexus-ready zip file
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path


# ─── Configuration ────────────────────────────────────────────────

APP_NAME = "SMAPI Mod Updater"
EXE_NAME = "SMAPIModUpdater"
VERSION = "1.0.0"

# Nexus manifest for the tool (NOT a SMAPI mod manifest — this just
# identifies it on Nexus and in mod managers)
NEXUS_MANIFEST = {
    "Name": APP_NAME,
    "Author": "Nortek LLC",
    "Version": VERSION,
    "Description": (
        "A GUI tool that streamlines updating Stardew Valley SMAPI mods "
        "from Nexus Mods. Parses SMAPI's update log, opens download pages, "
        "and automatically installs downloaded updates."
    ),
    "UniqueID": "tbonehunter.SMAPIModUpdater",
}


def main():
    repo_root = Path(__file__).parent
    dist_dir = repo_root / "dist"
    build_dir = repo_root / "build"
    spec_file = repo_root / "SMAPIModUpdater.spec"

    print(f"Building {APP_NAME} v{VERSION}...")
    print()

    # ─── Step 1: Run PyInstaller ──────────────────────────────────
    print("Step 1: Running PyInstaller...")

    result = subprocess.run(
        [
            sys.executable, "-m", "PyInstaller",
            str(spec_file),
            "--distpath", str(dist_dir),
            "--workpath", str(build_dir),
            "--noconfirm",
        ],
        cwd=str(repo_root),
    )

    if result.returncode != 0:
        print("ERROR: PyInstaller failed. Check the output above.")
        sys.exit(1)

    exe_dir = dist_dir / EXE_NAME
    if not exe_dir.is_dir():
        print(f"ERROR: Expected output directory not found: {exe_dir}")
        sys.exit(1)

    print(f"  Built to: {exe_dir}")
    print()

    # ─── Step 2: Add manifest.json ────────────────────────────────
    print("Step 2: Adding manifest.json...")

    manifest_path = exe_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(NEXUS_MANIFEST, indent=2),
        encoding="utf-8",
    )
    print(f"  Written: {manifest_path}")
    print()

    # ─── Step 3: Add README ───────────────────────────────────────
    print("Step 3: Adding README...")

    readme_src = repo_root / "README.md"
    if readme_src.is_file():
        shutil.copy2(readme_src, exe_dir / "README.md")
        print(f"  Copied: README.md")
    else:
        print("  WARNING: README.md not found in repo root, skipping.")
    print()

    # ─── Step 4: Create Nexus zip ─────────────────────────────────
    print("Step 4: Creating Nexus-ready zip...")

    zip_name = f"SMAPI Mod Updater {VERSION}"
    zip_path = dist_dir / zip_name

    shutil.make_archive(
        str(zip_path),
        "zip",
        root_dir=str(dist_dir),
        base_dir=EXE_NAME,
    )

    final_zip = dist_dir / f"{zip_name}.zip"
    size_mb = final_zip.stat().st_size / (1024 * 1024)
    print(f"  Created: {final_zip}")
    print(f"  Size: {size_mb:.1f} MB")
    print()

    # ─── Done ─────────────────────────────────────────────────────
    print("=" * 50)
    print(f"Build complete!")
    print()
    print(f"Executable:  {exe_dir / (EXE_NAME + '.exe')}")
    print(f"Nexus zip:   {final_zip}")
    print()
    print("To test: double-click SMAPIModUpdater.exe in the dist folder.")
    print("To upload: use the zip file on Nexus Mods.")


if __name__ == "__main__":
    main()
