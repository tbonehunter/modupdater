# version.py - Single source of truth for the app's version number
"""
Read by build_exe.py (for the Nexus manifest and archive filename) and
by web_server.py (to show the version in the page's title and header),
so there's exactly one place to update on a release.
"""

VERSION = "2.1.0"
