from telegram import Update
from telegram.ext import ContextTypes


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = """
<b>📖 Bantuan Bot EPS-TOPIK</b>
Semua perintah gabungan tiga bot di grup ini:

<b>🧪 Azizah-Bot (grup)</b>
<code>/jadwal &lt;jml&gt;</code> – Jadwal pelaksanaan EPS-TOPIK (isi jml opsional)
<code>/reg &lt;jml&gt;</code> – Jadwal pendaftaran EPS-TOPIK
<code>/pass1 &lt;jml&gt;</code> – Hasil Tahap 1 (CBT)
<code>/pass2 &lt;jml&gt;</code> – Hasil Tahap Final (lolos ke Korea)
<code>/get</code> – Pengumuman terbaru G to G
<code>/prelim</code> – Info tahap prelim
<code>/kurs</code> – Kurs 1 KRW → IDR
<code>/kursidr &lt;jml&gt;</code> – KRW → IDR, <code>/kurswon &lt;jml&gt;</code> – IDR → KRW
<code>/kursusd &lt;jml&gt;</code> – USD → IDR, <code>/kursidrusd &lt;jml&gt;</code> – IDR → USD
<code>/adminlist</code> – Daftar admin grup, <code>/cekstrike</code> – Cek strike kamu

<b>🧩 Nichanan-Bot</b>
<code>/cek &lt;nomor&gt;</code> – Cek hasil CBT EPS-TOPIK (hanya di grup; DM khusus admin)
<code>/tanya &lt;pertanyaan&gt;</code> – Tanya Meta AI (hanya di grup; DM khusus admin)
<code>/eps [USER PASS TGL]</code> – Cek progres EPS (hanya di DM & ID yang di-whitelist)

<b>🗒️ Park-Min-Soo-Bot (catatan)</b>
<code>/list</code> – Daftar catatan umum
<code>/notes</code> – Daftar catatan Korea
<code>#hashtag</code> – Lihat detail catatan
👑 Admin: <code>/add</code>, <code>/update</code>, <code>/delete</code>, <code>/add_korea</code>, <code>/update_korea</code>, <code>/delete_korea</code>

⚠️ <b>Admin Grup</b>: <code>/mute</code>, <code>/unmute</code>, <code>/ban</code>, <code>/unban</code>, <code>/restrike</code>
🛡️ <b>Owner</b>: <code>/resetstrikeall</code>, <code>/resetbanall</code>

<b>📎 Lainnya</b>
<code>/help</code> – Tampilkan bantuan ini
<code>/link</code> – Kumpulan link belajar Korea
<code>/cekid</code> – Tampilkan ID chat dan thread

✨ Moderasi aktif: anti spam command, filter kata kasar/topik sensitif, strike otomatis (ban setelah 3), auto mute.

💌 Powered by: <b>LeeBot EPS-TOPIK</b> 🇰🇷🇮🇩
"""
    await update.message.reply_html(message)
