import os
import json
from datetime import datetime, timezone, timedelta

CACHE_DIR = "data"
CACHE_AUTO_FILE = os.path.join(CACHE_DIR, "eps_cache_auto.json")
CACHE_MANUAL_FILE = os.path.join(CACHE_DIR, "eps_cache_manual.json")


def _ensure_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)


def _now_jakarta_iso() -> str:
    jkt = timezone(timedelta(hours=7))
    return datetime.now(jkt).strftime("%Y-%m-%d %H:%M:%S %z")


def _data_equal(a: dict, b: dict) -> bool:
    try:
        return json.dumps(a, sort_keys=True, ensure_ascii=False) == json.dumps(
            b, sort_keys=True, ensure_ascii=False
        )
    except Exception:
        return a == b


def _load_cache(path: str) -> dict:
    _ensure_dir()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _save_cache(path: str, cache: dict):
    _ensure_dir()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def _get_last_snapshot_for_account(cache: dict, uid: int, account_key: str):
    """
    Struktur:
      { "<uid>": { "<account_key>": [ {snapshot}, ... ] } }
    Kompat lama (list per uid) tetap dibaca sebagai satu stream default.
    """
    ukey = str(uid)
    node = cache.get(ukey)
    if not node:
        return None
    if isinstance(node, list):  # kompat lama
        return node[-1] if node else None
    hist = (node or {}).get(account_key) or []
    return hist[-1] if hist else None


def _append_snapshot_for_account(cache: dict, uid: int, account_key: str, entry: dict):
    ukey = str(uid)
    if ukey not in cache:
        cache[ukey] = {}
    if isinstance(cache[ukey], list):  # kompat lama → append ke list
        cache[ukey].append(entry)
        return
    cache[ukey].setdefault(account_key, []).append(entry)
