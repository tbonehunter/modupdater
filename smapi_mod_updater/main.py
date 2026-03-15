# main.py - SMAPI Mod Updater entry point
"""
SMAPI Mod Updater
A cross-platform tool to streamline updating Stardew Valley mods.
Parses SMAPI's update log, opens Nexus download pages, and
automatically installs downloaded updates.
"""

import sys
from gui import SMAPIModUpdaterGUI


def main():
    """Launch the SMAPI Mod Updater GUI."""
    app = SMAPIModUpdaterGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
