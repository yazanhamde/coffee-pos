# -*- coding: utf-8 -*-
"""شاشة إعدادات النظام (للمدير فقط) - اسم المحل، نسبة الضريبة، تذييل الفاتورة، بورت الطابعة."""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                              QLineEdit, QFormLayout, QMessageBox, QFrame, QComboBox, QSpinBox)
from PyQt5.QtCore import Qt

from ui.widgets import SmartDoubleSpinBox

from database.data_access import get_setting, set_setting
from utils.printer import list_windows_printers


class SettingsScreen(QWidget):
    def __init__(self, current_user, on_back):
        super().__init__()
        self.current_user = current_user
        self.on_back = on_back
        self.setLayoutDirection(Qt.RightToLeft)
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)

        header = QHBoxLayout()
        title = QLabel("⚙️ إعدادات النظام")
        title.setObjectName("titleLabel")
        header.addWidget(title)
        header.addStretch()
        back_btn = QPushButton("⬅ رجوع")
        back_btn.clicked.connect(self.on_back)
        header.addWidget(back_btn)
        outer.addLayout(header)

        card = QFrame()
        card.setObjectName("card")
        card.setMaximumWidth(500)
        form = QFormLayout(card)
        form.setContentsMargins(24, 24, 24, 24)
        form.setSpacing(14)

        self.store_name_input = QLineEdit()
        form.addRow("اسم المحل (يظهر على الفاتورة):", self.store_name_input)

        self.tax_input = SmartDoubleSpinBox()
        self.tax_input.setRange(0, 100)
        self.tax_input.setSuffix(" %")
        form.addRow("نسبة ضريبة افتراضية (لمنتج جديد فقط):", self.tax_input)

        self.footer_input = QLineEdit()
        form.addRow("رسالة تذييل الفاتورة:", self.footer_input)

        printer_row = QHBoxLayout()
        self.printer_name_combo = QComboBox()
        self.printer_name_combo.setEditable(True)
        self.printer_name_combo.setMinimumWidth(260)
        printer_row.addWidget(self.printer_name_combo)
        refresh_printers_btn = QPushButton("🔄 تحديث القائمة")
        refresh_printers_btn.clicked.connect(self.refresh_printer_list)
        printer_row.addWidget(refresh_printers_btn)
        form.addRow("طابعة وندوز (الأشيع - طابعة USB مركّبة بوندوز):", printer_row)

        self.printer_port_input = QLineEdit()
        self.printer_port_input.setPlaceholderText("مثال: COM3 (بس لو الطابعة Serial حقيقية - نادر)")
        form.addRow("بورت الطابعة (Serial - اختياري):", self.printer_port_input)

        test_print_btn = QPushButton("🖨️ طباعة تجريبية")
        test_print_btn.clicked.connect(self.handle_test_print)
        form.addRow(test_print_btn)

        note = QLabel(
            "ℹ️ اختاري اسم الطابعة متل ما ظاهر بوندوز (لوحة التحكم ← الأجهزة والطابعات) - هاي الطريقة\n"
            "الصح لأغلب طابعات الفواتير USB ومش محتاجة رقم بورت إطلاقاً.\n"
            "خانة البورت (COM) استخدميها بس لو الطابعة توصيلها Serial حقيقي، وهاي حالة نادرة.\n"
            "لو الاثنتين فاضيين، البرنامج بيشتغل بوضع محاكاة (بيسجل الفاتورة بس ما بيطبعها فعلياً).")
        note.setWordWrap(True)
        form.addRow(note)

        # ---- تعديل الوقت (تصحيح انحراف الساعة فقط - للطوارئ) ----
        time_offset_row = QHBoxLayout()
        self.time_offset_spin = QSpinBox()
        self.time_offset_spin.setRange(-720, 720)   # أقصى انحراف ممكن: 12 ساعة
        self.time_offset_spin.setSuffix(" دقيقة")
        self.time_offset_spin.setSpecialValueText("0 - بدون تعديل")
        self.time_offset_spin.setToolTip("انحراف الدقائق عن UTC+3 | استخدم فقط لتصحيح انحراف بسيط (اقل 60 دقيقة) | اكبر من ذلك يعني مشكلة بالمنطقة الزمنية")
        time_offset_row.addWidget(self.time_offset_spin)
        time_offset_label = QLabel("⚠️ للطوارئ فقط: لو ساعة الجهاز غلط بدقائق معدودة")
        time_offset_label.setStyleSheet("color: #b45309; font-size: 11px;")
        time_offset_row.addWidget(time_offset_label)
        form.addRow("تعديل انحراف الوقت (دقائق):", time_offset_row)

        save_btn = QPushButton("💾 حفظ الإعدادات")
        save_btn.setObjectName("successBtn")
        save_btn.clicked.connect(self.handle_save)
        form.addRow(save_btn)

        outer.addWidget(card, alignment=Qt.AlignLeft)
        outer.addStretch()

    def load_settings(self):
        self.store_name_input.setText(get_setting("store_name", "love.jo"))
        try:
            self.tax_input.setValue(float(get_setting("tax_percent", "16")))
        except ValueError:
            self.tax_input.setValue(16)
        self.footer_input.setText(get_setting("receipt_footer", "شكراً لزيارتكم"))
        self.printer_port_input.setText(get_setting("printer_port", ""))
        # تحميل انحراف الوقت المحفوظ
        try:
            self.time_offset_spin.setValue(int(get_setting("time_offset_minutes", "0")))
        except ValueError:
            self.time_offset_spin.setValue(0)
        self.refresh_printer_list()
        saved_printer = get_setting("printer_name", "")
        if saved_printer:
            idx = self.printer_name_combo.findText(saved_printer)
            if idx >= 0:
                self.printer_name_combo.setCurrentIndex(idx)
            else:
                self.printer_name_combo.setEditText(saved_printer)

    def refresh_printer_list(self):
        current = self.printer_name_combo.currentText()
        self.printer_name_combo.clear()
        self.printer_name_combo.addItem("")  # بدون طابعة وندوز محددة
        printers = list_windows_printers()
        self.printer_name_combo.addItems(printers)
        if current:
            self.printer_name_combo.setEditText(current)
        if not printers:
            QMessageBox.information(
                self, "تنبيه",
                "ما قدرنا نجيب قائمة طابعات وندوز تلقائياً (إما البرنامج مش شغال على وندوز،\n"
                "أو مكتبة pywin32 مش مثبتة: pip install pywin32).\n"
                "بإمكانك تكتبي اسم الطابعة يدوياً بنفس الخانة.")

    def handle_save(self):
        store_name = self.store_name_input.text().strip()
        if not store_name:
            QMessageBox.warning(self, "تنبيه", "اسم المحل ما ممكن يكون فاضي")
            return

        # ---- التحقق من انحراف الوقت ----
        offset_minutes = self.time_offset_spin.value()
        if abs(offset_minutes) > 60:
            msg_text = "انحراف " + str(offset_minutes) + " دقيقة - كبير جداً!\nالمقبول: -60 الى +60 دقيقة.\nهل تريد المتابعة؟"
            reply = QMessageBox.warning(
                self, "تحذير - انحراف كبير", msg_text,
                QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel,
            )
            if reply != QMessageBox.Yes:
                return

        set_setting("store_name", store_name)
        set_setting("tax_percent", str(self.tax_input.value()))
        set_setting("receipt_footer", self.footer_input.text().strip())
        set_setting("printer_port", self.printer_port_input.text().strip())
        set_setting("printer_name", self.printer_name_combo.currentText().strip())
        set_setting("time_offset_minutes", str(offset_minutes))

        QMessageBox.information(self, "تم", "تم حفظ الإعدادات بنجاح - فعّالة فوراً بدون ما تحتاجي تسكري البرنامج")

    def handle_test_print(self):
        from utils.printer import print_raw_text
        printer_name = self.printer_name_combo.currentText().strip()
        printer_port = self.printer_port_input.text().strip()
        sample = "=== love.jo ===\nطباعة تجريبية\nلو وصلتك هاي الورقة، الطابعة شغالة تمام ✅\n"
        ok, msg = print_raw_text(sample, printer_port=printer_port or None, printer_name=printer_name or None)
        if ok:
            QMessageBox.information(self, "نتيجة الطباعة التجريبية", msg)
        else:
            QMessageBox.warning(self, "فشلت الطباعة التجريبية", msg)
