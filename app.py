from flask import Flask, request, jsonify, render_template, redirect
from functools import wraps
from datetime import datetime
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from dotenv import load_dotenv
import bcrypt
import os
import sqlite3
import smtplib
from email.message import EmailMessage
import re

load_dotenv()

app = Flask(__name__, instance_relative_config=True)
os.makedirs(app.instance_path, exist_ok=True)

DB_NAME = os.path.join(app.instance_path, "kniha_jizd.db")

app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
if not app.config["SECRET_KEY"]:
    raise RuntimeError("Chybí SECRET_KEY v .env souboru")

serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"])
TOKEN_MAX_AGE = 60 * 60 * 48  # 48 hodin
RESET_TOKEN_MAX_AGE = 60 * 30  # 30 minut
REGISTER_TOKEN_MAX_AGE = 60 * 60  # 1 hodina

MAIL_SERVER = os.getenv("MAIL_SERVER")
MAIL_PORT = int(os.getenv("MAIL_PORT", 465))
MAIL_USERNAME = os.getenv("MAIL_USERNAME")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
MAIL_FROM = os.getenv("MAIL_FROM")
APP_URL = os.getenv("APP_URL", "http://localhost:5000")

def get_db():
    conn = sqlite3.connect(DB_NAME, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_db():
    with get_db() as conn:
        c = conn.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS vehicles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                spz TEXT,
                brand TEXT,
                model TEXT,
                current_odometer INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS trips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                vehicle_id INTEGER NOT NULL,
                trip_date TEXT NOT NULL,
                start_place TEXT,
                end_place TEXT,
                purpose TEXT,
                odometer_start INTEGER NOT NULL,
                odometer_end INTEGER NOT NULL,
                distance INTEGER NOT NULL,
                note TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE CASCADE
            )
        """)

        conn.commit()


def hash_hesla(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def over_heslo(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def vytvor_token(user_id: int, email: str) -> str:
    return serializer.dumps({"user_id": user_id, "email": email})

def vytvor_reset_token(user_id: int, email: str) -> str:
    return serializer.dumps({
        "type": "password_reset",
        "user_id": user_id,
        "email": email
    })

def posli_email(to_email: str, subject: str, body: str):
    msg = EmailMessage()

    msg["Subject"] = subject
    msg["From"] = MAIL_FROM
    msg["To"] = to_email

    msg.set_content(body)

    with smtplib.SMTP_SSL(MAIL_SERVER, MAIL_PORT) as smtp:
        smtp.login(MAIL_USERNAME, MAIL_PASSWORD)
        smtp.send_message(msg)

def nacti_token():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None

    token = auth.replace("Bearer ", "", 1)
    try:
        return serializer.loads(token, max_age=TOKEN_MAX_AGE)
    except (SignatureExpired, BadSignature):
        return None

def vytvor_register_token(email: str) -> str:
    return serializer.dumps({
        "type": "register",
        "email": email
    })

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = nacti_token()
        if not user:
            return jsonify({"error": "Neoprávněný přístup"}), 401
        request.user = user
        return fn(*args, **kwargs)
    return wrapper


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@app.route("/vozidla")
def vozidla_page():
    return render_template("vozidla.html")


@app.route("/nova-jizda")
def nova_jizda_page():
    return render_template("nova_jizda.html")


@app.route("/historie")
def historie_page():
    return render_template("historie.html")

@app.route("/dokoncit-registraci")
def dokoncit_registraci_page():
    return render_template("dokoncit_registraci.html")

def je_platny_email(email: str) -> bool:
    return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email) is not None

@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "").strip()

    if not email or not password:
        return jsonify({"error": "Vyplň e-mail i heslo."}), 400

    if len(password) < 6:
        return jsonify({"error": "Heslo musí mít alespoň 6 znaků."}), 400

    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute(
                "INSERT INTO users (email, password_hash) VALUES (?, ?)",
                (email, hash_hesla(password))
            )
            user_id = c.lastrowid
            conn.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "Uživatel s tímto e-mailem už existuje."}), 409

    token = vytvor_token(user_id, email)
    return jsonify({"success": True, "token": token, "email": email})

@app.route("/api/start-registration", methods=["POST"])
def start_registration():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()

    if not email:
        return jsonify({"error": "Vyplň e-mail."}), 400

    if not je_platny_email(email):
        return jsonify({"error": "Zadej platný e-mail."}), 400

    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE email = ?", (email,))
        existing = c.fetchone()

    if existing:
        return jsonify({"error": "Uživatel s tímto e-mailem už existuje."}), 409

    token = vytvor_register_token(email)
    register_link = f"{APP_URL}/dokoncit-registraci?token={token}"

    posli_email(
        email,
        "Dokončení registrace",
        f"""
Ahoj,

pro dokončení registrace klikni na tento odkaz:

{register_link}

Odkaz platí 1 hodinu.

Pokud jsi o registraci nežádal, tento e-mail ignoruj.
"""
    )

    print("ODKAZ PRO DOKONČENÍ REGISTRACE:")
    print(register_link)

    return jsonify({
        "success": True,
        "message": "Poslali jsme ti e-mail pro dokončení registrace."
    })

@app.route("/api/complete-registration", methods=["POST"])
def complete_registration():
    data = request.get_json() or {}

    token = data.get("token") or ""
    password = (data.get("password") or "").strip()

    if not token:
        return jsonify({"error": "Chybí registrační token."}), 400

    if len(password) < 6:
        return jsonify({"error": "Heslo musí mít alespoň 6 znaků."}), 400

    try:
        payload = serializer.loads(token, max_age=REGISTER_TOKEN_MAX_AGE)
    except SignatureExpired:
        return jsonify({"error": "Registrační odkaz vypršel."}), 400
    except BadSignature:
        return jsonify({"error": "Neplatný registrační odkaz."}), 400

    if payload.get("type") != "register":
        return jsonify({"error": "Neplatný typ tokenu."}), 400

    email = payload["email"]

    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute(
                "INSERT INTO users (email, password_hash) VALUES (?, ?)",
                (email, hash_hesla(password))
            )
            user_id = c.lastrowid
            conn.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "Uživatel s tímto e-mailem už existuje."}), 409

    login_token = vytvor_token(user_id, email)

    return jsonify({
        "success": True,
        "token": login_token,
        "email": email,
        "message": "Registrace dokončena."
    })

@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "").strip()

    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, email, password_hash FROM users WHERE email = ?", (email,))
        row = c.fetchone()

    if not row or not over_heslo(password, row["password_hash"]):
        return jsonify({"error": "Neplatný e-mail nebo heslo."}), 401

    token = vytvor_token(row["id"], row["email"])
    return jsonify({"success": True, "token": token, "email": row["email"]})

@app.route("/api/forgot-password", methods=["POST"])
def forgot_password():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()

    if not email:
        return jsonify({"error": "Vyplň e-mail."}), 400

    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, email FROM users WHERE email = ?", (email,))
        row = c.fetchone()

    # Bezpečnější hláška: neprozrazujeme, jestli e-mail existuje
    if row:
        token = vytvor_reset_token(row["id"], row["email"])
        reset_link = f"{APP_URL}/reset-hesla?token={token}"

        posli_email(
            row["email"],
            "Obnova hesla",
            f"""
        Ahoj,

        pro obnovu hesla klikni na tento odkaz:

        {reset_link}

        Odkaz platí 30 minut.

        Pokud jsi o obnovu hesla nežádal, tento e-mail ignoruj.
        """
        )

    return jsonify({
        "success": True,
        "message": "Pokud e-mail existuje, poslali jsme instrukce k obnově hesla."
    })

@app.route("/api/me")
@login_required
def me():
    return jsonify({"user_id": request.user["user_id"], "email": request.user["email"]})

@app.route("/reset-hesla")
def reset_hesla_page():
    return render_template("reset_hesla.html")

@app.route("/api/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json() or {}

    token = data.get("token") or ""
    password = (data.get("password") or "").strip()

    if not token:
        return jsonify({"error": "Chybí resetovací token."}), 400

    if len(password) < 6:
        return jsonify({"error": "Heslo musí mít alespoň 6 znaků."}), 400

    try:
        payload = serializer.loads(token, max_age=RESET_TOKEN_MAX_AGE)
    except SignatureExpired:
        return jsonify({"error": "Odkaz pro obnovu hesla vypršel."}), 400
    except BadSignature:
        return jsonify({"error": "Neplatný odkaz pro obnovu hesla."}), 400

    if payload.get("type") != "password_reset":
        return jsonify({"error": "Neplatný typ tokenu."}), 400

    user_id = payload["user_id"]

    with get_db() as conn:
        c = conn.cursor()
        c.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (hash_hesla(password), user_id)
        )
        conn.commit()

    return jsonify({
        "success": True,
        "message": "Heslo bylo změněno. Teď se můžeš přihlásit."
    })

@app.route("/api/vehicles", methods=["GET", "POST"])
@login_required
def vehicles_api():
    user_id = request.user["user_id"]

    if request.method == "GET":
        with get_db() as conn:
            c = conn.cursor()
            c.execute("""
                SELECT id, name, spz, brand, model, current_odometer, is_active
                FROM vehicles
                WHERE user_id = ? AND is_active = 1
                ORDER BY id DESC
            """, (user_id,))
            return jsonify([dict(row) for row in c.fetchall()])

    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    spz = (data.get("spz") or "").strip().upper()
    brand = (data.get("brand") or "").strip()
    model = (data.get("model") or "").strip()
    current_odometer = int(data.get("current_odometer") or 0)

    if not name:
        return jsonify({"error": "Vyplň název vozidla."}), 400

    with get_db() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO vehicles (user_id, name, spz, brand, model, current_odometer)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, name, spz, brand, model, current_odometer))
        conn.commit()

    return jsonify({"success": True})


@app.route("/api/vehicles/<int:vehicle_id>", methods=["DELETE"])
@login_required
def archive_vehicle(vehicle_id):
    user_id = request.user["user_id"]
    with get_db() as conn:
        c = conn.cursor()
        c.execute(
            "UPDATE vehicles SET is_active = 0 WHERE id = ? AND user_id = ?",
            (vehicle_id, user_id)
        )
        conn.commit()
    return jsonify({"success": True})


@app.route("/api/trips", methods=["GET", "POST"])
@login_required
def trips_api():
    user_id = request.user["user_id"]

    if request.method == "GET":
        with get_db() as conn:
            c = conn.cursor()
            c.execute("""
                SELECT trips.id, trips.trip_date, trips.start_place, trips.end_place,
                       trips.purpose, trips.odometer_start, trips.odometer_end,
                       trips.distance, trips.note, vehicles.name AS vehicle_name
                FROM trips
                JOIN vehicles ON vehicles.id = trips.vehicle_id
                WHERE trips.user_id = ?
                ORDER BY trips.trip_date DESC, trips.id DESC
            """, (user_id,))
            return jsonify([dict(row) for row in c.fetchall()])

    data = request.get_json() or {}
    vehicle_id = int(data.get("vehicle_id") or 0)
    trip_date = data.get("trip_date") or datetime.now().strftime("%Y-%m-%d")
    start_place = (data.get("start_place") or "").strip()
    end_place = (data.get("end_place") or "").strip()
    purpose = (data.get("purpose") or "").strip()
    note = (data.get("note") or "").strip()
    odometer_start = int(data.get("odometer_start") or 0)
    odometer_end = int(data.get("odometer_end") or 0)

    if not vehicle_id:
        return jsonify({"error": "Vyber vozidlo."}), 400
    if odometer_end < odometer_start:
        return jsonify({"error": "Konečný tachometr nesmí být menší než počáteční."}), 400

    distance = odometer_end - odometer_start

    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM vehicles WHERE id = ? AND user_id = ? AND is_active = 1", (vehicle_id, user_id))
        if not c.fetchone():
            return jsonify({"error": "Vozidlo nenalezeno."}), 404

        c.execute("""
            INSERT INTO trips (
                user_id, vehicle_id, trip_date, start_place, end_place, purpose,
                odometer_start, odometer_end, distance, note
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, vehicle_id, trip_date, start_place, end_place, purpose,
            odometer_start, odometer_end, distance, note
        ))

        c.execute("UPDATE vehicles SET current_odometer = ? WHERE id = ? AND user_id = ?", (odometer_end, vehicle_id, user_id))
        conn.commit()

    return jsonify({"success": True, "distance": distance})


@app.route("/api/vehicle-last-km/<int:vehicle_id>")
@login_required
def vehicle_last_km(vehicle_id):
    user_id = request.user["user_id"]
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT current_odometer FROM vehicles WHERE id = ? AND user_id = ?", (vehicle_id, user_id))
        row = c.fetchone()
        if not row:
            return jsonify({"error": "Vozidlo nenalezeno."}), 404
        return jsonify({"current_odometer": row["current_odometer"] or 0})

@app.route("/api/contact", methods=["POST"])
def contact():
    data = request.get_json() or {}

    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    message = (data.get("message") or "").strip()

    if not name or not email or not message:
        return jsonify({"error": "Vyplň jméno, e-mail i zprávu."}), 400

    if not je_platny_email(email):
        return jsonify({"error": "Zadej platný e-mail."}), 400

    posli_email(
        MAIL_FROM,
        "Zpráva z HistorieJízd.cz",
        f"""
Nová zpráva z webu HistorieJízd.cz

Jméno:
{name}

E-mail:
{email}

Zpráva:
{message}
"""
    )

    return jsonify({
        "success": True,
        "message": "Zpráva byla odeslána."
    })

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
