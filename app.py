from flask import Flask, render_template, jsonify, request, redirect, session, url_for, Response
import psutil 
import json
import time

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
    cpu_usage = psutil.cpu_percent(interval=1)
    memory_info = psutil.virtual_memory()
    disk_info = psutil.disk_usage('/')
    
    return jsonify({
        "cpu_usage": cpu_usage,
        "memory_total": memory_info.total,
        "memory_used": memory_info.used,
        "memory_percent": memory_info.percent,
        "disk_total": disk_info.total,
        "disk_used": disk_info.used,
        "disk_percent": disk_info.percent
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)