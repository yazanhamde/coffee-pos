# -*- coding: utf-8 -*-
"""نظام النسخ الاحتياطي التلقائي لقاعدة البيانات."""

import shutil
import os
from utils.time_utils import jordan_now_str, jordan_today_str
from database.db_setup import DB_PATH, APP_DATA_DIR
from database.data_access import set_setting

# مجلد النسخ الاحتياطية جوا مجلد بيانات البرنامج الثابت (نفس مكان قاعدة البيانات)
# مش جوا مجلد البرنامج، عشان ما ينمسح لو البرنامج .exe واحد وبينفك بمجلد مؤقت.
BACKUP_DIR = os.path.join(APP_DATA_DIR, "backups")


def run_backup():
    """ينسخ قاعدة البيانات لمجلد backups باسم فيه التاريخ والوقت."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = jordan_now_str("%Y-%m-%d_%H-%M-%S")
    backup_file = os.path.join(BACKUP_DIR, f"coffee_pos_backup_{timestamp}.db")
    shutil.copy2(DB_PATH, backup_file)
    set_setting("last_backup", timestamp)

    # الاحتفاظ بآخر 60 نسخة فقط عشان ما يمتلئ القرص
    backups = sorted(
        [f for f in os.listdir(BACKUP_DIR) if f.endswith(".db")]
    )
    while len(backups) > 60:
        os.remove(os.path.join(BACKUP_DIR, backups.pop(0)))

    return backup_file


def should_backup_today():
    """يتحقق هل صار Backup اليوم أو لأ."""
    last = get_last_backup_date()
    today = jordan_today_str()
    return last != today


def get_last_backup_date():
    from database.data_access import get_setting
    last = get_setting("last_backup", "")
    if not last:
        return ""
    return last.split("_")[0]
