import re
from typing import Any, List, Dict, Optional


def normalize_birthday(value: str) -> str:
    """
    Return hanya digit; valid kalau 6 (YYMMDD) atau 8 (YYYYMMDD).
    Jika bukan 6/8 digit, kembalikan string awal (biar ketahuan salah format).
    """
    digits = re.sub(r"\D", "", value or "")
    return digits if len(digits) in (6, 8) else value


def to_int(v: Any) -> int:
    try:
        return int(str(v).strip())
    except Exception:
        return 0


def roster_key(r: Dict) -> int:
    try:
        return int(re.sub(r"\D", "", r.get("no", "") or "0") or 0)
    except Exception:
        return 0


def pick_latest(pengiriman_list: List[Dict]) -> Optional[Dict]:
    if not pengiriman_list:
        return None
    try:
        return max(pengiriman_list, key=roster_key)
    except Exception:
        return pengiriman_list[-1]
