# -*- coding: utf-8 -*-
"""
نظام كاشير القهوة - نقطة التشغيل الرئيسية
============================================
يشغّل: تسجيل الدخول → فتح/متابعة الشِفت → شاشة الكاشير
مع نسخ احتياطي تلقائي يومي لقاعدة البيانات عند بداية التشغيل.
"""

import sys
import os
import logging
import traceback
from utils.time_utils import jordan_now_str

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ==================================================================
# إعداد Logging — يحفظ كل الأخطاء والأحداث في logs/app.log
# ==================================================================

def setup_logging():
    """
    يضبط نظام السجلات (Logging) ليكتب في:
      - logs/app.log  : ملف يومي يحتفظ بآخر 7 أيام
      - الكونسول      : مستوى WARNING وأعلى فقط (عشان ما يزعج أثناء التطوير)

    مستويات الأهمية:
      DEBUG   : تفاصيل كثيرة (للتطوير فقط)
      INFO    : أحداث عادية (تسجيل دخول، بيع، طباعة...)
      WARNING : شيء غريب بس البرنامج استمر (طابعة فشلت، ترميز خاطئ...)
      ERROR   : خطأ في وظيفة معينة
      CRITICAL: خطأ أوقف البرنامج كلياً
    """
    # مجلد اللوجات بجانب main.py
    base_dir  = os.path.dirname(os.path.abspath(__file__))
    logs_dir  = os.path.join(base_dir, "logs")
    os.makedirs(logs_dir, exist_ok=True)

    log_file = os.path.join(logs_dir, "app.log")

    # صيغة السطر: [2026-09-09 14:30:00] INFO     coffee_pos.main : رسالة
    fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)-8s %(name)-25s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # --- Handler للملف (INFO وأعلى، rotating يومي يحتفظ بـ 7 أيام) ---
    try:
        from logging.handlers import TimedRotatingFileHandler
        file_handler = TimedRotatingFileHandler(
            log_file,
            when="midnight",      # يدور الملف كل منتصف ليل
            interval=1,
            backupCount=7,        # يحتفظ بآخر 7 أيام
            encoding="utf-8"
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(fmt)
    except Exception:
        # fallback: FileHandler عادي لو TimedRotating ما اشتغل
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(fmt)

    # --- Handler للكونسول (WARNING وأعلى بس) ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(fmt)

    # --- الـ Root Logger ---
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # الـ handlers بتفلتر هي
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    return log_file


def _handle_uncaught_exception(exc_type, exc_value, exc_tb):
    """
    يلتقط أي استثناء غير متوقع (Uncaught Exception) ويكتبه في اللوج
    قبل ما البرنامج يوقف — بدله بيظهر خطأ صامت بوندوز.
    """
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    logger = logging.getLogger("coffee_pos.main")
    logger.critical(
        "خطأ غير متوقع أوقف البرنامج!\n" +
        "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    )


# ==================================================================
# Imports بقية المشروع (بعد إعداد Logging)
# ==================================================================

from PyQt5.QtWidgets import QApplication, QMainWindow, QStackedWidget, QMessageBox
from PyQt5.QtCore import Qt

from database.db_setup import create_database
from database.data_access import get_open_shift, get_resumable_shift_today, resume_shift
from ui.style import MAIN_STYLESHEET
from ui.login_screen import LoginScreen
from ui.pos_screen import POSScreen
from ui.shift_screen import OpenShiftScreen, CloseShiftScreen
from ui.products_screen import ProductsManagementScreen
from ui.settings_screen import SettingsScreen
from ui.reports_screen import ReportsScreen
from ui.force_password_screen import ForcePasswordChangeScreen
from utils.backup import run_backup, should_backup_today


# ==================================================================
# النافذة الرئيسية
# ==================================================================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger("coffee_pos.main_window")
        self.setWindowTitle("love.jo — نظام كاشير القهوة")
        self.setLayoutDirection(Qt.RightToLeft)
        self.resize(1200, 750)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.current_user = None
        self.current_shift_id = None

        self.show_login()

    # ---------------------------------------------------------
    def show_login(self):
        self.current_user = None
        self.current_shift_id = None
        login = LoginScreen(on_login_success=self.handle_login_success)
        self._set_screen(login)

    def handle_login_success(self, user):
        self.current_user = user
        self.logger.info(f"تسجيل دخول ناجح — المستخدم: {user.get('username')} | الدور: {user.get('role')}")
        if user.get("must_change_password"):
            self.logger.info(f"إجبار تغيير كلمة السر — {user.get('username')}")
            self.show_force_password_change()
            return
        self._continue_after_login(user)

    def show_force_password_change(self):
        screen = ForcePasswordChangeScreen(self.current_user, on_done=self._continue_after_login)
        self._set_screen(screen)

    def _continue_after_login(self, user):
        self.current_user = user

        open_shift_row = get_open_shift(user["id"])
        if open_shift_row:
            self.current_shift_id = open_shift_row["id"]
            self.logger.info(f"متابعة شِفت مفتوح ID={self.current_shift_id} — {user.get('username')}")
            self.show_pos_screen()
            return

        resumable = get_resumable_shift_today(user["id"])
        if resumable:
            ended_label = (resumable.get("ended_at") or "")[:16]
            answer = QMessageBox.question(
                self, "إكمال الشِفت السابق؟",
                f"عندك شِفت مقفول ({ended_label}).\n"
                "بدك تكمل عليه (تضل فواتيره ومبيعاته محفوظة ومرتبطة)؟\n"
                "أو تفضّل تبلش شِفت جديد من الصفر (الكاش والفواتير يرجعوا صفر)؟",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
            )
            if answer == QMessageBox.Yes:
                self.current_shift_id = resume_shift(resumable["id"], user["id"])
                self.logger.info(f"استئناف شِفت ID={self.current_shift_id} — {user.get('username')}")
                self.show_pos_screen()
                return

        self.show_open_shift_screen()

    # ---------------------------------------------------------
    def show_open_shift_screen(self):
        screen = OpenShiftScreen(self.current_user, on_shift_opened=self.handle_shift_opened)
        self._set_screen(screen)

    def handle_shift_opened(self, shift_id):
        self.current_shift_id = shift_id
        self.logger.info(f"فُتح شِفت جديد ID={shift_id} — {self.current_user.get('username')}")
        self.show_pos_screen()

    # ---------------------------------------------------------
    def show_pos_screen(self):
        screen = POSScreen(
            current_user=self.current_user,
            current_shift_id=self.current_shift_id,
            on_logout=self.handle_logout_request,
            on_manage_products=self.show_products_management,
            on_manage_settings=self.show_settings,
            on_view_reports=self.show_reports,
        )
        self._set_screen(screen)

    def show_products_management(self):
        screen = ProductsManagementScreen(
            current_user=self.current_user,
            on_back=self.show_pos_screen,
        )
        self._set_screen(screen)

    def show_settings(self):
        screen = SettingsScreen(
            current_user=self.current_user,
            on_back=self.show_pos_screen,
        )
        self._set_screen(screen)

    def show_reports(self):
        screen = ReportsScreen(
            current_user=self.current_user,
            on_back=self.show_pos_screen,
        )
        self._set_screen(screen)

    def handle_logout_request(self):
        screen = CloseShiftScreen(
            self.current_user, self.current_shift_id,
            on_shift_closed=self.show_login,
        )
        self._set_screen(screen)

    # ---------------------------------------------------------
    def _set_screen(self, widget):
        while self.stack.count() > 0:
            old = self.stack.widget(0)
            self.stack.removeWidget(old)
            old.deleteLater()
        self.stack.addWidget(widget)
        self.stack.setCurrentWidget(widget)


# ==================================================================
# نقطة التشغيل
# ==================================================================

def main():
    # إعداد Logging أول شي قبل أي import آخر
    log_file = setup_logging()
    sys.excepthook = _handle_uncaught_exception

    logger = logging.getLogger("coffee_pos.main")
    logger.info("=" * 60)
    logger.info(f"تشغيل نظام كاشير القهوة — {jordan_now_str('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Python: {sys.version} | Platform: {sys.platform}")
    logger.info(f"ملف اللوج: {log_file}")
    logger.info("=" * 60)

    # 1) التأكد من وجود قاعدة البيانات وإنشائها لو أول تشغيل
    try:
        create_database()
        logger.info("قاعدة البيانات جاهزة ✓")
    except Exception as e:
        logger.critical(f"فشل إنشاء قاعدة البيانات: {e}", exc_info=True)
        sys.exit(1)

    # 2) نسخة احتياطية تلقائية يومية
    if should_backup_today():
        try:
            run_backup()
            logger.info("النسخة الاحتياطية اليومية تمت بنجاح ✓")
        except Exception as e:
            logger.warning(f"فشل النسخ الاحتياطي (البرنامج سيكمل): {e}", exc_info=True)
            print(f"⚠️ فشل النسخ الاحتياطي: {e}")

    # 3) تشغيل التطبيق
    app = QApplication(sys.argv)
    app.setLayoutDirection(Qt.RightToLeft)
    app.setStyleSheet(MAIN_STYLESHEET)

    window = MainWindow()
    window.showMaximized()

    logger.info("النافذة الرئيسية تشغّلت ✓")
    exit_code = app.exec_()
    logger.info(f"انتهى التطبيق — exit code: {exit_code}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
