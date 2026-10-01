# nexus_updater.py - Checks Nexus for a newer release of this tool itself
"""
This tool isn't a SMAPI mod, so SMAPI's own update-check (the thing
that drives every other version comparison in this app) never sees
it. This module fills that one gap: it asks the Nexus API directly
whether a newer version of the SMAPI Mod Updater has been published,
so the page can show a banner rather than the tool going silently
stale.

Testing-build note: this currently authenticates with a personal
Nexus API key (set in Settings), per Nexus's Acceptable Use Policy
for an application still in the testing stage. Once this tool is
registered as a public application with Nexus, this will be
switched to Nexus's SSO flow so end users never handle a raw key —
see https://help.nexusmods.com/article/114-api-acceptable-use-policy
"""

import json
import urllib.error
import urllib.request
from typing import Optional

from version import VERSION

# This tool's own Nexus listing — not a SMAPI mod ID, this app's ID.
NEXUS_GAME_DOMAIN = "stardewvalley"
NEXUS_MOD_ID = 43712
NEXUS_MOD_PAGE_URL = f"https://www.nexusmods.com/{NEXUS_GAME_DOMAIN}/mods/{NEXUS_MOD_ID}"

_MOD_INFO_URL = f"https://api.nexusmods.com/v1/games/{NEXUS_GAME_DOMAIN}/mods/{NEXUS_MOD_ID}.json"
_REQUEST_TIMEOUT = 10  # seconds — a slow/unreachable Nexus shouldn't hang the caller


def _version_tuple(version_str: str) -> tuple:
    """
    Parse a dotted version string into a tuple of ints for comparison,
    e.g. "2.10.1" -> (2, 10, 1). Any non-numeric suffix on a segment
    (like the "-alpha" in "2.1.0-alpha") is dropped from that segment.
    """
    parts = []
    for chunk in version_str.strip().split("."):
        digits = ""
        for ch in chunk:
            if ch.isdigit():
                digits += ch
            else:
                break
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def is_newer(remote_version: str, local_version: str) -> bool:
    """Return True if remote_version is strictly newer than local_version."""
    try:
        return _version_tuple(remote_version) > _version_tuple(local_version)
    except (ValueError, AttributeError):
        return False


def check_for_update(api_key: str, current_version: str = VERSION) -> Optional[dict]:
    """
    Ask Nexus for this tool's currently-published version.

    Returns None if the check couldn't be completed (no key configured,
    network error, unexpected response) or if the published version
    isn't newer than current_version. Returns {"version": str, "url": str}
    when an update is available.

    Never raises — a failed check should be silent, not disruptive to
    startup or page load.
    """
    if not api_key:
        return None

    request = urllib.request.Request(
        _MOD_INFO_URL,
        headers={
            "apikey": api_key,
            # Required by the Nexus API Acceptable Use Policy so they can
            # identify this app's traffic and flag unusual usage patterns.
            "Application-Name": "SMAPIModUpdater",
            "Application-Version": current_version,
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=_REQUEST_TIMEOUT) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError):
        return None

    remote_version = data.get("version")
    if not remote_version or not is_newer(remote_version, current_version):
        return None

    return {"version": remote_version, "url": NEXUS_MOD_PAGE_URL}