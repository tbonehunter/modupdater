# config_manager.py - Configuration management for SMAPI Mod Updater
"""
Handles loading, saving, and auto-detecting configuration settings.

Config file (smapi_updater_config.json) stores:
  - SMAPI log path
  - Mods folder path (derived from SMAPI log header)
  - Downloads folder path

The Mods path is read from the SMAPI log's "Mods go here:" header line,
eliminating the need for Steam/GOG/filesystem scanning. SMAPI must have
been run at least once for this to work.
"""

import json
import sys
from pathlib import Path
from typing import Optional

from log_parser import parse_smapi_log_paths
from platform_utils import (
    detect_downloads_folder,
    detect_smapi_log_path,
)

# Config file lives next to the script (or next to the exe when frozen)
CONFIG_FILENAME = "smapi_updater_config.json"


def _get_config_path() -> Path:
    """
    Return the path to the config file.

    When running from source: adjacent to config_manager.py
    When running as a PyInstaller exe: adjacent to the exe itself
    """
    if getattr(sys, 'frozen', False):
        # Running as a PyInstaller bundle — use the exe's directory
        return Path(sys.executable).parent / CONFIG_FILENAME
    else:
        # Running from source — use the script's directory
        return Path(__file__).parent / CONFIG_FILENAME


def _default_config() -> dict:
    """
    Build a default config by auto-detecting paths.
    Returns a config dict ready to be saved.
    """
    config = {
        "version": 3,
        "downloads_folder": None,
        "smapi_log_path": None,
        "mods_path": None,
    }

    # Auto-detect downloads folder
    downloads = detect_downloads_folder()
    if downloads:
        config["downloads_folder"] = str(downloads)

    # Auto-detect SMAPI log location
    log_path = detect_smapi_log_path()
    if log_path:
        config["smapi_log_path"] = str(log_path)

        # Derive Mods path from the SMAPI log header
        paths = parse_smapi_log_paths(log_path)
        if paths["mods_path"]:
            config["mods_path"] = str(paths["mods_path"])

    return config


def load_config() -> dict:
    """
    Load config from disk. If no config file exists, auto-detect
    defaults and save them.

    Returns the config dict.
    """
    config_path = _get_config_path()

    if config_path.is_file():
        try:
            content = config_path.read_text(encoding="utf-8")
            config = json.loads(content)
            return _ensure_config_integrity(config)
        except (json.JSONDecodeError, OSError):
            # Corrupt config — regenerate
            pass

    # First run or corrupt file: auto-detect and save
    config = _default_config()
    save_config(config)
    return config


def save_config(config: dict) -> bool:
    """
    Save config dict to disk. Returns True on success.
    """
    config_path = _get_config_path()
    try:
        content = json.dumps(config, indent=2, default=str)
        config_path.write_text(content, encoding="utf-8")
        return True
    except OSError:
        return False


def _ensure_config_integrity(config: dict) -> dict:
    """
    Validate and fill in any missing fields in a loaded config.
    Handles upgrades from older config versions gracefully.
    """
    # Upgrade from v2 (game_instances) to v3 (log-derived mods_path)
    if config.get("version", 1) < 3:
        # Migrate: pull mods_path from the first game instance if available
        instances = config.pop("game_instances", [])
        if instances and "mods_path" not in config:
            config["mods_path"] = instances[0].get("mods_path")
        config.pop("active_instance_index", None)
        config["version"] = 3

    if "downloads_folder" not in config:
        downloads = detect_downloads_folder()
        config["downloads_folder"] = str(downloads) if downloads else None

    if "smapi_log_path" not in config:
        log_path = detect_smapi_log_path()
        config["smapi_log_path"] = str(log_path) if log_path else None

    if "mods_path" not in config:
        config["mods_path"] = None

    # If mods_path is missing, try to derive from the SMAPI log
    if not config.get("mods_path"):
        log = config.get("smapi_log_path")
        if log:
            paths = parse_smapi_log_paths(Path(log))
            if paths["mods_path"]:
                config["mods_path"] = str(paths["mods_path"])

    return config


# ─── Convenience accessors ────────────────────────────────────────

def get_mods_path(config: dict) -> Optional[Path]:
    """Return the Mods folder Path (derived from SMAPI log or user override)."""
    mods = config.get("mods_path")
    if mods:
        return Path(mods)
    return None


def get_log_path(config: dict) -> Optional[Path]:
    """Return the SMAPI log Path."""
    log = config.get("smapi_log_path")
    if log:
        return Path(log)
    return None


def get_downloads_path(config: dict) -> Optional[Path]:
    """Return the Downloads folder Path."""
    dl = config.get("downloads_folder")
    if dl:
        return Path(dl)
    return None


def update_downloads_path(config: dict, path: str) -> dict:
    """Override the downloads folder path."""
    config["downloads_folder"] = path
    return config


def refresh_mods_path(config: dict) -> dict:
    """Re-derive the Mods path from the current SMAPI log."""
    log = config.get("smapi_log_path")
    if log:
        paths = parse_smapi_log_paths(Path(log))
        if paths["mods_path"]:
            config["mods_path"] = str(paths["mods_path"])
    return config
