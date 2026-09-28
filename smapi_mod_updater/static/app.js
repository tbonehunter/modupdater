// app.js - SMAPI Mod Updater front end
//
// Talks to web_server.py over fetch() for actions and an EventSource
// for live updates (log lines, per-mod status, issue count, watch
// completion). Selection state (which checkboxes are checked) lives
// here in the browser only — the server doesn't need to know until
// an action is triggered.

(() => {
  "use strict";

  // ─── State ──────────────────────────────────────────────────────

  let mods = [];              // current mod list, each with {id, name, current, available, status, is_nexus}
  let isWatching = false;
  let browseTarget = null;    // "log" | "downloads" — which settings field the folder browser is filling
  let browsePath = null;      // path currently shown in the folder browser

  // ─── Element refs ───────────────────────────────────────────────

  const el = {
    modsPath: document.getElementById("mods-path"),
    reloadBtn: document.getElementById("reload-btn"),
    statusBar: document.getElementById("status-bar"),
    modList: document.getElementById("mod-list"),
    selectAllBtn: document.getElementById("select-all-btn"),
    deselectAllBtn: document.getElementById("deselect-all-btn"),
    openPagesBtn: document.getElementById("open-pages-btn"),
    watchInstallBtn: document.getElementById("watch-install-btn"),
    issuesBtn: document.getElementById("issues-btn"),
    logBox: document.getElementById("log-box"),
    quitBtn: document.getElementById("quit-btn"),

    settingsBtn: document.getElementById("settings-btn"),
    settingsModal: document.getElementById("settings-modal"),
    settingsLogPath: document.getElementById("settings-log-path"),
    settingsDownloads: document.getElementById("settings-downloads"),
    settingsModsPath: document.getElementById("settings-mods-path"),
    settingsBackupPolicy: document.getElementById("settings-backup-policy"),
    settingsSaveBtn: document.getElementById("settings-save-btn"),
    settingsCancelBtn: document.getElementById("settings-cancel-btn"),
    browseLogBtn: document.getElementById("browse-log-btn"),
    browseDownloadsBtn: document.getElementById("browse-downloads-btn"),

    browseModal: document.getElementById("browse-modal"),
    browseTitle: document.getElementById("browse-title"),
    browseCurrent: document.getElementById("browse-current"),
    browseList: document.getElementById("browse-list"),
    browseCancelBtn: document.getElementById("browse-cancel-btn"),
    browseSelectBtn: document.getElementById("browse-select-btn"),

    issuesModal: document.getElementById("issues-modal"),
    issuesTitle: document.getElementById("issues-title"),
    issuesList: document.getElementById("issues-list"),
    issuesCloseBtn: document.getElementById("issues-close-btn"),

    steamosModal: document.getElementById("steamos-modal"),
    steamosList: document.getElementById("steamos-list"),
    steamosCancelBtn: document.getElementById("steamos-cancel-btn"),

    backupPromptModal: document.getElementById("backup-prompt-modal"),
    backupPromptText: document.getElementById("backup-prompt-text"),
    backupPromptSkipBtn: document.getElementById("backup-prompt-skip-btn"),
    backupPromptProceedBtn: document.getElementById("backup-prompt-proceed-btn"),
  };

  const STATUS_TEXT = {
    pending: "",
    downloading: "…",
    installed: "OK",
    error: "!!",
    skipped: "--",
  };

  // ─── API helpers ────────────────────────────────────────────────

  async function apiGet(path) {
    const res = await fetch(path);
    return res.json();
  }

  async function apiPost(path, body) {
    const res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
    return res.json();
  }

  // ─── Rendering ──────────────────────────────────────────────────

  function applyState(state) {
    mods = state.mods;
    isWatching = state.watching;

    el.modsPath.textContent = state.mods_path || "(not detected — run SMAPI once)";
    renderModList();
    renderStatusBar();
    updateIssuesButton(state.issue_count);
    updateWatchButton();

    if (state.is_steamos && !state.log_path) {
      maybeShowSteamosPicker();
    }
  }

  function renderStatusBar() {
    const count = mods.length;
    el.statusBar.textContent =
      count === 0 ? "No updates available." : `Found ${count} mod${count !== 1 ? "s" : ""} to update.`;
  }

  function renderModList() {
    el.modList.innerHTML = "";

    if (mods.length === 0) {
      const empty = document.createElement("div");
      empty.className = "mod-list-empty";
      empty.textContent = "No updates loaded yet.";
      el.modList.appendChild(empty);
      return;
    }

    for (const mod of mods) {
      el.modList.appendChild(renderModRow(mod));
    }
  }

  function renderModRow(mod) {
    const row = document.createElement("div");
    row.className = "mod-row";
    row.dataset.id = mod.id;

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = true;
    checkbox.className = "mod-checkbox";
    row.appendChild(checkbox);

    const name = document.createElement("span");
    name.className = "mod-name";
    name.textContent = mod.name;
    row.appendChild(name);

    const version = document.createElement("span");
    version.className = "mod-version";
    version.textContent = `${mod.current}  →  ${mod.available}`;
    row.appendChild(version);

    const status = document.createElement("span");
    status.className = `mod-status mod-status-${mod.status}`;
    status.textContent = STATUS_TEXT[mod.status] || "";
    row.appendChild(status);

    return row;
  }

  function getRow(id) {
    return el.modList.querySelector(`.mod-row[data-id="${CSS.escape(id)}"]`);
  }

  function setRowStatus(id, status) {
    const mod = mods.find((m) => m.id === id);
    if (mod) mod.status = status;

    const row = getRow(id);
    if (!row) return;
    const statusEl = row.querySelector(".mod-status");
    statusEl.className = `mod-status mod-status-${status}`;
    statusEl.textContent = STATUS_TEXT[status] || "";
  }

  function selectedIds({ excludeInstalled = false } = {}) {
    const ids = [];
    el.modList.querySelectorAll(".mod-row").forEach((row) => {
      const checkbox = row.querySelector(".mod-checkbox");
      if (!checkbox.checked) return;
      if (excludeInstalled) {
        const mod = mods.find((m) => m.id === row.dataset.id);
        if (mod && mod.status === "installed") return;
      }
      ids.push(row.dataset.id);
    });
    return ids;
  }

  function updateIssuesButton(count) {
    if (count > 0) {
      el.issuesBtn.textContent = `View Issues (${count})`;
      el.issuesBtn.disabled = false;
    } else {
      el.issuesBtn.textContent = "View Issues";
      el.issuesBtn.disabled = true;
    }
  }

  function updateWatchButton() {
    el.watchInstallBtn.textContent = isWatching ? "Stop Watching" : "Watch & Install";
  }

  function appendLog(message) {
    const line = document.createElement("div");
    line.textContent = `> ${message}`;
    el.logBox.appendChild(line);
    el.logBox.scrollTop = el.logBox.scrollHeight;
  }

  // ─── Actions ────────────────────────────────────────────────────

  async function loadState() {
    applyState(await apiGet("/api/state"));
  }

  el.reloadBtn.addEventListener("click", async () => {
    applyState(await apiPost("/api/reload"));
  });

  el.selectAllBtn.addEventListener("click", () => {
    el.modList.querySelectorAll(".mod-checkbox").forEach((c) => (c.checked = true));
  });

  el.deselectAllBtn.addEventListener("click", () => {
    el.modList.querySelectorAll(".mod-checkbox").forEach((c) => (c.checked = false));
  });

  el.openPagesBtn.addEventListener("click", async () => {
    const ids = selectedIds({ excludeInstalled: true });
    if (ids.length === 0) {
      appendLog("No mods to open (all selected mods already installed).");
      return;
    }
    el.openPagesBtn.disabled = true;
    try {
      await apiPost("/api/open-pages", { ids });
    } finally {
      el.openPagesBtn.disabled = false;
    }
  });

  el.watchInstallBtn.addEventListener("click", async () => {
    if (isWatching) {
      const result = await apiPost("/api/watch/stop");
      isWatching = result.watching;
      updateWatchButton();
      return;
    }

    const ids = selectedIds();
    if (ids.length === 0) {
      appendLog("No mods selected.");
      return;
    }

    for (const id of ids) setRowStatus(id, "downloading");

    const result = await apiPost("/api/watch/start", { ids });
    if (result.error) {
      return; // error already logged server-side via SSE
    }
    isWatching = result.watching;
    updateWatchButton();
  });

  el.issuesBtn.addEventListener("click", async () => {
    const { issues } = await apiGet("/api/issues");
    renderIssues(issues);
    showModal(el.issuesModal);
  });

  el.issuesCloseBtn.addEventListener("click", () => hideModal(el.issuesModal));

  el.quitBtn.addEventListener("click", async () => {
    if (!confirm("Quit the SMAPI Mod Updater?")) return;
    await apiPost("/api/quit");
    document.body.innerHTML =
      '<div class="quit-message">SMAPI Mod Updater has stopped. You can close this tab.</div>';
  });

  function renderIssues(issues) {
    el.issuesTitle.textContent = `${issues.length} issue${issues.length !== 1 ? "s" : ""} this session`;
    el.issuesList.innerHTML = "";

    if (issues.length === 0) {
      const none = document.createElement("div");
      none.className = "issues-empty";
      none.textContent = "No issues to report.";
      el.issuesList.appendChild(none);
      return;
    }

    for (const issue of issues) {
      const item = document.createElement("div");
      item.className = "issue-item";

      const header = document.createElement("div");
      header.className = "issue-header";
      header.textContent = `${issue.mod} — ${issue.reason}`;
      item.appendChild(header);

      const detail = document.createElement("div");
      detail.className = "issue-detail";
      detail.textContent = issue.detail;
      item.appendChild(detail);

      el.issuesList.appendChild(item);
    }
  }

  // ─── Settings dialog ────────────────────────────────────────────

  el.settingsBtn.addEventListener("click", async () => {
    const settings = await apiGet("/api/settings");
    el.settingsLogPath.value = settings.smapi_log_path || "";
    el.settingsDownloads.value = settings.downloads_folder || "";
    el.settingsModsPath.textContent = settings.mods_path || "(not detected — run SMAPI once)";
    el.settingsBackupPolicy.value = settings.backup_failure_policy || "abort";
    showModal(el.settingsModal);
  });

  el.settingsCancelBtn.addEventListener("click", () => hideModal(el.settingsModal));

  el.settingsSaveBtn.addEventListener("click", async () => {
    const state = await apiPost("/api/settings", {
      smapi_log_path: el.settingsLogPath.value.trim(),
      downloads_folder: el.settingsDownloads.value.trim(),
      backup_failure_policy: el.settingsBackupPolicy.value,
    });
    applyState(state);
    hideModal(el.settingsModal);
  });

  // ─── In-page folder browser ─────────────────────────────────────

  el.browseLogBtn.addEventListener("click", () => openBrowser("log", el.settingsLogPath.value));
  el.browseDownloadsBtn.addEventListener("click", () =>
    openBrowser("downloads", el.settingsDownloads.value)
  );
  el.browseCancelBtn.addEventListener("click", () => hideModal(el.browseModal));

  el.browseSelectBtn.addEventListener("click", () => {
    if (browseTarget === "log") {
      // The log field wants a file, not a folder — drop the picked
      // folder in and let the user type the filename, since the
      // browser only ever lists directories.
      el.settingsLogPath.value = browsePath;
    } else if (browseTarget === "downloads") {
      el.settingsDownloads.value = browsePath;
    }
    hideModal(el.browseModal);
  });

  async function openBrowser(target, startPath) {
    browseTarget = target;
    el.browseTitle.textContent = target === "log" ? "Locate SMAPI Log Folder" : "Choose Downloads Folder";
    await loadBrowsePath(startPath || null);
    showModal(el.browseModal);
  }

  async function loadBrowsePath(path) {
    const data = await apiGet("/api/browse" + (path ? `?path=${encodeURIComponent(path)}` : ""));
    browsePath = data.path;
    el.browseCurrent.textContent = data.path;
    el.browseList.innerHTML = "";

    if (data.parent) {
      const up = document.createElement("div");
      up.className = "browse-entry browse-entry-up";
      up.textContent = ".. (up one level)";
      up.addEventListener("click", () => loadBrowsePath(data.parent));
      el.browseList.appendChild(up);
    }

    for (const name of data.entries) {
      const entry = document.createElement("div");
      entry.className = "browse-entry";
      entry.textContent = name;
      entry.addEventListener("click", () => {
        const sep = data.path.includes("\\") ? "\\" : "/";
        loadBrowsePath(data.path.replace(/[\\/]+$/, "") + sep + name);
      });
      el.browseList.appendChild(entry);
    }
  }

  // ─── SteamOS picker ─────────────────────────────────────────────

  let steamosPromptShown = false;

  async function maybeShowSteamosPicker() {
    if (steamosPromptShown) return;
    const { candidates } = await apiGet("/api/steamos-candidates");
    if (candidates.length <= 1) return;

    steamosPromptShown = true;
    el.steamosList.innerHTML = "";
    for (const candidate of candidates) {
      const entry = document.createElement("div");
      entry.className = "browse-entry";
      entry.textContent = candidate.name;
      entry.addEventListener("click", async () => {
        const state = await apiPost("/api/steamos-select", { path: candidate.path });
        applyState(state);
        hideModal(el.steamosModal);
      });
      el.steamosList.appendChild(entry);
    }
    showModal(el.steamosModal);
  }

  el.steamosCancelBtn.addEventListener("click", () => hideModal(el.steamosModal));

  // ─── Backup-failure prompt ("Ask me each time" Settings policy) ─

  let currentBackupRequestId = null;

  function showBackupPrompt({ request_id, mod, folder }) {
    currentBackupRequestId = request_id;
    el.backupPromptText.textContent =
      `Couldn't back up "${folder}" before updating ${mod}. ` +
      `Install the update anyway without a backup, or skip this mod for now?`;
    showModal(el.backupPromptModal);
  }

  async function answerBackupPrompt(decision) {
    if (!currentBackupRequestId) return;
    await apiPost("/api/backup-decision", { request_id: currentBackupRequestId, decision });
    currentBackupRequestId = null;
    hideModal(el.backupPromptModal);
  }

  el.backupPromptSkipBtn.addEventListener("click", () => answerBackupPrompt("abort"));
  el.backupPromptProceedBtn.addEventListener("click", () => answerBackupPrompt("skip_backup"));

  // ─── Modal helpers ──────────────────────────────────────────────

  function showModal(modal) {
    modal.classList.remove("hidden");
  }

  function hideModal(modal) {
    modal.classList.add("hidden");
  }

  // ─── Live updates (SSE) ─────────────────────────────────────────

  function connectEvents() {
    const source = new EventSource("/api/events");

    source.addEventListener("log", (e) => appendLog(JSON.parse(e.data).message));

    source.addEventListener("mod_status", (e) => {
      const { id, status } = JSON.parse(e.data);
      setRowStatus(id, status);
    });

    source.addEventListener("issues", (e) => updateIssuesButton(JSON.parse(e.data).count));

    source.addEventListener("watch_complete", () => {
      isWatching = false;
      updateWatchButton();
    });

    source.addEventListener("state", (e) => applyState(JSON.parse(e.data)));

    source.addEventListener("backup_prompt", (e) => showBackupPrompt(JSON.parse(e.data)));

    source.onerror = () => {
      // Browser auto-reconnects EventSource; nothing to do here.
    };
  }

  // ─── Startup ────────────────────────────────────────────────────

  loadState();
  connectEvents();
})();
