# 🇰🇷 EPS-TOPIK Telegram Bot

Bot Telegram untuk komunitas EPS-TOPIK Indonesia, dilengkapi dengan:

- 🔐 Sistem verifikasi member baru (auto kick jika tidak menyetujui aturan)
- ⚔️ Moderasi otomatis (kata terlarang, kasar, topik sensitif)
- 👮‍♂️ Admin tools (mute, ban, unban, cek strike)
- 📅 Pengambilan data EPS Korea ringan (jadwal/pengumuman via HTTP, tanpa Playwright/Selenium)

---

## 🚀 Cara Menjalankan

### 1. Buat file `.env`:

```env
BOT_TOKEN=isi_token_bot_anda
ADMIN_LIST=123456789,987654321
MY_TELEGRAM_ID=123456789
Bisa juga untuk cek akun EPS
```

---

## 🖥️ Monitoring Dashboard (Node.js)

- Jalankan dengan `node monitor/server.js` (port default 8000). Pastikan Node.js 18+ terpasang.
- Dashboard auto hot-reload data via SSE/polling; hanya monitoring (tidak ada kontrol bot).
- Untuk akses sensor penuh, jalankan monitor sebagai root (misal tmux root via `start_monitor_root.sh`).
- Bot tetap dijalankan sebagai user biasa (tmux session `telebot`), terpisah dari monitor.
- Konfigurasi tersimpan di `monitor_config.json` (Termux home, fallback di `monitor/monitor_config.json`):
  - `alerts_enabled`: true/false untuk kirim notifikasi (suhu, RAM, storage) via Telegram.
  - `ram_threshold`, `temp_threshold`, `storage_threshold`: angka persen/derajat.
  - `polling_interval_sec`: 1–10 (default 3) untuk interval update SSE/polling.
- Endpoint cepat: `/` dashboard, `/api/stats` JSON, `/api/stream` SSE feed.

## 🧹 Catatan

- Folder `handlers_heavy` sudah dihapus (bot tidak lagi memuat modul berat tersebut).
- Struktur bot:
  - `handlers/` berisi command, moderasi, autoreply (`register_handlers.py` sebagai entry).
  - `utils/constants.py` menyimpan lokasi file data/log.
  - Data bot di `data/` (misal `respon.json`, `autoreply.json`, cache EPS, dll).
  - Monitor terpisah di folder `monitor/` (config/stats/alerts/server).
- Prioritas handler: moderasi lebih dulu, lalu autoreply, lalu responder mention/reply (diatur via `group` di `register_handlers.py`).
