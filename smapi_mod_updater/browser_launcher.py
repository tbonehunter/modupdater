# browser_launcher.py - Browser tab launcher for SMAPI Mod Updater
"""
Phase 2: Open Nexus Mods download pages in the user's default browser.

Opens the Files tab for each selected mod so the user can click
"Slow Download" without having to navigate to each mod page manually.

Includes a small delay between tabs to avoid overwhelming the browser
or triggering Nexus rate limiting.
"""

import os
import shutil
import subprocess
import sys
import time
import webbrowser
from typing import Callable, Optional

from log_parser import get_files_tab_url


# Delay between opening tabs (seconds).
# Too fast and the browser chokes or Nexus may throttle.
# Too slow and the user is waiting for no reason.
TAB_OPEN_DELAY = 0.5


def _open_url(url: str) -> None:
    """
    Open a URL in the user's default browser, raising on failure.

    webbrowser.open() on Linux merely launches xdg-open (or similar) as a
    subprocess and reports success as soon as it starts, even if it exits
    with an error (e.g. no display session, no MIME association) — so we
    call xdg-open directly here to surface real failures instead of a
    false "opened" result.
    """
    if sys.platform.startswith("linux") and shutil.which("xdg-open"):
        if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            raise RuntimeError("no graphical session detected (DISPLAY/WAYLAND_DISPLAY not set)")
        result = subprocess.run(
            ["xdg-open", url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=5,
        )
        if result.returncode != 0:
            stderr = result.stderr.decode(errors="replace").strip()
            raise RuntimeError(stderr or f"xdg-open exited with code {result.returncode}")
        return

    if not webbrowser.open(url, new=2):
        raise RuntimeError("no browser controller could open the URL")


def open_download_pages(
    mods: list[dict],
    delay: float = TAB_OPEN_DELAY,
    on_progress: Optional[Callable[[str, int, int], None]] = None,
) -> dict:
    """
    Open Nexus Files tab pages in the default browser for each mod.

    Args:
        mods:        List of mod dicts (from log_parser.parse_smapi_log).
                     Each must have 'url', 'name', and 'is_nexus' keys.
        delay:       Seconds to wait between opening tabs.
        on_progress: Optional callback(mod_name, current_index, total)
                     called after each tab is opened.

    Returns:
        Dict with results:
          - opened:  int   Number of tabs successfully opened
          - skipped: int   Number of non-Nexus mods skipped
          - errors:  list  List of (mod_name, error_message) tuples
    """
    results = {
        "opened": 0,
        "skipped": 0,
        "errors": [],
    }

    total = len(mods)

    for i, mod in enumerate(mods):
        name = mod.get("name", "Unknown")

        # Skip non-Nexus mods (we can only auto-open Nexus URLs)
        if not mod.get("is_nexus", False):
            results["skipped"] += 1
            if on_progress:
                on_progress(f"Skipped {name} (not on Nexus)", i + 1, total)
            continue

        # Build the Files tab URL
        url = get_files_tab_url(mod["url"])

        try:
            _open_url(url)
            results["opened"] += 1
            if on_progress:
                on_progress(f"Opened {name}", i + 1, total)
        except Exception as e:
            results["errors"].append((name, str(e)))
            if on_progress:
                on_progress(f"Error opening {name}: {e}", i + 1, total)

        # Delay between tabs (skip after the last one)
        if i < total - 1 and delay > 0:
            time.sleep(delay)

    return results
