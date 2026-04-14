# gui.py - SMAPI Mod Updater GUI
r"""
Main GUI window for the SMAPI Mod Updater.
Uses CustomTkinter for a modern cross-platform interface.

Layout:
  ┌─────────────────────────────────────────┐
  │  SMAPI Mod Updater          [Settings]  │
  │─────────────────────────────────────────│
  │  Mods: D:\Stardew Valley\Mods  [Reload] │
  │  Status: Found 18 mods to update        │
  │─────────────────────────────────────────│
  │  ☑ Automate         2.5.0 → 2.6.0      │
  │  ☑ Content Patcher  2.9.0 → 2.9.1      │
  │  ☑ SpaceCore        1.27.0 → 1.28.4    │
  │  ☐ Debug Mode       1.17.3 → 1.17.4    │
  │  ...                                    │
  │─────────────────────────────────────────│
  │  [Select All] [Deselect All]            │
  │  [Open Download Pages]  [Watch & Install]│
  │─────────────────────────────────────────│
  │  Session Log:          [View Issues (2)] │
  │  > Ready.                               │
  └─────────────────────────────────────────┘
"""

import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog
from typing import Optional

import customtkinter as ctk

from config_manager import (
    get_downloads_path,
    get_log_path,
    get_mods_path,
    load_config,
    refresh_mods_path,
    save_config,
    update_downloads_path,
)
from log_parser import parse_smapi_log
from browser_launcher import open_download_pages
from download_watcher import DownloadWatcher
from session_logger import SessionLogger


class ModCheckboxRow(ctk.CTkFrame):
    """A single row in the mod checklist: checkbox + name + version info + status."""

    def __init__(self, parent, mod_data: dict, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.mod_data = mod_data
        self.is_selected = ctk.BooleanVar(value=True)
        self.status = "pending"  # pending | downloading | installed | error

        self.grid_columnconfigure(1, weight=1)

        # Checkbox
        self.checkbox = ctk.CTkCheckBox(
            self,
            text="",
            variable=self.is_selected,
            width=24,
            checkbox_width=20,
            checkbox_height=20,
        )
        self.checkbox.grid(row=0, column=0, padx=(4, 4), pady=2)

        # Mod name label
        self.name_label = ctk.CTkLabel(
            self,
            text=mod_data["name"],
            anchor="w",
            font=ctk.CTkFont(size=13),
        )
        self.name_label.grid(row=0, column=1, padx=(0, 8), pady=2, sticky="w")

        # Version info: current → available
        version_text = f"{mod_data['current']}  →  {mod_data['available']}"
        self.version_label = ctk.CTkLabel(
            self,
            text=version_text,
            anchor="e",
            font=ctk.CTkFont(size=12, family="Courier"),
        )
        self.version_label.grid(row=0, column=2, padx=(8, 4), pady=2, sticky="e")

        # Status indicator
        self.status_label = ctk.CTkLabel(
            self,
            text="",
            anchor="e",
            width=28,
            font=ctk.CTkFont(size=14),
        )
        self.status_label.grid(row=0, column=3, padx=(4, 8), pady=2, sticky="e")

    def set_status(self, status: str):
        """Update the visual status indicator for this mod row."""
        self.status = status
        indicators = {
            "pending": ("", "gray"),
            "downloading": ("...", "yellow"),
            "installed": ("OK", "green"),
            "error": ("!!", "red"),
            "skipped": ("--", "gray"),
        }
        text, color = indicators.get(status, ("", "gray"))
        self.status_label.configure(text=text, text_color=color)


class IssuesDialog(ctk.CTkToplevel):
    """Dialog showing a summary of issues encountered during the session."""

    def __init__(self, parent, issues: list[dict]):
        super().__init__(parent)
        self.title("Session Issues")
        self.geometry("620x400")
        self.minsize(480, 300)
        self.transient(parent)
        self.wait_visibility()
        try:
            self.grab_set()
        except tk.TclError:
            pass  # Window not viewable — skip modal grab

        # Close button at bottom
        ctk.CTkButton(self, text="Close", width=100,
                       command=self.destroy).pack(side="bottom", pady=(8, 16))

        # Header
        count = len(issues)
        ctk.CTkLabel(
            self,
            text=f"{count} issue{'s' if count != 1 else ''} this session",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
        ).pack(fill="x", padx=16, pady=(12, 4))

        # Scrollable issue list
        content = ctk.CTkScrollableFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=8, pady=(4, 4))

        if not issues:
            ctk.CTkLabel(content, text="No issues to report.",
                          text_color="gray").pack(padx=16, pady=8)
        else:
            for issue in issues:
                frame = ctk.CTkFrame(content)
                frame.pack(fill="x", padx=8, pady=4)

                # Mod name and reason on one line
                header_text = f"{issue['mod']}  —  {issue['reason']}"
                ctk.CTkLabel(
                    frame, text=header_text, anchor="w",
                    font=ctk.CTkFont(size=13, weight="bold"),
                ).pack(fill="x", padx=12, pady=(8, 2))

                # Detail text
                ctk.CTkLabel(
                    frame, text=issue["detail"], anchor="w",
                    font=ctk.CTkFont(size=11),
                    wraplength=540,
                    justify="left",
                ).pack(fill="x", padx=12, pady=(0, 8))


class SettingsDialog(ctk.CTkToplevel):
    """Settings dialog for overriding auto-detected paths."""

    def __init__(self, parent, config: dict, on_save=None):
        super().__init__(parent)
        self.title("Settings")
        self.geometry("600x480")
        self.minsize(500, 380)
        self.transient(parent)
        self.wait_visibility()
        try:
            self.grab_set()
        except tk.TclError:
            pass  # Window not viewable — skip modal grab

        self._config = config
        self._on_save = on_save

        # ─── Save / Cancel buttons pinned at bottom ───────────
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(side="bottom", fill="x", padx=20, pady=(8, 16))

        ctk.CTkButton(btn_frame, text="Save", width=100,
                       command=self._save).pack(side="right", padx=(8, 0))
        ctk.CTkButton(btn_frame, text="Cancel", width=100,
                       command=self.destroy).pack(side="right")

        # ─── Scrollable content area above buttons ────────────
        content = ctk.CTkScrollableFrame(self, fg_color="transparent")
        content.pack(side="top", fill="both", expand=True, padx=4, pady=(8, 0))

        # SMAPI Log path
        ctk.CTkLabel(content, text="SMAPI Log File:", anchor="w",
                      font=ctk.CTkFont(size=13)).pack(fill="x", padx=16, pady=(8, 2))

        log_frame = ctk.CTkFrame(content, fg_color="transparent")
        log_frame.pack(fill="x", padx=16, pady=(0, 8))
        log_frame.grid_columnconfigure(0, weight=1)

        current_log = config.get("smapi_log_path", "") or ""
        self.log_var = ctk.StringVar(value=current_log)
        ctk.CTkEntry(log_frame, textvariable=self.log_var,
                      font=ctk.CTkFont(size=12)).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkButton(log_frame, text="Browse", width=70,
                       command=self._browse_log).grid(row=0, column=1)

        # Downloads folder
        ctk.CTkLabel(content, text="Downloads Folder:", anchor="w",
                      font=ctk.CTkFont(size=13)).pack(fill="x", padx=16, pady=(8, 2))

        dl_frame = ctk.CTkFrame(content, fg_color="transparent")
        dl_frame.pack(fill="x", padx=16, pady=(0, 8))
        dl_frame.grid_columnconfigure(0, weight=1)

        current_dl = config.get("downloads_folder", "") or ""
        self.dl_var = ctk.StringVar(value=current_dl)
        ctk.CTkEntry(dl_frame, textvariable=self.dl_var,
                      font=ctk.CTkFont(size=12)).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkButton(dl_frame, text="Browse", width=70,
                       command=self._browse_downloads).grid(row=0, column=1)

        # Mods folder (read from SMAPI log, shown for reference)
        mods = config.get("mods_path", "") or "(not detected — run SMAPI once)"
        ctk.CTkLabel(content, text="Mods Folder (from SMAPI log):", anchor="w",
                      font=ctk.CTkFont(size=13)).pack(fill="x", padx=16, pady=(8, 2))
        ctk.CTkLabel(content, text=f"  {mods}", anchor="w",
                      font=ctk.CTkFont(size=11, family="Courier"),
                      text_color="gray").pack(fill="x", padx=16, pady=(0, 8))

    def _browse_downloads(self):
        path = filedialog.askdirectory(title="Select Downloads Folder")
        if path:
            self.dl_var.set(path)

    def _browse_log(self):
        path = filedialog.askopenfilename(
            title="Select SMAPI-latest.txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if path:
            self.log_var.set(path)

    def _save(self):
        # Update SMAPI log path
        log = self.log_var.get().strip()
        if log:
            self._config["smapi_log_path"] = log
            # Re-derive mods path from the (possibly new) log file
            refresh_mods_path(self._config)

        # Update downloads path
        dl = self.dl_var.get().strip()
        if dl:
            update_downloads_path(self._config, dl)

        save_config(self._config)

        if self._on_save:
            self._on_save()

        self.destroy()


class SMAPIModUpdaterGUI(ctk.CTk):
    """Main application window."""

    WINDOW_TITLE = "SMAPI Mod Updater"
    WINDOW_WIDTH = 640
    WINDOW_HEIGHT = 580

    def __init__(self):
        super().__init__()

        # --- Window setup ---
        self.title(self.WINDOW_TITLE)
        self.geometry(f"{self.WINDOW_WIDTH}x{self.WINDOW_HEIGHT}")
        self.minsize(500, 400)

        # Set appearance (follows system dark/light by default)
        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")

        # --- State ---
        self.mod_rows: list[ModCheckboxRow] = []
        self._watcher: Optional[DownloadWatcher] = None
        self._config = load_config()
        self._logger = SessionLogger()

        # --- Build the UI ---
        self._build_header()
        self._build_mods_info()
        self._build_status_bar()
        self._build_mod_list()
        self._build_selection_buttons()
        self._build_action_buttons()
        self._build_log_area()

        # Connect session logger to GUI log display
        self._logger.set_gui_callback(self._log)
        self._logger.set_issue_callback(self._on_issues_changed)

        # --- Initial load ---
        self._load_smapi_log()

        # --- Clean shutdown ---
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ─── UI Construction ──────────────────────────────────────────

    def _build_header(self):
        """Top bar with title and settings button."""
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(12, 0))
        header.grid_columnconfigure(0, weight=1)

        title_label = ctk.CTkLabel(
            header,
            text=self.WINDOW_TITLE,
            font=ctk.CTkFont(size=20, weight="bold"),
            anchor="w",
        )
        title_label.grid(row=0, column=0, sticky="w")

        settings_btn = ctk.CTkButton(
            header,
            text="Settings",
            width=80,
            height=30,
            font=ctk.CTkFont(size=12),
            command=self._on_settings_click,
        )
        settings_btn.grid(row=0, column=1, sticky="e")

    def _build_mods_info(self):
        """Mods folder path display and reload button."""
        info_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_frame.pack(fill="x", padx=16, pady=(4, 0))
        info_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            info_frame, text="Mods:", anchor="w",
            font=ctk.CTkFont(size=12),
        ).grid(row=0, column=0, padx=(0, 8), sticky="w")

        mods_path = get_mods_path(self._config)
        mods_text = str(mods_path) if mods_path else "(not detected — run SMAPI once)"
        self._mods_path_var = ctk.StringVar(value=mods_text)
        ctk.CTkLabel(
            info_frame,
            textvariable=self._mods_path_var,
            anchor="w",
            font=ctk.CTkFont(size=12),
            text_color="gray",
        ).grid(row=0, column=1, sticky="ew", padx=(0, 8))

        reload_btn = ctk.CTkButton(
            info_frame,
            text="Reload",
            width=70,
            height=28,
            font=ctk.CTkFont(size=12),
            command=self._on_reload,
        )
        reload_btn.grid(row=0, column=2, sticky="e")

    def _build_status_bar(self):
        """Status line below header."""
        self.status_var = ctk.StringVar(value="No mods loaded.")
        status_label = ctk.CTkLabel(
            self,
            textvariable=self.status_var,
            font=ctk.CTkFont(size=12),
            text_color="gray",
            anchor="w",
        )
        status_label.pack(fill="x", padx=20, pady=(4, 4))

    def _build_mod_list(self):
        """Scrollable checklist of mods to update."""
        self.mod_list_frame = ctk.CTkScrollableFrame(
            self,
            label_text="Available Updates",
            label_font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.mod_list_frame.pack(fill="both", expand=True, padx=16, pady=(4, 4))
        self.mod_list_frame.grid_columnconfigure(0, weight=1)

    def _build_selection_buttons(self):
        """Select All / Deselect All buttons."""
        sel_frame = ctk.CTkFrame(self, fg_color="transparent")
        sel_frame.pack(fill="x", padx=16, pady=(0, 4))

        select_all_btn = ctk.CTkButton(
            sel_frame,
            text="Select All",
            width=100,
            height=28,
            font=ctk.CTkFont(size=12),
            command=self._on_select_all,
        )
        select_all_btn.pack(side="left", padx=(0, 8))

        deselect_all_btn = ctk.CTkButton(
            sel_frame,
            text="Deselect All",
            width=100,
            height=28,
            font=ctk.CTkFont(size=12),
            command=self._on_deselect_all,
        )
        deselect_all_btn.pack(side="left")

    def _build_action_buttons(self):
        """Primary action buttons: Open Download Pages, Watch & Install."""
        action_frame = ctk.CTkFrame(self, fg_color="transparent")
        action_frame.pack(fill="x", padx=16, pady=(4, 4))
        action_frame.grid_columnconfigure(0, weight=1)
        action_frame.grid_columnconfigure(1, weight=1)

        self.open_pages_btn = ctk.CTkButton(
            action_frame,
            text="Open Download Pages",
            height=36,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._on_open_pages,
        )
        self.open_pages_btn.grid(row=0, column=0, padx=(0, 6), sticky="ew")

        self.watch_install_btn = ctk.CTkButton(
            action_frame,
            text="Watch && Install",
            height=36,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._on_watch_install,
        )
        self.watch_install_btn.grid(row=0, column=1, padx=(6, 0), sticky="ew")

    def _build_log_area(self):
        """Session log display at the bottom with View Issues button."""
        log_header = ctk.CTkFrame(self, fg_color="transparent")
        log_header.pack(fill="x", padx=20, pady=(4, 0))
        log_header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            log_header,
            text="Session Log",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        self._issues_btn = ctk.CTkButton(
            log_header,
            text="View Issues",
            width=100,
            height=24,
            font=ctk.CTkFont(size=11),
            state="disabled",
            command=self._on_view_issues,
        )
        self._issues_btn.grid(row=0, column=1, sticky="e")

        self.log_textbox = ctk.CTkTextbox(
            self,
            height=80,
            font=ctk.CTkFont(size=11, family="Courier"),
            state="disabled",
            activate_scrollbars=True,
        )
        self.log_textbox.pack(fill="x", padx=16, pady=(2, 12))

    # ─── Mod List Population ──────────────────────────────────────

    def _populate_mod_list(self, mods: list[dict]):
        """Clear and rebuild the mod checklist from a list of mod data dicts."""
        # Clear existing rows
        for row in self.mod_rows:
            row.destroy()
        self.mod_rows.clear()

        # Build new rows
        for i, mod in enumerate(mods):
            row = ModCheckboxRow(self.mod_list_frame, mod)
            row.grid(row=i, column=0, sticky="ew", pady=1)
            self.mod_rows.append(row)

        # Update status bar
        count = len(mods)
        if count == 0:
            self.status_var.set("No updates available.")
        else:
            self.status_var.set(f"Found {count} mod{'s' if count != 1 else ''} to update.")

    def _get_selected_mods(self) -> list[dict]:
        """Return mod_data dicts for all checked rows."""
        return [
            row.mod_data for row in self.mod_rows if row.is_selected.get()
        ]

    def _get_row_for_mod(self, mod: dict) -> Optional[ModCheckboxRow]:
        """Find the checkbox row matching a mod dict by mod_id."""
        mod_id = mod.get("mod_id")
        if mod_id is None:
            return None
        for row in self.mod_rows:
            if row.mod_data.get("mod_id") == mod_id:
                return row
        return None

    # ─── Log Loading ──────────────────────────────────────────────

    def _load_smapi_log(self):
        """Parse the SMAPI log for the active game instance and populate the list."""
        log_path = get_log_path(self._config)
        if log_path is None or not log_path.is_file():
            self._populate_mod_list([])
            self._logger.warning(
                "SMAPI log not found. Run SMAPI once, or set the path in Settings."
            )
            return

        mods = parse_smapi_log(log_path)
        self._populate_mod_list(mods)

        if mods:
            self._logger.info(f"Loaded {len(mods)} available updates from SMAPI log.")
        else:
            self._logger.info("SMAPI log parsed — no updates available.")

    # ─── Session Log Display ──────────────────────────────────────

    def _log(self, message: str):
        """Append a message to the session log display (thread-safe)."""
        def _update():
            self.log_textbox.configure(state="normal")
            self.log_textbox.insert("end", f"> {message}\n")
            self.log_textbox.see("end")
            self.log_textbox.configure(state="disabled")

        # Ensure GUI updates happen on the main thread
        try:
            self.after(0, _update)
        except RuntimeError:
            # Window already destroyed
            pass

    def _on_issues_changed(self):
        """Called when the issue count changes — update the button state."""
        def _update():
            count = self._logger.issue_count
            if count > 0:
                self._issues_btn.configure(
                    text=f"View Issues ({count})",
                    state="normal",
                )
            else:
                self._issues_btn.configure(
                    text="View Issues",
                    state="disabled",
                )

        try:
            self.after(0, _update)
        except RuntimeError:
            pass

    def _on_view_issues(self):
        """Open the issues summary dialog."""
        IssuesDialog(self, self._logger.issues)

    def _on_reload(self):
        """Reload the SMAPI log and refresh the Mods path."""
        self._logger.info("Reloading SMAPI log...")
        refresh_mods_path(self._config)
        save_config(self._config)
        self._refresh_mods_display()
        self._load_smapi_log()

    def _refresh_mods_display(self):
        """Update the Mods path label from the current config."""
        mods_path = get_mods_path(self._config)
        text = str(mods_path) if mods_path else "(not detected — run SMAPI once)"
        self._mods_path_var.set(text)

    # ─── Button Handlers ──────────────────────────────────────────

    def _on_settings_click(self):
        """Open settings dialog for path overrides."""
        SettingsDialog(self, self._config, on_save=self._on_settings_saved)

    def _on_settings_saved(self):
        """Called after settings dialog saves successfully."""
        self._config = load_config()
        self._refresh_mods_display()
        self._logger.info("Settings saved.")
        self._load_smapi_log()

    def _on_select_all(self):
        """Check all mod checkboxes."""
        for row in self.mod_rows:
            row.is_selected.set(True)

    def _on_deselect_all(self):
        """Uncheck all mod checkboxes."""
        for row in self.mod_rows:
            row.is_selected.set(False)

    def _on_open_pages(self):
        """Phase 2: Open Nexus download pages for selected, non-installed mods."""
        selected = [
            row.mod_data for row in self.mod_rows
            if row.is_selected.get() and row.status != "installed"
        ]
        if not selected:
            self._logger.warning("No mods to open (all selected mods already installed).")
            return

        self._logger.info(f"Opening {len(selected)} download pages...")

        # Disable button during operation
        self.open_pages_btn.configure(state="disabled")

        def _do_open():
            def _progress(msg, current, total):
                self._logger.info(f"  ({current}/{total}) {msg}")

            results = open_download_pages(selected, on_progress=_progress)

            self._logger.info(
                f"Done: {results['opened']} opened, "
                f"{results['skipped']} skipped, "
                f"{len(results['errors'])} errors."
            )
            # Re-enable button on main thread
            self.after(0, lambda: self.open_pages_btn.configure(state="normal"))

        threading.Thread(target=_do_open, daemon=True).start()

    def _on_watch_install(self):
        """Phase 3: Start/stop watching Downloads folder."""
        # If already watching, stop
        if self._watcher and self._watcher.is_running:
            self._watcher.stop()
            self._watcher = None
            self.watch_install_btn.configure(text="Watch && Install")
            self._logger.info("Stopped watching.")
            return

        selected = self._get_selected_mods()
        if not selected:
            self._logger.warning("No mods selected.")
            return

        downloads_path = get_downloads_path(self._config)
        mods_path = get_mods_path(self._config)

        if not downloads_path or not downloads_path.is_dir():
            self._logger.error("Downloads folder not found. Check Settings.")
            return

        if not mods_path or not mods_path.is_dir():
            self._logger.error("Mods folder not found. Check Settings or game instance.")
            return

        # Mark all selected as pending
        for row in self.mod_rows:
            if row.is_selected.get():
                row.set_status("downloading")

        def _on_mod_installed(mod, message):
            """Callback when a mod is successfully installed."""
            self._logger.success(message)
            row = self._get_row_for_mod(mod)
            if row:
                self.after(0, lambda r=row: r.set_status("installed"))

        def _on_mod_error(mod, message):
            """Callback when a mod installation fails."""
            self._logger.error(message)
            row = self._get_row_for_mod(mod)
            if row:
                self.after(0, lambda r=row: r.set_status("error"))

        def _on_status(message):
            """General status update from the watcher."""
            self._logger.info(message)

        def _on_complete():
            """All mods installed."""
            self.after(0, self._on_watch_complete)

        def _on_issue(mod_name, reason, detail):
            """Record an issue for the View Issues dialog."""
            self._logger.add_issue(mod_name, reason, detail)

        self._watcher = DownloadWatcher(
            downloads_path=downloads_path,
            mods_path=mods_path,
            pending_mods=selected,
            on_mod_installed=_on_mod_installed,
            on_mod_error=_on_mod_error,
            on_status=_on_status,
            on_complete=_on_complete,
            on_issue=_on_issue,
        )
        self._watcher.start()

        # Update button to show it's active
        self.watch_install_btn.configure(text="Stop Watching")
        self._logger.info(f"Watching for {len(selected)} mod downloads...")

    def _on_watch_complete(self):
        """Called when all mods have been installed."""
        self.watch_install_btn.configure(text="Watch && Install")
        if self._watcher:
            self._watcher.stop()
            self._watcher = None

    # ─── Cleanup ──────────────────────────────────────────────────

    def _on_close(self):
        """Clean shutdown: stop watcher, save config, destroy window."""
        if self._watcher and self._watcher.is_running:
            self._watcher.stop()
        save_config(self._config)
        self.destroy()


# ─── Standalone launch for testing ────────────────────────────────

if __name__ == "__main__":
    app = SMAPIModUpdaterGUI()
    app.mainloop()
