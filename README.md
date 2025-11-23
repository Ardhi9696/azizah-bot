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
- Dashboard akan otomatis hot-reload data via SSE/polling tanpa perlu refresh halaman.
- Jika monitor perlu akses sensor (harus root), jalankan monitor dengan `TMUX_SOCKET` menunjuk ke socket tmux milik user bot, misal di `start_monitor_root.sh`:
  ```
  TMUX_SOCKET=/data/data/com.termux/files/usr/tmp/tmux-XXXX/default
  TMUX_SOCKET=$TMUX_SOCKET tmux new-session -d -s monitor "cd ~/Azizah-Bot && TMUX_SOCKET=$TMUX_SOCKET node monitor_server.js"
  ```
  (script ini sudah mencari socket otomatis; sesuaikan jika path berbeda)
- Konfigurasi alert tersimpan di `monitor_config.json` (fallback di repo jika path Termux tidak ada).
- Endpoint cepat: `/` dashboard, `/api/stats` JSON, `/api/stream` SSE feed, aksi bot di `/bot/start|stop|restart`.
