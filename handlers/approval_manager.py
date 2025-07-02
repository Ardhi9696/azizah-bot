# approval_manager.py
import json
import os
from datetime import datetime, timedelta
from utils.constants import APPROVAL_FILE

STATUS_FILE = APPROVAL_FILE
user_status = {}  # Format: {user_id: {"joined": "isoformat", "approved": bool}}


def load_status():
    global user_status
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Konversi string ISO ke datetime
                for uid, info in data.items():
                    info["joined"] = datetime.fromisoformat(info["joined"])
                user_status = {int(k): v for k, v in data.items()}
        except Exception as e:
            print(f"❌ Gagal memuat status approval: {e}")


def save_status():
    try:
        to_save = {
            str(uid): {
                "joined": data["joined"].isoformat(),
                "approved": data["approved"],
            }
            for uid, data in user_status.items()
        }
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(to_save, f, indent=2)
    except Exception as e:
        print(f"❌ Gagal menyimpan status approval: {e}")


def add_new_user(user_id: int):
    if user_id not in user_status:
        user_status[user_id] = {
            "joined": datetime.utcnow(),
            "approved": False,
        }
        save_status()


def approve_user(user_id: int):
    if user_id in user_status:
        user_status[user_id]["approved"] = True
        save_status()


def is_approved(user_id: int) -> bool:
    return user_status.get(user_id, {}).get("approved", False)


def get_unapproved_users(expire_minutes: int = 5):
    now = datetime.utcnow()
    return [
        uid
        for uid, data in user_status.items()
        if not data["approved"]
        and now - data["joined"] > timedelta(minutes=expire_minutes)
    ]


def remove_user(user_id: int):
    if user_id in user_status:
        user_status.pop(user_id)
        save_status()


# Panggil saat modul pertama kali diimpor
load_status()
