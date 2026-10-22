/* Admin - Elderly Fall Alert (vanilla JS). */

const els = {
  btnWarning: document.getElementById("btn-warning"),
  btnEmergency: document.getElementById("btn-emergency"),
  result: document.getElementById("result"),
  body: document.getElementById("alerts-body"),
  empty: document.getElementById("empty"),
};

const STATUS_LABELS = { sent: "Sent", failed: "Failed", null: "—" };

async function sendAlert(level) {
  els.result.className = "result hidden";
  els.btnWarning.disabled = true;
  els.btnEmergency.disabled = true;
  try {
    const res = await fetch(`/api/alert?level=${level}`, { method: "POST" });
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      throw new Error((data && data.detail) || `Request failed (${res.status})`);
    }
    renderResult(data);
  } catch (err) {
    showError(err.message);
  } finally {
    els.btnWarning.disabled = false;
    els.btnEmergency.disabled = false;
  }
}

function renderResult(data) {
  const failed = data.notification_status === "failed";
  const ok = data.level === 0 || !failed;
  els.result.className = "result " + (ok ? "success" : "warn");
  let html = `<h3>${ok ? "Alert sent successfully." : "Alert recorded, but Twilio notification failed."}</h3>`;
  html += `<p>Alert ID: ${data.alert_id}</p>`;
  if (data.notification) {
    const label = data.notification === "sms" ? "SMS" : "voice call";
    html += `<p>${label} status: ${STATUS_LABELS[data.notification_status] ?? data.notification_status}</p>`;
  } else {
    html += `<p>No notification (test alert).</p>`;
  }
  els.result.innerHTML = html;
  els.result.classList.remove("hidden");
}

function showError(msg) {
  els.result.className = "result error";
  els.result.textContent = "Error: " + msg;
  els.result.classList.remove("hidden");
}

async function loadRecent() {
  try {
    const res = await fetch("/api/alerts/latest?limit=10");
    if (!res.ok) throw new Error("Failed to load alerts");
    const data = await res.json();
    const alerts = data.alerts || [];
    els.empty.classList.toggle("hidden", alerts.length > 0);
    els.body.innerHTML = "";
    alerts.forEach((a) => {
      const tr = document.createElement("tr");
      const level = a.level === 2 ? "Emergency" : a.level === 1 ? "Warning" : "Test";
      const notif = a.notification_type === "sms" ? "SMS" : a.notification_type === "voice_call" ? "Voice call" : "—";
      const ts = new Date(a.created_at);
      const time = isNaN(ts) ? a.created_at : ts.toLocaleString();
      tr.innerHTML = `
        <td>${a.id}</td>
        <td class="lvl lvl-${a.level}">${level}</td>
        <td>${a.device_id || "—"}</td>
        <td>${time}</td>
        <td>${notif}</td>
        <td>${STATUS_LABELS[a.notification_status] ?? "—"}</td>`;
      els.body.appendChild(tr);
    });
  } catch (err) {
    showError(err.message);
  }
}

els.btnWarning.addEventListener("click", () => sendAlert(1));
els.btnEmergency.addEventListener("click", () => sendAlert(2));

loadRecent();
setInterval(loadRecent, 15000);
