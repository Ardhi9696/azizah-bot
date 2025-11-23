const { TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID } = require("./config");

const ALERT_COOLDOWN_SEC = 300; // 5 menit
let lastRamAlert = 0;
let lastTempAlert = 0;
let lastDiskAlert = 0;

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

function maybeSendAlerts(stats, config) {
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

module.exports = { maybeSendAlerts };
