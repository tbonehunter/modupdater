# config_manager.py - Configuration management for SMAPI Mod Updater
"""
Handles loading, saving, and auto-detecting configuration settings.

Config file (smapi_updater_config.json) stores:
  - Known game instances (game path, mods path, log path)
  - Active instance selection
  - Downloads folder path
  - User overrides

Auto-generates sensible defaults on first run using platform_utils,
then persists for future sessions.
"""

import json
from pathlib import Path
from typing import Optional

from platform_utils import (
    detect_downloads_folder,
    detect_smapi_log_path,
    discover_game_instances,
)

# Config file lives next to the script
CONFIG_FILENAME = "smapi_updater_config.json"


def _get_config_path() -> Path:
    """Return the path to the config file, adjacent to this script."""
    return Path(__file__).parent / CONFIG_FILENAME


def _default_config() -> dict:
    """
    Build a default config by auto-detecting paths.
    Returns a config dict ready to be saved.
    """
    config = {
        "version": 2,
        "active_instance_index": 0,
        "game_instances": [],
        "downloads_folder": None,
        "smapi_log_path": None,
    }

    # Auto-detect game instances
    instances = discover_game_instances()
    for inst in instances:
        config["game_instances"].append({
            "game_path": str(inst["game_path"]),
            "mods_path": str(inst["mods_path"]),
            "source": inst["source"],
            "label": inst["game_path"].name,  # e.g. "Stardew Valley"
        })

    # Auto-detect downloads folder
    downloads = detect_downloads_folder()
    if downloads:
        config["downloads_folder"] = str(downloads)

    # Auto-detect SMAPI log (system-wide, not per-instance)
    log_path = detect_smapi_log_path()
    if log_path:
        config["smapi_log_path"] = str(log_path)

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
    if "version" not in config:
        config["version"] = 2

    if "game_instances" not in config:
        config["game_instances"] = []

    if "active_instance_index" not in config:
        config["active_instance_index"] = 0

    if "downloads_folder" not in config:
        downloads = detect_downloads_folder()
        config["downloads_folder"] = str(downloads) if downloads else None

    # Upgrade from v1: move log_path from per-instance to system-wide
    if "smapi_log_path" not in config:
        log_path = detect_smapi_log_path()
        config["smapi_log_path"] = str(log_path) if log_path else None
        # Clean old log_path from instances if present
        for inst in config.get("game_instances", []):
            inst.pop("log_path", None)
        config["version"] = 2

    # Clamp active index to valid range
    if config["game_instances"]:
        max_index = len(config["game_instances"]) - 1
        config["active_instance_index"] = min(
            config["active_instance_index"], max_index
        )
    else:
        config["active_instance_index"] = 0

    return config


# ─── Convenience accessors ────────────────────────────────────────

def get_active_instance(config: dict) -> Optional[dict]:
    """Return the currently active game instance dict, or None."""
    instances = config.get("game_instances", [])
    index = config.get("active_instance_index", 0)
    if instances and 0 <= index < len(instances):
        return instances[index]
    return None


def get_mods_path(config: dict) -> Optional[Path]:
    """Return the Mods folder Path for the active game instance."""
    instance = get_active_instance(config)
    if instance and instance.get("mods_path"):
        return Path(instance["mods_path"])
    return None


def get_log_path(config: dict) -> Optional[Path]:
    """Return the SMAPI log Path (system-wide, not per-instance)."""
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


def add_game_instance(config: dict, game_path: str, label: Optional[str] = None) -> dict:
    """
    Manually add a game instance to the config.
    Used when auto-detect misses an installation and the user browses to it.
    """
    game = Path(game_path)
    instance = {
        "game_path": str(game),
        "mods_path": str(game / "Mods"),
        "source": "manual",
        "label": label or game.name,
    }
    config["game_instances"].append(instance)
    # Set the newly added instance as active
    config["active_instance_index"] = len(config["game_instances"]) - 1
    return config


def set_active_instance(config: dict, index: int) -> dict:
    """Set which game instance is active by index."""
    instances = config.get("game_instances", [])
    if 0 <= index < len(instances):
        config["active_instance_index"] = index
    return config


def update_downloads_path(config: dict, path: str) -> dict:
    """Override the downloads folder path."""
    config["downloads_folder"] = path
    return config
