from flask import Flask, render_template, jsonify, request, redirect, session, url_for
import psutil 
import sqlite3
import os
import logging
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from collections import deque

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global metrics history
METRICS_HISTORY = {
    "cpu": deque(maxlen=20),
    "memory": deque(maxlen=20),
    "disk": deque(maxlen=20)
}

# Server configuration
SERVER_INFO = {
    "server1": {"name": "Production", "region": "EU-West"},
    "server2": {"name": "Staging", "region": "EU-West"}
}

# Flask app configuration
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-key-change-in-production")
DATABASE = "metrics.db"

def get_db_connection():
    """Create a database connection with proper error handling."""
    try:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        logger.error(f"Database connection error: {e}")
        return None

def init_db():
    """Initialize database with all required tables."""
    conn = get_db_connection()
    if not conn:
        logger.error("Failed to initialize database")
        return
    
    try:
        c = conn.cursor()
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server TEXT NOT NULL,
                cpu REAL NOT NULL,
                memory REAL NOT NULL,
                disk REAL NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL
            )
        ''')
        
        conn.commit()
        logger.info("Database initialized successfully")
    except sqlite3.Error as e:
        logger.error(f"Database initialization error: {e}")
    finally:
        conn.close()

init_db()

@app.route("/metrics")
def metrics_page():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("metrics.html")

@app.route("/servers")
def servers_page():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("servers.html")

@app.route("/logs")
def logs_page():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("logs.html")

@app.route("/api/visits")
def get_visits():
    """Get total visit count from database."""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        
        c = conn.cursor()
        c.execute("SELECT COUNT(*) as total FROM visits")
        result = c.fetchone()
        conn.close()
        
        total_visits = result[0] if result else 0
        logger.info(f"Total visits: {total_visits}")
        
        return jsonify({"total_visits": total_visits})
    except Exception as e:
        logger.error(f"Error fetching visits: {e}")
        return jsonify({"error": str(e)}), 500
    
   

@app.route("/")
def home():
    """Home page - track visits."""
    try:
        conn = get_db_connection()
        if conn:
            c = conn.cursor()
            c.execute("INSERT INTO visits (timestamp) VALUES (?)", (datetime.now().isoformat(),))
            conn.commit()
            conn.close()
    except Exception as e:
        logger.error(f"Error tracking visit: {e}")
    
    return render_template("index.html")
@app.route("/login", methods=["GET", "POST"])
def login():
    """User login route."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            return render_template("login.html", error="Username and password required")

        try:
            conn = get_db_connection()
            if not conn:
                return render_template("login.html", error="Database error")
            
            c = conn.cursor()
            c.execute("SELECT password FROM users WHERE username = ?", (username,))
            user = c.fetchone()
            conn.close()

            if user and check_password_hash(user[0], password):
                session["user"] = username
                logger.info(f"User {username} logged in successfully")
                return redirect(url_for("dashboard"))
            else:
                logger.warning(f"Failed login attempt for user {username}")
                return render_template("login.html", error="Invalid credentials")
        except Exception as e:
            logger.error(f"Login error: {e}")
            return render_template("login.html", error="Server error")
        
    return render_template("login.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    """User signup route."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            return render_template("signup.html", error="Username and password required")
        
        if len(password) < 6:
            return render_template("signup.html", error="Password must be at least 6 characters")

        try:
            hashed_password = generate_password_hash(password)
            conn = get_db_connection()
            if not conn:
                return render_template("signup.html", error="Database error")
            
            c = conn.cursor()
            c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
            conn.commit()
            conn.close()
            
            session["user"] = username
            logger.info(f"New user {username} created successfully")
            return redirect(url_for("dashboard"))
        except sqlite3.IntegrityError:
            logger.warning(f"Signup attempt with existing username: {username}")
            return render_template("signup.html", error="Username already exists")
        except Exception as e:
            logger.error(f"Signup error: {e}")
            return render_template("signup.html", error="Server error")

    return render_template("signup.html")
    
   

@app.route("/projects")
def projects():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("projects.html")

@app.route("/dashboard")
def dashboard():
    """Protected dashboard route."""
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("dashboard.html")

@app.route("/logout")
def logout():
    """Logout route."""
    username = session.get("user", "unknown")
    session.pop("user", None)
    logger.info(f"User {username} logged out")
    return redirect(url_for("home"))

@app.route("/about")
def about():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("about.html")

@app.route("/api/system_info")
def system_info():
    """API endpoint to get real-time system metrics."""
    try:
        server_id = request.args.get("server", "server1")
        
        # Validate server ID
        if server_id not in SERVER_INFO:
            return jsonify({"error": "Invalid server ID"}), 400

        # Get system metrics
        cpu = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory().percent
        disk = psutil.disk_usage('/').percent

        # Store in history
        METRICS_HISTORY["cpu"].append(cpu)
        METRICS_HISTORY["memory"].append(memory)
        METRICS_HISTORY["disk"].append(disk)

        # Generate alerts
        alerts = []
        if cpu > 80:
            alerts.append("⚠️ High CPU usage detected!")
        if memory > 80:
            alerts.append("⚠️ High Memory usage detected!")
        if disk > 90:
            alerts.append("⚠️ High Disk usage detected!")

        response = {
            "server": SERVER_INFO[server_id]["name"],
            "region": SERVER_INFO[server_id]["region"],
            "cpu": round(float(cpu), 2),
            "memory": round(float(memory), 2),
            "disk": round(float(disk), 2),
            "history": {
                "cpu": [round(float(x), 2) for x in METRICS_HISTORY["cpu"]],
                "memory": [round(float(x), 2) for x in METRICS_HISTORY["memory"]],
                "disk": [round(float(x), 2) for x in METRICS_HISTORY["disk"]]
            },
            "alerts": alerts,
            "timestamp": datetime.now().isoformat()
        }
        
        return jsonify(response)

    except Exception as e:
        logger.error(f"System info error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)