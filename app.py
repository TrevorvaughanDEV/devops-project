"""DevOps Monitor: a small Flask app that reports host CPU, memory and disk usage."""

import logging
import os
import secrets
import sqlite3
from collections import deque
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import wraps

import psutil
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("devops-monitor")

# --- Configuration -----------------------------------------------------------
# APP_ENV=production is set in the Docker image. In production the app refuses
# to start without a SECRET_KEY, so a missing secret fails loudly at deploy time
# instead of silently signing sessions with a key that is public on GitHub.
APP_ENV = os.environ.get("APP_ENV", "development")
IS_PRODUCTION = APP_ENV == "production"
DATABASE = os.environ.get("DATABASE_PATH", "metrics.db")
ALLOW_SIGNUP = (
    os.environ.get("ALLOW_SIGNUP", "false" if IS_PRODUCTION else "true").lower() == "true"
)

SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    if IS_PRODUCTION:
        raise RuntimeError("SECRET_KEY must be set when APP_ENV=production")
    SECRET_KEY = secrets.token_hex(32)
    logger.warning("SECRET_KEY not set; using a random key (sessions reset on restart)")

app = Flask(__name__)
app.config.update(
    SECRET_KEY=SECRET_KEY,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    # Cookies only travel over HTTPS in production; override with
    # SESSION_COOKIE_SECURE=false when running locally over plain HTTP.
    SESSION_COOKIE_SECURE=os.environ.get(
        "SESSION_COOKIE_SECURE", "true" if IS_PRODUCTION else "false"
    ).lower()
    == "true",
)

METRICS_HISTORY = {name: deque(maxlen=20) for name in ("cpu", "memory", "disk")}

# Both entries currently read the host the app runs on; the second one is a
# placeholder for adding a remote agent later.
SERVER_INFO = {
    "server1": {"name": "Production", "region": "EU-West"},
    "server2": {"name": "Staging", "region": "EU-West"},
}

THRESHOLDS = {"cpu": 80, "memory": 80, "disk": 90}


# --- Database ----------------------------------------------------------------
@contextmanager
def get_db_connection():
    """Open a connection, commit on success, roll back on error, always close."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init_db():
    db_dir = os.path.dirname(DATABASE)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    with get_db_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL
            );
            """
        )
    logger.info("Database ready at %s", DATABASE)


init_db()


# --- Helpers -----------------------------------------------------------------
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


def build_alerts(cpu, memory, disk):
    readings = {"cpu": cpu, "memory": memory, "disk": disk}
    labels = {"cpu": "CPU", "memory": "Memory", "disk": "Disk"}
    return [
        f"⚠️ High {labels[name]} usage detected!"
        for name, value in readings.items()
        if value > THRESHOLDS[name]
    ]


# --- Health ------------------------------------------------------------------
@app.route("/healthz")
def healthz():
    """Liveness/readiness probe used by Docker and the deploy pipeline."""
    try:
        with get_db_connection() as conn:
            conn.execute("SELECT 1")
    except sqlite3.Error:
        logger.exception("Health check: database unavailable")
        return jsonify({"status": "error", "database": "unavailable"}), 503
    return jsonify({"status": "ok"})


# --- Public pages ------------------------------------------------------------
@app.route("/")
def home():
    try:
        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO visits (timestamp) VALUES (?)",
                (datetime.now(timezone.utc).isoformat(),),
            )
    except sqlite3.Error:
        logger.exception("Could not record visit")
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username or not password:
            return render_template("login.html", error="Username and password required"), 400

        with get_db_connection() as conn:
            user = conn.execute(
                "SELECT password FROM users WHERE username = ?", (username,)
            ).fetchone()

        if user and check_password_hash(user["password"], password):
            session.clear()
            session["user"] = username
            logger.info("Login succeeded for %s", username)
            return redirect(url_for("dashboard"))

        logger.warning("Login failed for %s", username)
        return render_template("login.html", error="Invalid credentials"), 401

    return render_template("login.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if not ALLOW_SIGNUP:
        return render_template("signup.html", error="Sign-ups are closed on this instance."), 403

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username or not password:
            return render_template("signup.html", error="Username and password required"), 400
        if len(password) < 8:
            return render_template(
                "signup.html", error="Password must be at least 8 characters"
            ), 400

        try:
            with get_db_connection() as conn:
                conn.execute(
                    "INSERT INTO users (username, password) VALUES (?, ?)",
                    (username, generate_password_hash(password)),
                )
        except sqlite3.IntegrityError:
            return render_template("signup.html", error="Username already exists"), 409

        session.clear()
        session["user"] = username
        logger.info("Created user %s", username)
        return redirect(url_for("dashboard"))

    return render_template("signup.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


# --- Authenticated pages -----------------------------------------------------
@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


@app.route("/metrics")
@login_required
def metrics_page():
    return render_template("metrics.html")


@app.route("/servers")
@login_required
def servers_page():
    return render_template("servers.html")


@app.route("/logs")
@login_required
def logs_page():
    return render_template("logs.html")


@app.route("/projects")
@login_required
def projects():
    return render_template("projects.html")


@app.route("/about")
@login_required
def about():
    return render_template("about.html")


# --- API ---------------------------------------------------------------------
@app.route("/api/visits")
def get_visits():
    try:
        with get_db_connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM visits").fetchone()[0]
    except sqlite3.Error:
        logger.exception("Could not count visits")
        return jsonify({"error": "Internal server error"}), 500
    return jsonify({"total_visits": total})


@app.route("/api/system_info")
def system_info():
    server_id = request.args.get("server", "server1")
    if server_id not in SERVER_INFO:
        return jsonify({"error": "Invalid server ID"}), 400

    try:
        cpu = round(float(psutil.cpu_percent(interval=0.1)), 2)
        memory = round(float(psutil.virtual_memory().percent), 2)
        disk = round(float(psutil.disk_usage("/").percent), 2)
    except Exception:
        logger.exception("Could not read system metrics")
        return jsonify({"error": "Internal server error"}), 500

    METRICS_HISTORY["cpu"].append(cpu)
    METRICS_HISTORY["memory"].append(memory)
    METRICS_HISTORY["disk"].append(disk)

    return jsonify(
        {
            "server": SERVER_INFO[server_id]["name"],
            "region": SERVER_INFO[server_id]["region"],
            "cpu": cpu,
            "memory": memory,
            "disk": disk,
            "history": {name: list(values) for name, values in METRICS_HISTORY.items()},
            "alerts": build_alerts(cpu, memory, disk),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
