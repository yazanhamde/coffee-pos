# -*- coding: utf-8 -*-
"""شاشة إجبارية لتغيير كلمة السر - تظهر أول ما مستخدم يسجل دخول بكلمة سر افتراضية/مصفّرة."""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton,
                              QMessageBox, QFrame)
from PyQt5.QtCore import Qt

from database.data_access import change_password


class ForcePasswordChangeScreen(QWidget):
    def __init__(self, user, on_done):
        super().__init__()
        self.user = user
        self.on_done = on_done
        self.setLayoutDirection(Qt.RightToLeft)
        self.init_ui()

    def init_ui(self):
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setObjectName("card")
        card.setFixedWidth(400)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(14)

        title = QLabel("🔒 لازم تغيّر كلمة السر")
        title.setObjectName("titleLabel")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        note = QLabel(
            "هاي أول مرة تسجّل فيها دخول (أو كلمة سرّك مصفّرة).\n"
            "لأسباب أمان، لازم تحط كلمة سر جديدة وخاصة فيك قبل ما تكمّل.")
        note.setWordWrap(True)
        note.setAlignment(Qt.AlignCenter)
        layout.addWidget(note)

        self.new_password = QLineEdit()
        self.new_password.setPlaceholderText("كلمة السر الجديدة (4 خانات على الأقل)")
        self.new_password.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.new_password)

        self.confirm_password = QLineEdit()
        self.confirm_password.setPlaceholderText("تأكيد كلمة السر")
        self.confirm_password.setEchoMode(QLineEdit.Password)
        self.confirm_password.returnPressed.connect(self.handle_submit)
        layout.addWidget(self.confirm_password)

        submit_btn = QPushButton("حفظ ومتابعة")
        submit_btn.setObjectName("successBtn")
        submit_btn.clicked.connect(self.handle_submit)
        layout.addWidget(submit_btn)

        outer.addWidget(card, alignment=Qt.AlignCenter)

    def handle_submit(self):
        p1 = self.new_password.text().strip()
        p2 = self.confirm_password.text().strip()

        if len(p1) < 4:
            QMessageBox.warning(self, "تنبيه", "كلمة السر لازم تكون 4 خانات على الأقل")
            return
        if p1 != p2:
            QMessageBox.warning(self, "تنبيه", "كلمتا السر غير متطابقتين")
            return
        if p1 in ("admin123", "1234"):
            QMessageBox.warning(self, "تنبيه", "لازم تختار كلمة سر مختلفة عن الكلمة الافتراضية")
            return

        change_password(self.user["id"], p1, force_change_again=False, changed_by=self.user["id"])
        self.user["must_change_password"] = 0
        QMessageBox.information(self, "تم", "تم تغيير كلمة السر بنجاح")
        self.on_done(self.user)
