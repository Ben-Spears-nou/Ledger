# Ledger — Build Plan

This is the authoritative, phased specification. Build the phases **in order**.
Each phase lists Tasks and Acceptance Criteria. A phase is **Done** only when
every acceptance criterion passes and its tests are green.

`docs/DECISIONS.md` is the product source of truth (D1–D31). When `db/schema.sql`
exists, it is the data-model source of truth — mirror it; do not invent, rename,
or drop columns without proposing the change in `DECISIONS.md` first.

> Context: Ledger tracks SBIR/STTR (and related) awards for a small research
> team. The operator enters agency/contract/grant facts when an award is won,
> defines that award’s labor-costing policy, and is the only time approver.
> Employees log their own hours. Ledger is **not** the official accounting book.
> See `docs/DECISIONS.md`.

**This document specifies Phases 0–5.** Phases 6–7 stay listed at the
bottom so they are not forgotten; do not implement them until 5 is Done.

---

## Phase 0 — Project setup

**Tasks**

- Initialize the Python project from `pyproject.toml`; create a virtualenv.
- Set up `ruff`, `black`, `pytest`, and pre-commit hooks.
- Create the package skeleton under `src/ledger/`:
  `config.py`, `db/`, `models/`, `schemas/`, `api/`.
- Load configuration from `.env` (copy `.env.example`).
- Add a `Makefile` (or `tasks.py`) with `install`, `lint`, `test`, `run`,
  `db-init` (`build-ui` and `backup` were added later).
- Add `.gitignore` covering `.env*`, `venv/`, `__pycache__/`, `data/`,
  local SQLite files, and node_modules (for the later UI).
- Scaffold an empty React + Vite app under `web/` **or** defer the UI folder
  until Phase 1 screens exist — but record the choice in `DECISIONS.md` if
  deferred. API-first is acceptable in Phase 0. **Chose deferral (D14).**

**Acceptance criteria**

- `make lint` and `make test` run with zero errors (tests may be trivial here).
  On Windows without GNU make, `python tasks.py lint` / `python tasks.py test`
  (or `make.bat lint`) are the same targets.
- `python -c "import ledger"` succeeds.
- No award, time, or money tables are required yet. Do not invent a schema
  in this phase beyond what Phase 1 will need documented.

---

## Phase 1 — Identity, awards, rate policy, and budgets

Auth and award intake before any dashboard. Employees exist as users; they
cannot yet log time (that is Phase 2).

**Tasks**

### Schema and persistence

- Write `db/schema.sql` and `docs/SCHEMA_NOTES.md` for Phase 1–2 entities
  only. Propose the table list in `DECISIONS.md` if it differs from the
  freeze below; then ask before expanding.
- Execute `db-init` (SQLite). SQLAlchemy 2 models mirror **every** table
  exactly. Alembic initial migration so schema == models.
- Money columns are integer cents. `PRAGMA foreign_keys=ON` on every
  connection.
- Seed lookups: award instrument, mechanism, phase, type, status, budget
  category, rate-policy templates, roles (`employee`, `admin`).
- Keep `organization_id` on relevant tables (D8). Seed one organization.
  No multi-company UI.

### Identity

- `user_account` ↔ `person`. Password (or equivalent) auth.
- Roles: `employee` | `admin` only (D9). Seed the operator as `admin`.
- Employees cannot edit awards, budgets, or rate policies.

### Award create (“new contract won”)

Required fields:

- Short code, title
- Agency (text; optional growing lookup — D1)
- Instrument: `contract` | `grant` | `internal`
- Mechanism: `SBIR` | `STTR` | `other`
- Phase: `I` | `II` | `IIB` | `III` | `n/a`
- Type: `CPFF` | `FFP` | `TM` | `grant` | `internal`
- Status: at least `pipeline` | `active` | `closed`
- PoP start/end; funded-through (nullable)
- Awarded/ceiling cost, funded amount, fee pot (nullable; used for CPFF)

Optional: CLINs; option lines (value + exercise window + not-exercised).
Option lines are pipeline until exercised (D4).

Stamp a **rules profile** from type:

| Type | Enforce remaining as a ceiling? | Labor is incurred against the award? | Fee |
|---|---|---|---|
| CPFF / grant | Yes — warn/block at funded and at estimated cost (configurable %) | Yes | Fixed pot; not a % of overrun |
| FFP | No block on actuals; show internal margin vs price | Yes for utilization/cost, not customer billing | Price is the award; no CPFF fee engine |
| T&M | Hour/ceiling checks when catalog is used | Yes, at catalog rate; also show internal burden | n/a |
| Internal | No federal ceiling | Yes, so hours can land somewhere | n/a |

### Award rate policy (D11) — required on create

- Pick a template (`CPFF_SBIR`, `FFP_INTERNAL`, `TM_CATALOG`, `GRANT`,
  `INTERNAL`) then edit. Templates fill the form only.
- Fields: `cost_basis` (`base` | `wrapped` | `fully_burdened` | `catalog`);
  `fringe_pct`, `oh_pct`, `ga_pct`, `fee_pct`; `fee_in_burden`;
  `labor_budget_line_id` (where loaded labor will post in Phase 2).
- Optional `award_rate_override` rows (person and/or labor category →
  loaded cents).
- Policy is effective-dated. Revisions are new rows (D5).
- Show the apply-order formula on the form.

### Budgets

- Versioned budget tree on the award (`budget_version`, `budget_line`).
- Category lookup (personnel, fringe, travel, ODC, equipment, sub,
  indirect, fee) — editable seed, not hard-coded names.
- New award picks a category template by type, then the operator edits lines.
- One version is `active`. Remaining views with zero actuals/commits:
  `current_approved − 0`.
- Mods: dated change to money and/or PoP; can also start a new rate-policy
  row when rates change.

### API / UI (minimum)

- Login.
- Admin: create/edit award including rate policy; budget lines; mods.
- Employee: can log in; cannot mutate awards.
- Phase 1 operator UI is FastAPI `/docs` (D14). React/Vite is still deferred.

**Schema freeze (Phase 1–2; do not add tables without asking)**

```
organization
person
person_rate                 -- Phase 2 writes; table may exist in Phase 1
user_account
award
award_mod
clin                        -- optional rows
award_rate_policy
award_rate_override
budget_version
budget_line
```

Lookups as needed (`award_type`, `budget_category`, role, status, …).
Phase 2 adds timesheet + charge tables (see below). Views in Phase 1:
`v_budget_remaining` (actuals/commits = 0 until Phase 2).

**Acceptance criteria**

- `db-init` builds the SQLite database with tables, FKs, and
  `v_budget_remaining`.
- An admin can create a CPFF (or grant) award and an FFP award with
  **different** rate policies and budget templates.
- Remaining is correct with zero actuals; a mod that increases travel
  updates remaining.
- Fee on CPFF is a fixed pot, not a percent of overrun (test).
- Changing an award rate policy writes a new effective-dated row; the
  previous row is closed, not overwritten (D5).
- An `employee` user cannot edit another award’s budget or policy.
- Agency can be a new string without a code change (D1).
- Pipeline status does not add option/proposal value into remaining (D4).
- Tests cover the rules-profile difference between CPFF ceiling behavior
  and FFP (no contractual ceiling block — even if actuals are still zero
  in this phase, the flag/profile must be stored and readable).

---

## Phase 2 — People, base rates, self-service time

**Tasks**

### People and base rates

- `person_rate`: effective-dated **base only** (hourly cents, or salary
  cents + `hours_per_year` to derive hourly). No company-wide wrap as the
  labor source of truth (D11).
- Hire/term dates; labor category optional (for catalog overrides).

### Timesheets

- Calendar week as a `timesheet_period` (grouping only).
- `timesheet_line`: award, optional task (task table may wait for Phase 3
  — if absent, charge code is award only), work date, hours.
- Employee **My week**: select award → hours. No rate inputs.
- Autopopulate for the admin/preview path: loaded $/hr and line $ from
  person base as-of date × award policy as-of date × override if any (D11).
- Employee UI shows hours + award only, not dollars (D11).
- **No hour constraints** (D10): no required total, no 40-hour check, no
  match-to-schedule, no warn-on-submit. Running total is informational.
- Status: `draft` → `submitted` → `approved` | `returned` (comment).
- Employee submits; only admin approves (D9). Admin may approve their own.
- Returned weeks go back to draft.

### Charges (on approve only)

- Insert `charge` rows; snapshot:

  `base_rate_cents`, `fringe_pct`, `oh_pct`, `ga_pct`, `fee_pct`,
  `fee_in_burden`, `loaded_rate_cents`, `hours`, `amount_cents`,
  `person_rate_id`, `policy_id`, `override_id` (nullable)

- `charge.source = labor`. One loaded amount per approved line; do not
  explode into fringe/OH/G&A lines (D11, D13).
- Post to `award_rate_policy.labor_budget_line_id`.
- If `fee_in_burden` is false, do not move the fee pot when hours post.
- Corrections: reversing charge + new charge (D5).

### Non-award time

- First-class codes so hours can land off a federal award: at least
  `pto`, `holiday`, `ird`, `bp` (bid & proposal). These do not consume
  award remaining. PTO does **not** hit an SBIR award unless a later
  decision says so.

### API / UI (minimum)

- `/login`, `/me/week` (employee home), `/approvals` (admin queue),
  award page actuals + remaining after approve.
- `/people` (admin): base rates.

**Additional schema (Phase 2)**

```
timesheet_period
timesheet_line
charge
```

Views: `v_budget_remaining` now includes actuals; `v_award_burn_monthly`
and `v_person_utilization` if cheap — otherwise defer burn views to Phase 6.

**Acceptance criteria**

- Two users: employee A cannot see employee B’s draft time.
- Admin approves A’s week; award actuals and remaining move.
- Same person logs 2 hours on Award A and 2 hours on Award B; **dollar
  amounts differ** if the policies differ (test).
- Change Award A’s OH (new policy row). Already-approved charges
  unchanged; a new week uses the new OH (D5).
- Employee can submit a 3-hour week; a 60-hour week is also accepted
  (D10).
- FFP actuals do not trip a contractual ceiling block (D1 rules profile).
- Employee week does not display dollars; admin approve queue does.
- Rate change on a person does not rewrite last period’s posted charges.
- Employee cannot post to a `closed` award.
- Re-approving or re-submitting the same approved week does not duplicate
  charges.

---

## Phase 2.5 — Share-readiness

Insert between 2 and 3 so colleagues can use Ledger without `/docs`. Do not
build Phase 3–7 here.

**Tasks**

### Docs and schema

- Record D18–D21. Add `audit_event` and `user_account.password_changed_at`
  (proposed in DECISIONS first). Alembic `0003_phase25_share`.
- My week UI must tolerate a future optional `task_id` on timesheet lines
  (Phase 3) without a redesign: render award + hours now; ignore unknown
  fields.

### A. Visibility (API)

- Employee `GET /awards` and `GET /awards/{id}` = slim DTO (D18).
- Admin detail and remaining stay `AwardOut`.
- Employee cannot `GET /people` or `/people/*/rates`. `/lookups` must not
  leak burden percents to employees; My week still needs open awards
  (picker) and `time_codes`. Prefer `GET /awards` as the picker.
- `/me/week` hours-only. `/approvals` admin + dollars.

### B. Auth hardening

- `POST /auth/password` `{current_password, new_password}` for the logged-in
  user. Tokens minted before `password_changed_at` return 401 (D20).
- Warn on startup if `LEDGER_SECRET_KEY` is the shipped default (log; do
  not crash tests). No OAuth, SSO, or email.

### C. Audit

- Append-only `audit_event` writes from existing services (D19).
- `GET /admin/audit` admin-only JSON list. No filters/export (Phase 7).

### D. Backup

- `tasks.py backup` (+ Makefile / make.bat target) copies SQLite to
  `data-dir/backups/` with a timestamp (D21).

### E. React + Vite under `web/`

Screens only: `/login`, `/me/week`, `/approvals`, `/awards/:id`, optional
`/portfolio`. Token in `sessionStorage`. No dollars on `/me/week`. Talk
only to the HTTP API (`localhost:5173` → `:8000`). No Phase 3–7 routes.

**Acceptance criteria**

- Docs list Phase 2.5; D18–D21 exist; schema matches models + Alembic.
- Employee cannot read another employee's rates or an award's `fringe_pct`
  / `fee_pot` (tests).
- Password change succeeds; old token then 401 (test).
- Approving a week writes `audit_event` (test).
- `python tasks.py backup` creates a timestamped copy (test).
- `python tasks.py lint` and `python tasks.py test` stay green, including
  Phase 0–2 tests.
- `web/`: login → employee can save and submit a week against a real award;
  admin can open `/approvals`, see $, approve, and see remaining move on
  `/awards/:id`.
- Phase 3 is still “do not build” in this document until 2.5 is Done.

---

## Phase 3 — Tasks, assignments, capacity, My week prefill

Schedule proposes; the timesheet records (D7). Do not build Phase 4–7 here.

**Tasks**

### Schema

- Propose D22–D24 in `DECISIONS.md`, then add tables/columns to `db/schema.sql`.
  Alembic `0004_phase3_schedule`. `CREATE TABLE IF NOT EXISTS` will not add
  `timesheet_line.task_id` on an existing database — bootstrap must `ALTER`.
- New tables only:

```
task
assignment
person_capacity
```

- `timesheet_line.task_id` is nullable. Charge rows do not grow a `task_id`
  (join through the line). No `pipeline_node`, purchases, or documents.
- Hours on assignments and capacity are integer hundredths, same as
  timesheet lines. Money stays cents. No new percent columns.

### Tasks (under an award)

- A task is a work package on one award: `short_code`, `title`, `status_code`
  (`open` | `closed`). Unique `(award_id, short_code)`.
- Charge code remains the **award** (D18, D22). Tasks are not a second
  project list. Employee `GET /awards` is still the slim card.
- Admin: `POST/PATCH /awards/{id}/tasks`. Close is a status, not a delete.
- Employee: `GET /awards/{id}/tasks` and `GET /tasks` (picker) return a slim
  DTO: `task_id`, `award_id`, `short_code`, `title`, `status_code`. No money.
- Closed awards reject new tasks. Closed tasks reject new assignments and
  new timesheet lines; existing draft lines may still be saved until submit
  if the operator already attached them — **new** writes with a closed
  `task_id` fail.
- Timesheet `time_code` that does not consume an award (`pto`, `holiday`,
  `ird`, `bp`) cannot carry `task_id` or `award_id`.

### Assignments

- Admin assigns a person to an award, optional task, date range, and
  **planned hours per week** (`hours_hundredths_per_week`).
- Revisions are new rows; close the previous open row for the same
  person + award + task (D5 pattern). Do not edit posted charges.
- Overlap with a week: `effective_from <= week_end` and
  (`effective_to` is null or `>= week_start`). If it overlaps at all, the
  full weekly hours prefill — do not prorate (D23).
- Cannot assign to a `closed` award or `closed` task.
- Employee `GET /assignments` is **own rows only**. Admin lists all.
  Payload is hours + award/task ids, not dollars.

### Capacity

- `person_capacity`: effective-dated **hours per week** (hundredths), like
  `person_rate`. Zero is allowed (unassigned / leave). Revisions close the
  previous open row.
- Admin `GET /capacity?week_start=` returns, per person with a login:
  capacity hours, planned hours (sum of overlapping assignment weeks),
  and `over_capacity` (planned > capacity). Informational only (D10, D24).
- Employees cannot read `/capacity` or another person's capacity rows.

### My week prefill (D7, D10)

- `GET /me/week` on a **newly created** empty draft copies overlapping
  assignments into lines: `time_code=award`, `award_id`, optional `task_id`,
  `work_date=week_start` (Monday), hours = that assignment’s weekly hours.
- Skip closed awards/tasks. Skip assignments that do not overlap.
- **Do not** prefill when the period already existed (employee cleared
  lines, or already saved). **Do not** auto-submit or auto-post charges.
- Employee may edit, delete, add PTO, or submit 0 / 3 / 60 hours. Submit
  must not require matching assignments.
- `PUT /me/week` accepts optional `task_id`. Extra unknown fields stay
  ignored. Invalid `task_id` is 400, not silently dropped.
- `/me/week` still has no dollars. Approvals may show task short code
  beside the award; dollars stay admin-only.

### API / UI (minimum)

- `/me/week` — optional task select (filtered by selected award); prefill.
- `/awards/:id` — admin: tasks and assignments for this award.
- `/people` — admin: dated capacity, assignments, planned vs capacity for
  a week. Base-rate POST remains the existing `/people/{id}/rates` API
  (no new rate UI required).
- Vite proxy must include `/tasks`, `/assignments`, `/capacity`.

**Acceptance criteria**

- `db-init` / Alembic head create `task`, `assignment`, `person_capacity`,
  and `timesheet_line.task_id`. ORM tables still match `schema.sql`.
- Admin creates two tasks on one award; employee picker lists them as slim
  DTOs; `GET /awards` employee card keys are **unchanged** (D18).
- Employee cannot `POST` tasks, assignments, or capacity (403).
- Employee A cannot `GET` employee B’s assignments or capacity.
- Empty first `GET /me/week` for a week covered by an assignment prefills
  hours + award + task; a second assignment on another award adds a second
  line; dollars are absent from the payload.
- Saving a week, then changing assignments, does **not** rewrite the saved
  week on the next GET.
- Employee can submit a week that ignores the prefill (different hours or
  awards). Approve still posts labor $ from the award policy (D11), not
  from planned hours. Assignments never insert `charge` rows.
- Closed award / closed task reject new assignments and new time lines.
- PTO line with `task_id` is 400.
- Capacity revision is a new row; previous row is closed, not overwritten.
- Planned hours above capacity set `over_capacity` on the admin week view
  and do **not** block submit (D10).
- `python tasks.py lint` and `python tasks.py test` stay green, including
  Phase 0–2.5 tests (the Phase 2.5 “ignore task_id” test becomes “invalid
  task_id is rejected; extra unknown fields still ignored”).
- Phase 4 is still “do not build” in this document until 3 is Done.

---

## Phase 4 — Purchases, travel, commitments, instrument splits

Non-labor money that is **committed** until invoiced, then posted as a
`charge` (D4, D25). Do not build Phase 5–7 here. Not QuickBooks (D3).

**Tasks**

### Schema

- Propose D25–D27 in `DECISIONS.md`, then add tables to `db/schema.sql`.
  Alembic `0005_phase4_commitments`. Views must stop hard-coding
  `committed_cents = 0`.
- New tables only:

```
commitment
instrument
instrument_share
```

- `charge.source` already allows `purchase` | `travel` | `instrument`.
  Posting a commitment inserts one charge and marks the commitment
  `posted`. Do not add GL accounts, vendor masters, or attachment columns.

### Purchases and travel

- Admin `POST /purchases` and `POST /travel` insert an **open** commitment
  (kind `purchase` or `travel`) on one award: category, amount cents,
  description, optional vendor; travel may name a `person_id` and trip
  dates. Status starts `open` (it is committed money).
- Closed or pipeline awards reject new commitments.
- CPFF/grant (`enforce_ceiling`): creating an open commitment that would
  make `remaining_approved` negative is 400. FFP/internal do not block (D1).
- `POST /commitments/{id}/post` writes a `charge` (same cents and
  category, `source` = kind) and sets status `posted`. Open commitment
  cents leave `committed`; they become `actual`. CPFF blocks post when
  `remaining_funded` would go negative (same funded check as labor).
- `POST /commitments/{id}/cancel` is allowed only while `open`. Posted
  rows are not edited: reverse charge + new charge (D5). v1: cancel-after-
  post is out of scope (no reverse UI); API may expose reverse later.
- Employees 403 on all of the above. `GET /awards` employee card unchanged.

### Instrument splits (D26)

- An instrument is a shared cost (equipment, facility, other) with a total
  in cents and dated `effective_from` / `effective_to`.
- Shares are `share_pct` integer hundredths of a percent (D16). On one
  instrument they **must sum to 10000** (100.00%). At least one share.
- Creating an instrument inserts one **open** commitment per share:
  `cents = amount * share_pct // 10000`, last share gets the remainder so
  cents sum to the total (D27).
- Revisions are a **new** instrument row (close the previous with
  `effective_to`). Do not rewrite posted charges. Open commitments on a
  closed-out instrument must be cancelled first, or the previous row is
  still `open` only if nothing posted — v1: cannot revise; cancel open
  commitments and create a new instrument.
- `POST /instruments/{id}/post` posts every still-open share commitment.
- Admin `GET /instruments` and `GET /instruments/{id}`. Employees 403.

### Remaining (D4)

- `v_budget_remaining.committed_cents` = SUM of `open` commitments.
- `remaining_approved_cents` = `approved − committed − actual` (0 if
  pipeline).
- `remaining_funded_cents` stays `funded − actual` (labor tests).
- Line remaining: `approved − committed − actual` by `category_code`.
- Unexercised options still excluded.

### API / UI (minimum)

- `/awards/:id` — admin: purchases, travel, open/posted commitments,
  post and cancel.
- `/instruments` — admin: create a split cost, list, post.
- Vite proxy `/purchases`, `/travel`, `/commitments`, `/instruments`.

**Acceptance criteria**

- Views report committed cents; ORM matches `schema.sql`; Alembic head
  includes `0005_phase4_commitments`.
- Open purchase reduces remaining_approved, not actual; posting moves the
  same cents from committed to actual; remaining_approved is unchanged by
  the post (commit replaced by actual).
- Travel commitment uses category `travel`.
- Two-award 60/40 instrument of $100.00 posts $60.00 and $40.00; share
  percents that do not sum to 10000 are 400; rounding remainder lands on
  the last share.
- Employee 403 on purchases, travel, instruments, and commitment post.
  D18 award card keys unchanged.
- FFP purchase over remaining_approved succeeds; CPFF that would make
  remaining_approved negative is 400.
- Cancelled open commitment restores remaining_approved; does not insert
  a charge.
- Re-posting a posted commitment is 409/400 and does not duplicate charges.
- Closed/pipeline awards reject new purchases.
- `python tasks.py lint` and `python tasks.py test` stay green, including
  Phase 0–3.
- Phase 5 documents wait for this phase to be Done.

---

## LAN browser access (D28) — not a numbered phase

After Phase 4, teammates need one URL on the host machine. This is not
Phase 6–7.

**Tasks**

- Record D28. Default bind stays `127.0.0.1`.
- `python tasks.py build-ui` runs `npm run build` in `web/`.
- FastAPI serves `web/dist/` when `index.html` exists: HTML navigation
  gets the SPA; JSON `fetch` still hits the API (same paths as Vite’s
  `bypass` for `text/html`).
- `tasks.py run` reads `LEDGER_API_HOST` / `LEDGER_API_PORT`. Refuse
  non-loopback bind if `LEDGER_SECRET_KEY` is the shipped default.
  `--reload` only on loopback.
- UI `fetch` uses `window.location.origin` unless `VITE_API_URL` is set.
- README: build UI, opt-in `0.0.0.0`, firewall, URL `http://<host>:8000`.

**Acceptance criteria**

- Default `LEDGER_API_HOST` is `127.0.0.1`; tests stay green without a
  built UI.
- With a fixture `web/dist`, `GET /login` with `Accept: text/html` is
  the SPA; `GET /health` stays JSON; JSON `GET /awards` is still the API.
- `python tasks.py lint` and `python tasks.py test` stay green.
- Phase 6 is still “do not build” in this document.

---

## Phase 5 — Documents, award files, compliance dates

A register of award documents with optional files on local disk, plus
dated compliance obligations (D29–D31). Do not build Phase 6–7 here.
Not a document-management product. Files are not remaining money (D4).

**Tasks**

### Schema

- Propose D29–D31 in `DECISIONS.md`, then add tables to `db/schema.sql`.
  Alembic `0006_phase5_documents`. Do not change remaining views.
- `db-init` must apply `CREATE INDEX` **after** `ensure_phase3_schema` so
  existing `timesheet_line` rows without `task_id` can be altered first.
- New objects only:

```
document_kind
compliance_kind
compliance_status
document
compliance_item
```

### Documents

- Admin `POST /awards/{id}/documents` JSON: `kind_code`, `title`, optional
  `document_date`, `notes`. Pipeline and closed awards are allowed.
- Admin `POST /documents/{id}/file` multipart field `file`. Store under
  `LEDGER_DATA_DIR/documents/{award_id}/`. 20 MiB cap. Suffix whitelist
  (D29). Replacing a file is a new document row, not an overwrite (D5);
  v1: one file per document; second upload is 409.
- Admin `GET /awards/{id}/documents`, `GET /documents/{id}`,
  `GET /documents/{id}/file` (authenticated download).
- Employees 403. D18 card unchanged. Remaining cents unchanged.

### Compliance

- Admin `POST /awards/{id}/compliance`: `kind_code`, `title`, `due_date`,
  optional `notes`. Status starts `open`.
- Admin `PATCH /compliance/{id}`: `status_code` (`open` | `done` |
  `waived`) and optional `notes`. `done` sets `completed_at`.
- Admin `GET /awards/{id}/compliance` and `GET /compliance` (optional
  `due_from`, `due_to`, `status_code`, `award_id`) ordered by `due_date`.
- Employees 403. No email, no 75% burn alerts (Phase 6).

### API / UI (minimum)

- `/awards/:id` — admin: document list, add metadata, attach file,
  download; compliance list, add due date, mark done/waived.
- `/compliance` — admin calendar across awards.
- Vite proxy `/documents`, `/compliance` (HTML bypass for `/compliance`).
- Lookups: `document_kinds`, `compliance_kinds`, `compliance_statuses`
  (admin `/lookups` only).

**Acceptance criteria**

- ORM matches `schema.sql`; Alembic head is `0006_phase5_documents`.
- Document without file lists; upload then download returns the bytes.
- Oversize or bad suffix is 400; second file on the same row is 409.
- Employee 403 on documents, file, and compliance. D18 keys unchanged.
- Creating a document does not change `remaining_approved_cents`.
- Compliance `done` sets `completed_at`; calendar `GET /compliance`
  returns the item by `due_date`.
- `db-init` succeeds on a pre-Phase-3 `timesheet_line` (no `task_id`
  column) without `--force`.
- `python tasks.py lint` and `python tasks.py test` stay green, including
  Phase 0–4.
- Phase 6 is still “do not build” in this document.

---

## Later phases (do not build yet)

Recorded so Phase 5 does not “helpfully” grow into them.

| Phase | Scope |
|---|---|
| 6 | Pipeline nodes, burn/EAC/runway, 75% and PoP alerts |
| 7 | Audit log UI, convenience CSV of charges — still not QuickBooks |

UI map for orientation (implement screens only when the phase needs them):

- `/login` — Phase 2.5
- `/me/week` — employee home (Phase 2.5; task + prefill in Phase 3)
- `/me/password` — change password (Phase 2.5 / D20)
- `/portfolio` — award cards (Phase 2.5 optional)
- `/awards/:id` — remaining; tasks + assignments (Phase 3); purchases/travel (Phase 4); documents + compliance (Phase 5)
- `/approvals` — submitted time (Phase 2.5)
- `/people` — capacity and assignments (Phase 3)
- `/instruments` — shared costs and splits (Phase 4)
- `/compliance` — due dates across awards (Phase 5)
- `/admin` — users, categories, templates
