from flask import Flask, render_template, jsonify, request, redirect, session, url_for, Response
import psutil 
import json
import time
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

from collections import deque

history = {
    "cpu": deque(maxlen=60),
    "memory": deque(maxlen=60),
    "disk": deque(maxlen=60)
}

servers = {
    "server1": {"name": "Production"},
    "server2": {"name": "Staging"}

}


app = Flask(__name__)
app.secret_key = "123456789"  # Change this to a random secret key in production

USERNAME = "admin"
PASSWORD = "manpoopa"

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
    conn.commit()
    conn.close()
    # In a real application, you would set up your database here

init_db()

@app.route("/")
def home():
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
        "server": servers[server_id]["name"],
        "cpu": cpu,
        "memory": memory,
        "disk": disk,
        "history": {
            "cpu": list(history["cpu"]),
            "memory": list(history["memory"]),
            "disk": list(history["disk"])
        },
        "alerts": alerts
    })

    

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)