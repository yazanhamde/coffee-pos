# -*- coding: utf-8 -*-
"""تنسيق موحّد للواجهة - ثيم احترافي بمزيج أحمر/أزرق/أبيض، هادئ ومريح للعين،
مناسب للمس والشاشات الكبيرة.

ملاحظة تصميم: الألوان الوظيفية (success = أخضر النجاح، warning = برتقالي التنبيه)
خليناها كما هي عن قصد، لأنها إشارات عالمية متعارف عليها (نجاح/تحذير) بعيدة عن هوية
النظام البصرية، وتغييرها لأحمر/أزرق ممكن يلخبط الكاشير وقت الدفع أو تنبيه المخزون
(نظام الألوان 🟢🟡🔴 على المنتجات مبني عليها أصلاً). أما danger (حذف/إلغاء) خليناه
بنفس أحمر الهوية عشان يبقى الأحمر متّسق بكل الشاشة."""

COLORS = {
    "primary": "#1F4E79",        # أزرق احترافي أساسي - أزرار، هيدر الجداول، تبويبات
    "primary_dark": "#153A5B",   # أزرق غامق - hover/pressed
    "primary_light": "#4A7FB5",  # أزرق فاتح - حدود وتلميحات خفيفة
    "accent": "#C0392B",         # أحمر الهوية - عناصر تمييز (تبويب مختار، إجمالي الفاتورة)
    "accent_dark": "#9C2E22",    # أحمر غامق - hover على عناصر الأحمر
    "accent_light": "#F5DAD8",   # أحمر فاتح جداً - خلفيات تمييز خفيفة/تحديد بالجداول
    "bg": "#F4F7FA",             # خلفية عامة - أبيض بلمسة زرقاء هادئة
    "bg_alt": "#E7EEF4",         # خلفية ثانوية/صفوف متبادلة
    "card_bg": "#FFFFFF",        # أبيض نقي للبطاقات وحقول الإدخال
    "border": "#D3DFE8",
    "text": "#1B2733",           # كحلي غامق قريب من الأسود - وضوح قراءة عالي
    "text_muted": "#60707F",
    "success": "#2E8B57",
    "success_dark": "#226B43",
    "danger": "#C0392B",
    "danger_dark": "#9C2E22",
    "warning": "#E0902B",
    "white": "#FFFFFF",
}

MAIN_STYLESHEET = f"""
* {{
    font-family: 'Segoe UI', 'Tahoma', 'Arial';
    outline: none;
}}

QWidget {{
    background-color: {COLORS['bg']};
    color: {COLORS['text']};
    font-size: 14px;
}}

QMainWindow {{
    background-color: {COLORS['bg']};
}}

/* ===================== أزرار ===================== */
QPushButton {{
    background-color: {COLORS['primary']};
    color: {COLORS['white']};
    border: none;
    border-radius: 10px;
    padding: 11px 18px;
    font-size: 14px;
    font-weight: 600;
}}

QPushButton:hover {{
    background-color: {COLORS['primary_dark']};
}}

QPushButton:pressed {{
    background-color: {COLORS['primary_dark']};
    padding-top: 12px;
}}

QPushButton:disabled {{
    background-color: #C9BBA6;
    color: #F4EFE8;
}}

QPushButton#dangerBtn {{
    background-color: {COLORS['danger']};
}}
QPushButton#dangerBtn:hover {{
    background-color: {COLORS['danger_dark']};
}}

QPushButton#successBtn {{
    background-color: {COLORS['success']};
    font-size: 15px;
    padding: 14px 18px;
}}
QPushButton#successBtn:hover {{
    background-color: {COLORS['success_dark']};
}}

QPushButton#secondaryBtn {{
    background-color: {COLORS['card_bg']};
    color: {COLORS['primary_dark']};
    border: 1.5px solid {COLORS['border']};
}}
QPushButton#secondaryBtn:hover {{
    background-color: {COLORS['bg_alt']};
}}

QPushButton#productBtn {{
    background-color: {COLORS['card_bg']};
    color: {COLORS['text']};
    border: 1.5px solid {COLORS['border']};
    border-radius: 14px;
    padding: 16px 10px;
    font-size: 15px;
    font-weight: 700;
    min-height: 78px;
    text-align: center;
}}

QPushButton#productBtn:hover {{
    background-color: {COLORS['accent_light']};
    border: 1.5px solid {COLORS['accent']};
    color: {COLORS['primary_dark']};
}}

QPushButton#productBtn:pressed {{
    background-color: {COLORS['accent']};
    color: white;
}}

/* ===================== حقول الإدخال ===================== */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit {{
    background-color: {COLORS['white']};
    border: 1.5px solid {COLORS['border']};
    border-radius: 8px;
    padding: 9px 10px;
    font-size: 14px;
    selection-background-color: {COLORS['accent']};
}}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus {{
    border: 1.5px solid {COLORS['primary']};
    background-color: #FFFDF9;
}}

QLineEdit:hover, QComboBox:hover {{
    border: 1.5px solid {COLORS['primary_light']};
}}

QComboBox::drop-down {{
    border: none;
    width: 26px;
}}

QComboBox QAbstractItemView {{
    background-color: {COLORS['white']};
    border: 1px solid {COLORS['border']};
    selection-background-color: {COLORS['accent_light']};
    selection-color: {COLORS['text']};
    padding: 4px;
}}

QDoubleSpinBox#bigNumberInput {{
    font-size: 24px;
    font-weight: 700;
    padding: 14px;
    border-radius: 10px;
    border: 2px solid {COLORS['primary']};
}}

QDoubleSpinBox::up-button, QDoubleSpinBox::down-button,
QSpinBox::up-button, QSpinBox::down-button {{
    width: 20px;
}}

QLabel#dialogLabel {{
    font-size: 15px;
    font-weight: 600;
    color: {COLORS['primary_dark']};
}}

/* ===================== عناوين وتسميات ===================== */
QLabel#titleLabel {{
    font-size: 21px;
    font-weight: 700;
    color: {COLORS['primary_dark']};
    padding: 2px 0;
}}

QLabel#clockLabel {{
    font-size: 13px;
    font-weight: 600;
    color: {COLORS['primary']};
    padding: 2px 10px;
    letter-spacing: 0.5px;
}}

QLabel#totalLabel {{
    font-size: 25px;
    font-weight: 800;
    color: {COLORS['primary_dark']};
    padding: 6px 0;
}}

/* ===================== الجداول ===================== */
QTableWidget {{
    background-color: {COLORS['white']};
    border: 1px solid {COLORS['border']};
    border-radius: 10px;
    gridline-color: {COLORS['bg_alt']};
    alternate-background-color: {COLORS['bg']};
    selection-background-color: {COLORS['accent_light']};
    selection-color: {COLORS['text']};
}}

QTableWidget::item {{
    padding: 6px;
    border-bottom: 1px solid {COLORS['bg_alt']};
}}

QHeaderView::section {{
    background-color: {COLORS['primary']};
    color: {COLORS['white']};
    padding: 10px 8px;
    border: none;
    font-weight: 700;
    font-size: 13px;
}}

QHeaderView::section:first {{
    border-top-right-radius: 10px;
}}
QHeaderView::section:last {{
    border-top-left-radius: 10px;
}}

/* ===================== تبويبات ===================== */
QTabWidget::pane {{
    border: 1px solid {COLORS['border']};
    border-radius: 10px;
    background-color: {COLORS['card_bg']};
    top: -1px;
}}

QTabBar::tab {{
    background: {COLORS['bg_alt']};
    color: {COLORS['text_muted']};
    padding: 11px 22px;
    margin: 2px 3px 0 3px;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    font-weight: 700;
    font-size: 13.5px;
}}

QTabBar::tab:hover {{
    background: {COLORS['accent_light']};
}}

QTabBar::tab:selected {{
    background: {COLORS['primary']};
    color: {COLORS['white']};
}}

/* ===================== بطاقات ===================== */
QFrame#card {{
    background-color: {COLORS['card_bg']};
    border-radius: 14px;
    border: 1px solid {COLORS['border']};
}}

/* ===================== قوائم ===================== */
QListWidget {{
    background-color: {COLORS['white']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    padding: 4px;
}}

QListWidget::item {{
    padding: 9px 8px;
    border-radius: 6px;
    margin: 2px;
}}

QListWidget::item:selected {{
    background-color: {COLORS['accent']};
    color: {COLORS['white']};
}}

QListWidget::item:hover {{
    background-color: {COLORS['accent_light']};
}}

/* ===================== نوافذ حوارية ===================== */
QDialog {{
    background-color: {COLORS['bg']};
}}

QDialogButtonBox QPushButton {{
    min-width: 90px;
}}

QRadioButton, QCheckBox {{
    font-size: 14px;
    padding: 4px;
    spacing: 8px;
}}

QRadioButton::indicator, QCheckBox::indicator {{
    width: 18px;
    height: 18px;
}}

/* ===================== أشرطة التمرير ===================== */
QScrollBar:vertical {{
    background: {COLORS['bg_alt']};
    width: 12px;
    border-radius: 6px;
}}
QScrollBar::handle:vertical {{
    background: {COLORS['accent']};
    border-radius: 6px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: {COLORS['primary']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    background: {COLORS['bg_alt']};
    height: 12px;
    border-radius: 6px;
}}
QScrollBar::handle:horizontal {{
    background: {COLORS['accent']};
    border-radius: 6px;
    min-width: 24px;
}}

/* ===================== شريط الحالة/التلميحات ===================== */
QToolTip {{
    background-color: {COLORS['primary_dark']};
    color: {COLORS['white']};
    border: none;
    padding: 6px 10px;
    border-radius: 6px;
    font-size: 12.5px;
}}

/* ===================== أزرار الاختصارات السريعة ===================== */
QPushButton#shortcutHintBtn {{
    background-color: {COLORS['bg_alt']};
    color: {COLORS['text_muted']};
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    padding: 2px 6px;
    font-size: 11px;
    min-height: 20px;
    max-height: 24px;
}}
QPushButton#shortcutHintBtn:hover {{
    background-color: {COLORS['primary']};
    color: {COLORS['white']};
    border-color: {COLORS['primary']};
}}
"""
