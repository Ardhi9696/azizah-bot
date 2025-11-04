# handlers/eps_core/formatter.py
from html import escape as _esc
import re
from typing import Optional, Tuple, Dict, Any
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from .constants import DATE_RE, EMOJI_MAP, NORMALIZE_LABELS


def _fd(text: str) -> str:
    """Extract date from text"""
    m = DATE_RE.search(text or "")
    return m.group(0) if m else "-"


def _esc_text(s: str) -> str:
    """Escape text for HTML"""
    return _esc(s or "", quote=False)


def _to_int(v) -> int:
    """Convert to integer safely"""
    try:
        return int(str(v).strip())
    except Exception:
        return 0


def _roster_key(r) -> int:
    """Sort key for roster"""
    try:
        return int(re.sub(r"\D", "", r.get("no", "") or "0") or 0)
    except Exception:
        return 0


def _ekstrak_tanggal_lulus_dari_riwayat(riwayat: list) -> Tuple[Optional[str], Optional[str]]:
    """
    Ekstrak tanggal lulus ujian bahasa Korea dari riwayat progres
    
    Returns:
        Tuple[tanggal_lulus_str, nama_prosedur]
    """
    try:
        for prosedur_raw, status_txt, tanggal in riwayat:
            prosedur = NORMALIZE_LABELS.get(prosedur_raw, prosedur_raw).strip()

            # Cek apakah ini ujian bahasa Korea dan statusnya Lulus
            if any(
                keyword in prosedur.lower()
                for keyword in [
                    "ujian bahasa korea",
                    "korean language",
                    "한국어능력시험",
                    "korean language test",
                    "eps-topik",
                ]
            ):
                status_lower = (status_txt or "").lower()
                if (
                    "lulus" in status_lower
                    or "pass" in status_lower
                    or "합격" in status_lower
                    or "completed" in status_lower
                ):
                    if tanggal and tanggal != "-":
                        # Ekstrak tanggal dari format "2024-07-26"
                        match = DATE_RE.search(tanggal)
                        if match:
                            return match.group(0), prosedur

        return None, None
    except Exception:
        return None, None


def _hitung_sisa_masa_berlaku_detail(tanggal_lulus_str: str) -> Dict[str, Any]:
    """
    Hitung sisa masa berlaku sertifikat secara detail (2 tahun - 1 hari dari tanggal lulus)
    
    Contoh: 
    - Lulus: 26 July 2024
    - Berakhir: 25 July 2026
    
    Returns:
        Dict dengan informasi lengkap masa berlaku
    """
    try:
        if not tanggal_lulus_str:
            return {
                "status": "error",
                "message": "❓ <b>Tanggal lulus tidak ditemukan</b>",
                "is_expired": False,
                "days_remaining": 0
            }

        # Parse tanggal lulus
        tanggal_lulus = datetime.strptime(tanggal_lulus_str, "%Y-%m-%d").date()

        # Hitung tanggal kedaluwarsa (2 tahun dari tanggal lulus MINUS 1 hari)
        # Contoh: 26 July 2024 → 26 July 2026 → 25 July 2026
        tanggal_kedaluwarsa = tanggal_lulus + relativedelta(years=2) - timedelta(days=1)

        # Hari ini
        hari_ini = date.today()

        # Format tanggal untuk display
        tgl_lulus_display = tanggal_lulus.strftime("%d %b %Y")
        tgl_expire_display = tanggal_kedaluwarsa.strftime("%d %b %Y")

        # Hitung selisih
        if hari_ini > tanggal_kedaluwarsa:
            hari_terlambat = (hari_ini - tanggal_kedaluwarsa).days
            return {
                "status": "expired",
                "message": f"⛔ <b>KEDALUWARSA ({hari_terlambat} hari)</b>",
                "tanggal_lulus": tgl_lulus_display,
                "tanggal_kedaluwarsa": tgl_expire_display,
                "is_expired": True,
                "days_overdue": hari_terlambat,
                "days_remaining": 0
            }

        # Hitung sisa waktu
        sisa = relativedelta(tanggal_kedaluwarsa, hari_ini)
        total_hari_sisa = (tanggal_kedaluwarsa - hari_ini).days

        # Format output berdasarkan urgency
        if sisa.years >= 1:
            status_msg = f"🟢 <b>{sisa.years} tahun {sisa.months} bulan {sisa.days} hari</b>"
            status_type = "safe"
        elif total_hari_sisa >= 180:  # 6 bulan
            status_msg = f"🟡 <b>{sisa.months} bulan {sisa.days} hari</b>"
            status_type = "warning"
        elif total_hari_sisa >= 90:   # 3 bulan
            status_msg = f"🟠 <b>{sisa.months} bulan {sisa.days} hari</b>"
            status_type = "caution"
        elif total_hari_sisa >= 30:   # 1 bulan
            status_msg = f"🔴 <b>{sisa.months} bulan {sisa.days} hari</b>"
            status_type = "danger"
        else:
            status_msg = f"🚨 <b>{sisa.days} HARI LAGI!</b>"
            status_type = "critical"

        return {
            "status": status_type,
            "message": status_msg,
            "tanggal_lulus": tgl_lulus_display,
            "tanggal_kedaluwarsa": tgl_expire_display,
            "years": sisa.years,
            "months": sisa.months,
            "days": sisa.days,
            "is_expired": False,
            "days_remaining": total_hari_sisa
        }

    except ValueError:
        return {
            "status": "error", 
            "message": "❓ <b>Format tanggal tidak valid</b>",
            "is_expired": False,
            "days_remaining": 0
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"❓ <b>Error perhitungan: {str(e)}</b>",
            "is_expired": False, 
            "days_remaining": 0
        }


def _format_masa_berlaku_section(tanggal_lulus: str, nama_prosedur: str) -> str:
    """Format section masa berlaku sertifikat"""
    if not tanggal_lulus:
        return ""

    masa_info = _hitung_sisa_masa_berlaku_detail(tanggal_lulus)
    
    lines = []
    lines.append("\n━━━━━━━━━━━━━━━━━━━")
    lines.append("📅 <b>Masa Berlaku Sertifikat Bahasa Korea</b>")
    lines.append(f"📝 <i>Prosedur:</i> {_esc_text(nama_prosedur)}")
    lines.append(f"🎓 <i>Tanggal Lulus:</i> <code>{masa_info['tanggal_lulus']}</code>")
    lines.append(f"⏰ <i>Kedaluwarsa:</i> <code>{masa_info['tanggal_kedaluwarsa']}</code>")
    
    # Status dengan warna berdasarkan urgency
    lines.append(f"📊 <i>Sisa Waktu:</i> {masa_info['message']}")
    
    # Additional info berdasarkan status
    if masa_info['status'] == 'expired':
        lines.append(f"⚠️ <i>Status:</i> <b>TELAH KEDALUWARSA</b>")
        lines.append(f"📆 <i>Terlambat:</i> <b>{masa_info['days_overdue']} hari</b>")
    elif masa_info['status'] == 'critical':
        lines.append(f"🚨 <i>Status:</i> <b>SEGERA HABIS!</b>")
        lines.append(f"📆 <i>Hari Tersisa:</i> <b>{masa_info['days_remaining']} hari</b>")
    elif masa_info['status'] == 'danger':
        lines.append(f"🔴 <i>Status:</i> <b>WASPADA</b>")
        lines.append(f"📆 <i>Hari Tersisa:</i> <b>{masa_info['days_remaining']} hari</b>")
    elif masa_info['status'] == 'caution':
        lines.append(f"🟠 <i>Status:</i> <b>PERHATIAN</b>")
        lines.append(f"📆 <i>Hari Tersisa:</i> <b>{masa_info['days_remaining']} hari</b>")
    elif masa_info['status'] == 'warning':
        lines.append(f"🟡 <i>Status:</i> <b>AMAN</b>")
        lines.append(f"📆 <i>Hari Tersisa:</i> <b>{masa_info['days_remaining']} hari</b>")
    elif masa_info['status'] == 'safe':
        lines.append(f"🟢 <i>Status:</i> <b>SANGAT AMAN</b>")
        lines.append(f"📆 <i>Hari Tersisa:</i> <b>{masa_info['days_remaining']} hari</b>")
    else:
        lines.append(f"❓ <i>Status:</i> <b>Tidak Diketahui</b>")

    return "\n".join(lines)


def format_data(data: dict, status: str = "", checked_at: Optional[str] = None) -> str:
    """Format EPS data dengan masa berlaku sertifikat yang detail"""
    
    nama = _esc_text(data.get("nama", "-"))
    aktif_ref = _esc_text(data.get("aktif_ref_id") or "-")

    peng = data.get("pengiriman") or {}
    t_kirim = _esc_text(peng.get("tanggal_kirim", "-"))
    t_terima = _esc_text(_fd(peng.get("tanggal_terima", "-")))
    ref_id_latest = _esc_text(peng.get("ref_id") or "-")

    pengiriman_list = data.get("pengiriman_list") or []
    total_mediasi = sum(_to_int(r.get("mediasi", 0)) for r in pengiriman_list)

    # ====== EKSTRAK TANGGAL LULUS DAN HITUNG SISA MASA BERLAKU ======
    riwayat = data.get("riwayat", []) or []
    tanggal_lulus, nama_prosedur = _ekstrak_tanggal_lulus_dari_riwayat(riwayat)
    # ================================================================

    title_suffix = f" {status}".strip() if status else ""
    lines = []
    
    # Header
    lines.append(f"📋 <b>Hasil Kemajuan EPS{title_suffix}</b>")
    lines.append("━━━━━━━━━━━━━━━━━━━")
    
    # Data Utama
    lines.append("📬 <b>Data Utama</b>")
    lines.append(f"👤 <i>Nama:</i> <b>{nama}</b>")
    lines.append(f"🆔 <i>ID Aktif:</i> <code>{aktif_ref}</code>")
    lines.append(f"📮 <i>Pengiriman Terbaru:</i> <code>{t_kirim}</code>")
    lines.append(f"📥 <i>Penerimaan Terbaru:</i> <code>{t_terima}</code>")
    
    if ref_id_latest and ref_id_latest != "-":
        lines.append(f"🆔 <i>ID Nodongbu Terbaru:</i> <code>{ref_id_latest}</code>")

    # Section Masa Berlaku (jika ada tanggal lulus)
    if tanggal_lulus:
        masa_section = _format_masa_berlaku_section(tanggal_lulus, nama_prosedur or "Ujian Bahasa Korea")
        lines.append(masa_section)
    else:
        # Tampilkan info jika belum ada sertifikat
        lines.append("\n━━━━━━━━━━━━━━━━━━━")
        lines.append("📅 <b>Masa Berlaku Sertifikat</b>")
        lines.append("❌ <i>Belum ada sertifikat bahasa Korea yang berlaku</i>")

    # Riwayat roster & mediasi
    if pengiriman_list:
        lines.append("\n━━━━━━━━━━━━━━━━━━━")
        lines.append("📦 <b>Riwayat Pengiriman & Mediasi</b>")
        
        for r in sorted(pengiriman_list, key=_roster_key):
            no = _esc_text(r.get("no", "-"))
            rid = _esc_text(r.get("ref_id") or "-")
            kirim = _esc_text(r.get("tanggal_kirim", "-"))
            terima = _esc_text(r.get("tanggal_terima", "-"))
            masa = _esc_text(r.get("masa_berlaku") or "")
            med = _esc_text(str(r.get("mediasi", "-")))

            lines.append(f"\n<b>• Roster #{no}</b>")
            lines.append(f"  🆔 <i>ID:</i> <code>{rid}</code>")
            lines.append(f"  📤 <i>Tanggal Kirim:</i> {kirim}")
            lines.append(f"  📥 <i>Tanggal Terima:</i> {terima}")
            if masa:
                lines.append(f"  ⏰ <i>Masa Berlaku:</i> {masa}")
            lines.append(f"  💬 <i>Jumlah Mediasi:</i> <b>{med} kali</b>")

        if pengiriman_list:
            last_no = _esc_text(sorted(pengiriman_list, key=_roster_key)[-1].get("no", "-"))
            lines.append(
                f"\n📊 <b>Total Mediasi (Roster 1–{last_no}):</b> <b>{total_mediasi} kali</b>"
            )

    # Progres (single loop) + sematan link
    if riwayat:
        lines.append("\n━━━━━━━━━━━━━━━━━━━")
        lines.append("🧾 <b>Progres Kemajuan Imigrasi</b>")

        job_links = data.get("tautan_pekerjaan") or {}

        for idx, (prosedur_raw, status_txt, tanggal) in enumerate(riwayat, 1):
            prosedur = NORMALIZE_LABELS.get(prosedur_raw, prosedur_raw).strip()
            emoji = EMOJI_MAP.get(prosedur, "🔹")

            # status sudah plain text, tapi tetap escape
            status_bersih = re.sub(
                r"\b(URL|IMG2?|ROAD VIEW)\b", "", status_txt or "", flags=re.IGNORECASE
            )
            status_bersih = re.sub(r"\s{2,}", " ", status_bersih).strip()
            status_safe = _esc_text(status_bersih)

            tanggal_safe = _esc_text(tanggal or "")
            tanggal_str = f" ({tanggal_safe})" if tanggal_safe not in ("", "-") else ""

            line = f"\n{idx:02d}. {emoji} { _esc_text(prosedur) } — <b>{status_safe}</b>{tanggal_str}"

            # sisipkan link hanya untuk baris 'Keadaan pencarian pekerjaan'
            if prosedur in ("Keadaan pencarian pekerjaan", "구직 진행상태") and job_links:
                btns = []
                if job_links.get("url"):
                    btns.append(f'<a href="{job_links["url"]}">URL</a>')
                if job_links.get("img"):
                    btns.append(f'<a href="{job_links["img"]}">IMG</a>')
                if job_links.get("img2"):
                    btns.append(f'<a href="{job_links["img2"]}">IMG2</a>')
                if job_links.get("road_view"):
                    btns.append(f'<a href="{job_links["road_view"]}">ROAD VIEW</a>')
                if btns:
                    line += "  •  " + " | ".join(btns)

            lines.append(line)

    # Footer dengan timestamp
    if checked_at:
        lines.append("\n━━━━━━━━━━━━━━━━━━━")
        lines.append(f"🕒 <i>Dicek pada:</i> <code>{_esc_text(checked_at)}</code>")

    return "\n".join(lines)


# Fungsi untuk testing perhitungan
def test_perhitungan_masa_berlaku():
    """Test function untuk verifikasi perhitungan"""
    test_cases = [
        "2024-07-26",  # Lulus 26 July 2024 → Berakhir 25 July 2026
        "2023-12-15",  # Lulus 15 Dec 2023 → Berakhir 14 Dec 2025
        "2024-02-29",  # Leap year test
    ]
    
    for tgl_lulus in test_cases:
        info = _hitung_sisa_masa_berlaku_detail(tgl_lulus)
        print(f"Lulus: {tgl_lulus} → Kedaluwarsa: {info['tanggal_kedaluwarsa']}")
        print(f"Sisa: {info['message']}")
        print("---")