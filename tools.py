import os
import smtplib
import requests
from base64 import b64encode
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

QB_CLIENT_ID = os.environ["QB_CLIENT_ID"]
QB_CLIENT_SECRET = os.environ["QB_CLIENT_SECRET"]
QB_REALM_ID = os.environ["QB_REALM_ID"]
QB_REFRESH_TOKEN = os.environ["QB_REFRESH_TOKEN"]
QB_BASE_URL = "https://sandbox-quickbooks.api.intuit.com"



def _qb_access_token() -> str:
    credentials = b64encode(f"{QB_CLIENT_ID}:{QB_CLIENT_SECRET}".encode()).decode()
    resp = requests.post(
        "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer",
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"grant_type": "refresh_token", "refresh_token": QB_REFRESH_TOKEN},
        timeout=10,
    )
    if not resp.ok:
        raise RuntimeError(f"QB token refresh failed {resp.status_code}: {resp.text}")
    return resp.json()["access_token"]


def lookup_vendor_quickbooks(vendor_name: str) -> dict:
    token = _qb_access_token()
    query = f"SELECT * FROM Vendor WHERE DisplayName LIKE '%{vendor_name}%'"
    url = f"{QB_BASE_URL}/v3/company/{QB_REALM_ID}/query"
    resp = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        params={"query": query},
        timeout=10,
    )
    resp.raise_for_status()
    vendors = resp.json().get("QueryResponse", {}).get("Vendor", [])
    if not vendors:
        return {"error": f"No vendor found matching '{vendor_name}'"}
    v = vendors[0]
    given = v.get("GivenName", "")
    family = v.get("FamilyName", "")
    rep_name = f"{given} {family}".strip() or v.get("DisplayName", "")
    email = v.get("PrimaryEmailAddr", {}).get("Address", "")
    return {
        "vendor_name": v.get("DisplayName", vendor_name),
        "rep_name": rep_name,
        "rep_email_address": email,
    }


def draft_quote_email(
    vendor_name: str,
    rep_name: str,
    email: str,
    items: list,
) -> dict:
    if len(items) == 1:
        i = items[0]
        subject = f"Quote Request: {i['material']} ({i['size']}) — Qty {i['quantity']}"
    else:
        subject = f"Quote Request: {len(items)} Items"

    has_details = any(i.get("details", "").strip() for i in items)

    headers = ["Item", "Size", "Qty"] + (["Details"] if has_details else [])
    rows = [
        [i["material"], i["size"], i["quantity"]] + ([i.get("details", "") or ""] if has_details else [])
        for i in items
    ]

    col_widths = []
    for c in range(len(headers)):
        w = len(headers[c])
        for row in rows:
            w = max(w, len(str(row[c])))
        col_widths.append(w)

    if has_details:
        col_widths[3] = max(col_widths[3], sum(col_widths[:3]) + 6)

    print(f"[debug] col_widths: {dict(zip(headers, col_widths))}", flush=True)

    def fmt_row(cells):
        parts = []
        for c, cell in enumerate(cells):
            if has_details and c == 3:
                parts.append(cell.ljust(col_widths[c]))
            else:
                parts.append(cell.center(col_widths[c]))
        return " | ".join(parts)

    separator = fmt_row(["-" * w for w in col_widths]).replace("|", "+")
    table_lines = [fmt_row(headers), separator] + [fmt_row(r) for r in rows]
    table = "\n".join(table_lines)

    body = (
        f"Hi {rep_name},\n\n"
        f"I hope you're doing well. I'm reaching out to request a quote from {vendor_name} "
        f"for the following material{'s' if len(items) > 1 else ''}:\n\n"
        f"{table}\n\n"
        f"Could you please send over pricing and lead time at your earliest convenience?\n\n"
        f"Thank you,\n"
        f"Midstate"
    )
    return {"subject": subject, "body": body, "to_email": email}



def send_email_outlook(subject: str, body: str, to_email: str) -> dict:
    host = os.environ["SMTP_HOST"]
    port = int(os.environ["SMTP_PORT"])
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASSWORD"]

    msg = MIMEText(body, "plain")
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to_email

    with smtplib.SMTP(host, port) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(user, password)
        smtp.sendmail(user, [to_email], msg.as_string())

    return {"status": "sent", "to": to_email}
