# ☕ Coffee POS — Offline Point of Sale System

<div align="center">

![Python](https://img.shields.io/badge/Python-3.8%2B-blue?style=for-the-badge&logo=python)
![PyQt5](https://img.shields.io/badge/PyQt5-5.15-41CD52?style=for-the-badge&logo=qt)
![SQLite](https://img.shields.io/badge/SQLite-18_Tables-003B57?style=for-the-badge&logo=sqlite)
![Windows](https://img.shields.io/badge/Windows-7_|_10_|_11-0078D6?style=for-the-badge&logo=windows)
![Offline](https://img.shields.io/badge/Offline-100%25_No_Cloud-success?style=for-the-badge)
![ESC/POS](https://img.shields.io/badge/Printer-ESC%2FPOS_Ready-orange?style=for-the-badge)

**A fully offline POS system for coffee shops and retail stores — built with Python + PyQt5 + SQLite.**  
**Runs without internet, supports thermal printers, and works on Windows 7 through 11.**

[Features](#-features) • [Quick Start](#-quick-start) • [Upgrading Windows](#-upgrading-from-windows-7-to-1011) • [Printer Setup](#-thermal-printer-setup) • [Project Structure](#-project-structure)

</div>

---

## 🎯 What does this system do?

A complete POS system designed for coffee shops and small retail stores — runs entirely without internet or cloud subscriptions.

Full business workflow:
**Login** ← **Open Shift** ← **Sell & Print Receipt** ← **Close Shift** ← **Daily/Monthly Reports**

---

## ✨ Features

| Feature | Details |
|---|---|
| 🔐 **Role-Based Access** | Admin / Cashier — forced password change on first login |
| 🛒 **Full POS Screen** | Categories + products + options (size, milk type...) + tax + discount |
| 📋 **Shift Management** | Open / close / resume a closed shift on the same day |
| 🖨️ **ESC/POS Printing** | Supports Epson, Xprinter, Rongta — USB and Serial |
| 📊 **Reports** | Daily, monthly, per-cashier performance |
| 💾 **Auto Backup** | Daily on startup — keeps last 30 backups |
| 📦 **Inventory** | Auto stock deduction on sale (when recipe is linked) |
| 📝 **Audit Log** | Every sensitive action logged with timestamp and user |
| 📤 **Excel Export** | Reports exportable to .xlsx |
| 🏗️ **EXE Build** | Ready script to build a distributable `.exe` without Python |
| ☁️ **100% Offline** | No internet, no subscription, no server |

---

## 🖥️ System Requirements

| OS | Python | Notes |
|---|---|---|
| Windows 7 | **3.8.x only** | Last official version supporting Win7 |
| Windows 10 | 3.8 – 3.12 | Any modern version works |
| Windows 11 | 3.8 – 3.12 | Any modern version works |

---

## 🚀 Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the system

```bash
python main.py
```

### 3. Default login credentials

| User | Username | Password | Role |
|---|---|---|---|
| System Admin | `admin` | `admin123` | Admin |
| Fareed | `fareed` | `1234` | Cashier |
| Sulaiman | `sulaiman` | `1234` | Cashier |

> ⚠️ **Important:** The system forces every user to change their password on first login — this screen cannot be skipped.

---

## 🔄 Upgrading from Windows 7 to 10 / 11

This system is designed from the ground up for smooth upgrades — **no reconfiguration or manual data migration needed.**

### Why is the upgrade easy?

The database is **not stored next to the program**, but in a fixed user folder:

```
Windows 7/10/11:
  C:\Users\<YourName>\AppData\Roaming\love.jo\coffee_pos.db
```

This folder is not deleted when reinstalling the program or upgrading to a new machine.

### Upgrade Steps (3 steps only)

**① Copy the database from the old machine:**
```
C:\Users\<YourName>\AppData\Roaming\love.jo\coffee_pos.db
```
Transfer it via USB or any storage medium.

**② On the new machine (Windows 10/11):**

Install Python (any version from 3.8 to 3.12):
```bash
pip install -r requirements.txt
```

**③ Place the database at the same path:**
```
C:\Users\<YourName>\AppData\Roaming\love.jo\coffee_pos.db
```

Then run the program — **all data is intact:** products, invoices, users, reports.

### Upgrading requirements.txt for modern systems

On Windows 10/11 you can use newer library versions:

```bash
# Instead of the Win7-restricted requirements.txt, install:
pip install PyQt5 pyserial pyinstaller pywin32 openpyxl
```

> Note: The original `requirements.txt` pins versions for Win7 only (`PyQt5==5.15.9`). On Win10/11 you can remove the version restrictions.

---

## 🖨️ Thermal Printer Setup

The system supports **3 connection types** and auto-detects the printer:

```
1. USB (Windows Spooler) ← Most common and easiest
2. Serial / COM Port     ← Older Serial printers
3. Simulation mode       ← No printer (never blocks a sale)
```

### USB Printer Setup:

1. Connect the printer and confirm it appears in **Devices and Printers**
2. Open **⚙️ Settings** from the POS screen
3. Select the printer name from the list
4. Press **Test Print**

### Supported Printers:

| Brand | Model | Recommended Encoding |
|---|---|---|
| Epson | TM-T20, TM-T82 | `cp864` |
| Xprinter | XP-58, XP-80 | `cp864` or `cp720` |
| Rongta | RP58, RP80 | `cp720` |
| Modern printers | Any model | `utf-8` |

> If you see boxes instead of Arabic characters: open `utils/printer.py` and move the correct encoding to the top of the list in `ENCODING_PRIORITY`.

---

## 📁 Project Structure

```
coffee_pos/
├── main.py                      # 🚀 Main entry point
├── requirements.txt             # 📦 Required libraries
├── build_exe.bat                # 🏗️ EXE build script for distribution
├── coffee_pos.spec              # ⚙️ PyInstaller configuration
│
├── database/
│   ├── db_setup.py              # 🗄️ Database schema (18 tables)
│   └── data_access.py           # 📖 All read/write operations
│
├── ui/
│   ├── style.py                 # 🎨 Coffee theme (colors and fonts)
│   ├── login_screen.py          # 🔐 Login screen
│   ├── pos_screen.py            # 🛒 Main POS screen
│   ├── shift_screen.py          # ⏰ Open / close shift
│   ├── products_screen.py       # 📦 Product and category management
│   ├── reports_screen.py        # 📊 Daily and monthly reports
│   ├── settings_screen.py       # ⚙️ Store and printer settings
│   ├── force_password_screen.py # 🔒 Forced password change
│   └── widgets.py               # 🧩 Shared UI components
│
└── utils/
    ├── printer.py               # 🖨️ ESC/POS printing (USB + Serial + Simulation)
    ├── backup.py                # 💾 Automatic daily backup
    ├── cash_drawer.py           # 💰 Cash drawer control
    ├── excel_export.py          # 📤 Export reports to Excel
    └── time_utils.py            # 🕐 Jordan timezone utilities
```

---

## 🗄️ Database

18 SQLite tables covering all system modules:

| Module | Tables |
|---|---|
| **Core** | users, products, categories, orders, order_items, shifts |
| **Financial** | payments, discounts, taxes, daily_close |
| **Inventory** | inventory, recipes, suppliers, purchases |
| **Customers** | customers, loyalty_points |
| **Admin** | audit_log, settings, backups |

---

## 🔒 Security

- Passwords hashed with **SHA-256 + random Salt** per user
- **Forced password change** on first login
- **Audit Log** for every sensitive action (delete, edit, discount, password reset)
- No data sent to any external server

---

## 📦 Building an EXE for Distribution

```bash
# Windows only
build_exe.bat
```

Produces `coffee_pos.exe` in the `dist/` folder — runs on any Windows machine **without installing Python**.

> Note: Data is stored in `AppData\Roaming\love.jo\` on the user's machine — not lost when updating the exe.

---

## ✅ Current Status

- [x] Login system with roles + random Salt
- [x] Full POS screen (categories, options, tax, discount)
- [x] Product management (add, edit, disable)
- [x] Reports screen (daily, monthly, cashier performance)
- [x] ESC/POS printing with auto encoding detection
- [x] Automatic daily backup
- [x] Excel export
- [x] Ready EXE build

### 🔜 Upcoming Features
- [ ] Daily expenses interface
- [ ] Inventory management + low stock alerts
- [ ] Supplier and purchase management
- [ ] Customer loyalty system
- [ ] Table management

---

## 🛠️ Tech Stack

`Python 3.8+` · `PyQt5` · `SQLite` · `pyserial` · `pywin32` · `openpyxl` · `PyInstaller`

---

<div align="center">
Built by <a href="https://github.com/yazanhamde">Yazan Hamdi</a> — Full Stack AI Engineer, Jordan 🇯🇴
<br><br>
<i>"Offline-first POS for real businesses — no subscriptions, no cloud, no surprises."</i>
</div>
