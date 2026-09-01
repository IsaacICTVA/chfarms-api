# C&H Farms — Live System Deployment Guide

## What's in this package
- `backend/app.py` — Python Flask API (24 endpoints)
- `backend/requirements.txt` — Python dependencies
- `backend/Procfile` — Render/Heroku start command
- `backend/sheets_sync.py` — Google Sheet write-back module
- `frontend/index.html` — Full dashboard (open in any browser)
- `render.yaml` — One-click Render deployment config

## Step 1 — Upload to GitHub
1. Sign up at github.com (free)
2. New repository → name: `chfarms-api` → Public → Create
3. Upload: `backend/app.py`, `backend/requirements.txt`, `backend/Procfile`, `backend/sheets_sync.py`

## Step 2 — Deploy to Render (free)
1. Sign up at render.com → Connect GitHub
2. New → Web Service → select `chfarms-api` repo
3. Settings:
   - Build: `pip install -r requirements.txt`
   - Start: `gunicorn app:app --bind 0.0.0.0:$PORT`
   - Plan: Free
4. Deploy → wait ~2 min → copy your URL (e.g. https://chfarms-api.onrender.com)

## Step 3 — Set environment variables on Render
Go to: Your Service → Environment → Add variable

| Key | Value |
|-----|-------|
| GOOGLE_SHEET_ID | 1ajWKs867tssC1DqY-miGiLG61eNZIKoZCpv5x-18LvY |
| GOOGLE_CREDENTIALS | (paste entire JSON from Google Service Account key file) |
| ALERT_EMAIL | your@email.com |
| GMAIL_USER | yourmail@gmail.com (for email alerts) |
| GMAIL_PASS | your_gmail_app_password |
| CALLMEBOT_KEY | your_callmebot_key (for WhatsApp alerts) |
| WHATSAPP_PHONE | +2348012345678 |

## Step 4 — Connect Google Sheets
1. console.cloud.google.com → New Project → Enable Google Sheets API
2. IAM → Service Accounts → Create → Download JSON key
3. Open your Google Sheet → Share → paste service account email → Editor
4. Paste JSON content as GOOGLE_CREDENTIALS on Render

## Step 5 — Connect dashboard to backend
1. Open `frontend/index.html` in a text editor
2. Find: `let API_URL = localStorage.getItem('ch_api') || 'http://localhost:5000'`
3. Change to: `let API_URL = localStorage.getItem('ch_api') || 'https://chfarms-api.onrender.com'`
4. Save → open in browser → sign in → system is live

## Step 6 — WhatsApp alerts (free)
1. Open WhatsApp → send to +34 698 891 767:
   `I allow callmebot to send me messages`
2. You receive a free API key in reply
3. Set CALLMEBOT_KEY + WHATSAPP_PHONE on Render

## User PINs
| User | PIN | Role |
|------|-----|------|
| Iyanu | 1234 | Admin (full access + sync) |
| John | 2001 | Counter (daily log) |
| Taiwo | 3001 | Egg & Feed |
| Nana | 4001 | Processing |
| Sunday | 5001 | Layer Counter |

## Google Sheet tabs used
- `03_Broiler Live Log` — daily mortality + feed log
- `07_Customer_Order_Quote` — buyer quotes written back automatically
- `05_Egg_Stock_Log` — egg daily harvest
- `04_Vaccine_Drug_Log` — vaccine administration
- `02_Processing Log` — processing sessions
