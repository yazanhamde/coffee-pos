# -*- coding: utf-8 -*-
"""
فتح درج الكاش (Cash Drawer)
============================
درج الكاش بمعظم المحلات موصول بالطابعة الحرارية (USB/Serial) وبينفتح
بإرسال أمر ESC/POS خاص (kick-out pulse) للطابعة.

هاد الملف فيه دالة واحدة `open_cash_drawer()` منادى عليها من شاشة الكاشير
(بعد كل عملية دفع كاش، أو يدوياً بالضغط F6). حالياً هي "stub" آمنة:
لو ما في طابعة/بورت متوصل، بتسجّل محاولة الفتح بالكونسول وما بتوقّف البرنامج.

لما يتوفر رقم البورت الفعلي (مثلاً COM3 على وندوز، أو /dev/ttyUSB0 على لينكس)
فعّلي الكود الموجود بالأسفل وحطّي رقم البورت الصحيح.
"""

# أمر ESC/POS القياسي لفتح الدرج (Pin 2)، يشتغل مع أغلب الطابعات الحرارية
ESC_POS_OPEN_DRAWER = b"\x1b\x70\x00\x19\xfa"

# غيّري هاد المتغير لرقم البورت الحقيقي متى صار فيه طابعة/درج متوصل فعلياً بـ Serial
DRAWER_PORT = None  # مثال: "COM3" أو "/dev/ttyUSB0"


def open_cash_drawer(printer_port=None, printer_name=None):
    """
    يحاول فتح درج الكاش. الدرج بالعادة موصول بالطابعة نفسها وبينفتح بإرسال
    نفس أمر ESC/POS إلها - فلو محدد اسم طابعة وندوز أو بورت Serial (من
    شاشة الإعدادات)، منستخدمهم بدل DRAWER_PORT الثابت تحت.
    يرجع True إذا نجح الإرسال، False إذا فشل أو ما في طابعة/بورت معرّف
    (بدون ما يرمي استثناء يوقف البرنامج).
    """
    name = printer_name
    port = printer_port or DRAWER_PORT

    if name:
        try:
            from utils.printer import _print_via_windows_spooler
            _print_via_windows_spooler(name, ESC_POS_OPEN_DRAWER)
            return True
        except Exception as e:
            print(f"⚠️ فشل فتح درج الكاش عبر الطابعة '{name}': {e}")

    if port:
        try:
            import serial  # pyserial - أضيفيه لـ requirements.txt عند الربط الفعلي
            with serial.Serial(port, baudrate=9600, timeout=1) as ser:
                ser.write(ESC_POS_OPEN_DRAWER)
            return True
        except Exception as e:
            print(f"⚠️ فشل فتح درج الكاش عبر البورت {port}: {e}")
            return False

    print("💰 [محاكاة] فتح درج الكاش — لسا ما تم ربط طابعة/بورت حقيقي.")
    return False
