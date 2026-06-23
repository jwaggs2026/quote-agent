import os
import smtplib
import openpyxl
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv(override=False)


def lookup_vendor_excel(vendor_name: str) -> dict:
    path = os.path.join(os.path.dirname(__file__), "vendors.xlsx")
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.worksheets[0]

    rows = iter(ws.rows)
    headers = [cell.value for cell in next(rows)]
    col = {h: i for i, h in enumerate(headers) if h}

    query = vendor_name.lower()
    for row in rows:
        values = [cell.value for cell in row]
        vendor_cell = str(values[col["Vendor"]] or "")
        if query not in vendor_cell.lower():
            continue
        first = str(values[col["First Name"]] or "").strip()
        last = str(values[col["Last Name"]] or "").strip()
        main_email = str(values[col["Main Email"]] or "").strip()
        alt_email = str(values[col["Alt. Email 1"]] or "").strip()
        return {
            "vendor_name": vendor_cell.strip(),
            "rep_name": f"{first} {last}".strip(),
            "rep_email_address": main_email or alt_email,
        }

    return {"error": f"No vendor found matching '{vendor_name}'"}


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
        f"Mid-State Metals"
    )
    return {"subject": subject, "body": body, "to_email": email}



def send_email(subject: str, body: str, to_email: str) -> dict:
    host = os.environ["SMTP_HOST"]
    port = int(os.environ["SMTP_PORT"])
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASSWORD"]

    msg = MIMEText(body, "plain")
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to_email

    try:
        with smtplib.SMTP(host, port) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(user, password)
            print(f"[send_email] calling sendmail: from={user} to={to_email}", flush=True)
            smtp.sendmail(user, [to_email], msg.as_string())
            print(f"[send_email] sendmail returned OK", flush=True)
    except Exception as e:
        import traceback
        print(f"[send_email] FAILED: {e}", flush=True)
        traceback.print_exc()
        return {"status": "error", "error": str(e), "to": to_email}

    return {"status": "sent", "to": to_email}
