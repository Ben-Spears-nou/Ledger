# Ledger — one copy per team

This folder is **one team’s instance**. Another team lead gets their own
copy. Do not merge SQLite files. Teammates only need a browser.

## What you need

- Python **3.11+** on PATH (the person who hosts the instance).
- This folder (from `python tasks.py pack`, or a zip of that output).
- Node.js is **not** required here if `web/dist/` is already present.

SQLite and uploaded files live on **this computer’s local disk**, default
`%LOCALAPPDATA%\ledger` (not a network share). Two copies on the same
Windows user would share that folder — set `LEDGER_DATA_DIR` in `.env`
if you must run more than one instance on one login.

## First start

1. Double-click `start-ledger.bat` (or run it from cmd).
2. First run creates `.venv`, writes `.env` with a unique secret, and
   initializes the database if needed.
3. Open `http://127.0.0.1:8000`. Log in with the bootstrap admin from
   `.env` (see `.env.example`: default `ben` / `changeme`) and change
   the password in the app.

## Teammates on the LAN

1. Confirm `web/dist/index.html` exists.
2. In `.env`, set `LEDGER_API_HOST=0.0.0.0` (the generated
   `LEDGER_SECRET_KEY` is already not the shipped default).
3. Restart `start-ledger.bat`.
4. Teammates open `http://<this-computer>:8000`. Allow inbound TCP
   **8000** in Windows Firewall. Keep the process running (Task
   Scheduler) if they need it after you log off.

Do not point anyone at Vite `:5173`. HTTPS/SSO are out of v1.

## Backup

`python tasks.py backup` (from this folder, using `.venv\Scripts\python.exe`)
copies the SQLite file to the data dir `backups\` folder.
