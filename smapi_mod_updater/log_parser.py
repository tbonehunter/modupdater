# log_parser.py - SMAPI log parser for SMAPI Mod Updater
"""
Phase 1: Parse SMAPI's log file to extract the list of available mod updates.

SMAPI log lines have a timestamp and severity prefix:
  [10:07:05 ALERT SMAPI] You can update 18 mods:
  [10:07:05 ALERT SMAPI]    Automate 2.6.0: https://www.nexusmods.com/stardewvalley/mods/1063 (you have 2.5.0)
  [10:07:05 ALERT SMAPI]    (CP) Stoner Valley 1.2.8: https://... (you have 1.2.3)

The parser strips the bracketed prefix, then matches the mod update content.

Returns a list of mod update dicts ready for the GUI checklist.
"""

import re
from pathlib import Path
from typing import Optional


# Matches the bracketed prefix at the start of every SMAPI log line.
# Examples:
#   [10:07:05 ALERT SMAPI]
#   [SMAPI]
# Captures everything after the closing bracket.
_PREFIX_PATTERN = re.compile(
    r"^\[.*?SMAPI\]\s*(.*)"
)

# After stripping the prefix, matches a mod update line:
#   (CP) Stoner Valley 1.2.8: https://www.nexusmods.com/...mods/32742 (you have 1.2.3)
#   Automate 2.6.0: https://www.nexusmods.com/...mods/1063 (you have 2.5.0)
#
# Regex breakdown:
#   (?:\(CP\)\s+)?   - Optional Content Pack prefix "(CP) "
#   (.+?)            - Mod name (non-greedy)
#   \s+              - Whitespace separator
#   ([\d.]+)         - Available version number
#   :\s+             - Colon and space
#   (https?://\S+)   - Download URL
#   \s+\(you have\s+ - " (you have "
#   ([\d.]+)         - Current installed version
#   \)               - Closing paren
_MOD_UPDATE_PATTERN = re.compile(
    r"(?:\(CP\)\s+)?"
    r"(.+?)"
    r"\s+([\d.]+)"
    r":\s+(https?://\S+)"
    r"\s+\(you have\s+([\d.]+)\)$"
)

# Extract Nexus mod ID from URL like:
#   https://www.nexusmods.com/stardewvalley/mods/1063
_NEXUS_MOD_ID_PATTERN = re.compile(
    r"nexusmods\.com/stardewvalley/mods/(\d+)"
)


def _extract_nexus_mod_id(url: str) -> Optional[int]:
    """Pull the numeric mod ID from a Nexus Mods URL."""
    match = _NEXUS_MOD_ID_PATTERN.search(url)
    if match:
        return int(match.group(1))
    return None


def _strip_smapi_prefix(line: str) -> Optional[str]:
    """
    Strip the SMAPI log prefix from a line.

    Returns the content after the prefix, or None if the line
    doesn't have a SMAPI prefix.
    """
    match = _PREFIX_PATTERN.match(line)
    if match:
        return match.group(1)
    return None


def parse_smapi_log(log_path: Path) -> list[dict]:
    """
    Parse a SMAPI log file and extract all available mod updates.

    Args:
        log_path: Path to SMAPI-latest.txt

    Returns:
        List of dicts, each containing:
          - name:       str   Mod display name
          - mod_id:     int   Nexus mod ID (from URL), or None if not Nexus
          - current:    str   Currently installed version
          - available:  str   Available version on Nexus
          - url:        str   Full download page URL
          - is_nexus:   bool  Whether this is a Nexus Mods link
    """
    if not log_path.is_file():
        return []

    updates = []
    seen_mod_ids = set()
    in_update_section = False

    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []

    for line in lines:
        # Detect the start of the update section
        if "You can update" in line and "SMAPI" in line:
            in_update_section = True
            continue

        # If we're in the update section, parse update lines
        if in_update_section:
            # Strip the SMAPI prefix to get the content
            content = _strip_smapi_prefix(line)

            if content is None:
                # Non-SMAPI line — we've left the update section
                in_update_section = False
                continue

            # Try matching the content as a mod update line
            # Content will be like:
            #   "   Automate 2.6.0: https://... (you have 2.5.0)"
            content = content.strip()

            if not content:
                # Blank content after prefix — still in section, skip
                continue

            match = _MOD_UPDATE_PATTERN.match(content)
            if match:
                name = match.group(1).strip()
                available = match.group(2)
                url = match.group(3)
                current = match.group(4)

                mod_id = _extract_nexus_mod_id(url)
                is_nexus = mod_id is not None

                # Deduplicate by mod_id (some mods appear twice,
                # e.g. "StonerValley" and "(CP) Stoner Valley" sharing an ID)
                if mod_id is not None and mod_id in seen_mod_ids:
                    continue
                if mod_id is not None:
                    seen_mod_ids.add(mod_id)

                updates.append({
                    "name": name,
                    "mod_id": mod_id,
                    "current": current,
                    "available": available,
                    "url": url,
                    "is_nexus": is_nexus,
                })
            else:
                # SMAPI line that doesn't match mod pattern — section is over
                in_update_section = False

    return updates


def get_files_tab_url(url: str) -> str:
    """
    Convert a Nexus mod page URL to its Files tab URL.

    Input:  https://www.nexusmods.com/stardewvalley/mods/1063
    Output: https://www.nexusmods.com/stardewvalley/mods/1063?tab=files
    """
    # Strip any existing query params or fragments
    base = url.split("?")[0].split("#")[0].rstrip("/")
    return f"{base}?tab=files"
