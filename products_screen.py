# -*- coding: utf-8 -*-
"""شاشة إدارة المنتجات، الفئات، والخيارات/الإضافات. (صلاحية مدير فقط)"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                              QTableWidget, QTableWidgetItem, QMessageBox, QFrame,
                              QLineEdit, QComboBox, QHeaderView,
                              QDialog, QFormLayout, QCheckBox, QListWidget,
                              QListWidgetItem, QInputDialog)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

from ui.widgets import SmartDoubleSpinBox, get_double_input

from database.data_access import (
    get_categories, add_category, update_category, set_category_active,
    get_all_products_flat, add_product, update_product, set_product_active, delete_product, ProductInStockError,
    get_product_options, add_option_group, delete_option_group,
    add_option_value, delete_option_value, get_product_by_barcode,
    set_product_quantity, get_product_stock_status,
    get_product_barcodes, add_product_barcode, delete_product_barcode,
)

# ألوان تنبيه المخزون - 🟢 أكثر من 3 | 🟡 3 أو أقل | 🔴 صفر
STOCK_COLORS = {
    "green": QColor("#d4edda"),
    "yellow": QColor("#fff3cd"),
    "red": QColor("#f8d7da"),
}


class ProductsManagementScreen(QWidget):
    def __init__(self, current_user, on_back):
        super().__init__()
        self.current_user = current_user
        self.on_back = on_back
        self.setLayoutDirection(Qt.RightToLeft)
        self.init_ui()
        self.refresh_all()

    # ---------------------------------------------------------
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(14)

        header = QHBoxLayout()
        title = QLabel("🛠 إدارة المنتجات والفئات")
        title.setObjectName("titleLabel")
        header.addWidget(title)
        header.addStretch()
        back_btn = QPushButton("رجوع لشاشة الكاشير")
        back_btn.clicked.connect(self.on_back)
        header.addWidget(back_btn)
        main_layout.addLayout(header)

        body = QHBoxLayout()

        # ===== عمود الفئات =====
        cat_frame = QFrame()
        cat_frame.setObjectName("card")
        cat_frame.setFixedWidth(300)
        cat_layout = QVBoxLayout(cat_frame)
        cat_layout.setContentsMargins(14, 14, 14, 14)
        cat_layout.addWidget(QLabel("📂 الفئات"))

        self.categories_list = QListWidget()
        self.categories_list.currentItemChanged.connect(self.on_category_selected)
        cat_layout.addWidget(self.categories_list)

        add_cat_row = QHBoxLayout()
        self.new_cat_input = QLineEdit()
        self.new_cat_input.setPlaceholderText("اسم فئة جديدة")
        add_cat_btn = QPushButton("إضافة")
        add_cat_btn.clicked.connect(self.add_new_category)
        add_cat_row.addWidget(self.new_cat_input)
        add_cat_row.addWidget(add_cat_btn)
        cat_layout.addLayout(add_cat_row)

        cat_actions_row = QHBoxLayout()
        rename_cat_btn = QPushButton("إعادة تسمية")
        rename_cat_btn.clicked.connect(self.rename_category)
        toggle_cat_btn = QPushButton("تعطيل/تفعيل")
        toggle_cat_btn.clicked.connect(self.toggle_category)
        cat_actions_row.addWidget(rename_cat_btn)
        cat_actions_row.addWidget(toggle_cat_btn)
        cat_layout.addLayout(cat_actions_row)

        body.addWidget(cat_frame)

        # ===== عمود المنتجات =====
        prod_frame = QFrame()
        prod_frame.setObjectName("card")
        prod_layout = QVBoxLayout(prod_frame)
        prod_layout.setContentsMargins(14, 14, 14, 14)
        prod_layout.addWidget(QLabel("☕ المنتجات"))

        self.products_table = QTableWidget(0, 10)
        self.products_table.setHorizontalHeaderLabels(
            ["الفئة", "اسم المنتج", "الباركود", "سعر البيع", "التكلفة", "ضريبة %",
             "فعّال؟", "خيارات", "الكمية", "حالة المخزون"]
        )
        self.products_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.products_table.verticalHeader().setVisible(False)
        self.products_table.setAlternatingRowColors(True)
        self.products_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.products_table.setSelectionBehavior(QTableWidget.SelectRows)
        prod_layout.addWidget(self.products_table)

        # نموذج إضافة/تعديل منتج
        form_row = QHBoxLayout()
        self.category_combo = QComboBox()
        self.product_name_input = QLineEdit()
        self.product_name_input.setPlaceholderText("اسم المنتج")
        self.barcode_input = QLineEdit()
        self.barcode_input.setPlaceholderText("امسح أو اكتب الباركود (اختياري)")
        self.price_input = SmartDoubleSpinBox()
        self.price_input.setRange(0, 1000)
        self.price_input.setDecimals(2)
        self.price_input.setPrefix("سعر: ")
        self.cost_input = SmartDoubleSpinBox()
        self.cost_input.setRange(0, 1000)
        self.cost_input.setDecimals(2)
        self.cost_input.setPrefix("تكلفة: ")
        self.tax_input = SmartDoubleSpinBox()
        self.tax_input.setRange(0, 100)
        self.tax_input.setDecimals(2)
        self.tax_input.setPrefix("ضريبة %: ")

        form_row.addWidget(self.category_combo)
        form_row.addWidget(self.product_name_input)
        form_row.addWidget(self.barcode_input)
        form_row.addWidget(self.price_input)
        form_row.addWidget(self.cost_input)
        form_row.addWidget(self.tax_input)
        prod_layout.addLayout(form_row)

        # ===== صف مخزون المنتج (اختياري - للمنتجات اللي بتُباع بالحبة زي دخان/شوكولاتة/عصائر) =====
        stock_row = QHBoxLayout()
        self.track_qty_checkbox = QCheckBox("تتبّع كمية هالمنتج (مخزون)")
        self.qty_input = SmartDoubleSpinBox()
        self.qty_input.setRange(0, 100000)
        self.qty_input.setDecimals(0)
        self.qty_input.setPrefix("الكمية: ")
        self.qty_input.setEnabled(False)
        self.track_qty_checkbox.toggled.connect(self.qty_input.setEnabled)
        stock_row.addWidget(self.track_qty_checkbox)
        stock_row.addWidget(self.qty_input)
        stock_row.addStretch()
        prod_layout.addLayout(stock_row)

        btn_row = QHBoxLayout()
        add_prod_btn = QPushButton("➕ إضافة منتج جديد")
        add_prod_btn.setObjectName("successBtn")
        add_prod_btn.clicked.connect(self.add_new_product)
        edit_prod_btn = QPushButton("✏️ تعديل المنتج المحدد")
        edit_prod_btn.clicked.connect(self.edit_selected_product)
        toggle_prod_btn = QPushButton("تعطيل/تفعيل")
        toggle_prod_btn.clicked.connect(self.toggle_selected_product)
        delete_prod_btn = QPushButton("🗑 حذف نهائي")
        delete_prod_btn.setObjectName("dangerBtn")
        delete_prod_btn.clicked.connect(self.delete_selected_product)
        options_btn = QPushButton("⚙️ خيارات/إضافات المنتج")
        options_btn.clicked.connect(self.manage_options_for_selected)
        barcodes_btn = QPushButton("🔖 باركودات إضافية")
        barcodes_btn.clicked.connect(self.manage_extra_barcodes)
        qty_btn = QPushButton("📦 تعديل كمية المخزون")
        qty_btn.clicked.connect(self.adjust_selected_product_quantity)

        btn_row.addWidget(add_prod_btn)
        btn_row.addWidget(edit_prod_btn)
        btn_row.addWidget(toggle_prod_btn)
        btn_row.addWidget(delete_prod_btn)
        btn_row.addWidget(options_btn)
        btn_row.addWidget(barcodes_btn)
        btn_row.addWidget(qty_btn)
        prod_layout.addLayout(btn_row)

        body.addWidget(prod_frame, stretch=1)
        main_layout.addLayout(body)

    # ---------------------------------------------------------
    def refresh_all(self):
        self.refresh_categories()
        self.refresh_products_table()

    def refresh_categories(self):
        self.categories_list.clear()
        self.category_combo.clear()
        cats = get_categories(active_only=False)
        self.all_categories = cats
        for c in cats:
            label = c["name"] + ("" if c["is_active"] else "  (معطّلة)")
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, c["id"])
            self.categories_list.addItem(item)
            if c["is_active"]:
                self.category_combo.addItem(c["name"], c["id"])

    def refresh_products_table(self):
        self.all_products = get_all_products_flat()
        self._apply_category_filter()

    def _apply_category_filter(self):
        """يفلتر الجدول حسب الفئة المختارة في القائمة. لو ما في اختيار يعرض الكل."""
        selected_item = self.categories_list.currentItem()
        if selected_item:
            selected_cat_id = selected_item.data(Qt.UserRole)
            products = [p for p in self.all_products if p["category_id"] == selected_cat_id]
        else:
            products = self.all_products

        # لازم نخزن اللستة المعروضة فعلياً بالجدول، لأنه صف الجدول (row)
        # بيمثل ترتيبها هي مش ترتيب self.all_products الكاملة (لو في فلترة).
        self.displayed_products = products

        self.products_table.setRowCount(len(products))
        for i, p in enumerate(products):
            self.products_table.setItem(i, 0, QTableWidgetItem(p["category_name"]))
            self.products_table.setItem(i, 1, QTableWidgetItem(p["name"]))
            self.products_table.setItem(i, 2, QTableWidgetItem(p["barcode"] or "—"))
            self.products_table.setItem(i, 3, QTableWidgetItem(f"{p['base_price']:.2f}"))
            self.products_table.setItem(i, 4, QTableWidgetItem(f"{p['cost_price']:.2f}"))
            self.products_table.setItem(i, 5, QTableWidgetItem(f"{p.get('tax_percent', 0):.2f}"))
            self.products_table.setItem(i, 6, QTableWidgetItem("نعم" if p["is_active"] else "لا"))
            opts = get_product_options(p["id"])
            self.products_table.setItem(i, 7, QTableWidgetItem(str(len(opts)) + " مجموعة"))

            if p.get("track_quantity"):
                qty_item = QTableWidgetItem(f"{p['quantity']:.0f}")
                status = get_product_stock_status(p)
                status_text = {"green": "🟢 متوفر", "yellow": "🟡 قرب النفاذ", "red": "🔴 نافذ"}.get(status, "-")
                status_item = QTableWidgetItem(status_text)
                color = STOCK_COLORS.get(status)
                if color:
                    qty_item.setBackground(color)
                    status_item.setBackground(color)
            else:
                qty_item = QTableWidgetItem("—")
                status_item = QTableWidgetItem("غير متتبَّع")
            self.products_table.setItem(i, 8, qty_item)
            self.products_table.setItem(i, 9, status_item)

    # ---------------------------------------------------------
    # الفئات
    def add_new_category(self):
        name = self.new_cat_input.text().strip()
        if not name:
            return
        add_category(name)
        self.new_cat_input.clear()
        self.refresh_categories()

    def on_category_selected(self, current, previous):
        """لما المستخدم يضغط على فئة في القائمة اليسرى، يفلتر الجدول ليعرض منتجاتها فقط."""
        self._apply_category_filter()

    def _selected_category_id(self):
        item = self.categories_list.currentItem()
        if not item:
            return None
        return item.data(Qt.UserRole)

    def rename_category(self):
        cat_id = self._selected_category_id()
        if not cat_id:
            QMessageBox.warning(self, "تنبيه", "اختر فئة أولاً")
            return
        new_name, ok = QInputDialog.getText(self, "إعادة تسمية", "الاسم الجديد:")
        if ok and new_name.strip():
            update_category(cat_id, new_name.strip())
            self.refresh_categories()

    def toggle_category(self):
        cat_id = self._selected_category_id()
        if not cat_id:
            QMessageBox.warning(self, "تنبيه", "اختر فئة أولاً")
            return
        cat = next(c for c in self.all_categories if c["id"] == cat_id)
        set_category_active(cat_id, 0 if cat["is_active"] else 1)
        self.refresh_categories()

    # ---------------------------------------------------------
    # المنتجات
    def _selected_product(self):
        row = self.products_table.currentRow()
        if row < 0:
            return None
        products = getattr(self, "displayed_products", self.all_products)
        if row >= len(products):
            return None
        return products[row]

    def add_new_product(self):
        name = self.product_name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "تنبيه", "اكتب اسم المنتج")
            return
        if self.category_combo.count() == 0:
            QMessageBox.warning(self, "تنبيه", "لازم تضيف فئة أولاً")
            return
        barcode = self.barcode_input.text().strip() or None
        if barcode:
            existing = get_product_by_barcode(barcode)
            if existing:
                names = "، ".join(p["name"] for p in existing)
                confirm = QMessageBox.question(
                    self, "باركود مشترك",
                    f"هاد الباركود مستخدم مسبقاً مع:\n{names}\n\n"
                    "هل تريد ربط هاد المنتج بنفس الباركود؟\n"
                    "(مفيد لو المنتجات بنفس السعر وبنفس الباركود — كالدخان بنكهات مختلفة)"
                )
                if confirm != QMessageBox.Yes:
                    return
        category_id = self.category_combo.currentData()
        add_product(category_id, name, self.price_input.value(), self.cost_input.value(), barcode,
                    self.tax_input.value(),
                    track_quantity=self.track_qty_checkbox.isChecked(),
                    quantity=self.qty_input.value())
        self.product_name_input.clear()
        self.barcode_input.clear()
        self.price_input.setValue(0)
        self.cost_input.setValue(0)
        self.tax_input.setValue(0)
        self.track_qty_checkbox.setChecked(False)
        self.qty_input.setValue(0)
        self.refresh_products_table()
        QMessageBox.information(self, "تم", f"تمت إضافة \"{name}\" بنجاح")

    def edit_selected_product(self):
        product = self._selected_product()
        if not product:
            QMessageBox.warning(self, "تنبيه", "اختر منتج من الجدول أولاً")
            return
        name = self.product_name_input.text().strip() or product["name"]
        price = self.price_input.value() or product["base_price"]
        cost = self.cost_input.value()
        tax_percent = self.tax_input.value()
        barcode = self.barcode_input.text().strip() or product["barcode"]
        category_id = self.category_combo.currentData() or product["category_id"]
        update_product(product["id"], name, price, cost, category_id, barcode, self.current_user["id"],
                       tax_percent=tax_percent)
        self.refresh_products_table()
        QMessageBox.information(self, "تم", "تم تعديل المنتج بنجاح")

    def toggle_selected_product(self):
        product = self._selected_product()
        if not product:
            QMessageBox.warning(self, "تنبيه", "اختر منتج من الجدول أولاً")
            return
        set_product_active(product["id"], 0 if product["is_active"] else 1, self.current_user["id"])
        self.refresh_products_table()

    def delete_selected_product(self):
        product = self._selected_product()
        if not product:
            QMessageBox.warning(self, "تنبيه", "اختر منتج من الجدول أولاً")
            return
        confirm = QMessageBox.question(
            self, "تأكيد الحذف",
            f"⚠️ هل متأكد من حذف \"{product['name']}\" نهائياً؟\n"
            "(الفواتير القديمة لهذا المنتج بتضل محفوظة زي ما هي)"
        )
        if confirm == QMessageBox.Yes:
            try:
                delete_product(product["id"], self.current_user["id"])
                self.refresh_products_table()
            except ProductInStockError as e:
                QMessageBox.warning(
                    self, "ما ينحذف",
                    f"ما فيك تحذف \"{product['name']}\" لأنه لسا فيه رصيد {e.quantity} بالمخزون.\n"
                    "لازم تصفّي رصيد المخزون (يصير نافذ = 0) قبل ما تقدر تحذفه،\n"
                    "أو استخدم تعطيل المنتج بدل الحذف."
                )

    def adjust_selected_product_quantity(self):
        """يفتح نافذة صغيرة لتفعيل/تعطيل تتبّع الكمية وتعديل الرصيد لمنتج محدد - منفصل
        عن نموذج التعديل العام حتى ما ينحذف تتبّع المخزون بالغلط أثناء تعديل السعر مثلاً."""
        product = self._selected_product()
        if not product:
            QMessageBox.warning(self, "تنبيه", "اختر منتج من الجدول أولاً")
            return

        dlg = QDialog(self)
        dlg.setLayoutDirection(Qt.RightToLeft)
        dlg.setWindowTitle(f"📦 مخزون: {product['name']}")
        dlg.setMinimumWidth(340)
        layout = QFormLayout(dlg)

        track_cb = QCheckBox("تتبّع كمية هالمنتج")
        track_cb.setChecked(bool(product.get("track_quantity")))
        layout.addRow(track_cb)

        qty_spin = SmartDoubleSpinBox()
        qty_spin.setRange(0, 100000)
        qty_spin.setDecimals(0)
        qty_spin.setValue(product.get("quantity", 0) or 0)
        qty_spin.setEnabled(track_cb.isChecked())
        track_cb.toggled.connect(qty_spin.setEnabled)
        layout.addRow("الكمية الحالية:", qty_spin)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("حفظ")
        cancel_btn = QPushButton("إلغاء")
        cancel_btn.setObjectName("dangerBtn")
        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)
        layout.addRow(btn_row)
        cancel_btn.clicked.connect(dlg.reject)
        save_btn.clicked.connect(dlg.accept)

        if dlg.exec_() != QDialog.Accepted:
            return

        track_on = track_cb.isChecked()
        new_qty = qty_spin.value() if track_on else 0
        # نعدّل التتبّع فقط هون - الكمية نفسها بتنعدّل عبر set_product_quantity حتى
        # ينسجل الفرق الحقيقي بسجل حركة المخزون (product_stock_transactions)
        update_product(product["id"], product["name"], product["base_price"], product["cost_price"],
                        product["category_id"], product["barcode"], self.current_user["id"],
                        tax_percent=product.get("tax_percent", 0),
                        track_quantity=track_on)
        set_product_quantity(product["id"], new_qty, self.current_user["id"],
                              reason="تعديل مخزون من شاشة إدارة المنتجات")
        self.refresh_products_table()

    def manage_extra_barcodes(self):
        product = self._selected_product()
        if not product:
            QMessageBox.warning(self, "تنبيه", "اختر منتج من الجدول أولاً")
            return
        dialog = ExtraBarcodesDialog(product, self)
        dialog.exec_()

    def manage_options_for_selected(self):
        product = self._selected_product()
        if not product:
            QMessageBox.warning(self, "تنبيه", "اختر منتج من الجدول أولاً")
            return
        dialog = OptionsManagerDialog(product, self)
        dialog.exec_()
        self.refresh_products_table()


class OptionsManagerDialog(QDialog):
    """نافذة فرعية لإدارة الخيارات/الإضافات لمنتج معين (مثال: الحجم، نوع الحليب)."""

    def __init__(self, product, parent=None):
        super().__init__(parent)
        self.product = product
        self.setWindowTitle(f"خيارات: {product['name']}")
        self.setLayoutDirection(Qt.RightToLeft)
        self.resize(450, 400)
        self.init_ui()
        self.refresh()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"⚙️ خيارات وإضافات: {self.product['name']}"))

        self.groups_list = QListWidget()
        layout.addWidget(self.groups_list)

        add_group_row = QHBoxLayout()
        self.new_group_input = QLineEdit()
        self.new_group_input.setPlaceholderText("اسم مجموعة جديدة (مثلاً: الحجم)")
        add_group_btn = QPushButton("إضافة مجموعة")
        add_group_btn.clicked.connect(self.add_group)
        add_group_row.addWidget(self.new_group_input)
        add_group_row.addWidget(add_group_btn)
        layout.addLayout(add_group_row)

        add_value_row = QHBoxLayout()
        self.new_value_name = QLineEdit()
        self.new_value_name.setPlaceholderText("اسم الخيار (مثلاً: كبير)")
        self.new_value_price = SmartDoubleSpinBox()
        self.new_value_price.setRange(0, 100)
        self.new_value_price.setDecimals(2)
        self.new_value_price.setPrefix("سعر إضافي: ")
        add_value_btn = QPushButton("إضافة قيمة لآخر مجموعة محددة")
        add_value_btn.clicked.connect(self.add_value)
        add_value_row.addWidget(self.new_value_name)
        add_value_row.addWidget(self.new_value_price)
        layout.addLayout(add_value_row)
        layout.addWidget(add_value_btn)

        delete_group_btn = QPushButton("حذف المجموعة المحددة بالكامل")
        delete_group_btn.setObjectName("dangerBtn")
        delete_group_btn.clicked.connect(self.delete_group)
        layout.addWidget(delete_group_btn)

        close_btn = QPushButton("إغلاق")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def refresh(self):
        self.groups_list.clear()
        self.groups = get_product_options(self.product["id"])
        for g in self.groups:
            values_text = "، ".join(f"{v['name']} (+{v['extra_price']:.2f})" for v in g["values"])
            item = QListWidgetItem(f"📁 {g['name']}: {values_text or '(لا يوجد قيم بعد)'}")
            item.setData(Qt.UserRole, g["id"])
            self.groups_list.addItem(item)

    def add_group(self):
        name = self.new_group_input.text().strip()
        if not name:
            return
        add_option_group(self.product["id"], name)
        self.new_group_input.clear()
        self.refresh()

    def add_value(self):
        item = self.groups_list.currentItem()
        if not item:
            QMessageBox.warning(self, "تنبيه", "اختر مجموعة أولاً من القائمة فوق")
            return
        name = self.new_value_name.text().strip()
        if not name:
            return
        group_id = item.data(Qt.UserRole)
        add_option_value(group_id, name, self.new_value_price.value())
        self.new_value_name.clear()
        self.new_value_price.setValue(0)
        self.refresh()

    def delete_group(self):
        item = self.groups_list.currentItem()
        if not item:
            return
        confirm = QMessageBox.question(self, "تأكيد", "حذف هاي المجموعة بكل قيمها؟")
        if confirm == QMessageBox.Yes:
            delete_option_group(item.data(Qt.UserRole))
            self.refresh()


# ---------------------------------------------------------------------------
class ExtraBarcodesDialog(QDialog):
    """نافذة إدارة الباركودات الإضافية لمنتج واحد.

    مثال الاستخدام:
        كيد شوكولاتة باركود أصلي 111.
        الزبون جاب كيد فراولة بباركود 222 → نضيف 222 هون
        بدون ما نخلق منتج جديد. بعد الإضافة، مسح 222 بالكاشير
        بيفتح نفس المنتج تماماً.
    """

    def __init__(self, product: dict, parent=None):
        super().__init__(parent)
        self.product = product
        self.setWindowTitle(f"🔖 الباركودات الإضافية — {product['name']}")
        self.setMinimumWidth(480)
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # معلومة الباركود الأصلي
        main_bc = self.product.get("barcode") or "—"
        info = QLabel(f"<b>المنتج:</b> {self.product['name']}<br>"
                      f"<b>الباركود الرئيسي:</b> {main_bc}")
        info.setTextFormat(Qt.RichText)
        layout.addWidget(info)

        # جدول الباركودات الإضافية
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["الباركود", "ملاحظة", ""])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table)

        # صف الإضافة
        add_row = QHBoxLayout()
        self.new_barcode_input = QLineEdit()
        self.new_barcode_input.setPlaceholderText("امسح أو اكتب الباركود الجديد")
        self.new_barcode_input.returnPressed.connect(self.add_barcode)
        self.new_note_input = QLineEdit()
        self.new_note_input.setPlaceholderText("ملاحظة (اختياري، مثلاً: فراولة)")
        add_btn = QPushButton("➕ إضافة")
        add_btn.setObjectName("successBtn")
        add_btn.clicked.connect(self.add_barcode)
        add_row.addWidget(self.new_barcode_input, stretch=2)
        add_row.addWidget(self.new_note_input, stretch=2)
        add_row.addWidget(add_btn)
        layout.addLayout(add_row)

        close_btn = QPushButton("إغلاق")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def refresh(self):
        rows = get_product_barcodes(self.product["id"])
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(r["barcode"]))
            self.table.setItem(i, 1, QTableWidgetItem(r["note"] or ""))
            del_btn = QPushButton("🗑 حذف")
            del_btn.setObjectName("dangerBtn")
            del_btn.clicked.connect(lambda _, rid=r["id"]: self.delete_barcode(rid))
            self.table.setCellWidget(i, 2, del_btn)

    def add_barcode(self):
        barcode = self.new_barcode_input.text().strip()
        if not barcode:
            QMessageBox.warning(self, "تنبيه", "الباركود فاضي")
            return
        note = self.new_note_input.text().strip() or None
        result = add_product_barcode(self.product["id"], barcode, note)
        if result is True:
            self.new_barcode_input.clear()
            self.new_note_input.clear()
            self.new_barcode_input.setFocus()
            self.refresh()
        else:
            QMessageBox.warning(self, "خطأ", str(result))

    def delete_barcode(self, barcode_id: int):
        confirm = QMessageBox.question(self, "تأكيد", "حذف هاد الباركود الإضافي؟")
        if confirm == QMessageBox.Yes:
            delete_product_barcode(barcode_id)
            self.refresh()
