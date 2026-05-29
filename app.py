import os
import sys
sys.stdout.reconfigure(encoding="utf-8")

from flask import Flask, render_template, request, session, redirect, url_for
from dotenv import load_dotenv
from agent import run_agent
from tools import send_email_outlook

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ["FLASK_SECRET_KEY"]


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/preview", methods=["POST"])
def preview():
    vendor_name = request.form["vendor_name"].strip()
    materials  = request.form.getlist("material")
    sizes      = request.form.getlist("size")
    quantities = request.form.getlist("quantity")
    details    = request.form.getlist("details")

    items = [
        {"material": m.strip(), "size": s.strip(), "quantity": q.strip(), "details": d.strip()}
        for m, s, q, d in zip(materials, sizes, quantities, details)
    ]

    try:
        draft = run_agent(vendor_name, items)
    except Exception as e:
        return render_template("index.html", error=str(e))

    session["draft"] = draft
    return render_template("index.html", draft=draft)


@app.route("/send", methods=["POST"])
def send():
    draft = session.get("draft")
    if not draft:
        return redirect(url_for("index"))

    try:
        send_email_outlook(
            subject=draft["subject"],
            body=draft["body"],
            to_email=draft["to_email"],
        )
    except Exception as e:
        return render_template("index.html", draft=draft, error=str(e))

    session.pop("draft", None)
    return render_template("index.html", sent=draft["to_email"])


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
