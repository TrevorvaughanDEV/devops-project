from flask import Flask, render_template, jsonify
import psutil 

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/projects")
def projects():
    return render_template("projects.html")

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

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