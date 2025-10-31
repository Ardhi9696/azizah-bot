# handlers/eps_core/formatter.py
from html import escape as _esc
import re
from typing import Optional
from datetime import datetime
from dateutil.relativedelta import relativedelta
from .constants import DATE_RE, EMOJI_MAP, NORMALIZE_LABELS


def _fd(text: str) -> str:
    m = DATE_RE.search(text or "")
    return m.group(0) if m else "-"


def _esc_text(s: str) -> str:
    # Escape &, <, > (biar aman untuk parse_mode="HTML")
    return _esc(s or "", quote=False)


def _to_int(v):
    try:
        return int(str(v).strip())
    except Exception:
        return 0


def _roster_key(r):
    import re as _re

    try:
        return int(_re.sub(r"\D", "", r.get("no", "") or "0") or 0)
    except Exception:
        return 0


def _ekstrak_tanggal_lulus_dari_riwayat(riwayat: list) -> Optional[str]:
    """
    Ekstrak tanggal lulus ujian bahasa Korea dari riwayat progres
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
                ]
            ):
                if (
                    "lulus" in (status_txt or "").lower()
                    or "pass" in (status_txt or "").lower()
                ):
                    if tanggal and tanggal != "-":
                        # Ekstrak tanggal dari format "2024-07-26"
                        match = DATE_RE.search(tanggal)
                        if match:
                            return match.group(0)

        return None
    except Exception:
        return None


def _hitung_sisa_masa_berlaku(tanggal_lulus_str: str) -> str:
    """
    Hitung sisa masa berlaku sertifikat (2 tahun dari tanggal lulus)
    """
    try:
        if not tanggal_lulus_str:
            return "❓ <b>Tanggal lulus tidak ditemukan</b>"

        # Parse tanggal lulus
        tanggal_lulus = datetime.strptime(tanggal_lulus_str, "%Y-%m-%d")

        # Hitung tanggal kedaluwarsa (2 tahun dari tanggal lulus)
        tanggal_kedaluwarsa = tanggal_lulus + relativedelta(years=2)

        # Hitung selisih dengan hari ini
        hari_ini = datetime.now()

        # Format tanggal untuk display
        tgl_lulus_display = tanggal_lulus.strftime("%d %b %Y")
        tgl_expire_display = tanggal_kedaluwarsa.strftime("%d %b %Y")

        if hari_ini > tanggal_kedaluwarsa:
            hari_terlambat = (hari_ini - tanggal_kedaluwarsa).days
            return f"⛔ <b>KEDALUWARSA ({hari_terlambat} hari)</b>"

        # Hitung sisa waktu
        sisa = relativedelta(tanggal_kedaluwarsa, hari_ini)

        # Format output dengan warna berdasarkan urgency
        if sisa.years >= 1:
            return f"🟢 <b>{sisa.years} tahun {sisa.months} bulan</b>"
        elif sisa.months >= 6:
            return f"🟡 <b>{sisa.months} bulan {sisa.days} hari</b>"
        elif sisa.months >= 3:
            return f"🟠 <b>{sisa.months} bulan {sisa.days} hari</b>"
        elif sisa.months >= 1:
            return f"🔴 <b>{sisa.months} bulan {sisa.days} hari</b>"
        else:
            return f"🚨 <b>{sisa.days} HARI LAGI!</b>"

    except ValueError:
        return "❓ <b>Format tanggal tidak valid</b>"
    except Exception:
        return "❓ <b>Error perhitungan</b>"


def format_data(data: dict, status: str = "", checked_at: Optional[str] = None) -> str:
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
    tanggal_lulus = _ekstrak_tanggal_lulus_dari_riwayat(riwayat)
    sisa_masa_berlaku = (
        _hitung_sisa_masa_berlaku(tanggal_lulus)
        if tanggal_lulus
        else "❓ <b>Tanggal lulus tidak ditemukan</b>"
    )
    # ================================================================

    title_suffix = f" {status}".strip() if status else ""
    lines = []
    lines.append(f"📋 <b>Hasil Kemajuan EPS{title_suffix}</b>")
    lines.append("━━━━━━━━━━━━━━━━━━━")
    lines.append("📬 <b>Data Utama</b>")
    lines.append(f"👤 Nama : <b>{nama}</b>")
    lines.append(f"🆔 ID Aktif : <code>{aktif_ref}</code>")
    lines.append(f"📮 Pengiriman Terbaru : <code>{t_kirim}</code>")
    lines.append(f"📥 Penerimaan Terbaru : <code>{t_terima}</code>")
    if ref_id_latest and ref_id_latest != "-":
        lines.append(f"🆔 ID Nodongbu Terbaru : <code>{ref_id_latest}</code>")
        lines.append(f"📅 Sisa Masa Berlaku Sertifikat : {sisa_masa_berlaku}")

    # Riwayat roster & mediasi
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
        lines.append(f"ID : <code>{rid}</code>")
        lines.append(f"Tanggal Kirim : {kirim}")
        lines.append(f"Tanggal Terima : {terima}")
        if masa:
            lines.append(f"Masa Berlaku : {masa}")
        lines.append(f"💬 Jumlah Mediasi : <b>{med} kali</b>")

    if pengiriman_list:
        last_no = _esc_text(sorted(pengiriman_list, key=_roster_key)[-1].get("no", "-"))
        lines.append(
            f"\n📊 <b>Total Mediasi (Roster 1–{last_no}):</b> <b>{total_mediasi} kali</b>"
        )

    # Progres (single loop) + sematan link
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

    if checked_at:
        lines.append("\n━━━━━━━━━━━━━━━━━━━")
        lines.append(f"🕒 <i>Dicek pada:</i> <code>{_esc_text(checked_at)}</code>")

    return "\n".join(lines)
