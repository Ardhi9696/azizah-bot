function renderDashboard(res, initialStats, config) {
  const polling = Number.isFinite(Number(config.polling_interval_sec))
    ? Math.min(Math.max(Number(config.polling_interval_sec), 1), 10)
    : 3;

  const html = `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Set Top Box Monitoring</title>
  <link rel="icon" href="/icon.png">
  <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Cdefs%3E%3ClinearGradient id='g' x1='0' x2='1' y1='0' y2='1'%3E%3Cstop stop-color='%2338bdf8'/%3E%3Cstop offset='1' stop-color='%23f43f5e'/%3E%3C/linearGradient%3E%3C/defs%3E%3Crect width='64' height='64' rx='14' fill='%23050917'/%3E%3Cpath fill='url(%23g)' d='M18 24c0-4 3-7 7-7h14c4 0 7 3 7 7v16c0 4-3 7-7 7H25c-4 0-7-3-7-7V24z'/%3E%3Cpath fill='none' stroke='%23e5e7eb' stroke-width='3' stroke-linecap='round' d='M24 24v16m16-16v16M20 30h24M20 38h24'/%3E%3Ccircle cx='32' cy='32' r='4' fill='%23e5e7eb'/%3E%3C/svg%3E">
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
    .container { width: min(1100px, 100%); display: flex; flex-direction: column; gap: 16px; }
    header { display: flex; flex-wrap: wrap; gap: 12px; justify-content: space-between; align-items: center; }
    h1 { margin: 0; font-size: 26px; letter-spacing: 0.2px; }
    .pill { padding: 6px 12px; border-radius: 999px; background: rgba(56, 189, 248, 0.15); border: 1px solid rgba(56, 189, 248, 0.35); color: var(--text); font-size: 13px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px; }
    .card { background: var(--card); border: 1px solid var(--border); border-radius: 14px; padding: 16px; box-shadow: 0 24px 60px rgba(0,0,0,0.25); backdrop-filter: blur(8px); }
    .card h2 { margin: 0 0 10px; font-size: 17px; display: flex; align-items: center; gap: 8px; }
    .muted { color: var(--muted); font-size: 13px; }
    .value { font-size: 22px; font-weight: 700; }
    .row { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
    .spec-list { list-style: none; padding: 0; margin: 0; display: grid; gap: 6px; }
    .spec-list li { font-size: 14px; color: var(--text); }
    .spec-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 12px; }
    .tag { display: inline-block; padding: 2px 8px; border-radius: 999px; background: rgba(56,189,248,0.16); border: 1px solid rgba(56,189,248,0.35); font-size: 12px; color: var(--text); }
    .toast { position: fixed; top: 16px; right: 16px; background: #0b1224; border: 1px solid var(--border); padding: 12px 14px; border-radius: 12px; box-shadow: 0 16px 35px rgba(0,0,0,0.35); display: none; min-width: 220px; }
    .toast.show { display: block; }
    @media (max-width: 640px) { body { padding: 16px; } h1 { font-size: 22px; } }
    .bar { width: 100%; background: #0b1224; border: 1px solid var(--border); border-radius: 10px; height: 12px; overflow: hidden; margin-top: 8px; }
    .bar-fill { height: 100%; width: 0%; background: linear-gradient(90deg, #38bdf8, #34d399); transition: width 160ms ease, background 160ms ease; }
    .bar-fill.danger { background: linear-gradient(90deg, #f43f5e, #f59e0b); }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div>
        <h1>📊 Set Top Box Monitoring</h1>
        <div class="muted">Realtime stats & alerts</div>
      </div>
      <div class="pill" id="uptime-pill">Uptime: …</div>
    </header>

    <div class="grid">
      <div class="card">
        <h2>⚙️ CPU</h2>
        <div class="value" id="cpu-usage">–</div>
        <div class="muted">Temperatur: <span id="cpu-temp">–</span></div>
        <div class="muted">Auto update.</div>
        <div class="bar"><div class="bar-fill" id="bar-cpu"></div></div>
      </div>

      <div class="card">
        <h2>🧠 Memory</h2>
        <div class="value" id="ram-usage">–</div>
        <div class="muted" id="ram-detail">–</div>
        <div class="bar"><div class="bar-fill" id="bar-ram"></div></div>
      </div>

      <div class="card">
        <h2>💾 Storage</h2>
        <div class="value" id="disk-usage">–</div>
        <div class="muted" id="disk-detail">–</div>
        <div class="bar"><div class="bar-fill" id="bar-disk"></div></div>
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
          <li><b>Device:</b> Android TV Box (ZTE B860H V5.0)</li>
          <li><b>OS:</b> Android 12 (API Level 31)</li>
          <li><b>Arch:</b> ARMv8l (64-bit)</li>
          <li><span class="tag">Uptime</span> <span id="overview-uptime">-</span></li>
          <li><span class="tag">IP</span> 192.168.1.xx</li>
        </ul>
      </div>

      <div class="card">
        <h2>⚙️ Hardware</h2>
        <ul class="spec-list">
          <li><b>CPU:</b> AMLogic S905X2 · 4x Cortex-A53 @ 1.80 GHz</li>
          <li><b>GPU:</b> Mali-G31 MP2 (Integrated)</li>
          <li><b>RAM:</b> 2 GB total</li>
          <li><b>Storage:</b> Internal 8 GB total</li>
          <li><b>Swap:</b> 400 MB</li>
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
    const state = { stats: ${JSON.stringify(initialStats)}, intervalSec: ${polling} };
    const toastEl = document.getElementById("toast");

    function formatGb(val) { return val ? val.toFixed(2) + " GiB" : "N/A"; }
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
      const barCpu = document.getElementById("bar-cpu");
      if (barCpu) {
        const cpuVal = data.cpu;
        if (cpuVal === null || cpuVal === undefined) {
          barCpu.style.width = "0%";
          barCpu.classList.remove("danger");
        } else {
          const clamped = Math.min(Math.max(cpuVal, 0), 100);
          barCpu.style.width = clamped + "%";
          barCpu.classList.toggle("danger", clamped >= 85);
        }
      }
      document.getElementById("cpu-temp").textContent = data.temp === null ? "Tidak tersedia" : data.temp.toFixed(1) + "°C";

      if (data.ram) {
        document.getElementById("ram-usage").textContent = data.ram.percent.toFixed(1) + "%";
        document.getElementById("ram-detail").textContent = formatGb(data.ram.usedGb) + " / " + formatGb(data.ram.totalGb);
        const barRam = document.getElementById("bar-ram");
        if (barRam) {
          const clamped = Math.min(Math.max(data.ram.percent, 0), 100);
          barRam.style.width = clamped + "%";
          barRam.classList.toggle("danger", clamped >= 85);
        }
      } else {
        document.getElementById("ram-usage").textContent = "N/A";
        document.getElementById("ram-detail").textContent = "Akses RAM dibatasi oleh OS";
        const barRam = document.getElementById("bar-ram");
        if (barRam) {
          barRam.style.width = "0%";
          barRam.classList.remove("danger");
        }
      }

      if (data.disk) {
        const diskPercent = data.disk.percent;
        document.getElementById("disk-usage").textContent = (diskPercent === null || diskPercent === undefined)
          ? "N/A"
          : diskPercent.toFixed(1) + "%";
        const mountInfo = data.disk.mount ? " (" + data.disk.mount + ")" : "";
        document.getElementById("disk-detail").textContent =
          formatGb(data.disk.usedGb) + " / " + formatGb(data.disk.totalGb) + mountInfo;
        const barDisk = document.getElementById("bar-disk");
        if (barDisk) {
          if (diskPercent === null || diskPercent === undefined) {
            barDisk.style.width = "0%";
            barDisk.classList.remove("danger");
          } else {
            const clamped = Math.min(Math.max(diskPercent, 0), 100);
            barDisk.style.width = clamped + "%";
            barDisk.classList.toggle("danger", clamped >= 85);
          }
        }
      } else {
        document.getElementById("disk-usage").textContent = "N/A";
        document.getElementById("disk-detail").textContent = "Akses disk dibatasi";
        const barDisk = document.getElementById("bar-disk");
        if (barDisk) {
          barDisk.style.width = "0%";
          barDisk.classList.remove("danger");
        }
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
      const pollMs = Math.max(1000, Math.min(10000, state.intervalSec * 1000));
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

    updateUI(state.stats);
    startSSE();
  </script>
</body>
</html>`;

  res.writeHead(200, { "Content-Type": "text/html" });
  res.end(html);
}

module.exports = { renderDashboard };
