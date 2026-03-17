# backup_manager.py - Backup and restore logic for SMAPI Mod Updater
"""
Handles the file operations for mod updates:
  - Back up the old mod folder to Mods/.backups/ModFolder_version/
  - Extract the new mod archive into the Mods folder
  - Restore a previous version from backup

Supports multi-mod archives where a single zip contains multiple
mod folders (e.g., a SMAPI code mod + a Content Patcher pack).

Preserves subfolder organization — if a mod lives at
Mods/Category/Automate/, the update goes back to the same place.

Keeps exactly one previous version per mod (overwrites older backups).
"""

import json
import shutil
import time
import zipfile
from pathlib import Path
from typing import Optional


BACKUP_DIR_NAME = ".backups"


def _get_backup_dir(mods_path: Path) -> Path:
    """Return the .backups directory inside the Mods folder, creating if needed."""
    backup_dir = mods_path / BACKUP_DIR_NAME
    backup_dir.mkdir(exist_ok=True)
    return backup_dir


# ─── Manifest Reading ─────────────────────────────────────────────

def _strip_json_comments(text: str) -> str:
    """
    Strip C-style comments from JSON text.

    SMAPI's manifest parser supports /* ... */ block comments and
    // line comments, but Python's json module does not.
    Removes both styles so json.loads() can parse the result.
    """
    import re
    # Remove block comments (/* ... */), including multi-line
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    # Remove line comments (// ...) but not inside strings
    # Simple approach: only strip // that appear after optional whitespace
    # at the start of a line, or after a comma/brace
    text = re.sub(r"(?m)^\s*//.*$", "", text)
    # Also handle inline // comments after values
    # Be conservative — only strip if // follows whitespace after a value
    text = re.sub(r'(?<=[\"\d\w\]\}])\s*//.*$', "", text, flags=re.MULTILINE)
    return text


def _parse_manifest(text: str) -> Optional[dict]:
    """
    Parse a manifest.json string, tolerating SMAPI-style comments.

    Returns the parsed dict, or None if parsing fails.
    """
    # Try direct parse first (fast path for comment-free manifests)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strip comments and retry
    try:
        cleaned = _strip_json_comments(text)
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None


def read_manifest_from_folder(mod_folder: Path) -> Optional[dict]:
    """
    Read manifest.json from an installed mod folder.

    Returns the parsed manifest dict, or None if not found/invalid.
    """
    manifest_path = mod_folder / "manifest.json"
    if not manifest_path.is_file():
        return None

    try:
        content = manifest_path.read_text(encoding="utf-8-sig", errors="replace")
        return _parse_manifest(content)
    except OSError:
        return None


def read_manifest_from_archive(archive_path: Path) -> Optional[dict]:
    """
    Peek inside a zip archive to find and read the first manifest.json.

    For matching purposes (identifying which mod this archive contains).
    For multi-mod archives, returns the shallowest manifest — typically
    the "primary" mod. Use read_all_manifests_from_archive() to get all.

    Returns the parsed manifest dict, or None if not found/invalid.
    """
    manifests = read_all_manifests_from_archive(archive_path)
    if manifests:
        return manifests[0]["manifest"]
    return None


def read_all_manifests_from_archive(archive_path: Path) -> list[dict]:
    """
    Read ALL manifest.json files from a zip archive.

    Handles multi-mod archives like:
      StonerValley/
      +-- StonerValley Code/manifest.json      (SMAPI mod)
      +-- [CP] StonerValley/manifest.json      (Content Pack)

    Returns a list of dicts, each containing:
      - manifest: dict    The parsed manifest.json contents
      - prefix:   str     The zip path prefix for this mod's files
      - folder:   str     The folder name to use in Mods/

    Sorted by depth (shallowest first), so the "primary" mod is first.
    Returns empty list if no manifests found.
    """
    if not zipfile.is_zipfile(archive_path):
        return []

    try:
        with zipfile.ZipFile(archive_path, "r") as zf:
            # Find all manifest.json files in the archive
            manifest_entries = [
                name for name in zf.namelist()
                if name.lower().endswith("manifest.json")
                and not name.startswith("__MACOSX")
                and "/." not in name
            ]

            if not manifest_entries:
                return []

            # Sort by depth (shallowest first)
            manifest_entries.sort(key=lambda x: x.count("/"))

            results = []
            for entry in manifest_entries:
                try:
                    content = zf.read(entry).decode("utf-8-sig", errors="replace")
                    manifest = _parse_manifest(content)
                except KeyError:
                    continue

                if manifest is None:
                    continue

                # Determine the prefix (path to this mod's folder in the zip)
                # and the folder name to use in Mods/
                parts = entry.split("/")

                if len(parts) == 1:
                    # manifest.json at root — single mod, no wrapper
                    prefix = ""
                    folder = archive_path.stem
                elif len(parts) == 2:
                    # ModName/manifest.json — standard single mod
                    prefix = parts[0] + "/"
                    folder = parts[0]
                elif len(parts) >= 3:
                    # Wrapper/ModFolder/manifest.json — multi-mod archive
                    # The mod folder is the parent of manifest.json
                    mod_folder_path = "/".join(parts[:-1])
                    prefix = mod_folder_path + "/"
                    # Use the immediate parent folder name for Mods/
                    folder = parts[-2]
                else:
                    continue

                results.append({
                    "manifest": manifest,
                    "prefix": prefix,
                    "folder": folder,
                })

            return results

    except (zipfile.BadZipFile, OSError):
        return []


# ─── Mod Identification ──────────────────────────────────────────

def get_nexus_id_from_manifest(manifest: dict) -> Optional[int]:
    """
    Extract the Nexus mod ID from a manifest's UpdateKeys.

    UpdateKeys typically looks like: ["Nexus:1063"]
    Returns the integer mod ID, or None.
    """
    update_keys = manifest.get("UpdateKeys", [])
    if not update_keys:
        return None

    for key in update_keys:
        if not isinstance(key, str):
            continue
        parts = key.strip().split(":")
        if len(parts) == 2 and parts[0].lower() == "nexus":
            try:
                return int(parts[1])
            except ValueError:
                continue

    return None


def get_unique_id_from_manifest(manifest: dict) -> Optional[str]:
    """Extract the UniqueID from a manifest."""
    return manifest.get("UniqueID")


def get_version_from_manifest(manifest: dict) -> Optional[str]:
    """Extract the Version string from a manifest."""
    return manifest.get("Version")


# ─── Matching Downloaded Archive to Installed Mod ─────────────────

def _walk_mod_folders(mods_path: Path) -> list[Path]:
    """
    Recursively find all folders containing a manifest.json under mods_path.

    Walks the directory tree, skipping hidden folders and the .backups
    directory. Stops descending into a folder once a manifest.json is
    found (a mod folder won't contain nested mod folders).

    Returns a list of Paths to folders that contain manifest.json.
    """
    mod_folders = []

    def _walk(directory: Path):
        try:
            entries = sorted(directory.iterdir())
        except OSError:
            return

        for entry in entries:
            if not entry.is_dir():
                continue
            # Skip hidden folders and backups
            if entry.name.startswith(("_", ".")):
                continue

            # Check if this folder has a manifest
            if (entry / "manifest.json").is_file():
                mod_folders.append(entry)
                # Don't descend further — mod folders don't nest
            else:
                # No manifest here — keep looking deeper
                _walk(entry)

    _walk(mods_path)
    return mod_folders


def find_installed_mod_folder(mods_path: Path, nexus_id: Optional[int] = None,
                               unique_id: Optional[str] = None) -> Optional[Path]:
    """
    Find the installed mod folder that matches the given identifiers.

    Recursively searches all subdirectories of the Mods folder,
    reading each manifest.json to match by UniqueID (primary) or
    Nexus mod ID (fallback).

    Supports organized Mods folders like:
      Mods/Pathoschild/Automate/manifest.json
      Mods/CJB/CJBItemSpawner/manifest.json
      Mods/Utilities/Framework/SpaceCore/manifest.json

    Args:
        mods_path:  Path to the Mods directory
        nexus_id:   Nexus mod ID to match against UpdateKeys
        unique_id:  SMAPI UniqueID to match against

    Returns:
        Path to the matching mod folder, or None.
    """
    if nexus_id is None and unique_id is None:
        return None

    dirs = _walk_mod_folders(mods_path)

    # Pass 1: Match by UniqueID (most specific — critical for multi-mod
    # archives where sub-mods share the same Nexus ID)
    if unique_id is not None:
        for entry in dirs:
            manifest = read_manifest_from_folder(entry)
            if manifest is None:
                continue
            installed_uid = get_unique_id_from_manifest(manifest)
            if installed_uid and installed_uid.lower() == unique_id.lower():
                return entry

    # Pass 2: Match by Nexus ID (broader — only if UniqueID didn't match)
    if nexus_id is not None:
        for entry in dirs:
            manifest = read_manifest_from_folder(entry)
            if manifest is None:
                continue
            installed_nexus_id = get_nexus_id_from_manifest(manifest)
            if installed_nexus_id == nexus_id:
                return entry

    return None


def get_relative_mod_path(mods_path: Path, mod_folder: Path) -> str:
    """
    Get the path of a mod folder relative to the Mods root.

    Examples:
      mods_path = D:/Stardew Valley/Mods
      mod_folder = D:/Stardew Valley/Mods/Pathoschild/Automate
      returns "Pathoschild/Automate"

      mod_folder = D:/Stardew Valley/Mods/SpaceCore
      returns "SpaceCore"

    Returns a forward-slash-separated relative path string.
    """
    try:
        rel = mod_folder.relative_to(mods_path)
        # Use forward slashes for consistency
        return str(rel).replace("\\", "/")
    except ValueError:
        # mod_folder isn't under mods_path — shouldn't happen but be safe
        return mod_folder.name


# ─── Backup ───────────────────────────────────────────────────────

def backup_mod(mods_path: Path, mod_folder: Path) -> Optional[Path]:
    """
    Back up an installed mod folder to .backups/.

    Creates: Mods/.backups/ModFolderName_version/
    If a previous backup exists for this mod, it is removed first
    (single previous version policy).

    Args:
        mods_path:  Path to the Mods directory
        mod_folder: Path to the specific mod folder to back up

    Returns:
        Path to the backup folder, or None on failure.
    """
    backup_dir = _get_backup_dir(mods_path)

    # Read the current version for the backup folder name
    manifest = read_manifest_from_folder(mod_folder)
    version = "unknown"
    if manifest:
        version = get_version_from_manifest(manifest) or "unknown"

    # Sanitize version string for use in folder name
    version_clean = version.replace(" ", "_").replace("/", "-").replace("\\", "-")
    backup_name = f"{mod_folder.name}_{version_clean}"
    backup_path = backup_dir / backup_name

    # Remove any existing backups for this mod (single previous version)
    _remove_old_backups(backup_dir, mod_folder.name)

    try:
        # Copy the entire mod folder to backup location
        shutil.copytree(mod_folder, backup_path)
        return backup_path
    except OSError:
        return None


def _remove_old_backups(backup_dir: Path, mod_folder_name: str):
    """
    Remove existing backups for a mod.

    Matches backup folders that start with the mod folder name followed
    by an underscore (e.g., "Automate_" matches "Automate_2.5.0").
    """
    prefix = f"{mod_folder_name}_"
    try:
        for entry in backup_dir.iterdir():
            if entry.is_dir() and entry.name.startswith(prefix):
                shutil.rmtree(entry, ignore_errors=True)
    except OSError:
        pass


# ─── Install (Extract) ───────────────────────────────────────────

def _rmtree_with_retry(path: Path, retries: int = 3, delay: float = 0.5):
    """
    Remove a directory tree with retry logic for Windows.

    On Windows, antivirus scanners, search indexers, and other processes
    can briefly hold file locks that cause shutil.rmtree to fail with
    PermissionError. Retrying after a short delay usually resolves this.
    """
    for attempt in range(retries):
        try:
            shutil.rmtree(path)
            return
        except PermissionError:
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                raise


def _extract_mod_folder(zf: zipfile.ZipFile, prefix: str,
                         target_path: Path) -> int:
    """
    Extract a single mod's files from a zip, stripping the given prefix.

    Args:
        zf:          Open ZipFile to read from
        prefix:      Path prefix to strip (e.g., "StonerValley/StonerValley Code/")
        target_path: Destination folder (full path including any subfolder structure)

    Returns:
        Number of files extracted.
    """
    # Remove existing folder if present, with retry for Windows file locks
    if target_path.exists():
        _rmtree_with_retry(target_path)

    target_path.mkdir(parents=True, exist_ok=True)

    extracted_count = 0
    for member in zf.infolist():
        # Skip directories, macOS resource forks, hidden files
        if member.is_dir():
            continue
        if member.filename.startswith("__MACOSX"):
            continue
        if "/." in member.filename:
            continue

        # Only extract files under our prefix
        if prefix and not member.filename.startswith(prefix):
            continue

        # Calculate the relative path after stripping prefix
        if prefix:
            rel_path = member.filename[len(prefix):]
        else:
            rel_path = member.filename

        if not rel_path:
            continue

        # Create subdirectories as needed
        dest_file = target_path / rel_path
        dest_file.parent.mkdir(parents=True, exist_ok=True)

        # Extract the file
        with zf.open(member) as src, open(dest_file, "wb") as dst:
            shutil.copyfileobj(src, dst)
        extracted_count += 1

    return extracted_count


def install_mod_from_archive(archive_path: Path, mods_path: Path,
                              target_folder_name: Optional[str] = None) -> Optional[Path]:
    """
    Extract a single mod from an archive into the Mods folder.

    For single-mod archives, extracts the mod.
    For multi-mod archives, extracts only the first (primary) mod.
    Use install_all_mods_from_archive() for multi-mod archives.

    Args:
        archive_path:       Path to the downloaded zip file
        mods_path:          Path to the Mods directory
        target_folder_name: Relative path for the mod folder in Mods/.
                            Can include subdirectories (e.g., "Pathoschild/Automate").
                            If None, uses the folder name from inside the archive.

    Returns:
        Path to the newly installed mod folder, or None on failure.
    """
    manifests = read_all_manifests_from_archive(archive_path)
    if not manifests:
        return None

    entry = manifests[0]
    folder_name = target_folder_name or entry["folder"]

    try:
        with zipfile.ZipFile(archive_path, "r") as zf:
            target_path = mods_path / folder_name
            count = _extract_mod_folder(zf, entry["prefix"], target_path)
            if count == 0:
                return None
            return target_path

    except (zipfile.BadZipFile, OSError, PermissionError) as e:
        print(f"[EXTRACT ERROR] {archive_path.name}: {type(e).__name__}: {e}")
        return None


def install_all_mods_from_archive(archive_path: Path, mods_path: Path,
                                   folder_overrides: Optional[dict] = None
                                   ) -> list[dict]:
    """
    Extract ALL mods from a multi-mod archive into the Mods folder.

    Preserves subfolder organization: if folder_overrides maps a mod's
    UniqueID to a relative path like "Pathoschild/Automate", the mod
    is extracted to Mods/Pathoschild/Automate/.

    Args:
        archive_path:     Path to the downloaded zip file
        mods_path:        Path to the Mods directory
        folder_overrides: Optional dict mapping UniqueID -> relative path
                          to install into existing mod folders.
                          e.g., {"Pathoschild.Automate": "Pathoschild/Automate",
                                 "BongWater.StonerValley": "StonerValley Code"}

    Returns:
        List of result dicts, each containing:
          - manifest:       dict          The manifest for this sub-mod
          - installed_path: Path or None  Where it was installed
          - folder:         str           Relative path used
          - success:        bool          Whether extraction succeeded
    """
    manifests = read_all_manifests_from_archive(archive_path)
    if not manifests:
        return []

    results = []

    try:
        with zipfile.ZipFile(archive_path, "r") as zf:
            for entry in manifests:
                manifest = entry["manifest"]
                unique_id = get_unique_id_from_manifest(manifest)

                # Check for folder override (install into existing location)
                folder_rel = entry["folder"]
                if folder_overrides and unique_id and unique_id in folder_overrides:
                    folder_rel = folder_overrides[unique_id]

                target_path = mods_path / folder_rel

                try:
                    count = _extract_mod_folder(zf, entry["prefix"], target_path)
                    success = count > 0
                except (OSError, PermissionError) as e:
                    print(f"[EXTRACT ERROR] {archive_path.name} -> {folder_rel}: "
                          f"{type(e).__name__}: {e}")
                    success = False

                results.append({
                    "manifest": manifest,
                    "installed_path": target_path if success else None,
                    "folder": folder_rel,
                    "success": success,
                })

    except (zipfile.BadZipFile, OSError) as e:
        print(f"[EXTRACT ERROR] {archive_path.name}: {type(e).__name__}: {e}")

    return results


# ─── Restore ──────────────────────────────────────────────────────

def get_available_backup(mods_path: Path, mod_folder_name: str) -> Optional[Path]:
    """
    Check if a backup exists for the given mod folder name.

    Returns the backup folder path, or None.
    """
    backup_dir = mods_path / BACKUP_DIR_NAME
    if not backup_dir.is_dir():
        return None

    prefix = f"{mod_folder_name}_"
    for entry in backup_dir.iterdir():
        if entry.is_dir() and entry.name.startswith(prefix):
            return entry

    return None


def restore_mod_from_backup(mods_path: Path, mod_folder_name: str) -> Optional[Path]:
    """
    Restore a mod from its backup, replacing the current version.

    Args:
        mods_path:       Path to the Mods directory
        mod_folder_name: Name of the mod folder (e.g., "Automate")

    Returns:
        Path to the restored mod folder, or None if no backup exists.
    """
    backup_path = get_available_backup(mods_path, mod_folder_name)
    if backup_path is None:
        return None

    target_path = mods_path / mod_folder_name

    try:
        # Remove current version
        if target_path.exists():
            shutil.rmtree(target_path)

        # Copy backup to mod location
        shutil.copytree(backup_path, target_path)
        return target_path

    except OSError:
        return None
