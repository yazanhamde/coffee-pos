# -*- coding: utf-8 -*-
"""
ويدجتس مشتركة لتسهيل إدخال الأرقام.
====================================
كثير مستخدمين بيكتبوا الأرقام العشرية بفاصلة (5,25) بدل نقطة (5.25) -
خصوصاً من لوحة المفاتيح الرقمية أو العربي. SmartDoubleSpinBox بيقبل الاثنين
بدون ما يعطي خطأ أو يرفض الكتابة.
"""

from PyQt5.QtWidgets import (QDoubleSpinBox, QDialog, QVBoxLayout, QLabel,
                              QDialogButtonBox, QHBoxLayout)
from PyQt5.QtCore import Qt


class SmartDoubleSpinBox(QDoubleSpinBox):
    """QDoubleSpinBox بيقبل الفاصلة (,) كنقطة عشرية (.) تلقائياً أثناء الكتابة."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setButtonSymbols(QDoubleSpinBox.UpDownArrows)
        self.setAlignment(Qt.AlignCenter)

    def keyPressEvent(self, event):
        if event.text() == ",":
            # نحوّل الفاصلة لنقطة مباشرة بمكان المؤشر
            self.lineEdit().insert(".")
            return
        super().keyPressEvent(event)

    def validate(self, text, pos):
        # لو المستخدم لصق رقم فيه فاصلة (نسخ/لصق)، نحوّلها قبل التحقق
        fixed = text.replace(",", ".")
        return super().validate(fixed, pos)

    def valueFromText(self, text):
        return super().valueFromText(text.replace(",", "."))


class AmountInputDialog(QDialog):
    """نافذة إدخال رقم واحد (بديل QInputDialog.getDouble) بس بتقبل الفاصلة كنقطة عشرية،
    وبخط أكبر وأوضح تناسب شاشة كاشير."""

    def __init__(self, parent=None, title="إدخال قيمة", label="القيمة:",
                 value=0, min_value=0, max_value=1000000, decimals=2, suffix=""):
        super().__init__(parent)
        self.setLayoutDirection(Qt.RightToLeft)
        self.setWindowTitle(title)
        self.setMinimumWidth(320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(14)

        lbl = QLabel(label)
        lbl.setObjectName("dialogLabel")
        layout.addWidget(lbl)

        self.spin = SmartDoubleSpinBox()
        self.spin.setRange(min_value, max_value)
        self.spin.setDecimals(decimals)
        self.spin.setValue(value)
        if suffix:
            self.spin.setSuffix(suffix)
        self.spin.setObjectName("bigNumberInput")
        self.spin.selectAll()
        layout.addWidget(self.spin)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("تأكيد")
        buttons.button(QDialogButtonBox.Cancel).setText("إلغاء")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.spin.setFocus()

    def value(self):
        return self.spin.value()


def get_double_input(parent, title, label, value=0, min_value=0, max_value=1000000,
                      decimals=2, suffix=""):
    """بديل مباشر لـ QInputDialog.getDouble بس بيقبل الفاصلة كنقطة عشرية.
    يرجع (value, ok) بنفس أسلوب QInputDialog."""
    dialog = AmountInputDialog(parent, title, label, value, min_value, max_value, decimals, suffix)
    ok = dialog.exec_() == QDialog.Accepted
    return dialog.value(), ok
