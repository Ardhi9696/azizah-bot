const http = require("http");
const path = require("path");
const fs = require("fs");
const { randomUUID } = require("crypto");

const { buildStats, primeCpu } = require("./stats");
const { maybeSendAlerts } = require("./alerts");
const { loadConfig } = require("./config");
const { renderDashboard } = require("./ui");

const PORT = process.env.MONITOR_PORT || 8000;

// In-memory state
let config = loadConfig();
const sseClients = new Map(); // id -> response

// Prime CPU reading so the first response is not empty.
primeCpu();

function handleJson(res, payload, status = 200) {
  res.writeHead(status, { "Content-Type": "application/json" });
  res.end(JSON.stringify(payload));
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

function parseUrl(req) {
  return new URL(req.url, "http://localhost");
}

function getIntervalMs() {
  const cfgVal = Number(config.polling_interval_sec);
  const sec = Number.isFinite(cfgVal) ? Math.min(Math.max(cfgVal, 1), 10) : 3;
  return sec * 1000;
}

function handleRequest(req, res) {
  const url = parseUrl(req);
  if (req.method === "GET" && url.pathname === "/icon.png") {
    const iconPath = path.join(__dirname, "icon.png");
    if (fs.existsSync(iconPath)) {
      const buf = fs.readFileSync(iconPath);
      res.writeHead(200, { "Content-Type": "image/png" });
      res.end(buf);
    } else {
      res.writeHead(404, { "Content-Type": "text/plain" });
      res.end("icon not found");
    }
    return;
  }

  if (req.method === "GET" && url.pathname === "/") {
    const stats = buildStats(config);
    renderDashboard(res, stats, config);
    return;
  }

  if (req.method === "GET" && url.pathname === "/api/stats") {
    const stats = buildStats(config);
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
setInterval(() => {
  const stats = buildStats(config);
  broadcastStats(stats);
  maybeSendAlerts(stats, config);
}, getIntervalMs());
