# -*- coding: utf-8 -*-
"""شاشة فتح الشِفت وشاشة الإقفال اليومي."""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton, QFrame, QMessageBox, QLineEdit)
from PyQt5.QtCore import Qt

from ui.widgets import SmartDoubleSpinBox

from database.data_access import open_shift, close_shift, get_shift_summary, get_shift_item_summary, get_setting, get_shift_detail
from utils.printer import print_raw_text


class OpenShiftScreen(QWidget):
    """تظهر بعد تسجيل الدخول مباشرة إذا ما في شِفت مفتوح للمستخدم."""

    def __init__(self, current_user, on_shift_opened):
        super().__init__()
        self.current_user = current_user
        self.on_shift_opened = on_shift_opened
        self.setLayoutDirection(Qt.RightToLeft)
        self.init_ui()

    def init_ui(self):
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setObjectName("card")
        card.setFixedWidth(360)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(14)

        title = QLabel("🕐 بداية الشِفت")
        title.setObjectName("titleLabel")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        cashier_header = QLabel("الماسك:")
        cashier_header.setAlignment(Qt.AlignCenter)
        cashier_header.setStyleSheet("font-size: 13px; color: #2c7be5; padding: 2px 0;")
        layout.addWidget(cashier_header)

        self.cashier_name_input = QLineEdit()
        self.cashier_name_input.setPlaceholderText("ادخل اسم الموظف...")
        self.cashier_name_input.setAlignment(Qt.AlignRight)
        self.cashier_name_input.setStyleSheet("font-size: 15px; font-weight: bold;")
        layout.addWidget(self.cashier_name_input)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep)

        layout.addWidget(QLabel("الرصد الافتتاحي بالدرج (كاش):"))
        self.opening_cash_input = SmartDoubleSpinBox()
        self.opening_cash_input.setRange(0, 100000)
        self.opening_cash_input.setDecimals(2)
        layout.addWidget(self.opening_cash_input)

        start_btn = QPushButton("بدء الشِفت")
        start_btn.setObjectName("successBtn")
        start_btn.clicked.connect(self.start_shift)
        layout.addWidget(start_btn)

        outer.addWidget(card, alignment=Qt.AlignCenter)

    def start_shift(self):
        cashier_name = self.cashier_name_input.text().strip()
        if not cashier_name:
            QMessageBox.warning(self, "تنبيه", "الرجاء إدخال اسم الموظف قبل بدء الشِفت")
            self.cashier_name_input.setFocus()
            return
        opening_cash = self.opening_cash_input.value()
        shift_id = open_shift(self.current_user["id"], opening_cash, cashier_name)
        self.on_shift_opened(shift_id)


class CloseShiftScreen(QWidget):
    """شاشة الإقفال اليومي - تظهر عند طلب إنهاء الشِفت."""

    def __init__(self, current_user, shift_id, on_shift_closed):
        super().__init__()
        self.current_user = current_user
        self.shift_id = shift_id
        self.on_shift_closed = on_shift_closed
        self.setLayoutDirection(Qt.RightToLeft)
        self.init_ui()

    def init_ui(self):
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setObjectName("card")
        card.setFixedWidth(400)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(14)

        title = QLabel("🔒 إقفال الشِفت")
        title.setObjectName("titleLabel")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        summary = get_shift_summary(self.shift_id)
        cash_total = sum(o["cash_paid"] for o in summary["orders"])
        network_total = sum(o["card_paid"] for o in summary["orders"])
        layout.addWidget(QLabel(f"عدد الفواتير: {summary['orders_count']}"))
        layout.addWidget(QLabel(f"إجمالي المبيعات: {summary['total_sales']:.2f}"))
        layout.addWidget(QLabel(f"منها كاش: {cash_total:.2f}  |  شبكة: {network_total:.2f}"))

        layout.addWidget(QLabel("الكاش الفعلي بالدرج الآن:"))
        self.actual_cash_input = SmartDoubleSpinBox()
        self.actual_cash_input.setRange(0, 100000)
        self.actual_cash_input.setDecimals(2)
        layout.addWidget(self.actual_cash_input)

        close_btn = QPushButton("تأكيد الإقفال")
        close_btn.setObjectName("dangerBtn")
        close_btn.clicked.connect(self.do_close)
        layout.addWidget(close_btn)

        outer.addWidget(card, alignment=Qt.AlignCenter)

    def do_close(self):
        actual = self.actual_cash_input.value()
        result = close_shift(self.shift_id, actual, self.current_user["id"])

        diff = result["difference"]
        # الكاش والشبكة منفصلين تماماً بالعرض - فرق الكاش يُحسب على الكاش بس،
        # الشبكة تُعرض/تُسجَّل فقط بدون أي حساب فرق عليها
        msg = (
            f"— الكاش —\n"
            f"الكاش المتوقع: {result['expected']:.2f}\n"
            f"الكاش الفعلي: {result['actual']:.2f}\n"
            f"الفرق: {diff:.2f}\n\n"
            f"— الشبكة —\n"
            f"إجمالي مدفوعات الشبكة: {result['network_total']:.2f}\n"
            f"(مدفوعات الشبكة لا يُحسب عليها فرق - عرض/تسجيل فقط)"
        )
        if abs(diff) > 0.01:
            msg += "\n\n⚠️ يوجد فرق بالكاش، الرجاء المراجعة."

        # طباعة تقرير إقفال الشِفت (ملخص + إجمالي المبيعات لكل صنف)
        self.print_shift_report(result)

        QMessageBox.information(self, "نتيجة الإقفال", msg)
        self.on_shift_closed()

    def print_shift_report(self, close_result):
        summary = get_shift_summary(self.shift_id)
        items = get_shift_item_summary(self.shift_id)
        store_name = get_setting("store_name", "love.jo")

        lines = []
        lines.append(f"=== {store_name} ===")
        lines.append("تقرير إقفال شِفت")
        shift_detail = get_shift_detail(self.shift_id)
        shift_cashier = (shift_detail['shift'].get('cashier_name') or self.current_user['full_name']) if shift_detail else self.current_user['full_name']
        lines.append(f"الكاشير: {shift_cashier}")
        lines.append("-" * 32)
        lines.append(f"عدد الفواتير: {summary['orders_count']}")
        lines.append(f"إجمالي المبيعات: {summary['total_sales']:.2f}")
        lines.append(f"الكاش المتوقع: {close_result['expected']:.2f}")
        lines.append(f"الكاش الفعلي: {close_result['actual']:.2f}")
        lines.append(f"الفرق (كاش فقط): {close_result['difference']:.2f}")
        lines.append("-" * 32)
        lines.append(f"إجمالي مدفوعات الشبكة: {close_result.get('network_total', 0):.2f}")
        lines.append("(بدون حساب فرق - عرض/تسجيل فقط)")
        lines.append("-" * 32)
        lines.append("إجمالي المبيعات حسب الصنف:")
        if items:
            for it in items:
                lines.append(f"{it['product_name_snapshot']} x{it['total_qty']}  ({it['total_amount']:.2f})")
        else:
            lines.append("(لا يوجد مبيعات هالشِفت)")
        lines.append("-" * 32)

        report_text = "\n".join(lines)
        success, print_msg = print_raw_text(
            report_text,
            printer_port=get_setting("printer_port", "") or None,
            printer_name=get_setting("printer_name", "") or None,
        )
        if not success:
            QMessageBox.warning(self, "تنبيه طباعة", f"ما قدرنا نطبع تقرير الإقفال: {print_msg}")
