# build_exe.py - Build a standalone executable and Nexus-ready archive
"""
Builds the SMAPI Mod Updater into a standalone executable for the
current platform and packages it into an archive ready for Nexus Mods.

Run from the repo root:
    python build_exe.py

Requires PyInstaller:
    pip install pyinstaller

Output (varies by platform):
    dist/SMAPIModUpdater/                          - The built executable and dependencies
    dist/SMAPI Mod Updater x.x.x (platform).zip   - Nexus-ready archive
"""

import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from smapi_mod_updater.version import VERSION


# ─── Configuration ────────────────────────────────────────────────

APP_NAME = "SMAPI Mod Updater"
EXE_NAME = "SMAPIModUpdater"

# Nexus manifest for the tool (NOT a SMAPI mod manifest — this just
# identifies it on Nexus and in mod managers)
NEXUS_MANIFEST = {
    "Name": APP_NAME,
    "Author": "tbonehunter",
    "Version": VERSION,
    "Description": (
        "A GUI tool that streamlines updating Stardew Valley SMAPI mods "
        "from Nexus Mods. Parses SMAPI's update log, opens download pages, "
        "and automatically installs downloaded updates. See README.md for "
        "installation and usage"
    ),
    "UniqueID": "tbonehunter.SMAPIModUpdater",
}


def get_platform_tag() -> str:
    """Return a short platform tag for archive naming."""
    system = platform.system().lower()
    if system == "darwin":
        return "macOS"
    elif system == "linux":
        return "Linux"
    return "Windows"


def get_exe_filename() -> str:
    """Return the executable filename for the current platform."""
    if platform.system().lower() == "windows":
        return EXE_NAME + ".exe"
    return EXE_NAME


# Per-platform build guide bundled into that platform's archive.
# When adding support for a new platform, add its build doc here too.
BUILD_DOC_BY_PLATFORM = {
    "Windows": "Windows_build.md",
    "Linux": "Linux_build.md",
    "macOS": "MacOS_build.md",
}


def main():
    repo_root = Path(__file__).parent
    dist_dir = repo_root / "dist"
    build_dir = repo_root / "build"
    spec_file = repo_root / "SMAPIModUpdater.spec"
    platform_tag = get_platform_tag()
    step_num = 0

    def next_step(label: str) -> None:
        nonlocal step_num
        step_num += 1
        print(f"Step {step_num}: {label}...")

    print(f"Building {APP_NAME} v{VERSION} for {platform_tag}...")
    print()

    # ─── Step: Run PyInstaller ─────────────────────────────────────
    next_step("Running PyInstaller")

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

    # ─── Step: Add manifest.json ───────────────────────────────────
    next_step("Adding manifest.json")

    manifest_path = exe_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(NEXUS_MANIFEST, indent=2),
        encoding="utf-8",
    )
    print(f"  Written: {manifest_path}")
    print()

    # ─── Step: Add README ───────────────────────────────────────────
    next_step("Adding README")

    readme_src = repo_root / "Docs" / "README.md"
    if readme_src.is_file():
        shutil.copy2(readme_src, exe_dir / "README.md")
        print(f"  Copied: README.md")
    else:
        print("  WARNING: README.md not found in Docs/, skipping.")
    print()

    # ─── Step: Add platform-specific build guide ───────────────────
    next_step("Adding build guide")

    build_doc_name = BUILD_DOC_BY_PLATFORM.get(platform_tag)
    build_doc_src = repo_root / "Docs" / build_doc_name if build_doc_name else None
    if build_doc_src and build_doc_src.is_file():
        shutil.copy2(build_doc_src, exe_dir / build_doc_name)
        print(f"  Copied: {build_doc_name}")
    else:
        print(f"  WARNING: {build_doc_name or '(no build doc mapped)'} not found in Docs/, skipping.")
    print()

    # ─── Step: Set executable permission (Linux/macOS) ─────────────
    if platform_tag != "Windows":
        next_step("Setting executable permission")
        exe_path = exe_dir / EXE_NAME
        if exe_path.is_file():
            exe_path.chmod(exe_path.stat().st_mode | 0o755)
            print(f"  chmod +x: {exe_path}")
        print()

    # ─── Step: Create Nexus archive ─────────────────────────────────
    next_step("Creating Nexus-ready archive")

    archive_base = f"SMAPI Mod Updater {VERSION} ({platform_tag})"

    shutil.make_archive(
        str(dist_dir / archive_base),
        "zip",
        root_dir=str(dist_dir),
        base_dir=EXE_NAME,
    )
    archive_path = dist_dir / f"{archive_base}.zip"

    size_mb = archive_path.stat().st_size / (1024 * 1024)
    print(f"  Created: {archive_path}")
    print(f"  Size: {size_mb:.1f} MB")
    print()

    # ─── Done ─────────────────────────────────────────────────────
    print("=" * 50)
    print(f"Build complete!")
    print()
    print(f"Executable:  {exe_dir / get_exe_filename()}")
    print(f"Archive:     {archive_path}")
    print()

    if platform_tag == "Windows":
        print("To test: double-click SMAPIModUpdater.exe in the dist folder.")
    elif platform_tag == "macOS":
        print("To test: ./dist/SMAPIModUpdater/SMAPIModUpdater")
        print("Note: macOS users may need to right-click → Open or run")
        print("  xattr -cr dist/SMAPIModUpdater/  to bypass Gatekeeper.")
    else:
        print("To test: ./dist/SMAPIModUpdater/SMAPIModUpdater")

    print("To upload: use the archive file on Nexus Mods.")


if __name__ == "__main__":
    main()
