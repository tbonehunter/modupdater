# download_watcher.py - Download folder watcher for SMAPI Mod Updater
"""
Phase 3: Watch the Downloads folder for new mod archives, match them
to the update list via manifest.json inspection, and install them.

Supports multi-mod archives where a single zip contains multiple
mod folders (e.g., a SMAPI code mod + a Content Patcher pack).

Workflow:
  1. Scan existing files in Downloads for any matching mod archives
  2. Start monitoring for new .zip files appearing
  3. For each matching archive (existing or new):
     a. Read ALL manifest.json files from inside the archive
     b. Match each to the mod list via Nexus ID or UniqueID
     c. Verify versions match what SMAPI expected
     d. Back up old mod folders
     e. Extract all mod folders into Mods/
     f. Report status back to the GUI

Uses the watchdog library for cross-platform filesystem monitoring,
with a polling fallback if watchdog is unavailable.
"""

import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from backup_manager import (
    backup_mod,
    find_installed_mod_folder,
    get_nexus_id_from_manifest,
    get_unique_id_from_manifest,
    get_version_from_manifest,
    install_all_mods_from_archive,
    read_all_manifests_from_archive,
    read_manifest_from_archive,
)

# How often the polling fallback checks for new files (seconds)
POLL_INTERVAL = 2.0

# How long to wait after a file appears before processing it,
# giving the browser time to finish writing the download
SETTLE_DELAY = 1.5

# File extensions we consider as mod archives
ARCHIVE_EXTENSIONS = {".zip"}


def _versions_equivalent(version_a: str, version_b: str) -> bool:
    """
    Check if two version strings are equivalent, allowing for
    trailing zero differences like "1.12" vs "1.12.0".

    Splits on dots, pads the shorter one with zeros, then compares.
    """
    try:
        parts_a = [int(x) for x in version_a.split(".")]
        parts_b = [int(x) for x in version_b.split(".")]
    except ValueError:
        return False

    # Pad shorter list with zeros
    max_len = max(len(parts_a), len(parts_b))
    parts_a.extend([0] * (max_len - len(parts_a)))
    parts_b.extend([0] * (max_len - len(parts_b)))

    return parts_a == parts_b


class ModMatcher:
    """
    Matches downloaded archives to the list of mods pending update.

    Maintains the update list and tracks which mods have been
    successfully installed, so duplicates are ignored.
    """

    def __init__(self, pending_mods: list[dict]):
        """
        Args:
            pending_mods: List of mod dicts from log_parser, filtered
                          to only the selected (checked) mods.
        """
        # Index by Nexus mod ID for fast lookup
        self._by_nexus_id: dict[int, dict] = {}
        # Index by mod name (lowercase) as last-resort fallback
        self._by_name: dict[str, dict] = {}
        # Track which mods have been handled
        self._installed_ids: set[int] = set()

        for mod in pending_mods:
            mod_id = mod.get("mod_id")
            if mod_id is not None:
                self._by_nexus_id[mod_id] = mod
            name = mod.get("name", "").lower().strip()
            if name:
                self._by_name[name] = mod

    def match(self, manifest: dict) -> Optional[dict]:
        """
        Try to match a manifest from a downloaded archive to a pending mod.

        Returns the matching mod dict, or None if no match found or
        the mod has already been installed.
        """
        # Try Nexus ID match first
        nexus_id = get_nexus_id_from_manifest(manifest)
        if nexus_id is not None:
            if nexus_id in self._installed_ids:
                return None  # Already handled
            if nexus_id in self._by_nexus_id:
                return self._by_nexus_id[nexus_id]

        # Fallback: try matching by mod name from manifest
        name = manifest.get("Name", "").lower().strip()
        if name and name in self._by_name:
            mod = self._by_name[name]
            mod_id = mod.get("mod_id")
            if mod_id is not None and mod_id in self._installed_ids:
                return None
            return mod

        return None

    def mark_installed(self, mod: dict):
        """Mark a mod as successfully installed so it won't be matched again."""
        mod_id = mod.get("mod_id")
        if mod_id is not None:
            self._installed_ids.add(mod_id)

    @property
    def remaining_count(self) -> int:
        """Number of mods still waiting to be installed."""
        return len(self._by_nexus_id) - len(self._installed_ids)

    @property
    def total_count(self) -> int:
        """Total number of mods being tracked."""
        return len(self._by_nexus_id)


class DownloadWatcher:
    """
    Watches a folder for new mod archives and installs them.

    On start, first scans existing files in the Downloads folder for
    any matching mod archives (so previously downloaded files are
    picked up without re-downloading). Then begins monitoring for
    new arrivals.

    Supports two backends:
      - watchdog (preferred): Real-time filesystem events
      - polling (fallback): Periodic directory scans

    The watcher runs in a background thread so the GUI stays responsive.
    """

    def __init__(
        self,
        downloads_path: Path,
        mods_path: Path,
        pending_mods: list[dict],
        on_mod_installed: Optional[Callable[[dict, str], None]] = None,
        on_mod_error: Optional[Callable[[dict, str], None]] = None,
        on_status: Optional[Callable[[str], None]] = None,
        on_complete: Optional[Callable[[], None]] = None,
    ):
        """
        Args:
            downloads_path:   Folder to watch for new downloads
            mods_path:        Stardew Valley Mods folder
            pending_mods:     List of mod dicts to watch for
            on_mod_installed: Callback(mod_dict, message) on successful install
            on_mod_error:     Callback(mod_dict, error_message) on failure
            on_status:        Callback(message) for general status updates
            on_complete:      Callback() when all mods have been installed
        """
        self._downloads_path = downloads_path
        self._mods_path = mods_path
        self._matcher = ModMatcher(pending_mods)
        self._on_mod_installed = on_mod_installed
        self._on_mod_error = on_mod_error
        self._on_status = on_status
        self._on_complete = on_complete

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._start_time: Optional[datetime] = None

        # Track files we've already processed to avoid re-processing
        self._processed_files: set[Path] = set()

    def start(self):
        """Begin by scanning existing files, then watch for new downloads."""
        if self._running:
            return

        self._running = True
        self._start_time = datetime.now()
        self._processed_files.clear()

        self._status(
            f"Watching {self._downloads_path} for {self._matcher.total_count} mod downloads..."
        )

        # Phase 3a: Scan existing files first
        self._scan_existing_files()

        # If all mods were found in existing downloads, we're done
        if self._matcher.remaining_count == 0:
            self._status("All selected mods found in existing downloads!")
            if self._on_complete:
                self._on_complete()
            return

        # Phase 3b: Watch for new arrivals
        # Snapshot current files so the watcher only processes truly new ones
        self._existing_files = set(self._downloads_path.iterdir())

        if self._try_start_watchdog():
            self._status("Using filesystem events for monitoring.")
        else:
            self._status("Using polling for monitoring (watchdog not available).")
            self._thread = threading.Thread(target=self._poll_loop, daemon=True)
            self._thread.start()

    def stop(self):
        """Stop watching."""
        self._running = False
        self._stop_watchdog()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._status("Stopped watching.")

    @property
    def is_running(self) -> bool:
        """Whether the watcher is currently active."""
        return self._running

    # ─── Existing File Scan ───────────────────────────────────────

    def _scan_existing_files(self):
        """
        Scan the Downloads folder for existing zip files that match
        pending mods. Processes them immediately without waiting.
        """
        self._status("Scanning existing downloads for matching mods...")

        existing_zips = sorted(
            (f for f in self._downloads_path.iterdir()
             if f.is_file() and f.suffix.lower() in ARCHIVE_EXTENSIONS),
            key=lambda f: f.stat().st_mtime,
            reverse=True,  # Newest first — more likely to be the right version
        )

        if not existing_zips:
            self._status("No existing zip files found in Downloads.")
            return

        found_count = 0
        for archive_path in existing_zips:
            if self._matcher.remaining_count == 0:
                break  # All mods accounted for

            if archive_path in self._processed_files:
                continue

            # Check if ANY manifest in this archive matches a pending mod
            all_manifests = read_all_manifests_from_archive(archive_path)
            if not all_manifests:
                continue

            # Check primary manifest for a match
            primary = all_manifests[0]["manifest"]
            matched_mod = self._matcher.match(primary)
            if matched_mod is None:
                continue

            # Version check on primary manifest
            mod_version = get_version_from_manifest(primary) or "unknown"
            expected_version = matched_mod.get("available", "")
            if expected_version and mod_version != expected_version:
                if not _versions_equivalent(mod_version, expected_version):
                    continue  # Wrong version, keep looking

            # Found a match — process it
            self._processed_files.add(archive_path)
            found_count += 1
            self._process_archive(archive_path)

        if found_count > 0:
            self._status(
                f"Found {found_count} matching archive(s) in existing downloads. "
                f"{self._matcher.remaining_count} mod(s) still needed."
            )
        else:
            self._status("No matching mods found in existing downloads.")

    # ─── Watchdog Backend ─────────────────────────────────────────

    def _try_start_watchdog(self) -> bool:
        """Try to start monitoring with watchdog. Returns False if unavailable."""
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler

            watcher = self

            class _Handler(FileSystemEventHandler):
                def on_created(self, event):
                    if not event.is_directory:
                        path = Path(event.src_path)
                        watcher._on_new_file(path)

                def on_moved(self, event):
                    # Some browsers download to .part then rename
                    if not event.is_directory:
                        path = Path(event.dest_path)
                        watcher._on_new_file(path)

            self._observer = Observer()
            self._observer.schedule(_Handler(), str(self._downloads_path), recursive=False)
            self._observer.daemon = True
            self._observer.start()
            return True

        except ImportError:
            self._observer = None
            return False

    def _stop_watchdog(self):
        """Stop the watchdog observer if running."""
        if hasattr(self, "_observer") and self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None

    # ─── Polling Backend ──────────────────────────────────────────

    def _poll_loop(self):
        """Periodically scan the downloads folder for new files."""
        while self._running:
            try:
                current_files = set(self._downloads_path.iterdir())
                new_files = current_files - self._existing_files

                for path in new_files:
                    self._on_new_file(path)
                    self._existing_files.add(path)

            except OSError:
                pass

            time.sleep(POLL_INTERVAL)

    # ─── File Processing ──────────────────────────────────────────

    def _on_new_file(self, path: Path):
        """Handle a new file appearing in the downloads folder."""
        if not self._running:
            return

        # Skip if already processed
        if path in self._processed_files:
            return

        # Only process archive files
        if path.suffix.lower() not in ARCHIVE_EXTENSIONS:
            return

        # Skip partial downloads (browsers often use .part, .crdownload, .tmp)
        if path.suffix.lower() in {".part", ".crdownload", ".tmp"}:
            return

        self._processed_files.add(path)

        # Wait for the file to finish writing
        self._wait_for_settle(path)

        # Process in a thread to not block the watcher
        threading.Thread(
            target=self._process_archive,
            args=(path,),
            daemon=True,
        ).start()

    def _wait_for_settle(self, path: Path):
        """
        Wait until a file has stopped growing, indicating the
        download is complete.
        """
        try:
            prev_size = -1
            for _ in range(30):  # Max ~45 seconds wait
                if not path.exists():
                    return
                current_size = path.stat().st_size
                if current_size == prev_size and current_size > 0:
                    return
                prev_size = current_size
                time.sleep(SETTLE_DELAY)
        except OSError:
            pass

    def _process_archive(self, archive_path: Path):
        """
        Process a downloaded archive: identify, match, backup, install.

        Handles multi-mod archives by processing all sub-mods within
        a single zip file.
        """
        self._status(f"Processing: {archive_path.name}")

        # Step 1: Read ALL manifests from archive
        all_manifests = read_all_manifests_from_archive(archive_path)
        if not all_manifests:
            self._status(f"Skipped {archive_path.name} (no manifest.json found)")
            return

        # Step 2: Match primary manifest to pending mods list
        primary = all_manifests[0]["manifest"]
        mod_name = primary.get("Name", "Unknown")
        mod_version = get_version_from_manifest(primary) or "unknown"

        matched_mod = self._matcher.match(primary)
        if matched_mod is None:
            self._status(
                f"Skipped {archive_path.name} ({mod_name}) — "
                f"not in update list or already installed"
            )
            return

        expected_version = matched_mod.get("available", "")
        self._status(
            f"Matched {mod_name} v{mod_version} "
            f"(expected {expected_version})"
        )

        # Step 3: Version verification
        if expected_version and mod_version != expected_version:
            if not _versions_equivalent(mod_version, expected_version):
                self._status(
                    f"Skipped {archive_path.name} — version {mod_version} "
                    f"doesn't match expected {expected_version}"
                )
                return
            else:
                self._status(
                    f"Note: {mod_name} version {mod_version} "
                    f"treated as equivalent to {expected_version}"
                )

        # Step 4: For each sub-mod in the archive, find existing folder
        #         and build folder overrides map
        folder_overrides = {}
        mods_to_backup = []

        for entry in all_manifests:
            manifest = entry["manifest"]
            nexus_id = get_nexus_id_from_manifest(manifest)
            unique_id = get_unique_id_from_manifest(manifest)
            sub_name = manifest.get("Name", "Unknown")

            installed_folder = find_installed_mod_folder(
                self._mods_path, nexus_id=nexus_id, unique_id=unique_id
            )

            if installed_folder:
                # Use the existing folder name so we replace in-place
                if unique_id:
                    folder_overrides[unique_id] = installed_folder.name
                mods_to_backup.append((sub_name, installed_folder))
            else:
                self._status(f"  No existing install for {sub_name} — fresh install.")

        # Step 5: Back up all existing sub-mod folders
        for sub_name, installed_folder in mods_to_backup:
            backup_path = backup_mod(self._mods_path, installed_folder)
            if backup_path:
                self._status(f"  Backed up {installed_folder.name} to .backups/")
            else:
                self._error(
                    matched_mod,
                    f"Failed to back up {installed_folder.name}. Skipping install."
                )
                return

        # Step 6: Extract all sub-mods
        is_multi = len(all_manifests) > 1
        if is_multi:
            self._status(
                f"Multi-mod archive: extracting {len(all_manifests)} mod folders..."
            )

        results = install_all_mods_from_archive(
            archive_path, self._mods_path, folder_overrides
        )

        # Step 7: Report results
        all_success = True
        for result in results:
            sub_name = result["manifest"].get("Name", "Unknown")
            if result["success"]:
                self._status(f"  Installed {sub_name} to {result['folder']}/")
            else:
                self._status(f"  FAILED to install {sub_name}")
                all_success = False

        if all_success and results:
            self._matcher.mark_installed(matched_mod)
            message = f"Installed {mod_name} {mod_version}"
            if is_multi:
                folders = ", ".join(r["folder"] for r in results)
                message += f" ({len(results)} folders: {folders})"
            else:
                message += f" to {results[0]['folder']}/"

            if self._on_mod_installed:
                self._on_mod_installed(matched_mod, message)

            # Check if all mods are done
            remaining = self._matcher.remaining_count
            if remaining == 0:
                self._status("All selected mods have been installed!")
                if self._on_complete:
                    self._on_complete()
            else:
                self._status(f"{remaining} mod(s) remaining.")
        elif not all_success:
            self._error(
                matched_mod,
                f"Some sub-mods in {archive_path.name} failed to install."
            )

    # ─── Callback Helpers ─────────────────────────────────────────

    def _status(self, message: str):
        """Send a status message."""
        if self._on_status:
            self._on_status(message)

    def _error(self, mod: dict, message: str):
        """Report an error for a specific mod."""
        if self._on_mod_error:
            self._on_mod_error(mod, message)
        self._status(f"ERROR: {message}")
