import os
import sys
import uuid
import json
from datetime import datetime, timezone
import zoneinfo

sys.stdout.reconfigure(encoding="utf-8")

from flask import Flask, render_template, request, session, redirect, url_for
from dotenv import load_dotenv
from agent import run_agent
from tools import send_email

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ["FLASK_SECRET_KEY"]

EASTERN = zoneinfo.ZoneInfo("America/New_York")
COST_PER_INPUT_TOKEN  = 3.0  / 1_000_000   # $3.00 / 1M tokens
COST_PER_OUTPUT_TOKEN = 15.0 / 1_000_000   # $15.00 / 1M tokens
ALERT_EMAIL = "juliuswaggoner@gmail.com"
_BIZ_OPEN  = (7, 30)   # 7:30 AM EST
_BIZ_CLOSE = (17, 30)  # 5:30 PM EST


def is_after_hours(dt_utc):
    local = dt_utc.astimezone(EASTERN)
    if local.weekday() == 6:  # Sunday
        return True
    t = (local.hour, local.minute)
    return t < _BIZ_OPEN or t >= _BIZ_CLOSE


def emit_run(record):
    print(json.dumps(record), flush=True)


def send_error_alert(run_id, step, error, timestamp):
    subject = f"[quote-agent] Error in {step} — {run_id[:8]}"
    body = (
        f"Run ID:    {run_id}\n"
        f"Step:      {step}\n"
        f"Error:     {error}\n"
        f"Timestamp: {timestamp}\n"
    )
    try:
        send_email(subject=subject, body=body, to_email=ALERT_EMAIL)
    except Exception as alert_exc:
        print(f"ALERT_SEND_FAILED run_id={run_id} alert_error={alert_exc}", flush=True)


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/preview", methods=["POST"])
def preview():
    run_id = str(uuid.uuid4())
    received_at = datetime.now(timezone.utc)

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
        result = run_agent(vendor_name, items)
        draft = result["draft"]
        session["draft"]       = draft
        session["run_id"]      = run_id
        session["received_at"] = received_at.isoformat()
        session["tokens_in"]   = result["tokens_in"]
        session["tokens_out"]  = result["tokens_out"]
        return render_template("index.html", draft=draft)
    except Exception as e:
        emit_run({
            "run_id": run_id,
            "agent": "quote_agent",
            "version": "1.0",
            "trigger_source": "web_form",
            "received_at": received_at.isoformat(),
            "quote_sent_at": None,
            "response_time_sec": None,
            "after_hours": is_after_hours(received_at),
            "status": "error",
            "step": "run_agent",
            "error": str(e),
            "tokens_in": 0,
            "tokens_out": 0,
            "est_cost_usd": 0.0,
        })
        send_error_alert(run_id, "run_agent", str(e), received_at.isoformat())
        return render_template("index.html", error=str(e))


@app.route("/send", methods=["POST"])
def send():
    draft = session.get("draft")
    if not draft:
        send_error_alert(str(uuid.uuid4()), "send_missing_draft", "No draft in session", datetime.now(timezone.utc).isoformat())
        return redirect(url_for("index"))

    run_id          = session.get("run_id", str(uuid.uuid4()))
    received_at_str = session.get("received_at")
    tokens_in       = session.get("tokens_in", 0)
    tokens_out      = session.get("tokens_out", 0)

    received_at   = datetime.fromisoformat(received_at_str) if received_at_str else datetime.now(timezone.utc)
    quote_sent_at = datetime.now(timezone.utc)
    response_time_sec = round((quote_sent_at - received_at).total_seconds(), 2)
    est_cost = round(tokens_in * COST_PER_INPUT_TOKEN + tokens_out * COST_PER_OUTPUT_TOKEN, 6)

    def _record(status, error=None):
        return {
            "run_id": run_id,
            "agent": "quote_agent",
            "version": "1.0",
            "trigger_source": "web_form",
            "received_at": received_at.isoformat(),
            "quote_sent_at": quote_sent_at.isoformat(),
            "response_time_sec": response_time_sec,
            "after_hours": is_after_hours(received_at),
            "status": status,
            "step": "send_email",
            "error": error,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "est_cost_usd": est_cost,
        }

    try:
        result = send_email(
            subject=draft["subject"],
            body=draft["body"],
            to_email=draft["to_email"],
        )
        if isinstance(result, dict) and result.get("status") == "error":
            err_msg = result.get("error", "unknown SMTP error")
            emit_run(_record("error", err_msg))
            send_error_alert(run_id, "send_email", err_msg, quote_sent_at.isoformat())
            return render_template("index.html", draft=draft, error=err_msg)
    except Exception as e:
        emit_run(_record("error", str(e)))
        send_error_alert(run_id, "send_email", str(e), quote_sent_at.isoformat())
        return render_template("index.html", draft=draft, error=str(e))

    emit_run(_record("success"))
    session.clear()
    return render_template("index.html", sent=draft["to_email"])


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
