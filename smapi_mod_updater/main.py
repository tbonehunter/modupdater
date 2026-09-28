# main.py - SMAPI Mod Updater entry point
"""
SMAPI Mod Updater
A cross-platform tool to streamline updating Stardew Valley mods.
Parses SMAPI's update log, opens Nexus download pages, and
automatically installs downloaded updates.

Runs a local web server and opens it in the default browser instead
of a native GUI window, so there's no per-OS GUI toolkit (Tk/Tcl) to
build or break. The server keeps running after the browser tab is
closed — use the page's Quit button, or close this console window,
to stop it.
"""

import socket
import sys
import threading
import time

from browser_launcher import open_url
from web_server import DEFAULT_PORT, create_app, initial_load


def _find_open_port(preferred: int) -> int:
    """Return the first free port starting at `preferred`, scanning a small range."""
    for port in range(preferred, preferred + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return preferred  # Let Flask raise its own error if even this is taken.


def main():
    """Start the local server, open it in the browser, and block until it stops."""
    app, state = create_app()
    initial_load(state)

    port = _find_open_port(DEFAULT_PORT)
    url = f"http://127.0.0.1:{port}"

    server_thread = threading.Thread(
        target=lambda: app.run(
            host="127.0.0.1", port=port, threaded=True, use_reloader=False, debug=False
        ),
        daemon=True,
    )
    server_thread.start()

    # Give the server a moment to start listening before opening the browser.
    time.sleep(0.5)

    print(f"SMAPI Mod Updater running at {url}")
    print("Close this window (or click Quit in the page) to stop it.")

    try:
        open_url(url)
    except Exception as e:
        print(f"Couldn't open a browser automatically ({e}). Open {url} manually.")

    # The server thread is a daemon, so the process exits as soon as the
    # main thread does — either Ctrl+C here, or /api/quit calling os._exit().
    try:
        while server_thread.is_alive():
            server_thread.join(timeout=1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
