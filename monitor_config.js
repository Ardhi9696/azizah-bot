// Shared configuration for the Node.js monitoring server.
// Mirrors the values used by the former Flask monitor so paths stay compatible.
const fs = require("fs");
const path = require("path");

const TERMUX_HOME = "/data/data/com.termux/files/home";
const TMUX_BIN = "/data/data/com.termux/files/usr/bin/tmux";

// Bot location and start command
const BOT_DIR = `${TERMUX_HOME}/Azizah-Bot`;
const BOT_COMMAND = "python3 run.py";

// Telegram credentials for alert notifications
const TELEGRAM_BOT_TOKEN = "7777245606:AAEo9fS7AH7Of9DSngYPEtfECS1Hbmh2j9Q";
const TELEGRAM_CHAT_ID = "7088612068";

// Where alert config is stored; fall back to repo copy when running locally.
const CONFIG_FILE = path.join(TERMUX_HOME, "monitor_config.json");
const LOCAL_CONFIG_FILE = path.join(__dirname, "monitor_config.json");

const DEFAULT_CONFIG = {
  alerts_enabled: true,
  ram_threshold: 90,
  temp_threshold: 75,
};

function safeReadJson(filePath) {
  try {
    if (!fs.existsSync(filePath)) return null;
    const raw = fs.readFileSync(filePath, "utf8");
    return JSON.parse(raw);
  } catch (err) {
    console.warn("[config] Failed to read", filePath, err.message);
    return null;
  }
}

function loadConfig() {
  const merged = { ...DEFAULT_CONFIG };
  const candidates = [CONFIG_FILE, LOCAL_CONFIG_FILE];
  for (const file of candidates) {
    const data = safeReadJson(file);
    if (data) {
      Object.assign(merged, data);
      break;
    }
  }
  return merged;
}

function saveConfig(nextConfig) {
  const payload = { ...DEFAULT_CONFIG, ...nextConfig };
  const targets = [CONFIG_FILE, LOCAL_CONFIG_FILE];

  for (const file of targets) {
    try {
      fs.writeFileSync(file, JSON.stringify(payload));
      return file;
    } catch (err) {
      console.warn("[config] Failed to write", file, err.message);
    }
  }
  throw new Error("Unable to write config to any known location");
}

module.exports = {
  TERMUX_HOME,
  TMUX_BIN,
  BOT_DIR,
  BOT_COMMAND,
  TELEGRAM_BOT_TOKEN,
  TELEGRAM_CHAT_ID,
  CONFIG_FILE,
  LOCAL_CONFIG_FILE,
  DEFAULT_CONFIG,
  loadConfig,
  saveConfig,
};
