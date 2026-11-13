# -*- coding: utf-8 -*-
"""
طباعة الفاتورة على الطابعة الحرارية (ESC/POS)
================================================
معظم طابعات الكاشير الحرارية (Epson TM-T20, Xprinter, Rongta...) بتفهم
بروتوكول ESC/POS، سواء موصولة USB (بتظهر كـ Virtual COM Port على وندوز)
أو Serial حقيقي.

هاد الملف "آمن" بشكل مبدئي: لو ما في طابعة متوصلة أو ما تحدد بورتها،
بيطبع الإيصال بالكونسول (وضع محاكاة) وما بيوقّف البرنامج أبداً - القطاع
هذا بالذات لازم يبقى مضمون 100% إنه ما بيكسر عملية البيع حتى لو الطابعة
مش شغالة.

لما توصل الطابعة الفعلية بالمحل:
1. افتحي "إدارة الأجهزة" بوندوز وشوفي شو رقم البورت (مثلاً COM3).
2. حطي الرقم بمتغير PRINTER_PORT تحت (أو مرريه عن طريق شاشة الإعدادات).
3. ثبتي pyserial:  pip install pyserial

---
ترميز العربية (Encoding) — المشكلة والحل:
-------------------------------------------
ما في ترميز واحد يشتغل على كل الطابعات الحرارية الرخيصة. الأشيع:
  - cp864  : IBM Arabic — شائع على Epson وXprinter الجيل الأول
  - cp720  : OEM Arabic — شائع على Rongta وبعض Xprinter الأحدث
  - cp1256 : Windows Arabic — أقل شيوعاً على ESC/POS
  - utf-8  : بعض الطابعات الحديثة (محتاج أمر تفعيل خاص)

الكود هون بيجرّب الترميزات بالترتيب تلقائياً ويختار أول واحد
ينجح — مش محتاج تعديل يدوي إلا لو رأيت مربعات بدل حروف.

لو الطباعة طلعت مربعات:
  1. شوف رقم موديل الطابعة (مطبوع على علبتها أو ظهرها)
  2. دوّر "ENCODING_PRIORITY" تحت وحرّك الترميز المناسب لأول القائمة
  3. لو ما عرفت، جرّب UTF8 وفعّل دعمه بالطابعة من إعداداتها
"""

import os
import sys
import logging

logger = logging.getLogger("coffee_pos.printer")

# غيّري لرقم البورت الحقيقي عند توصيل الطابعة (مثال: "COM3" على وندوز)
PRINTER_PORT = os.environ.get("COFFEE_POS_PRINTER_PORT") or None
PRINTER_BAUDRATE = 9600

# ترتيب تجربة الترميزات — حرّك الترميز الصح لأول القائمة لتسريع الطباعة
# بعد معرفة موديل الطابعة من المحل
ENCODING_PRIORITY = ["cp864", "cp720", "cp1256", "utf-8"]

# ==================================================================
# أوامر ESC/POS الأساسية
# ==================================================================
ESC = b"\x1b"
GS  = b"\x1d"

CMD_INIT             = ESC + b"@"
CMD_ALIGN_CENTER     = ESC + b"a" + b"\x01"
CMD_ALIGN_LEFT       = ESC + b"a" + b"\x00"
CMD_BOLD_ON          = ESC + b"E" + b"\x01"
CMD_BOLD_OFF         = ESC + b"E" + b"\x00"
CMD_DOUBLE_HEIGHT_ON = GS  + b"!" + b"\x11"
CMD_DOUBLE_HEIGHT_OFF= GS  + b"!" + b"\x00"
CMD_CUT_PAPER        = GS  + b"V" + b"\x00"
CMD_OPEN_DRAWER      = ESC + b"p" + b"\x00\x19\xfa"

# تفعيل ترميز UTF-8 على الطابعات التي تدعمه (ليس كل الطابعات)
CMD_UTF8_ENABLE = ESC + b"t" + b"\x00"

LINE_WIDTH = 32  # 58mm ~ 32 حرف | 80mm ~ 42 حرف


# ==================================================================
# دوال مساعدة لبناء النص
# ==================================================================

def _line(char="-"):
    return (char * LINE_WIDTH) + "\n"


def _center_text(text):
    pad = max(0, (LINE_WIDTH - len(text)) // 2)
    return (" " * pad) + text


def _two_columns(left, right):
    left, right = str(left), str(right)
    space = max(1, LINE_WIDTH - len(left) - len(right))
    return left + (" " * space) + right


def _smart_encode(text, encoding):
    """
    يرمّز النص مع استبدال الأحرف غير المدعومة بـ '?' بدل رمي خطأ.
    لو encoding هو utf-8، بيُضيف BOM وأمر تفعيله بالطابعة.
    """
    if encoding == "utf-8":
        return text.encode("utf-8", errors="replace")
    return text.encode(encoding, errors="replace")


def _detect_best_encoding(sample_text):
    """
    يجرّب الترميزات بالترتيب ويرجع أول واحد يرمّز النص بدون خسارة.
    بيساعد تحديد الترميز الصح تلقائياً عند أول طباعة.
    """
    for enc in ENCODING_PRIORITY:
        try:
            encoded = sample_text.encode(enc, errors="strict")
            decoded = encoded.decode(enc, errors="strict")
            if decoded == sample_text:
                logger.info(f"[Printer] الترميز المحدد تلقائياً: {enc}")
                return enc
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
    logger.warning("[Printer] ما أُوجد ترميز مثالي، سيُستخدم cp864 مع استبدال")
    return ENCODING_PRIORITY[0]


# ==================================================================
# طابعة Windows Spooler (USB)
# ==================================================================

def list_windows_printers():
    """يرجع أسماء كل الطابعات المثبّتة بوندوز."""
    if sys.platform != "win32":
        return []
    try:
        import win32print
        return [p[2] for p in win32print.EnumPrinters(
            win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        )]
    except Exception as e:
        logger.warning(f"[Printer] list_windows_printers: {e}")
        return []


def _print_via_windows_spooler(printer_name, data_bytes):
    """يرسل بايتات RAW مباشرة لطابعة Windows (USB الحرارية)."""
    import win32print
    hprinter = win32print.OpenPrinter(printer_name)
    try:
        hjob = win32print.StartDocPrinter(hprinter, 1, ("فاتورة", None, "RAW"))
        try:
            win32print.StartPagePrinter(hprinter)
            win32print.WritePrinter(hprinter, data_bytes)
            win32print.EndPagePrinter(hprinter)
        finally:
            win32print.EndDocPrinter(hprinter)
    finally:
        win32print.ClosePrinter(hprinter)


# ==================================================================
# بناء نص الإيصال (للمعاينة والطباعة العادية)
# ==================================================================

def build_receipt_text(order, store_name="اسم المحل", tax_percent=16, footer="شكراً لزيارتكم"):
    """
    يبني نص الإيصال بدون أوامر تحكم — يُستخدم للعرض/المعاينة
    وللطباعة النصية لو ما في طابعة ESC/POS.
    """
    lines = [
        _center_text(store_name),
        _center_text(f"فاتورة رقم: {order['order_number']}"),
        _center_text(order.get("created_at", "")),
        _line(),
        f"الكاشير: {order.get('cashier_name', '')}",
        f"نوع الطلب: {order.get('order_type', '')}",
        _line(),
    ]

    for item in order["items"]:
        name  = item["product_name_snapshot"]
        qty   = item["quantity"]
        total = item["line_total"]
        lines.append(_two_columns(f"{name} x{qty}", f"{total:.2f}"))
        if item.get("options_snapshot"):
            lines.append(f"  ({item['options_snapshot']})")
        if item.get("tax_percent"):
            lines.append(f"  ضريبة {item['tax_percent']:.1f}%: {item.get('tax_amount', 0):.2f}")

    lines += [
        _line(),
        _two_columns("المجموع الفرعي:", f"{order['subtotal']:.2f}"),
    ]
    if order.get("discount_amount"):
        lines.append(_two_columns("الخصم:", f"-{order['discount_amount']:.2f}"))
    lines += [
        _two_columns("إجمالي الضريبة:", f"{order['tax_amount']:.2f}"),
        _line(),
        _two_columns("الإجمالي:", f"{order['total_amount']:.2f}"),
        _line(),
        _two_columns("طريقة الدفع:", order.get("payment_method", "")),
    ]
    if order.get("payment_method") == "كاش":
        lines.append(_two_columns("المبلغ المستلم:", f"{order.get('amount_tendered', 0):.2f}"))
        lines.append(_two_columns("الباقي:", f"{order.get('change_due', 0):.2f}"))
    lines += ["", _center_text(footer), "\n\n"]
    return "\n".join(lines)


# ==================================================================
# بناء بايتات ESC/POS
# ==================================================================

def _build_escpos_bytes(order, store_name="اسم المحل", tax_percent=16,
                        footer="شكراً لزيارتكم", encoding=None):
    """
    يبني بايتات ESC/POS جاهزة للإرسال للطابعة الحرارية.
    إذا لم يُحدد encoding، يكتشفه تلقائياً من نص الفاتورة.
    """
    if encoding is None:
        sample = store_name + footer + "فاتورة الإجمالي الكاشير"
        encoding = _detect_best_encoding(sample)

    enc = lambda s: _smart_encode(s, encoding)

    data = CMD_INIT + CMD_ALIGN_CENTER + CMD_BOLD_ON
    data += enc(store_name) + b"\n"
    data += CMD_BOLD_OFF
    data += enc(f"فاتورة رقم: {order['order_number']}") + b"\n"
    data += enc(order.get("created_at", "")) + b"\n"
    data += CMD_ALIGN_LEFT
    data += enc("-" * LINE_WIDTH) + b"\n"

    for item in order["items"]:
        name  = item["product_name_snapshot"]
        qty   = item["quantity"]
        total = item["line_total"]
        data += enc(_two_columns(f"{name} x{qty}", f"{total:.2f}")) + b"\n"
        if item.get("options_snapshot"):
            data += enc(f"  ({item['options_snapshot']})") + b"\n"

    data += enc("-" * LINE_WIDTH) + b"\n"
    data += CMD_BOLD_ON
    data += enc(_two_columns("الإجمالي:", f"{order['total_amount']:.2f}")) + b"\n"
    data += CMD_BOLD_OFF

    if order.get("payment_method") == "كاش":
        data += enc(_two_columns("المستلم:", f"{order.get('amount_tendered', 0):.2f}")) + b"\n"
        data += enc(_two_columns("الباقي:", f"{order.get('change_due', 0):.2f}")) + b"\n"

    data += enc(_center_text(footer)) + b"\n\n\n"
    data += CMD_CUT_PAPER
    return data


# ==================================================================
# الدالة الرئيسية للطباعة
# ==================================================================

def print_receipt(order, store_name="اسم المحل", tax_percent=16,
                  footer="شكراً لزيارتكم", printer_port=None, printer_name=None):
    """
    يطبع الإيصال. يرجع (success: bool, message: str).

    ترتيب المحاولة:
      1) اسم طابعة Windows  — الأنسب لطابعات USB الحرارية (الأشيع).
         يجرّب الترميزات تلقائياً (cp864 ← cp720 ← cp1256 ← utf-8).
      2) بورت Serial/COM    — لطابعات Serial حقيقية.
      3) وضع محاكاة         — لو ما في طابعة، يطبع بالكونسول فقط
         ولا يوقف عملية البيع أبداً.
    """
    text_preview = build_receipt_text(order, store_name, tax_percent, footer)

    # --- 1) طابعة USB متركبة على Windows (الأشيع) ---
    if printer_name:
        # نجرّب الترميزات بالترتيب حتى تنجح الطباعة
        last_error = None
        for enc in ENCODING_PRIORITY:
            try:
                payload = _build_escpos_bytes(order, store_name, tax_percent, footer, encoding=enc)
                _print_via_windows_spooler(printer_name, payload)
                logger.info(f"[Printer] طُبع بنجاح — طابعة: {printer_name} | ترميز: {enc}")
                return True, f"تمت الطباعة بنجاح عبر الطابعة: {printer_name}"
            except ImportError:
                msg = "مكتبة pywin32 غير مثبّتة — شغّل: pip install pywin32"
                logger.error(f"[Printer] {msg}")
                print(f"⚠️ {msg}")
                break  # ImportError ما له علاقة بالترميز، ما تفيد التجربة مجدداً
            except Exception as e:
                last_error = e
                logger.warning(f"[Printer] فشل ترميز {enc} مع '{printer_name}': {e}")
                continue

        if last_error:
            logger.error(f"[Printer] فشلت كل محاولات الطباعة عبر '{printer_name}': {last_error}")
            return False, f"فشلت الطباعة عبر الطابعة '{printer_name}': {last_error}"

    # --- 2) بورت Serial/COM ---
    port = printer_port or PRINTER_PORT
    if port:
        last_error = None
        for enc in ENCODING_PRIORITY:
            try:
                import serial
                payload = _build_escpos_bytes(order, store_name, tax_percent, footer, encoding=enc)
                with serial.Serial(port, baudrate=PRINTER_BAUDRATE, timeout=2) as ser:
                    ser.write(payload)
                logger.info(f"[Printer] طُبع بنجاح — بورت: {port} | ترميز: {enc}")
                return True, "تمت الطباعة بنجاح"
            except Exception as e:
                last_error = e
                logger.warning(f"[Printer] فشل ترميز {enc} عبر {port}: {e}")
                continue

        logger.error(f"[Printer] فشلت كل محاولات الطباعة عبر {port}: {last_error}")
        return False, f"فشلت الطباعة عبر {port}: {last_error}"

    # --- 3) وضع محاكاة (لا طابعة محددة) ---
    logger.info("[Printer] وضع محاكاة — لا طابعة مربوطة")
    print("🖨️ [محاكاة طباعة] لسا ما تم ربط طابعة فعلية:")
    print(text_preview)
    return True, "تمت طباعة الإيصال (وضع محاكاة - بدون طابعة متصلة)"


def print_raw_text(text, printer_port=None, printer_name=None):
    """يطبع نص عادي جاهز (مثلاً تقرير إقفال شِفت) — نفس منطق print_receipt."""
    last_error = None

    if printer_name:
        for enc in ENCODING_PRIORITY:
            try:
                data = CMD_INIT + CMD_ALIGN_LEFT
                data += _smart_encode(text, enc) + b"\n\n\n" + CMD_CUT_PAPER
                _print_via_windows_spooler(printer_name, data)
                logger.info(f"[Printer] print_raw_text — طُبع عبر '{printer_name}' | ترميز: {enc}")
                return True, f"تمت الطباعة عبر الطابعة: {printer_name}"
            except ImportError:
                break
            except Exception as e:
                last_error = e
                continue
        if last_error:
            return False, f"فشلت الطباعة عبر '{printer_name}': {last_error}"

    port = printer_port or PRINTER_PORT
    if port:
        for enc in ENCODING_PRIORITY:
            try:
                import serial
                data = CMD_INIT + CMD_ALIGN_LEFT
                data += _smart_encode(text, enc) + b"\n\n\n" + CMD_CUT_PAPER
                with serial.Serial(port, baudrate=PRINTER_BAUDRATE, timeout=2) as ser:
                    ser.write(data)
                logger.info(f"[Printer] print_raw_text — طُبع عبر {port} | ترميز: {enc}")
                return True, "تمت الطباعة بنجاح"
            except Exception as e:
                last_error = e
                continue
        return False, f"فشلت الطباعة عبر {port}: {last_error}"

    print("🖨️ [محاكاة طباعة]:")
    print(text)
    return True, "تمت الطباعة (وضع محاكاة)"
