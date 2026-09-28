# SMAPIModUpdater.spec - PyInstaller build specification (cross-platform)
#
# Run from the repo root:
#   pyinstaller SMAPIModUpdater.spec
#
# Or use the build script:
#   python build_exe.py

import sys
import os
from pathlib import Path

block_cipher = None

current_os = sys.platform  # 'win32', 'darwin', 'linux'

# The smapi_mod_updater folder must be on the path so PyInstaller
# can resolve the sibling imports (web_server, config_manager, etc.)
pkg_dir = os.path.join(os.getcwd(), 'smapi_mod_updater')

# templates/ and static/ are the browser UI's page and assets — bundled
# as data files (not code) so web_server.py can find them at runtime
# via sys._MEIPASS, the same way in onefile and onedir builds.
datas = [
    (os.path.join(pkg_dir, 'templates'), 'templates'),
    (os.path.join(pkg_dir, 'static'), 'static'),
]

a = Analysis(
    ['smapi_mod_updater/main.py'],
    pathex=[pkg_dir],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'web_server',
        'log_parser',
        'browser_launcher',
        'download_watcher',
        'backup_manager',
        'config_manager',
        'platform_utils',
        'session_logger',
        'flask',
        'watchdog',
        'watchdog.observers',
        'watchdog.events',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SMAPIModUpdater',
    debug=False,
    bootloader_ignore_signals=False,
    strip=(current_os != 'win32'),  # Strip symbols on Linux/macOS
    upx=(current_os == 'win32'),    # UPX only reliable on Windows
    # A visible console window now doubles as the "stop the app" control
    # for anyone who closes the browser tab without clicking Quit —
    # there's no window handle to close a browser tab from anymore.
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=(current_os != 'win32'),
    upx=(current_os == 'win32'),
    upx_exclude=[],
    name='SMAPIModUpdater',
)
