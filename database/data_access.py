# -*- coding: utf-8 -*-
"""
طبقة الوصول للبيانات (Data Access Layer)
كل التعامل مع قاعدة البيانات يمر من هون، عشان الواجهات ما تحكي SQL مباشرة.
"""

from database.db_setup import get_connection, hash_password, log_action
from utils.time_utils import jordan_timestamp_str, jordan_now_str, jordan_today_str
import uuid


# ==================================================================
# المستخدمون
# ==================================================================
def verify_login(username, password):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM users WHERE username = ? AND is_active = 1",
        (username,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    computed, _ = hash_password(password, row["password_salt"])
    if computed == row["password_hash"]:
        return dict(row)
    return None


def get_all_users():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM users ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_user_by_id(user_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def username_exists(username, exclude_user_id=None):
    conn = get_connection()
    if exclude_user_id:
        row = conn.execute(
            "SELECT id FROM users WHERE username = ? AND id != ?", (username, exclude_user_id)
        ).fetchone()
    else:
        row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return row is not None


def add_user(full_name, username, password, role, created_by=None):
    h, salt = hash_password(password)
    conn = get_connection()
    conn.execute(
        """INSERT INTO users (full_name, username, password_hash, password_salt, role, must_change_password)
           VALUES (?, ?, ?, ?, ?, 1)""",
        (full_name, username, h, salt, role)
    )
    conn.commit()
    conn.close()
    if created_by:
        log_action(created_by, "إضافة مستخدم جديد", f"username={username} role={role}")


def update_user(user_id, full_name, role, updated_by=None):
    conn = get_connection()
    conn.execute("UPDATE users SET full_name = ?, role = ? WHERE id = ?", (full_name, role, user_id))
    conn.commit()
    conn.close()
    if updated_by:
        log_action(updated_by, "تعديل بيانات مستخدم", f"user_id={user_id} full_name={full_name} role={role}")


def set_user_active(user_id, is_active, changed_by=None):
    conn = get_connection()
    conn.execute("UPDATE users SET is_active = ? WHERE id = ?", (is_active, user_id))
    conn.commit()
    conn.close()
    if changed_by:
        log_action(changed_by, "تفعيل/تعطيل مستخدم", f"user_id={user_id} is_active={is_active}")


def change_password(user_id, new_password, force_change_again=False, changed_by=None):
    """تغيير كلمة السر - بيولّد salt جديد كل مرة."""
    h, salt = hash_password(new_password)
    conn = get_connection()
    conn.execute(
        "UPDATE users SET password_hash = ?, password_salt = ?, must_change_password = ? WHERE id = ?",
        (h, salt, 1 if force_change_again else 0, user_id)
    )
    conn.commit()
    conn.close()
    log_action(changed_by or user_id, "تغيير كلمة السر", f"user_id={user_id}")


def admin_reset_password(user_id, new_password, admin_id):
    """المدير بيصفّر كلمة سر مستخدم وبيجبره يغيّرها أول ما يسجل دخول."""
    change_password(user_id, new_password, force_change_again=True, changed_by=admin_id)


# ==================================================================
# الفئات والمنتجات
# ==================================================================
def get_categories(active_only=True):
    conn = get_connection()
    q = "SELECT * FROM categories"
    if active_only:
        q += " WHERE is_active = 1"
    q += " ORDER BY display_order, id"
    rows = conn.execute(q).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_category(name, display_order=0):
    conn = get_connection()
    conn.execute("INSERT INTO categories (name, display_order) VALUES (?, ?)", (name, display_order))
    conn.commit()
    conn.close()


def update_category(category_id, name):
    conn = get_connection()
    conn.execute("UPDATE categories SET name = ? WHERE id = ?", (name, category_id))
    conn.commit()
    conn.close()


def set_category_active(category_id, is_active):
    conn = get_connection()
    conn.execute("UPDATE categories SET is_active = ? WHERE id = ?", (is_active, category_id))
    conn.commit()
    conn.close()


def get_products_by_category(category_id, active_only=True):
    conn = get_connection()
    q = "SELECT * FROM products WHERE category_id = ?"
    if active_only:
        q += " AND is_active = 1"
    q += " ORDER BY display_order, id"
    rows = conn.execute(q, (category_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_product(category_id, name, base_price, cost_price=0, barcode=None, tax_percent=0,
                 track_quantity=0, quantity=0):
    conn = get_connection()
    conn.execute(
        """INSERT INTO products (category_id, name, base_price, cost_price, barcode, tax_percent,
           track_quantity, quantity) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (category_id, name, base_price, cost_price, barcode, tax_percent,
         1 if track_quantity else 0, quantity)
    )
    conn.commit()
    conn.close()


def update_product_price(product_id, new_price, user_id):
    conn = get_connection()
    conn.execute("UPDATE products SET base_price = ? WHERE id = ?", (new_price, product_id))
    conn.commit()
    conn.close()
    log_action(user_id, "تعديل سعر منتج", f"product_id={product_id} new_price={new_price}")


def update_product(product_id, name, base_price, cost_price, category_id, barcode=None, user_id=None,
                    tax_percent=None, track_quantity=None, quantity=None):
    conn = get_connection()
    if tax_percent is None:
        conn.execute(
            "UPDATE products SET name = ?, base_price = ?, cost_price = ?, category_id = ?, barcode = ? WHERE id = ?",
            (name, base_price, cost_price, category_id, barcode, product_id)
        )
    else:
        conn.execute(
            "UPDATE products SET name = ?, base_price = ?, cost_price = ?, category_id = ?, barcode = ?, tax_percent = ? WHERE id = ?",
            (name, base_price, cost_price, category_id, barcode, tax_percent, product_id)
        )
    if track_quantity is not None:
        conn.execute("UPDATE products SET track_quantity = ? WHERE id = ?",
                      (1 if track_quantity else 0, product_id))
    if quantity is not None:
        conn.execute("UPDATE products SET quantity = ? WHERE id = ?", (quantity, product_id))
    conn.commit()
    conn.close()
    if user_id:
        log_action(user_id, "تعديل منتج", f"product_id={product_id} name={name}")


# ==================================================================
# مخزون المنتجات (مباشر - غير نظام وصفة product_recipe)
# ==================================================================
def set_product_quantity(product_id, new_quantity, user_id, reason="تعديل يدوي للكمية"):
    """تصفير/تعديل كمية منتج يدوياً من شاشة إدارة المنتجات - عملية حساسة تُسجَّل بالـ audit_log."""
    conn = get_connection()
    row = conn.execute("SELECT quantity FROM products WHERE id = ?", (product_id,)).fetchone()
    old_qty = row["quantity"] if row else 0
    change = new_quantity - old_qty
    conn.execute("UPDATE products SET quantity = ? WHERE id = ?", (new_quantity, product_id))
    conn.execute("""
        INSERT INTO product_stock_transactions (product_id, change_amount, reason, user_id)
        VALUES (?, ?, ?, ?)
    """, (product_id, change, reason, user_id))
    conn.commit()
    conn.close()
    log_action(user_id, "تعديل كمية منتج", f"product_id={product_id} من {old_qty} إلى {new_quantity}")


def get_inventory_report():
    """تقرير المخزون (كميات) للمدير فقط - كل المنتجات اللي متتبَّعة كمياتها + حالتها اللونية."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT p.*, c.name as category_name
        FROM products p
        JOIN categories c ON p.category_id = c.id
        WHERE p.track_quantity = 1
        ORDER BY p.quantity ASC, p.name
    """).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        if d["quantity"] <= 0:
            d["stock_status"] = "نافذ"
            d["stock_color"] = "red"
        elif d["quantity"] <= 3:
            d["stock_status"] = "قرب النفاذ"
            d["stock_color"] = "yellow"
        else:
            d["stock_status"] = "متوفر"
            d["stock_color"] = "green"
        result.append(d)
    return result



def get_inventory_sales_report(date_from: str, date_to: str):
    """
    تقرير مبيعات المخزون بالفترة المحددة:
    - إجمالي مبيعات كل فئة
    - تفاصيل كل صنف داخل الفئة (كمية مباعة + مبلغ)
    يعتمد على order_items + products + categories + orders (مكتملة فقط).
    date_from / date_to: نصوص بصيغة YYYY-MM-DD
    """
    conn = get_connection()
    rows = conn.execute("""
        SELECT
            c.id   AS category_id,
            c.name AS category_name,
            oi.product_name_snapshot,
            SUM(oi.quantity)   AS total_qty,
            SUM(oi.line_total) AS total_amount
        FROM order_items oi
        JOIN orders o   ON oi.order_id   = o.id
        JOIN products p ON oi.product_id = p.id
        JOIN categories c ON p.category_id = c.id
        WHERE o.created_at BETWEEN ? AND ?
          AND o.status = 'مكتملة'
        GROUP BY c.id, c.name, oi.product_name_snapshot
        ORDER BY c.name, total_amount DESC
    """, (date_from + " 00:00:00", date_to + " 23:59:59")).fetchall()
    conn.close()

    categories = {}
    for r in rows:
        cat = r["category_name"]
        if cat not in categories:
            categories[cat] = {"category_id": r["category_id"],
                                "category_name": cat,
                                "total_qty": 0,
                                "total_amount": 0.0,
                                "items": []}
        categories[cat]["total_qty"]    += r["total_qty"]
        categories[cat]["total_amount"] += r["total_amount"]
        categories[cat]["items"].append({
            "product_name": r["product_name_snapshot"],
            "total_qty":    r["total_qty"],
            "total_amount": round(r["total_amount"], 2),
        })

    sorted_cats = sorted(categories.values(), key=lambda x: x["total_amount"], reverse=True)
    for cat in sorted_cats:
        cat["total_amount"] = round(cat["total_amount"], 2)

    grand_total_qty    = sum(c["total_qty"]    for c in sorted_cats)
    grand_total_amount = round(sum(c["total_amount"] for c in sorted_cats), 2)

    return {
        "date_from": date_from,
        "date_to":   date_to,
        "categories": sorted_cats,
        "grand_total_qty":    grand_total_qty,
        "grand_total_amount": grand_total_amount,
    }

def get_product_stock_status(product):
    """يرجع 'green' / 'yellow' / 'red' لمنتج معيّن حسب رصيده - تُستخدم لتلوين بطاقة المنتج
    بشاشة الكاشير وشاشة إدارة المنتجات."""
    if not product.get("track_quantity"):
        return None
    qty = product.get("quantity", 0) or 0
    if qty <= 0:
        return "red"
    elif qty <= 3:
        return "yellow"
    return "green"


def search_products_by_name(query, active_only=True):
    """بحث سريع بالمنتجات بالاسم (جزئي) - يُستخدم بخانة البحث السريع بشاشة الكاشير."""
    conn = get_connection()
    like = f"%{query.strip()}%"
    q = "SELECT p.*, c.name as category_name FROM products p JOIN categories c ON p.category_id = c.id WHERE p.name LIKE ?"
    params = [like]
    if active_only:
        q += " AND p.is_active = 1"
    q += " ORDER BY p.name LIMIT 30"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def set_product_active(product_id, is_active, user_id=None):
    conn = get_connection()
    conn.execute("UPDATE products SET is_active = ? WHERE id = ?", (is_active, product_id))
    conn.commit()
    conn.close()
    if user_id:
        log_action(user_id, "تفعيل/تعطيل منتج", f"product_id={product_id} is_active={is_active}")


class ProductInStockError(Exception):
    """يُرفع لما نحاول نحذف منتج لسا عنده رصيد كمية بالمخزون (لازم يصير نافذ = 0 أولاً)."""
    def __init__(self, quantity):
        self.quantity = quantity
        super().__init__(f"المنتج لسا فيه رصيد مخزون ({quantity}) - لازم يصير نافذ أولاً قبل الحذف")


def delete_product(product_id, user_id=None):
    """حذف نهائي للمنتج.

    الفواتير القديمة ما بتتأثر: كل سطر فاتورة (order_items) فيه product_name_snapshot
    محفوظ مسبقاً، وربط product_id صار ON DELETE SET NULL، فالفاتورة القديمة بتضل
    تنعرض بشكل طبيعي حتى بعد حذف المنتج نفسه.

    الشرط الوحيد: ما بنسمح بحذف منتج متابَع الكمية (track_quantity=1) إلا إذا كان
    نافذ من المخزون (quantity <= 0). المنتجات غير المتابَعة كمياً تنحذف بدون قيد.
    """
    conn = get_connection()
    row = conn.execute(
        "SELECT track_quantity, quantity FROM products WHERE id = ?", (product_id,)
    ).fetchone()
    if row and row["track_quantity"] and row["quantity"] > 0:
        conn.close()
        raise ProductInStockError(row["quantity"])

    conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()
    if user_id:
        log_action(user_id, "حذف منتج", f"product_id={product_id}")


def get_product_by_barcode(barcode):
    """يرجع قائمة بالمنتجات المرتبطة بهاد الباركود.
    يبحث في products.barcode (الأصلي) وكذلك في product_barcodes (الإضافية).
    """
    conn = get_connection()
    # 1. ابحث في الباركود الأصلي
    rows = conn.execute(
        "SELECT * FROM products WHERE barcode = ? AND is_active = 1", (barcode,)
    ).fetchall()
    found_ids = {r["id"] for r in rows}

    # 2. ابحث في الباركودات الإضافية
    extra = conn.execute("""
        SELECT p.* FROM products p
        JOIN product_barcodes pb ON pb.product_id = p.id
        WHERE pb.barcode = ? AND p.is_active = 1
    """, (barcode,)).fetchall()
    conn.close()

    # ادمج بدون تكرار
    result = list(rows)
    for r in extra:
        if r["id"] not in found_ids:
            result.append(r)
            found_ids.add(r["id"])
    return [dict(r) for r in result]


# ---- إدارة الباركودات الإضافية ----

def get_product_barcodes(product_id):
    """يرجع كل الباركودات الإضافية لمنتج معين."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM product_barcodes WHERE product_id = ? ORDER BY created_at",
        (product_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_product_barcode(product_id, barcode, note=None):
    """يضيف باركود إضافي لمنتج موجود.
    يرجع True عند النجاح، أو رسالة خطأ نصية عند الفشل.
    """
    barcode = barcode.strip()
    if not barcode:
        return "الباركود فاضي"
    conn = get_connection()
    try:
        # تحقق إنه مش مستخدم في products.barcode أو product_barcodes
        existing_main = conn.execute(
            "SELECT id, name FROM products WHERE barcode = ?", (barcode,)
        ).fetchone()
        if existing_main:
            conn.close()
            return f"هاد الباركود مسجّل أصلاً كباركود رئيسي للمنتج: {existing_main['name']}"

        existing_extra = conn.execute("""
            SELECT p.name FROM products p
            JOIN product_barcodes pb ON pb.product_id = p.id
            WHERE pb.barcode = ?
        """, (barcode,)).fetchone()
        if existing_extra:
            conn.close()
            return f"هاد الباركود مضاف مسبقاً كباركود إضافي للمنتج: {existing_extra['name']}"

        conn.execute(
            "INSERT INTO product_barcodes (product_id, barcode, note) VALUES (?, ?, ?)",
            (product_id, barcode, note)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        conn.close()
        return str(e)


def delete_product_barcode(barcode_id):
    """يحذف باركود إضافي بـ id."""
    conn = get_connection()
    conn.execute("DELETE FROM product_barcodes WHERE id = ?", (barcode_id,))
    conn.commit()
    conn.close()


def get_all_products_flat():
    """كل المنتجات (فعالة وغير فعالة) مع اسم الفئة، لعرضها بجدول الإدارة."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT p.*, c.name as category_name
        FROM products p
        JOIN categories c ON p.category_id = c.id
        ORDER BY c.display_order, p.display_order, p.id
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---- مجموعات الخيارات / الإضافات ----
def add_option_group(product_id, name, is_required=0, allow_multiple=0):
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO option_groups (product_id, name, is_required, allow_multiple) VALUES (?, ?, ?, ?)",
        (product_id, name, is_required, allow_multiple)
    )
    conn.commit()
    group_id = cur.lastrowid
    conn.close()
    return group_id


def delete_option_group(group_id):
    conn = get_connection()
    conn.execute("DELETE FROM option_groups WHERE id = ?", (group_id,))
    conn.commit()
    conn.close()


def add_option_value(option_group_id, name, extra_price=0):
    conn = get_connection()
    conn.execute(
        "INSERT INTO option_values (option_group_id, name, extra_price) VALUES (?, ?, ?)",
        (option_group_id, name, extra_price)
    )
    conn.commit()
    conn.close()


def delete_option_value(value_id):
    conn = get_connection()
    conn.execute("DELETE FROM option_values WHERE id = ?", (value_id,))
    conn.commit()
    conn.close()


def get_product_options(product_id):
    """يرجع مجموعات الخيارات مع قيمها لمنتج معين."""
    conn = get_connection()
    groups = conn.execute(
        "SELECT * FROM option_groups WHERE product_id = ?", (product_id,)
    ).fetchall()
    result = []
    for g in groups:
        values = conn.execute(
            "SELECT * FROM option_values WHERE option_group_id = ?", (g["id"],)
        ).fetchall()
        result.append({**dict(g), "values": [dict(v) for v in values]})
    conn.close()
    return result


# ==================================================================
# الشِفتات
# ==================================================================
def open_shift(user_id, opening_cash, cashier_name=""):
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO shifts (user_id, opening_cash, cashier_name) VALUES (?, ?, ?)",
        (user_id, opening_cash, cashier_name.strip())
    )
    conn.commit()
    shift_id = cur.lastrowid
    conn.close()
    log_action(user_id, "فتح شِفت", f"opening_cash={opening_cash} cashier_name={cashier_name}")
    return shift_id


def get_open_shift(user_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM shifts WHERE user_id = ? AND status = 'مفتوح' ORDER BY id DESC LIMIT 1",
        (user_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_resumable_shift_today(user_id):
    """آخر شِفت مقفول لنفس المستخدم - يُعرض عليه إكمال نفس الشِفت بدل ما تبلش شِفت
    جديد، حتى تضل مبيعات الشِفت السابق مرتبطة وما تتصفر عند فتح شِفت جديد."""
    # BUG-04 FIX: كان يستخدم date('now', 'localtime') = توقيت الجهاز، واللي ممكن يختلف
    # عن توقيت الأردن (UTC+3) المستخدم في باقي النظام. الآن نمرر jordan_today_str() مباشرة.
    conn = get_connection()
    row = conn.execute("""
        SELECT * FROM shifts
        WHERE user_id = ? AND status = 'مقفول'
          AND date(started_at) = ?
        ORDER BY id DESC LIMIT 1
    """, (user_id, jordan_today_str())).fetchone()
    conn.close()
    return dict(row) if row else None


def resume_shift(shift_id, user_id):
    """يعيد فتح شِفت كان مقفول (نفس اليوم) بدل إنشاء شِفت جديد."""
    conn = get_connection()
    conn.execute("""
        UPDATE shifts SET status = 'مفتوح', ended_at = NULL,
        closing_cash_expected = NULL, closing_cash_actual = NULL, cash_difference = NULL
        WHERE id = ?
    """, (shift_id,))
    conn.commit()
    conn.close()
    log_action(user_id, "إكمال شِفت", f"shift_id={shift_id}")
    return shift_id


def get_today_sales_for_user(user_id):
    """إجمالي مبيعات وعدد فواتير اليوم لكاشير معيّن (لكل شِفتاته اليوم) - للعرض بشاشة الكاشير/الجرد."""
    conn = get_connection()
    orders = conn.execute("""
        SELECT total_amount FROM orders
        WHERE user_id = ? AND date(created_at) = ? AND status = 'مكتملة'
    """, (user_id, jordan_today_str())).fetchall()
    conn.close()
    return {
        "orders_count": len(orders),
        "total_sales": sum(o["total_amount"] for o in orders),
    }


def close_shift(shift_id, closing_cash_actual, user_id):
    """
    ملاحظة مهمة: الكاش والشبكة منفصلين تماماً هون -
    فرق الكاش (متوقع مقابل فعلي) بيُحسب على الكاش بس (cash_paid)، أما مدفوعات الشبكة
    (card_paid) فبتنعرض/تنسجل بس بدون أي حساب فرق عليها (ما إلها معنى "فرق" أصلاً
    لأنها ما بتنحسب يدوياً بالدرج زي الكاش).
    """
    conn = get_connection()
    shift = conn.execute("SELECT * FROM shifts WHERE id = ?", (shift_id,)).fetchone()

    sales_cash = conn.execute(
        """SELECT COALESCE(SUM(cash_paid), 0) as total FROM orders
           WHERE shift_id = ? AND status = 'مكتملة'""",
        (shift_id,)
    ).fetchone()["total"]

    sales_network = conn.execute(
        """SELECT COALESCE(SUM(card_paid), 0) as total FROM orders
           WHERE shift_id = ? AND status = 'مكتملة'""",
        (shift_id,)
    ).fetchone()["total"]

    expenses_total = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) as total FROM expenses WHERE shift_id = ?",
        (shift_id,)
    ).fetchone()["total"]

    expected = shift["opening_cash"] + sales_cash - expenses_total
    difference = closing_cash_actual - expected

    conn.execute("""
        UPDATE shifts SET closing_cash_expected = ?, closing_cash_actual = ?,
        cash_difference = ?, ended_at = ?, status = 'مقفول'
        WHERE id = ?
    """, (expected, closing_cash_actual, difference, jordan_now_str(), shift_id))
    conn.commit()
    conn.close()
    log_action(user_id, "إقفال شِفت", f"shift_id={shift_id} difference={difference} network_total={sales_network}")
    return {
        "expected": expected, "actual": closing_cash_actual, "difference": difference,
        "network_total": sales_network, "cash_sales": sales_cash, "expenses_total": expenses_total,
    }


def get_shifts_report(date_from, date_to, user_id=None):
    """تقرير الشِفتات - كل شِفت بفترة معيّنة (قابل للفلترة بالتاريخ وبالموظف)."""
    conn = get_connection()
    params = [date_from + " 00:00:00", date_to + " 23:59:59"]
    user_filter = ""
    if user_id:
        user_filter = " AND s.user_id = ?"
        params.append(user_id)
    rows = conn.execute(f"""
        SELECT s.*, CASE WHEN s.cashier_name != '' THEN s.cashier_name ELSE u.full_name END as cashier_name,
            (SELECT COALESCE(SUM(o.total_amount), 0) FROM orders o
                WHERE o.shift_id = s.id AND o.status = 'مكتملة') as total_sales,
            (SELECT COALESCE(SUM(o.cash_paid), 0) FROM orders o
                WHERE o.shift_id = s.id AND o.status = 'مكتملة') as cash_total,
            (SELECT COALESCE(SUM(o.card_paid), 0) FROM orders o
                WHERE o.shift_id = s.id AND o.status = 'مكتملة') as network_total,
            (SELECT COUNT(*) FROM orders o
                WHERE o.shift_id = s.id AND o.status = 'مكتملة') as orders_count
        FROM shifts s
        JOIN users u ON s.user_id = u.id
        WHERE s.started_at BETWEEN ? AND ?{user_filter}
        ORDER BY s.started_at DESC
    """, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_shift_detail(shift_id):
    """
    تفاصيل شِفت واحد: ملخص المبيعات (كاش/شبكة/مختلط) + كل الفواتير.
    يُستخدم لتقرير الشِفت الواحد عند الضغط عليه من قائمة الشِفتات.
    """
    conn = get_connection()

    shift = conn.execute("""
        SELECT s.*, CASE WHEN s.cashier_name != '' THEN s.cashier_name ELSE u.full_name END as cashier_name
        FROM shifts s
        JOIN users u ON s.user_id = u.id
        WHERE s.id = ?
    """, (shift_id,)).fetchone()

    if not shift:
        conn.close()
        return None

    # ملخص الدفع
    summary = conn.execute("""
        SELECT
            COUNT(*) as orders_count,
            COALESCE(SUM(total_amount), 0) as total_sales,
            COALESCE(SUM(cash_paid), 0) as cash_total,
            COALESCE(SUM(card_paid), 0) as network_total,
            COALESCE(SUM(discount_amount), 0) as total_discount,
            COALESCE(SUM(tax_amount), 0) as total_tax
        FROM orders
        WHERE shift_id = ? AND status = 'مكتملة'
    """, (shift_id,)).fetchone()

    # كل فواتير الشِفت (مكتملة + ملغاة + مرتجعة)
    orders = conn.execute("""
        SELECT o.id, o.order_number, o.created_at, o.total_amount,
               o.payment_method, o.cash_paid, o.card_paid, o.discount_amount,
               o.tax_amount, o.status,
               COALESCE(c.name, o.order_number) as customer_label
        FROM orders o
        LEFT JOIN customers c ON o.customer_id = c.id
        WHERE o.shift_id = ?
        ORDER BY o.created_at ASC
    """, (shift_id,)).fetchall()

    conn.close()
    return {
        "shift": dict(shift),
        "summary": dict(summary),
        "orders": [dict(r) for r in orders],
    }


def get_returned_orders_report(date_from, date_to, user_id=None):
    """تقرير الفواتير المسترجعة (مرتجعات) بفترة معيّنة، مع اسم الكاشير الأصلي،
    مين عمل الاسترجاع، وسبب الاسترجاع. قابل للفلترة بالموظف اللي عمل الاسترجاع."""
    conn = get_connection()
    params = [date_from + " 00:00:00", date_to + " 23:59:59"]
    user_filter = ""
    if user_id:
        user_filter = " AND o.returned_by = ?"
        params.append(user_id)
    rows = conn.execute(f"""
        SELECT o.id, o.order_number, o.created_at, o.total_amount, o.payment_method,
               o.order_type, o.return_reason, o.returned_at,
               cashier.full_name as cashier_name,
               returner.full_name as returned_by_name
        FROM orders o
        JOIN users cashier ON o.user_id = cashier.id
        LEFT JOIN users returner ON o.returned_by = returner.id
        WHERE o.status = 'مرتجعة' AND o.returned_at BETWEEN ? AND ?{user_filter}
        ORDER BY o.returned_at DESC
    """, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_profit_loss_report(date_from, date_to, include_expenses=True):
    """
    تقرير ربح/خسارة حقيقي: الفرق بين سعر البيع وسعر التكلفة (cost_price) لكل الكمية
    المباعة بالفترة، مطروح منه المصاريف اليومية (expenses) لو include_expenses=True.
    """
    conn = get_connection()
    rows = conn.execute("""
        SELECT oi.product_name_snapshot, oi.quantity, oi.line_total, oi.line_discount_amount,
               COALESCE(p.cost_price, 0) as cost_price
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.id
        LEFT JOIN products p ON oi.product_id = p.id
        WHERE o.created_at BETWEEN ? AND ? AND o.status = 'مكتملة'
    """, (date_from + " 00:00:00", date_to + " 23:59:59")).fetchall()

    revenue = 0.0
    cost = 0.0
    by_product = {}
    for r in rows:
        line_revenue = r["line_total"]
        line_cost = r["cost_price"] * r["quantity"]
        revenue += line_revenue
        cost += line_cost
        key = r["product_name_snapshot"]
        if key not in by_product:
            by_product[key] = {"product_name": key, "quantity": 0, "revenue": 0.0, "cost": 0.0}
        by_product[key]["quantity"] += r["quantity"]
        by_product[key]["revenue"] += line_revenue
        by_product[key]["cost"] += line_cost

    expenses_total = 0.0
    if include_expenses:
        expenses_total = conn.execute("""
            SELECT COALESCE(SUM(amount), 0) as total FROM expenses
            WHERE created_at BETWEEN ? AND ?
        """, (date_from + " 00:00:00", date_to + " 23:59:59")).fetchone()["total"]

    conn.close()

    gross_profit = revenue - cost
    net_profit = gross_profit - expenses_total

    for p in by_product.values():
        p["profit"] = p["revenue"] - p["cost"]

    return {
        "date_from": date_from, "date_to": date_to,
        "revenue": round(revenue, 2), "cost": round(cost, 2),
        "gross_profit": round(gross_profit, 2),
        "expenses_total": round(expenses_total, 2),
        "net_profit": round(net_profit, 2),
        "by_product": sorted(by_product.values(), key=lambda x: x["profit"], reverse=True),
    }


def get_shift_item_summary(shift_id):
    """تقرير بإجمالي المبيعات لكل صنف خلال شِفت معيّن - يُستخدم بتقرير/طباعة إقفال الشِفت."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT oi.product_name_snapshot, SUM(oi.quantity) as total_qty, SUM(oi.line_total) as total_amount
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.id
        WHERE o.shift_id = ? AND o.status = 'مكتملة'
        GROUP BY oi.product_name_snapshot
        ORDER BY total_amount DESC
    """, (shift_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_shift_summary(shift_id):
    conn = get_connection()
    orders = conn.execute(
        "SELECT * FROM orders WHERE shift_id = ? AND status = 'مكتملة'", (shift_id,)
    ).fetchall()
    total_sales = sum(o["total_amount"] for o in orders)
    conn.close()
    return {
        "orders_count": len(orders),
        "total_sales": total_sales,
        "orders": [dict(o) for o in orders]
    }


# ==================================================================
# الطلبات (الفواتير)
# ==================================================================
def generate_order_number():
    return jordan_timestamp_str() + "-" + str(uuid.uuid4())[:4]


def create_order(shift_id, user_id, items, discount_amount=0, tax_percent=16,
                  payment_method="كاش", cash_paid=0, card_paid=0,
                  order_type="بالمحل", customer_id=None, table_id=None,
                  amount_tendered=None):
    """
    items: list of dicts {product_id, name, quantity, unit_price, options_snapshot, line_total, tax_percent}
    كل صنف عندو نسبة ضريبته الخاصة (item['tax_percent']) - مش نسبة موحدة على كل الفاتورة،
    لأنه كل منتج ممكن يكون إلو ضريبة مختلفة. الضريبة تُحسب على سعر كل سطر (بعد توزيع الخصم
    عليه بالتناسب لو في خصم).
    amount_tendered: المبلغ اللي عطاه الزبون فعلياً (للدفع الكاش) - لو ما انبعث،
                      بيُفترض إنه ساوى المبلغ المطلوب بالضبط (change_due = 0).
    """
    subtotal = sum(i["line_total"] for i in items)
    # نسبة توزيع الخصم على كل سطر بالتناسب مع وزنه من المجموع الفرعي
    discount_ratio = (discount_amount / subtotal) if subtotal > 0 else 0

    tax_amount = 0
    for item in items:
        item_tax_percent = item.get("tax_percent", 0) or 0
        line_after_discount = item["line_total"] * (1 - discount_ratio)
        item_tax = round(line_after_discount * (item_tax_percent / 100), 2)
        item["tax_amount"] = item_tax
        item["tax_percent_snapshot"] = item_tax_percent
        tax_amount += item_tax
    tax_amount = round(tax_amount, 2)

    taxable = subtotal - discount_amount
    total_amount = round(taxable + tax_amount, 2)

    if amount_tendered is None:
        amount_tendered = total_amount
    change_due = round(amount_tendered - total_amount, 2)
    if change_due < 0:
        change_due = 0  # لا يفترض بمبلغ مستلم أقل من المطلوب أن يصل لهون أصلاً

    conn = get_connection()
    order_number = generate_order_number()
    cur = conn.execute("""
        INSERT INTO orders (order_number, shift_id, user_id, customer_id, table_id,
            order_type, subtotal, discount_amount, tax_amount, total_amount,
            payment_method, cash_paid, card_paid, amount_tendered, change_due)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (order_number, shift_id, user_id, customer_id, table_id, order_type,
          subtotal, discount_amount, tax_amount, total_amount,
          payment_method, cash_paid, card_paid, amount_tendered, change_due))
    order_id = cur.lastrowid

    pending_discount_logs = []  # نجمّع رسائل خصم الأصناف ونسجّلها بعد إغلاق الاتصال، حتى ما تعلق
    # قاعدة البيانات (log_action بيفتح اتصال جديد، ولو الاتصال الحالي لسا فاتح على نفس الملف
    # بمعاملة كتابة، بيصير "database is locked" على SQLite)

    for item in items:
        conn.execute("""
            INSERT INTO order_items (order_id, product_id, product_name_snapshot,
                quantity, unit_price, options_snapshot, tax_percent, tax_amount, line_total,
                line_discount_type, line_discount_value, line_discount_amount)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (order_id, item["product_id"], item["name"], item["quantity"],
              item["unit_price"], item.get("options_snapshot", ""),
              item.get("tax_percent_snapshot", 0), item.get("tax_amount", 0), item["line_total"],
              item.get("line_discount_type"), item.get("line_discount_value", 0),
              item.get("line_discount_amount", 0)))

        if item.get("line_discount_amount", 0):
            pending_discount_logs.append(
                f"order_id={order_id} product={item['name']} "
                f"discount_type={item.get('line_discount_type')} "
                f"discount_value={item.get('line_discount_value')} "
                f"discount_amount={item.get('line_discount_amount')}"
            )

        # سحب المخزون تلقائياً حسب الوصفة (لو موجودة)
        recipe = conn.execute(
            "SELECT * FROM product_recipe WHERE product_id = ?", (item["product_id"],)
        ).fetchall()
        for r in recipe:
            used = r["quantity_used"] * item["quantity"]
            conn.execute(
                "UPDATE inventory_items SET current_quantity = current_quantity - ?, "
                "updated_at = ? WHERE id = ?",
                (used, jordan_now_str(), r["inventory_item_id"])
            )
            conn.execute("""
                INSERT INTO inventory_transactions (inventory_item_id, change_amount, reason, related_order_id, user_id)
                VALUES (?, ?, 'بيع', ?, ?)
            """, (r["inventory_item_id"], -used, order_id, user_id))

        # سحب مخزون المنتج نفسه مباشرة (لو هاد المنتج متتبَّعة كميته مباشرة)
        prod_row = conn.execute(
            "SELECT track_quantity FROM products WHERE id = ?", (item["product_id"],)
        ).fetchone()
        if prod_row and prod_row["track_quantity"]:
            conn.execute(
                "UPDATE products SET quantity = quantity - ? WHERE id = ?",
                (item["quantity"], item["product_id"])
            )
            conn.execute("""
                INSERT INTO product_stock_transactions (product_id, change_amount, reason, related_order_id, user_id)
                VALUES (?, ?, 'بيع', ?, ?)
            """, (item["product_id"], -item["quantity"], order_id, user_id))

    conn.commit()
    conn.close()
    for log_msg in pending_discount_logs:
        log_action(user_id, "خصم على صنف بالسلة", log_msg)
    return order_id, order_number, total_amount, change_due


def get_order_with_items(order_id):
    """يرجع الفاتورة كاملة مع أصنافها - تُستخدم لطباعة الإيصال."""
    conn = get_connection()
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not order:
        conn.close()
        return None
    items = conn.execute(
        "SELECT * FROM order_items WHERE order_id = ?", (order_id,)
    ).fetchall()
    cashier = conn.execute(
        "SELECT full_name FROM users WHERE id = ?", (order["user_id"],)
    ).fetchone()
    conn.close()
    result = dict(order)
    result["items"] = [dict(i) for i in items]
    result["cashier_name"] = cashier["full_name"] if cashier else ""
    return result


def get_order_by_number(order_number):
    """يبحث عن فاتورة برقمها (تُستخدم بشاشة استرجاع الفاتورة)."""
    conn = get_connection()
    order = conn.execute("SELECT id FROM orders WHERE order_number = ?", (order_number.strip(),)).fetchone()
    conn.close()
    if not order:
        return None
    return get_order_with_items(order["id"])


def return_order(order_id, user_id, reason=""):
    """
    استرجاع فاتورة كاملة (مرتجع):
    - يغيّر حالة الفاتورة إلى 'مرتجعة' (ما بتنحسب ضمن المبيعات ولا التقارير بعدها).
    - يرجّع المخزون المسحوب منها (لو في وصفة مرتبطة بالمنتجات).
    - يسجّل مين عمل الاسترجاع ومتى وليش، بسجل النشاطات (Audit Log).
    يرجع (success: bool, message: str).
    """
    conn = get_connection()
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not order:
        conn.close()
        return False, "الفاتورة غير موجودة"
    if order["status"] == "مرتجعة":
        conn.close()
        return False, "الفاتورة مسترجعة مسبقاً"
    if order["status"] == "ملغاة":
        conn.close()
        return False, "الفاتورة ملغاة أصلاً، ما ممكن استرجاعها"

    items = conn.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,)).fetchall()
    for item in items:
        recipe = conn.execute(
            "SELECT * FROM product_recipe WHERE product_id = ?", (item["product_id"],)
        ).fetchall()
        for r in recipe:
            used = r["quantity_used"] * item["quantity"]
            conn.execute(
                "UPDATE inventory_items SET current_quantity = current_quantity + ?, "
                "updated_at = ? WHERE id = ?",
                (used, jordan_now_str(), r["inventory_item_id"])
            )
            conn.execute("""
                INSERT INTO inventory_transactions (inventory_item_id, change_amount, reason, related_order_id, user_id)
                VALUES (?, ?, 'استرجاع فاتورة', ?, ?)
            """, (r["inventory_item_id"], used, order_id, user_id))

        prod_row = conn.execute(
            "SELECT track_quantity FROM products WHERE id = ?", (item["product_id"],)
        ).fetchone()
        if prod_row and prod_row["track_quantity"]:
            conn.execute(
                "UPDATE products SET quantity = quantity + ? WHERE id = ?",
                (item["quantity"], item["product_id"])
            )
            conn.execute("""
                INSERT INTO product_stock_transactions (product_id, change_amount, reason, related_order_id, user_id)
                VALUES (?, ?, 'استرجاع فاتورة', ?, ?)
            """, (item["product_id"], item["quantity"], order_id, user_id))

    conn.execute("""
        UPDATE orders SET status = 'مرتجعة', returned_by = ?, return_reason = ?,
        returned_at = ? WHERE id = ?
    """, (user_id, reason, jordan_now_str(), order_id))
    conn.commit()
    conn.close()
    log_action(user_id, "استرجاع فاتورة", f"order_id={order_id} order_number={order['order_number']} reason={reason}")
    return True, f"تم استرجاع الفاتورة رقم {order['order_number']} بنجاح وأُرجع المخزون المرتبط فيها"


def cancel_order(order_id, user_id, reason):
    # BUG-02 FIX: إرجاع المخزون عند إلغاء الفاتورة (مثل return_order تماماً)
    conn = get_connection()
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not order:
        conn.close()
        return
    items = conn.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,)).fetchall()
    for item in items:
        # إرجاع مخزون المواد الخام (الوصفة)
        recipe = conn.execute(
            "SELECT * FROM product_recipe WHERE product_id = ?", (item["product_id"],)
        ).fetchall()
        for r in recipe:
            used = r["quantity_used"] * item["quantity"]
            conn.execute(
                "UPDATE inventory_items SET current_quantity = current_quantity + ?, "
                "updated_at = ? WHERE id = ?",
                (used, jordan_now_str(), r["inventory_item_id"])
            )
            conn.execute("""
                INSERT INTO inventory_transactions (inventory_item_id, change_amount, reason, related_order_id, user_id)
                VALUES (?, ?, 'إلغاء فاتورة', ?, ?)
            """, (r["inventory_item_id"], used, order_id, user_id))

        # إرجاع مخزون المنتج المباشر
        prod_row = conn.execute(
            "SELECT track_quantity FROM products WHERE id = ?", (item["product_id"],)
        ).fetchone()
        if prod_row and prod_row["track_quantity"]:
            conn.execute(
                "UPDATE products SET quantity = quantity + ? WHERE id = ?",
                (item["quantity"], item["product_id"])
            )
            conn.execute("""
                INSERT INTO product_stock_transactions (product_id, change_amount, reason, related_order_id, user_id)
                VALUES (?, ?, 'إلغاء فاتورة', ?, ?)
            """, (item["product_id"], item["quantity"], order_id, user_id))

    conn.execute(
        "UPDATE orders SET status = 'ملغاة', cancelled_by = ?, cancel_reason = ? WHERE id = ?",
        (user_id, reason, order_id)
    )
    conn.commit()
    conn.close()
    log_action(user_id, "إلغاء فاتورة", f"order_id={order_id} reason={reason}")


# ==================================================================
# المخزون
# ==================================================================
def get_low_stock_items():
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM inventory_items WHERE current_quantity <= min_quantity_alert"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_purchase(supplier_id, inventory_item_id, quantity, total_cost, user_id):
    conn = get_connection()
    conn.execute("""
        INSERT INTO purchases (supplier_id, inventory_item_id, quantity, total_cost, user_id)
        VALUES (?, ?, ?, ?, ?)
    """, (supplier_id, inventory_item_id, quantity, total_cost, user_id))
    conn.execute(
        "UPDATE inventory_items SET current_quantity = current_quantity + ? WHERE id = ?",
        (quantity, inventory_item_id)
    )
    conn.execute("""
        INSERT INTO inventory_transactions (inventory_item_id, change_amount, reason, user_id)
        VALUES (?, ?, 'شراء', ?)
    """, (inventory_item_id, quantity, user_id))
    conn.commit()
    conn.close()


# ==================================================================
# المصاريف
# ==================================================================
def add_expense(shift_id, description, amount, user_id):
    conn = get_connection()
    conn.execute(
        "INSERT INTO expenses (shift_id, description, amount, user_id) VALUES (?, ?, ?, ?)",
        (shift_id, description, amount, user_id)
    )
    conn.commit()
    conn.close()
    log_action(user_id, "إضافة مصروف", f"{description} - {amount}")


# ==================================================================
# التقارير
# ==================================================================
def get_recent_orders(limit=30, shift_id=None):
    """آخر الفواتير المكتملة (الأحدث أولاً) - تُستخدم بنافذة استرجاع الفاتورة حتى الكاشير
    يقدر يختار من قائمة بدل ما يكتب/ينسخ رقم الفاتورة يدوياً (رقم طويل وصعب النسخ)."""
    conn = get_connection()
    params = []
    shift_filter = ""
    if shift_id:
        shift_filter = " AND o.shift_id = ?"
        params.append(shift_id)
    params.append(limit)
    rows = conn.execute(f"""
        SELECT o.id, o.order_number, o.created_at, o.total_amount, o.status, u.full_name as cashier_name
        FROM orders o
        JOIN users u ON o.user_id = u.id
        WHERE o.status != 'ملغاة'{shift_filter}
        ORDER BY o.created_at DESC
        LIMIT ?
    """, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_daily_report(date_str):
    """date_str بصيغة YYYY-MM-DD."""
    conn = get_connection()
    # نستخدم date(created_at) = date_str عشان نتجنب أي مشكلة في الـ format أو timezone
    params = [date_str]

    orders = conn.execute("""
        SELECT o.*, u.full_name as cashier_name, c.name as customer_name, c.phone as customer_phone
        FROM orders o
        JOIN users u ON o.user_id = u.id
        LEFT JOIN customers c ON o.customer_id = c.id
        WHERE date(o.created_at) = ? AND o.status = 'مكتملة'
        ORDER BY o.created_at DESC
    """, params).fetchall()

    top_products = conn.execute("""
        SELECT product_name_snapshot, SUM(quantity) as total_qty, SUM(line_total) as total_amount
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.id
        WHERE date(o.created_at) = ? AND o.status = 'مكتملة'
        GROUP BY product_name_snapshot
        ORDER BY total_qty DESC
        LIMIT 10
    """, params).fetchall()

    conn.close()
    return {
        "date": date_str,
        "orders_count": len(orders),
        "total_sales": sum(o["total_amount"] for o in orders),
        "total_tax": sum(o["tax_amount"] for o in orders),
        "total_discount": sum(o["discount_amount"] for o in orders),
        "top_products": [dict(p) for p in top_products],
        "orders": [dict(o) for o in orders],
    }


def get_monthly_report(year, month, day_from=None, day_to=None):
    """تقرير شهري، مع إمكانية تحديد مدى أيام معيّن داخل الشهر (day_from/day_to)
    بدل الشهر كامل. لو مش محددين، بيرجع الشهر كامل من أول يوم لآخر يوم."""
    conn = get_connection()
    import calendar
    last_day = calendar.monthrange(year, month)[1]
    day_start = day_from if day_from else 1
    day_end = day_to if day_to else last_day
    day_start = max(1, min(day_start, last_day))
    day_end = max(1, min(day_end, last_day))
    if day_start > day_end:
        day_start, day_end = day_end, day_start
    month_str = f"{year:04d}-{month:02d}"
    date_start = f"{year:04d}-{month:02d}-{day_start:02d} 00:00:00"
    date_end   = f"{year:04d}-{month:02d}-{day_end:02d} 23:59:59"

    orders = conn.execute("""
        SELECT o.*, u.full_name as cashier_name, c.name as customer_name, c.phone as customer_phone
        FROM orders o
        JOIN users u ON o.user_id = u.id
        LEFT JOIN customers c ON o.customer_id = c.id
        WHERE o.created_at BETWEEN ? AND ? AND o.status = 'مكتملة'
        ORDER BY o.created_at DESC
    """, (date_start, date_end)).fetchall()

    conn.close()
    return {
        "month": month_str,
        "day_from": day_start, "day_to": day_end,
        "orders_count": len(orders),
        "total_sales": sum(o["total_amount"] for o in orders),
        "orders": [dict(o) for o in orders],
    }


# ==================================================================
# الزبائن + فواتير الزبائن
# ==================================================================
def get_or_create_customer(name=None, phone=None):
    """يرجع customer_id: يدور برقم الهاتف أولاً، لو موجود يحدث الاسم (لو انبعث)،
    لو مش موجود ينشئ زبون جديد. لو ما في اسم ولا هاتف، يرجع None (بيع بدون زبون)."""
    name = (name or "").strip()
    phone = (phone or "").strip()
    if not name and not phone:
        return None
    conn = get_connection()
    row = None
    if phone:
        row = conn.execute("SELECT * FROM customers WHERE phone = ?", (phone,)).fetchone()
    if row:
        if name and name != row["name"]:
            conn.execute("UPDATE customers SET name = ? WHERE id = ?", (name, row["id"]))
            conn.commit()
        conn.close()
        return row["id"]
    cur = conn.execute(
        "INSERT INTO customers (name, phone) VALUES (?, ?)",
        (name or None, phone or None)
    )
    conn.commit()
    customer_id = cur.lastrowid
    conn.close()
    return customer_id


def search_customers(query):
    """بحث بالاسم أو رقم الهاتف (جزئي)."""
    conn = get_connection()
    like = f"%{query.strip()}%"
    rows = conn.execute(
        "SELECT * FROM customers WHERE name LIKE ? OR phone LIKE ? ORDER BY name",
        (like, like)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_orders_by_customer(customer_id):
    conn = get_connection()
    rows = conn.execute("""
        SELECT o.*, u.full_name as cashier_name
        FROM orders o JOIN users u ON o.user_id = u.id
        WHERE o.customer_id = ?
        ORDER BY o.created_at DESC
    """, (customer_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_orders_for_shift(shift_id, user_id=None):
    """كل فواتير شِفت معيّن (تستخدم لعرض 'فواتيري اليوم' للكاشير)."""
    conn = get_connection()
    if user_id:
        rows = conn.execute("""
            SELECT o.*, c.name as customer_name, c.phone as customer_phone
            FROM orders o LEFT JOIN customers c ON o.customer_id = c.id
            WHERE o.shift_id = ? AND o.user_id = ?
            ORDER BY o.created_at DESC
        """, (shift_id, user_id)).fetchall()
    else:
        rows = conn.execute("""
            SELECT o.*, c.name as customer_name, c.phone as customer_phone
            FROM orders o LEFT JOIN customers c ON o.customer_id = c.id
            WHERE o.shift_id = ?
            ORDER BY o.created_at DESC
        """, (shift_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_quick_sale_product():
    """يرجع (وينشئ لو أول مرة) منتج مخفي يُستخدم لعمليات البيع اليدوي
    (أرقام تُدخل يدوياً، أو أصناف بدون باركود وبدون تسجيل مسبق بالقائمة)."""
    conn = get_connection()
    cat = conn.execute("SELECT * FROM categories WHERE name = '__quick_sale__'").fetchone()
    if not cat:
        cur = conn.execute(
            "INSERT INTO categories (name, display_order, is_active) VALUES ('__quick_sale__', 999, 0)"
        )
        cat_id = cur.lastrowid
    else:
        cat_id = cat["id"]

    prod = conn.execute("SELECT * FROM products WHERE category_id = ? AND name = '__quick_sale__'",
                         (cat_id,)).fetchone()
    if not prod:
        cur = conn.execute(
            "INSERT INTO products (category_id, name, base_price, is_active) VALUES (?, '__quick_sale__', 0, 0)",
            (cat_id,)
        )
        prod_id = cur.lastrowid
    else:
        prod_id = prod["id"]
    conn.commit()
    conn.close()
    return prod_id


# ==================================================================
# الإعدادات
# ==================================================================
def get_setting(key, default=""):
    conn = get_connection()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key, value):
    conn = get_connection()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()


# ==================================================================
# كل الفواتير (بدون قيود تاريخ أو شِفت)
# ==================================================================
def get_all_orders(date_from=None, date_to=None, status_filter=None):
    """يرجع كل الفواتير من قاعدة البيانات مع إمكانية الفلترة بالتاريخ والحالة."""
    conn = get_connection()
    conditions = []
    params = []
    if date_from:
        conditions.append("date(o.created_at) >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("date(o.created_at) <= ?")
        params.append(date_to)
    if status_filter and status_filter != "الكل":
        conditions.append("o.status = ?")
        params.append(status_filter)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = conn.execute(f"""
        SELECT o.id, o.order_number, o.created_at, o.total_amount, o.status,
               o.payment_method, o.discount_amount, o.tax_amount,
               u.full_name as cashier_name,
               c.name as customer_name
        FROM orders o
        JOIN users u ON o.user_id = u.id
        LEFT JOIN customers c ON o.customer_id = c.id
        {where}
        ORDER BY o.created_at DESC
    """, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def hard_delete_order(order_id, user_id):
    """حذف فاتورة نهائياً من قاعدة البيانات، مع إرجاع كل ما تم سحبه من المخزون
    (المواد الخام حسب الوصفة + كمية المنتج المباع مباشرة لو كان متتبَّعاً)،
    ثم تسجيل العملية بسجل النشاطات."""
    conn = get_connection()
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not order:
        conn.close()
        return False, "الفاتورة غير موجودة"
    order_number = order["order_number"]

    # --- إرجاع مخزون المواد الخام (inventory_items) اللي انسحبت بسبب هاي الفاتورة ---
    # BUG-03 FIX: change_amount محفوظة سالبة وقت البيع (مثلاً -3)، فلإرجاعها نطرحها (- -3 = +3).
    # الكود السابق كان صحيح رياضياً (current - negative = current + positive) لكنه مُربك ويصعب تدقيقه.
    # الآن نستخدم صيغة صريحة: current_quantity - change_amount (حيث change_amount سالبة = إضافة فعلية).
    inv_moves = conn.execute(
        "SELECT * FROM inventory_transactions WHERE related_order_id = ?",
        (order_id,)
    ).fetchall()
    for mv in inv_moves:
        # change_amount سالبة وقت البيع → طرحها = إضافة للمخزون (الإرجاع الصحيح)
        conn.execute(
            "UPDATE inventory_items SET current_quantity = current_quantity - ?, "
            "updated_at = ? WHERE id = ?",
            (mv["change_amount"], jordan_now_str(), mv["inventory_item_id"])
        )

    # --- إرجاع مخزون المنتج نفسه (products.quantity) اللي انسحب بسبب هاي الفاتورة ---
    # BUG-03 FIX: نفس المنطق — change_amount سالبة وقت البيع، فطرحها = إضافة للمخزون.
    prod_moves = conn.execute(
        "SELECT * FROM product_stock_transactions WHERE related_order_id = ?",
        (order_id,)
    ).fetchall()
    for mv in prod_moves:
        conn.execute(
            "UPDATE products SET quantity = quantity - ? WHERE id = ?",
            (mv["change_amount"], mv["product_id"])
        )

    # --- تنظيف حركات المخزون المرتبطة بالفاتورة المحذوفة حتى ما تظل يتيمة بالسجل ---
    conn.execute("DELETE FROM inventory_transactions WHERE related_order_id = ?", (order_id,))
    conn.execute("DELETE FROM product_stock_transactions WHERE related_order_id = ?", (order_id,))

    conn.execute("DELETE FROM order_items WHERE order_id = ?", (order_id,))
    conn.execute("DELETE FROM orders WHERE id = ?", (order_id,))
    conn.commit()
    conn.close()
    log_action(user_id, "حذف فاتورة نهائي",
               f"order_id={order_id} order_number={order_number} "
               f"(تم إرجاع {len(inv_moves)} حركة مخزون خام و{len(prod_moves)} حركة مخزون منتج)")
    return True, f"تم حذف الفاتورة رقم {order_number} نهائياً وإرجاع المخزون المرتبط بها"


def purge_all_transactions(user_id):
    """
    تصفير بيانات التشغيل/التست بالكامل مع الإبقاء على إعدادات النظام.
    المحذوف: فواتير، شِفتات، مصاريف، مشتريات، حركات مخزون، سجل نشاطات.
    """
    conn = get_connection()
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        tables = [
            "order_items",
            "orders",
            "shifts",
            "expenses",
            "purchases",
            "inventory_transactions",
            "product_stock_transactions",
        ]
        for t in tables:
            conn.execute(f"DELETE FROM {t}")
            conn.execute(f"DELETE FROM sqlite_sequence WHERE name='{t}'")
        # مسح audit_log آخر شي
        conn.execute("DELETE FROM audit_log")
        conn.execute("DELETE FROM sqlite_sequence WHERE name='audit_log'")
        conn.execute("PRAGMA foreign_keys = ON")
        conn.commit()
        # سجّل العملية من جديد بعد المسح
        log_action(user_id, "تصفير بيانات التست", "تم مسح جميع الفواتير والشفتات والتقارير")
        # VACUUM لازم يكون خارج أي transaction
        conn.close()
        vac = get_connection()
        vac.execute("VACUUM")
        vac.close()
        return True, "✅ تم تصفير جميع بيانات التست بنجاح"
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
        return False, f"❌ خطأ أثناء التصفير: {e}"
