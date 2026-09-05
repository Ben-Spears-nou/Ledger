# Ledger

SBIR/STTR award operations: contracts, contract-specific labor costing, and
self-service time. Not the official accounting book. See `docs/DECISIONS.md`
and `docs/BUILD_PLAN.md`.

## Run the API and UI

The API listens on **:8000**. The React UI (Phase 2.5) listens on **:5173**.

```text
# one-time
python tasks.py install
python tasks.py db-init

# terminal 1 — API
python tasks.py run

# terminal 2 — UI (requires Node.js + npm)
cd web
npm install
npm run dev
```

Open `http://127.0.0.1:5173`. Log in with the bootstrap admin from `.env`
(default `ben` / `changeme`). Copy `.env.example` to `.env` and change
`LEDGER_SECRET_KEY` before sharing the instance.

`python tasks.py backup` copies the SQLite file to
`%LOCALAPPDATA%\ledger\backups\` (or `$LEDGER_DATA_DIR/backups/`).

Screens in `web/`: `/login`, `/me/week`, `/approvals`, `/awards/:id`,
`/portfolio`, `/people` (admin: capacity and assignments), `/instruments`
(admin: shared costs). Phases 5–7 are not built.
