# platform_utils.py - OS-specific path detection for SMAPI Mod Updater
"""
Detects default paths for the SMAPI log and Downloads folder
across Windows, macOS, and Linux.

The game and Mods paths are derived from the SMAPI log header
(parsed by log_parser.parse_smapi_log_paths), so this module
only needs to locate the log file and the Downloads folder.
"""

import platform
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
