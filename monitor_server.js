const http = require("http");
const { execFileSync } = require("child_process");
const fs = require("fs");
const os = require("os");
const { randomUUID } = require("crypto");
const {
  TELEGRAM_BOT_TOKEN,
  TELEGRAM_CHAT_ID,
  loadConfig,
  saveConfig,
} = require("./monitor_config");

const PORT = process.env.MONITOR_PORT || 8000;
const ALERT_COOLDOWN_SEC = 300; // 5 minutes

// In-memory state
let config = loadConfig();
let lastCpuTimes = null;
let lastRamAlert = 0;
let lastTempAlert = 0;
let lastDiskAlert = 0;
const sseClients = new Map(); // id -> response

// Prime CPU reading so the first response is not empty.
getCpuPercent();

function readCpuTimes() {
  try {
    const stat = fs.readFileSync("/proc/stat", "utf8");
    const line = stat
      .split("\n")
      .find((row) => row.startsWith("cpu "))?.trim();
    if (!line) return null;
    const parts = line.split(/\s+/).slice(1).map(Number);
    const [user, nice, system, idle, iowait, irq, softirq, steal] = parts;
    const idleAll = idle + iowait;
    const nonIdle = user + nice + system + irq + softirq + steal;
    return { idle: idleAll, total: idleAll + nonIdle };
  } catch (err) {
    console.warn("[stats] Unable to read /proc/stat", err.message);
    return null;
  }
}

function getCpuPercent() {
  const current = readCpuTimes();
  if (!current) return null;
  if (!lastCpuTimes) {
    lastCpuTimes = current;
    return null; // need a delta to compute usage
  }
  const totalDiff = current.total - lastCpuTimes.total;
  const idleDiff = current.idle - lastCpuTimes.idle;
  lastCpuTimes = current;
  if (totalDiff <= 0) return null;
  const usage = ((totalDiff - idleDiff) / totalDiff) * 100;
  return Number(usage.toFixed(1));
}

function getTemp() {
  const candidates = [
    "/sys/class/thermal/thermal_zone0/temp",
    "/sys/devices/virtual/thermal/thermal_zone0/temp",
  ];
  for (const file of candidates) {
    try {
      if (fs.existsSync(file)) {
        const raw = fs.readFileSync(file, "utf8").trim();
        const val = Number(raw) / 1000;
        if (!Number.isNaN(val)) {
          return Number(val.toFixed(1));
        }
      }
    } catch (err) {
      console.warn("[stats] Temp read failed", err.message);
    }
  }
  return null;
}

function getRamStats() {
  try {
    const total = os.totalmem();
    const free = os.freemem();
    const used = total - free;
    const percent = (used / total) * 100;
    return {
      total,
      used,
      percent: Number(percent.toFixed(1)),
    };
  } catch (err) {
    console.warn("[stats] RAM read failed", err.message);
    return null;
  }
}

function getDiskStats() {
  try {
    const output = execFileSync("df", ["-k", "/"], { encoding: "utf8" });
    const [, dataLine] = output.trim().split("\n");
    if (!dataLine) return null;
    const parts = dataLine.trim().split(/\s+/);
    const totalKb = Number(parts[1]);
    const usedKb = Number(parts[2]);
    const percentStr = parts[4] || "";
    const percent = Number(percentStr.replace("%", ""));
    return {
      total: totalKb * 1024,
      used: usedKb * 1024,
      percent: Number.isNaN(percent) ? null : percent,
    };
  } catch (err) {
    console.warn("[stats] Disk read failed", err.message);
    return null;
  }
}

function getUptime() {
  try {
    return os.uptime();
  } catch (err) {
    console.warn("[stats] Uptime read failed", err.message);
    return null;
  }
}

function formatBytesToGb(bytes) {
  return Number((bytes / 1e9).toFixed(2));
}

function buildStats() {
  const cpu = getCpuPercent();
  const ram = getRamStats();
  const disk = getDiskStats();
  const uptimeSec = getUptime();
  const temp = getTemp();

  return {
    cpu,
    ram: ram
      ? {
          totalGb: formatBytesToGb(ram.total),
          usedGb: formatBytesToGb(ram.used),
          percent: ram.percent,
        }
      : null,
    disk: disk
      ? {
          totalGb: formatBytesToGb(disk.total),
          usedGb: formatBytesToGb(disk.used),
          percent: disk.percent,
        }
      : null,
    uptimeSec,
    temp,
    alertsEnabled: Boolean(config.alerts_enabled),
    ramThreshold: config.ram_threshold,
    tempThreshold: config.temp_threshold,
    storageThreshold: config.storage_threshold,
    ts: Date.now(),
  };
}

async function sendTelegramMessage(text) {
  if (!TELEGRAM_BOT_TOKEN || !TELEGRAM_CHAT_ID) return;
  const url = `https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage`;
  try {
    const payload = JSON.stringify({
      chat_id: TELEGRAM_CHAT_ID,
      text,
      parse_mode: "HTML",
    });
    await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: payload,
    });
  } catch (err) {
    console.warn("[alert] Telegram send failed", err.message);
  }
}

function maybeSendAlerts(stats) {
  if (!config.alerts_enabled) return;
  const now = Date.now() / 1000;

  if (
    stats.ram &&
    stats.uptimeSec !== null &&
    stats.ram.percent >= config.ram_threshold
  ) {
    if (now - lastRamAlert > ALERT_COOLDOWN_SEC) {
      const msg = [
        "🚨 <b>STB RAM ALERT</b>",
        "",
        `💾 RAM: <b>${stats.ram.percent.toFixed(1)}%</b>`,
        `⏱ Uptime: ${(stats.uptimeSec / 3600).toFixed(2)} jam`,
      ].join("\n");
      sendTelegramMessage(msg);
      lastRamAlert = now;
    }
  }

  if (
    stats.temp !== null &&
    stats.uptimeSec !== null &&
    stats.temp >= config.temp_threshold
  ) {
    if (now - lastTempAlert > ALERT_COOLDOWN_SEC) {
      const msg = [
        "🔥 <b>STB TEMPERATURE ALERT</b>",
        "",
        `🌡 Suhu CPU: <b>${stats.temp.toFixed(1)}°C</b>`,
        `⏱ Uptime: ${(stats.uptimeSec / 3600).toFixed(2)} jam`,
      ].join("\n");
      sendTelegramMessage(msg);
      lastTempAlert = now;
    }
  }

  if (stats.disk && stats.disk.percent !== null) {
    if (
      stats.disk.percent >= config.storage_threshold &&
      now - lastDiskAlert > ALERT_COOLDOWN_SEC
    ) {
      const msg = [
        "💾 <b>STB STORAGE ALERT</b>",
        "",
        `📂 Storage: <b>${stats.disk.percent.toFixed(1)}%</b>`,
        `⏱ Uptime: ${(stats.uptimeSec / 3600).toFixed(2)} jam`,
      ].join("\n");
      sendTelegramMessage(msg);
      lastDiskAlert = now;
    }
  }
}

function handleJson(res, payload, status = 200) {
  res.writeHead(status, { "Content-Type": "application/json" });
  res.end(JSON.stringify(payload));
}

function renderDashboard(res, initialStats) {
  const html = `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>STB Monitor</title>
  <style>
    :root {
      --bg: #050917;
      --card: rgba(17, 24, 39, 0.6);
      --border: #1f2937;
      --text: #e5e7eb;
      --muted: #9ca3af;
      --accent: #38bdf8;
      --danger: #f43f5e;
      --success: #34d399;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: "Manrope", "Segoe UI", "Helvetica Neue", sans-serif;
      color: var(--text);
      background: radial-gradient(circle at 20% 20%, rgba(56, 189, 248, 0.12), transparent 30%),
                  radial-gradient(circle at 80% 0%, rgba(244, 63, 94, 0.12), transparent 30%),
                  var(--bg);
      padding: 32px;
      display: flex;
      justify-content: center;
    }
    .container {
      width: min(1100px, 100%);
      display: flex;
      flex-direction: column;
      gap: 16px;
    }
    header {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      justify-content: space-between;
      align-items: center;
    }
    h1 {
      margin: 0;
      font-size: 26px;
      letter-spacing: 0.2px;
    }
    .pill {
      padding: 6px 12px;
      border-radius: 999px;
      background: rgba(56, 189, 248, 0.15);
      border: 1px solid rgba(56, 189, 248, 0.35);
      color: var(--text);
      font-size: 13px;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 12px;
    }
    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 16px;
      box-shadow: 0 24px 60px rgba(0,0,0,0.25);
      backdrop-filter: blur(8px);
    }
    .card h2 {
      margin: 0 0 10px;
      font-size: 17px;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .muted { color: var(--muted); font-size: 13px; }
    .value { font-size: 22px; font-weight: 700; }
    .row { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
    .btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      padding: 9px 12px;
      background: rgba(56, 189, 248, 0.15);
      border: 1px solid rgba(56, 189, 248, 0.35);
      color: var(--text);
      border-radius: 10px;
      cursor: pointer;
      text-decoration: none;
      font-weight: 600;
      transition: transform 120ms ease, box-shadow 120ms ease;
    }
    .btn:hover { transform: translateY(-1px); box-shadow: 0 8px 20px rgba(0,0,0,0.35); }
    .btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
    .btn.danger {
      background: rgba(244, 63, 94, 0.15);
      border-color: rgba(244, 63, 94, 0.35);
    }
    .stat-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 10px;
    }
    .status-dot {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: var(--muted);
      box-shadow: 0 0 0 6px rgba(255,255,255,0.05);
    }
    .status-dot.on { background: var(--success); box-shadow: 0 0 0 6px rgba(52, 211, 153, 0.16); }
    .status-dot.off { background: var(--danger); box-shadow: 0 0 0 6px rgba(244, 63, 94, 0.16); }
    .spec-list { list-style: none; padding: 0; margin: 0; display: grid; gap: 6px; }
    .spec-list li { font-size: 14px; color: var(--text); }
    .spec-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 12px; }
    .tag { display: inline-block; padding: 2px 8px; border-radius: 999px; background: rgba(56,189,248,0.16); border: 1px solid rgba(56,189,248,0.35); font-size: 12px; color: var(--text); }
    .toast {
      position: fixed;
      top: 16px;
      right: 16px;
      background: #0b1224;
      border: 1px solid var(--border);
      padding: 12px 14px;
      border-radius: 12px;
      box-shadow: 0 16px 35px rgba(0,0,0,0.35);
      display: none;
      min-width: 220px;
    }
    .toast.show { display: block; }
    @media (max-width: 640px) {
      body { padding: 16px; }
      h1 { font-size: 22px; }
    }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div>
        <h1>📊 STB Monitoring</h1>
        <div class="muted">Realtime stats & alerts (root untuk sensor)</div>
      </div>
      <div class="pill" id="uptime-pill">Uptime: …</div>
    </header>

    <div class="grid">
      <div class="card">
        <h2>⚙️ CPU</h2>
        <div class="value" id="cpu-usage">–</div>
        <div class="muted">Temperatur: <span id="cpu-temp">–</span></div>
        <div class="muted">Auto update setiap beberapa detik.</div>
      </div>

      <div class="card">
        <h2>🧠 Memory</h2>
        <div class="value" id="ram-usage">–</div>
        <div class="muted" id="ram-detail">–</div>
      </div>

      <div class="card">
        <h2>💾 Storage</h2>
        <div class="value" id="disk-usage">–</div>
        <div class="muted" id="disk-detail">–</div>
      </div>

      <div class="card">
        <h2>⏱️ Uptime</h2>
        <div class="value" id="uptime">–</div>
        <div class="muted" id="updated-at">Menunggu data...</div>
      </div>
    </div>

    <div class="spec-grid">
      <div class="card">
        <h2>📱 Device Overview</h2>
        <ul class="spec-list">
          <li><b>Device:</b> Android TV Box (askey B860H V5.0)</li>
          <li><b>OS:</b> Android 12 (API Level 31)</li>
          <li><b>Arch:</b> ARMv8l (64-bit)</li>
          <li><span class="tag">Uptime</span> <span id="overview-uptime">-</span></li>
          <li><span class="tag">IP</span> 192.168.1.58 (eth0)</li>
        </ul>
      </div>

      <div class="card">
        <h2>⚙️ Hardware</h2>
        <ul class="spec-list">
          <li><b>CPU:</b> AMLogic S905X2 · 4x Cortex-A53 @ 1.80 GHz</li>
          <li><b>GPU:</b> Mali-G31 MP2 (Integrated)</li>
          <li><b>RAM:</b> 1.89 GiB total · 51% dipakai (~1 GiB sisa)</li>
          <li><b>Storage:</b> Internal 1.14 GiB (85% used)</li>
          <li><b>Ext/Emu:</b> 3.66 GiB total (2.30 GiB free)</li>
          <li><b>Swap:</b> 384 MiB (0.2% used)</li>
        </ul>
      </div>

      <div class="card">
        <h2>💻 Software</h2>
        <ul class="spec-list">
          <li><b>Kernel:</b> Linux 4.9.269</li>
          <li><b>Shell:</b> Bash 5.3.3</li>
          <li><b>WM:</b> SurfaceFlinger (Android)</li>
          <li><b>Locale:</b> en_US.UTF-8</li>
          <li><b>Packages:</b> 126 (dpkg)</li>
          <li><b>Terminal:</b> /dev/pts/3</li>
        </ul>
      </div>
    </div>
  </div>

  <div class="toast" id="toast"></div>
  <script>
    const state = { stats: ${JSON.stringify(initialStats)} };
    const toastEl = document.getElementById("toast");

    function formatGb(val) { return val ? val.toFixed(2) + " GB" : "N/A"; }
    function formatPercent(val) { return val === null ? "N/A" : val.toFixed(1) + "%"; }
    function formatUptime(sec) {
      if (sec === null || sec === undefined) return "N/A";
      let s = Math.floor(sec);
      const years = Math.floor(s / 31536000); s -= years * 31536000;
      const months = Math.floor(s / 2592000); s -= months * 2592000;
      const days = Math.floor(s / 86400); s -= days * 86400;
      const hours = Math.floor(s / 3600); s -= hours * 3600;
      const minutes = Math.floor(s / 60); s -= minutes * 60;
      const parts = [];
      if (years) parts.push(years + " tahun");
      if (months) parts.push(months + " bulan");
      if (days) parts.push(days + " hari");
      if (hours) parts.push(hours + " jam");
      if (minutes) parts.push(minutes + " menit");
      parts.push(s + " detik");
      return parts.join(" ");
    }
    function showToast(msg) {
      toastEl.textContent = msg;
      toastEl.classList.add("show");
      setTimeout(() => toastEl.classList.remove("show"), 3200);
    }
    function setLoading(isLoading) {
      document.querySelectorAll("button.btn").forEach((btn) => { btn.disabled = isLoading; });
    }
    async function callAction(path) {
      try {
        setLoading(true);
        const res = await fetch(path, { method: "POST" });
        const data = await res.json();
        if (data && data.message) showToast(data.message);
        if (data.stats) updateUI(data.stats);
      } catch (err) {
        showToast("Gagal memproses aksi: " + err.message);
      } finally {
        setLoading(false);
      }
    }
    function updateUI(data) {
      state.stats = data;
      document.getElementById("cpu-usage").textContent = data.cpu === null ? "N/A" : data.cpu.toFixed(1) + "%";
      document.getElementById("cpu-temp").textContent = data.temp === null ? "Tidak tersedia" : data.temp.toFixed(1) + "°C";

      if (data.ram) {
        document.getElementById("ram-usage").textContent = data.ram.percent.toFixed(1) + "%";
        document.getElementById("ram-detail").textContent = formatGb(data.ram.usedGb) + " / " + formatGb(data.ram.totalGb);
      } else {
        document.getElementById("ram-usage").textContent = "N/A";
        document.getElementById("ram-detail").textContent = "Akses RAM dibatasi oleh OS";
      }

      if (data.disk) {
        const diskPercent = data.disk.percent;
        document.getElementById("disk-usage").textContent = (diskPercent === null || diskPercent === undefined)
          ? "N/A"
          : diskPercent.toFixed(1) + "%";
        document.getElementById("disk-detail").textContent = formatGb(data.disk.usedGb) + " / " + formatGb(data.disk.totalGb);
      } else {
        document.getElementById("disk-usage").textContent = "N/A";
        document.getElementById("disk-detail").textContent = "Akses disk dibatasi";
      }

      document.getElementById("uptime").textContent = formatUptime(data.uptimeSec);
      const updatedAt = new Date(data.ts || Date.now());
      document.getElementById("updated-at").textContent = "Update: " + updatedAt.toLocaleTimeString();

      document.getElementById("uptime-pill").textContent = "Uptime: " + formatUptime(data.uptimeSec);
      const overviewUptime = document.getElementById("overview-uptime");
      if (overviewUptime) overviewUptime.textContent = formatUptime(data.uptimeSec);

    }

    function startSSE() {
      const source = new EventSource("/api/stream");
      source.onmessage = (event) => {
        try { updateUI(JSON.parse(event.data)); } catch (err) { console.error(err); }
      };
      source.onerror = () => {
        source.close();
        startPolling();
      };
    }

    let pollTimer = null;
    function startPolling() {
      if (pollTimer) return;
      const pollMs = Math.max(1000, Math.min(10000, getIntervalMs()));
      pollTimer = setInterval(async () => {
        try {
          const res = await fetch("/api/stats");
          const data = await res.json();
          updateUI(data);
        } catch (err) {
          console.error("Polling failed", err);
        }
      }, pollMs);
    }

    document.getElementById("btn-toggle-alert").onclick = () => {
      const enable = state.stats?.alertsEnabled ? 0 : 1;
      callAction("/alerts/toggle?enable=" + enable);
    };

    updateUI(state.stats);
    startSSE();
  </script>
</body>
</html>`;

  res.writeHead(200, { "Content-Type": "text/html" });
  res.end(html);
}

function handleSse(req, res) {
  res.writeHead(200, {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    Connection: "keep-alive",
  });
  res.write("retry: 4000\n\n");

  const id = randomUUID();
  sseClients.set(id, res);
  req.on("close", () => {
    sseClients.delete(id);
  });
}

function broadcastStats(stats) {
  const payload = `data: ${JSON.stringify(stats)}\n\n`;
  for (const res of sseClients.values()) {
    res.write(payload);
  }
}

function toggleAlerts(enable) {
  const next = { ...config, alerts_enabled: enable };
  try {
    saveConfig(next);
  } catch (err) {
    console.warn("[config] Failed to persist alert toggle", err.message);
  }
  config = next;
  return config;
}

function parseUrl(req) {
  return new URL(req.url, "http://localhost");
}

async function handleRequest(req, res) {
  const url = parseUrl(req);
  if (req.method === "GET" && url.pathname === "/") {
    const stats = buildStats();
    renderDashboard(res, stats);
    return;
  }

  if (req.method === "GET" && url.pathname === "/api/stats") {
    const stats = buildStats();
    handleJson(res, stats);
    return;
  }

  if (req.method === "GET" && url.pathname === "/api/stream") {
    handleSse(req, res);
    return;
  }

  if (req.method === "GET" && url.pathname === "/healthz") {
    res.writeHead(200, { "Content-Type": "text/plain" });
    res.end("ok");
    return;
  }

  res.writeHead(404, { "Content-Type": "text/plain" });
  res.end("Not found");
}

const server = http.createServer((req, res) => {
  // Basic security headers
  res.setHeader("X-Content-Type-Options", "nosniff");
  res.setHeader("Cross-Origin-Opener-Policy", "same-origin");
  res.setHeader("Cross-Origin-Embedder-Policy", "require-corp");
  handleRequest(req, res);
});

server.listen(PORT, () => {
  console.log(`Monitoring server listening at http://0.0.0.0:${PORT}`);
});

// Push stats to SSE clients and evaluate alerts every few seconds (configurable 1-10s, default 3s).
function getIntervalMs() {
  const cfgVal = Number(config.polling_interval_sec);
  const sec = Number.isFinite(cfgVal) ? Math.min(Math.max(cfgVal, 1), 10) : 3;
  return sec * 1000;
}

setInterval(() => {
  const stats = buildStats();
  broadcastStats(stats);
  maybeSendAlerts(stats);
}, getIntervalMs());
