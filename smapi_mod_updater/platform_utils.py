# platform_utils.py - OS-specific path detection for SMAPI Mod Updater
"""
Detects default paths for SMAPI log, Mods folder, and Downloads folder
across Windows, macOS, and Linux. Uses a tiered search strategy:

  Tier 1: Common known locations (fast)
  Tier 2: Parse Steam's libraryfolders.vdf to find all library paths (reliable)
  Tier 3: Fallback to None (caller should prompt user to browse)
"""

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


# ─── Steam Library Discovery ─────────────────────────────────────

def _get_steam_root() -> Optional[Path]:
    """Return the root Steam installation directory for the current OS."""
    current_os = get_os()

    candidates = []
    if current_os == "windows":
        candidates = [
            Path("C:/Program Files (x86)/Steam"),
            Path("C:/Program Files/Steam"),
            # Check all drive letters for relocated Steam installs
            *[Path(f"{d}:/Steam") for d in "DEFGHIJKLMNOPQRSTUVWXYZ"],
        ]
    elif current_os == "macos":
        candidates = [
            Path.home() / "Library" / "Application Support" / "Steam",
        ]
    elif current_os == "linux":
        candidates = [
            Path.home() / ".steam" / "steam",
            Path.home() / ".local" / "share" / "Steam",
            Path.home() / ".steam" / "debian-installation",
        ]

    for path in candidates:
        if path.is_dir():
            return path
    return None


def _parse_library_folders_vdf(vdf_path: Path) -> list[Path]:
    """
    Parse Steam's libraryfolders.vdf to extract all Steam library paths.
    Returns a list of library root directories.

    The VDF format uses nested braces with key-value pairs like:
      "0" { "path"  "C:\\Program Files (x86)\\Steam" }
      "1" { "path"  "D:\\SteamLibrary" }
    """
    library_paths = []

    if not vdf_path.is_file():
        return library_paths

    try:
        content = vdf_path.read_text(encoding="utf-8", errors="replace")
        # Match "path" values - handles both escaped and forward slashes
        pattern = r'"path"\s+"([^"]+)"'
        matches = re.findall(pattern, content)
        for match in matches:
            # Normalize escaped backslashes from VDF format
            normalized = match.replace("\\\\", "/").replace("\\", "/")
            lib_path = Path(normalized)
            if lib_path.is_dir():
                library_paths.append(lib_path)
    except (OSError, UnicodeDecodeError):
        pass

    return library_paths


def get_steam_library_paths() -> list[Path]:
    """
    Discover all Steam library folders on this system.
    Returns a list of directories that may contain steamapps/common/.
    """
    steam_root = _get_steam_root()
    if steam_root is None:
        return []

    libraries = [steam_root]

    # Parse libraryfolders.vdf for additional library locations
    vdf_path = steam_root / "steamapps" / "libraryfolders.vdf"
    parsed = _parse_library_folders_vdf(vdf_path)
    for lib in parsed:
        if lib not in libraries:
            libraries.append(lib)

    return libraries


# ─── Stardew Valley Game Instance Discovery ───────────────────────

def _find_stardew_in_library(library_path: Path) -> Optional[Path]:
    """Check a Steam library path for a Stardew Valley installation."""
    game_path = library_path / "steamapps" / "common" / "Stardew Valley"
    if game_path.is_dir():
        return game_path
    return None


def _get_gog_candidates() -> list[Path]:
    """Return candidate paths for GOG Stardew Valley installations."""
    current_os = get_os()

    candidates = []
    if current_os == "windows":
        candidates = [
            Path("C:/GOG Games/Stardew Valley"),
            Path("C:/Program Files/GOG Galaxy/Games/Stardew Valley"),
            Path("C:/Program Files (x86)/GOG Galaxy/Games/Stardew Valley"),
            # Check other drives
            *[Path(f"{d}:/GOG Games/Stardew Valley") for d in "DEFGHIJKLMNOPQRSTUVWXYZ"],
        ]
    elif current_os == "macos":
        candidates = [
            Path.home() / "Applications" / "Stardew Valley.app" / "Contents" / "MacOS",
        ]
    elif current_os == "linux":
        candidates = [
            Path.home() / "GOG Games" / "Stardew Valley" / "game",
        ]

    return candidates


def _get_direct_install_candidates() -> list[Path]:
    """
    Return candidate paths for direct/custom Stardew Valley installations.
    Covers common patterns like installing directly to a drive root.
    """
    current_os = get_os()

    candidates = []
    if current_os == "windows":
        candidates = [
            # Direct drive root installs (like Stan's D:\Stardew Valley)
            *[Path(f"{d}:/Stardew Valley") for d in "CDEFGHIJKLMNOPQRSTUVWXYZ"],
            # Subfolder patterns
            *[Path(f"{d}:/Games/Stardew Valley") for d in "CDEFGHIJKLMNOPQRSTUVWXYZ"],
        ]
    elif current_os == "macos":
        candidates = [
            Path("/Applications/Stardew Valley.app/Contents/MacOS"),
            Path.home() / "Applications" / "Stardew Valley.app" / "Contents" / "MacOS",
        ]
    elif current_os == "linux":
        candidates = [
            Path.home() / ".local" / "share" / "Steam" / "steamapps" / "common" / "Stardew Valley",
            Path.home() / "Games" / "Stardew Valley",
        ]

    return candidates


def _validate_stardew_folder(path: Path) -> bool:
    """
    Verify a path looks like a real Stardew Valley installation.
    Checks for the Mods folder (SMAPI installed) and the game executable.
    """
    if not path.is_dir():
        return False

    # Must have a Mods folder (indicates SMAPI is installed)
    mods_folder = path / "Mods"
    if not mods_folder.is_dir():
        return False

    # Check for game executable (varies by platform)
    current_os = get_os()
    if current_os == "windows":
        has_exe = (path / "Stardew Valley.exe").is_file() or (path / "StardewModdingAPI.exe").is_file()
    elif current_os == "macos":
        has_exe = (path / "StardewModdingAPI").is_file() or (path / "Stardew Valley").is_file()
    elif current_os == "linux":
        has_exe = (path / "StardewModdingAPI").is_file() or (path / "Stardew Valley").is_file()
    else:
        has_exe = True  # Don't block on unknown OS

    return has_exe


def discover_game_instances() -> list[dict]:
    """
    Find all Stardew Valley installations on this system.

    Returns a list of dicts, each containing:
      - game_path: Path to the game root directory
      - mods_path: Path to the Mods folder
      - source:    How it was found ('steam', 'gog', 'direct')
    """
    found = []
    seen_paths = set()

    def _add_instance(game_path: Path, source: str):
        """Add a validated game instance, avoiding duplicates."""
        resolved = game_path.resolve()
        if resolved in seen_paths:
            return
        if not _validate_stardew_folder(resolved):
            return
        seen_paths.add(resolved)
        found.append({
            "game_path": resolved,
            "mods_path": resolved / "Mods",
            "source": source,
        })

    # Tier 1a: Steam libraries (most reliable)
    for library in get_steam_library_paths():
        stardew = _find_stardew_in_library(library)
        if stardew:
            _add_instance(stardew, "steam")

    # Tier 1b: GOG default locations
    for candidate in _get_gog_candidates():
        if candidate.is_dir():
            _add_instance(candidate, "gog")

    # Tier 1c: Direct/custom install locations
    for candidate in _get_direct_install_candidates():
        if candidate.is_dir():
            _add_instance(candidate, "direct")

    return found


# ─── SMAPI Log Detection (system-wide, not per-instance) ─────────

def detect_smapi_log_path() -> Optional[Path]:
    """
    Detect the SMAPI log file location.

    SMAPI writes its log to the game's AppData saves folder,
    NOT the game install folder. This is the same location
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


# ─── Convenience: Single best-guess paths ─────────────────────────

def detect_mods_folder() -> Optional[Path]:
    """Return the Mods folder path from the first discovered game instance."""
    instances = discover_game_instances()
    if instances:
        return instances[0]["mods_path"]
    return None
