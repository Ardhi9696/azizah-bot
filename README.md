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

- Jalankan dengan `node monitor_server.js` (port default 8000). Pastikan Node.js 18+ terpasang.
- Dashboard auto hot-reload data via SSE/polling; tidak ada kontrol bot (hanya monitor + toggle alert).
- Untuk akses sensor penuh, jalankan monitor sebagai root (misal tmux root via `start_monitor_root.sh`).
- Bot tetap dijalankan sebagai user biasa (tmux session `telebot`), terpisah dari monitor.
- Konfigurasi alert tersimpan di `monitor_config.json` (fallback di repo jika path Termux tidak ada).
- Endpoint cepat: `/` dashboard, `/api/stats` JSON, `/api/stream` SSE feed, toggle alert di `/alerts/toggle`.
