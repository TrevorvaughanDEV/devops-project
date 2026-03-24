from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return """
    <html>
        <head>
            <title>DevOps App</title>
        </head>
        <body style="font-family: Arial; text-align:center; margin-top:50px;">
            <h1>🚀 DevOps Project Live</h1>
            <p>Deployed using Docker + AWS</p>
            <p><b>Built by Trevor Vaughan</b></p>
        </body>
    </html>
    """

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)