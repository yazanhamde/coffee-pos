"""
time_utils.py — توقيت الأردن الثابت (UTC+3)
=============================================
الأردن أُلغي فيه التوقيت الصيفي ابتداءً من عام 2022،
فالفارق ثابت دائماً UTC+3 بدون أي تغيير موسمي.

نستخدم UTC + timedelta بدل datetime.now() عشان نضمن
إن الفواتير والتقارير تظهر التوقيت الصحيح بغض النظر
عن إعدادات الكمبيوتر.

time_offset_minutes: إعداد طارئ بقاعدة البيانات لتصحيح
انحراف بسيط بساعة الجهاز (أقل من ساعة عادةً).
"""

from datetime import datetime, timezone, timedelta
from datetime import date as _date

# الأردن: UTC+3 ثابت
JORDAN_TZ = timezone(timedelta(hours=3), name="Asia/Amman")


def _get_offset_minutes() -> int:
    """يقرأ انحراف الدقائق المحفوظ بقاعدة البيانات (الإعداد time_offset_minutes).
    يرجع 0 لو ما في إعداد أو لو صار خطأ بالقراءة.
    الحد الأقصى المسموح: ±60 دقيقة - أي شي أكبر يُتجاهل للأمان.
    """
    try:
        from database.data_access import get_setting
        val = int(get_setting("time_offset_minutes", "0"))
        # حماية صارمة: لو تجاوز ±60 دقيقة نتجاهله
        if abs(val) > 60:
            return 0
        return val
    except Exception:
        return 0


def jordan_now() -> datetime:
    """الوقت والتاريخ الحالي بتوقيت الأردن (UTC+3) + انحراف الدقائق المحفوظ."""
    offset = _get_offset_minutes()
    base = datetime.now(tz=timezone.utc).astimezone(JORDAN_TZ)
    if offset:
        base = base + timedelta(minutes=offset)
    return base


def jordan_today() -> _date:
    """تاريخ اليوم بتوقيت الأردن."""
    return jordan_now().date()


def jordan_now_str(fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """الوقت الحالي بتوقيت الأردن كنص مُنسَّق."""
    return jordan_now().strftime(fmt)


def jordan_today_str(fmt: str = "%Y-%m-%d") -> str:
    """تاريخ اليوم بتوقيت الأردن كنص."""
    return jordan_today().strftime(fmt)


def jordan_timestamp_str() -> str:
    """timestamp للأسماء والباك أب: YYYYMMDD-HHMMSS"""
    return jordan_now().strftime("%Y%m%d-%H%M%S")
