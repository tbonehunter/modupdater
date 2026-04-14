# session_logger.py - Per-session logging for SMAPI Mod Updater
"""
Writes a session log file that records actions taken during a single run.
Overwrites on each new session (does not append across runs).

Also supports a GUI callback so log messages appear in both the file
and the GUI's session log display simultaneously.

Tracks issues (skipped/failed mods) separately so the GUI can present
a clear summary to the user via the "View Issues" dialog.
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

LOG_FILENAME = "smapi_updater_log.txt"


class SessionLogger:
    """
    Manages the per-session log file and optional GUI callback.

    Usage:
        logger = SessionLogger()
        logger.set_gui_callback(some_function)
        logger.info("Updated Automate from 2.5.0 to 2.6.0")
        logger.warning("Version mismatch for SpaceCore")
        logger.error("Failed to extract archive")
        logger.add_issue("SpaceCore", "Version mismatch", "...")
    """

    def __init__(self, log_dir: Optional[Path] = None):
        """
        Initialize the session logger.

        Args:
            log_dir: Directory to write the log file in.
                     Defaults to the directory containing this script.
        """
        if log_dir is None:
            if getattr(sys, 'frozen', False):
                log_dir = Path(sys.executable).parent
            else:
                log_dir = Path(__file__).parent

        self._log_path = log_dir / LOG_FILENAME
        self._gui_callback: Optional[Callable[[str], None]] = None
        self._issue_callback: Optional[Callable[[], None]] = None
        self._issues: list[dict] = []
        self._start_session()

    def _start_session(self):
        """Begin a new session, overwriting any existing log file."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        header = (
            f"SMAPI Mod Updater - Session Log\n"
            f"Started: {timestamp}\n"
            f"{'=' * 50}\n"
        )
        try:
            self._log_path.write_text(header, encoding="utf-8")
        except OSError:
            # If we can't write the log file, continue without it.
            # GUI callback will still work.
            pass

    def set_gui_callback(self, callback: Callable[[str], None]):
        """
        Register a callback function for GUI display.
        The callback receives the formatted message string.
        """
        self._gui_callback = callback

    def set_issue_callback(self, callback: Callable[[], None]):
        """
        Register a callback to notify the GUI when a new issue is added.
        Called after each add_issue() so the GUI can update the button.
        """
        self._issue_callback = callback

    def _write(self, level: str, message: str):
        """Write a log entry to file and GUI."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        file_entry = f"[{timestamp}] [{level}] {message}\n"
        display_entry = f"[{timestamp}] {message}"

        # Write to file
        try:
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(file_entry)
        except OSError:
            pass

        # Send to GUI
        if self._gui_callback:
            self._gui_callback(display_entry)

    def info(self, message: str):
        """Log an informational message."""
        self._write("INFO", message)

    def warning(self, message: str):
        """Log a warning message."""
        self._write("WARN", message)

    def error(self, message: str):
        """Log an error message."""
        self._write("ERROR", message)

    def success(self, message: str):
        """Log a success message (e.g., mod installed)."""
        self._write("OK", message)

    @property
    def log_path(self) -> Path:
        """Return the path to the current log file."""
        return self._log_path

    # ─── Issue Tracking ───────────────────────────────────────────

    def add_issue(self, mod_name: str, reason: str, detail: str):
        """
        Record an issue for the View Issues summary.

        Args:
            mod_name: Display name of the mod (e.g. "Immersive Farm 2 Update")
            reason:   Short category (e.g. "Version mismatch", "No manifest",
                      "Backup failed", "Install failed")
            detail:   Human-readable explanation of what happened
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._issues.append({
            "time": timestamp,
            "mod": mod_name,
            "reason": reason,
            "detail": detail,
        })
        # Also log to file
        self._write("ISSUE", f"{mod_name}: {detail}")
        # Notify GUI so it can update the button count
        if self._issue_callback:
            self._issue_callback()

    @property
    def issues(self) -> list[dict]:
        """Return all recorded issues for the current session."""
        return list(self._issues)

    @property
    def issue_count(self) -> int:
        """Return the number of issues recorded this session."""
        return len(self._issues)

    def clear_issues(self):
        """Clear all recorded issues (e.g. on a fresh reload)."""
        self._issues.clear()
        if self._issue_callback:
            self._issue_callback()
