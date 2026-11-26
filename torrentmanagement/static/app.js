/** Browser-side state and event handlers for the local torrent workflow. */
const notice = document.querySelector("#notice");
const jobsList = document.querySelector("#jobs-list");
const playerPanel = document.querySelector("#player-panel");
const player = document.querySelector("#video-player");
const videoSelect = document.querySelector("#video-select");
const uploadButton = document.querySelector("#upload-form button");
let jobs = [];
let selectedJobId = null;
let currentSubtitleIds = new Set();

function showNotice(message, kind = "info") {
  /** Present API, validation, and operation feedback accessibly. */
  notice.textContent = message;
  notice.dataset.kind = kind;
  notice.hidden = !message;
}

async function api(url, options = {}) {
  /** Decode the JSON API response and turn HTTP failures into UI errors. */
  const response = await fetch(url, options);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = body.detail;
    const message = typeof detail === "string" ? detail : detail?.message;
    throw new Error(message || `Request failed (${response.status})`);
  }
  return body;
}

function displayName(job) {
  /** Prefer the selected media path, then the candidate file, then its hash. */
  return job.selected_file_path || job.files.find((file) => file.selected)?.path || job.infohash;
}

function formatBytes(bytes) {
  /** Convert a non-negative byte count to a compact user-facing unit. */
  if (!Number.isFinite(bytes) || bytes < 0) return "—";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`;
}

function progressPercent(job) {
  /** Keep rounded progress below 100 until the backend confirms completion. */
  if (job.state === "complete") return 100;
  const rawPercent = Math.round(Math.max(0, Math.min(1, job.progress || 0)) * 1000) / 10;
  return Math.min(rawPercent, 99.9);
}

function downloadStatus(job) {
  /** Describe lifecycle state explicitly instead of inferring it from a bar. */
  const percent = progressPercent(job).toFixed(1);
  if (job.state === "complete") return "Download complete · 100%";
  if (job.state === "failed") return `Download failed · ${percent}%`;
  if (job.state === "queued") return `Queued to download · ${percent}%`;
  if (job.state === "streamable") {
    return `Playable while still downloading · ${percent}%`;
  }
  return `Still downloading · ${percent}%`;
}

function renderJobs() {
  /** Render each job with an explicit completion state and accessible progress. */
  document.querySelector("#job-count").textContent = String(jobs.length);
  jobsList.replaceChildren();
  if (jobs.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "Your downloads will appear here.";
    jobsList.append(empty);
    return;
  }

  for (const job of jobs) {
    const button = document.createElement("button");
    button.className = "job-item";
    button.type = "button";
    button.setAttribute("aria-pressed", String(job.id === selectedJobId));
    button.addEventListener("click", () => selectJob(job.id));

    const name = document.createElement("span");
    name.className = "job-name";
    name.textContent = displayName(job);

    const state = document.createElement("span");
    state.className = "job-state";
    state.textContent = downloadStatus(job);

    const progress = document.createElement("progress");
    progress.className = "job-progress";
    progress.max = 1;
    progress.value = Math.max(0, Math.min(1, job.progress || 0));
    progress.setAttribute("aria-label", downloadStatus(job));

    button.append(name, state, progress);
    jobsList.append(button);
  }
}

function selectJob(jobId) {
  /** Reset media and subtitle state before switching the selected job. */
  selectedJobId = jobId;
  currentSubtitleIds = new Set();
  player.removeAttribute("src");
  player.replaceChildren();
  player.load();
  document.querySelector("#subtitle-list").replaceChildren();
  renderJobs();
  renderSelectedJob();
}

function renderSelectedJob() {
  /** Render selected-file controls, download status, readiness, and player URL. */
  const job = jobs.find((item) => item.id === selectedJobId);
  if (!job) {
    playerPanel.hidden = true;
    return;
  }
  playerPanel.hidden = false;
  document.querySelector("#player-heading").textContent = displayName(job);
  document.querySelector("#torrent-hash").textContent = `Infohash · ${job.infohash}`;
  document.querySelector("#progress-value").textContent = downloadStatus(job);
  const progress = document.querySelector("#download-progress");
  progress.value = Math.max(0, Math.min(1, job.progress || 0));
  progress.setAttribute("aria-label", downloadStatus(job));

  const selectedIndex = String(job.selected_file_index ?? "");
  const existingOptions = Array.from(videoSelect.options).map((option) => `${option.value}:${option.textContent}`);
  const nextOptions = job.files
    .filter((file) => /\.(avi|m4v|mkv|mov|mp4|mpeg|mpg|webm)$/i.test(file.path))
    .map((file) => `${file.index}:${file.path} · ${formatBytes(file.size)}`);
  if (existingOptions.join("|") !== nextOptions.join("|")) {
    videoSelect.replaceChildren();
    for (const file of job.files.filter((item) => /\.(avi|m4v|mkv|mov|mp4|mpeg|mpg|webm)$/i.test(item.path))) {
      const option = document.createElement("option");
      option.value = String(file.index);
      option.textContent = `${file.path} · ${formatBytes(file.size)}`;
      videoSelect.append(option);
    }
  }
  videoSelect.value = selectedIndex;

  const statePill = document.querySelector("#playback-state");
  statePill.dataset.state = job.state;
  statePill.textContent = downloadStatus(job);

  const readiness = job._readiness;
  const readinessCopy = document.querySelector("#readiness-copy");
  if (job.state === "failed") {
    readinessCopy.textContent = job.error || "The download failed.";
  } else if (readiness?.ready) {
    readinessCopy.textContent = readiness.mode === "direct"
      ? "Ready · seeking is available while pieces download."
      : readiness.complete
        ? "Ready · converted media supports seeking."
        : "Ready · converted playback is sequential until download completes.";
  } else if (job.state === "complete" && job.conversion_state === "running") {
    readinessCopy.textContent = "Download complete · preparing a browser-compatible version.";
  } else {
    readinessCopy.textContent = "Waiting for a decodable opening frame and required container metadata.";
  }

  const streamUrl = `/api/torrents/${encodeURIComponent(job.id)}/stream`;
  if (readiness?.ready && player.dataset.streamUrl !== streamUrl) {
    player.dataset.streamUrl = streamUrl;
    player.src = streamUrl;
    player.load();
  } else if (!readiness?.ready && player.dataset.streamUrl !== streamUrl) {
    player.removeAttribute("src");
    player.dataset.streamUrl = "";
    player.load();
  }
  document.querySelector("#subtitle-title").value = displayName(job).replace(/\.[^.]+$/, "");
  refreshSubtitles(job.id);
}

async function refreshJobs() {
  /** Poll job state and readiness without treating rounded progress as done. */
  try {
    const data = await api("/api/torrents");
    jobs = data.items;
    if (!jobs.some((job) => job.id === selectedJobId)) {
      selectedJobId = jobs[0]?.id || null;
    }
    if (selectedJobId) {
      for (const job of jobs) {
        if (job.id === selectedJobId && job.selected_file_index !== null) {
          try {
            job._readiness = await api(`/api/torrents/${encodeURIComponent(job.id)}/readiness`);
          } catch (error) {
            job._readiness = { ready: false, reason: error.message };
          }
        }
      }
    }
    renderJobs();
    renderSelectedJob();
  } catch (error) {
    showNotice(error.message, "error");
  }
}

async function refreshSubtitles(jobId) {
  /** Synchronize locally available subtitle tracks with the video element. */
  try {
    const data = await api(`/api/torrents/${encodeURIComponent(jobId)}/subtitles`);
    const list = document.querySelector("#subtitle-list");
    const newItems = data.items.filter((item) => !currentSubtitleIds.has(item.id));
    for (const item of newItems) {
      currentSubtitleIds.add(item.id);
      const track = document.createElement("track");
      track.kind = "subtitles";
      track.label = `${item.language.toUpperCase()} · ${item.release_name || item.filename}`;
      track.srclang = item.language;
      track.src = `/api/subtitles/${encodeURIComponent(item.id)}`;
      player.append(track);

      const row = document.createElement("li");
      row.textContent = `${item.language.toUpperCase()} · ${item.release_name || item.filename}`;
      list.append(row);
    }
  } catch (error) {
    showNotice(error.message, "error");
  }
}

document.querySelector("#torrent-file").addEventListener("change", (event) => {
  /** Reflect the file chosen for the next torrent upload. */
  const file = event.currentTarget.files?.[0];
  document.querySelector("#file-label").textContent = file?.name || "Choose a .torrent file";
});

document.querySelector("#upload-form").addEventListener("submit", async (event) => {
  /** Upload raw torrent metadata and select the returned or reused job. */
  event.preventDefault();
  const file = document.querySelector("#torrent-file").files?.[0];
  if (!file) {
    showNotice("Choose a .torrent file first.", "error");
    return;
  }
  uploadButton.disabled = true;
  showNotice("Inspecting torrent metadata…");
  try {
    const result = await api("/api/torrents", {
      method: "POST",
      headers: { "Content-Type": "application/x-bittorrent" },
      body: file,
    });
    selectedJobId = result.job.id;
    showNotice(result.reused ? "This torrent already has a job; reopening it." : "Download job started.", "success");
    await refreshJobs();
  } catch (error) {
    showNotice(error.message, "error");
  } finally {
    uploadButton.disabled = false;
  }
});

videoSelect.addEventListener("change", async () => {
  /** Apply an explicit file choice and refresh its download/readiness state. */
  if (!selectedJobId || videoSelect.value === "") return;
  try {
    await api(`/api/torrents/${encodeURIComponent(selectedJobId)}/selection`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file_index: Number(videoSelect.value) }),
    });
    player.removeAttribute("src");
    player.dataset.streamUrl = "";
    player.load();
    showNotice("Video selection updated.", "success");
    await refreshJobs();
  } catch (error) {
    showNotice(error.message, "error");
  }
});

document.querySelector("#subtitle-form").addEventListener("submit", async (event) => {
  /** Search and download subtitle tracks for the chosen languages. */
  event.preventDefault();
  if (!selectedJobId) return;
  const title = document.querySelector("#subtitle-title").value.trim();
  const languages = Array.from(document.querySelectorAll('input[name="language"]:checked'))
    .map((input) => input.value);
  const subtitleStatus = document.querySelector("#subtitle-status");
  subtitleStatus.textContent = "Searching and downloading up to five matches…";
  try {
    const result = await api(`/api/torrents/${encodeURIComponent(selectedJobId)}/subtitles`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, languages }),
    });
    subtitleStatus.textContent = `${result.downloaded.length} subtitle file(s) downloaded; ${result.failures.length} failed.`;
    await refreshSubtitles(selectedJobId);
  } catch (error) {
    subtitleStatus.textContent = error.message;
  }
});

refreshJobs();
window.setInterval(refreshJobs, 2500);
