from flask import Flask, render_template, jsonify, request, redirect, session, url_for, Response
import psutil 
import json
import time
import sqlite3
import os
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from collections import deque

history = {
    "cpu": deque(maxlen=20),
    "memory": deque(maxlen=20),
    "disk": deque(maxlen=20)
}

servers = {
    "server1": {"name": "Production"},
    "server2": {"name": "Staging"}
}

app = Flask(__name__)
# ⚠️ IMPORTANT: Change this secret key in production!
app.secret_key = os.environ.get("SECRET_KEY", "change-this-in-production")

def init_db():
    conn = sqlite3.connect("metrics.db")
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            server TEXT,
            cpu REAL,
            memory REAL,
            disk REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    ''')

    c.execute("""
              CREATE TABLE IF NOT EXISTS visits (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp TEXT
              )
                """)
              
    conn.commit()
    conn.close()
    # In a real application, you would set up your database here
   


init_db()

@app.route("/metrics")
def metrics():
    return render_template("metrics.html")

@app.route("/servers")
def servers():
    return render_template("servers.html")

@app.route("/logs")
def logs():
    return render_template("logs.html")

@app.route("/api/visits")
def get_visits():
    import sqlite3

    conn = sqlite3.connect("metrics.db")
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM visits")
    result = c.fetchone()   

    conn.close()

    total_visits = result[0] if result else 0

    print("VISITS:", total_visits)
    
    return jsonify({
        "total_visits": total_visits
    })
    
   

@app.route("/")
def home():
    conn = sqlite3.connect("metrics.db")
    c = conn.cursor()

    c.execute("INSERT INTO visits (timestamp) VALUES (?)", (datetime.now().isoformat(),))
    conn.commit()
    conn.close()

    return render_template("index.html")
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        conn = sqlite3.connect("metrics.db")
        c = conn.cursor()
        c.execute("SELECT password FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user[0], password):
            session["user"] = username
            return redirect(url_for("dashboard"))
        else:
            return render_template("login.html", error="Invalid credentials")
        
    return render_template("login.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        hashed_password = generate_password_hash(password)

        conn = sqlite3.connect("metrics.db")
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
            conn.commit()
            session["user"] = username
            return redirect(url_for("dashboard"))
        except sqlite3.IntegrityError:
            return render_template("signup.html", error="Username already exists")
        finally:
            conn.close()

    return render_template("signup.html")
    
   

@app.route("/projects")
def projects():
    return render_template("projects.html")

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("dashboard.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

    

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/api/system_info")
def system_info():
    try:
        server_id = request.args.get("server", "server1")

        cpu = psutil.cpu_percent(interval=None)
        memory = psutil.virtual_memory().percent
        disk = psutil.disk_usage('/').percent

        history["cpu"].append(cpu)
        history["memory"].append(memory)
        history["disk"].append(disk)

        alerts = []
        if cpu > 80:
            alerts.append("High CPU usage detected!")
        if memory > 80:
         alerts.append("High Memory usage detected!")

        return jsonify({
            "server": servers.get(server_id, {}).get("name", "Unknown"),
            "cpu": float(cpu),
            "memory": float(memory),
            "disk": float(disk),
            "history": {
                "cpu": [float(x) for x in history["cpu"]],
                "memory": [float(x) for x in history["memory"]],
                "disk": [float(x) for x in history["disk"]]
            },
            "alerts": alerts
        })  

    except Exception as e:  
     print("ERROR:", e)
     return jsonify({"error": str(e)}), 500


    

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)