# Ledger

SBIR/STTR award operations: contracts, contract-specific labor costing, and
self-service time. Not the official accounting book. See `docs/DECISIONS.md`
and `docs/BUILD_PLAN.md`.

## Run on this computer (you only)

The API listens on **:8000**. For day-to-day edits, the React UI (Vite) listens
on **:5173**.

```text
# one-time
python tasks.py install
python tasks.py db-init
cd web && npm install && cd ..

# terminal 1 — API
python tasks.py run

# terminal 2 — UI
cd web
npm run dev
```

Open `http://127.0.0.1:5173`. Log in with the bootstrap admin from `.env`
(default `ben` / `changeme`) unless you already created users — then use the
password in the database, not a later `.env` change. Copy `.env.example` to
`.env` and set `LEDGER_SECRET_KEY` before sharing the instance.

`python tasks.py backup` copies the SQLite file to
`%LOCALAPPDATA%\ledger\backups\` (or `$LEDGER_DATA_DIR/backups/`).

## Share with teammates (one URL)

Teammates should not install Node. One host runs Ledger; others open a
browser (D28). SQLite stays on that host’s local disk (D15).

1. Set `LEDGER_SECRET_KEY` in `.env` to something other than
   `dev-only-change-me`. Change your admin password in the app
   (**Password**), not by editing `LEDGER_BOOTSTRAP_ADMIN_*` after users
   already exist.
2. Build the website: `python tasks.py build-ui` (needs Node.js on the host).
3. Set `LEDGER_API_HOST=0.0.0.0` in `.env`. Leave it `127.0.0.1` if you do
   not want the LAN to reach the process. `tasks.py run` will refuse
   `0.0.0.0` while the shipped secret is still in use.
4. Restart: `python tasks.py run`.
5. Teammates open `http://<this-computer>:8000` (hostname or IPv4). Allow
   inbound TCP **8000** in Windows Firewall. Keep the process running when
   you log off (Task Scheduler or equivalent) if they need it after hours.

Do not point teammates at Vite `:5173`. HTTPS and SSO are out of v1 (D13).

Screens in `web/`: `/login`, `/me/week`, `/me/password`, `/approvals`,
`/awards/:id`, `/portfolio`, `/people` (admin: capacity and assignments),
`/instruments` (admin: shared costs), `/compliance` (admin: due dates),
`/alerts` (admin: 75% and PoP), `/audit` (admin: event log and charges CSV).
