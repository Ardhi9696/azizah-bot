# monitor_stats.py
import os
import time
import psutil


def get_cpu_temp_value():
    paths = [
        "/sys/class/thermal/thermal_zone0/temp",
        "/sys/devices/virtual/thermal/thermal_zone0/temp",
    ]
    for p in paths:
        if os.path.exists(p):
            try:
                t = int(open(p).read()) / 1000
                return float(f"{t:.1f}")
            except Exception:
                pass
    return None


def get_stats():
    """
    Kembalikan: (cpu_percent, ram_obj, disk_obj, uptime_sec, temp_val)
    Kalau ada yang tidak bisa diakses → None.
    """
    # CPU
    try:
        cpu = psutil.cpu_percent()
    except Exception:
        cpu = None

    # RAM
    try:
        ram = psutil.virtual_memory()
    except Exception:
        ram = None

    # Disk
    try:
        disk = psutil.disk_usage("/")
    except Exception:
        disk = None

    # Uptime
    try:
        uptime_sec = time.time() - psutil.boot_time()
    except Exception:
        uptime_sec = None

    temp_val = get_cpu_temp_value()
    return cpu, ram, disk, uptime_sec, temp_val

