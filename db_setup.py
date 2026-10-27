# -*- coding: utf-8 -*-
"""
نظام كاشير قهوة - إعداد قاعدة البيانات
========================================
يبني قاعدة بيانات SQLite كاملة تشمل:
- الوحدات الأساسية: المستخدمين، المنتجات، الفواتير، الشِفتات، الإقفال اليومي
- الوحدات الثانوية: المخزون، الزبائن/الولاء، الطاولات، المصاريف، الموردين،
  سجل النشاطات (Audit Log)، النسخ الاحتياطي
"""

import sqlite3
import os
import sys
import hashlib
import secrets
from datetime import datetime


def get_app_data_dir():
    """
    مجلد ثابت لتخزين بيانات البرنامج (قاعدة البيانات + النسخ الاحتياطية)
    خارج مجلد البرنامج نفسه.

    ليش هاد مهم جداً: لما البرنامج يكون مبني كـ .exe واحد (PyInstaller --onefile)،
    ويندوز بيفك ضغط البرنامج بمجلد مؤقت (Temp) كل مرة يشتغل فيها، وبيمسحه أول
    ما يسكر البرنامج. لو قاعدة البيانات محفوظة جوا هداك المجلد المؤقت (زي ما كانت
    قبل)، كل البيانات (منتجات، مستخدمين، فواتير...) بتنمسح مع كل إعادة تشغيل.

    الحل: نحفظ قاعدة البيانات دايماً بمجلد ثابت خاص بالمستخدم:
      - وندوز: C:\\Users\\<User>\\AppData\\Roaming\\love.jo
      - لينكس/ماك: ~/.local/share/love.jo
    هاد المجلد ما بينمسح أبداً، لا عند إغلاق البرنامج ولا عند تحديثه.
    """
    app_name = "love.jo"
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    path = os.path.join(base, app_name)
    os.makedirs(path, exist_ok=True)
    return path


APP_DATA_DIR = get_app_data_dir()
DB_PATH = os.path.join(APP_DATA_DIR, "coffee_pos.db")

# ---- ترحيل تلقائي لقاعدة بيانات قديمة كانت محفوظة بجانب البرنامج (نسخ قديمة) ----
_OLD_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "coffee_pos.db")
if not os.path.exists(DB_PATH) and os.path.exists(_OLD_DB_PATH) and os.path.abspath(_OLD_DB_PATH) != os.path.abspath(DB_PATH):
    try:
        import shutil
        shutil.copy2(_OLD_DB_PATH, DB_PATH)
    except Exception:
        pass


def generate_salt() -> str:
    """ملح عشوائي فريد (32 خانة hex) - يتولّد مرة واحدة لكل مستخدم/كل تغيير كلمة سر."""
    return secrets.token_hex(16)


def hash_password(password: str, salt: str = None) -> tuple:
    """
    تشفير كلمة السر بـ SHA-256 + salt عشوائي خاص بكل مستخدم (وليس ثابت بالكود).
    لو ما انبعث salt، يتولّد وحدة جديدة (حالة إنشاء مستخدم/تغيير كلمة سر).
    يرجع (hash, salt) عشان تنخزن الاثنين بالداتابيز.
    """
    if salt is None:
        salt = generate_salt()
    h = hashlib.sha256((password + salt).encode("utf-8")).hexdigest()
    return h, salt


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def create_database():
    conn = get_connection()
    cur = conn.cursor()

    # ==========================================================
    # 1) المستخدمون والصلاحيات
    # ==========================================================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        password_salt TEXT NOT NULL DEFAULT '',
        role TEXT NOT NULL CHECK(role IN ('admin', 'cashier')),
        is_active INTEGER NOT NULL DEFAULT 1,
        must_change_password INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT (datetime('now', '+3 hours'))
    )
    """)

    # ---- ترقية قاعدة بيانات قديمة (لو كانت موجودة قبل إضافة هاي الأعمدة) ----
    existing_cols = [r["name"] for r in cur.execute("PRAGMA table_info(users)").fetchall()]
    if "password_salt" not in existing_cols:
        cur.execute("ALTER TABLE users ADD COLUMN password_salt TEXT NOT NULL DEFAULT ''")
    if "must_change_password" not in existing_cols:
        cur.execute("ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0")

    # ==========================================================
    # 2) الفئات والمنتجات والخيارات/الإضافات
    # ==========================================================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        display_order INTEGER NOT NULL DEFAULT 0,
        is_active INTEGER NOT NULL DEFAULT 1
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        base_price REAL NOT NULL DEFAULT 0,
        cost_price REAL NOT NULL DEFAULT 0,
        tax_percent REAL NOT NULL DEFAULT 0,
        barcode TEXT,
        image_path TEXT,
        is_active INTEGER NOT NULL DEFAULT 1,
        display_order INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now', '+3 hours')),
        FOREIGN KEY (category_id) REFERENCES categories(id)
    )
    """)

    # ---- ترقية قاعدة بيانات قديمة: إضافة ضريبة خاصة لكل منتج ----
    existing_product_cols = [r["name"] for r in cur.execute("PRAGMA table_info(products)").fetchall()]
    if existing_product_cols and "tax_percent" not in existing_product_cols:
        cur.execute("ALTER TABLE products ADD COLUMN tax_percent REAL NOT NULL DEFAULT 0")

    # ---- ترقية قاعدة بيانات قديمة: مخزون مرتبط بالمنتج مباشرة (غير نظام الوصفة product_recipe) ----
    # track_quantity = 1 يعني هاد المنتج إله رصيد كمية بيتخصم تلقائياً كل عملية بيع
    # (مثال: باكيتات دخان، شوكولاتة، عصائر) - المنتجات المرتبطة بوصفة (قهوة مثلاً) تقدر
    # تستخدم النظامين مع بعض لو حابين، بس الأغلب بيكتفوا بواحد منهم.
    existing_product_cols = [r["name"] for r in cur.execute("PRAGMA table_info(products)").fetchall()]
    if existing_product_cols and "track_quantity" not in existing_product_cols:
        cur.execute("ALTER TABLE products ADD COLUMN track_quantity INTEGER NOT NULL DEFAULT 0")
    if existing_product_cols and "quantity" not in existing_product_cols:
        cur.execute("ALTER TABLE products ADD COLUMN quantity REAL NOT NULL DEFAULT 0")

    # ---- باركودات إضافية لنفس المنتج ----
    # مثال: كيد شوكولاتة عنده باركود 111 (الأصلي في products.barcode)
    # الزبون جاب كيد فراولة بباركود 222 → نضيف 222 هون بدون ما نخلق منتج جديد
    cur.execute("""
    CREATE TABLE IF NOT EXISTS product_barcodes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        barcode TEXT NOT NULL,
        note TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now', '+3 hours')),
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
    )
    """)
    cur.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS idx_product_barcodes_barcode
        ON product_barcodes(barcode)
    """)

    # مجموعات الخيارات (مثال: الحجم، نوع الحليب)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS option_groups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        is_required INTEGER NOT NULL DEFAULT 0,
        allow_multiple INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
    )
    """)

    # قيم الخيارات (مثال: صغير/وسط/كبير - أو حليب كامل الدسم/لوز)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS option_values (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        option_group_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        extra_price REAL NOT NULL DEFAULT 0,
        FOREIGN KEY (option_group_id) REFERENCES option_groups(id) ON DELETE CASCADE
    )
    """)

    # ==========================================================
    # 3) المخزون (ثانوي)
    # ==========================================================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS inventory_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        unit TEXT NOT NULL DEFAULT 'قطعة',
        current_quantity REAL NOT NULL DEFAULT 0,
        min_quantity_alert REAL NOT NULL DEFAULT 0,
        updated_at TEXT NOT NULL DEFAULT (datetime('now', '+3 hours'))
    )
    """)

    # وصفة المنتج: كم يسحب من كل مادة خام
    cur.execute("""
    CREATE TABLE IF NOT EXISTS product_recipe (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        inventory_item_id INTEGER NOT NULL,
        quantity_used REAL NOT NULL,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
        FOREIGN KEY (inventory_item_id) REFERENCES inventory_items(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS inventory_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        inventory_item_id INTEGER NOT NULL,
        change_amount REAL NOT NULL,
        reason TEXT NOT NULL,
        related_order_id INTEGER,
        user_id INTEGER,
        created_at TEXT NOT NULL DEFAULT (datetime('now', '+3 hours')),
        FOREIGN KEY (inventory_item_id) REFERENCES inventory_items(id)
    )
    """)

    # سجل حركة المخزون المرتبط مباشرة بالمنتج (مختلف عن inventory_transactions
    # اللي هي لمواد الوصفة product_recipe) - كل زيادة/نقصان على products.quantity
    # يتسجل هون عشان نقدر نرجع نتتبع ليش تغيّرت الكمية.
    cur.execute("""
    CREATE TABLE IF NOT EXISTS product_stock_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER,
        change_amount REAL NOT NULL,
        reason TEXT NOT NULL,
        related_order_id INTEGER,
        user_id INTEGER,
        created_at TEXT NOT NULL DEFAULT (datetime('now', '+3 hours')),
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """)

    # ---- ترقية قاعدة بيانات قديمة: كان product_id هون NOT NULL وبدون ON DELETE SET NULL
    # وهاد كان يمنع حذف أي منتج له أي حركة مخزون قديمة. نعيد بناء الجدول عشان نسمح
    # بالحذف الفعلي للمنتج مع الإبقاء على سجل الحركات القديمة (product_id يصير NULL). ----
    pst_sql = cur.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='product_stock_transactions'"
    ).fetchone()
    if pst_sql and "ON DELETE SET NULL" not in pst_sql["sql"]:
        cur.execute("PRAGMA foreign_keys = OFF")
        cur.execute("ALTER TABLE product_stock_transactions RENAME TO product_stock_transactions_old")
        cur.execute("""
        CREATE TABLE product_stock_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            change_amount REAL NOT NULL,
            reason TEXT NOT NULL,
            related_order_id INTEGER,
            user_id INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now', '+3 hours')),
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """)
        old_cols = [r["name"] for r in cur.execute("PRAGMA table_info(product_stock_transactions_old)").fetchall()]
        common_cols = ", ".join(old_cols)
        cur.execute(f"INSERT INTO product_stock_transactions ({common_cols}) "
                    f"SELECT {common_cols} FROM product_stock_transactions_old")
        cur.execute("DROP TABLE product_stock_transactions_old")
        cur.execute("PRAGMA foreign_keys = ON")

    # ==========================================================
    # 4) الموردون والمشتريات (ثانوي)
    # ==========================================================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT,
        notes TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier_id INTEGER,
        inventory_item_id INTEGER NOT NULL,
        quantity REAL NOT NULL,
        total_cost REAL NOT NULL,
        purchase_date TEXT NOT NULL DEFAULT (datetime('now', '+3 hours')),
        user_id INTEGER,
        FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
        FOREIGN KEY (inventory_item_id) REFERENCES inventory_items(id)
    )
    """)

    # ==========================================================
    # 5) الزبائن والولاء (ثانوي)
    # ==========================================================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        phone TEXT UNIQUE,
        loyalty_points INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now', '+3 hours'))
    )
    """)

    # ==========================================================
    # 6) الطاولات (ثانوي)
    # ==========================================================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS tables (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        table_number TEXT NOT NULL UNIQUE,
        status TEXT NOT NULL DEFAULT 'فاضية' CHECK(status IN ('فاضية', 'مشغولة'))
    )
    """)

    # ==========================================================
    # 7) الشِفتات
    # ==========================================================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS shifts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        opening_cash REAL NOT NULL DEFAULT 0,
        closing_cash_expected REAL,
        closing_cash_actual REAL,
        cash_difference REAL,
        started_at TEXT NOT NULL DEFAULT (datetime('now', '+3 hours')),
        ended_at TEXT,
        status TEXT NOT NULL DEFAULT 'مفتوح' CHECK(status IN ('مفتوح', 'مقفول')),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """)

    # ==========================================================
    # 8) الطلبات / الفواتير
    # ==========================================================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_number TEXT NOT NULL UNIQUE,
        shift_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        customer_id INTEGER,
        table_id INTEGER,
        order_type TEXT NOT NULL DEFAULT 'بالمحل' CHECK(order_type IN ('بالمحل', 'دلفري')),
        subtotal REAL NOT NULL DEFAULT 0,
        discount_amount REAL NOT NULL DEFAULT 0,
        tax_amount REAL NOT NULL DEFAULT 0,
        total_amount REAL NOT NULL DEFAULT 0,
        payment_method TEXT NOT NULL DEFAULT 'كاش' CHECK(payment_method IN ('كاش', 'شبكة', 'مختلط')),
        cash_paid REAL NOT NULL DEFAULT 0,
        card_paid REAL NOT NULL DEFAULT 0,
        amount_tendered REAL NOT NULL DEFAULT 0,
        change_due REAL NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'مكتملة' CHECK(status IN ('مكتملة', 'ملغاة', 'مرتجعة')),
        cancelled_by INTEGER,
        cancel_reason TEXT,
        returned_by INTEGER,
        return_reason TEXT,
        returned_at TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now', '+3 hours')),
        FOREIGN KEY (shift_id) REFERENCES shifts(id),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (customer_id) REFERENCES customers(id),
        FOREIGN KEY (table_id) REFERENCES tables(id)
    )
    """)

    # ---- ترقية قاعدة بيانات قديمة (لو كانت موجودة قبل إضافة هاي الأعمدة) ----
    existing_order_cols = [r["name"] for r in cur.execute("PRAGMA table_info(orders)").fetchall()] \
        if cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='orders'").fetchone() else []
    if existing_order_cols:
        if "amount_tendered" not in existing_order_cols:
            cur.execute("ALTER TABLE orders ADD COLUMN amount_tendered REAL NOT NULL DEFAULT 0")
        if "change_due" not in existing_order_cols:
            cur.execute("ALTER TABLE orders ADD COLUMN change_due REAL NOT NULL DEFAULT 0")
        if "returned_by" not in existing_order_cols:
            cur.execute("ALTER TABLE orders ADD COLUMN returned_by INTEGER")
        if "return_reason" not in existing_order_cols:
            cur.execute("ALTER TABLE orders ADD COLUMN return_reason TEXT")
        if "returned_at" not in existing_order_cols:
            cur.execute("ALTER TABLE orders ADD COLUMN returned_at TEXT")

    # ---- ترقية قاعدة بيانات قديمة: تحديث أنواع الطلب (كان فيها "محلي/تيك أواي/ديليفري"،
    # صارت بس "بالمحل/دلفري") - نعيد بناء الجدول عشان الـ CHECK القديم ما يمنع الحفظ ----
    if existing_order_cols:
        old_check_sql = cur.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='orders'"
        ).fetchone()["sql"]
        needs_rebuild = old_check_sql and ("تيك أواي" in old_check_sql or "مرتجعة" not in old_check_sql)
        if needs_rebuild:
            cur.execute("PRAGMA foreign_keys = OFF")
            cur.execute("ALTER TABLE orders RENAME TO orders_old")
            cur.execute("""
            CREATE TABLE orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_number TEXT NOT NULL UNIQUE,
                shift_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                customer_id INTEGER,
                table_id INTEGER,
                order_type TEXT NOT NULL DEFAULT 'بالمحل' CHECK(order_type IN ('بالمحل', 'دلفري')),
                subtotal REAL NOT NULL DEFAULT 0,
                discount_amount REAL NOT NULL DEFAULT 0,
                tax_amount REAL NOT NULL DEFAULT 0,
                total_amount REAL NOT NULL DEFAULT 0,
                payment_method TEXT NOT NULL DEFAULT 'كاش' CHECK(payment_method IN ('كاش', 'شبكة', 'مختلط')),
                cash_paid REAL NOT NULL DEFAULT 0,
                card_paid REAL NOT NULL DEFAULT 0,
                amount_tendered REAL NOT NULL DEFAULT 0,
                change_due REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'مكتملة' CHECK(status IN ('مكتملة', 'ملغاة', 'مرتجعة')),
                cancelled_by INTEGER,
                cancel_reason TEXT,
                returned_by INTEGER,
                return_reason TEXT,
                returned_at TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now', '+3 hours')),
                FOREIGN KEY (shift_id) REFERENCES shifts(id),
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (customer_id) REFERENCES customers(id),
                FOREIGN KEY (table_id) REFERENCES tables(id)
            )
            """)
            select_cols = ", ".join(
                "CASE order_type WHEN 'محلي' THEN 'بالمحل' WHEN 'تيك أواي' THEN 'بالمحل' "
                "WHEN 'ديليفري' THEN 'دلفري' ELSE order_type END"
                if col == "order_type" else col
                for col in existing_order_cols
            )
            common_cols = ", ".join(existing_order_cols)
            cur.execute(f"INSERT INTO orders ({common_cols}) SELECT {select_cols} FROM orders_old")
            cur.execute("DROP TABLE orders_old")
            cur.execute("PRAGMA foreign_keys = ON")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        product_id INTEGER,
        product_name_snapshot TEXT NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 1,
        unit_price REAL NOT NULL,
        options_snapshot TEXT,
        tax_percent REAL NOT NULL DEFAULT 0,
        tax_amount REAL NOT NULL DEFAULT 0,
        line_total REAL NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
    )
    """)

    # ---- ترقية قاعدة بيانات قديمة: كان product_id هون NOT NULL وبدون ON DELETE SET NULL
    # وهاد كان يمنع حذف أي منتج له فاتورة قديمة نهائياً. product_name_snapshot أصلاً
    # موجود بكل سطر فاتورة، فالفاتورة القديمة بتضل تنعرض صح حتى لو انحذف المنتج. ----
    oi_sql = cur.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='order_items'"
    ).fetchone()
    if oi_sql and "ON DELETE SET NULL" not in oi_sql["sql"]:
        cur.execute("PRAGMA foreign_keys = OFF")
        cur.execute("ALTER TABLE order_items RENAME TO order_items_old")
        cur.execute("""
        CREATE TABLE order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER,
            product_name_snapshot TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            unit_price REAL NOT NULL,
            options_snapshot TEXT,
            tax_percent REAL NOT NULL DEFAULT 0,
            tax_amount REAL NOT NULL DEFAULT 0,
            line_total REAL NOT NULL,
            line_discount_type TEXT,
            line_discount_value REAL NOT NULL DEFAULT 0,
            line_discount_amount REAL NOT NULL DEFAULT 0,
            FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
        )
        """)
        old_cols = [r["name"] for r in cur.execute("PRAGMA table_info(order_items_old)").fetchall()]
        new_cols_available = {"id", "order_id", "product_id", "product_name_snapshot", "quantity",
                               "unit_price", "options_snapshot", "tax_percent", "tax_amount", "line_total",
                               "line_discount_type", "line_discount_value", "line_discount_amount"}
        common = [c for c in old_cols if c in new_cols_available]
        common_cols = ", ".join(common)
        cur.execute(f"INSERT INTO order_items ({common_cols}) SELECT {common_cols} FROM order_items_old")
        cur.execute("DROP TABLE order_items_old")
        cur.execute("PRAGMA foreign_keys = ON")

    # ---- ترقية قاعدة بيانات قديمة: إضافة ضريبة لكل سطر فاتورة ----
    existing_item_cols = [r["name"] for r in cur.execute("PRAGMA table_info(order_items)").fetchall()] \
        if cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='order_items'").fetchone() else []
    if existing_item_cols:
        if "tax_percent" not in existing_item_cols:
            cur.execute("ALTER TABLE order_items ADD COLUMN tax_percent REAL NOT NULL DEFAULT 0")
        if "tax_amount" not in existing_item_cols:
            cur.execute("ALTER TABLE order_items ADD COLUMN tax_amount REAL NOT NULL DEFAULT 0")
        # ---- ترقية قاعدة بيانات قديمة: خصم على سطر منفرد بالسلة (مو خصم إجمالي بس) ----
        # discount_type: 'percent' أو 'fixed' - discount_value: القيمة اللي أدخلها المدير
        # discount_amount: القيمة النهائية بالدينار المخصومة من هاد السطر (بعد التحويل لو نسبة)
        if "line_discount_type" not in existing_item_cols:
            cur.execute("ALTER TABLE order_items ADD COLUMN line_discount_type TEXT")
        if "line_discount_value" not in existing_item_cols:
            cur.execute("ALTER TABLE order_items ADD COLUMN line_discount_value REAL NOT NULL DEFAULT 0")
        if "line_discount_amount" not in existing_item_cols:
            cur.execute("ALTER TABLE order_items ADD COLUMN line_discount_amount REAL NOT NULL DEFAULT 0")

    # ---- ترقية جدول shifts: إضافة اسم الكاشير اليدوي ----
    existing_shift_cols = [r[1] for r in conn.execute("PRAGMA table_info(shifts)").fetchall()]
    if "cashier_name" not in existing_shift_cols:
        cur.execute("ALTER TABLE shifts ADD COLUMN cashier_name TEXT NOT NULL DEFAULT ''")

    # ==========================================================
    # 9) المصاريف اليومية (ثانوي)
    # ==========================================================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        shift_id INTEGER,
        description TEXT NOT NULL,
        amount REAL NOT NULL,
        user_id INTEGER,
        created_at TEXT NOT NULL DEFAULT (datetime('now', '+3 hours')),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """)

    # ==========================================================
    # 10) سجل النشاطات Audit Log (ثانوي بس مهم جداً)
    # ==========================================================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action_type TEXT NOT NULL,
        details TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now', '+3 hours')),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """)

    # ==========================================================
    # 11) إعدادات النظام العامة (اسم المحل، الضريبة، إلخ)
    # ==========================================================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    conn.commit()

    # ---- إعدادات افتراضية ----
    default_settings = {
        "store_name": "love.jo",
        "tax_percent": "16",
        "receipt_footer": "شكراً لزيارتكم",
        "printer_port": "",
        "printer_name": "",
        "last_backup": "",
    }
    for k, v in default_settings.items():
        cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

    # ---- مستخدم مدير افتراضي وحيد (لازم يتغير أول ما يشتغل النظام) ----
    # النظام الآن أصبح بمستخدم واحد فقط (أدمن) - ما في كاشيرين منفصلين.
    # must_change_password = 1 يجبر المستخدم يغيّر كلمة السر أول ما يسجّل دخول
    cur.execute("SELECT COUNT(*) as c FROM users")
    if cur.fetchone()["c"] == 0:
        h, salt = hash_password("admin123")
        cur.execute("""
            INSERT INTO users (full_name, username, password_hash, password_salt, role, must_change_password)
            VALUES (?, ?, ?, ?, ?, 1)
        """, ("مدير النظام", "admin", h, salt, "admin"))

    conn.commit()
    conn.close()
    print(f"✅ تم إنشاء قاعدة البيانات بنجاح: {DB_PATH}")


def log_action(user_id, action_type, details=""):
    """تسجيل نشاط بسجل الـ Audit Log."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO audit_log (user_id, action_type, details) VALUES (?, ?, ?)",
        (user_id, action_type, details)
    )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    create_database()
