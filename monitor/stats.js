const fs = require("fs");
const os = require("os");
const { execFileSync } = require("child_process");

let lastCpuTimes = null;
let lastCpuInfo = null; // fallback using os.cpus()

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
  if (current) {
    if (!lastCpuTimes) {
      lastCpuTimes = current;
      return null; // need a delta to compute usage
    }
    const totalDiff = current.total - lastCpuTimes.total;
    const idleDiff = current.idle - lastCpuTimes.idle;
    lastCpuTimes = current;
    if (totalDiff > 0) {
      const usage = ((totalDiff - idleDiff) / totalDiff) * 100;
      return Number(usage.toFixed(1));
    }
  }

  // Fallback: use os.cpus() times delta
  const infos = os.cpus();
  if (!infos || !infos.length) return null;
  const aggregate = infos.reduce(
    (acc, cpu) => {
      const t = cpu.times;
      acc.idle += t.idle;
      acc.total += t.user + t.nice + t.sys + t.irq + t.idle;
      return acc;
    },
    { idle: 0, total: 0 }
  );
  if (!lastCpuInfo) {
    lastCpuInfo = aggregate;
    return null;
  }
  const totalDiff = aggregate.total - lastCpuInfo.total;
  const idleDiff = aggregate.idle - lastCpuInfo.idle;
  lastCpuInfo = aggregate;
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
    const percent = total > 0 ? (used / total) * 100 : 0;
    return {
      total,
      used,
      percent: Number(percent.toFixed(1)),
    };
  } catch (err) {
    console.warn("[stats] RAM read failed", err.message);
    // Fallback via /proc/meminfo
    try {
      const meminfo = fs.readFileSync("/proc/meminfo", "utf8");
      const lines = Object.fromEntries(
        meminfo
          .split("\n")
          .filter(Boolean)
          .map((l) => l.split(":"))
          .map(([k, v]) => [k.trim(), v.trim()])
      );
      const total = lines.MemTotal ? parseInt(lines.MemTotal, 10) * 1024 : null;
      const free = lines.MemAvailable
        ? parseInt(lines.MemAvailable, 10) * 1024
        : null;
      if (total && free) {
        const used = total - free;
        const percent = (used / total) * 100;
        return {
          total,
          used,
          percent: Number(percent.toFixed(1)),
        };
      }
    } catch (err2) {
      console.warn("[stats] RAM fallback failed", err2.message);
    }
    return null;
  }
}

function getDiskStats() {
  try {
    const output = execFileSync("df", ["-k", "/"], { encoding: "utf8" });
    const [, dataLine] = output.trim().split("\n");
    if (!dataLine) throw new Error("df no dataLine");
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
    console.warn("[stats] Disk read failed (/):", err.message);
    // Fallback: try /data
    try {
      const output = execFileSync("df", ["-k", "/data"], { encoding: "utf8" });
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
    } catch (err2) {
      console.warn("[stats] Disk read failed (/data):", err2.message);
      return null;
    }
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

function buildStats(config) {
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

function primeCpu() {
  getCpuPercent();
}

module.exports = {
  buildStats,
  primeCpu,
};
