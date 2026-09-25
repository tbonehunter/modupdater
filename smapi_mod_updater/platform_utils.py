# platform_utils.py - OS-specific path detection for SMAPI Mod Updater
"""
Detects default paths for the SMAPI log and Downloads folder
across Windows, macOS, and Linux.

The game and Mods paths are derived from the SMAPI log header
(parsed by log_parser.parse_smapi_log_paths), so this module
only needs to locate the log file and the Downloads folder.
"""

import os
import platform
import re
from pathlib import Path
from typing import Optional


def get_os() -> str:
    """Return normalized OS name: 'windows', 'macos', or 'linux'."""
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    return system  # 'windows' or 'linux'


# ─── Downloads Folder ─────────────────────────────────────────────

def detect_downloads_folder() -> Optional[Path]:
    """Return the default Downloads folder for the current OS."""
    downloads = Path.home() / "Downloads"
    if downloads.is_dir():
        return downloads
    return None


# ─── SMAPI Log Detection ─────────────────────────────────────────

def detect_smapi_log_path() -> Optional[Path]:
    """
    Detect the SMAPI log file location.

    SMAPI writes its log to the same AppData/config folder
    regardless of where the game is installed:

      Windows: %AppData%/StardewValley/ErrorLogs/SMAPI-latest.txt
      macOS:   ~/.config/StardewValley/ErrorLogs/SMAPI-latest.txt
      Linux:   ~/.config/StardewValley/ErrorLogs/SMAPI-latest.txt
    """
    current_os = get_os()

    if current_os == "windows":
        # %AppData% resolves to C:\Users\<user>\AppData\Roaming
        appdata = Path.home() / "AppData" / "Roaming"
        log_path = appdata / "StardewValley" / "ErrorLogs" / "SMAPI-latest.txt"
    elif current_os in ("macos", "linux"):
        log_path = Path.home() / ".config" / "StardewValley" / "ErrorLogs" / "SMAPI-latest.txt"
    else:
        return None

    if log_path.is_file():
        return log_path
    return None


# ─── SteamOS / Proton Detection ───────────────────────────────────

_VDF_PATH_PATTERN = re.compile(r'"path"\s+"([^"]+)"')
_VDF_NAME_PATTERN = re.compile(r'"name"\s+"([^"]+)"')

# Relative path from a compatdata/<appid> folder to SMAPI's log, since the
# game runs as a Windows process under Proton and always uses this layout.
_PROTON_LOG_SUFFIX = Path("pfx/drive_c/users/steamuser/AppData/Roaming/StardewValley/ErrorLogs/SMAPI-latest.txt")


def is_steamos() -> bool:
    """Detect SteamOS (e.g. Steam Deck) via its env var or /etc/os-release."""
    if os.environ.get("SteamDeck") == "1":
        return True
    os_release = Path("/etc/os-release")
    if os_release.is_file():
        try:
            return "ID=steamos" in os_release.read_text(encoding="utf-8", errors="replace")
        except OSError:
            pass
    return False


def _steam_library_roots() -> list[Path]:
    """Find Steam installation roots, including extra libraries from libraryfolders.vdf."""
    roots = []
    for candidate in (Path.home() / ".steam" / "steam", Path.home() / ".local" / "share" / "Steam"):
        if candidate.is_dir() and candidate not in roots:
            roots.append(candidate)

    for root in list(roots):
        vdf_path = root / "steamapps" / "libraryfolders.vdf"
        if not vdf_path.is_file():
            continue
        try:
            content = vdf_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for match in _VDF_PATH_PATTERN.finditer(content):
            extra = Path(match.group(1).replace("\\\\", "/"))
            if extra.is_dir() and extra not in roots:
                roots.append(extra)

    return roots


def find_steamos_smapi_logs() -> list[Path]:
    """
    Scan all Steam library compatdata folders for a Proton-run SMAPI log.

    Returns every match found, since a user may have multiple Stardew
    Valley installs (e.g. across internal storage and an SD card).
    """
    logs = []
    for root in _steam_library_roots():
        compatdata = root / "steamapps" / "compatdata"
        if not compatdata.is_dir():
            continue
        for appid_dir in compatdata.iterdir():
            log_path = appid_dir / _PROTON_LOG_SUFFIX
            if log_path.is_file() and log_path not in logs:
                logs.append(log_path)
    return logs


def get_steam_app_name(log_path: Path) -> Optional[str]:
    """Best-effort lookup of the Steam app name for a compatdata SMAPI log."""
    pfx_dir = next((p for p in log_path.parents if p.name == "pfx"), None)
    if pfx_dir is None:
        return None

    appid = pfx_dir.parent.name  # compatdata/<appid>/pfx
    steamapps_dir = pfx_dir.parent.parent.parent  # compatdata/<appid>/pfx -> compatdata -> steamapps
    manifest = steamapps_dir / f"appmanifest_{appid}.acf"
    if manifest.is_file():
        try:
            content = manifest.read_text(encoding="utf-8", errors="replace")
            match = _VDF_NAME_PATTERN.search(content)
            if match:
                return match.group(1)
        except OSError:
            pass
    return f"App {appid}"
