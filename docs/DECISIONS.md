# Decisions & Scope

Short, ADR-style record of the choices baked into this build, so the agent
does not undo them. Propose changes here before editing `db/schema.sql` or
adding dependencies.

Ledger is an SBIR/STTR **award operations** tool: awards, contract-specific
labor costing, self-service time, remaining budget, and (later) schedule,
instruments, and documents. It is not ALTUM and must not live in that repo.

---

## D1 — Award facts are entered when an award is won (or proposed)

Every award carries its own agency, instrument (contract vs grant vs internal),
mechanism (SBIR / STTR / other), phase, and type (CPFF, FFP, T&M, grant, …).
The app is a form plus a rules profile, not a DoD-only or NIH-only product.

No WAWF, ASAP, eRA Commons, Research.gov, or SAM integrations.

Agency is stored as text (or a lookup that can grow from the UI). Do not
hard-code an enum of NIH/DoD only. New agencies must not require a migration.

Awards may be created with `status = pipeline` (proposal not yet won). Pipeline
money is excluded from remaining-to-spend (D4).

---

## D2 — Team members log their own time

Timesheets are a primary surface, not an admin afterthought. Each person has a
login and submits their own hours. Auth and roles belong in Phase 1–2, before
instruments and documents.

---

## D3 — Ledger is not the official book

No QuickBooks/Xero sync, no general ledger, no tax/GAAP export as a
requirement. Money in Ledger is **management actuals** for remaining budget,
burn, and staffing.

A convenience CSV dump of charges may come later (Phase 7). It is not a v1
success criterion. Do not add accountant-mapping columns “for later.”

---

## D4 — Five money states stay separate

Keep these distinct on every award:

1. **Approved budget** (awarded, then current after mods)
2. **Funded / obligated**
3. **Committed** (approved POs, travel, instrument splits not yet invoiced)
4. **Actual** (posted charges)
5. **Pipeline / forecast** (unexercised options, next phase, commercial)

Unexercised options and Phase II/III hopes never sit in “remaining to spend.”
`pipeline_node` must not have a user-facing “include in remaining” checkbox;
remaining views exclude pipeline by construction.

Remaining (view, not a stored column):

- `current_approved − committed − actual`
- and separately `funded − actual` (and funded − committed − actual)

FFP still computes internal actuals vs a management budget; it does not treat
remaining as a contractual ceiling.

---

## D5 — Rates and allocations are dated; history is not rewritten

Employee base rates, award rate policies, and (later) instrument splits are
effective-dated. A posted timesheet line **snapshots** the rate stack used.

Changing someone’s base rate or an award’s G&A next month does not change
already-approved charges. Policy revisions are **new rows**, not in-place
updates (same pattern as award mods).

Corrections to posted charges = reversing charge + new charge, not edits in
place.

---

## D6 — Time is the labor cost driver

Personnel actuals come from approved hours × the loaded rate in force on the
work date (D11). Monthly labor lump-sums are not the source of truth. A budget
line may still hold a *planned* personnel amount.

---

## D7 — Schedule proposes; timesheet records

Assignments (Phase 3+) may pre-fill the employee’s week. They do not auto-post
charges. Planned vs actual is a report. Prefill is UX, not a validation rule
(see D10).

---

## D8 — One organization for now

Keep `organization_id` on the schema. Do not build multi-company UI.

---

## D9 — Single approver

Only `admin` approves time. There is no manager-approval chain.

v1 roles are **`employee`** and **`admin`** only. The operator (Ben) is admin
and also logs time as an employee. Admin can approve others and can approve
their own (sole-approver bootstrap).

`/approvals` is an admin-only queue. Employees see Submitted / Returned /
Approved on their own weeks only. Bounce = comment + back to draft.

---

## D10 — Weeks are unconstrained

No required total, no 40-hour check, no “must match assignments,” no
warn-on-submit for hours. Show a running total as **information only**.

A week may be 0, 6, or 60 hours. Empty days are fine. Multiple awards per week
are fine. Period is still a calendar week for grouping.

---

## D11 — Labor costing is an award policy, not a company default

When an award is created, the operator defines **how hours on that award turn
into dollars**. When someone picks that award on a timesheet, loaded rate and
line $ are computed from:

- person **base** rate as-of the work date (`person_rate`)
- that award’s **rate policy** as-of the work date (`award_rate_policy`)
- optional per-person or per-labor-category **override** on that policy

Employees do not type rates and do not pick “wrapped” vs “fully burdened.”
The contract already did.

### Recipe (default path)

Apply order is fixed in code and shown on the award form:

```
loaded = base × (1 + fringe) × (1 + oh) × (1 + ga)
if fee_in_burden: loaded = loaded × (1 + fee)
```

Then `cost_basis` chooses what posts:

| `cost_basis` | What posts as labor $ |
|---|---|
| `base` | person base only |
| `wrapped` | after fringe + OH |
| `fully_burdened` | wrap + G&A (and fee only if `fee_in_burden`) |
| `catalog` | ignore person base; use a rate card / override on this award |

`fee_in_burden = false` is typical for CPFF incurred cost: fee stays in the
award fee pot and is not in the hourly $. `fee_in_burden = true` puts
`fee_pct` inside the hourly loaded rate (some FFP/internal views).

If a contract is not written as this recipe, use `catalog` or a per-person
override. Do not add a second formula engine in v1.

### Templates

Presets (`CPFF_SBIR`, `FFP_INTERNAL`, `TM_CATALOG`, `GRANT`, `INTERNAL`) only
fill the create form. The saved award owns the numbers. Templates are seed
data, not hard-wired agency logic.

Suggested template defaults:

- `CPFF_SBIR` — fringe+OH+G&A, `cost_basis=fully_burdened`, `fee_in_burden=false`
- `FFP_INTERNAL` — same structure; used for **margin** vs price, not a ceiling
- `TM_CATALOG` — `cost_basis=catalog`
- `GRANT` — same structure as CPFF, fee usually 0
- `INTERNAL` — often `cost_basis=base` or a light wrap, no fee

### Posting

On admin approve, write one `charge` for the **loaded** amount (not four
GL-like lines). Store the component percents and base on the charge so a
later split is possible. v1 posts to a single budget line named on the
policy (`labor_budget_line_id`).

Fee, when not in burden, does not move when hours post.

### Employee vs admin display

Employees see **hours + award/task** on My week. Dollars appear on the admin
approve queue and award pages. Preview math still runs on submit so the
approver sees $.

---

## D12 — Stack (default; change in one place)

Python 3.11+ · FastAPI · SQLAlchemy 2 · Pydantic v2 · SQLite (dev) · Alembic ·
React + Vite · pytest.

Ask before adding any dependency not in `pyproject.toml`. SQLite now;
PostgreSQL later if a second concurrent user or file store needs it.

Money is integer **cents**. Never float.

`tasks.py install` also queries public PyPI as an extra index because the
default corporate Artifactory here does not publish `setuptools`.

---

## D13 — Deferred (do not build without a request)

Phase 2.5 (share-readiness) is an official insert between 2 and 3. Do not
skip 2.5. Phase 3 is tasks/assignments/capacity. Phase 4 is purchases,
travel, commitments, and instrument splits. After 4 is Done, these remain
later:

- Phase 5 — Documents, compliance calendar
- Phase 6 — Pipeline nodes, burn/runway, 75% and PoP alerts
- Phase 7 — Audit *UI* and CSV dump (not books). The `audit_event` table
  itself is Phase 2.5 (D19).

Also out of v1: payroll/tax, depreciation engine, bank feeds, AI receipt
coding, agency e-file, invoice *submission*, multi-company UI, exploding
labor into fringe/OH/G&A journal lines, Postgres/HTTPS/SSO. Opt-in LAN
bind and same-origin UI are D28; they are not a cloud rewrite.

---

## D14 — React UI ships in Phase 2.5

Phases 0–2 were API-first. Phase 2.5 adds `web/` (Vite + React): `/login`,
`/me/week`, `/approvals`, `/awards/:id`, optional `/portfolio`. The UI talks
only to the FastAPI HTTP API. Bearer token lives in `sessionStorage`, not
the URL. `/me/week` never shows dollars, even for an admin on that route.
Vite on `:5173` is local development. Teammates use D28 (one origin).

My week renders award + hours (and, in Phase 3, optional task). Unknown
line fields stay ignored so later phases remain additive. Phase 4 may add
purchases/travel on `/awards/:id` and `/instruments`. Do not add
Phase 5–7 screens.

---

## D15 — SQLite and runtime files live on local disk

The repo may sit on a UNC share; the database must not. When `LEDGER_DB_URL`
is unset, SQLite is `%LOCALAPPDATA%\ledger\ledger.db` (or
`~/.local/share/ledger` on Unix). Override with `LEDGER_DATA_DIR`.

---

## D16 — Percents are integer hundredths of a percent

`fringe_pct` / `oh_pct` / `ga_pct` / `fee_pct` store `32.15%` as `3215`.
The labor multiplier is `1 + pct / 10000`. Not float. Money remains cents.

---

## D17 — Unexercised options are CLINs, not remaining

`clin.is_option = 1` and `exercised_at IS NULL` is pipeline money. Remaining
views never add it. A dedicated `pipeline_node` table waits for Phase 6.

`budget_template_line` and `rate_policy_template` are lookups, not new
domain tables beyond the Phase 1 freeze.

---

## D18 — Employee-visible award is a charge-code card, not AwardOut

`GET /awards` (and any picker the UI uses) returns a slim DTO for employees:

`award_id`, `short_code`, `title`, `status_code`, `phase_code`, `type_code`.

No remaining $, `fee_pot`, rate policy, CLINs, mods, or people rates.
Employee `GET /awards/{id}` returns the same slim DTO (not `AwardOut`).
Admin `GET /awards/{id}` and remaining stay full. Do not break `AwardOut`
for admin. This slim list is also the Phase 3 prefill charge-code source —
do not invent a second “project” list. Tasks are children of an award
(D22), not a parallel picker.

---

## D19 — Audit is an append-only event table now; Phase 7 is the UI/CSV

One `audit_event` table: who, when, action, entity_type, entity_id,
optional JSON detail. Write events for: login failure (never store the
password), password change, person/rate create, award create, policy
revision, week submit / approve / return, task create, assignment create,
capacity create, commitment create / post / cancel, instrument create. Do not
update or delete audit rows. `GET /admin/audit` is admin-only JSON.

---

## D20 — Tokens die when the password changes

`user_account.password_changed_at` is an ISO timestamp. Tokens carry `iat`.
`read_token` rejects a token whose `iat` is before `password_changed_at`.
`POST /auth/password` updates the stamp. No email reset in 2.5.

---

## D21 — Backup is a file copy, not a new product

`python tasks.py backup` copies the SQLite file into the local data dir
(`%LOCALAPPDATA%\ledger\backups\` or `$LEDGER_DATA_DIR/backups/`) with a
timestamp. No cloud, no cron daemon.

---

## D22 — Tasks belong to an award; they are not a charge code

A task is a named work package on one `award`. The timesheet charge code
is still the award. `GET /awards` (and `?as=picker`) stays the D18 card:

`award_id`, `short_code`, `title`, `status_code`, `phase_code`, `type_code`.

Do not add tasks, remaining, or dollars to that card. Employee task lists
are a separate slim DTO: `task_id`, `award_id`, `short_code`, `title`,
`status_code`. My week filters tasks by the selected award.

`timesheet_line.task_id` is optional. Labor $ still come from the award
rate policy (D11). Employees never type rates.

Proposed tables/columns (Phase 3 freeze; ask before adding more):

- `task` — `task_id`, `award_id`, `short_code`, `title`, `status_code`
  (`open` | `closed`), `created_at`, `created_by`
- `timesheet_line.task_id` — nullable FK to `task`

---

## D23 — Assignments propose a week; they do not post

An assignment is dated planned hours for one person on one award
(optional task). It prefills a **newly created** empty draft week (D7).
It does not insert `charge` rows, auto-submit, or rewrite a week the
employee already has.

If an assignment overlaps any day of the calendar week, prefill the
**full** `hours_hundredths_per_week` on Monday (`week_start`). No daily
proration. Multiple assignments → multiple lines.

Submit does not have to match the plan (D10). Planned vs actual is an
admin hours view, not a validation rule.

Proposed table:

- `assignment` — `assignment_id`, `person_id`, `award_id`, `task_id`
  (nullable), `hours_hundredths_per_week`, `effective_from`, `effective_to`,
  `created_at`, `created_by`

Revisions are new rows (D5). Audit `assignment_create` (D19).

---

## D24 — Capacity is dated hours/week, informational

`person_capacity` is effective-dated available hours per week (integer
hundredths), same pattern as `person_rate`. It is not money, not FTE as a
second unit, and not a timesheet rule. Planned assignment hours may exceed
capacity; the admin week view flags `over_capacity` and still allows
submit (D10).

Proposed table:

- `person_capacity` — `person_capacity_id`, `person_id`,
  `hours_hundredths_per_week` (>= 0), `effective_from`, `effective_to`,
  `created_at`, `created_by`

Revisions are new rows. Audit `capacity_create`. Employees cannot read
another person’s capacity.

---

## D25 — Open commitments are remaining, not actuals

A purchase, travel booking, or instrument share is **committed** while
`commitment.status_code = open`. It is not a `charge` yet. Remaining:

- `remaining_approved = current_approved − committed − actual`
- `remaining_funded` stays `funded − actual` (labor already uses this)

Posting writes one `charge` (`source` = `purchase` | `travel` |
`instrument`) for the same cents and category, then sets the commitment
`posted`. Cancel is only for `open` rows. Posted money is not edited in
place (D5).

Proposed table:

- `commitment` — `commitment_id`, `award_id`, `kind` (`purchase` |
  `travel` | `instrument`), `status_code` (`open` | `posted` |
  `cancelled`), `category_code`, `amount_cents`, `description`, `vendor`,
  `person_id` (nullable), `effective_date`, `trip_end` (nullable),
  `instrument_id` (nullable), `charge_id` (nullable), `created_at`,
  `created_by`

---

## D26 — Instrument splits are fixed percents, not a second formula

An instrument is a shared cost allocated to awards by **fixed percents**.
`share_pct` uses D16: `5000` is 50.00%. Shares on one instrument must
sum to `10000`. Do not add a second allocation engine.

Proposed tables:

- `instrument` — `instrument_id`, `organization_id`, `short_code`,
  `title`, `amount_cents`, `category_code`, `status_code` (`open` |
  `posted` | `cancelled`), `effective_from`, `effective_to`, `created_at`,
  `created_by`
- `instrument_share` — `instrument_share_id`, `instrument_id`, `award_id`,
  `share_pct`

Creating an instrument inserts one open commitment per share (D25).
Posting the instrument posts those commitments.

---

## D27 — Split cents are integer; last share takes the remainder

`cents_i = amount_cents × share_pct // 10000` for every share except the
last; the last share is `amount_cents − sum(previous)` so posted charges
sum to the instrument total. Never float.

---

## D28 — One machine serves the site; LAN bind is opt-in

Teammates open Ledger in a browser on their own computers. They do not
install Node or run Vite. `python tasks.py build-ui` writes `web/dist/`.
FastAPI serves that folder on the same origin as the API. Browser
navigation sends `Accept: text/html` and gets `index.html`; `fetch` from
the UI sends `Accept: application/json` and hits the API. Default
`api.js` calls are same-origin (no hardcoded `127.0.0.1:8000`).

`LEDGER_API_HOST` defaults to `127.0.0.1`. Sharing requires
`LEDGER_API_HOST=0.0.0.0` (or another non-loopback bind). `tasks.py run`
refuses a non-loopback bind while `LEDGER_SECRET_KEY` is still the
shipped default. HTTPS and SSO stay out of v1 (D13). SQLite stays on the
host’s local disk (D15). Windows Firewall and “stay up when I log off”
are OS work, not a product rewrite.
