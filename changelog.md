<!-- CHANGELOG.md - SMAPI Mod Updater version history -->

# Changelog

## 2.1.0

### Added

- **Self-update check.** This tool isn't a SMAPI mod, so SMAPI's own
  update-checking never notices when a newer version of the updater
  itself is released. On startup (and again after Settings is saved),
  the app now asks Nexus directly whether a newer version is published.
  If one is, a banner appears at the top of the page with a
  **Download Update** button that opens this tool's Nexus page in the
  browser — the same manual-download flow already used for mod
  updates. The check runs in the background and never delays the page
  loading, even if Nexus is slow or unreachable.

  This is deliberately alert-only, not a silent auto-download or
  self-installer. Nexus's API only hands back a direct download link
  automatically to Premium accounts; everyone else has to go through
  the site's own manual-download flow. Automating that step would
  have silently worked for some users and silently failed for most
  others, so the update path stays manual and identical for everyone.

- **Settings: Nexus Personal API Key field.** The self-update check
  needs to authenticate to Nexus's API, so Settings gained a field for
  a personal API key. This is a **testing-build-only** measure,
  required by Nexus's Acceptable Use Policy for an application still
  in that stage — once this tool is registered as a public application
  with Nexus, this field and the personal key will be replaced by
  Nexus's SSO flow, so end users never handle a raw key at all. The
  key is stored only in the local config file, which is not tracked in
  version control.

- **`NexusModID` in the build manifest.** `build_exe.py` now writes
  this tool's own Nexus mod ID (43712) into the generated
  `manifest.json`, alongside the existing name/author/version fields.

### Changed

- Version bumped from 2.0.0 to 2.1.0.

### Files touched

| File | Change |
|---|---|
| `smapi_mod_updater/nexus_updater.py` | New module — queries Nexus's API for this tool's published version and compares it to the running version. |
| `smapi_mod_updater/config_manager.py` | Added `nexus_api_key` to the config schema, with `get_nexus_api_key()` / `set_nexus_api_key()` accessors. |
| `smapi_mod_updater/web_server.py` | Runs the update check in a background thread at startup and after Settings is saved; `/api/settings` now reads/writes the API key; app state carries the check's result to the page. |
| `smapi_mod_updater/version.py` | `VERSION` bumped to `"2.1.0"`. |
| `templates/index.html` | Added the update banner markup and the Nexus API Key field in the Settings dialog. |
| `static/style.css` | Added `.update-banner` styling. |
| `static/app.js` | Renders the banner from app state, wires its Download button to open the Nexus page, and reads/writes the API key field in Settings. |
| `build_exe.py` | Added `NexusModID` to `NEXUS_MANIFEST`. |

### Known limitation

Because the download step stays manual (see above), this release
doesn't close the loop automatically — the user still has to notice
the banner, click through to Nexus, download, quit the app, and
replace the installed folder themselves. That's an intentional
trade-off for now; a more automated version was discussed (see the
project's working notes) but set aside as unnecessary for the current
need.

---

## 2.0.0

The release this changelog starts tracking from: replaced the
CustomTkinter desktop GUI (`gui.py`) with a local Flask server and
browser-based UI (`web_server.py` + `templates/index.html` +
`static/`). All underlying logic — SMAPI log parsing, backup/install,
the download watcher, config handling, platform detection, session
logging — was carried over unchanged; only the UI layer changed.
Also added SteamOS support (auto-detecting SMAPI logs under Proton
and prompting when multiple Stardew Valley installs are found).