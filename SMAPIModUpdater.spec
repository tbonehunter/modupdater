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
# can resolve the sibling imports (gui, config_manager, etc.)
pkg_dir = os.path.join(os.getcwd(), 'smapi_mod_updater')

a = Analysis(
    ['smapi_mod_updater/main.py'],
    pathex=[pkg_dir],
    binaries=[],
    datas=[],
    hiddenimports=[
        'gui',
        'log_parser',
        'browser_launcher',
        'download_watcher',
        'backup_manager',
        'config_manager',
        'platform_utils',
        'session_logger',
        'customtkinter',
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
    console=False,  # No terminal window — GUI only
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
