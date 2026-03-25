from flask import Flask, render_template, jsonify, request, redirect, session, url_for, Response
import psutil 
import json
import time

from collections import deque

history = {
    "cpu": deque(maxlen=60),
    "memory": deque(maxlen=60),
    "disk": deque(maxlen=60)
}


app = Flask(__name__)
app.secret_key = "123456789"  # Change this to a random secret key in production

USERNAME = "admin"
PASSWORD = "manpoopa"

@app.route("/")
def home():
    return render_template("index.html")
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        if username == USERNAME and password == PASSWORD:
            session["user"] = username
            return redirect(url_for("dashboard"))
        else:
            return render_template("login.html", error="Invalid credentials")
    
    return render_template("login.html")

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
    cpu = psutil.cpu_percent(interval=1)
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