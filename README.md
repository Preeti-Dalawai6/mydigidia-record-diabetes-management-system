# 🩺 MyDigiDia Record

A web-based blood glucose tracking and diabetes management system built with **Flask** and **MySQL**. MyDigiDia Record lets users log glucose readings, visualize trends, generate reports, receive personalized diet guidance, and manage their health profile — all from a single, secure dashboard.

---

## 📋 Table of Contents

- [Description](#-description)
- [Features](#-features)
- [Technologies Used](#-technologies-used)
- [Project Structure](#-project-structure)
- [Installation](#-installation)
- [Database Setup](#-database-setup)
- [How to Run](#-how-to-run)
- [Future Improvements](#-future-improvements)
- [License](#-license)

---

## 📖 Description

**MyDigiDia Record** is a personal digital diabetes diary. It helps users record and monitor their blood glucose levels over time, understand patterns through charts and analytics, and get diet suggestions tailored to their most recent readings and age group. The app also supports importing historical data from **mySugr** CSV exports, so users switching from another tracker don't lose their history.

The system includes full user account management (signup, login via email or phone, OTP-based password reset), a customizable settings panel, and downloadable/exportable health reports — making it suitable as a lightweight personal health record or as a foundation for a larger telehealth platform.

---

## ✨ Features

- 🔐 **User Authentication** — sign up and log in with email or phone number; secure password hashing (SHA-256)
- 📧 **OTP-Based Password Recovery** — email one-time-passcodes for secure password resets
- 📊 **Glucose Tracking** — add, edit, and delete blood glucose readings with timestamps, meal timing, and notes
- 📈 **Interactive Reports & Analytics** — daily, weekly, monthly, custom-range, and all-time reports with averages, highs/lows, and in-range percentages
- 📉 **Charts** — line, bar, and pie chart endpoints (via Matplotlib) for visualizing glucose trends
- 🥗 **Smart Diet Suggestions** — diet recommendations generated from the user's latest reading and age group
- 📥 **mySugr CSV Import** — flexible parser that auto-detects glucose, date/time, notes, and carbohydrate columns from mySugr exports, with duplicate detection
- 👤 **Profile Management** — edit personal details, health info (diabetes type, doctor, emergency contact), and profile picture
- ⚙️ **Settings** — theme, language, glucose unit (mg/dL), notification preferences, reminder frequency, and privacy controls
- 🔔 **Notifications** — in-app notifications respecting each user's notification preferences
- 🧾 **PDF/Table Export Ready** — ReportLab integration for generating formatted report tables
- 🛡️ **Input Validation** — realistic email domain checks and Indian mobile number validation on signup

---

## 🛠️ Technologies Used

| Category         | Technology                                  |
|-------------------|----------------------------------------------|
| **Backend**       | Python 3, Flask                              |
| **Database**      | MySQL (via `mysql-connector-python`)         |
| **Data Processing**| Pandas, NumPy                               |
| **Charts/Reports**| Matplotlib, ReportLab                        |
| **Frontend**      | HTML5, CSS3, Jinja2 templates                |
| **Auth & Security**| Werkzeug, SHA-256 password hashing, SMTP OTP emails |
| **Config**        | python-dotenv (environment variables)        |

---

## 📁 Project Structure

```
MyDigiDia-Record/
├── app.py                  # Main Flask application (routes, DB logic, APIs)
├── requirements.txt        # Python dependencies
├── schema.sql              # MySQL schema — creates all required tables
├── .env.example            # Template for required environment variables
├── .gitignore
├── README.md
├── templates/               # Jinja2 HTML templates
│   ├── index.html            # Landing / login-choice page
│   ├── login.html
│   ├── signup.html
│   ├── forgot_password.html
│   ├── verify_otp.html
│   ├── reset_password.html
│   ├── main.html              # Dashboard
│   ├── record.html            # Add/view glucose readings
│   ├── reports.html           # Analytics & reports
│   ├── diet.html              # Diet recommendations
│   ├── profile.html
│   ├── settings.html
│   ├── mysugr_import.html     # CSV import page
│   ├── learn_more.html
│   └── help.html
└── static/
    ├── medical-bg.jpg
    └── uploads/               # User-uploaded files (profile pictures, CSVs)
```

---

## ⚙️ Installation

### Prerequisites

- Python 3.10+
- MySQL Server 8.0+ (or MariaDB equivalent)
- `pip` and `venv`

### Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/<your-username>/mydigidia-record.git
   cd mydigidia-record
   ```

2. **Create and activate a virtual environment**
   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   ```
   Then edit `.env` with your own database credentials and mail settings (see [Database Setup](#-database-setup) below).

---

## 🗄️ Database Setup

1. **Create the database and tables** using the provided schema file:
   ```bash
   mysql -u root -p < schema.sql
   ```
   This creates the `mydigidia_record` database along with the `users`, `glucose_readings`, `user_settings`, and `notifications` tables.

   > The app also self-heals older databases: on startup it checks for and automatically adds any missing optional columns (e.g. profile fields, notification settings), so existing installs stay compatible with new features.

2. **Set your database credentials** in `.env`:
   ```env
   DB_HOST=localhost
   DB_USER=root
   DB_PASSWORD=your_mysql_password
   DB_NAME=mydigidia_record
   ```

3. **Configure email for OTP password resets** (used by the forgot-password flow):
   ```env
   MAIL_SENDER_EMAIL=your-email@gmail.com
   MAIL_SENDER_APP_PASSWORD=your-16-character-gmail-app-password
   ```
   > ⚠️ **Security note:** Use a Gmail **App Password**, not your real account password, and never commit your `.env` file. `.env` is already excluded via `.gitignore`.

4. **Set a strong Flask secret key** in `.env`:
   ```env
   SECRET_KEY=a-long-random-string
   ```

---

## ▶️ How to Run

With your virtual environment activated and `.env` configured:

```bash
python app.py
```

The app will start in debug mode at:

```
http://localhost:5000
```

Open this URL in your browser, sign up for a new account, and start logging glucose readings.

---

## 🚀 Future Improvements

- [ ] Migrate password hashing from SHA-256 to a salted algorithm (e.g. bcrypt/argon2)
- [ ] Add JWT/session hardening and CSRF protection on all forms
- [ ] Replace SMTP-based OTP delivery with a transactional email service (e.g. SendGrid, SES)
- [ ] Add SMS OTP/notification support (Twilio) to match the existing SMS settings toggle
- [ ] Containerize the app with Docker Compose (Flask + MySQL)
- [ ] Add automated tests (pytest) and CI pipeline
- [ ] Build a REST API layer with token auth for a future mobile app
- [ ] Add data visualization dashboard using Chart.js/Plotly for richer, interactive charts
- [ ] Support multi-language UI (i18n), building on the existing language setting
- [ ] Add doctor/caregiver shared-access view based on the existing `profile_visibility`/`data_sharing` settings

---

## 📄 License

This project is licensed under the **MIT License**. You are free to use, modify, and distribute this software with attribution.

```
MIT License

Copyright (c) 2026 MyDigiDia Record

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

<p align="center">Built with ❤️ for better diabetes management.</p>
