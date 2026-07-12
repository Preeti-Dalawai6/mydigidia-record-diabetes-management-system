from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, request, redirect, session, flash, url_for, send_file, jsonify, make_response
import mysql.connector
from mysql.connector import Error
import hashlib
import os
import random
import re
import socket
import smtplib
from email.mime.text import MIMEText
from werkzeug.utils import secure_filename
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
from datetime import datetime, timedelta, date

try:
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
    from reportlab.lib import colors
except ImportError:
    pass

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-before-deployment")
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# ─────────────────────────────────────────────
# DATABASE CONNECTION
# ─────────────────────────────────────────────
def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host=os.environ.get("DB_HOST", "localhost"),
            user=os.environ.get("DB_USER", "root"),
            password=os.environ.get("DB_PASSWORD", ""),
            database=os.environ.get("DB_NAME", "mydigidia_record")
        )
        return conn
    except Error as e:
        print(f"[DB ERROR] {e}")
        return None

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$")
DISALLOWED_EMAIL_DOMAINS = {
    "example.com", "example.org", "example.net", "test.com", "fake.com",
    "mailinator.com", "tempmail.com", "10minutemail.com",
}
DEFAULT_SETTINGS = {
    "theme": "light",
    "language": "English",
    "email_notifications": 1,
    "sms_notifications": 0,
    "glucose_alerts": 1,
    "weekly_report": 0,
    "reminder_notifications": 1,
    "profile_visibility": 0,
    "data_sharing": 0,
    "auto_save": 1,
    "cloud_sync": 0,
    "glucose_unit": "mg/dL",
    "reminder_frequency": "daily",
    "emergency_contact": "",
    "daily_tracking": "4",
}

def email_domain_exists(domain):
    try:
        previous_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(3)
        socket.getaddrinfo(domain, None)
        return True
    except socket.gaierror:
        return False
    finally:
        socket.setdefaulttimeout(previous_timeout)

def is_realistic_email(email):
    if not email or len(email) > 254 or not EMAIL_PATTERN.match(email):
        return False
    local, domain = email.rsplit("@", 1)
    domain = domain.lower()
    labels = domain.split(".")
    if len(local) > 64 or domain in DISALLOWED_EMAIL_DOMAINS:
        return False
    if any(not label or label.startswith("-") or label.endswith("-") for label in labels):
        return False
    if len(labels[-1]) < 2:
        return False
    return email_domain_exists(domain)

def normalize_phone(phone):
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    return digits

def is_realistic_indian_mobile(phone):
    digits = normalize_phone(phone)
    if not re.fullmatch(r"[6-9]\d{9}", digits):
        return False
    if len(set(digits)) <= 2:
        return False
    if digits in {"9876543210", "9123456789", "1234567890", "0123456789"}:
        return False
    ascending = "01234567890123456789"
    descending = "98765432109876543210"
    if digits in ascending or digits in descending:
        return False
    return True

def ensure_user_profile_columns(db):
    """Create optional profile/health columns if an older database is missing them."""
    required_columns = {
        "gender": "VARCHAR(20) NULL",
        "date_of_birth": "DATE NULL",
        "profile_pic": "VARCHAR(255) NULL",
        "age": "INT NULL",
        "diabetes_type": "VARCHAR(50) NULL",
        "emergency_name": "VARCHAR(100) NULL",
        "emergency_phone": "VARCHAR(20) NULL",
        "doctor_name": "VARCHAR(150) NULL",
        "last_login": "DATETIME NULL",
    }
    cursor = db.cursor()
    cursor.execute("SHOW COLUMNS FROM users")
    existing_columns = {row[0] for row in cursor.fetchall()}
    for column, definition in required_columns.items():
        if column not in existing_columns:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {column} {definition}")
    db.commit()
    cursor.close()

def ensure_user_settings_table(db):
    cursor = db.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            theme VARCHAR(20) DEFAULT 'light',
            language VARCHAR(40) DEFAULT 'English',
            email_notifications TINYINT(1) DEFAULT 1,
            sms_notifications TINYINT(1) DEFAULT 0,
            glucose_alerts TINYINT(1) DEFAULT 1,
            weekly_report TINYINT(1) DEFAULT 0,
            reminder_notifications TINYINT(1) DEFAULT 1,
            profile_visibility TINYINT(1) DEFAULT 0,
            data_sharing TINYINT(1) DEFAULT 0,
            auto_save TINYINT(1) DEFAULT 1,
            cloud_sync TINYINT(1) DEFAULT 0,
            glucose_unit VARCHAR(20) DEFAULT 'mg/dL',
            reminder_frequency VARCHAR(30) DEFAULT 'daily',
            emergency_contact VARCHAR(30) NULL,
            daily_tracking VARCHAR(20) DEFAULT '4',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY unique_user_settings (user_id)
        )
    """)
    required_columns = {
        "theme": "VARCHAR(20) DEFAULT 'light'",
        "language": "VARCHAR(40) DEFAULT 'English'",
        "email_notifications": "TINYINT(1) DEFAULT 1",
        "sms_notifications": "TINYINT(1) DEFAULT 0",
        "glucose_alerts": "TINYINT(1) DEFAULT 1",
        "weekly_report": "TINYINT(1) DEFAULT 0",
        "reminder_notifications": "TINYINT(1) DEFAULT 1",
        "profile_visibility": "TINYINT(1) DEFAULT 0",
        "data_sharing": "TINYINT(1) DEFAULT 0",
        "auto_save": "TINYINT(1) DEFAULT 1",
        "cloud_sync": "TINYINT(1) DEFAULT 0",
        "glucose_unit": "VARCHAR(20) DEFAULT 'mg/dL'",
        "reminder_frequency": "VARCHAR(30) DEFAULT 'daily'",
        "emergency_contact": "VARCHAR(30) NULL",
        "daily_tracking": "VARCHAR(20) DEFAULT '4'",
        "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
    }
    cursor.execute("SHOW COLUMNS FROM user_settings")
    existing_columns = {row[0] for row in cursor.fetchall()}
    for column, definition in required_columns.items():
        if column not in existing_columns:
            cursor.execute(f"ALTER TABLE user_settings ADD COLUMN {column} {definition}")
    db.commit()
    cursor.close()

# ─────────────────────────────────────────────
# NOTIFICATION FUNCTION
# ─────────────────────────────────────────────
def ensure_glucose_readings_columns(db):
    """Keep older glucose_readings tables compatible with records and reports."""
    required_columns = {
        "device_id": "INT NULL",
        "status": "VARCHAR(20) DEFAULT 'normal'",
        "notes": "TEXT NULL",
        "meal_timing": "VARCHAR(50) NULL",
    }
    cursor = db.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS glucose_readings (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            device_id INT NULL,
            glucose_level FLOAT NOT NULL,
            reading_time DATETIME NOT NULL,
            status VARCHAR(20) DEFAULT 'normal',
            notes TEXT NULL,
            meal_timing VARCHAR(50) NULL,
            INDEX idx_user_reading_time (user_id, reading_time)
        )
    """)
    cursor.execute("SHOW COLUMNS FROM glucose_readings")
    existing_columns = {row[0] for row in cursor.fetchall()}
    for column, definition in required_columns.items():
        if column not in existing_columns:
            cursor.execute(f"ALTER TABLE glucose_readings ADD COLUMN {column} {definition}")
    db.commit()
    cursor.close()

def create_notification(user_id, message, type="system"):
    db = get_db_connection()
    if db is None:
        return
    ensure_user_settings_table(db)
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT email_notifications, sms_notifications FROM user_settings WHERE user_id=%s", (user_id,))
    settings = cursor.fetchone()
    if not settings or (not settings['email_notifications'] and not settings['sms_notifications']):
        cursor.close(); db.close(); return
    cursor.execute("INSERT INTO notifications (user_id, message, type) VALUES (%s, %s, %s)", (user_id, message, type))
    db.commit(); cursor.close(); db.close()

# ─────────────────────────────────────────────
# SEND OTP EMAIL
# ─────────────────────────────────────────────
def send_otp_email(to_email, otp):
    sender_email = os.environ.get("MAIL_SENDER_EMAIL")
    sender_password = os.environ.get("MAIL_SENDER_APP_PASSWORD")
    if not sender_email or not sender_password:
        raise RuntimeError(
            "Email is not configured. Set MAIL_SENDER_EMAIL and MAIL_SENDER_APP_PASSWORD "
            "environment variables (see README.md)."
        )
    msg = MIMEText(f"Your OTP is: {otp}")
    msg['Subject'] = "Password Reset OTP"
    msg['From'] = sender_email
    msg['To'] = to_email
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(sender_email, sender_password)
    server.send_message(msg)
    server.quit()

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def get_glucose_status(level):
    if level < 70:
        return 'low'
    elif level <= 140:
        return 'normal'
    else:
        return 'high'

def get_readings(user_id, from_dt, to_dt):
    db = get_db_connection()
    if db is None:
        return []
    ensure_glucose_readings_columns(db)
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, glucose_level, reading_time, status, notes, meal_timing
        FROM glucose_readings
        WHERE user_id = %s AND reading_time BETWEEN %s AND %s
        ORDER BY reading_time DESC
    """, (user_id, from_dt, to_dt))
    rows = cursor.fetchall()
    cursor.close(); db.close()
    for r in rows:
        if isinstance(r['reading_time'], datetime):
            r['reading_time'] = r['reading_time'].strftime('%Y-%m-%d %H:%M:%S')
    return rows

def get_all_readings(user_id):
    db = get_db_connection()
    if db is None:
        return []
    ensure_glucose_readings_columns(db)
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, glucose_level, reading_time, status, notes, meal_timing
        FROM glucose_readings
        WHERE user_id = %s
        ORDER BY reading_time DESC
    """, (user_id,))
    rows = cursor.fetchall()
    cursor.close(); db.close()
    for r in rows:
        if isinstance(r['reading_time'], datetime):
            r['reading_time'] = r['reading_time'].strftime('%Y-%m-%d %H:%M:%S')
    return rows

def compute_analytics(readings):
    if not readings:
        return {"total":0,"average":0,"max":0,"min":0,"normal_count":0,"high_count":0,"low_count":0,"normal_pct":0,"high_pct":0,"low_pct":0}
    levels = [r['glucose_level'] for r in readings]
    total  = len(levels)
    avg    = round(sum(levels)/total, 1)
    low_c  = sum(1 for v in levels if v < 70)
    norm_c = sum(1 for v in levels if 70 <= v <= 140)
    high_c = sum(1 for v in levels if v > 140)
    return {"total":total,"average":avg,"max":max(levels),"min":min(levels),
            "normal_count":norm_c,"high_count":high_c,"low_count":low_c,
            "normal_pct":round(norm_c/total*100,1),"high_pct":round(high_c/total*100,1),"low_pct":round(low_c/total*100,1)}

# ─────────────────────────────────────────────
# AUTH ROUTES
# ─────────────────────────────────────────────
@app.route('/forgot_password', methods=['GET','POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        db = get_db_connection(); cursor = db.cursor()
        cursor.execute("SELECT user_id FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()
        cursor.close(); db.close()
        if not user:
            flash("Email not found","error")
            return render_template('forgot_password.html')
        import time
        otp = str(random.randint(100000,999999))
        session['reset_email'] = email; session['otp'] = otp; session['otp_time'] = time.time()
        session.pop('otp_verified', None)
        send_otp_email(email, otp)
        return redirect('/verify_otp')
    return render_template('forgot_password.html')

@app.route('/verify_otp', methods=['GET','POST'])
def verify_otp():
    if not session.get('reset_email') or not session.get('otp'):
        flash("Please enter your email first.","error")
        return redirect('/forgot_password')
    if request.method == 'POST':
        import time
        if time.time() - session.get('otp_time',0) > 60:
            flash("OTP expired.","error"); return redirect('/forgot_password')
        if request.form.get('otp', '').strip() == session.get('otp'):
            session['otp_verified'] = True
            return redirect('/reset_password')
        flash("Invalid OTP","error")
    return render_template('verify_otp.html')

@app.route('/resend_otp')
def resend_otp():
    if not session.get('reset_email'):
        flash("Please enter your email first.","error")
        return redirect('/forgot_password')
    import time
    if time.time() - session.get('otp_time',0) < 30:
        flash("Please wait before requesting again.","error"); return redirect('/verify_otp')
    otp = str(random.randint(100000,999999))
    session['otp'] = otp; session['otp_time'] = time.time()
    session.pop('otp_verified', None)
    send_otp_email(session.get('reset_email'), otp)
    flash("OTP resent!","success"); return redirect('/verify_otp')

@app.route('/reset_password', methods=['GET','POST'])
def reset_password():
    if not session.get('reset_email') or not session.get('otp_verified'):
        flash("Please verify the OTP first.","error")
        return redirect('/forgot_password')
    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        if password != confirm_password:
            flash("Passwords do not match.","error")
            return render_template('reset_password.html')
        if len(password) < 6:
            flash("Password must be at least 6 characters.","error")
            return render_template('reset_password.html')
        db = get_db_connection(); cursor = db.cursor()
        cursor.execute("UPDATE users SET password_hash=%s WHERE email=%s",
                       (hash_password(password), session.get('reset_email')))
        db.commit(); cursor.close(); db.close()
        session.pop('otp',None); session.pop('otp_time',None); session.pop('reset_email',None); session.pop('otp_verified',None)
        flash("Password updated!","success"); return redirect('/login_page')
    return render_template('reset_password.html')

@app.route('/debug')
def debug():
    db = get_db_connection()
    if db is None:
        return "<h2 style='color:red'>Database connection failed.</h2>"
    cursor = db.cursor(); cursor.execute("SHOW TABLES"); tables = cursor.fetchall()
    try:
        cursor.execute("SELECT user_id, name, email FROM users"); users = cursor.fetchall()
    except Exception as e:
        users = [("ERROR", str(e), "")]
    cursor.close(); db.close()
    html = "<h2>Database Connected</h2>"
    html += f"<p>Tables: {tables}</p><h3>Users:</h3><table border='1' cellpadding='8'>"
    html += "<tr><th>ID</th><th>Name</th><th>Email</th></tr>"
    for u in users:
        html += f"<tr><td>{u[0]}</td><td>{u[1]}</td><td>{u[2]}</td></tr>"
    html += "</table><br><a href='/'>Back</a>"
    return html

# ─────────────────────────────────────────────
# MAIN PAGE
# ─────────────────────────────────────────────
@app.route('/')
def main():
    user = session.get('user')
    return render_template('main.html', user=user)

@app.route('/login_page')
def login_page():
    return render_template('index.html')

@app.route('/index')
def index():
    return render_template('index.html')

# ─────────────────────────────────────────────
# LOGIN
# ─────────────────────────────────────────────
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email','').strip()
        password = request.form.get('password','').strip()
        if not email or not password:
            flash("Please fill in all fields.","error")
            return render_template('login.html')
        db = get_db_connection()
        if db is None:
            flash("Database connection failed.","error")
            return render_template('login.html')
        ensure_user_profile_columns(db)
        cursor = db.cursor()
        cursor.execute("SELECT user_id, name FROM users WHERE email=%s AND password_hash=%s",
                       (email, hash_password(password)))
        user = cursor.fetchone()
        if not user:
            cursor.execute("SELECT user_id, name FROM users WHERE email=%s AND password_hash=%s",
                           (email, password))
            user = cursor.fetchone()
            if user:
                cursor.execute("UPDATE users SET password_hash=%s WHERE user_id=%s",
                               (hash_password(password), user[0]))
                db.commit()
        if user:
            cursor.execute("UPDATE users SET last_login=NOW() WHERE user_id=%s", (user[0],))
            db.commit()
            session['user_id'] = user[0]; session['user'] = user[1]
            cursor.close(); db.close()
            return redirect('/')
        cursor.close(); db.close()
        flash("Invalid email or password.","error")
    return render_template('login.html')

@app.route('/phone_login', methods=['POST'])
def phone_login():
    phone = request.form.get('phone','').strip()
    password = request.form.get('password','').strip()
    if not phone or not password:
        flash("Please enter phone and password.","error"); return redirect('/login_page')
    db = get_db_connection()
    if db is None:
        flash("Database connection failed.","error"); return redirect('/login_page')
    ensure_user_profile_columns(db)
    cursor = db.cursor()
    cursor.execute("SELECT user_id, name FROM users WHERE phone=%s AND password_hash=%s",
                   (phone, hash_password(password)))
    user = cursor.fetchone()
    if not user:
        cursor.execute("SELECT user_id, name FROM users WHERE phone=%s AND password_hash=%s",
                       (phone, password))
        user = cursor.fetchone()
        if user:
            cursor.execute("UPDATE users SET password_hash=%s WHERE user_id=%s",
                           (hash_password(password), user[0]))
            db.commit()
    if user:
        cursor.execute("UPDATE users SET last_login=NOW() WHERE user_id=%s", (user[0],))
        db.commit()
        session['user_id'] = user[0]; session['user'] = user[1]
        cursor.close(); db.close()
        return redirect('/')
    cursor.close(); db.close()
    flash("Invalid phone or password.","error"); return redirect('/login_page')

# ─────────────────────────────────────────────
# SIGNUP
# ─────────────────────────────────────────────
@app.route('/signup', methods=['GET','POST'])
def signup():
    if request.method == 'GET':
        session.pop('user_id', None)
        session.pop('user', None)
        response = make_response(render_template('signup.html'))
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    if request.method == 'POST':
        name = request.form.get('name','').strip()
        email = request.form.get('email','').strip().lower()
        phone = normalize_phone(request.form.get('phone','').strip())
        password = request.form.get('password','').strip()
        confirm_password = request.form.get('confirm_password','').strip()
        if not all([name,email,phone,password,confirm_password]):
            flash("All fields are required.","error"); return render_template('signup.html')
        if not is_realistic_email(email):
            flash("Please enter a valid email with an existing mail domain.","error"); return render_template('signup.html')
        if not is_realistic_indian_mobile(phone):
            flash("Please enter a valid Indian mobile number.","error"); return render_template('signup.html')
        if password != confirm_password:
            flash("Passwords do not match.","error"); return render_template('signup.html')
        db = get_db_connection()
        if db is None:
            flash("Database connection failed.","error"); return render_template('signup.html')
        ensure_user_profile_columns(db)
        cursor = db.cursor()
        cursor.execute("SELECT user_id FROM users WHERE email=%s", (email,))
        if cursor.fetchone():
            flash("Email already registered.","error"); cursor.close(); db.close()
            return render_template('signup.html')
        cursor.execute("SELECT user_id FROM users WHERE phone=%s", (phone,))
        if cursor.fetchone():
            flash("Phone number already registered.","error"); cursor.close(); db.close()
            return render_template('signup.html')
        cursor.execute("INSERT INTO users (name, email, phone, password_hash, last_login) VALUES (%s,%s,%s,%s,NOW())",
                       (name, email, phone, hash_password(password)))
        db.commit(); new_id = cursor.lastrowid
        cursor.close(); db.close()
        session['user_id'] = new_id; session['user'] = name
        return redirect('/')

@app.route('/logout')
def logout():
    session.clear(); return redirect('/')

# ─────────────────────────────────────────────
# LEARN MORE / HELP
# ─────────────────────────────────────────────
@app.route('/learn_more')
def learn_more():
    return render_template('learn_more.html')

@app.route('/help')
def help_page():
    return render_template('help.html')

# ─────────────────────────────────────────────
# RECORDS PAGE
# ─────────────────────────────────────────────
@app.route('/record')
def record():
    if not session.get('user_id'):
        return redirect('/login_page')
    return render_template('record.html')

# ─────────────────────────────────────────────
# ─────────────────────────────────────────────
# GLUCOSE API — ADD  (Manual Entry)
# ─────────────────────────────────────────────
@app.route('/api/glucose/add', methods=['POST'])
def api_glucose_add():
    """Receive a manual glucose reading from the frontend and insert it into MySQL."""
    if not session.get('user_id'):
        return jsonify({'success': False, 'error': 'Not logged in. Please refresh and log in again.'}), 401

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'error': 'Invalid JSON payload.'}), 400

    glucose_raw = data.get('glucose_level')
    date_str    = data.get('date', '').strip()
    time_str    = data.get('time', '').strip()
    notes       = (data.get('notes') or '').strip()
    meal_timing = (data.get('meal_timing') or '').strip()

    # ── Server-side validation ──────────────────
    if glucose_raw is None or date_str == '' or time_str == '':
        return jsonify({'success': False, 'error': 'Glucose level, date and time are required.'}), 400
    try:
        glucose_level = float(glucose_raw)
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'Glucose level must be a numeric value.'}), 400
    if not (20 <= glucose_level <= 600):
        return jsonify({'success': False, 'error': 'Glucose level must be between 20 and 600 mg/dL.'}), 400
    try:
        reading_time = datetime.strptime(f"{date_str} {time_str}", '%Y-%m-%d %H:%M')
    except ValueError:
        return jsonify({'success': False, 'error': 'Invalid date or time format received.'}), 400

    status = get_glucose_status(glucose_level)

    db = get_db_connection()
    if db is None:
        return jsonify({'success': False, 'error': 'Database connection failed. Please try again shortly.'}), 500
    ensure_glucose_readings_columns(db)

    cursor = None
    try:
        cursor = db.cursor()
        cursor.execute(
            """
            INSERT INTO glucose_readings
                (user_id, glucose_level, reading_time, status, notes, meal_timing)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (session['user_id'], glucose_level, reading_time, status,
             notes if notes else None,
             meal_timing if meal_timing else None)
        )
        db.commit()
        new_id = cursor.lastrowid
        return jsonify({'success': True, 'message': 'Reading saved successfully.', 'id': new_id}), 201
    except Exception as e:
        db.rollback()
        print(f"[api_glucose_add] DB error: {e}")
        return jsonify({'success': False, 'error': 'Failed to save reading. Please try again.'}), 500
    finally:
        if cursor:  cursor.close()
        db.close()


# ─────────────────────────────────────────────
# GLUCOSE API — UPDATE
# ─────────────────────────────────────────────
@app.route('/api/glucose/update/<int:reading_id>', methods=['POST'])
def api_glucose_update(reading_id):
    """Update an existing glucose reading that belongs to the logged-in user."""
    if not session.get('user_id'):
        return jsonify({'success': False, 'error': 'Not logged in.'}), 401

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'error': 'Invalid JSON payload.'}), 400

    glucose_raw = data.get('glucose_level')
    date_str    = data.get('date', '').strip()
    time_str    = data.get('time', '').strip()
    notes       = (data.get('notes') or '').strip()
    meal_timing = (data.get('meal_timing') or '').strip()

    if glucose_raw is None or date_str == '' or time_str == '':
        return jsonify({'success': False, 'error': 'Glucose level, date and time are required.'}), 400
    try:
        glucose_level = float(glucose_raw)
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'Glucose level must be a numeric value.'}), 400
    if not (20 <= glucose_level <= 600):
        return jsonify({'success': False, 'error': 'Glucose level must be between 20 and 600 mg/dL.'}), 400
    try:
        reading_time = datetime.strptime(f"{date_str} {time_str}", '%Y-%m-%d %H:%M')
    except ValueError:
        return jsonify({'success': False, 'error': 'Invalid date or time format.'}), 400

    status = get_glucose_status(glucose_level)

    db = get_db_connection()
    if db is None:
        return jsonify({'success': False, 'error': 'Database connection failed.'}), 500
    ensure_glucose_readings_columns(db)

    cursor = None
    try:
        cursor = db.cursor()
        cursor.execute(
            """
            UPDATE glucose_readings
               SET glucose_level = %s,
                   reading_time  = %s,
                   status        = %s,
                   notes         = %s,
                   meal_timing   = %s
             WHERE id      = %s
               AND user_id = %s
            """,
            (glucose_level, reading_time, status,
             notes if notes else None,
             meal_timing if meal_timing else None,
             reading_id, session['user_id'])
        )
        db.commit()
        if cursor.rowcount == 0:
            return jsonify({'success': False, 'error': 'Reading not found or permission denied.'}), 404
        return jsonify({'success': True, 'message': 'Reading updated successfully.'})
    except Exception as e:
        db.rollback()
        print(f"[api_glucose_update] DB error: {e}")
        return jsonify({'success': False, 'error': 'Failed to update reading.'}), 500
    finally:
        if cursor:  cursor.close()
        db.close()


# ─────────────────────────────────────────────
# GLUCOSE API — DELETE
# ─────────────────────────────────────────────
@app.route('/api/glucose/delete/<int:reading_id>', methods=['POST'])
def api_glucose_delete(reading_id):
    """Permanently delete a glucose reading that belongs to the logged-in user."""
    if not session.get('user_id'):
        return jsonify({'success': False, 'error': 'Not logged in.'}), 401

    db = get_db_connection()
    if db is None:
        return jsonify({'success': False, 'error': 'Database connection failed.'}), 500
    ensure_glucose_readings_columns(db)

    cursor = None
    try:
        cursor = db.cursor()
        cursor.execute(
            "DELETE FROM glucose_readings WHERE id = %s AND user_id = %s",
            (reading_id, session['user_id'])
        )
        db.commit()
        if cursor.rowcount == 0:
            return jsonify({'success': False, 'error': 'Reading not found or permission denied.'}), 404
        return jsonify({'success': True, 'message': 'Reading deleted.'})
    except Exception as e:
        db.rollback()
        print(f"[api_glucose_delete] DB error: {e}")
        return jsonify({'success': False, 'error': 'Failed to delete reading.'}), 500
    finally:
        if cursor:  cursor.close()
        db.close()


# ─────────────────────────────────────────────
# GLUCOSE API — LIST
# ─────────────────────────────────────────────
@app.route('/api/glucose/list')
def api_glucose_list():
    """Return all glucose readings for the logged-in user, sorted latest first."""
    if not session.get('user_id'):
        return jsonify({'success': False, 'error': 'Not logged in.'}), 401

    db = get_db_connection()
    if db is None:
        return jsonify({'success': False, 'error': 'Database connection failed.'}), 500
    ensure_glucose_readings_columns(db)

    cursor = None
    try:
        cursor = db.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id,
                   glucose_level,
                   reading_time,
                   status,
                   COALESCE(notes, '')       AS notes,
                   COALESCE(meal_timing, '') AS meal_timing
              FROM glucose_readings
             WHERE user_id = %s
             ORDER BY reading_time DESC
            """,
            (session['user_id'],)
        )
        rows = cursor.fetchall()
        # Serialise datetime objects so JSON encoder handles them
        for r in rows:
            if isinstance(r['reading_time'], datetime):
                r['reading_time'] = r['reading_time'].strftime('%Y-%m-%d %H:%M:%S')
            r['glucose_level'] = float(r['glucose_level'])
        return jsonify({'success': True, 'readings': rows})
    except Exception as e:
        print(f"[api_glucose_list] DB error: {e}")
        return jsonify({'success': False, 'error': 'Failed to fetch readings.'}), 500
    finally:
        if cursor:  cursor.close()
        db.close()

# ─────────────────────────────────────────────
# PROFILE
# ─────────────────────────────────────────────
@app.route('/profile')
def profile():
    if not session.get('user_id'):
        return redirect('/login_page')
    db = get_db_connection()
    if db is None:
        flash("Database connection failed.","error")
        return redirect('/')
    ensure_user_profile_columns(db)
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE user_id=%s", (session['user_id'],))
    user = cursor.fetchone()
    cursor.close(); db.close()
    return render_template('profile.html', user=user)

@app.route('/update_profile', methods=['POST'])
def update_profile():
    if 'user_id' not in session:
        return redirect('/login_page')
    name   = request.form.get('name')
    phone  = request.form.get('phone')
    gender = request.form.get('gender')
    dob    = request.form.get('dob') or None
    db = get_db_connection()
    if db is None:
        flash("Database connection failed.","error")
        return redirect('/profile')
    ensure_user_profile_columns(db)
    cursor = db.cursor()
    file = request.files.get('profile_pic')
    remove_photo = request.form.get('remove_photo')
    filename = None
    if remove_photo:
        filename = None
    elif file and file.filename != "":
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    cursor.execute("""
        UPDATE users
        SET name=%s, phone=%s, gender=%s, date_of_birth=%s,
            profile_pic = CASE WHEN %s IS NULL THEN NULL WHEN %s != '' THEN %s ELSE profile_pic END
        WHERE user_id=%s
    """, (name, phone, gender, dob, filename, filename, filename, session['user_id']))
    db.commit(); cursor.close(); db.close()
    flash("Profile updated successfully!","success")
    return redirect('/profile')

# ─────────────────────────────────────────────
# UPDATE HEALTH INFO (NEW)
# ─────────────────────────────────────────────
@app.route('/update_health_info', methods=['POST'])
def update_health_info():
    if 'user_id' not in session:
        return redirect('/login_page')
    age             = request.form.get('age') or None
    diabetes_type   = request.form.get('diabetes_type') or None
    emergency_name  = request.form.get('emergency_name') or None
    emergency_phone = request.form.get('emergency_phone') or None
    doctor_name     = request.form.get('doctor_name') or None
    db = get_db_connection()
    if db is None:
        flash("Database connection failed.","error")
        return redirect('/profile')
    cursor = None
    # Try to update; columns may not exist — handle gracefully
    try:
        ensure_user_profile_columns(db)
        cursor = db.cursor()
        cursor.execute("""
            UPDATE users
            SET age=%s, diabetes_type=%s, emergency_name=%s, emergency_phone=%s, doctor_name=%s
            WHERE user_id=%s
        """, (age, diabetes_type, emergency_name, emergency_phone, doctor_name, session['user_id']))
        db.commit()
        flash("Health info updated successfully!","success")
    except Exception as e:
        print(f"[update_health_info] DB error: {e}")
        flash("Could not save health info. Please check the database.","error")
    finally:
        if cursor:
            cursor.close()
        db.close()
    return redirect('/profile')

@app.route('/change_password', methods=['POST'])
def change_password():
    if 'user_id' not in session:
        return redirect('/profile')
    current = request.form.get('current_password')
    new     = request.form.get('new_password')
    db = get_db_connection(); cursor = db.cursor()
    cursor.execute("SELECT password_hash FROM users WHERE user_id=%s", (session['user_id'],))
    user = cursor.fetchone()
    if user[0] != hash_password(current):
        flash("Current password is incorrect","error"); return redirect('/profile')
    cursor.execute("UPDATE users SET password_hash=%s WHERE user_id=%s",
                   (hash_password(new), session['user_id']))
    db.commit(); cursor.close(); db.close()
    flash("Password changed successfully!","success"); return redirect('/profile')

@app.route('/delete_account', methods=['POST'])
def delete_account():
    if 'user_id' not in session:
        return redirect('/login_page')
    db = get_db_connection(); cursor = db.cursor()
    cursor.execute("DELETE FROM users WHERE user_id=%s", (session['user_id'],))
    db.commit(); cursor.close(); db.close()
    session.clear()
    flash("Your account has been deleted.","success"); return redirect('/')

# ─────────────────────────────────────────────
# SETTINGS
# ─────────────────────────────────────────────
@app.route('/settings')
def settings():
    if 'user_id' not in session:
        return redirect('/login_page')
    db = get_db_connection()
    if not db:
        flash("Database connection failed.", "error")
        return redirect('/')
    cursor = None
    try:
        ensure_user_settings_table(db)
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM user_settings WHERE user_id=%s", (session['user_id'],))
        settings_row = cursor.fetchone()
        if not settings_row:
            # Create default settings row for new user
            cursor.execute("""
                INSERT INTO user_settings
                (user_id, theme, language, email_notifications, sms_notifications,
                 glucose_alerts, weekly_report, reminder_notifications,
                 profile_visibility, data_sharing, auto_save, cloud_sync,
                 glucose_unit, reminder_frequency, daily_tracking)
                VALUES (%s, 'light', 'English', 1, 0, 1, 0, 1, 0, 0, 1, 0, 'mg/dL', 'daily', '4')
            """, (session['user_id'],))
            db.commit()
            cursor.execute("SELECT * FROM user_settings WHERE user_id=%s", (session['user_id'],))
            settings_row = cursor.fetchone()
        settings_row = {**DEFAULT_SETTINGS, **(settings_row or {})}
        return render_template('settings.html', settings=settings_row)
    except Exception as e:
        print(f"[settings] DB error: {e}")
        db.rollback()
        flash("Settings table was repaired. Please refresh if the page does not load normally.", "error")
        return render_template('settings.html', settings=DEFAULT_SETTINGS)
    finally:
        if cursor:
            cursor.close()
        db.close()


@app.route('/save_settings', methods=['POST'])
def save_settings():
    if 'user_id' not in session:
        return redirect('/login_page')
    db = get_db_connection()
    if not db:
        flash("Database connection failed.", "error")
        return redirect('/settings')
    try:
        ensure_user_settings_table(db)
        theme                  = request.form.get('theme', 'light')
        language               = request.form.get('language', 'English')
        email_notifications    = 1 if request.form.get('email_notifications')    else 0
        sms_notifications      = 1 if request.form.get('sms_notifications')      else 0
        glucose_alerts         = 1 if request.form.get('glucose_alerts')         else 0
        weekly_report          = 1 if request.form.get('weekly_report')          else 0
        reminder_notifications = 1 if request.form.get('reminder_notifications') else 0
        profile_visibility     = 1 if request.form.get('profile_visibility')     else 0
        data_sharing           = 1 if request.form.get('data_sharing')           else 0
        auto_save              = 1 if request.form.get('auto_save')              else 0
        cloud_sync             = 1 if request.form.get('cloud_sync')             else 0
        glucose_unit           = request.form.get('glucose_unit', 'mg/dL')
        reminder_frequency     = request.form.get('reminder_frequency', 'daily')
        emergency_contact      = request.form.get('emergency_contact') or None
        daily_tracking         = request.form.get('daily_tracking', '4')

        cursor = db.cursor()
        # Upsert: update if exists, insert if not
        cursor.execute("SELECT user_id FROM user_settings WHERE user_id=%s", (session['user_id'],))
        existing = cursor.fetchone()
        if existing:
            cursor.execute("""
                UPDATE user_settings SET
                  theme=%s, language=%s,
                  email_notifications=%s, sms_notifications=%s,
                  glucose_alerts=%s, weekly_report=%s, reminder_notifications=%s,
                  profile_visibility=%s,  data_sharing=%s,
                  auto_save=%s,           cloud_sync=%s,
                  glucose_unit=%s, reminder_frequency=%s,
                  emergency_contact=%s, daily_tracking=%s
                WHERE user_id=%s
            """, (theme, language,
                  email_notifications, sms_notifications,
                  glucose_alerts, weekly_report, reminder_notifications,
                  profile_visibility,  data_sharing,
                  auto_save,           cloud_sync,
                  glucose_unit, reminder_frequency,
                  emergency_contact, daily_tracking,
                  session['user_id']))
        else:
            cursor.execute("""
                INSERT INTO user_settings
                  (user_id, theme, language, email_notifications, sms_notifications,
                   glucose_alerts, weekly_report, reminder_notifications,
                   profile_visibility, data_sharing, auto_save, cloud_sync,
                   glucose_unit, reminder_frequency, emergency_contact, daily_tracking)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (session['user_id'], theme, language,
                  email_notifications, sms_notifications,
                  glucose_alerts, weekly_report, reminder_notifications,
                  profile_visibility,  data_sharing,
                  auto_save,           cloud_sync,
                  glucose_unit, reminder_frequency,
                  emergency_contact, daily_tracking))
        db.commit()
        cursor.close()
        flash("Settings saved successfully!", "success")
    except Exception as e:
        flash(f"Error saving settings: {str(e)}", "error")
    finally:
        db.close()
    return redirect('/settings')

# ─────────────────────────────────────────────
# DIET
# ─────────────────────────────────────────────
@app.route('/diet')
def diet():
    if 'user_id' not in session:
        return redirect('/login_page')
    user_id = session['user_id']
    conn = get_db_connection()
    if not conn:
        return "Database connection failed"
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE user_id=%s", (user_id,))
    user = cursor.fetchone()
    cursor.execute("SELECT glucose_level FROM glucose_readings WHERE user_id=%s ORDER BY reading_time DESC LIMIT 1", (user_id,))
    record = cursor.fetchone()
    glucose = record['glucose_level'] if record else None
    age = None
    if user and user.get('date_of_birth'):
        today = date.today()
        age = today.year - user['date_of_birth'].year
    if glucose is None:
        diet_type = "No Data"
    elif glucose < 70:
        diet_type = "Low Sugar Diet"
    elif 70 <= glucose <= 140:
        if age and age < 30:
            diet_type = "Normal Diet (Young)"
        elif age and age < 50:
            diet_type = "Normal Diet (Adult)"
        else:
            diet_type = "Normal Diet (Senior)"
    else:
        diet_type = "High Sugar Control Diet"
    cursor.close(); conn.close()
    return render_template('diet.html', user=user, glucose=glucose, diet_type=diet_type)

# ─────────────────────────────────────────────
# REPORTS
# ─────────────────────────────────────────────
@app.route('/reports_page')
def reports_page():
    if not session.get('user_id'):
        return redirect('/login_page')
    return render_template('reports.html')

@app.route('/api/report/daily')
def api_daily_report():
    if not session.get('user_id'):
        return jsonify({"error":"Unauthorized"}), 401
    now = datetime.now()
    start = now.replace(hour=0,minute=0,second=0,microsecond=0)
    readings = get_readings(session['user_id'], start, now)
    analytics = compute_analytics(readings)
    return jsonify({"period":"daily","from":start.strftime('%Y-%m-%d'),"to":now.strftime('%Y-%m-%d %H:%M'),"readings":readings,"analytics":analytics})

@app.route('/api/report/all')
def api_all_report():
    if not session.get('user_id'):
        return jsonify({"error":"Unauthorized"}), 401
    readings = get_all_readings(session['user_id'])
    analytics = compute_analytics(readings)
    date_from = readings[-1]['reading_time'][:10] if readings else None
    date_to = readings[0]['reading_time'][:10] if readings else None
    return jsonify({"period":"all","from":date_from,"to":date_to,"readings":readings,"analytics":analytics})

@app.route('/api/report/weekly')
def api_weekly_report():
    if not session.get('user_id'):
        return jsonify({"error":"Unauthorized"}), 401
    now = datetime.now(); week_start = now - timedelta(days=7)
    readings = get_readings(session['user_id'], week_start, now)
    analytics = compute_analytics(readings)
    weekdays = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
    by_day = {d: [] for d in weekdays}
    for r in readings:
        dt = datetime.strptime(r['reading_time'], '%Y-%m-%d %H:%M:%S')
        by_day[weekdays[dt.weekday()]].append(r['glucose_level'])
    daily_avgs = {d:(round(sum(v)/len(v),1) if v else None) for d,v in by_day.items()}
    return jsonify({"period":"weekly","from":week_start.strftime('%Y-%m-%d'),"to":now.strftime('%Y-%m-%d'),"readings":readings,"analytics":analytics,"daily_avgs":daily_avgs})

@app.route('/api/report/monthly')
def api_monthly_report():
    if not session.get('user_id'):
        return jsonify({"error":"Unauthorized"}), 401
    now = datetime.now(); month_start = now.replace(day=1,hour=0,minute=0,second=0,microsecond=0)
    readings = get_readings(session['user_id'], month_start, now)
    analytics = compute_analytics(readings)
    by_date = {}
    for r in readings:
        dk = r['reading_time'][:10]
        by_date.setdefault(dk,[]).append(r['glucose_level'])
    daily_avgs = {d:round(sum(v)/len(v),1) for d,v in sorted(by_date.items())}
    return jsonify({"period":"monthly","from":month_start.strftime('%Y-%m-%d'),"to":now.strftime('%Y-%m-%d'),"readings":readings,"analytics":analytics,"daily_avgs":daily_avgs})

@app.route('/api/report/custom')
def api_custom_report():
    if not session.get('user_id'):
        return jsonify({"error":"Unauthorized"}), 401
    from_str = request.args.get('from'); to_str = request.args.get('to')
    if not from_str or not to_str:
        return jsonify({"error":"from and to dates required"}), 400
    try:
        from_dt = datetime.strptime(from_str, '%Y-%m-%d')
        to_dt   = datetime.strptime(to_str,   '%Y-%m-%d').replace(hour=23,minute=59,second=59)
    except ValueError:
        return jsonify({"error":"Invalid date format"}), 400
    readings  = get_readings(session['user_id'], from_dt, to_dt)
    analytics = compute_analytics(readings)
    return jsonify({"period":"custom","from":from_str,"to":to_str,"readings":readings,"analytics":analytics})

@app.route('/api/analytics/summary')
def api_analytics_summary():
    if not session.get('user_id'):
        return jsonify({"error":"Unauthorized"}), 401
    uid = session['user_id']; now = datetime.now()
    today_r  = get_readings(uid, now.replace(hour=0,minute=0,second=0,microsecond=0), now)
    week_r   = get_readings(uid, now - timedelta(days=7), now)
    month_r  = get_readings(uid, now.replace(day=1,hour=0,minute=0,second=0,microsecond=0), now)
    all_r    = get_all_readings(uid)
    prev_end   = now.replace(day=1,hour=0,minute=0,second=0,microsecond=0) - timedelta(seconds=1)
    prev_start = prev_end.replace(day=1,hour=0,minute=0,second=0,microsecond=0)
    prev_r   = get_readings(uid, prev_start, prev_end)
    ta = compute_analytics(today_r); wa = compute_analytics(week_r)
    ma = compute_analytics(month_r); pa = compute_analytics(prev_r)
    aa = compute_analytics(all_r)
    mom = None
    if pa['average'] and ma['average']:
        mom = round((ma['average'] - pa['average']) / pa['average'] * 100, 1)
    return jsonify({"today_avg":ta['average'],"weekly_avg":wa['average'],"monthly_avg":ma['average'],
                    "max":aa['max'],"min":aa['min'],"total":aa['total'],"normal_pct":wa['normal_pct'],
                    "high_pct":wa['high_pct'],"low_pct":wa['low_pct'],"prev_month_avg":pa['average'],"mom_change_pct":mom})

@app.route('/api/chart/line')
def api_chart_line():
    if not session.get('user_id'):
        return jsonify({"error":"Unauthorized"}), 401
    period = request.args.get('period','weekly'); now = datetime.now()
    if period == 'daily':
        start = now.replace(hour=0,minute=0,second=0,microsecond=0)
    elif period == 'monthly':
        start = now.replace(day=1,hour=0,minute=0,second=0,microsecond=0)
    else:
        start = now - timedelta(days=7)
    readings = get_readings(session['user_id'], start, now)
    readings = list(reversed(readings))
    values   = [r['glucose_level'] for r in readings]
    return jsonify({"labels":[r['reading_time'] for r in readings],"values":values,"statuses":[r['status'] for r in readings],
                    "point_colors":['#3b82f6' if v<70 else ('#22c55e' if v<=140 else '#ef4444') for v in values]})

@app.route('/api/chart/bar')
def api_chart_bar():
    if not session.get('user_id'):
        return jsonify({"error":"Unauthorized"}), 401
    now = datetime.now()
    readings = get_readings(session['user_id'], now - timedelta(days=7), now)
    weekdays = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
    by_day = {d:[] for d in weekdays}
    for r in readings:
        dt = datetime.strptime(r['reading_time'], '%Y-%m-%d %H:%M:%S')
        by_day[weekdays[dt.weekday()]].append(r['glucose_level'])
    avgs   = [round(sum(v)/len(v),1) if v else 0 for v in by_day.values()]
    colors = ['rgba(59,130,246,0.7)' if a<70 else ('rgba(34,197,94,0.7)' if a<=140 else 'rgba(239,68,68,0.7)') if a>0 else 'rgba(200,200,200,0.4)' for a in avgs]
    return jsonify({"labels":weekdays,"values":avgs,"colors":colors})

@app.route('/api/chart/pie')
def api_chart_pie():
    if not session.get('user_id'):
        return jsonify({"error":"Unauthorized"}), 401
    period = request.args.get('period','weekly'); now = datetime.now()
    start  = now.replace(day=1,hour=0,minute=0,second=0,microsecond=0) if period=='monthly' else now - timedelta(days=7)
    readings = get_readings(session['user_id'], start, now)
    return jsonify({"labels":["Low","Normal","High"],
                    "values":[sum(1 for r in readings if r['glucose_level']<70),
                              sum(1 for r in readings if 70<=r['glucose_level']<=140),
                              sum(1 for r in readings if r['glucose_level']>140)],
                    "colors":["#3b82f6","#22c55e","#ef4444"]})

# ─────────────────────────────────────────────
# LEGACY ROUTES (keep backward compat)
# ─────────────────────────────────────────────
@app.route('/glucose', methods=['POST'])
def glucose():
    data = request.json
    print("Received:", data)
    return {"status": "success"}

@app.route('/reading', methods=['POST'])
def add_reading():
    if not session.get('user_id'):
        return jsonify({"error":"Not logged in"}), 401
    data = request.json
    glucose_level = data.get('glucose_level')
    status = get_glucose_status(float(glucose_level)) if glucose_level else 'normal'
    db = get_db_connection()
    if db is None:
        return jsonify({"error":"DB failed"}), 500
    ensure_glucose_readings_columns(db)
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO glucose_readings (user_id, device_id, glucose_level, reading_time, status)
        VALUES (%s, %s, %s, NOW(), %s)
    """, (session['user_id'], data.get('device_id',0), glucose_level, status))
    db.commit(); cursor.close(); db.close()
    return jsonify({"message":"Reading saved successfully"})


# ─────────────────────────────────────────────
# MYSUGR CSV IMPORT
# ─────────────────────────────────────────────
@app.route('/mysugr_import')
def mysugr_import():
    if 'user_id' not in session:
        flash("Please login to import data.", "error")
        return redirect('/login_page')
    return render_template('mysugr_import.html')


@app.route('/mysugr_upload', methods=['POST'])
def mysugr_upload():
    if 'user_id' not in session:
        flash("Please login to import data.", "error")
        return redirect('/login_page')

    file = request.files.get('csv_file')
    if not file or file.filename == '':
        flash("No file selected. Please choose a CSV file.", "error")
        return redirect('/mysugr_import')

    if not file.filename.lower().endswith('.csv'):
        flash("Invalid file type. Please upload a .csv file only.", "error")
        return redirect('/mysugr_import')

    try:
        import pandas as pd
        import io
        import re

        content = file.read().decode('utf-8-sig', errors='ignore')
        df = pd.read_csv(io.StringIO(content), sep=None, engine='python')

        # Clean up column names
        df.columns = df.columns.astype(str).str.replace('\ufeff', '', regex=False).str.strip()

        # Find glucose column flexibly
        glucose_col = None
        for col in df.columns:
            col_key = col.lower().strip()
            if (
                'glucose' in col_key
                or 'blood sugar' in col_key
                or 'blood glucose' in col_key
                or col_key in ('bg', 'bg value')
            ):
                glucose_col = col
                break

        if glucose_col is None:
            flash("Could not find a glucose column in your CSV. Please export again from mySugr.", "error")
            return redirect('/mysugr_import')

        # Find other columns flexibly
        def find_col(df, keywords):
            for col in df.columns:
                for kw in keywords:
                    if kw.lower() in col.lower():
                        return col
            return None

        def parse_glucose(raw_value):
            if pd.isna(raw_value):
                return None
            value = str(raw_value).strip()
            if not value or value.lower() in ('nan', 'none', 'null'):
                return None
            match = re.search(r'\d+(?:[.,]\d+)?', value)
            if not match:
                return None
            return float(match.group(0).replace(',', '.'))

        def parse_reading_time(row, date_col, time_col, datetime_col):
            if datetime_col:
                combined = str(row.get(datetime_col, '')).strip()
            else:
                date_str = str(row.get(date_col, '')).strip() if date_col else ''
                time_str = str(row.get(time_col, '')).strip() if time_col else ''
                if not date_str or date_str.lower() in ('nan', 'none', ''):
                    return None
                if time_col and time_str and time_str.lower() not in ('nan', 'none', ''):
                    combined = f"{date_str} {time_str}"
                else:
                    combined = date_str

            if not combined or combined.lower() in ('nan', 'none', ''):
                return None

            for dayfirst in (True, False):
                parsed = pd.to_datetime(combined, errors='coerce', dayfirst=dayfirst)
                if not pd.isna(parsed):
                    return parsed.to_pydatetime()
            return None

        datetime_col = find_col(df, ['date/time', 'datetime', 'timestamp', 'created at'])
        date_col  = find_col(df, ['date', 'Date'])
        time_col  = find_col(df, ['time', 'Time'])
        if datetime_col and date_col == datetime_col:
            date_col = None
            time_col = None
        notes_col = find_col(df, ['notes', 'Notes', 'comment', 'Comment'])
        carb_col  = find_col(df, ['carbohydrate', 'carb', 'Carb'])

        db = get_db_connection()
        if not db:
            flash("Database connection failed.", "error")
            return redirect('/mysugr_import')

        ensure_glucose_readings_columns(db)
        cursor = db.cursor()
        cursor.execute("SHOW COLUMNS FROM glucose_readings LIKE 'device_id'")
        has_device_id = cursor.fetchone() is not None
        imported = 0
        skipped  = 0
        errors   = 0
        first_error = None

        for _, row in df.iterrows():
            try:
                # Get glucose value — skip blank rows
                raw_glucose = row.get(glucose_col)
                glucose_level = parse_glucose(raw_glucose)
                if glucose_level is None:
                    skipped += 1
                    continue

                # Validate range
                if not (20 <= glucose_level <= 600):
                    skipped += 1
                    continue

                # Build reading_time
                parsed_time = parse_reading_time(row, date_col, time_col, datetime_col)
                date_str = parsed_time.strftime('%Y-%m-%d') if parsed_time else ''
                time_str = parsed_time.strftime('%H:%M:%S') if parsed_time else '00:00'

                if not date_str or date_str.lower() in ('nan', 'none', ''):
                    skipped += 1
                    continue

                # Try parsing datetime — handle multiple mySugr export formats
                reading_time = None
                for fmt, val in [
                    ('%Y-%m-%d %H:%M:%S', f"{date_str} {time_str}"),
                    ('%Y-%m-%d %H:%M',    f"{date_str} {time_str}"),
                    ('%d/%m/%Y %H:%M:%S', f"{date_str} {time_str}"),
                    ('%d/%m/%Y %H:%M',    f"{date_str} {time_str}"),
                    ('%m/%d/%Y %H:%M:%S', f"{date_str} {time_str}"),
                    ('%m/%d/%Y %H:%M',    f"{date_str} {time_str}"),
                    ('%d-%m-%Y %H:%M:%S', f"{date_str} {time_str}"),
                    ('%d-%m-%Y %H:%M',    f"{date_str} {time_str}"),
                    ('%Y-%m-%d',           date_str),
                    ('%d/%m/%Y',           date_str),
                    ('%m/%d/%Y',           date_str),
                    ('%d-%m-%Y',           date_str),
                ]:
                    try:
                        reading_time = datetime.strptime(val.strip(), fmt)
                        break
                    except ValueError:
                        continue
                if reading_time is None:
                    skipped += 1
                    continue

                # Build notes
                notes_parts = []
                if notes_col and not pd.isna(row.get(notes_col, '')):
                    n = str(row.get(notes_col, '')).strip()
                    if n and n.lower() not in ('nan', 'none', ''):
                        notes_parts.append(n)
                if carb_col and not pd.isna(row.get(carb_col, '')):
                    c = str(row.get(carb_col, '')).strip()
                    if c and c.lower() not in ('nan', 'none', '0.0', '0'):
                        notes_parts.append(f"Carbs: {c}g")
                notes = ' | '.join(notes_parts) if notes_parts else 'Imported from mySugr'

                # Auto status
                status = get_glucose_status(glucose_level)

                # Skip duplicate (same user + same reading_time + same glucose)
                cursor.execute("""
                    SELECT id FROM glucose_readings
                    WHERE user_id=%s AND reading_time=%s AND glucose_level=%s
                    LIMIT 1
                """, (session['user_id'], reading_time, glucose_level))
                if cursor.fetchone():
                    skipped += 1
                    continue

                if has_device_id:
                    cursor.execute("""
                        INSERT INTO glucose_readings
                          (user_id, device_id, glucose_level, reading_time, status, notes, meal_timing)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (session['user_id'], 0, glucose_level, reading_time,
                          status, notes, None))
                else:
                    cursor.execute("""
                        INSERT INTO glucose_readings
                          (user_id, glucose_level, reading_time, status, notes, meal_timing)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (session['user_id'], glucose_level, reading_time,
                          status, notes, None))
                imported += 1

            except Exception as row_error:
                errors += 1
                if first_error is None:
                    first_error = str(row_error)
                continue

        db.commit()
        cursor.close()
        db.close()

        if imported == 0:
            msg = f"No new readings imported. {skipped} rows were skipped (duplicates or invalid)."
            if errors:
                msg += f" {errors} row(s) failed while saving"
                if first_error:
                    msg += f": {first_error}"
                msg += "."
            msg += " Check your CSV file."
            flash(msg, "error")
        else:
            msg = f"✅ Successfully imported {imported} reading(s) from mySugr!"
            if skipped > 0:
                msg += f" ({skipped} duplicate/invalid rows skipped)"
            if errors > 0:
                msg += f" ({errors} row errors)"
            flash(msg, "success")
            return redirect('/record')

    except Exception as e:
        flash(f"Import failed: {str(e)}", "error")

    return redirect('/mysugr_import')


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
