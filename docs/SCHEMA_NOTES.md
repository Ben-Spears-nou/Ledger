# Schema notes

`db/schema.sql` is the data-model source of truth. This file is the dictionary.
Propose column changes in `docs/DECISIONS.md` before editing the SQL.

Money is **integer cents**. Percents (`fringe_pct`, `oh_pct`, `ga_pct`,
`fee_pct`) are **integer hundredths of a percent**: `3215` means 32.15%.
The labor multiplier is `1 + pct / 10000` (D16).

Dates are ISO `YYYY-MM-DD`. Timestamps are SQLite `datetime('now')` text.

---

## Lookups

| Table | Key | Purpose |
|---|---|---|
| `organization` | `organization_id` | Single org in v1 (D8). Seeded as id 1. |
| `role` | `role_code` | `employee`, `admin` |
| `award_instrument` | `instrument_code` | `contract`, `grant`, `internal` |
| `award_mechanism` | `mechanism_code` | `SBIR`, `STTR`, `other` |
| `award_phase` | `phase_code` | `I`, `II`, `IIB`, `III`, `n/a` |
| `award_type` | `type_code` | Rules profile: `enforce_ceiling`, `labor_incurred`, `fee_engine`, `ceiling_warn_pct`, `overrun_policy` (`stop`/`warn`/`allow`) |
| `award_status` | `status_code` | `pipeline`, `active`, `closed` |
| `cost_basis` | `cost_basis_code` | `base`, `wrapped`, `fully_burdened`, `catalog` |
| `budget_category` | `category_code` | Editable seed; not hard-coded in app logic except personnel/fee helpers |
| `agency` | `agency_name` | Grows from the UI when a new string is used (D1) |
| `rate_policy_template` | `template_code` | Fills the create form only. Percents seed as 0 (do not fabricate rates) |
| `budget_template_line` | id | Default budget lines per `award_type` |

Admin `GET /lookups` also returns `audit_actions` and `audit_entity_types`
(Phase 8 / D37). Those are code lists for the Audit UI, not tables.

`award_type.fee_engine = fixed_pot` means fee is a stored pot (`award.fee_pot_cents`),
never `awarded_cost × fee_pct`.

---

## Identity

| Table | Notes |
|---|---|
| `person` | Hire/term dates, optional `labor_category` for catalog overrides |
| `person_rate` | Dated **base** only. Written in Phase 2; Phase 8 UI posts hourly or salary-derived cents |
| `user_account` | `username` + `password_hash` + `role_code`. One account per person. `password_changed_at` is set on `POST /auth/password` and admin `POST /people/{id}/password` (D20, D38). Username is not patched. Last active admin cannot be demoted or deactivated. |

---

## Awards

| Table | Notes |
|---|---|
| `award` | Intake fields plus a **stamped** copy of the type's rules profile (`enforce_ceiling`, `labor_incurred`, `fee_engine`, `ceiling_warn_pct`, `overrun_policy`). Type restamp only while unused (D39). Unused awards may be deleted; used awards close. |
| `award_mod` | History of money/PoP changes. New row per mod; award current fields update |
| `clin` | Optional CLINs. `is_option=1` and `exercised_at IS NULL` is pipeline money (D17). Phase 9 can add/patch/exercise; delete only while unexercised. |
| `budget_version` | One `is_active=1` per award (partial unique index) |
| `budget_line` | Approved cents on a version. Remaining is a view |
| `award_rate_policy` | Dated recipe (D11). Revisions are new rows (D5) |
| `award_rate_override` | Per person **or** labor category loaded cents |

`award_rate_policy.labor_budget_line_id` is where Phase 2 posts loaded labor.
It may be null until a personnel line exists.

---

## Views

`v_budget_remaining` (award rollup) and `v_budget_line_remaining` (per line):

- `actual_cents` is `SUM(charge.amount_cents)`
- `committed_cents` is `SUM(commitment.amount_cents)` where `status_code = open` (Phase 4)
- `remaining_*` is 0 when `status_code = pipeline`
- `unexercised_option_cents` and `pipeline_cents` are **not** included in remaining

---

## Time (Phase 2)

| Table | Notes |
|---|---|
| `time_code` | `award` (consumes remaining) plus `pto`, `holiday`, `ird`, `bp` (do not) |
| `timesheet_period` | One person × Monday `week_start`. Status `draft`/`submitted`/`approved`/`returned` |
| `timesheet_line` | `hours_hundredths` (250 = 2.50 hours). Optional `award_id`. Optional `task_id` (Phase 3) |
| `charge` | Posted fact. Labor snapshots the rate stack. Reversals are new rows (D5) |

Hours are integer hundredths, not float. API accepts/returns hours as a decimal
and converts.

`v_budget_remaining.actual_cents` is `SUM(charge.amount_cents)` per award.
Line remaining attributes actuals by `charge.category_code` so a budget mod
does not hide earlier labor.

---

## Audit (Phase 2.5)

| Table | Notes |
|---|---|
| `audit_event` | Append-only (D19). `who` (`actor_user_id`, nullable), `when` (`occurred_at`), `action`, `entity_type`, `entity_id` (text), optional JSON `detail`. Never update or delete rows. Phase 7 is the UI and charges CSV (D35, D36). Phase 8 adds lookup lists for action/entity filters (D37). |

Written for: login failure (never the password), password change, password reset, person create / update, person rate create, award create / update / delete, policy revision, week submit / approve / return, task create, assignment create, capacity create, commitment create / post / cancel / update, instrument create, document create / file, compliance create / status, pipeline create / update / delete, clin create / update / exercise / delete, funding expectation create / delete.

---

## Commitments (Phase 4)

| Table | Notes |
|---|---|
| `commitment` | Open / posted / cancelled. Kind `purchase`, `travel`, or `instrument`. Open cents are remaining committed (D25). Optional `expected_date` is aging only, not remaining (D42) |
| `instrument` | Shared cost header. Dated. Status follows its commitments |
| `instrument_share` | `share_pct` hundredths of a percent; must sum to 10000 per instrument (D26, D27) |

Posting inserts `charge.source` matching `commitment.kind`. Pipeline and closed awards reject new commitments.

---

## Schedule (Phase 3)

| Table | Notes |
|---|---|
| `task` | Work package on one award (D22). `status_code` `open`/`closed`. Unique `(award_id, short_code)` |
| `assignment` | Dated planned hours/week for a person on an award, optional task (D23). Prefill only |
| `person_capacity` | Dated available hours/week (D24). Zero allowed. Not a timesheet constraint |

Assignment and capacity hours are integer hundredths of an hour, like
`timesheet_line`. The API accepts/returns decimal hours per week.

`timesheet_line.task_id` must belong to the line’s `award_id` when both are
set. Non-award time codes cannot carry a task.

---

## Documents and compliance (Phase 5)

| Table | Notes |
|---|---|
| `document_kind` | Lookup: contract, mod, report, invoice, correspondence, other |
| `document` | Award register row. Optional file on local disk (D29), not a BLOB |
| `compliance_kind` | Lookup: technical_report, financial_report, pop_end, irb, iacuc, property, invoice, other |
| `compliance_status` | `open`, `done`, `waived` |
| `compliance_item` | Due date on an award. Not remaining money (D30). Optional `document_id` on the same award (D42) |

Files: `{data_dir}/documents/{award_id}/{document_id}{ext}`. Max 20 MiB.
Admin-only. Remaining views unchanged.

---

## Pipeline and burn (Phase 6)

| Table / view | Notes |
|---|---|
| `pipeline_kind` | Lookup: next_phase, commercial, proposal, other |
| `pipeline_node` | Forecast cents on an award. Not remaining (D32). Not a CLIN option (D17) |
| `v_award_burn_monthly` | `SUM(charge.amount_cents)` by award and `YYYY-MM` of `work_date` |

EAC and runway are computed (D33). Alerts are computed on read (D34): no alert table, no email.

---

## Operations (Phase 10)

| Table / column | Notes |
|---|---|
| `award.overrun_policy` | Stamped `stop` / `warn` / `allow` (D43). Hard 409 still uses `enforce_ceiling` on funded remaining |
| `award_type.overrun_policy` | Default profile copied onto the award at create / type restamp |
| `commitment.expected_date` | Expected invoice. Aging uses this or `effective_date`; not remaining |
| `compliance_item.document_id` | Optional link to a document on the same award; does not mark done |
| `funding_expectation` | Expected increment. Not remaining, not pipeline, not a CLIN (D42) |

Home, staffing, search, and close are computed. No extra remaining columns.

---

## Unused delete (Phase 11)

No new tables. `DELETE` unused register rows and `PATCH` assignment
`effective_to` (D45). Posted `charge` snapshots (`person_rate_id`,
`policy_id`) still block delete. Award mods stay append-only.
