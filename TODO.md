# Quote Agent — Gmail OAuth2 Update TODO

## Code Changes (Done)
- [x] `requirements.txt` — added `google-auth`, `google-auth-oauthlib`, `google-api-python-client`
- [x] `tools.py` — `send_email()` now uses Gmail API + OAuth2 instead of SMTP app passwords
- [x] `.env.example` — updated with new OAuth2 var names
- [x] `scripts/gmail_auth.py` — one-time auth script created
- [x] `app.py` — error alert now fires on missing session draft in `/send` route

## Manual Steps (Still Required)

### 1. Google Cloud Console Setup
- [ ] Go to https://console.cloud.google.com → APIs & Services
- [ ] Enable the **Gmail API** for your project
- [ ] Go to Credentials → Create Credentials → **OAuth 2.0 Client ID**
- [ ] Application type: **Desktop app**
- [ ] Copy the **Client ID** and **Client Secret**

### 2. Get the Refresh Token
- [ ] Add `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` to your local `.env` temporarily
- [ ] Run: `python scripts/gmail_auth.py`
- [ ] Sign in with the Gmail account you want to send from
- [ ] Copy the printed `GOOGLE_REFRESH_TOKEN` value

### 3. Update Local `.env`
- [ ] Remove `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`
- [ ] Add:
  ```
  GOOGLE_CLIENT_ID=<from Cloud Console>
  GOOGLE_CLIENT_SECRET=<from Cloud Console>
  GOOGLE_REFRESH_TOKEN=<from gmail_auth.py>
  GMAIL_SENDER=<the gmail address sending emails>
  ```

### 4. Update Railway Dashboard
- [ ] Go to Railway project → Service → Variables
- [ ] Remove: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`
- [ ] Add: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN`, `GMAIL_SENDER`
- [ ] Railway will redeploy automatically

### 5. Commit & Push
- [ ] `git add requirements.txt tools.py .env.example scripts/gmail_auth.py app.py TODO.md`
- [ ] `git commit -m "feat: migrate email to Gmail API OAuth2"`
- [ ] `git push`

---

## Verification

### Quote sends successfully
1. Open the app and submit a valid vendor + line items
2. Click Preview → review the draft → click Confirm & Send
3. Check Railway logs for: `[send_email] sent id=<message_id> to=<vendor_email>`
4. Confirm the vendor email arrives in their inbox

### Error alert fires correctly
1. Submit the form with a vendor name that doesn't exist in `vendors.xlsx`
2. The agent should fail during the preview step
3. Check `juliuswaggoner@gmail.com` for an email with subject `[quote-agent] Error in run_agent — <id>`

### Railway env vars applied
- After updating Railway variables, check the deployment logs confirm a fresh deploy completed
- Watch for any `KeyError: 'GOOGLE_REFRESH_TOKEN'` startup errors — means the vars weren't saved
