# handlers/eps_core/formatter.py
from html import escape as _esc
import re
from typing import Optional
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


def format_data(data: dict, status: str = "", checked_at: Optional[str] = None) -> str:
    nama = _esc_text(data.get("nama", "-"))
    aktif_ref = _esc_text(data.get("aktif_ref_id") or "-")

    peng = data.get("pengiriman") or {}
    t_kirim = _esc_text(peng.get("tanggal_kirim", "-"))
    t_terima = _esc_text(_fd(peng.get("tanggal_terima", "-")))
    ref_id_latest = _esc_text(peng.get("ref_id") or "-")

    pengiriman_list = data.get("pengiriman_list") or []
    total_mediasi = sum(_to_int(r.get("mediasi", 0)) for r in pengiriman_list)

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
        lines.append(f"🆔 ID Nodongbu (terbaru) : <code>{ref_id_latest}</code>")

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
    riwayat = data.get("riwayat", []) or []

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
