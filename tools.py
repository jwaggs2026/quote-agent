import os
import requests
from base64 import b64encode
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
    material: str,
    size: str,
    quantity: str,
) -> dict:
    subject = f"Quote Request: {material} ({size}) — Qty {quantity}"
    body = (
        f"Hi {rep_name},\n\n"
        f"I hope you're doing well. I'm reaching out to request a quote from {vendor_name} "
        f"for the following material:\n\n"
        f"  Material: {material}\n"
        f"  Size: {size}\n"
        f"  Quantity: {quantity}\n\n"
        f"Could you please send over pricing and lead time at your earliest convenience?\n\n"
        f"Thank you,\n"
        f"Midstate"
    )
    return {"subject": subject, "body": body, "to_email": email}



def send_email_outlook(subject: str, body: str, to_email: str) -> dict:
    # TODO: replace with Microsoft Graph API send when client's Outlook subscription is ready
    print(f"[STUB] would send to={to_email!r} subject={subject!r}", flush=True)
    return {"status": "sent", "to": to_email}
