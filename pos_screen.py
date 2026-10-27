# -*- coding: utf-8 -*-
"""شاشة الكاشير - البيع الفعلي."""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                              QScrollArea, QGridLayout, QFrame, QTableWidget,
                              QTableWidgetItem, QMessageBox, QInputDialog, QTabWidget,
                              QHeaderView, QComboBox, QLineEdit, QShortcut, QDialog,
                              QRadioButton, QButtonGroup, QDialogButtonBox, QListWidget,
                              QListWidgetItem, QDateEdit, QGroupBox, QFileDialog, QSizePolicy)
from PyQt5.QtCore import Qt, QDate, QTimer
from PyQt5.QtGui import QKeySequence, QColor
from datetime import timedelta

from ui.widgets import SmartDoubleSpinBox, get_double_input

from database.data_access import (get_categories, get_products_by_category,
                                   create_order, get_setting, get_product_by_barcode,
                                   get_order_with_items, get_product_options,
                                   get_quick_sale_product, get_or_create_customer,
                                   get_orders_for_shift, get_shift_summary,
                                   get_order_by_number, return_order,
                                   get_product_stock_status, search_products_by_name,
                                   get_recent_orders, get_all_orders, hard_delete_order)
from database.db_setup import DB_PATH, get_connection
from utils.cash_drawer import open_cash_drawer
from utils.printer import print_receipt
from utils.time_utils import jordan_now

# ألوان تنبيه المخزون على بطاقة المنتج بشاشة الكاشير
STOCK_BTN_COLORS = {
    "green": "#d4edda",
    "yellow": "#fff3cd",
    "red": "#f8d7da",
}


class VariantDialog(QDialog):
    """نافذة تختار منها النوع/النكهة/الحجم لمنتج عنده خيارات
    (مثال: دخان بأنواع، عصير بنكهات، قهوة بأحجام)."""

    def __init__(self, product, option_groups, parent=None):
        super().__init__(parent)
        self.setLayoutDirection(Qt.RightToLeft)
        self.setWindowTitle(f"اختر: {product['name']}")
        self.product = product
        self.option_groups = option_groups
        self.group_widgets = {}  # group_id -> {value_id: radiobutton}

        layout = QVBoxLayout(self)
        title = QLabel(f"🔸 {product['name']} — اختر النوع/الخيار")
        title.setObjectName("titleLabel")
        layout.addWidget(title)

        for group in option_groups:
            box = QFrame()
            box.setObjectName("card")
            box_layout = QVBoxLayout(box)
            box_layout.addWidget(QLabel(f"{group['name']}:"))
            btn_group = QButtonGroup(self)
            widgets = {}
            for i, val in enumerate(group["values"]):
                extra = val["extra_price"]
                label = val["name"] if extra == 0 else f"{val['name']} (+{extra:.2f})"
                rb = QRadioButton(label)
                if i == 0:
                    rb.setChecked(True)
                btn_group.addButton(rb)
                box_layout.addWidget(rb)
                widgets[val["id"]] = rb
            self.group_widgets[group["id"]] = widgets
            layout.addWidget(box)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_selection(self):
        """يرجع (extra_total, options_snapshot_text)"""
        extra_total = 0
        parts = []
        for group in self.option_groups:
            widgets = self.group_widgets[group["id"]]
            for val in group["values"]:
                rb = widgets[val["id"]]
                if rb.isChecked():
                    extra_total += val["extra_price"]
                    parts.append(f"{group['name']}: {val['name']}")
        return extra_total, " | ".join(parts)


class LineDiscountDialog(QDialog):
    """خصم على صنف واحد بالسلة (وليس الفاتورة كاملة) - بصلاحية مدير فقط.
    يدعم نسبة % أو مبلغ ثابت، والمدير يختار وقت الخصم."""

    def __init__(self, item, parent=None):
        super().__init__(parent)
        self.item = item
        self.setLayoutDirection(Qt.RightToLeft)
        self.setWindowTitle(f"خصم على: {item['name']}")
        self.setMinimumWidth(340)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(f"إجمالي السطر الحالي: {item['line_total']:.2f}"))

        type_row = QHBoxLayout()
        self.percent_radio = QRadioButton("نسبة %")
        self.fixed_radio = QRadioButton("مبلغ ثابت")
        self.percent_radio.setChecked(True)
        type_group = QButtonGroup(self)
        type_group.addButton(self.percent_radio)
        type_group.addButton(self.fixed_radio)
        type_row.addWidget(self.percent_radio)
        type_row.addWidget(self.fixed_radio)
        layout.addLayout(type_row)

        self.value_input = SmartDoubleSpinBox()
        self.value_input.setRange(0, 100000)
        self.value_input.setDecimals(2)
        layout.addWidget(self.value_input)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.value_input.setFocus()

    def get_discount(self):
        """يرجع (discount_type, discount_value, discount_amount)"""
        value = self.value_input.value()
        base = self.item["quantity"] * self.item["unit_price"]
        if self.percent_radio.isChecked():
            amount = round(base * (value / 100), 2)
            return "percent", value, min(amount, base)
        else:
            return "fixed", value, min(value, base)


class QuickSaleDialog(QDialog):
    """حاسبة / بيع يدوي لصنف بدون باركود أو ما إلو بالقائمة أصلاً."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLayoutDirection(Qt.RightToLeft)
        self.setWindowTitle("🧮 حاسبة البيع اليدوي / بدون باركود")
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("اسم الصنف (اختياري):"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("مثلاً: صنف متفرقة")
        layout.addWidget(self.name_input)

        layout.addWidget(QLabel("السعر:"))
        self.price_input = SmartDoubleSpinBox()
        self.price_input.setRange(0, 100000)
        self.price_input.setDecimals(2)
        self.price_input.setSingleStep(0.5)
        layout.addWidget(self.price_input)

        layout.addWidget(QLabel("الكمية:"))
        self.qty_input = SmartDoubleSpinBox()
        self.qty_input.setDecimals(0)
        self.qty_input.setRange(1, 999)
        self.qty_input.setValue(1)
        layout.addWidget(self.qty_input)

        layout.addWidget(QLabel("نسبة الضريبة % (اختياري):"))
        self.tax_input = SmartDoubleSpinBox()
        self.tax_input.setRange(0, 100)
        self.tax_input.setDecimals(2)
        self.tax_input.setValue(0)
        layout.addWidget(self.tax_input)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.price_input.setFocus()

    def get_values(self):
        name = self.name_input.text().strip() or "صنف يدوي"
        return name, self.price_input.value(), int(self.qty_input.value()), self.tax_input.value()


class ReturnInvoiceDialog(QDialog):
    """نافذة استرجاع فاتورة سابقة: تبحث برقم الفاتورة، أو تختار مباشرة من قائمة آخر
    الفواتير (بدل ما تكتب/تنسخ رقم فاتورة طويل يدوياً)، تعرض التفاصيل، وتاخذ سبب الاسترجاع."""

    def __init__(self, shift_id=None, parent=None):
        super().__init__(parent)
        self.setLayoutDirection(Qt.RightToLeft)
        self.setWindowTitle("↩️ استرجاع فاتورة")
        self.setMinimumWidth(460)
        self.found_order = None
        self.shift_id = shift_id

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("📋 اختر من آخر الفواتير مباشرة (دبل كليك):"))
        self.recent_list = QListWidget()
        self.recent_list.setMaximumHeight(150)
        self.recent_list.itemDoubleClicked.connect(self.handle_recent_selected)
        layout.addWidget(self.recent_list)
        self._load_recent_orders()

        layout.addWidget(QLabel("— أو ابحث برقم الفاتورة (مطبوع بأعلى الإيصال) —"))

        search_row = QHBoxLayout()
        self.order_number_input = QLineEdit()
        self.order_number_input.setPlaceholderText("مثال: 20260904-153000-a1b2")
        search_row.addWidget(self.order_number_input)
        search_btn = QPushButton("🔍 بحث")
        search_btn.clicked.connect(self.search_order)
        search_row.addWidget(search_btn)
        layout.addLayout(search_row)

        self.details_label = QLabel("")
        self.details_label.setWordWrap(True)
        self.details_label.setObjectName("card")
        layout.addWidget(self.details_label)

        layout.addWidget(QLabel("سبب الاسترجاع (اختياري):"))
        self.reason_input = QLineEdit()
        self.reason_input.setPlaceholderText("مثلاً: طلب الزبون، غلط بالفاتورة...")
        layout.addWidget(self.reason_input)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("تأكيد الاسترجاع")
        buttons.accepted.connect(self.handle_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.ok_button = buttons.button(QDialogButtonBox.Ok)
        self.ok_button.setEnabled(False)
        self.order_number_input.setFocus()

    def _load_recent_orders(self):
        # نعرض آخر فواتير هالشِفت أولاً (الأكثر احتمالاً يطلبها الكاشير)، ولو الشِفت
        # ما إله فواتير كفاية منعرض آخر الفواتير عموماً
        orders = get_recent_orders(limit=15, shift_id=self.shift_id) or get_recent_orders(limit=15)
        self.recent_list.clear()
        for o in orders:
            label = f"#{o['order_number']}  |  {o['cashier_name']}  |  {o['created_at']}  |  {o['total_amount']:.2f}"
            if o["status"] == "مرتجعة":
                label += "  (مسترجعة مسبقاً)"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, o["order_number"])
            self.recent_list.addItem(item)

    def handle_recent_selected(self, item):
        number = item.data(Qt.UserRole)
        if not number:
            return
        self.order_number_input.setText(number)
        self.search_order()

    def search_order(self):
        number = self.order_number_input.text().strip()
        if not number:
            return
        order = get_order_by_number(number)
        if not order:
            self.details_label.setText("⚠️ ما لقينا فاتورة بهاد الرقم.")
            self.found_order = None
            self.ok_button.setEnabled(False)
            return

        if order["status"] == "مرتجعة":
            self.details_label.setText("⚠️ هاي الفاتورة مسترجعة مسبقاً.")
            self.found_order = None
            self.ok_button.setEnabled(False)
            return
        if order["status"] == "ملغاة":
            self.details_label.setText("⚠️ هاي الفاتورة ملغاة أصلاً، ما ممكن استرجاعها.")
            self.found_order = None
            self.ok_button.setEnabled(False)
            return

        lines = [f"الكاشير: {order.get('cashier_name', '')}", f"التاريخ: {order.get('created_at', '')}"]
        for item in order["items"]:
            lines.append(f"• {item['product_name_snapshot']} x{item['quantity']} = {item['line_total']:.2f}")
        lines.append(f"الإجمالي: {order['total_amount']:.2f}")
        self.details_label.setText("\n".join(lines))
        self.found_order = order
        self.ok_button.setEnabled(True)

    def handle_accept(self):
        if self.found_order:
            self.accept()

    def get_result(self):
        return self.found_order, self.reason_input.text().strip()


class AllInvoicesDialog(QDialog):
    """شاشة كل الفواتير — بدون قيود تاريخ — مع إمكانية الحذف والتصدير."""

    ALL_INVOICES_PASSWORD = "123123"

    def __init__(self, current_user, parent=None):
        super().__init__(parent)
        self.current_user = current_user
        self.orders = []
        self.setLayoutDirection(Qt.RightToLeft)
        self.setWindowTitle("📋 كل الفواتير — النظام الكامل")
        self.resize(950, 620)
        self._build_ui()
        self._load_orders()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # --- شريط الفلترة ---
        filter_box = QGroupBox("🔍 فلترة")
        filter_layout = QHBoxLayout(filter_box)

        filter_layout.addWidget(QLabel("الفترة:"))
        self.period_combo = QComboBox()
        self.period_combo.addItems([
            "الكل", "اليوم", "آخر 7 أيام", "آخر 30 يوم",
            "هذا الشهر", "هذه السنة", "سنة محددة"
        ])
        self.period_combo.currentTextChanged.connect(self._on_period_changed)
        filter_layout.addWidget(self.period_combo)

        self.year_combo = QComboBox()
        _this_year = jordan_now().date().year
        self.year_combo.addItems([str(y) for y in range(_this_year, 2009, -1)])
        self.year_combo.setVisible(False)
        filter_layout.addWidget(self.year_combo)

        filter_layout.addWidget(QLabel("الحالة:"))
        self.status_combo = QComboBox()
        self.status_combo.addItems(["الكل", "مكتملة", "مرتجعة", "ملغاة"])
        filter_layout.addWidget(self.status_combo)

        search_btn = QPushButton("🔍 بحث")
        search_btn.clicked.connect(self._load_orders)
        filter_layout.addWidget(search_btn)

        reset_btn = QPushButton("↩ إعادة تعيين")
        reset_btn.clicked.connect(self._reset_filter)
        filter_layout.addWidget(reset_btn)

        layout.addWidget(filter_box)

        # --- تشخيص: مسار قاعدة البيانات + عدد الفواتير الفعلي بدون أي فلتر ---
        self.debug_label = QLabel("")
        self.debug_label.setStyleSheet("color:#888; font-size:11px;")
        self.debug_label.setWordWrap(True)
        layout.addWidget(self.debug_label)

        # --- إجماليات ---
        self.summary_label = QLabel("")
        self.summary_label.setObjectName("totalLabel")
        layout.addWidget(self.summary_label)

        # --- الجدول ---
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "رقم الفاتورة", "التاريخ والوقت", "الكاشير", "الزبون",
            "الإجمالي", "طريقة الدفع", "الحالة"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.doubleClicked.connect(self._view_details)
        self.table.itemSelectionChanged.connect(self._update_selection_label)
        layout.addWidget(self.table)

        # --- شريط التحديد ---
        select_row = QHBoxLayout()
        self.selection_label = QLabel("لا يوجد تحديد")
        self.selection_label.setObjectName("totalLabel")
        select_row.addWidget(self.selection_label)
        select_row.addStretch()
        select_all_btn = QPushButton("☑ تحديد الكل")
        select_all_btn.clicked.connect(self.table.selectAll)
        select_row.addWidget(select_all_btn)
        deselect_all_btn = QPushButton("☐ إلغاء التحديد")
        deselect_all_btn.clicked.connect(self.table.clearSelection)
        select_row.addWidget(deselect_all_btn)
        layout.addLayout(select_row)

        # --- أزرار الإجراءات ---
        btn_row = QHBoxLayout()

        view_btn = QPushButton("👁 عرض التفاصيل")
        view_btn.clicked.connect(self._view_details)
        btn_row.addWidget(view_btn)

        export_btn = QPushButton("📊 تصدير Excel")
        export_btn.clicked.connect(self._export_excel)
        btn_row.addWidget(export_btn)

        btn_row.addStretch()

        delete_btn = QPushButton("🗑 حذف المحدد نهائياً")
        delete_btn.setObjectName("dangerBtn")
        delete_btn.clicked.connect(self._delete_selected)
        btn_row.addWidget(delete_btn)

        close_btn = QPushButton("✖ إغلاق")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

    def _on_period_changed(self, text):
        self.year_combo.setVisible(text == "سنة محددة")

    def _load_orders(self):
        period = self.period_combo.currentText()
        today = jordan_now().date()
        date_from = None
        date_to = None
        if period == "اليوم":
            date_from = date_to = today.strftime("%Y-%m-%d")
        elif period == "آخر 7 أيام":
            date_from = (today - timedelta(days=6)).strftime("%Y-%m-%d")
            date_to = today.strftime("%Y-%m-%d")
        elif period == "آخر 30 يوم":
            date_from = (today - timedelta(days=29)).strftime("%Y-%m-%d")
            date_to = today.strftime("%Y-%m-%d")
        elif period == "هذا الشهر":
            date_from = today.replace(day=1).strftime("%Y-%m-%d")
            date_to = today.strftime("%Y-%m-%d")
        elif period == "هذه السنة":
            date_from = today.replace(month=1, day=1).strftime("%Y-%m-%d")
            date_to = today.strftime("%Y-%m-%d")
        elif period == "سنة محددة":
            year = int(self.year_combo.currentText())
            date_from = f"{year}-01-01"
            date_to = f"{year}-12-31"
        # period == "الكل" -> date_from/date_to تبقى None، أي بدون أي قيد تاريخ إطلاقاً

        status = self.status_combo.currentText()
        self.orders = get_all_orders(date_from=date_from, date_to=date_to,
                                     status_filter=status)

        # --- تشخيص: نتأكد من مسار قاعدة البيانات الفعلي وعدد الفواتير الكلي بدون أي فلتر ---
        try:
            conn = get_connection()
            total_in_db = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
            first_last = conn.execute(
                "SELECT MIN(created_at), MAX(created_at) FROM orders"
            ).fetchone()
            conn.close()
            if total_in_db == 0:
                self.debug_label.setText(
                    f"⚠️ قاعدة البيانات المستخدمة: {DB_PATH} — جدول orders فاضي كلياً (0 فاتورة)."
                )
            else:
                self.debug_label.setText(
                    f"قاعدة البيانات: {DB_PATH} | إجمالي الفواتير بالجدول (بدون فلتر): {total_in_db} "
                    f"| من {first_last[0]} إلى {first_last[1]}"
                )
        except Exception as e:
            self.debug_label.setText(f"⚠️ خطأ بقراءة قاعدة البيانات: {e}")

        self._fill_table()

    def _reset_filter(self):
        self.period_combo.setCurrentIndex(0)  # "الكل"
        self.year_combo.setVisible(False)
        self.status_combo.setCurrentIndex(0)
        self._load_orders()

    def _fill_table(self):
        self.table.setRowCount(len(self.orders))
        total_amount = 0
        for i, o in enumerate(self.orders):
            self.table.setItem(i, 0, QTableWidgetItem(o["order_number"] or ""))
            self.table.setItem(i, 1, QTableWidgetItem(o["created_at"] or ""))
            self.table.setItem(i, 2, QTableWidgetItem(o.get("cashier_name") or ""))
            cust = o.get("customer_name") or "-"
            self.table.setItem(i, 3, QTableWidgetItem(cust))
            self.table.setItem(i, 4, QTableWidgetItem(f"{o['total_amount']:.2f}"))
            self.table.setItem(i, 5, QTableWidgetItem(o.get("payment_method") or ""))
            status_item = QTableWidgetItem(o["status"])
            if o["status"] == "مكتملة":
                status_item.setForeground(QColor("#155724"))
            elif o["status"] == "مرتجعة":
                status_item.setForeground(QColor("#856404"))
            elif o["status"] == "ملغاة":
                status_item.setForeground(QColor("#721c24"))
            self.table.setItem(i, 6, status_item)
            if o["status"] == "مكتملة":
                total_amount += o["total_amount"]

        self.summary_label.setText(
            f"إجمالي الفواتير: {len(self.orders)} | "
            f"إجمالي المبيعات المكتملة: {total_amount:.2f}"
        )

    def _view_details(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.orders):
            QMessageBox.information(self, "تنبيه", "اختر فاتورة أولاً")
            return
        order = get_order_with_items(self.orders[row]["id"])
        if not order:
            return
        lines = [
            f"رقم الفاتورة: {order['order_number']}",
            f"التاريخ: {order['created_at']}",
            f"الكاشير: {order.get('cashier_name', '')}",
            f"نوع الطلب: {order.get('order_type', '')}",
            "-" * 40,
        ]
        for it in order.get("items", []):
            opt = f" ({it['options_snapshot']})" if it.get("options_snapshot") else ""
            lines.append(
                f"{it['product_name_snapshot']}{opt} × {it['quantity']} = {it['line_total']:.2f}"
            )
        lines += [
            "-" * 40,
            f"المجموع الفرعي: {order['subtotal']:.2f}",
            f"الخصم: {order['discount_amount']:.2f}",
            f"الضريبة: {order['tax_amount']:.2f}",
            f"الإجمالي: {order['total_amount']:.2f}",
            f"طريقة الدفع: {order.get('payment_method', '')}",
            f"الحالة: {order['status']}",
        ]
        QMessageBox.information(
            self, f"تفاصيل الفاتورة {order['order_number']}", "\n".join(lines)
        )

    def _update_selection_label(self):
        selected_rows = sorted(set(idx.row() for idx in self.table.selectedIndexes()))
        count = len(selected_rows)
        if count == 0:
            self.selection_label.setText("لا يوجد تحديد")
        else:
            total = sum(self.orders[r]["total_amount"] for r in selected_rows if r < len(self.orders))
            self.selection_label.setText(f"محدد: {count} فاتورة | إجمالي المحدد: {total:.2f}")

    def _delete_selected(self):
        selected_rows = sorted(set(idx.row() for idx in self.table.selectedIndexes()))
        if not selected_rows:
            QMessageBox.information(self, "تنبيه", "اختر فاتورة أو أكثر أولاً")
            return

        selected_orders = [self.orders[r] for r in selected_rows if r < len(self.orders)]
        count = len(selected_orders)
        total = sum(o["total_amount"] for o in selected_orders)

        if count == 1:
            o = selected_orders[0]
            msg_body = (f"الفاتورة رقم: {o['order_number']}\n"
                        f"بتاريخ: {o['created_at']}\nالإجمالي: {o['total_amount']:.2f}")
        else:
            lines = "\n".join(f"  • {o['order_number']} ({o['total_amount']:.2f})"
                              for o in selected_orders[:10])
            if count > 10:
                lines += f"\n  ... و{count - 10} فواتير أخرى"
            msg_body = f"عدد الفواتير: {count}\nالإجمالي الكلي: {total:.2f}\n\n{lines}"

        confirm = QMessageBox.question(
            self,
            f"⚠️ تأكيد حذف {count} فاتورة نهائياً",
            f"{msg_body}\n\n⚠️ هذا الحذف نهائي ولا يمكن التراجع عنه!",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return

        failed = []
        for o in selected_orders:
            success, err = hard_delete_order(o["id"], self.current_user["id"])
            if not success:
                failed.append(f"{o['order_number']}: {err}")

        if failed:
            QMessageBox.warning(self, "تحذير",
                                f"تم حذف معظم الفواتير، لكن فشل الحذف في:\n" + "\n".join(failed))
        else:
            QMessageBox.information(self, "تم", f"تم حذف {count} فاتورة بنجاح ✓")
        self._load_orders()

    def _export_excel(self):
        if not self.orders:
            QMessageBox.information(self, "تنبيه", "لا توجد فواتير للتصدير")
            return
        filepath, _ = QFileDialog.getSaveFileName(
            self, "حفظ ملف Excel",
            f"كل_الفواتير_{jordan_now().strftime('%Y-%m-%d')}.xlsx",
            "Excel Files (*.xlsx)"
        )
        if not filepath:
            return
        from utils.excel_export import export_rows_to_excel
        headers = ["رقم الفاتورة", "التاريخ", "الكاشير", "الزبون",
                   "الإجمالي", "طريقة الدفع", "الخصم", "الضريبة", "الحالة"]
        rows = [
            (
                o["order_number"], o["created_at"], o.get("cashier_name", ""),
                o.get("customer_name") or "-", o["total_amount"],
                o.get("payment_method", ""), o.get("discount_amount", 0),
                o.get("tax_amount", 0), o["status"]
            )
            for o in self.orders
        ]
        completed = [o for o in self.orders if o["status"] == "مكتملة"]
        summary = [
            ("إجمالي الفواتير", len(self.orders)),
            ("إجمالي المبيعات المكتملة", sum(o["total_amount"] for o in completed)),
            ("الفترة المحددة", self.period_combo.currentText()),
            ("الحالة", self.status_combo.currentText()),
        ]
        success, msg = export_rows_to_excel(filepath, "كل الفواتير", headers, rows, summary)
        if success:
            QMessageBox.information(self, "تم التصدير", msg)
        else:
            QMessageBox.warning(self, "خطأ", msg)


class POSScreen(QWidget):
    def __init__(self, current_user, current_shift_id, on_logout, on_manage_products=None,
                 on_manage_settings=None, on_view_reports=None):
        super().__init__()
        self.current_user = current_user
        self.current_shift_id = current_shift_id
        self.on_logout = on_logout
        self.on_manage_products = on_manage_products
        self.on_manage_settings = on_manage_settings
        self.on_view_reports = on_view_reports
        self._SECTION_PASSWORD = "1212"  # باسورد الأقسام المحمية
        self.cart = []  # قائمة العناصر بالسلة الحالية
        self._last_order_id = None  # آخر فاتورة مكتملة - تُستخدم لإعادة الطباعة بـ F10
        self.setLayoutDirection(Qt.RightToLeft)
        self.init_ui()
        self.load_categories()
        self.init_shortcuts()
        self.refresh_today_stats()

    # ---------------------------------------------------------
    def _update_clock(self):
        """تحديث عرض الوقت والتاريخ بتوقيت الأردن."""
        now = jordan_now()
        DAYS_AR = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
        day_name = DAYS_AR[now.weekday()]
        text = f"{day_name}  {now.strftime('%Y/%m/%d')}  |  {now.strftime('%I:%M:%S %p')}"
        text = text.replace("AM", "ص").replace("PM", "م")
        self.clock_label.setText(text)

    # ---------------------------------------------------------
    def _ask_password(self, title="🔒 تحقق من الصلاحية"):
        """يطلب كلمة السر قبل الدخول للأقسام المحمية. يرجع True لو صحيحة."""
        pwd, ok = QInputDialog.getText(
            self, title,
            "أدخل كلمة السر للمتابعة:",
            QLineEdit.Password
        )
        if not ok:
            return False
        if pwd == self._SECTION_PASSWORD:
            return True
        QMessageBox.warning(self, "خطأ", "كلمة السر غير صحيحة.")
        return False

    def _open_manage_products_protected(self):
        if self._ask_password("🛠 إدارة المنتجات") and self.on_manage_products:
            self.on_manage_products()

    def _open_reports_protected(self):
        if self._ask_password("📊 التقارير") and self.on_view_reports:
            self.on_view_reports()

    def _open_all_invoices_protected(self):
        """يفتح شاشة كل الفواتير بعد التحقق من كلمة السر الخاصة بها."""
        pwd, ok = QInputDialog.getText(
            self, "🔒 كل الفواتير",
            "أدخل كلمة السر للوصول لكل الفواتير:",
            QLineEdit.Password
        )
        if not ok:
            return
        if pwd != AllInvoicesDialog.ALL_INVOICES_PASSWORD:
            QMessageBox.warning(self, "خطأ", "كلمة السر غير صحيحة.")
            return
        dlg = AllInvoicesDialog(self.current_user, parent=self)
        dlg.exec_()
        # بعد إغلاق نافذة كل الفواتير، لازم نحدّث إحصائيات الشِفت بالواجهة الرئيسية
        # فوراً لأنه ممكن يكون تم حذف فواتير نهائياً من جوا النافذة وأثّرت على المبيعات
        self.refresh_today_stats()
        self.load_categories()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)

        # ===== شريط الهيدر العلوي =====
        header = QHBoxLayout()
        user_label = QLabel(f"👤 {self.current_user['full_name']}")
        user_label.setObjectName("titleLabel")
        header.addWidget(user_label)

        self.clock_label = QLabel()
        self.clock_label.setObjectName("clockLabel")
        self.clock_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self._update_clock()
        header.addWidget(self.clock_label)

        header.addStretch()
        if self.current_user["role"] == "admin" and self.on_manage_products:
            manage_btn = QPushButton("🛠 إدارة المنتجات")
            manage_btn.clicked.connect(self._open_manage_products_protected)
            header.addWidget(manage_btn)
        if self.current_user["role"] == "admin" and self.on_view_reports:
            reports_btn = QPushButton("📊 التقارير")
            reports_btn.clicked.connect(self._open_reports_protected)
            header.addWidget(reports_btn)
        if self.current_user["role"] == "admin" and self.on_manage_settings:
            settings_btn = QPushButton("⚙️ الإعدادات")
            settings_btn.clicked.connect(self.on_manage_settings)
            header.addWidget(settings_btn)
        my_invoices_btn = QPushButton("🧾 فواتيري اليوم")
        my_invoices_btn.clicked.connect(self.show_my_invoices)
        header.addWidget(my_invoices_btn)
        all_invoices_btn = QPushButton("📋 كل الفواتير")
        all_invoices_btn.clicked.connect(self._open_all_invoices_protected)
        header.addWidget(all_invoices_btn)
        logout_btn = QPushButton("تسجيل خروج")
        logout_btn.setObjectName("dangerBtn")
        logout_btn.clicked.connect(self.on_logout)
        header.addWidget(logout_btn)
        main_layout.addLayout(header)

        # تايمر ساعة الأردن — يتجدد كل ثانية
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1000)

        # شريط مبيعات اليوم
        today_stats_row = QHBoxLayout()
        self.today_stats_label = QLabel("مبيعاتي اليوم: 0.00 | عدد الفواتير: 0")
        self.today_stats_label.setObjectName("totalLabel")
        today_stats_row.addWidget(self.today_stats_label)
        today_stats_row.addStretch()
        main_layout.addLayout(today_stats_row)

        # شريط الاختصارات — يظهر دايماً (النظام أصبح بمستخدم أدمن وحيد بيبيع ويدير)
        shortcuts_bar = QHBoxLayout()
        shortcuts_bar.setSpacing(4)
        shortcut_hints = [
            ("F1",  "باركود",          self.focus_barcode_input),
            ("F2",  "بيع يدوي",        self.open_quick_sale_dialog),
            ("F3",  "دفع كاش 💵",      lambda: self.checkout("كاش")),
            ("F4",  "دفع فيزا 💳",     lambda: self.checkout("شبكة")),
            ("F5",  "مبيعات اليوم",    self.show_my_invoices),
            ("F6",  "فتح الدرج",       self.open_drawer_manual),
            ("F7",  "مرتجع",           self.open_return_invoice_dialog),
            ("F10", "إعادة طباعة",     self.reprint_last_invoice),
            ("F11", "❓ الاختصارات",   self.show_shortcuts_help),
            ("ESC", "مسح الفاتورة 🗑", self.clear_cart),
        ]
        for key, desc, action in shortcut_hints:
            btn = QPushButton(f"[{key}]  {desc}")
            btn.setObjectName("shortcutHintBtn")
            btn.setFocusPolicy(Qt.NoFocus)  # ما يسرق الفوكس من الباركود
            btn.clicked.connect(action)
            shortcuts_bar.addWidget(btn)
        shortcuts_bar.addStretch()
        main_layout.addLayout(shortcuts_bar)

        # شريط الباركود + أزرار سريعة
        barcode_row = QHBoxLayout()
        barcode_label = QLabel("📷 امسح الباركود:")
        self.barcode_input = QLineEdit()
        self.barcode_input.setPlaceholderText("امسح المنتج هون، أو اكتب الباركود واضغط Enter")
        self.barcode_input.returnPressed.connect(self.handle_barcode_scan)
        barcode_row.addWidget(barcode_label)
        barcode_row.addWidget(self.barcode_input, stretch=1)

        drawer_btn_top = QPushButton("💰 فتح الدرج (F6)")
        drawer_btn_top.clicked.connect(self.open_drawer_manual)
        barcode_row.addWidget(drawer_btn_top)

        # زر إظهار الفاتورة الحالية
        self.show_cart_btn = QPushButton("🧾 عرض الفاتورة")
        self.show_cart_btn.setObjectName("successBtn")
        self.show_cart_btn.clicked.connect(self.show_cart_panel)
        barcode_row.addWidget(self.show_cart_btn)

        main_layout.addLayout(barcode_row)
        self.barcode_input.setFocus()

        # ===== بحث سريع بالمنتجات بالاسم (منفصل عن خانة الباركود) =====
        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("🔎 بحث سريع باسم الصنف:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("اكتب جزء من اسم المنتج...")
        self.search_input.textChanged.connect(self.handle_quick_search)
        search_row.addWidget(self.search_input, stretch=1)
        main_layout.addLayout(search_row)

        self.search_results_list = QListWidget()
        self.search_results_list.setMaximumHeight(160)
        self.search_results_list.itemDoubleClicked.connect(self.handle_search_result_clicked)
        self.search_results_list.hide()
        main_layout.addWidget(self.search_results_list)

        # ===== منطقة الفئات والمنتجات - تملأ كل المساحة =====
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs, stretch=1)

        # ===== تهيئة متغيرات السلة المخفية =====
        self.discount_amount = 0

        # إنشاء عناصر السلة (مخفية، تُعرض في نافذة منفصلة)
        self.cart_table = QTableWidget(0, 4)
        self.cart_table.setHorizontalHeaderLabels(["الصنف", "كمية", "سعر", "الإجمالي"])
        self.cart_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.cart_table.verticalHeader().setVisible(False)
        self.cart_table.setAlternatingRowColors(True)

        self.customer_name_input = QLineEdit()
        self.customer_name_input.setPlaceholderText("اسم الزبون (اختياري)")
        self.customer_phone_input = QLineEdit()
        self.customer_phone_input.setPlaceholderText("رقم الهاتف (اختياري)")

        self.order_type_combo = QComboBox()
        self.order_type_combo.addItems(["بالمحل", "دلفري"])

        self.subtotal_label = QLabel("المجموع الفرعي: 0.00")
        self.tax_label = QLabel("الضريبة (حسب كل صنف): 0.00")
        self.total_label = QLabel("الإجمالي: 0.00")
        self.total_label.setObjectName("totalLabel")

        # نافذة الفاتورة (تُبنى مرة واحدة وتُعرض عند الطلب)
        self._cart_dialog = None

    # ---------------------------------------------------------
    def show_cart_panel(self):
        """يفتح نافذة الفاتورة الحالية كـ dialog منفصل كبير."""
        if self._cart_dialog and self._cart_dialog.isVisible():
            self._rebuild_cart_dialog_table()
            self._cart_dialog.raise_()
            self._cart_dialog.activateWindow()
            return

        dialog = QDialog(self)
        dialog.setLayoutDirection(Qt.RightToLeft)
        dialog.setWindowTitle("🧾 الفاتورة الحالية")
        # نافذة كبيرة واضحة
        dialog.resize(700, 750)
        self._cart_dialog = dialog

        main_v = QVBoxLayout(dialog)
        main_v.setContentsMargins(20, 16, 20, 16)
        main_v.setSpacing(10)

        # عنوان
        cart_title = QLabel("🧾 الفاتورة الحالية")
        cart_title.setObjectName("titleLabel")
        cart_title.setAlignment(Qt.AlignCenter)
        cart_title.setStyleSheet("font-size:18px; font-weight:bold; padding:6px;")
        main_v.addWidget(cart_title)

        # جدول الأصناف - كبير ويأخذ أكبر مساحة
        self._dlg_cart_table = QTableWidget(0, 4)
        self._dlg_cart_table.setHorizontalHeaderLabels(["الصنف", "كمية", "سعر", "الإجمالي"])
        self._dlg_cart_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._dlg_cart_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._dlg_cart_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._dlg_cart_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._dlg_cart_table.verticalHeader().setVisible(False)
        self._dlg_cart_table.setAlternatingRowColors(True)
        self._dlg_cart_table.setMinimumHeight(280)
        self._dlg_cart_table.setStyleSheet("font-size:14px;")
        self._dlg_cart_table.doubleClicked.connect(self._dlg_edit_quantity)
        main_v.addWidget(self._dlg_cart_table, stretch=1)
        main_v.addWidget(QLabel("💡 دبل كليك على عمود الكمية لتعديلها مباشرة"))

        # صف أزرار على الصنف المحدد
        line_actions_row = QHBoxLayout()
        remove_btn = QPushButton("🗑 حذف الصنف المحدد")
        remove_btn.clicked.connect(self._dlg_remove_selected)
        line_discount_btn = QPushButton("💸 خصم على الصنف المحدد (مدير)")
        line_discount_btn.clicked.connect(self._dlg_apply_line_discount)
        line_actions_row.addWidget(remove_btn)
        line_actions_row.addWidget(line_discount_btn)
        main_v.addLayout(line_actions_row)

        # بيانات الزبون
        customer_row = QHBoxLayout()
        self._dlg_name = QLineEdit()
        self._dlg_name.setPlaceholderText("اسم الزبون (اختياري)")
        self._dlg_name.setText(self.customer_name_input.text())
        self._dlg_name.textChanged.connect(lambda t: self.customer_name_input.setText(t))
        self._dlg_phone = QLineEdit()
        self._dlg_phone.setPlaceholderText("رقم الهاتف (اختياري)")
        self._dlg_phone.setText(self.customer_phone_input.text())
        self._dlg_phone.textChanged.connect(lambda t: self.customer_phone_input.setText(t))
        customer_row.addWidget(self._dlg_name)
        customer_row.addWidget(self._dlg_phone)
        main_v.addLayout(customer_row)

        # نوع الطلب
        order_type_row = QHBoxLayout()
        order_type_row.addWidget(QLabel("نوع الطلب:"))
        self._dlg_order_type = QComboBox()
        self._dlg_order_type.addItems(["بالمحل", "دلفري"])
        self._dlg_order_type.setCurrentIndex(self.order_type_combo.currentIndex())
        self._dlg_order_type.currentIndexChanged.connect(
            lambda i: self.order_type_combo.setCurrentIndex(i))
        order_type_row.addWidget(self._dlg_order_type)
        order_type_row.addStretch()
        main_v.addLayout(order_type_row)

        # الإجماليات بشكل واضح
        totals_frame = QFrame()
        totals_frame.setObjectName("card")
        totals_v = QVBoxLayout(totals_frame)
        self._dlg_subtotal = QLabel("المجموع الفرعي: 0.00")
        self._dlg_tax = QLabel("الضريبة (حسب كل صنف): 0.00")
        self._dlg_total = QLabel("الإجمالي: 0.00")
        self._dlg_total.setObjectName("totalLabel")
        self._dlg_total.setStyleSheet("font-size:20px; font-weight:bold; color:#1F4E79;")
        totals_v.addWidget(self._dlg_subtotal)
        totals_v.addWidget(self._dlg_tax)
        totals_v.addWidget(self._dlg_total)
        main_v.addWidget(totals_frame)

        # خصم
        discount_btn = QPushButton("إضافة خصم (مدير)")
        discount_btn.clicked.connect(self.apply_discount)
        main_v.addWidget(discount_btn)

        # أزرار الدفع - كبيرة وواضحة
        pay_row = QHBoxLayout()
        cash_btn = QPushButton("💵 دفع كاش")
        cash_btn.setObjectName("successBtn")
        cash_btn.setMinimumHeight(50)
        cash_btn.setStyleSheet("font-size:16px; font-weight:bold;")
        cash_btn.clicked.connect(lambda: self.checkout("كاش"))
        card_btn = QPushButton("💳 دفع شبكة")
        card_btn.setObjectName("successBtn")
        card_btn.setMinimumHeight(50)
        card_btn.setStyleSheet("font-size:16px; font-weight:bold;")
        card_btn.clicked.connect(lambda: self.checkout("شبكة"))
        pay_row.addWidget(cash_btn)
        pay_row.addWidget(card_btn)
        main_v.addLayout(pay_row)

        # أزرار ثانوية
        bottom_row = QHBoxLayout()
        quick_btn = QPushButton("🧮 بيع يدوي (F2)")
        quick_btn.clicked.connect(self.open_quick_sale_dialog)
        return_btn = QPushButton("↩️ استرجاع فاتورة")
        return_btn.setObjectName("dangerBtn")
        return_btn.clicked.connect(self.open_return_invoice_dialog)
        clear_btn = QPushButton("🗑 إلغاء الفاتورة")
        clear_btn.setObjectName("dangerBtn")
        clear_btn.clicked.connect(self.clear_cart)
        bottom_row.addWidget(quick_btn)
        bottom_row.addWidget(return_btn)
        bottom_row.addWidget(clear_btn)
        main_v.addLayout(bottom_row)

        self._rebuild_cart_dialog_table()
        dialog.show()

    def _dlg_remove_selected(self):
        """حذف الصنف المحدد من جدول الفاتورة داخل الـ dialog."""
        row = self._dlg_cart_table.currentRow()
        if row >= 0:
            del self.cart[row]
            self._rebuild_cart_dialog_table()
            self.refresh_cart_table()

    def _dlg_edit_quantity(self, index):
        """تعديل كمية سطر بالسلة مباشرة (دبل كليك على عمود الكمية) - بدون حذف السطر وإعادة إضافته."""
        row = index.row()
        if row < 0 or row >= len(self.cart):
            return
        if index.column() != 1:
            return
        item = self.cart[row]
        new_qty, ok = get_double_input(
            self, "تعديل الكمية", f"الكمية الجديدة لـ \"{item['name']}\":",
            item["quantity"], 1, 999, 0
        )
        if not ok:
            return
        new_qty = int(new_qty)
        item["quantity"] = new_qty
        self._recalc_line_total(item)
        self._rebuild_cart_dialog_table()
        self.refresh_cart_table()

    def _recalc_line_total(self, item):
        """يعيد حساب إجمالي السطر بعد تغيير الكمية، مع الحفاظ على أي خصم مطبّق على نفس السطر."""
        base = item["quantity"] * item["unit_price"]
        discount_type = item.get("line_discount_type")
        discount_value = item.get("line_discount_value", 0) or 0
        if discount_type == "percent":
            discount_amount = round(base * (discount_value / 100), 2)
        elif discount_type == "fixed":
            discount_amount = min(discount_value, base)
        else:
            discount_amount = 0
        item["line_discount_amount"] = discount_amount
        item["line_total"] = round(base - discount_amount, 2)

    def _dlg_apply_line_discount(self):
        """خصم على صنف منفرد بالسلة - بصلاحية مدير فقط (نفس منطق الخصم على الفاتورة كاملة)."""
        if self.current_user.get("role") != "admin":
            QMessageBox.warning(self, "غير مسموح", "خصم صنف منفرد يحتاج صلاحية مدير")
            return
        row = self._dlg_cart_table.currentRow()
        if row < 0 or row >= len(self.cart):
            QMessageBox.warning(self, "تنبيه", "اختر صنف من الجدول أولاً")
            return
        item = self.cart[row]
        dialog = LineDiscountDialog(item, self)
        if dialog.exec_() != QDialog.Accepted:
            return
        discount_type, discount_value, discount_amount = dialog.get_discount()
        item["line_discount_type"] = discount_type
        item["line_discount_value"] = discount_value
        item["line_discount_amount"] = discount_amount
        item["line_total"] = round(item["quantity"] * item["unit_price"] - discount_amount, 2)
        self._rebuild_cart_dialog_table()
        self.refresh_cart_table()

    def _rebuild_cart_dialog_table(self):
        """يحدث جدول الفاتورة والإجماليات داخل نافذة الفاتورة."""
        if not hasattr(self, '_dlg_cart_table') or self._dlg_cart_table is None:
            return
        t = self._dlg_cart_table
        t.setRowCount(len(self.cart))
        for i, item in enumerate(self.cart):
            t.setItem(i, 0, QTableWidgetItem(item["name"]))
            t.setItem(i, 1, QTableWidgetItem(str(item["quantity"])))
            t.setItem(i, 2, QTableWidgetItem(f"{item['unit_price']:.2f}"))
            t.setItem(i, 3, QTableWidgetItem(f"{item['line_total']:.2f}"))
        # تحديث الإجماليات
        subtotal = sum(i["line_total"] for i in self.cart)
        discount_ratio = (self.discount_amount / subtotal) if subtotal > 0 else 0
        tax = 0
        for i in self.cart:
            item_tax = i.get("tax_percent", 0) or 0
            line_after = i["line_total"] * (1 - discount_ratio)
            tax += line_after * (item_tax / 100)
        tax = round(tax, 2)
        total = round(subtotal - self.discount_amount + tax, 2)
        self._dlg_subtotal.setText(f"المجموع الفرعي: {subtotal:.2f}")
        self._dlg_tax.setText(f"الضريبة: {tax:.2f}")
        self._dlg_total.setText(f"الإجمالي: {total:.2f}")

    # ---------------------------------------------------------
    def load_categories(self):
        self.tabs.clear()
        categories = get_categories()
        if not categories:
            empty_label = QLabel("لا يوجد فئات منتجات بعد.\nالرجاء إضافتها من شاشة إدارة المنتجات.")
            empty_label.setAlignment(Qt.AlignCenter)
            self.tabs.addTab(empty_label, "تنبيه")
            return

        for cat in categories:
            tab = QWidget()
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            inner = QWidget()
            grid = QGridLayout(inner)
            grid.setSpacing(10)

            products = get_products_by_category(cat["id"])
            row, col = 0, 0
            for p in products:
                status = get_product_stock_status(p)
                label = f"{p['name']}\n{p['base_price']:.2f}"
                if status == "red":
                    label += "\n🔴 نافذ"
                elif status == "yellow":
                    label += f"\n🟡 باقي {p['quantity']:.0f}"
                btn = QPushButton(label)
                btn.setObjectName("productBtn")
                color = STOCK_BTN_COLORS.get(status)
                if color:
                    btn.setStyleSheet(f"background-color: {color};")
                btn.clicked.connect(lambda checked, prod=p: self.add_to_cart(prod))
                grid.addWidget(btn, row, col)
                col += 1
                if col >= 4:
                    col = 0
                    row += 1

            scroll.setWidget(inner)
            tab_layout = QVBoxLayout(tab)
            tab_layout.addWidget(scroll)
            self.tabs.addTab(tab, cat["name"])

    # ---------------------------------------------------------
    def init_shortcuts(self):
        """
        اختصارات لوحة المفاتيح.
        F1–F7, F10, F11, ESC — نفس الاختصارات للمستخدم الوحيد (الأدمن).
        """
        # F1 - باركود: نقّل المؤشر لخانة المسح الضوئي
        QShortcut(QKeySequence("F1"), self, activated=self.focus_barcode_input)

        # F2 - بيع يدوي: اختر منتج بدون باركود
        QShortcut(QKeySequence("F2"), self, activated=self.open_quick_sale_dialog)

        # F3 - دفع كاش
        QShortcut(QKeySequence("F3"), self, activated=lambda: self.checkout("كاش"))

        # F4 - دفع فيزا
        QShortcut(QKeySequence("F4"), self, activated=lambda: self.checkout("شبكة"))

        # F5 - مبيعات اليوم
        QShortcut(QKeySequence("F5"), self, activated=self.show_my_invoices)

        # F6 - فتح درج الكاش يدوياً
        QShortcut(QKeySequence("F6"), self, activated=self.open_drawer_manual)

        # F7 - مرتجع / فاتورة سابقة
        QShortcut(QKeySequence("F7"), self, activated=self.open_return_invoice_dialog)

        # F10 - إعادة طباعة آخر فاتورة
        QShortcut(QKeySequence("F10"), self, activated=self.reprint_last_invoice)

        # F11 - قائمة الاختصارات (للكاشير)
        QShortcut(QKeySequence("F11"), self, activated=self.show_shortcuts_help)

        # ESC - مسح الفاتورة الحالية
        QShortcut(QKeySequence("Escape"), self, activated=self.clear_cart)

    def reprint_last_invoice(self):
        if not self._last_order_id:
            QMessageBox.information(self, "طباعة", "ما في فاتورة مكتملة بعد لطباعتها.")
            return
        order_data = get_order_with_items(self._last_order_id)
        if not order_data:
            return
        store_name = get_setting("store_name", "love.jo")
        footer = get_setting("receipt_footer", "شكراً لزيارتكم")
        success, msg = print_receipt(
            order_data, store_name=store_name,
            tax_percent=float(get_setting("tax_percent", "16")), footer=footer,
            printer_port=get_setting("printer_port", "") or None,
            printer_name=get_setting("printer_name", "") or None,
        )
        if not success:
            QMessageBox.warning(self, "تنبيه طباعة", msg)

    def show_shortcuts_help(self):
        """يعرض نافذة قائمة الاختصارات."""
        shortcuts = [
            ("F1",  "باركود",           "نقّل المؤشر لخانة الباركود — جهّز الجهاز للمسح الضوئي"),
            ("F2",  "بيع يدوي",         "افتح نافذة اختيار المنتج يدوياً بدون باركود"),
            ("F3",  "دفع كاش 💵",       "أتمّ الفاتورة الحالية بالدفع كاش"),
            ("F4",  "دفع فيزا 💳",      "أتمّ الفاتورة الحالية بالدفع عبر كرت/شبكة"),
            ("F5",  "مبيعات اليوم",     "شوف كل الفواتير اللي تمّت خلال هاليوم"),
            ("F6",  "فتح الدرج",        "افتح درج الكاش يدوياً بدون عملية بيع"),
            ("F7",  "مرتجع",            "ابحث عن فاتورة قديمة وافتح نافذة الاسترجاع"),
            ("F10", "إعادة طباعة",      "اطبع نسخة ثانية من آخر فاتورة"),
            ("F11", "الاختصارات ❓",    "افتح هاي الشاشة — قائمة كل الاختصارات"),
            ("ESC", "مسح الفاتورة 🗑",  "فرّغ السلة الحالية وابدأ فاتورة جديدة"),
        ]
        highlight_keys = {"F3", "F4"}

        dlg = QDialog(self)
        dlg.setWindowTitle("⌨️ اختصارات لوحة المفاتيح")
        dlg.setLayoutDirection(Qt.RightToLeft)
        dlg.setMinimumWidth(580)
        layout = QVBoxLayout(dlg)
        layout.setSpacing(6)

        title = QLabel("⌨️ اختصارات لوحة المفاتيح — اضغط الزر لتنفيذه مباشرة")
        title.setObjectName("titleLabel")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        table = QTableWidget(len(shortcuts), 3)
        table.setHorizontalHeaderLabels(["الزر", "الوظيفة", "الشرح"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionMode(QTableWidget.NoSelection)
        table.setAlternatingRowColors(True)

        for row, (key, name, desc) in enumerate(shortcuts):
            key_item  = QTableWidgetItem(f"  {key}  ")
            name_item = QTableWidgetItem(name)
            desc_item = QTableWidgetItem(desc)
            key_item.setTextAlignment(Qt.AlignCenter)
            if key in highlight_keys:
                for item in (key_item, name_item, desc_item):
                    item.setBackground(QColor("#1a3a1a"))
                    item.setForeground(QColor("#7fff7f"))
            table.setItem(row, 0, key_item)
            table.setItem(row, 1, name_item)
            table.setItem(row, 2, desc_item)

        table.resizeRowsToContents()
        layout.addWidget(table)

        note = QLabel("💡 الأزرار الخضراء هي الأكثر استخداماً خلال البيع اليومي.")
        note.setAlignment(Qt.AlignCenter)
        layout.addWidget(note)

        close_btn = QPushButton("حسناً، فهمت ✓")
        close_btn.clicked.connect(dlg.accept)
        layout.addWidget(close_btn)

        dlg.exec_()

    # ---------------------------------------------------------
    def handle_quick_search(self, text):
        text = text.strip()
        if not text:
            self.search_results_list.hide()
            self.search_results_list.clear()
            return
        results = search_products_by_name(text)
        self.search_results_list.clear()
        if not results:
            item = QListWidgetItem("لا يوجد منتجات مطابقة")
            item.setFlags(Qt.NoItemFlags)
            self.search_results_list.addItem(item)
        else:
            for p in results:
                status = get_product_stock_status(p)
                badge = {"green": "🟢", "yellow": "🟡", "red": "🔴"}.get(status, "")
                item = QListWidgetItem(f"{badge} {p['name']} — {p['base_price']:.2f} ({p['category_name']})")
                item.setData(Qt.UserRole, p)
                self.search_results_list.addItem(item)
        self.search_results_list.show()

    def handle_search_result_clicked(self, item):
        product = item.data(Qt.UserRole)
        if not product:
            return
        self.add_to_cart(product)
        self.search_input.clear()
        self.search_results_list.hide()

    def focus_barcode_input(self):
        self.barcode_input.setFocus()
        self.barcode_input.selectAll()

    def refresh_today_stats(self):
        stats = get_shift_summary(self.current_shift_id)
        self.today_stats_label.setText(
            f"مبيعات الشِفت: {stats['total_sales']:.2f} | عدد الفواتير: {stats['orders_count']}"
        )

    def open_manage_products_shortcut(self):
        if self.current_user.get("role") != "admin":
            QMessageBox.warning(self, "غير مسموح", "إدارة المنتجات تحتاج صلاحية مدير")
            return
        self._open_manage_products_protected()

    def open_drawer_manual(self):
        opened = open_cash_drawer(
            printer_port=get_setting("printer_port", "") or None,
            printer_name=get_setting("printer_name", "") or None,
        )
        if not opened:
            QMessageBox.information(
                self, "درج الكاش",
                "ما قدرنا نفتح الدرج تلقائياً (ما في طابعة/بورت متوصل).\n"
                "افتحيه يدوياً إذا لزم."
            )

    def open_return_invoice_dialog(self):
        dialog = ReturnInvoiceDialog(self.current_shift_id, self)
        if dialog.exec_() == QDialog.Accepted:
            order, reason = dialog.get_result()
            if not order:
                return
            confirm = QMessageBox.question(
                self, "تأكيد الاسترجاع",
                f"متأكدة إنك بدك تسترجعي الفاتورة رقم {order['order_number']}\n"
                f"بقيمة {order['total_amount']:.2f}؟\nهاد الإجراء بيرجّع المخزون وما بينعكس بعدين.",
                QMessageBox.Yes | QMessageBox.No
            )
            if confirm != QMessageBox.Yes:
                return
            success, msg = return_order(order["id"], self.current_user["id"], reason)
            if success:
                QMessageBox.information(self, "تم الاسترجاع", msg)
                self.refresh_today_stats()
            else:
                QMessageBox.warning(self, "تعذّر الاسترجاع", msg)

    # ---------------------------------------------------------
    def handle_barcode_scan(self):
        barcode = self.barcode_input.text().strip()
        self.barcode_input.clear()
        if not barcode:
            return
        products = get_product_by_barcode(barcode)
        if not products:
            QMessageBox.warning(self, "غير موجود", f"ما في منتج مرتبط بهاد الباركود:\n{barcode}")
            return

        if len(products) == 1:
            # منتج واحد فقط - يضيفه مباشرة (وإذا عندو خيارات تفتح نافذة الخيارات تلقائياً)
            self.add_to_cart(products[0])
        else:
            # أكثر من منتج بنفس الباركود (مثلاً: دخان أبيض/أحمر، نكهات مختلفة)
            # نعرض قائمة للكاشير يختار منها
            product = self._pick_product_from_list(products, barcode)
            if product:
                self.add_to_cart(product)

    def _pick_product_from_list(self, products, barcode):
        """نافذة اختيار لما يكون في أكثر من منتج بنفس الباركود."""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QListWidget, QListWidgetItem, QPushButton, QLabel, QHBoxLayout
        dlg = QDialog(self)
        dlg.setLayoutDirection(Qt.RightToLeft)
        dlg.setWindowTitle("اختر النوع")
        dlg.setMinimumWidth(320)
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel(f"🔍 باركود: {barcode}\nاختر النوع المطلوب:"))
        lst = QListWidget()
        for p in products:
            item = QListWidgetItem(f"{p['name']}  —  {p['base_price']:.2f}")
            item.setData(Qt.UserRole, p)
            lst.addItem(item)
        lst.setCurrentRow(0)
        lst.itemDoubleClicked.connect(lambda: dlg.accept())
        layout.addWidget(lst)
        btn_row = QHBoxLayout()
        ok_btn = QPushButton("✔ اختيار")
        ok_btn.setObjectName("successBtn")
        ok_btn.clicked.connect(dlg.accept)
        cancel_btn = QPushButton("إلغاء")
        cancel_btn.clicked.connect(dlg.reject)
        btn_row.addWidget(ok_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)
        if dlg.exec_() == QDialog.Accepted and lst.currentItem():
            return lst.currentItem().data(Qt.UserRole)
        return None

    # ---------------------------------------------------------
    def add_to_cart(self, product):
        # لو المنتج متتبَّع الكمية ونافذ من المخزون (أو الكمية المطلوبة أكبر مما تبقى)،
        # نرفض الإضافة للسلة ونبلّغ الكاشير بدل ما نخليه يبيع منتج مش موجود فعلياً
        if product.get("track_quantity"):
            already_in_cart = sum(
                i["quantity"] for i in self.cart if i["product_id"] == product["id"]
            )
            available = (product.get("quantity") or 0) - already_in_cart
            if available <= 0:
                QMessageBox.warning(
                    self, "نفدت الكمية",
                    f"⚠️ لا يوجد كمية متوفرة من \"{product['name']}\" بالمخزون.\n"
                    f"نفدت الكمية من هالمنتج، الرجاء تزويد المخزون أولاً."
                )
                return

        # لو المنتج عندو مجموعات خيارات (نوع/نكهة/حجم...) نفتح نافذة الاختيار أولاً
        option_groups = get_product_options(product["id"])
        extra_price = 0
        options_snapshot = ""
        display_name = product["name"]
        if option_groups:
            dialog = VariantDialog(product, option_groups, self)
            if dialog.exec_() != QDialog.Accepted:
                return
            extra_price, options_snapshot = dialog.get_selection()
            if options_snapshot:
                display_name = f"{product['name']} ({options_snapshot})"

        unit_price = product["base_price"] + extra_price

        # لو نفس المنتج بنفس الخيارات موجود مسبقاً بالسلة، نزيد الكمية فقط
        for item in self.cart:
            if item["product_id"] == product["id"] and item.get("options_snapshot", "") == options_snapshot:
                item["quantity"] += 1
                # BUG-01 FIX: نستخدم _recalc_line_total عشان نحافظ على خصم السطر بعد زيادة الكمية
                self._recalc_line_total(item)
                self.refresh_cart_table()
                return

        self.cart.append({
            "product_id": product["id"],
            "name": display_name,
            "quantity": 1,
            "unit_price": unit_price,
            "options_snapshot": options_snapshot,
            "tax_percent": product.get("tax_percent", 0) or 0,
            "line_total": unit_price,
        })
        self.refresh_cart_table()
        self.focus_barcode_input()

    def open_quick_sale_dialog(self):
        """بيع صنف بدون باركود أو مش مسجّل بالقائمة - بتدخل الاسم والسعر والضريبة يدوياً."""
        dialog = QuickSaleDialog(self)
        if dialog.exec_() != QDialog.Accepted:
            return
        name, price, qty, tax_percent = dialog.get_values()
        if price <= 0:
            QMessageBox.warning(self, "تنبيه", "لازم تدخل سعر أكبر من صفر")
            return
        quick_product_id = get_quick_sale_product()
        self.cart.append({
            "product_id": quick_product_id,
            "name": name,
            "quantity": qty,
            "unit_price": price,
            "options_snapshot": "بيع يدوي",
            "tax_percent": tax_percent,
            "line_total": price * qty,
        })
        self.refresh_cart_table()
        self.focus_barcode_input()

    def show_my_invoices(self):
        orders = get_orders_for_shift(self.current_shift_id, self.current_user["id"])
        dialog = QDialog(self)
        dialog.setLayoutDirection(Qt.RightToLeft)
        dialog.setWindowTitle("🧾 فواتيري اليوم (الشِفت الحالي)")
        dialog.resize(650, 450)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(f"عدد الفواتير: {len(orders)}"))

        table = QTableWidget(len(orders), 5)
        table.setHorizontalHeaderLabels(["رقم الفاتورة", "الوقت", "الزبون", "الإجمالي", "الحالة"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        for i, o in enumerate(orders):
            table.setItem(i, 0, QTableWidgetItem(o["order_number"]))
            table.setItem(i, 1, QTableWidgetItem(o["created_at"]))
            cust = o.get("customer_name") or o.get("customer_phone") or "-"
            table.setItem(i, 2, QTableWidgetItem(cust))
            table.setItem(i, 3, QTableWidgetItem(f"{o['total_amount']:.2f}"))
            table.setItem(i, 4, QTableWidgetItem(o["status"]))
        layout.addWidget(table)

        def show_details():
            row = table.currentRow()
            if row < 0:
                return
            self.show_invoice_details(orders[row]["id"])

        view_btn = QPushButton("عرض تفاصيل الفاتورة المحددة")
        view_btn.clicked.connect(show_details)
        layout.addWidget(view_btn)
        table.doubleClicked.connect(lambda: show_details())

        dialog.exec_()

    def show_invoice_details(self, order_id):
        order = get_order_with_items(order_id)
        if not order:
            return
        lines = [
            f"رقم الفاتورة: {order['order_number']}",
            f"الوقت: {order['created_at']}",
            f"الكاشير: {order['cashier_name']}",
            f"نوع الطلب: {order['order_type']}",
            "-" * 30,
        ]
        for it in order["items"]:
            opt = f" ({it['options_snapshot']})" if it.get("options_snapshot") else ""
            lines.append(f"{it['product_name_snapshot']}{opt} × {it['quantity']} = {it['line_total']:.2f}")
        lines += [
            "-" * 30,
            f"المجموع الفرعي: {order['subtotal']:.2f}",
            f"الخصم: {order['discount_amount']:.2f}",
            f"الضريبة: {order['tax_amount']:.2f}",
            f"الإجمالي: {order['total_amount']:.2f}",
            f"طريقة الدفع: {order['payment_method']}",
        ]
        QMessageBox.information(self, f"تفاصيل الفاتورة {order['order_number']}", "\n".join(lines))

    def remove_selected_item(self):
        row = self.cart_table.currentRow()
        if row >= 0:
            del self.cart[row]
            self.refresh_cart_table()

    def refresh_cart_table(self):
        self.cart_table.setRowCount(len(self.cart))
        for i, item in enumerate(self.cart):
            self.cart_table.setItem(i, 0, QTableWidgetItem(item["name"]))
            self.cart_table.setItem(i, 1, QTableWidgetItem(str(item["quantity"])))
            self.cart_table.setItem(i, 2, QTableWidgetItem(f"{item['unit_price']:.2f}"))
            self.cart_table.setItem(i, 3, QTableWidgetItem(f"{item['line_total']:.2f}"))
        self.update_totals()
        # تحديث زر عرض الفاتورة بعدد الأصناف والإجمالي
        count = len(self.cart)
        total = sum(i["line_total"] for i in self.cart)
        if count > 0:
            self.show_cart_btn.setText(f"🧾 الفاتورة ({count} صنف | {total:.2f})")
            self.show_cart_btn.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold;")
        else:
            self.show_cart_btn.setText("🧾 عرض الفاتورة")
            self.show_cart_btn.setStyleSheet("")
        # تحديث جدول الـ dialog لو كان مفتوح
        if self._cart_dialog and self._cart_dialog.isVisible():
            self._rebuild_cart_dialog_table()

    def update_totals(self):
        subtotal = sum(i["line_total"] for i in self.cart)
        discount_ratio = (self.discount_amount / subtotal) if subtotal > 0 else 0
        tax = 0
        for i in self.cart:
            item_tax_percent = i.get("tax_percent", 0) or 0
            line_after_discount = i["line_total"] * (1 - discount_ratio)
            tax += line_after_discount * (item_tax_percent / 100)
        tax = round(tax, 2)
        taxable = subtotal - self.discount_amount
        total = round(taxable + tax, 2)

        self.subtotal_label.setText(f"المجموع الفرعي: {subtotal:.2f}")
        self.tax_label.setText(f"الضريبة (حسب كل صنف): {tax:.2f}")
        self.total_label.setText(f"الإجمالي: {total:.2f}")
        return subtotal, tax, total

    def apply_discount(self):
        if self.current_user["role"] != "admin":
            QMessageBox.warning(self, "غير مسموح", "الخصم يحتاج صلاحية مدير")
            return
        amount, ok = get_double_input(self, "خصم", "قيمة الخصم:", 0, 0, 10000, 2)
        if ok:
            self.discount_amount = amount
            self.update_totals()

    def clear_cart(self):
        if not self.cart:
            return
        confirm = QMessageBox.question(self, "تأكيد", "هل متأكد من إلغاء الفاتورة الحالية؟")
        if confirm == QMessageBox.Yes:
            self.cart = []
            self.discount_amount = 0
            self.refresh_cart_table()
            if self._cart_dialog and self._cart_dialog.isVisible():
                self._cart_dialog.close()

    # ---------------------------------------------------------
    def checkout(self, payment_method):
        if not self.cart:
            QMessageBox.warning(self, "تنبيه", "السلة فاضية")
            return

        subtotal, tax, total = self.update_totals()
        order_type = self.order_type_combo.currentText()

        amount_tendered = total  # دفع شبكة = بالمظبوط دايماً
        if payment_method == "كاش":
            amount_tendered, ok = get_double_input(
                self, "المبلغ المستلم من الزبون",
                f"الإجمالي المطلوب: {total:.2f}\nقديش عطاك الزبون؟",
                total, 0, 100000, 2
            )
            if not ok:
                return
            if amount_tendered < total:
                QMessageBox.warning(
                    self, "تنبيه",
                    f"المبلغ المستلم ({amount_tendered:.2f}) أقل من الإجمالي ({total:.2f})"
                )
                return

        cash_paid = total if payment_method == "كاش" else 0
        card_paid = total if payment_method == "شبكة" else 0

        customer_id = get_or_create_customer(
            self.customer_name_input.text(), self.customer_phone_input.text()
        )

        order_id, order_number, total_amount, change_due = create_order(
            shift_id=self.current_shift_id,
            user_id=self.current_user["id"],
            items=self.cart,
            discount_amount=self.discount_amount,
            payment_method=payment_method,
            cash_paid=cash_paid,
            card_paid=card_paid,
            order_type=order_type,
            customer_id=customer_id,
            amount_tendered=amount_tendered,
        )

        summary = (
            f"✅ تم إتمام الفاتورة رقم {order_number}\n"
            f"الإجمالي: {total_amount:.2f}"
        )
        if payment_method == "كاش":
            summary += f"\nالمبلغ المستلم: {amount_tendered:.2f}"
            summary += f"\nالباقي للزبون: {change_due:.2f}"

        QMessageBox.information(self, "تمت العملية", summary)
        self._last_order_id = order_id  # لإعادة الطباعة السريعة بـ F10

        # فتح درج الكاش تلقائياً بعد كل عملية دفع كاش (مش عند الدفع بالشبكة)
        if payment_method == "كاش":
            open_cash_drawer(
                printer_port=get_setting("printer_port", "") or None,
                printer_name=get_setting("printer_name", "") or None,
            )

        # طباعة الإيصال (وضع محاكاة تلقائياً لو ما في طابعة متصلة بعد)
        order_data = get_order_with_items(order_id)
        if order_data:
            store_name = get_setting("store_name", "love.jo")
            footer = get_setting("receipt_footer", "شكراً لزيارتكم")
            success, msg = print_receipt(
                order_data, store_name=store_name,
                tax_percent=float(get_setting("tax_percent", "16")), footer=footer,
                printer_port=get_setting("printer_port", "") or None,
                printer_name=get_setting("printer_name", "") or None,
            )
            if not success:
                QMessageBox.warning(self, "تنبيه طباعة", msg)

        self.cart = []
        self.discount_amount = 0
        self.customer_name_input.clear()
        self.customer_phone_input.clear()
        self.refresh_cart_table()
        self.refresh_today_stats()
        # إغلاق نافذة الفاتورة بعد إتمام الدفع تلقائياً
        if self._cart_dialog and self._cart_dialog.isVisible():
            self._cart_dialog.close()
        self.focus_barcode_input()
