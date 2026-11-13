# -*- coding: utf-8 -*-
"""شاشة التقارير (للمدير) - تقرير يومي وشهري."""

from datetime import date, datetime
from utils.time_utils import jordan_today

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                              QTableWidget, QTableWidgetItem, QHeaderView, QDateEdit,
                              QTabWidget, QFrame, QSpinBox, QGridLayout,
                              QMessageBox, QDialog, QFileDialog, QCheckBox, QComboBox)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QColor

from database.data_access import (get_daily_report, get_monthly_report,
                                   get_order_with_items,
                                   get_inventory_report, get_inventory_sales_report,
                                   get_profit_loss_report,
                                   get_shifts_report, get_shift_detail, get_categories,
                                   purge_all_transactions)
from utils.excel_export import export_rows_to_excel

STOCK_COLORS = {
    "green": QColor("#d4edda"),
    "yellow": QColor("#fff3cd"),
    "red": QColor("#f8d7da"),
}


def _pick_save_path(parent, default_name):
    path, _ = QFileDialog.getSaveFileName(parent, "حفظ التقرير", default_name, "Excel (*.xlsx)")
    return path


def _today_qdate():
    """
    تاريخ اليوم كـ QDate - مثبّت على توقيت الأردن (UTC+3) مباشرة.
    نستخدم jordan_today() بدل date.today() أو QDate.currentDate() عشان نضمن
    إن التاريخ صح بغض النظر عن إعداد توقيت الكمبيوتر أو إعدادات Qt.
    """
    t = jordan_today()
    return QDate(t.year, t.month, t.day)


class StatCard(QFrame):
    def __init__(self, title):
        super().__init__()
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        self.title_label = QLabel(title)
        self.value_label = QLabel("--")
        self.value_label.setObjectName("totalLabel")
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)

    def set_value(self, value):
        self.value_label.setText(str(value))


class ReportsScreen(QWidget):
    def __init__(self, current_user, on_back):
        super().__init__()
        self.current_user = current_user
        self.on_back = on_back
        self.setLayoutDirection(Qt.RightToLeft)
        self.init_ui()

    def init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)

        header = QHBoxLayout()
        title = QLabel("📊 التقارير")
        title.setObjectName("titleLabel")
        header.addWidget(title)
        header.addStretch()
        purge_btn = QPushButton("🗑️ مسح بيانات التست")
        purge_btn.setStyleSheet(
            "QPushButton { background-color: #dc3545; color: white; font-weight: bold; "
            "padding: 6px 14px; border-radius: 6px; }"
            "QPushButton:hover { background-color: #b02a37; }"
        )
        purge_btn.clicked.connect(self.confirm_purge_test_data)
        header.addWidget(purge_btn)

        back_btn = QPushButton("⬅ رجوع")
        back_btn.clicked.connect(self.on_back)
        header.addWidget(back_btn)
        outer.addLayout(header)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_daily_tab(), "تقرير يومي")
        self.tabs.addTab(self._build_monthly_tab(), "تقرير شهري")
        self.tabs.addTab(self._build_shifts_tab(), "🕐 تقرير الشِفتات")
        self.tabs.addTab(self._build_inventory_tab(), "📦 تقرير المخزون")
        self.tabs.addTab(self._build_inventory_sales_tab(), "📊 مبيعات المخزون")
        self.tabs.addTab(self._build_profit_loss_tab(), "💰 ربح/خسارة")
        # تحديث تلقائي للتقرير كل ما ينتقل المستخدم لتبويب
        self.tabs.currentChanged.connect(self._refresh_current_tab)
        outer.addWidget(self.tabs)

    # ---------------------------------------------------------
    def _refresh_current_tab(self, index):
        """يعيد تحميل بيانات التبويب اللي انتقلنا له بالفلاتر الحالية - حتى تنعكس أي
        عملية بيع/إرجاع/إقفال شِفت جديدة فوراً من غير ما نضطر نداس "عرض التقرير" يدوياً."""
        refresh_map = {
            0: self.load_daily_report,
            1: self.load_monthly_report,
            2: self.load_shifts_report,
            3: self.load_inventory_report,
            4: self.load_inventory_sales_report,
            5: self.load_profit_loss_report,
        }
        func = refresh_map.get(index)
        if func:
            func()

    def confirm_purge_test_data(self):
        """يسأل المستخدم مرتين قبل مسح بيانات التست"""
        msg1 = QMessageBox(self)
        msg1.setWindowTitle("⚠️ تحذير")
        msg1.setText(
            "هاد الإجراء سيمسح نهائياً:\n\n"
            "• جميع الفواتير والطلبات\n"
            "• جميع المناوبات (الشِفتات)\n"
            "• المصاريف والمشتريات\n"
            "• حركات المخزون\n"
            "• سجل النشاطات\n\n"
            "المنتجات والمستخدمين والإعدادات ستبقى كما هي.\n\n"
            "هل أنت متأكد؟"
        )
        msg1.setIcon(QMessageBox.Warning)
        msg1.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
        msg1.setDefaultButton(QMessageBox.Cancel)
        msg1.button(QMessageBox.Yes).setText("نعم، تابع")
        msg1.button(QMessageBox.Cancel).setText("إلغاء")
        if msg1.exec_() != QMessageBox.Yes:
            return

        msg2 = QMessageBox(self)
        msg2.setWindowTitle("تأكيد نهائي")
        msg2.setText("لا يمكن التراجع عن هذا الإجراء.\n\nهل تريد المتابعة؟")
        msg2.setIcon(QMessageBox.Critical)
        msg2.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
        msg2.setDefaultButton(QMessageBox.Cancel)
        msg2.button(QMessageBox.Yes).setText("نعم، امسح البيانات")
        msg2.button(QMessageBox.Cancel).setText("إلغاء")
        if msg2.exec_() != QMessageBox.Yes:
            return

        ok, msg = purge_all_transactions(self.current_user["id"])
        if ok:
            QMessageBox.information(self, "تم", msg)
            self._refresh_current_tab(self.tabs.currentIndex())
        else:
            QMessageBox.critical(self, "خطأ", msg)

    def _build_daily_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        controls = QHBoxLayout()
        self.daily_date = QDateEdit(_today_qdate())
        self.daily_date.setCalendarPopup(True)
        controls.addWidget(QLabel("التاريخ:"))
        controls.addWidget(self.daily_date)
        run_btn = QPushButton("عرض التقرير")
        run_btn.clicked.connect(self.load_daily_report)
        controls.addWidget(run_btn)
        export_btn = QPushButton("📤 تصدير Excel")
        export_btn.clicked.connect(self.export_daily_report)
        controls.addWidget(export_btn)
        controls.addStretch()
        layout.addLayout(controls)

        cards_row = QHBoxLayout()
        self.card_orders = StatCard("عدد الفواتير")
        self.card_sales = StatCard("إجمالي المبيعات")
        self.card_tax = StatCard("إجمالي الضريبة")
        self.card_discount = StatCard("إجمالي الخصومات")
        for c in (self.card_orders, self.card_sales, self.card_tax, self.card_discount):
            cards_row.addWidget(c)
        layout.addLayout(cards_row)

        layout.addWidget(QLabel("الأكثر مبيعاً:"))
        self.top_products_table = QTableWidget()
        self.top_products_table.setColumnCount(3)
        self.top_products_table.setHorizontalHeaderLabels(["المنتج", "الكمية", "الإجمالي"])
        self.top_products_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.top_products_table.verticalHeader().setVisible(False)
        self.top_products_table.setAlternatingRowColors(True)
        self.top_products_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.top_products_table.setMaximumHeight(180)
        layout.addWidget(self.top_products_table)

        layout.addWidget(QLabel("📋 فواتير اليوم - دبل كليك لعرض التفاصيل:"))
        self.daily_orders_table = QTableWidget()
        self.daily_orders_table.setColumnCount(5)
        self.daily_orders_table.setHorizontalHeaderLabels(
            ["رقم الفاتورة", "الوقت", "الزبون", "الضريبة", "الإجمالي"])
        self.daily_orders_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.daily_orders_table.verticalHeader().setVisible(False)
        self.daily_orders_table.setAlternatingRowColors(True)
        self.daily_orders_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.daily_orders_table.doubleClicked.connect(self.show_daily_order_details)
        layout.addWidget(self.daily_orders_table)

        self._daily_orders = []
        self.load_daily_report()
        return widget

    def load_daily_report(self):
        # نبني date_str من Python مباشرة بدل toString() عشان نتجنب مشاكل locale ويندوز
        qd = self.daily_date.date()
        date_str = f"{qd.year():04d}-{qd.month():02d}-{qd.day():02d}"
        report = get_daily_report(date_str)
        self.card_orders.set_value(report["orders_count"])
        self.card_sales.set_value(f"{report['total_sales']:.2f}")
        self.card_tax.set_value(f"{report['total_tax']:.2f}")
        self.card_discount.set_value(f"{report['total_discount']:.2f}")

        products = report["top_products"]
        self.top_products_table.setRowCount(len(products))
        for row, p in enumerate(products):
            self.top_products_table.setItem(row, 0, QTableWidgetItem(p["product_name_snapshot"]))
            self.top_products_table.setItem(row, 1, QTableWidgetItem(str(p["total_qty"])))
            self.top_products_table.setItem(row, 2, QTableWidgetItem(f"{p['total_amount']:.2f}"))

        self._daily_orders = report["orders"]
        self.daily_orders_table.setRowCount(len(self._daily_orders))
        for row, o in enumerate(self._daily_orders):
            self.daily_orders_table.setItem(row, 0, QTableWidgetItem(o["order_number"]))
            self.daily_orders_table.setItem(row, 1, QTableWidgetItem(o["created_at"]))
            cust = o.get("customer_name") or o.get("customer_phone") or "-"
            self.daily_orders_table.setItem(row, 2, QTableWidgetItem(cust))
            self.daily_orders_table.setItem(row, 3, QTableWidgetItem(f"{o['tax_amount']:.2f}"))
            self.daily_orders_table.setItem(row, 4, QTableWidgetItem(f"{o['total_amount']:.2f}"))

    def export_daily_report(self):
        qd = self.daily_date.date()
        date_str = f"{qd.year():04d}-{qd.month():02d}-{qd.day():02d}"
        path = _pick_save_path(self, f"تقرير_يومي_{date_str}.xlsx")
        if not path:
            return
        report = get_daily_report(date_str)
        headers = ["رقم الفاتورة", "الوقت", "الزبون", "الضريبة", "الإجمالي"]
        rows = [
            (o["order_number"], o["created_at"],
             o.get("customer_name") or o.get("customer_phone") or "-",
             o["tax_amount"], o["total_amount"])
            for o in report["orders"]
        ]
        summary = [
            ("التاريخ", report["date"]), ("عدد الفواتير", report["orders_count"]),
            ("إجمالي المبيعات", report["total_sales"]), ("إجمالي الضريبة", report["total_tax"]),
            ("إجمالي الخصومات", report["total_discount"]),
        ]
        success, msg = export_rows_to_excel(path, "تقرير يومي", headers, rows, summary)
        (QMessageBox.information if success else QMessageBox.warning)(self, "تصدير Excel", msg)

    def show_daily_order_details(self):
        row = self.daily_orders_table.currentRow()
        if row < 0 or row >= len(self._daily_orders):
            return
        self._show_order_details_dialog(self._daily_orders[row]["id"])

    def _show_order_details_dialog(self, order_id):
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
            tax_note = f" [ضريبة {it['tax_percent']:.1f}%: {it['tax_amount']:.2f}]" if it.get("tax_percent") else ""
            lines.append(f"{it['product_name_snapshot']}{opt} × {it['quantity']} = {it['line_total']:.2f}{tax_note}")
        lines += [
            "-" * 30,
            f"المجموع الفرعي: {order['subtotal']:.2f}",
            f"الخصم: {order['discount_amount']:.2f}",
            f"إجمالي الضريبة: {order['tax_amount']:.2f}",
            f"الإجمالي: {order['total_amount']:.2f}",
            f"طريقة الدفع: {order['payment_method']}",
        ]
        QMessageBox.information(self, f"تفاصيل الفاتورة {order['order_number']}", "\n".join(lines))

    # ---------------------------------------------------------
    def _build_monthly_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        controls = QHBoxLayout()
        self.month_spin = QSpinBox()
        self.month_spin.setRange(1, 12)
        # BUG-05 FIX: كان يستخدم date.today() = توقيت الجهاز، الآن jordan_today() = UTC+3
        _today = jordan_today()
        self.month_spin.setValue(_today.month)
        self.year_spin = QSpinBox()
        self.year_spin.setRange(2020, 2100)
        self.year_spin.setValue(_today.year)
        controls.addWidget(QLabel("الشهر:"))
        controls.addWidget(self.month_spin)
        controls.addWidget(QLabel("السنة:"))
        controls.addWidget(self.year_spin)

        self.month_day_from_spin = QSpinBox()
        self.month_day_from_spin.setRange(1, 31)
        self.month_day_from_spin.setValue(1)
        self.month_day_to_spin = QSpinBox()
        self.month_day_to_spin.setRange(1, 31)
        self.month_day_to_spin.setValue(31)
        controls.addWidget(QLabel("من يوم:"))
        controls.addWidget(self.month_day_from_spin)
        controls.addWidget(QLabel("إلى يوم:"))
        controls.addWidget(self.month_day_to_spin)

        self.month_spin.valueChanged.connect(self._update_month_day_range)
        self.year_spin.valueChanged.connect(self._update_month_day_range)

        run_btn = QPushButton("عرض التقرير")
        run_btn.clicked.connect(self.load_monthly_report)
        controls.addWidget(run_btn)
        export_btn = QPushButton("📤 تصدير Excel")
        export_btn.clicked.connect(self.export_monthly_report)
        controls.addWidget(export_btn)
        controls.addStretch()
        layout.addLayout(controls)

        cards_row = QHBoxLayout()
        self.month_card_orders = StatCard("عدد الفواتير")
        self.month_card_sales = StatCard("إجمالي المبيعات")
        cards_row.addWidget(self.month_card_orders)
        cards_row.addWidget(self.month_card_sales)
        layout.addLayout(cards_row)

        layout.addWidget(QLabel("📋 فواتير الشهر - دبل كليك لعرض التفاصيل:"))
        self.month_orders_table = QTableWidget()
        self.month_orders_table.setColumnCount(5)
        self.month_orders_table.setHorizontalHeaderLabels(
            ["رقم الفاتورة", "الوقت", "الزبون", "الضريبة", "الإجمالي"])
        self.month_orders_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.month_orders_table.verticalHeader().setVisible(False)
        self.month_orders_table.setAlternatingRowColors(True)
        self.month_orders_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.month_orders_table.doubleClicked.connect(self.show_month_order_details)
        layout.addWidget(self.month_orders_table)

        self._month_orders = []
        self._update_month_day_range()
        self.load_monthly_report()
        return widget

    def _update_month_day_range(self):
        """يحدّث الحد الأقصى ليوم 'من/إلى' حسب عدد أيام الشهر المختار (بيتغيّر مثلاً بين 28 و31)."""
        import calendar
        last_day = calendar.monthrange(self.year_spin.value(), self.month_spin.value())[1]
        for spin in (self.month_day_from_spin, self.month_day_to_spin):
            spin.blockSignals(True)
            if spin.value() > last_day:
                spin.setValue(last_day)
            spin.setMaximum(last_day)
            spin.blockSignals(False)

    def load_monthly_report(self):
        report = get_monthly_report(
            self.year_spin.value(), self.month_spin.value(),
            self.month_day_from_spin.value(), self.month_day_to_spin.value()
        )
        self.month_card_orders.set_value(report["orders_count"])
        self.month_card_sales.set_value(f"{report['total_sales']:.2f}")

        self._month_orders = report["orders"]
        self.month_orders_table.setRowCount(len(self._month_orders))
        for row, o in enumerate(self._month_orders):
            self.month_orders_table.setItem(row, 0, QTableWidgetItem(o["order_number"]))
            self.month_orders_table.setItem(row, 1, QTableWidgetItem(o["created_at"]))
            cust = o.get("customer_name") or o.get("customer_phone") or "-"
            self.month_orders_table.setItem(row, 2, QTableWidgetItem(cust))
            self.month_orders_table.setItem(row, 3, QTableWidgetItem(f"{o['tax_amount']:.2f}"))
            self.month_orders_table.setItem(row, 4, QTableWidgetItem(f"{o['total_amount']:.2f}"))

    def export_monthly_report(self):
        year, month = self.year_spin.value(), self.month_spin.value()
        day_from, day_to = self.month_day_from_spin.value(), self.month_day_to_spin.value()
        path = _pick_save_path(self, f"تقرير_شهري_{year}-{month:02d}_من_{day_from}_الى_{day_to}.xlsx")
        if not path:
            return
        report = get_monthly_report(year, month, day_from, day_to)
        headers = ["رقم الفاتورة", "الوقت", "الزبون", "الضريبة", "الإجمالي"]
        rows = [
            (o["order_number"], o["created_at"],
             o.get("customer_name") or o.get("customer_phone") or "-",
             o["tax_amount"], o["total_amount"])
            for o in report["orders"]
        ]
        summary = [("الشهر", report["month"]),
                   ("من يوم", report["day_from"]), ("إلى يوم", report["day_to"]),
                   ("عدد الفواتير", report["orders_count"]),
                   ("إجمالي المبيعات", report["total_sales"])]
        success, msg = export_rows_to_excel(path, "تقرير شهري", headers, rows, summary)
        (QMessageBox.information if success else QMessageBox.warning)(self, "تصدير Excel", msg)

    def show_month_order_details(self):
        row = self.month_orders_table.currentRow()
        if row < 0 or row >= len(self._month_orders):
            return
        self._show_order_details_dialog(self._month_orders[row]["id"])

    # ---------------------------------------------------------
    # تقرير الشِفتات - كل شِفت على حدا مع تفاصيله الكاملة
    def _build_shifts_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # ---- صف الفلاتر ----
        controls = QHBoxLayout()
        self.shifts_from_date = QDateEdit(_today_qdate().addDays(-7))
        self.shifts_from_date.setCalendarPopup(True)
        self.shifts_to_date = QDateEdit(_today_qdate())
        self.shifts_to_date.setCalendarPopup(True)
        controls.addWidget(QLabel("من:"))
        controls.addWidget(self.shifts_from_date)
        controls.addWidget(QLabel("إلى:"))
        controls.addWidget(self.shifts_to_date)
        run_btn = QPushButton("عرض التقرير")
        run_btn.clicked.connect(self.load_shifts_report)
        controls.addWidget(run_btn)
        export_btn = QPushButton("📤 تصدير Excel")
        export_btn.clicked.connect(self.export_shifts_report)
        controls.addWidget(export_btn)
        controls.addStretch()
        layout.addLayout(controls)

        # ---- بطاقات ملخص الفترة ----
        cards_row = QHBoxLayout()
        self.shifts_card_count = StatCard("عدد الشِفتات")
        self.shifts_card_sales = StatCard("إجمالي المبيعات")
        self.shifts_card_cash = StatCard("إجمالي كاش")
        self.shifts_card_network = StatCard("إجمالي شبكة")
        for c in (self.shifts_card_count, self.shifts_card_sales,
                  self.shifts_card_cash, self.shifts_card_network):
            cards_row.addWidget(c)
        layout.addLayout(cards_row)

        # ---- جدول الشِفتات ----
        layout.addWidget(QLabel("📋 الشِفتات - دبل كليك لعرض تفاصيل الشِفت وكل فواتيره:"))
        self.shifts_table = QTableWidget()
        self.shifts_table.setColumnCount(10)
        self.shifts_table.setHorizontalHeaderLabels([
            "رقم الشِفت", "الكاشير (ماسك الشِفت)", "بداية الشِفت", "نهاية الشِفت",
            "كاش افتتاحي", "عدد الفواتير", "إجمالي كاش", "إجمالي شبكة", "المجموع", "فرق الكاش"
        ])
        self.shifts_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.shifts_table.verticalHeader().setVisible(False)
        self.shifts_table.setAlternatingRowColors(True)
        self.shifts_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.shifts_table.doubleClicked.connect(self.show_shift_detail)
        layout.addWidget(self.shifts_table)

        self._shifts_data = []
        self.load_shifts_report()
        return widget

    def load_shifts_report(self):
        qf = self.shifts_from_date.date()
        qt = self.shifts_to_date.date()
        date_from = f"{qf.year():04d}-{qf.month():02d}-{qf.day():02d}"
        date_to = f"{qt.year():04d}-{qt.month():02d}-{qt.day():02d}"
        self._shifts_data = get_shifts_report(date_from, date_to)

        total_sales = sum(s["total_sales"] for s in self._shifts_data)
        total_cash = sum(s["cash_total"] for s in self._shifts_data)
        total_network = sum(s["network_total"] for s in self._shifts_data)

        self.shifts_card_count.set_value(len(self._shifts_data))
        self.shifts_card_sales.set_value(f"{total_sales:.2f}")
        self.shifts_card_cash.set_value(f"{total_cash:.2f}")
        self.shifts_card_network.set_value(f"{total_network:.2f}")

        self.shifts_table.setRowCount(len(self._shifts_data))
        for row, s in enumerate(self._shifts_data):
            diff = s.get("cash_difference") or 0
            # لون الصف حسب فرق الكاش
            if diff < -0.01:
                row_color = QColor("#f8d7da")   # أحمر = ناقص
            elif diff > 0.01:
                row_color = QColor("#fff3cd")   # أصفر = زيادة
            else:
                row_color = QColor("#d4edda")   # أخضر = مضبوط

            items = [
                str(s["id"]),
                s["cashier_name"],
                s["started_at"],
                s["ended_at"] or "مفتوح",
                f"{s.get('opening_cash', 0):.2f}",
                str(s.get("orders_count", "-")),
                f"{s['cash_total']:.2f}",
                f"{s['network_total']:.2f}",
                f"{s['total_sales']:.2f}",
                f"{diff:+.2f}" if s.get("ended_at") else "-",
            ]
            for col, text in enumerate(items):
                item = QTableWidgetItem(text)
                item.setBackground(row_color)
                self.shifts_table.setItem(row, col, item)

    def show_shift_detail(self):
        row = self.shifts_table.currentRow()
        if row < 0 or row >= len(self._shifts_data):
            return
        shift_id = self._shifts_data[row]["id"]
        detail = get_shift_detail(shift_id)
        if not detail:
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(f"تفاصيل الشِفت #{shift_id}")
        dlg.setLayoutDirection(Qt.RightToLeft)
        dlg.resize(820, 600)
        layout = QVBoxLayout(dlg)

        s = detail["shift"]
        sm = detail["summary"]

        # ---- معلومات الشِفت ----
        info_frame = QFrame()
        info_frame.setObjectName("card")
        info_layout = QGridLayout(info_frame)
        info_layout.addWidget(QLabel(f"الكاشير: {s['cashier_name']}"), 0, 0)
        info_layout.addWidget(QLabel(f"بداية الشِفت: {s['started_at']}"), 0, 1)
        info_layout.addWidget(QLabel(f"نهاية الشِفت: {s['ended_at'] or 'مفتوح'}"), 0, 2)
        info_layout.addWidget(QLabel(f"كاش افتتاحي: {s['opening_cash']:.2f}"), 1, 0)
        info_layout.addWidget(QLabel(f"كاش متوقع: {s['closing_cash_expected']:.2f}" if s.get('closing_cash_expected') is not None else "كاش متوقع: -"), 1, 1)
        info_layout.addWidget(QLabel(f"كاش فعلي: {s['closing_cash_actual']:.2f}" if s.get('closing_cash_actual') is not None else "كاش فعلي: -"), 1, 2)
        layout.addWidget(info_frame)

        # ---- بطاقات الملخص ----
        summary_row = QHBoxLayout()
        for title, val in [
            ("عدد الفواتير", str(sm["orders_count"])),
            ("إجمالي المبيعات", f"{sm['total_sales']:.2f}"),
            ("إجمالي كاش", f"{sm['cash_total']:.2f}"),
            ("إجمالي شبكة", f"{sm['network_total']:.2f}"),
            ("الخصومات", f"{sm['total_discount']:.2f}"),
        ]:
            c = StatCard(title)
            c.set_value(val)
            summary_row.addWidget(c)

        diff = s.get("cash_difference")
        if diff is not None:
            diff_card = StatCard("فرق الكاش")
            diff_card.set_value(f"{diff:+.2f}")
            if diff < -0.01:
                diff_card.setStyleSheet("background:#f8d7da; border-radius:8px;")
            elif diff > 0.01:
                diff_card.setStyleSheet("background:#fff3cd; border-radius:8px;")
            else:
                diff_card.setStyleSheet("background:#d4edda; border-radius:8px;")
            summary_row.addWidget(diff_card)
        layout.addLayout(summary_row)

        # ---- جدول الفواتير ----
        layout.addWidget(QLabel("📋 كل فواتير الشِفت:"))
        tbl = QTableWidget()
        tbl.setColumnCount(7)
        tbl.setHorizontalHeaderLabels(["رقم الفاتورة", "الوقت", "طريقة الدفع",
                                        "كاش", "شبكة", "خصم", "الإجمالي"])
        tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        tbl.verticalHeader().setVisible(False)
        tbl.setAlternatingRowColors(True)
        tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        tbl.setLayoutDirection(Qt.RightToLeft)

        STATUS_COLORS = {
            "ملغاة": QColor("#f8d7da"),
            "مرتجعة": QColor("#fff3cd"),
        }
        orders = detail["orders"]
        tbl.setRowCount(len(orders))
        for r, o in enumerate(orders):
            color = STATUS_COLORS.get(o["status"])
            row_items = [
                o["order_number"],
                o["created_at"],
                f"{o['payment_method']} {'⛔' if o['status'] == 'ملغاة' else '↩' if o['status'] == 'مرتجعة' else ''}",
                f"{o['cash_paid']:.2f}",
                f"{o['card_paid']:.2f}",
                f"{o['discount_amount']:.2f}",
                f"{o['total_amount']:.2f}",
            ]
            for col, text in enumerate(row_items):
                item = QTableWidgetItem(text)
                if color:
                    item.setBackground(color)
                tbl.setItem(r, col, item)

        layout.addWidget(tbl)

        close_btn = QPushButton("إغلاق")
        close_btn.clicked.connect(dlg.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignLeft)
        dlg.exec_()

    def export_shifts_report(self):
        if not self._shifts_data:
            return
        qf = self.shifts_from_date.date()
        qt = self.shifts_to_date.date()
        date_from = f"{qf.year():04d}-{qf.month():02d}-{qf.day():02d}"
        date_to = f"{qt.year():04d}-{qt.month():02d}-{qt.day():02d}"
        path = _pick_save_path(self, f"تقرير_شِفتات_{date_from}_إلى_{date_to}.xlsx")
        if not path:
            return
        headers = ["رقم الشِفت", "الكاشير (ماسك الشِفت)", "بداية الشِفت", "نهاية الشِفت",
                   "كاش افتتاحي", "عدد الفواتير", "إجمالي كاش", "إجمالي شبكة", "المجموع", "فرق الكاش"]
        rows = []
        for s in self._shifts_data:
            diff = s.get("cash_difference")
            rows.append((
                s["id"], s["cashier_name"], s["started_at"],
                s["ended_at"] or "مفتوح",
                s.get("opening_cash", 0),
                s.get("orders_count", 0),
                s["cash_total"], s["network_total"], s["total_sales"],
                f"{diff:+.2f}" if diff is not None else "-",
            ))
        summary = [
            ("من", date_from), ("إلى", date_to),
            ("عدد الشِفتات", len(self._shifts_data)),
            ("إجمالي المبيعات", sum(s["total_sales"] for s in self._shifts_data)),
            ("إجمالي كاش", sum(s["cash_total"] for s in self._shifts_data)),
            ("إجمالي شبكة", sum(s["network_total"] for s in self._shifts_data)),
        ]
        success, msg = export_rows_to_excel(path, "تقرير الشِفتات", headers, rows, summary)
        (QMessageBox.information if success else QMessageBox.warning)(self, "تصدير Excel", msg)

    # تقرير المخزون (كميات) - منفصل تماماً عن تقارير البيع، للمدير فقط
    def _build_inventory_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        controls = QHBoxLayout()
        refresh_btn = QPushButton("🔄 تحديث")
        refresh_btn.clicked.connect(self.load_inventory_report)
        controls.addWidget(refresh_btn)
        export_btn = QPushButton("📤 تصدير Excel")
        export_btn.clicked.connect(self.export_inventory_report)
        controls.addWidget(export_btn)
        controls.addWidget(QLabel("الفئة:"))
        self.inv_category_filter = QComboBox()
        self.inv_category_filter.addItem("كل الفئات", None)
        for cat in get_categories(active_only=False):
            self.inv_category_filter.addItem(cat["name"], cat["id"])
        controls.addWidget(self.inv_category_filter)
        controls.addStretch()
        layout.addLayout(controls)

        cards_row = QHBoxLayout()
        self.inv_card_total_qty = StatCard("إجمالي الكمية الحالية")
        self.inv_card_products_count = StatCard("عدد المنتجات")
        self.inv_card_total_sale = StatCard("مجموع إجمالي البيع")
        cards_row.addWidget(self.inv_card_total_qty)
        cards_row.addWidget(self.inv_card_products_count)
        cards_row.addWidget(self.inv_card_total_sale)
        cards_row.addStretch()
        layout.addLayout(cards_row)

        layout.addWidget(QLabel("مجموع الكمية حسب الفئة:"))
        self.inv_category_summary_table = QTableWidget()
        self.inv_category_summary_table.setColumnCount(3)
        self.inv_category_summary_table.setHorizontalHeaderLabels(
            ["الفئة", "عدد المنتجات", "إجمالي الكمية"])
        self.inv_category_summary_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.inv_category_summary_table.verticalHeader().setVisible(False)
        self.inv_category_summary_table.setAlternatingRowColors(True)
        self.inv_category_summary_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.inv_category_summary_table.setMaximumHeight(180)
        layout.addWidget(self.inv_category_summary_table)

        self.inventory_table = QTableWidget()
        self.inventory_table.setColumnCount(7)
        self.inventory_table.setHorizontalHeaderLabels(
            ["المنتج", "الفئة", "الكمية الحالية", "الحالة", "سعر التكلفة", "سعر البيع", "إجمالي البيع"])
        self.inventory_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.inventory_table.verticalHeader().setVisible(False)
        self.inventory_table.setAlternatingRowColors(True)
        self.inventory_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.inventory_table)

        self._inventory_rows = []
        self.inv_category_filter.currentIndexChanged.connect(self.load_inventory_report)
        self.load_inventory_report()
        return widget

    def load_inventory_report(self):
        all_rows = get_inventory_report()
        selected_cat_id = self.inv_category_filter.currentData()
        if selected_cat_id is not None:
            self._inventory_rows = [p for p in all_rows if p["category_id"] == selected_cat_id]
        else:
            self._inventory_rows = all_rows
        self.inventory_table.setRowCount(len(self._inventory_rows))
        total_qty = sum(p["quantity"] for p in self._inventory_rows)
        total_sale_sum = sum((p.get("base_price", 0) or 0) * p["quantity"] for p in self._inventory_rows)
        self.inv_card_total_qty.set_value(f"{total_qty:.0f}")
        self.inv_card_products_count.set_value(str(len(self._inventory_rows)))
        self.inv_card_total_sale.set_value(f"{total_sale_sum:.2f}")

        # جدول ملخص مجموع الكمية حسب كل فئة (دايمًا على أساس كل المنتجات، بغض النظر عن الفلتر)
        by_category = {}
        for p in all_rows:
            key = p["category_name"]
            if key not in by_category:
                by_category[key] = {"count": 0, "total_qty": 0}
            by_category[key]["count"] += 1
            by_category[key]["total_qty"] += p["quantity"]
        cat_names_sorted = sorted(by_category.keys(), key=lambda k: by_category[k]["total_qty"], reverse=True)
        self.inv_category_summary_table.setRowCount(len(cat_names_sorted))
        for row, cat_name in enumerate(cat_names_sorted):
            data = by_category[cat_name]
            self.inv_category_summary_table.setItem(row, 0, QTableWidgetItem(cat_name))
            self.inv_category_summary_table.setItem(row, 1, QTableWidgetItem(str(data["count"])))
            self.inv_category_summary_table.setItem(row, 2, QTableWidgetItem(f"{data['total_qty']:.0f}"))

        status_text = {"green": "🟢 متوفر", "yellow": "🟡 قرب النفاذ", "red": "🔴 نافذ"}
        for row, p in enumerate(self._inventory_rows):
            color = STOCK_COLORS.get(p["stock_color"])
            name_item = QTableWidgetItem(p["name"])
            cat_item = QTableWidgetItem(p["category_name"])
            qty_item = QTableWidgetItem(f"{p['quantity']:.0f}")
            status_item = QTableWidgetItem(status_text.get(p["stock_color"], "-"))
            cost_item = QTableWidgetItem(f"{p['cost_price']:.2f}")
            sell_price = p.get("base_price", 0) or 0
            total_sale = sell_price * p["quantity"]
            sell_item = QTableWidgetItem(f"{sell_price:.2f}")
            total_item = QTableWidgetItem(f"{total_sale:.2f}")
            for it in (name_item, cat_item, qty_item, status_item, cost_item, sell_item, total_item):
                if color:
                    it.setBackground(color)
            self.inventory_table.setItem(row, 0, name_item)
            self.inventory_table.setItem(row, 1, cat_item)
            self.inventory_table.setItem(row, 2, qty_item)
            self.inventory_table.setItem(row, 3, status_item)
            self.inventory_table.setItem(row, 4, cost_item)
            self.inventory_table.setItem(row, 5, sell_item)
            self.inventory_table.setItem(row, 6, total_item)

    def export_inventory_report(self):
        selected_cat_id = self.inv_category_filter.currentData()
        cat_name = self.inv_category_filter.currentText() if selected_cat_id is not None else "الكل"
        path = _pick_save_path(self, f"تقرير_المخزون_{cat_name}.xlsx")
        if not path:
            return
        status_text = {"green": "متوفر", "yellow": "قرب النفاذ", "red": "نافذ"}
        headers = ["المنتج", "الفئة", "الكمية الحالية", "الحالة", "سعر التكلفة", "سعر البيع", "إجمالي البيع"]
        rows = [
            (p["name"], p["category_name"], p["quantity"], status_text.get(p["stock_color"], "-"),
             p["cost_price"], p.get("base_price", 0) or 0,
             (p.get("base_price", 0) or 0) * p["quantity"])
            for p in self._inventory_rows
        ]
        success, msg = export_rows_to_excel(path, "تقرير المخزون", headers, rows)
        (QMessageBox.information if success else QMessageBox.warning)(self, "تصدير Excel", msg)


    # ---------------------------------------------------------
    # تقرير مبيعات المخزون - إجمالي البيع لكل فئة + تفاصيل كل صنف داخل الفئة
    def _build_inventory_sales_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # ---- صف الفلاتر ----
        controls = QHBoxLayout()
        self.inv_sales_from_date = QDateEdit(_today_qdate().addDays(-30))
        self.inv_sales_from_date.setCalendarPopup(True)
        self.inv_sales_to_date = QDateEdit(_today_qdate())
        self.inv_sales_to_date.setCalendarPopup(True)
        controls.addWidget(QLabel("من:"))
        controls.addWidget(self.inv_sales_from_date)
        controls.addWidget(QLabel("إلى:"))
        controls.addWidget(self.inv_sales_to_date)

        today_btn = QPushButton("📅 اليوم")
        today_btn.clicked.connect(self._inv_sales_set_today)
        controls.addWidget(today_btn)

        month_btn = QPushButton("🗓️ الشهر الحالي")
        month_btn.clicked.connect(self._inv_sales_set_month)
        controls.addWidget(month_btn)

        run_btn = QPushButton("عرض التقرير")
        run_btn.clicked.connect(self.load_inventory_sales_report)
        controls.addWidget(run_btn)

        export_btn = QPushButton("📤 تصدير Excel")
        export_btn.clicked.connect(self.export_inventory_sales_report)
        controls.addWidget(export_btn)
        controls.addStretch()
        layout.addLayout(controls)

        # ---- بطاقات الملخص ----
        cards_row = QHBoxLayout()
        self.inv_sales_card_amount  = StatCard("إجمالي المبيعات")
        self.inv_sales_card_qty     = StatCard("إجمالي الكمية المباعة")
        self.inv_sales_card_cats    = StatCard("عدد الفئات")
        for c in (self.inv_sales_card_amount, self.inv_sales_card_qty, self.inv_sales_card_cats):
            cards_row.addWidget(c)
        cards_row.addStretch()
        layout.addLayout(cards_row)

        # ---- جدول ملخص الفئات ----
        layout.addWidget(QLabel("📦 مجموع المبيعات حسب الفئة:"))
        self.inv_sales_category_table = QTableWidget()
        self.inv_sales_category_table.setColumnCount(3)
        self.inv_sales_category_table.setHorizontalHeaderLabels(["الفئة", "الكمية المباعة", "إجمالي المبيعات"])
        self.inv_sales_category_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.inv_sales_category_table.verticalHeader().setVisible(False)
        self.inv_sales_category_table.setAlternatingRowColors(True)
        self.inv_sales_category_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.inv_sales_category_table.setMaximumHeight(200)
        # كليك على فئة يصفّي جدول التفاصيل
        self.inv_sales_category_table.clicked.connect(self._inv_sales_filter_by_category)
        layout.addWidget(self.inv_sales_category_table)

        # ---- جدول تفاصيل الأصناف ----
        self.inv_sales_detail_label = QLabel("📋 تفاصيل الأصناف (كل الفئات):")
        layout.addWidget(self.inv_sales_detail_label)
        self.inv_sales_detail_table = QTableWidget()
        self.inv_sales_detail_table.setColumnCount(4)
        self.inv_sales_detail_table.setHorizontalHeaderLabels(["الفئة", "الصنف", "الكمية المباعة", "إجمالي المبيعات"])
        self.inv_sales_detail_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.inv_sales_detail_table.verticalHeader().setVisible(False)
        self.inv_sales_detail_table.setAlternatingRowColors(True)
        self.inv_sales_detail_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.inv_sales_detail_table)

        self._inv_sales_report = None
        self._inv_sales_selected_cat = None
        self.load_inventory_sales_report()
        return widget

    def _inv_sales_set_today(self):
        today = _today_qdate()
        self.inv_sales_from_date.setDate(today)
        self.inv_sales_to_date.setDate(today)
        self.load_inventory_sales_report()

    def _inv_sales_set_month(self):
        today = _today_qdate()
        first = QDate(today.year(), today.month(), 1)
        last  = QDate(today.year(), today.month(), first.daysInMonth())
        self.inv_sales_from_date.setDate(first)
        self.inv_sales_to_date.setDate(last)
        self.load_inventory_sales_report()

    def load_inventory_sales_report(self):
        qf = self.inv_sales_from_date.date()
        qt = self.inv_sales_to_date.date()
        date_from = f"{qf.year():04d}-{qf.month():02d}-{qf.day():02d}"
        date_to   = f"{qt.year():04d}-{qt.month():02d}-{qt.day():02d}"
        self._inv_sales_report = get_inventory_sales_report(date_from, date_to)
        self._inv_sales_selected_cat = None
        self._inv_sales_render()

    def _inv_sales_render(self):
        report = self._inv_sales_report
        if not report:
            return
        cats = report["categories"]

        # بطاقات
        self.inv_sales_card_amount.set_value(f"{report['grand_total_amount']:.2f}")
        self.inv_sales_card_qty.set_value(str(report["grand_total_qty"]))
        self.inv_sales_card_cats.set_value(str(len(cats)))

        # جدول الفئات
        self.inv_sales_category_table.setRowCount(len(cats))
        cat_colors = [
            QColor("#dbeafe"), QColor("#dcfce7"), QColor("#fef9c3"),
            QColor("#fce7f3"), QColor("#ede9fe"), QColor("#ffedd5"),
        ]
        for row, cat in enumerate(cats):
            color = cat_colors[row % len(cat_colors)]
            for col, val in enumerate([cat["category_name"], str(cat["total_qty"]), f"{cat['total_amount']:.2f}"]):
                item = QTableWidgetItem(val)
                item.setBackground(color)
                self.inv_sales_category_table.setItem(row, col, item)

        # جدول تفاصيل الأصناف
        selected = self._inv_sales_selected_cat
        if selected is not None:
            filtered_cats = [c for c in cats if c["category_name"] == selected]
            self.inv_sales_detail_label.setText(f"📋 أصناف فئة: {selected}")
        else:
            filtered_cats = cats
            self.inv_sales_detail_label.setText("📋 تفاصيل الأصناف (كل الفئات - اضغط على فئة للتصفية):")

        all_items = []
        for cat in filtered_cats:
            for item in cat["items"]:
                all_items.append((cat["category_name"], item))

        self.inv_sales_detail_table.setRowCount(len(all_items))
        for row, (cat_name, item) in enumerate(all_items):
            self.inv_sales_detail_table.setItem(row, 0, QTableWidgetItem(cat_name))
            self.inv_sales_detail_table.setItem(row, 1, QTableWidgetItem(item["product_name"]))
            self.inv_sales_detail_table.setItem(row, 2, QTableWidgetItem(str(item["total_qty"])))
            self.inv_sales_detail_table.setItem(row, 3, QTableWidgetItem(f"{item['total_amount']:.2f}"))

    def _inv_sales_filter_by_category(self, index):
        """كليك على صف في جدول الفئات يصفّي جدول الأصناف - كليك ثاني على نفس الصف يلغي التصفية."""
        row = index.row()
        cats = self._inv_sales_report["categories"] if self._inv_sales_report else []
        if row < len(cats):
            clicked_cat = cats[row]["category_name"]
            if self._inv_sales_selected_cat == clicked_cat:
                self._inv_sales_selected_cat = None   # إلغاء التصفية
            else:
                self._inv_sales_selected_cat = clicked_cat
            self._inv_sales_render()

    def export_inventory_sales_report(self):
        if not self._inv_sales_report:
            return
        report = self._inv_sales_report
        qf = self.inv_sales_from_date.date()
        qt = self.inv_sales_to_date.date()
        date_from = f"{qf.year():04d}-{qf.month():02d}-{qf.day():02d}"
        date_to   = f"{qt.year():04d}-{qt.month():02d}-{qt.day():02d}"
        path = _pick_save_path(self, f"مبيعات_المخزون_{date_from}_إلى_{date_to}.xlsx")
        if not path:
            return
        headers = ["الفئة", "الصنف", "الكمية المباعة", "إجمالي المبيعات"]
        rows = []
        for cat in report["categories"]:
            for item in cat["items"]:
                rows.append((cat["category_name"], item["product_name"], item["total_qty"], item["total_amount"]))
        summary = [
            ("من", report["date_from"]), ("إلى", report["date_to"]),
            ("إجمالي المبيعات", report["grand_total_amount"]),
            ("إجمالي الكمية", report["grand_total_qty"]),
            ("عدد الفئات", len(report["categories"])),
        ]
        success, msg = export_rows_to_excel(path, "مبيعات المخزون", headers, rows, summary)
        (QMessageBox.information if success else QMessageBox.warning)(self, "تصدير Excel", msg)

    # ---------------------------------------------------------
    # تقرير ربح/خسارة - فرق سعر البيع عن التكلفة، ناقص المصاريف (expenses)
    def _build_profit_loss_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # صفوف اختيار سريع: يومي / شهري بدل تحديد التاريخ يدوي كل مرة
        quick_row = QHBoxLayout()
        quick_label = QLabel("عرض سريع:")
        quick_label.setStyleSheet("font-weight: bold;")
        quick_row.addWidget(quick_label)
        daily_btn = QPushButton("📅 ربح/خسارة اليوم")
        daily_btn.clicked.connect(self.show_daily_profit_loss)
        quick_row.addWidget(daily_btn)
        monthly_btn = QPushButton("🗓️ ربح/خسارة الشهر الحالي")
        monthly_btn.clicked.connect(self.show_monthly_profit_loss)
        quick_row.addWidget(monthly_btn)
        quick_row.addStretch()
        layout.addLayout(quick_row)

        controls = QHBoxLayout()
        self.pl_from_date = QDateEdit(_today_qdate().addDays(-30))
        self.pl_from_date.setCalendarPopup(True)
        self.pl_to_date = QDateEdit(_today_qdate())
        self.pl_to_date.setCalendarPopup(True)
        controls.addWidget(QLabel("من:"))
        controls.addWidget(self.pl_from_date)
        controls.addWidget(QLabel("إلى:"))
        controls.addWidget(self.pl_to_date)
        self.pl_include_expenses = QCheckBox("خصم المصاريف اليومية (صافي ربح حقيقي)")
        self.pl_include_expenses.setChecked(True)
        controls.addWidget(self.pl_include_expenses)
        run_btn = QPushButton("عرض التقرير")
        run_btn.clicked.connect(self.load_profit_loss_report)
        controls.addWidget(run_btn)
        export_btn = QPushButton("📤 تصدير Excel")
        export_btn.clicked.connect(self.export_profit_loss_report)
        controls.addWidget(export_btn)
        controls.addStretch()
        layout.addLayout(controls)

        self.pl_period_label = QLabel("")
        self.pl_period_label.setStyleSheet("font-weight: bold; color: #2c3e50; padding: 4px 0;")
        layout.addWidget(self.pl_period_label)

        cards_row = QHBoxLayout()
        self.pl_card_revenue = StatCard("الإيرادات")
        self.pl_card_cost = StatCard("التكلفة")
        self.pl_card_gross = StatCard("الربح الإجمالي")
        self.pl_card_expenses = StatCard("المصاريف")
        self.pl_card_net = StatCard("صافي الربح")
        for c in (self.pl_card_revenue, self.pl_card_cost, self.pl_card_gross,
                  self.pl_card_expenses, self.pl_card_net):
            cards_row.addWidget(c)
        layout.addLayout(cards_row)

        layout.addWidget(QLabel("الربح/الخسارة حسب المنتج:"))
        self.pl_table = QTableWidget()
        self.pl_table.setColumnCount(4)
        self.pl_table.setHorizontalHeaderLabels(["المنتج", "الكمية المباعة", "الإيراد", "الربح"])
        self.pl_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.pl_table.verticalHeader().setVisible(False)
        self.pl_table.setAlternatingRowColors(True)
        self.pl_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.pl_table)

        self._pl_report = None
        self.show_daily_profit_loss()
        return widget

    def show_daily_profit_loss(self):
        """يعرض تقرير الربح/الخسارة لليوم الحالي فقط (من بداية اليوم لآخره)."""
        today = _today_qdate()
        self.pl_from_date.setDate(today)
        self.pl_to_date.setDate(today)
        self.pl_period_label.setText(f"📅 تقرير اليوم: {today.toString('yyyy-MM-dd')}")
        self.load_profit_loss_report()

    def show_monthly_profit_loss(self):
        """يعرض تقرير الربح/الخسارة للشهر الحالي بالكامل (من أول يوم لآخر يوم بالشهر)."""
        today = _today_qdate()
        first_day = QDate(today.year(), today.month(), 1)
        last_day = QDate(today.year(), today.month(), first_day.daysInMonth())
        self.pl_from_date.setDate(first_day)
        self.pl_to_date.setDate(last_day)
        self.pl_period_label.setText(
            f"🗓️ تقرير الشهر الحالي: {first_day.toString('yyyy-MM-dd')} إلى {last_day.toString('yyyy-MM-dd')}"
        )
        self.load_profit_loss_report()

    def load_profit_loss_report(self):
        date_from = self.pl_from_date.date().toString("yyyy-MM-dd")
        date_to = self.pl_to_date.date().toString("yyyy-MM-dd")
        report = get_profit_loss_report(date_from, date_to, self.pl_include_expenses.isChecked())
        self._pl_report = report
        today_str = _today_qdate().toString("yyyy-MM-dd")
        if date_from == date_to == today_str:
            self.pl_period_label.setText(f"📅 تقرير اليوم: {date_from}")
        else:
            self.pl_period_label.setText(f"الفترة المعروضة: {date_from} إلى {date_to}")
        self.pl_card_revenue.set_value(f"{report['revenue']:.2f}")
        self.pl_card_cost.set_value(f"{report['cost']:.2f}")
        self.pl_card_gross.set_value(f"{report['gross_profit']:.2f}")
        self.pl_card_expenses.set_value(f"{report['expenses_total']:.2f}")
        self.pl_card_net.set_value(f"{report['net_profit']:.2f}")

        products = report["by_product"]
        self.pl_table.setRowCount(len(products))
        for row, p in enumerate(products):
            self.pl_table.setItem(row, 0, QTableWidgetItem(p["product_name"]))
            self.pl_table.setItem(row, 1, QTableWidgetItem(str(p["quantity"])))
            self.pl_table.setItem(row, 2, QTableWidgetItem(f"{p['revenue']:.2f}"))
            self.pl_table.setItem(row, 3, QTableWidgetItem(f"{p['profit']:.2f}"))

    def export_profit_loss_report(self):
        if not self._pl_report:
            return
        report = self._pl_report
        path = _pick_save_path(self, f"ربح_خسارة_{report['date_from']}_إلى_{report['date_to']}.xlsx")
        if not path:
            return
        headers = ["المنتج", "الكمية المباعة", "الإيراد", "الربح"]
        rows = [(p["product_name"], p["quantity"], p["revenue"], p["profit"]) for p in report["by_product"]]
        summary = [
            ("من", report["date_from"]), ("إلى", report["date_to"]),
            ("الإيرادات", report["revenue"]), ("التكلفة", report["cost"]),
            ("الربح الإجمالي", report["gross_profit"]), ("المصاريف", report["expenses_total"]),
            ("صافي الربح", report["net_profit"]),
        ]
        success, msg = export_rows_to_excel(path, "ربح وخسارة", headers, rows, summary)
        (QMessageBox.information if success else QMessageBox.warning)(self, "تصدير Excel", msg)

