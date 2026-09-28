# web_server.py - Local Flask server for SMAPI Mod Updater
"""
Serves the browser-based UI and exposes the same actions the old
CustomTkinter GUI's buttons triggered, over HTTP + Server-Sent Events.

Replaces gui.py. Every other module (log_parser, backup_manager,
download_watcher, config_manager, browser_launcher, platform_utils,
session_logger) is untouched — they were already callback-driven and
UI-agnostic, so this module just wires their callbacks to SSE
broadcasts instead of Tk widget updates.

Architecture:
  AppState   - Holds config, the session logger, the current mod list
               (each entry tagged with a stable "id" and a live
               "status"), the active DownloadWatcher (if any), the set
               of subscriber queues used to fan out SSE events, and
               the pending backup-failure decisions awaiting a browser
               response (see request_backup_decision).
  create_app - Builds the Flask app and wires routes against an
               AppState instance. Returns (app, state) so main.py can
               run initial_load() before starting the server.

SSE event types pushed to /api/events:
  "log"            {"message": str}             - one session-log line
  "mod_status"     {"id": str, "status": str}    - one row's status changed
  "issues"         {"count": int}                - issue count changed
  "watch_complete" {}                             - watcher finished/stopped
  "backup_prompt"  {"request_id", "mod", "folder"} - backup failed under the
                                                      "prompt" policy; the page
                                                      must answer via
                                                      /api/backup-decision
  "state"          full state dict                - mod list was replaced
                                                      (reload / settings / steamos-select)
"""

import json
import os
import queue
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

from flask import Flask, Response, jsonify, render_template, request

from browser_launcher import open_download_pages
from config_manager import (
    get_backup_failure_policy,
    get_downloads_path,
    get_log_path,
    get_mods_path,
    load_config,
    refresh_mods_path,
    save_config,
    set_backup_failure_policy,
    update_downloads_path,
)
from download_watcher import DownloadWatcher, find_existing_download
from log_parser import parse_smapi_log
from platform_utils import find_steamos_smapi_logs, get_steam_app_name, is_steamos
from session_logger import SessionLogger
from version import VERSION

DEFAULT_PORT = 5317

# How long a "prompt" backup-failure decision waits for the browser to
# answer before giving up and aborting that mod's install, same as if
# no one were watching.
BACKUP_DECISION_TIMEOUT = 300.0


def _bundle_dir() -> Path:
    """
    Return the directory holding templates/ and static/.

    Running from source: next to this file.
    Running as a PyInstaller bundle (onefile or onedir): sys._MEIPASS,
    which PyInstaller sets in both modes to point at the extracted/
    collected data directory.
    """
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).parent


# ─── Application State ─────────────────────────────────────────────

class AppState:
    """
    Shared, thread-safe state for the running server.

    Mod entries carry a stable "id" (the Nexus mod_id as a string, or
    "idx<N>" for the rare non-Nexus log entry that has none) so the
    browser can reference a row without relying on mod_id being
    present — the same limitation the old GUI had for non-Nexus rows,
    just made explicit instead of silently dropping status updates.
    """

    def __init__(self):
        self.lock = threading.Lock()
        self.config: dict = load_config()
        self.logger = SessionLogger()
        self.mods: list[dict] = []
        self.watcher: Optional[DownloadWatcher] = None

        self._subscribers: list[queue.Queue] = []
        self._sub_lock = threading.Lock()

        # Pending "prompt"-policy backup-failure decisions, keyed by
        # request_id. Each entry is {"event": threading.Event, "decision": str}.
        # The watcher thread blocks on the Event; resolve_backup_decision()
        # (called from the /api/backup-decision route) sets it.
        self._pending_decisions: dict[str, dict] = {}
        self._decision_lock = threading.Lock()

    # ─── SSE fan-out ────────────────────────────────────────────

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue()
        with self._sub_lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue):
        with self._sub_lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def broadcast(self, event: str, data: dict):
        payload = f"event: {event}\ndata: {json.dumps(data)}\n\n"
        with self._sub_lock:
            subs = list(self._subscribers)
        for q in subs:
            q.put(payload)

    # ─── Mod list ───────────────────────────────────────────────

    def set_mods(self, mods: list[dict]):
        """Replace the mod list (on load/reload), resetting all statuses."""
        with self.lock:
            self.mods = []
            for i, mod in enumerate(mods):
                entry = dict(mod)
                mod_id = entry.get("mod_id")
                entry["id"] = str(mod_id) if mod_id is not None else f"idx{i}"
                entry["status"] = "pending"
                self.mods.append(entry)

    def selected_mods(self, ids: list[str]) -> list[dict]:
        """Return snapshot dicts for the given row ids, in list order."""
        wanted = set(ids)
        with self.lock:
            return [dict(m) for m in self.mods if m["id"] in wanted]

    def set_mod_status(self, mod_id: Optional[str], status: str):
        """Update one row's status by id and broadcast the change."""
        if mod_id is None:
            return
        with self.lock:
            for m in self.mods:
                if m["id"] == mod_id:
                    m["status"] = status
                    break
        self.broadcast("mod_status", {"id": mod_id, "status": status})

    def to_dict(self) -> dict:
        """Full state snapshot sent as the initial payload and after "state" events."""
        with self.lock:
            mods_snapshot = [dict(m) for m in self.mods]

        mods_path = get_mods_path(self.config)
        downloads_path = get_downloads_path(self.config)
        log_path = get_log_path(self.config)

        return {
            "mods": mods_snapshot,
            "mods_path": str(mods_path) if mods_path else None,
            "downloads_path": str(downloads_path) if downloads_path else None,
            "log_path": str(log_path) if log_path else None,
            "is_steamos": is_steamos(),
            "watching": bool(self.watcher and self.watcher.is_running),
            "issue_count": self.logger.issue_count,
            "backup_failure_policy": get_backup_failure_policy(self.config),
        }

    # ─── Backup-failure decisions ("prompt" policy) ──────────────

    def request_backup_decision(self, mod_name: str, folder_name: str) -> str:
        """
        Block the calling (watcher) thread until the browser answers a
        backup-failure prompt, or BACKUP_DECISION_TIMEOUT seconds pass
        (defaults to "abort" either way if nothing usable comes back).
        """
        request_id = str(uuid.uuid4())
        event = threading.Event()
        with self._decision_lock:
            self._pending_decisions[request_id] = {"event": event, "decision": "abort"}

        self.broadcast(
            "backup_prompt",
            {"request_id": request_id, "mod": mod_name, "folder": folder_name},
        )

        event.wait(BACKUP_DECISION_TIMEOUT)

        with self._decision_lock:
            entry = self._pending_decisions.pop(request_id, None)
        return entry["decision"] if entry else "abort"

    def resolve_backup_decision(self, request_id: str, decision: str) -> bool:
        """Called from /api/backup-decision. Returns False if the request_id is unknown/expired."""
        if decision not in ("skip_backup", "abort"):
            decision = "abort"
        with self._decision_lock:
            entry = self._pending_decisions.get(request_id)
            if entry is None:
                return False
            entry["decision"] = decision
            entry["event"].set()
        return True


# ─── Shared reload logic ───────────────────────────────────────────

def _reload_mods(state: AppState):
    """Re-parse the SMAPI log for the currently configured path and broadcast the new state."""
    log_path = get_log_path(state.config)
    if log_path is None or not log_path.is_file():
        state.set_mods([])
        state.logger.warning(
            "SMAPI log not found. Run SMAPI once, or set the path in Settings."
        )
    else:
        mods = parse_smapi_log(log_path)
        state.set_mods(mods)
        if mods:
            state.logger.info(f"Loaded {len(mods)} available updates from SMAPI log.")
        else:
            state.logger.info("SMAPI log parsed — no updates available.")

    state.broadcast("state", state.to_dict())


def _list_dirs(path_str: Optional[str]) -> dict:
    """
    List subdirectories of a folder for the in-page folder browser
    (the fallback when a path isn't auto-detected — see platform_utils
    for the auto-detection this only backstops).

    Returns the resolved path, its parent (None at the filesystem
    root), and the names of its visible subdirectories, sorted.
    Falls back to the user's home directory if the given path is
    missing or not a directory.
    """
    p = Path(path_str) if path_str else Path.home()
    if not p.is_dir():
        p = Path.home()

    try:
        entries = sorted(
            (c.name for c in p.iterdir() if c.is_dir() and not c.name.startswith(".")),
            key=str.lower,
        )
    except OSError:
        entries = []

    parent = str(p.parent) if p.parent != p else None
    return {"path": str(p), "parent": parent, "entries": entries}


def initial_load(state: AppState):
    """
    Run once at startup: SteamOS auto-detection (mirrors the old GUI's
    _check_steamos), then the first log parse. Call this before the
    Flask server starts serving requests.
    """
    if is_steamos():
        state.logger.info("SteamOS detected.")
        log_path = get_log_path(state.config)
        if not (log_path and log_path.is_file()):
            candidates = find_steamos_smapi_logs()
            if len(candidates) == 1:
                state.config["smapi_log_path"] = str(candidates[0])
                refresh_mods_path(state.config)
                save_config(state.config)
                state.logger.success(f"SMAPI log found automatically: {candidates[0]}")
            elif len(candidates) == 0:
                state.logger.warning(
                    "Couldn't find your SMAPI log automatically. Run the game once "
                    "through Steam, then click Reload — or open Settings to browse "
                    "for it manually."
                )
            # else: multiple candidates — the page fetches /api/steamos-candidates
            # and prompts the user to pick one; nothing to do here.

    _reload_mods(state)


# ─── App factory ────────────────────────────────────────────────────

def create_app() -> tuple[Flask, AppState]:
    base_dir = _bundle_dir()
    app = Flask(
        __name__,
        template_folder=str(base_dir / "templates"),
        static_folder=str(base_dir / "static"),
    )
    state = AppState()

    # Route session-log output and issue-count changes to connected browsers
    state.logger.set_gui_callback(lambda msg: state.broadcast("log", {"message": msg}))
    state.logger.set_issue_callback(
        lambda: state.broadcast("issues", {"count": state.logger.issue_count})
    )

    # ─── Page ───────────────────────────────────────────────────

    @app.route("/")
    def index():
        return render_template("index.html", version=VERSION)

    # ─── State ──────────────────────────────────────────────────

    @app.route("/api/state")
    def api_state():
        return jsonify(state.to_dict())

    @app.route("/api/reload", methods=["POST"])
    def api_reload():
        state.logger.info("Reloading SMAPI log...")
        refresh_mods_path(state.config)
        save_config(state.config)
        _reload_mods(state)
        return jsonify(state.to_dict())

    # ─── Settings ───────────────────────────────────────────────

    @app.route("/api/settings", methods=["GET"])
    def api_settings_get():
        return jsonify(
            {
                "smapi_log_path": state.config.get("smapi_log_path"),
                "downloads_folder": state.config.get("downloads_folder"),
                "mods_path": state.config.get("mods_path"),
                "backup_failure_policy": get_backup_failure_policy(state.config),
            }
        )

    @app.route("/api/settings", methods=["POST"])
    def api_settings_post():
        body = request.get_json(silent=True) or {}

        log = (body.get("smapi_log_path") or "").strip()
        if log:
            state.config["smapi_log_path"] = log
            refresh_mods_path(state.config)

        downloads = (body.get("downloads_folder") or "").strip()
        if downloads:
            update_downloads_path(state.config, downloads)

        policy = body.get("backup_failure_policy")
        if policy:
            set_backup_failure_policy(state.config, policy)

        save_config(state.config)
        state.logger.info("Settings saved.")
        _reload_mods(state)
        return jsonify(state.to_dict())

    # ─── Folder browser (fallback for un-detected paths) ────────

    @app.route("/api/browse")
    def api_browse():
        path = request.args.get("path")
        return jsonify(_list_dirs(path))

    # ─── SteamOS log picker ─────────────────────────────────────

    @app.route("/api/steamos-candidates")
    def api_steamos_candidates():
        if not is_steamos():
            return jsonify({"candidates": []})
        candidates = find_steamos_smapi_logs()
        return jsonify(
            {
                "candidates": [
                    {"path": str(p), "name": get_steam_app_name(p) or str(p)}
                    for p in candidates
                ]
            }
        )

    @app.route("/api/steamos-select", methods=["POST"])
    def api_steamos_select():
        body = request.get_json(silent=True) or {}
        path = (body.get("path") or "").strip()
        if not path:
            return jsonify({"error": "path is required"}), 400

        state.config["smapi_log_path"] = path
        refresh_mods_path(state.config)
        save_config(state.config)
        state.logger.success(f"SMAPI log set: {path}")
        _reload_mods(state)
        return jsonify(state.to_dict())

    # ─── Phase 2: open download pages ───────────────────────────

    @app.route("/api/open-pages", methods=["POST"])
    def api_open_pages():
        body = request.get_json(silent=True) or {}
        ids = body.get("ids", [])

        selected = [m for m in state.selected_mods(ids) if m["status"] != "installed"]
        if not selected:
            state.logger.warning("No mods to open (all selected mods already installed).")
            return jsonify({"ok": True, "count": 0})

        # Skip any mod that already has a matching archive sitting in
        # Downloads, instead of opening yet another Nexus tab for it —
        # that's what piles up "(1)", "(2)", "(3)" duplicate downloads.
        downloads_path = get_downloads_path(state.config)
        to_open = selected
        if downloads_path and downloads_path.is_dir():
            to_open = []
            already_downloaded = []
            for m in selected:
                if find_existing_download(downloads_path, m):
                    already_downloaded.append(m)
                else:
                    to_open.append(m)
            if already_downloaded:
                names = ", ".join(m["name"] for m in already_downloaded)
                state.logger.info(f"Already downloaded, skipping browser: {names}")

        if not to_open:
            return jsonify({"ok": True, "count": 0})

        state.logger.info(f"Opening {len(to_open)} download pages...")

        def _worker():
            def _progress(msg, current, total):
                state.logger.info(f"  ({current}/{total}) {msg}")

            results = open_download_pages(to_open, on_progress=_progress)
            state.logger.info(
                f"Done: {results['opened']} opened, "
                f"{results['skipped']} skipped, "
                f"{len(results['errors'])} errors."
            )

        threading.Thread(target=_worker, daemon=True).start()
        return jsonify({"ok": True, "count": len(to_open)})

    # ─── Phase 3: watch & install ────────────────────────────────

    @app.route("/api/watch/start", methods=["POST"])
    def api_watch_start():
        if state.watcher and state.watcher.is_running:
            return jsonify({"error": "already watching"}), 409

        body = request.get_json(silent=True) or {}
        ids = body.get("ids", [])
        selected = state.selected_mods(ids)
        if not selected:
            state.logger.warning("No mods selected.")
            return jsonify({"error": "no mods selected"}), 400

        downloads_path = get_downloads_path(state.config)
        mods_path = get_mods_path(state.config)

        if not downloads_path or not downloads_path.is_dir():
            state.logger.error("Downloads folder not found. Check Settings.")
            return jsonify({"error": "downloads folder not found"}), 400

        if not mods_path or not mods_path.is_dir():
            state.logger.error("Mods folder not found. Check Settings or game instance.")
            return jsonify({"error": "mods folder not found"}), 400

        for m in selected:
            state.set_mod_status(m["id"], "downloading")

        def _on_mod_installed(mod, message):
            state.logger.success(message)
            state.set_mod_status(mod.get("id"), "installed")

        def _on_mod_error(mod, message):
            state.logger.error(message)
            state.set_mod_status(mod.get("id"), "error")

        def _on_status(message):
            state.logger.info(message)

        def _on_complete():
            if state.watcher:
                state.watcher.stop()
                state.watcher = None
            state.broadcast("watch_complete", {})

        def _on_issue(mod_name, reason, detail):
            state.logger.add_issue(mod_name, reason, detail)

        def _on_backup_failure(mod_name, folder_name):
            policy = get_backup_failure_policy(state.config)
            if policy == "skip_backup":
                state.logger.warning(
                    f"Backup failed for {folder_name} — proceeding without a "
                    f"backup (per Settings)."
                )
                return "skip_backup"
            if policy == "prompt":
                return state.request_backup_decision(mod_name, folder_name)
            return "abort"

        state.watcher = DownloadWatcher(
            downloads_path=downloads_path,
            mods_path=mods_path,
            pending_mods=selected,
            on_mod_installed=_on_mod_installed,
            on_mod_error=_on_mod_error,
            on_status=_on_status,
            on_complete=_on_complete,
            on_issue=_on_issue,
            on_backup_failure=_on_backup_failure,
        )
        state.watcher.start()
        state.logger.info(f"Watching for {len(selected)} mod downloads...")
        return jsonify({"watching": True})

    @app.route("/api/watch/stop", methods=["POST"])
    def api_watch_stop():
        if state.watcher and state.watcher.is_running:
            state.watcher.stop()
            state.watcher = None
            state.logger.info("Stopped watching.")
        state.broadcast("watch_complete", {})
        return jsonify({"watching": False})

    # ─── Backup-failure decisions ("prompt" policy) ──────────────

    @app.route("/api/backup-decision", methods=["POST"])
    def api_backup_decision():
        body = request.get_json(silent=True) or {}
        request_id = body.get("request_id", "")
        decision = body.get("decision", "abort")

        if not state.resolve_backup_decision(request_id, decision):
            return jsonify({"error": "unknown or expired request_id"}), 404
        return jsonify({"ok": True})

    # ─── Issues ─────────────────────────────────────────────────

    @app.route("/api/issues")
    def api_issues():
        return jsonify({"issues": state.logger.issues})

    # ─── Live updates ───────────────────────────────────────────

    @app.route("/api/events")
    def api_events():
        def stream():
            q = state.subscribe()
            try:
                yield "retry: 2000\n\n"
                while True:
                    try:
                        payload = q.get(timeout=15)
                    except queue.Empty:
                        payload = ": keep-alive\n\n"
                    yield payload
            finally:
                state.unsubscribe(q)

        return Response(
            stream(),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # ─── Shutdown ───────────────────────────────────────────────

    @app.route("/api/quit", methods=["POST"])
    def api_quit():
        if state.watcher and state.watcher.is_running:
            state.watcher.stop()
        save_config(state.config)

        def _die():
            time.sleep(0.3)
            os._exit(0)

        threading.Thread(target=_die, daemon=True).start()
        return jsonify({"ok": True})

    return app, state
