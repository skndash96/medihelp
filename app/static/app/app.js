/* Elderly Care Monitor - PWA logic (vanilla JS). */

const LEVEL_LABELS = { 0: "Test", 1: "Warning", 2: "Emergency" };
const NOTIF_LABELS = { sms: "SMS", voice_call: "Voice call", null: "—" };
const STATUS_LABELS = { sent: "Sent", failed: "Failed", null: "—" };

const els = {
  connection: document.getElementById("connection-status"),
  currentStatus: document.getElementById("current-status"),
  sumWarnings: document.getElementById("sum-warnings"),
  sumEmergencies: document.getElementById("sum-emergencies"),
  recentAlerts: document.getElementById("recent-alerts"),
  alertsEmpty: document.getElementById("alerts-empty"),
  modal: document.getElementById("modal"),
  modalBody: document.getElementById("modal-body"),
  modalClose: document.getElementById("modal-close"),
  toast: document.getElementById("toast"),
  chartCanvas: document.getElementById("historyChart"),
};

let historyChart = null;
let currentRange = "1h"; // fetch relative URLs (same origin)

async function api(path, options) {
  const res = await fetch(path, options);
  let data = null;
  try { data = await res.json(); } catch (_) {}
  if (!res.ok) {
    const msg = (data && data.detail) || `Request failed (${res.status})`;
    throw new Error(msg);
  }
  return data;
}

function showToast(msg, isError = false) {
  els.toast.textContent = msg;
  els.toast.classList.remove("hidden");
  els.toast.classList.toggle("error", isError);
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => els.toast.classList.add("hidden"), 4000);
}

function levelLabel(level) {
  return LEVEL_LABELS[level] ?? `Level ${level}`;
}

function formatTime(iso) {
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  return d.toTimeString().slice(0, 5);
}

function formatFull(iso) {
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  const opts = { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" };
  return d.toLocaleString(undefined, opts);
}

function updateConnection(online) {
  els.connection.textContent = online ? "Connected" : "Offline";
  els.connection.classList.toggle("online", online);
  els.connection.classList.toggle("offline", !online);
}

/* ------- Dashboard data ------- */
async function loadDashboard() {
  try {
    const [latest, oneHour] = await Promise.all([
      api("/api/alerts/latest?limit=50"),
      api("/api/stats?range=1h"),
    ]);
    renderStatus(oneHour);
    renderRecent(latest.alerts);
    // Refresh the current chart data too
    await loadHistory();
  } catch (err) {
    showToast(err.message, true);
    updateConnection(navigator.onLine);
  }
}

function renderStatus(stats) {
  els.sumWarnings.textContent = stats.level_1;
  els.sumEmergencies.textContent = stats.level_2;
  els.sumWarnings.classList.toggle("warn", stats.level_1 > 0);
  els.sumEmergencies.classList.toggle("danger", stats.level_2 > 0);

  const banner = els.currentStatus;
  if (stats.level_2 > 0) {
    banner.className = "status-banner danger";
    banner.querySelector(".status-label").textContent = "Emergency — check on the elderly person now!";
  } else if (stats.level_1 > 0) {
    banner.className = "status-banner warning";
    banner.querySelector(".status-label").textContent = "Warning — possible incident detected";
  } else {
    banner.className = "status-banner clear";
    banner.querySelector(".status-label").textContent = "No recent emergency";
  }
}

function renderRecent(alerts) {
  els.recentAlerts.innerHTML = "";
  els.alertsEmpty.classList.toggle("hidden", alerts.length > 0);
  alerts.slice(0, 12).forEach((a) => {
    const li = document.createElement("li");
    li.className = `alert-item level-${a.level}`;

    const badge = document.createElement("span");
    badge.className = `badge ${a.level === 2 ? "danger" : a.level === 1 ? "warning" : "normal"}`;
    badge.textContent = levelLabel(a.level);

    const rec = document.createElement("span");
    rec.className = "rec";
    rec.textContent = a.notification_type ? NOTIF_LABELS[a.notification_type] : "";

    const time = document.createElement("span");
    time.className = "time";
    time.textContent = formatTime(a.created_at);

    li.append(badge, rec, time);
    li.addEventListener("click", () => openDetail(a));
    els.recentAlerts.appendChild(li);
  });
}

/* ------- Alert detail modal ------- */
function openDetail(a) {
  let html = `<h3 style="margin-top:0">Alert #${a.id}</h3>`;
  html += `<div class="detail-row"><span class="detail-label">Level</span><span class="detail-value">${levelLabel(a.level)}</span></div>`;
  html += `<div class="detail-row"><span class="detail-label">Time</span><span class="detail-value">${formatFull(a.created_at)}</span></div>`;
  html += `<div class="detail-row"><span class="detail-label">Device</span><span class="detail-value">${a.device_id || "—"}</span></div>`;
  html += `<div class="detail-row"><span class="detail-label">Location</span><span class="detail-value">${a.latitude !== null ? a.latitude + ", " + a.longitude : "—"}</span></div>`;
  html += `<div class="detail-row"><span class="detail-label">Notification</span><span class="detail-value">${NOTIF_LABELS[a.notification_type] ?? "—"}</span></div>`;
  html += `<div class="detail-row"><span class="detail-label">Status</span><span class="detail-value">${STATUS_LABELS[a.notification_status] ?? "—"}</span></div>`;
  if (a.latitude !== null && a.longitude !== null) {
    html += `<a class="map-btn" target="_blank" rel="noopener" href="https://maps.google.com/?q=${a.latitude},${a.longitude}">Open in map</a>`;
  }
  els.modalBody.innerHTML = html;
  els.modal.classList.remove("hidden");
}

els.modalClose.addEventListener("click", () => els.modal.classList.add("hidden"));
els.modal.addEventListener("click", (e) => { if (e.target === els.modal) els.modal.classList.add("hidden"); });

/* ------- Chart for history range ------- */
async function loadHistory() {
  try {
    const data = await api(`/api/alerts?range=${currentRange}&limit=500`);
    renderChart(data.alerts, data.range);
  } catch (err) {
    showToast(err.message, true);
  }
}

function renderChart(alerts, range) {
  const buckets = bucketize(alerts, range);
  const labels = buckets.map((b) => b.label);
  const warnings = buckets.map((b) => b.level1);
  const emergencies = buckets.map((b) => b.level2);

  const ctx = els.chartCanvas.getContext("2d");
  if (historyChart) historyChart.destroy();
  historyChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [
        { label: "Warnings", data: warnings, backgroundColor: "#d97706", borderRadius: 4 },
        { label: "Emergencies", data: emergencies, backgroundColor: "#dc2626", borderRadius: 4 },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: { beginAtZero: true, ticks: { precision: 0 } },
        x: { stacked: true },
      },
    },
  });
}

function bucketSize(range) {
  if (range === "1h") return { ms: 10 * 60 * 1000, n: 6 };
  if (range === "1d") return { ms: 60 * 60 * 1000, n: 8 };
  if (range === "1w") return { ms: 24 * 60 * 60 * 1000, n: 7 };
  return { ms: 7 * 24 * 60 * 60 * 1000, n: 6 };
}

function bucketize(alerts, range) {
  const { ms, n } = bucketSize(range);
  const now = Date.now();
  const buckets = [];
  for (let i = n - 1; i >= 0; i--) {
    buckets.push({ label: "", level1: 0, level2: 0, start: now - (i + 1) * ms, end: now - i * ms });
  }
  alerts.forEach((a) => {
    const t = new Date(a.created_at).getTime();
    const b = buckets.find((bk) => t >= bk.start && t < bk.end);
    if (!b) return;
    if (a.level === 1) b.level1++;
    if (a.level === 2) b.level2++;
  });
  const fmt = (d) => new Date(d);
  buckets.forEach((b) => {
    if (range === "1h") b.label = fmt(b.start).toTimeString().slice(0, 5);
    else if (range === "1d") b.label = fmt(b.start).toTimeString().slice(0, 5) + "h";
    else if (range === "1w") b.label = fmt(b.start).toLocaleDateString(undefined, { weekday: "short" });
    else b.label = fmt(b.start).toLocaleDateString(undefined, { month: "short", day: "numeric" });
  });
  return buckets;
}

/* ------- Range buttons ------- */
document.querySelectorAll(".range-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    currentRange = btn.dataset.range;
    document.querySelectorAll(".range-btn").forEach((b) => b.classList.toggle("active", b === btn));
    loadHistory();
  });
});

/* ------- Connectivity ------- */
window.addEventListener("online", () => { updateConnection(true); loadDashboard(); });
window.addEventListener("offline", () => updateConnection(false));
setInterval(() => updateConnection(navigator.onLine), 3000);

/* ------- Boot ------- */
(function init() {
  loadDashboard();
  setInterval(loadDashboard, 30000);
})();
