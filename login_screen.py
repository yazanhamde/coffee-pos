# -*- coding: utf-8 -*-
"""شاشة تسجيل الدخول - النظام أصبح بمستخدم أدمن وحيد، فالدخول بكلمة السر فقط."""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QLineEdit,
                              QPushButton, QMessageBox, QFrame)
from PyQt5.QtCore import Qt
from database.data_access import verify_login

ADMIN_USERNAME = "admin"


class LoginScreen(QWidget):
    def __init__(self, on_login_success):
        super().__init__()
        self.on_login_success = on_login_success
        self.setLayoutDirection(Qt.RightToLeft)
        self.init_ui()

    def init_ui(self):
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setObjectName("card")
        card.setFixedWidth(380)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(40, 40, 40, 40)
        card_layout.setSpacing(16)

        title = QLabel("☕ love.jo")
        title.setObjectName("titleLabel")
        title.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(title)

        subtitle = QLabel("تسجيل الدخول")
        subtitle.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(subtitle)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("كلمة السر")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.returnPressed.connect(self.handle_login)
        card_layout.addWidget(self.password_input)

        login_btn = QPushButton("دخول")
        login_btn.clicked.connect(self.handle_login)
        card_layout.addWidget(login_btn)

        outer.addWidget(card, alignment=Qt.AlignCenter)
        self.password_input.setFocus()

    def handle_login(self):
        password = self.password_input.text().strip()

        if not password:
            QMessageBox.warning(self, "تنبيه", "الرجاء إدخال كلمة السر")
            return

        user = verify_login(ADMIN_USERNAME, password)
        if user:
            self.password_input.clear()
            self.on_login_success(user)
        else:
            QMessageBox.critical(self, "خطأ", "كلمة السر غير صحيحة")
            self.password_input.clear()
