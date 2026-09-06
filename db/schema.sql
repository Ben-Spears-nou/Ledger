-- Ledger Phase 1–6 schema. SQLite 3.31+.
-- Money is integer cents. Percents are integer hundredths of a percent
-- (3215 = 32.15%; multiplier is 1 + pct/10000). See docs/SCHEMA_NOTES.md.
-- db/schema.sql is the source of truth. Do not invent tables here.

PRAGMA foreign_keys = ON;

-- =====================================================================
-- Lookups
-- =====================================================================

CREATE TABLE IF NOT EXISTS organization (
    organization_id  INTEGER PRIMARY KEY,
    name             TEXT NOT NULL,
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);
INSERT INTO organization (organization_id, name) VALUES (1, 'Default Organization');

CREATE TABLE IF NOT EXISTS role (
    role_code    TEXT PRIMARY KEY,
    description  TEXT NOT NULL
);
INSERT INTO role (role_code, description) VALUES
    ('employee', 'Logs own time; cannot edit awards or policies'),
    ('admin',    'Sole time approver; owns awards, budgets, and rates');

CREATE TABLE IF NOT EXISTS award_instrument (
    instrument_code  TEXT PRIMARY KEY,
    description      TEXT NOT NULL
);
INSERT INTO award_instrument (instrument_code, description) VALUES
    ('contract', 'Federal or commercial contract'),
    ('grant',    'Grant (e.g. NIH/NSF SBIR)'),
    ('internal', 'Company IR&D / B&P / overhead');

CREATE TABLE IF NOT EXISTS award_mechanism (
    mechanism_code  TEXT PRIMARY KEY,
    description     TEXT NOT NULL
);
INSERT INTO award_mechanism (mechanism_code, description) VALUES
    ('SBIR',  'Small Business Innovation Research'),
    ('STTR',  'Small Business Technology Transfer'),
    ('other', 'Not SBIR/STTR');

CREATE TABLE IF NOT EXISTS award_phase (
    phase_code   TEXT PRIMARY KEY,
    description  TEXT NOT NULL
);
INSERT INTO award_phase (phase_code, description) VALUES
    ('I',    'Phase I'),
    ('II',   'Phase II'),
    ('IIB',  'Phase IIB / sequential / enhancement'),
    ('III',  'Phase III / commercialization'),
    ('n/a',  'Not a phased SBIR/STTR award');

CREATE TABLE IF NOT EXISTS award_type (
    type_code           TEXT PRIMARY KEY,
    description         TEXT NOT NULL,
    enforce_ceiling     INTEGER NOT NULL CHECK (enforce_ceiling IN (0, 1)),
    labor_incurred      INTEGER NOT NULL CHECK (labor_incurred IN (0, 1)),
    fee_engine          TEXT NOT NULL CHECK (fee_engine IN ('fixed_pot', 'none')),
    ceiling_warn_pct    INTEGER NOT NULL DEFAULT 75
        CHECK (ceiling_warn_pct BETWEEN 0 AND 100)
);
INSERT INTO award_type (
    type_code, description, enforce_ceiling, labor_incurred, fee_engine, ceiling_warn_pct
) VALUES
    ('CPFF',     'Cost Plus Fixed Fee',          1, 1, 'fixed_pot', 75),
    ('FFP',      'Firm Fixed Price',             0, 1, 'none',      75),
    ('TM',       'Time and Materials',           1, 1, 'none',      75),
    ('grant',    'Cost-reimbursable grant',      1, 1, 'fixed_pot', 75),
    ('internal', 'Internal / IR&D / B&P',        0, 1, 'none',      75);

CREATE TABLE IF NOT EXISTS award_status (
    status_code  TEXT PRIMARY KEY,
    description  TEXT NOT NULL
);
INSERT INTO award_status (status_code, description) VALUES
    ('pipeline', 'Proposed or not yet awarded; money is not remaining-to-spend'),
    ('active',   'Awarded and open'),
    ('closed',   'PoP ended or administratively closed');

CREATE TABLE IF NOT EXISTS cost_basis (
    cost_basis_code  TEXT PRIMARY KEY,
    description      TEXT NOT NULL
);
INSERT INTO cost_basis (cost_basis_code, description) VALUES
    ('base',            'Post person base rate only'),
    ('wrapped',         'Base after fringe and overhead'),
    ('fully_burdened',  'Wrapped plus G&A (and fee only if fee_in_burden)'),
    ('catalog',         'Ignore person base; use a rate card / override');

CREATE TABLE IF NOT EXISTS budget_category (
    category_code  TEXT PRIMARY KEY,
    description    TEXT NOT NULL,
    sort_order     INTEGER NOT NULL DEFAULT 0
);
INSERT INTO budget_category (category_code, description, sort_order) VALUES
    ('personnel', 'Direct personnel (loaded labor posts here in Phase 2)', 10),
    ('fringe',    'Fringe as a standalone bucket (optional)',              20),
    ('travel',    'Travel',                                               30),
    ('odc',       'Other direct costs / materials / supplies',            40),
    ('equipment', 'Equipment / instrumentation',                          50),
    ('sub',       'Subcontracts / consultants',                           60),
    ('indirect',  'Indirects shown as a budget line',                     70),
    ('fee',       'Fixed fee pot (CPFF); not a percent of overrun',       80);

CREATE TABLE IF NOT EXISTS agency (
    agency_name  TEXT PRIMARY KEY,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS document_kind (
    kind_code    TEXT PRIMARY KEY,
    description  TEXT NOT NULL
);
INSERT INTO document_kind (kind_code, description) VALUES
    ('contract',       'Award / contract / grant document'),
    ('mod',            'Modification or amendment'),
    ('report',         'Technical or progress report'),
    ('invoice',        'Invoice or voucher'),
    ('correspondence', 'Letter or email record'),
    ('other',          'Other');

CREATE TABLE IF NOT EXISTS compliance_kind (
    kind_code    TEXT PRIMARY KEY,
    description  TEXT NOT NULL
);
INSERT INTO compliance_kind (kind_code, description) VALUES
    ('technical_report', 'Technical / progress report due'),
    ('financial_report', 'Financial report due'),
    ('pop_end',          'Period of performance end'),
    ('irb',              'Human subjects / IRB'),
    ('iacuc',            'Animal care / IACUC'),
    ('property',         'Property or equipment report'),
    ('invoice',          'Invoice due to the sponsor'),
    ('other',            'Other obligation');

CREATE TABLE IF NOT EXISTS compliance_status (
    status_code  TEXT PRIMARY KEY,
    description  TEXT NOT NULL
);
INSERT INTO compliance_status (status_code, description) VALUES
    ('open',   'Not finished'),
    ('done',   'Completed'),
    ('waived', 'No longer required');

CREATE TABLE IF NOT EXISTS pipeline_kind (
    kind_code    TEXT PRIMARY KEY,
    description  TEXT NOT NULL
);
INSERT INTO pipeline_kind (kind_code, description) VALUES
    ('next_phase', 'Next SBIR/STTR phase or follow-on'),
    ('commercial', 'Commercial or customer follow-on'),
    ('proposal',   'Proposal not yet awarded'),
    ('other',      'Other forecast');

CREATE TABLE IF NOT EXISTS rate_policy_template (
    template_code      TEXT PRIMARY KEY,
    description        TEXT NOT NULL,
    award_type_code    TEXT NOT NULL REFERENCES award_type (type_code),
    cost_basis_code    TEXT NOT NULL REFERENCES cost_basis (cost_basis_code),
    fringe_pct         INTEGER NOT NULL DEFAULT 0 CHECK (fringe_pct >= 0),
    oh_pct             INTEGER NOT NULL DEFAULT 0 CHECK (oh_pct >= 0),
    ga_pct             INTEGER NOT NULL DEFAULT 0 CHECK (ga_pct >= 0),
    fee_pct            INTEGER NOT NULL DEFAULT 0 CHECK (fee_pct >= 0),
    fee_in_burden      INTEGER NOT NULL DEFAULT 0 CHECK (fee_in_burden IN (0, 1))
);
-- Percents stay 0 so we never fabricate a contract rate (D11).
INSERT INTO rate_policy_template (
    template_code, description, award_type_code, cost_basis_code,
    fringe_pct, oh_pct, ga_pct, fee_pct, fee_in_burden
) VALUES
    ('CPFF_SBIR',    'CPFF SBIR: fully burdened, fee not in hourly', 'CPFF',     'fully_burdened', 0, 0, 0, 0, 0),
    ('FFP_INTERNAL', 'FFP internal cost: fully burdened',            'FFP',      'fully_burdened', 0, 0, 0, 0, 0),
    ('TM_CATALOG',   'T&M catalog rates',                            'TM',       'catalog',        0, 0, 0, 0, 0),
    ('GRANT',        'Grant: fully burdened, no fee in hourly',      'grant',    'fully_burdened', 0, 0, 0, 0, 0),
    ('INTERNAL',     'Internal: base only',                          'internal', 'base',           0, 0, 0, 0, 0);

CREATE TABLE IF NOT EXISTS budget_template_line (
    budget_template_line_id  INTEGER PRIMARY KEY,
    award_type_code          TEXT NOT NULL REFERENCES award_type (type_code),
    category_code            TEXT NOT NULL REFERENCES budget_category (category_code),
    label                    TEXT,
    sort_order               INTEGER NOT NULL DEFAULT 0
);
INSERT INTO budget_template_line (award_type_code, category_code, label, sort_order) VALUES
    ('CPFF',     'personnel', 'Personnel', 10),
    ('CPFF',     'travel',    'Travel',    20),
    ('CPFF',     'odc',       'ODCs',      30),
    ('CPFF',     'equipment', 'Equipment', 40),
    ('CPFF',     'sub',       'Subs',      50),
    ('CPFF',     'fee',       'Fee',       60),
    ('grant',    'personnel', 'Personnel', 10),
    ('grant',    'travel',    'Travel',    20),
    ('grant',    'odc',       'ODCs',      30),
    ('grant',    'equipment', 'Equipment', 40),
    ('grant',    'sub',       'Subs',      50),
    ('FFP',      'personnel', 'Personnel', 10),
    ('FFP',      'travel',    'Travel',    20),
    ('FFP',      'odc',       'ODCs',      30),
    ('FFP',      'equipment', 'Equipment', 40),
    ('FFP',      'sub',       'Subs',      50),
    ('TM',       'personnel', 'Labor',     10),
    ('TM',       'travel',    'Travel',    20),
    ('TM',       'odc',       'ODCs',      30),
    ('internal', 'personnel', 'Personnel', 10),
    ('internal', 'travel',    'Travel',    20),
    ('internal', 'odc',       'ODCs',      30);

-- =====================================================================
-- Identity
-- =====================================================================

CREATE TABLE IF NOT EXISTS person (
    person_id         INTEGER PRIMARY KEY,
    organization_id   INTEGER NOT NULL REFERENCES organization (organization_id),
    display_name      TEXT NOT NULL,
    email             TEXT,
    hire_date         TEXT,
    term_date         TEXT,
    labor_category    TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS person_rate (
    person_rate_id    INTEGER PRIMARY KEY,
    person_id         INTEGER NOT NULL REFERENCES person (person_id),
    effective_from    TEXT NOT NULL,
    effective_to      TEXT,
    base_rate_cents   INTEGER NOT NULL CHECK (base_rate_cents >= 0),
    hours_per_year    INTEGER,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (effective_to IS NULL OR effective_to >= effective_from)
);

CREATE TABLE IF NOT EXISTS user_account (
    user_account_id       INTEGER PRIMARY KEY,
    person_id             INTEGER NOT NULL UNIQUE REFERENCES person (person_id),
    username              TEXT NOT NULL UNIQUE,
    password_hash         TEXT NOT NULL,
    role_code             TEXT NOT NULL REFERENCES role (role_code),
    is_active             INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at            TEXT NOT NULL DEFAULT (datetime('now')),
    password_changed_at   TEXT
);

-- =====================================================================
-- Awards
-- =====================================================================

CREATE TABLE IF NOT EXISTS award (
    award_id              INTEGER PRIMARY KEY,
    organization_id       INTEGER NOT NULL REFERENCES organization (organization_id),
    short_code            TEXT NOT NULL,
    title                 TEXT NOT NULL,
    agency                TEXT NOT NULL,
    instrument_code       TEXT NOT NULL REFERENCES award_instrument (instrument_code),
    mechanism_code        TEXT NOT NULL REFERENCES award_mechanism (mechanism_code),
    phase_code            TEXT NOT NULL REFERENCES award_phase (phase_code),
    type_code             TEXT NOT NULL REFERENCES award_type (type_code),
    status_code           TEXT NOT NULL REFERENCES award_status (status_code),
    pop_start             TEXT NOT NULL,
    pop_end               TEXT NOT NULL,
    funded_through        TEXT,
    awarded_cost_cents    INTEGER NOT NULL DEFAULT 0 CHECK (awarded_cost_cents >= 0),
    funded_amount_cents   INTEGER NOT NULL DEFAULT 0 CHECK (funded_amount_cents >= 0),
    fee_pot_cents         INTEGER NOT NULL DEFAULT 0 CHECK (fee_pot_cents >= 0),
    enforce_ceiling       INTEGER NOT NULL CHECK (enforce_ceiling IN (0, 1)),
    labor_incurred        INTEGER NOT NULL CHECK (labor_incurred IN (0, 1)),
    fee_engine            TEXT NOT NULL CHECK (fee_engine IN ('fixed_pot', 'none')),
    ceiling_warn_pct      INTEGER NOT NULL DEFAULT 75
        CHECK (ceiling_warn_pct BETWEEN 0 AND 100),
    created_at            TEXT NOT NULL DEFAULT (datetime('now')),
    created_by            INTEGER REFERENCES user_account (user_account_id),
    UNIQUE (organization_id, short_code),
    CHECK (pop_end >= pop_start)
);

CREATE TABLE IF NOT EXISTS award_mod (
    award_mod_id          INTEGER PRIMARY KEY,
    award_id              INTEGER NOT NULL REFERENCES award (award_id),
    mod_number            TEXT NOT NULL,
    effective_date        TEXT NOT NULL,
    description           TEXT,
    awarded_cost_cents    INTEGER,
    funded_amount_cents   INTEGER,
    fee_pot_cents         INTEGER,
    pop_start             TEXT,
    pop_end               TEXT,
    funded_through        TEXT,
    created_at            TEXT NOT NULL DEFAULT (datetime('now')),
    created_by            INTEGER REFERENCES user_account (user_account_id),
    UNIQUE (award_id, mod_number)
);

CREATE TABLE IF NOT EXISTS clin (
    clin_id                 INTEGER PRIMARY KEY,
    award_id                INTEGER NOT NULL REFERENCES award (award_id),
    clin_number             TEXT NOT NULL,
    description             TEXT,
    amount_cents            INTEGER NOT NULL DEFAULT 0 CHECK (amount_cents >= 0),
    is_option               INTEGER NOT NULL DEFAULT 0 CHECK (is_option IN (0, 1)),
    exercise_window_start   TEXT,
    exercise_window_end     TEXT,
    exercised_at            TEXT,
    created_at              TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (award_id, clin_number)
);

CREATE TABLE IF NOT EXISTS budget_version (
    budget_version_id   INTEGER PRIMARY KEY,
    award_id            INTEGER NOT NULL REFERENCES award (award_id),
    label               TEXT NOT NULL,
    is_active           INTEGER NOT NULL DEFAULT 0 CHECK (is_active IN (0, 1)),
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    created_by          INTEGER REFERENCES user_account (user_account_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_budget_version_active
    ON budget_version (award_id) WHERE is_active = 1;

CREATE TABLE IF NOT EXISTS budget_line (
    budget_line_id      INTEGER PRIMARY KEY,
    budget_version_id   INTEGER NOT NULL REFERENCES budget_version (budget_version_id),
    category_code       TEXT NOT NULL REFERENCES budget_category (category_code),
    label               TEXT,
    approved_cents      INTEGER NOT NULL DEFAULT 0 CHECK (approved_cents >= 0),
    sort_order          INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS award_rate_policy (
    policy_id              INTEGER PRIMARY KEY,
    award_id               INTEGER NOT NULL REFERENCES award (award_id),
    effective_from         TEXT NOT NULL,
    effective_to           TEXT,
    cost_basis_code        TEXT NOT NULL REFERENCES cost_basis (cost_basis_code),
    fringe_pct             INTEGER NOT NULL DEFAULT 0 CHECK (fringe_pct >= 0),
    oh_pct                 INTEGER NOT NULL DEFAULT 0 CHECK (oh_pct >= 0),
    ga_pct                 INTEGER NOT NULL DEFAULT 0 CHECK (ga_pct >= 0),
    fee_pct                INTEGER NOT NULL DEFAULT 0 CHECK (fee_pct >= 0),
    fee_in_burden          INTEGER NOT NULL DEFAULT 0 CHECK (fee_in_burden IN (0, 1)),
    labor_budget_line_id   INTEGER REFERENCES budget_line (budget_line_id),
    created_at             TEXT NOT NULL DEFAULT (datetime('now')),
    created_by             INTEGER REFERENCES user_account (user_account_id),
    CHECK (effective_to IS NULL OR effective_to >= effective_from)
);

CREATE TABLE IF NOT EXISTS award_rate_override (
    override_id         INTEGER PRIMARY KEY,
    policy_id           INTEGER NOT NULL REFERENCES award_rate_policy (policy_id),
    person_id           INTEGER REFERENCES person (person_id),
    labor_category      TEXT,
    loaded_rate_cents   INTEGER NOT NULL CHECK (loaded_rate_cents >= 0),
    CHECK (
        (person_id IS NOT NULL AND labor_category IS NULL)
        OR (person_id IS NULL AND labor_category IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS ix_award_org_code ON award (organization_id, short_code);
CREATE INDEX IF NOT EXISTS ix_policy_award_from ON award_rate_policy (award_id, effective_from);
CREATE INDEX IF NOT EXISTS ix_person_rate_from ON person_rate (person_id, effective_from);
CREATE INDEX IF NOT EXISTS ix_clin_award ON clin (award_id);
CREATE INDEX IF NOT EXISTS ix_budget_line_version ON budget_line (budget_version_id);

-- =====================================================================
-- Schedule (Phase 3). Tasks under awards; assignments and capacity are hours.
-- =====================================================================

CREATE TABLE IF NOT EXISTS task (
    task_id       INTEGER PRIMARY KEY,
    award_id      INTEGER NOT NULL REFERENCES award (award_id),
    short_code    TEXT NOT NULL,
    title         TEXT NOT NULL,
    status_code   TEXT NOT NULL DEFAULT 'open' CHECK (status_code IN ('open', 'closed')),
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    created_by    INTEGER REFERENCES user_account (user_account_id),
    UNIQUE (award_id, short_code)
);

CREATE TABLE IF NOT EXISTS assignment (
    assignment_id                 INTEGER PRIMARY KEY,
    person_id                     INTEGER NOT NULL REFERENCES person (person_id),
    award_id                      INTEGER NOT NULL REFERENCES award (award_id),
    task_id                       INTEGER REFERENCES task (task_id),
    hours_hundredths_per_week     INTEGER NOT NULL CHECK (hours_hundredths_per_week > 0),
    effective_from                TEXT NOT NULL,
    effective_to                  TEXT,
    created_at                    TEXT NOT NULL DEFAULT (datetime('now')),
    created_by                    INTEGER REFERENCES user_account (user_account_id),
    CHECK (effective_to IS NULL OR effective_to >= effective_from)
);

CREATE TABLE IF NOT EXISTS person_capacity (
    person_capacity_id            INTEGER PRIMARY KEY,
    person_id                     INTEGER NOT NULL REFERENCES person (person_id),
    hours_hundredths_per_week     INTEGER NOT NULL CHECK (hours_hundredths_per_week >= 0),
    effective_from                TEXT NOT NULL,
    effective_to                  TEXT,
    created_at                    TEXT NOT NULL DEFAULT (datetime('now')),
    created_by                    INTEGER REFERENCES user_account (user_account_id),
    CHECK (effective_to IS NULL OR effective_to >= effective_from)
);

CREATE INDEX IF NOT EXISTS ix_task_award ON task (award_id);
CREATE INDEX IF NOT EXISTS ix_assignment_person_from ON assignment (person_id, effective_from);
CREATE INDEX IF NOT EXISTS ix_assignment_award ON assignment (award_id);
CREATE INDEX IF NOT EXISTS ix_capacity_person_from ON person_capacity (person_id, effective_from);

-- =====================================================================
-- Time (Phase 2)
-- =====================================================================

CREATE TABLE IF NOT EXISTS time_code (
    time_code         TEXT PRIMARY KEY,
    description       TEXT NOT NULL,
    consumes_award    INTEGER NOT NULL CHECK (consumes_award IN (0, 1))
);
INSERT INTO time_code (time_code, description, consumes_award) VALUES
    ('award',   'Hours charged to an award', 1),
    ('pto',     'Paid time off (company, not an SBIR award)', 0),
    ('holiday', 'Holiday', 0),
    ('ird',     'Independent research and development', 0),
    ('bp',      'Bid and proposal', 0);

CREATE TABLE IF NOT EXISTS timesheet_period (
    timesheet_period_id  INTEGER PRIMARY KEY,
    person_id            INTEGER NOT NULL REFERENCES person (person_id),
    week_start           TEXT NOT NULL,
    status_code          TEXT NOT NULL CHECK (
        status_code IN ('draft', 'submitted', 'approved', 'returned')
    ),
    return_comment       TEXT,
    submitted_at         TEXT,
    approved_at          TEXT,
    approved_by          INTEGER REFERENCES user_account (user_account_id),
    created_at           TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (person_id, week_start)
);

CREATE TABLE IF NOT EXISTS timesheet_line (
    timesheet_line_id     INTEGER PRIMARY KEY,
    timesheet_period_id   INTEGER NOT NULL REFERENCES timesheet_period (timesheet_period_id),
    work_date             TEXT NOT NULL,
    hours_hundredths      INTEGER NOT NULL CHECK (hours_hundredths > 0),
    time_code             TEXT NOT NULL REFERENCES time_code (time_code),
    award_id              INTEGER REFERENCES award (award_id),
    task_id               INTEGER REFERENCES task (task_id)
);

CREATE TABLE IF NOT EXISTS charge (
    charge_id             INTEGER PRIMARY KEY,
    source                TEXT NOT NULL CHECK (
        source IN ('labor', 'purchase', 'travel', 'instrument', 'manual', 'reversal')
    ),
    timesheet_line_id     INTEGER REFERENCES timesheet_line (timesheet_line_id),
    award_id              INTEGER REFERENCES award (award_id),
    budget_line_id        INTEGER REFERENCES budget_line (budget_line_id),
    category_code         TEXT REFERENCES budget_category (category_code),
    person_id             INTEGER REFERENCES person (person_id),
    work_date             TEXT,
    hours_hundredths      INTEGER,
    amount_cents          INTEGER NOT NULL,
    base_rate_cents       INTEGER,
    fringe_pct            INTEGER,
    oh_pct                INTEGER,
    ga_pct                INTEGER,
    fee_pct               INTEGER,
    fee_in_burden         INTEGER,
    loaded_rate_cents     INTEGER,
    person_rate_id        INTEGER REFERENCES person_rate (person_rate_id),
    policy_id             INTEGER REFERENCES award_rate_policy (policy_id),
    override_id           INTEGER REFERENCES award_rate_override (override_id),
    reverses_charge_id    INTEGER REFERENCES charge (charge_id),
    created_at            TEXT NOT NULL DEFAULT (datetime('now')),
    created_by            INTEGER REFERENCES user_account (user_account_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_charge_labor_line
    ON charge (timesheet_line_id)
    WHERE source = 'labor' AND reverses_charge_id IS NULL;

CREATE INDEX IF NOT EXISTS ix_timesheet_person_week
    ON timesheet_period (person_id, week_start);
CREATE INDEX IF NOT EXISTS ix_timesheet_line_period
    ON timesheet_line (timesheet_period_id);
CREATE INDEX IF NOT EXISTS ix_timesheet_line_task
    ON timesheet_line (task_id);
CREATE INDEX IF NOT EXISTS ix_charge_award
    ON charge (award_id);

-- =====================================================================
-- Audit (Phase 2.5). Append-only; Phase 7 is the UI/CSV (D19).
-- =====================================================================

CREATE TABLE IF NOT EXISTS audit_event (
    audit_event_id   INTEGER PRIMARY KEY,
    occurred_at      TEXT NOT NULL DEFAULT (datetime('now')),
    actor_user_id    INTEGER REFERENCES user_account (user_account_id),
    action           TEXT NOT NULL,
    entity_type      TEXT NOT NULL,
    entity_id        TEXT,
    detail           TEXT
);

CREATE INDEX IF NOT EXISTS ix_audit_event_occurred
    ON audit_event (occurred_at);

-- =====================================================================
-- Commitments (Phase 4). Open cents are remaining, not actuals (D25).
-- =====================================================================

CREATE TABLE IF NOT EXISTS instrument (
    instrument_id     INTEGER PRIMARY KEY,
    organization_id   INTEGER NOT NULL REFERENCES organization (organization_id),
    short_code        TEXT NOT NULL,
    title             TEXT NOT NULL,
    amount_cents      INTEGER NOT NULL CHECK (amount_cents >= 0),
    category_code     TEXT NOT NULL REFERENCES budget_category (category_code),
    status_code       TEXT NOT NULL DEFAULT 'open' CHECK (
        status_code IN ('open', 'posted', 'cancelled')
    ),
    effective_from    TEXT NOT NULL,
    effective_to      TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    created_by        INTEGER REFERENCES user_account (user_account_id),
    UNIQUE (organization_id, short_code),
    CHECK (effective_to IS NULL OR effective_to >= effective_from)
);

CREATE TABLE IF NOT EXISTS instrument_share (
    instrument_share_id  INTEGER PRIMARY KEY,
    instrument_id        INTEGER NOT NULL REFERENCES instrument (instrument_id),
    award_id             INTEGER NOT NULL REFERENCES award (award_id),
    share_pct            INTEGER NOT NULL CHECK (share_pct > 0),
    UNIQUE (instrument_id, award_id)
);

CREATE TABLE IF NOT EXISTS commitment (
    commitment_id     INTEGER PRIMARY KEY,
    award_id          INTEGER NOT NULL REFERENCES award (award_id),
    kind              TEXT NOT NULL CHECK (kind IN ('purchase', 'travel', 'instrument')),
    status_code       TEXT NOT NULL DEFAULT 'open' CHECK (
        status_code IN ('open', 'posted', 'cancelled')
    ),
    category_code     TEXT NOT NULL REFERENCES budget_category (category_code),
    amount_cents      INTEGER NOT NULL CHECK (amount_cents >= 0),
    description       TEXT,
    vendor            TEXT,
    person_id         INTEGER REFERENCES person (person_id),
    effective_date    TEXT NOT NULL,
    trip_end          TEXT,
    instrument_id     INTEGER REFERENCES instrument (instrument_id),
    charge_id         INTEGER REFERENCES charge (charge_id),
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    created_by        INTEGER REFERENCES user_account (user_account_id)
);

CREATE INDEX IF NOT EXISTS ix_commitment_award_status
    ON commitment (award_id, status_code);
CREATE INDEX IF NOT EXISTS ix_instrument_share_instrument
    ON instrument_share (instrument_id);
CREATE INDEX IF NOT EXISTS ix_instrument_org_code
    ON instrument (organization_id, short_code);

-- =====================================================================
-- Views (actuals from charge; open commitments are remaining committed)
-- =====================================================================

DROP VIEW IF EXISTS v_budget_line_remaining;
CREATE VIEW v_budget_line_remaining AS
SELECT
    bl.budget_line_id,
    a.award_id,
    a.short_code,
    a.status_code,
    bl.category_code,
    bl.label,
    bl.approved_cents,
    COALESCE(cmt.committed_cents, 0) AS committed_cents,
    COALESCE(act.actual_cents, 0) AS actual_cents,
    CASE
        WHEN a.status_code = 'pipeline' THEN 0
        ELSE bl.approved_cents
            - COALESCE(cmt.committed_cents, 0)
            - COALESCE(act.actual_cents, 0)
    END AS remaining_cents
FROM budget_line bl
JOIN budget_version bv
    ON bv.budget_version_id = bl.budget_version_id
   AND bv.is_active = 1
JOIN award a ON a.award_id = bv.award_id
LEFT JOIN (
    SELECT
        ch.award_id AS award_id,
        ch.category_code AS category_code,
        SUM(ch.amount_cents) AS actual_cents
    FROM charge ch
    WHERE ch.category_code IS NOT NULL
    GROUP BY ch.award_id, ch.category_code
) AS act
    ON act.award_id = a.award_id
   AND act.category_code = bl.category_code
LEFT JOIN (
    SELECT
        cm.award_id AS award_id,
        cm.category_code AS category_code,
        SUM(cm.amount_cents) AS committed_cents
    FROM commitment cm
    WHERE cm.status_code = 'open'
    GROUP BY cm.award_id, cm.category_code
) AS cmt
    ON cmt.award_id = a.award_id
   AND cmt.category_code = bl.category_code;

DROP VIEW IF EXISTS v_budget_remaining;
CREATE VIEW v_budget_remaining AS
SELECT
    a.award_id,
    a.short_code,
    a.status_code,
    a.type_code,
    a.enforce_ceiling,
    a.labor_incurred,
    a.fee_engine,
    a.fee_pot_cents,
    a.awarded_cost_cents,
    a.funded_amount_cents,
    COALESCE(lines.approved_cents, 0) AS approved_cents,
    COALESCE(commits.committed_cents, 0) AS committed_cents,
    COALESCE(actuals.actual_cents, 0) AS actual_cents,
    CASE
        WHEN a.status_code = 'pipeline' THEN 0
        ELSE COALESCE(lines.approved_cents, 0)
            - COALESCE(commits.committed_cents, 0)
            - COALESCE(actuals.actual_cents, 0)
    END AS remaining_approved_cents,
    CASE
        WHEN a.status_code = 'pipeline' THEN 0
        ELSE a.funded_amount_cents - COALESCE(actuals.actual_cents, 0)
    END AS remaining_funded_cents,
    COALESCE(opts.unexercised_option_cents, 0) AS unexercised_option_cents
FROM award a
LEFT JOIN (
    SELECT
        bv.award_id AS award_id,
        SUM(bl.approved_cents) AS approved_cents
    FROM budget_version bv
    JOIN budget_line bl ON bl.budget_version_id = bv.budget_version_id
    WHERE bv.is_active = 1
    GROUP BY bv.award_id
) AS lines ON lines.award_id = a.award_id
LEFT JOIN (
    SELECT
        ch.award_id AS award_id,
        SUM(ch.amount_cents) AS actual_cents
    FROM charge ch
    WHERE ch.award_id IS NOT NULL
    GROUP BY ch.award_id
) AS actuals ON actuals.award_id = a.award_id
LEFT JOIN (
    SELECT
        cm.award_id AS award_id,
        SUM(cm.amount_cents) AS committed_cents
    FROM commitment cm
    WHERE cm.status_code = 'open'
    GROUP BY cm.award_id
) AS commits ON commits.award_id = a.award_id
LEFT JOIN (
    SELECT
        c.award_id AS award_id,
        SUM(c.amount_cents) AS unexercised_option_cents
    FROM clin c
    WHERE c.is_option = 1
      AND c.exercised_at IS NULL
    GROUP BY c.award_id
) AS opts ON opts.award_id = a.award_id;

DROP VIEW IF EXISTS v_award_burn_monthly;
CREATE VIEW v_award_burn_monthly AS
SELECT
    ch.award_id AS award_id,
    substr(ch.work_date, 1, 7) AS year_month,
    SUM(ch.amount_cents) AS actual_cents
FROM charge ch
WHERE ch.award_id IS NOT NULL
  AND ch.work_date IS NOT NULL
GROUP BY ch.award_id, substr(ch.work_date, 1, 7);

-- =====================================================================
-- Documents and compliance (Phase 5). Files are on local disk (D29).
-- =====================================================================

CREATE TABLE IF NOT EXISTS document (
    document_id         INTEGER PRIMARY KEY,
    award_id            INTEGER NOT NULL REFERENCES award (award_id),
    kind_code           TEXT NOT NULL REFERENCES document_kind (kind_code),
    title               TEXT NOT NULL,
    document_date       TEXT,
    notes               TEXT,
    original_filename   TEXT,
    stored_ext          TEXT,
    content_type        TEXT,
    size_bytes          INTEGER,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    created_by          INTEGER REFERENCES user_account (user_account_id)
);

CREATE TABLE IF NOT EXISTS compliance_item (
    compliance_item_id  INTEGER PRIMARY KEY,
    award_id            INTEGER NOT NULL REFERENCES award (award_id),
    kind_code           TEXT NOT NULL REFERENCES compliance_kind (kind_code),
    title               TEXT NOT NULL,
    due_date            TEXT NOT NULL,
    status_code         TEXT NOT NULL REFERENCES compliance_status (status_code),
    notes               TEXT,
    completed_at        TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    created_by          INTEGER REFERENCES user_account (user_account_id)
);

CREATE INDEX IF NOT EXISTS ix_document_award
    ON document (award_id);
CREATE INDEX IF NOT EXISTS ix_compliance_award_due
    ON compliance_item (award_id, due_date);
CREATE INDEX IF NOT EXISTS ix_compliance_due
    ON compliance_item (due_date);

-- =====================================================================
-- Pipeline forecast (Phase 6). Not remaining (D32).
-- =====================================================================

CREATE TABLE IF NOT EXISTS pipeline_node (
    pipeline_node_id    INTEGER PRIMARY KEY,
    award_id            INTEGER NOT NULL REFERENCES award (award_id),
    kind_code           TEXT NOT NULL REFERENCES pipeline_kind (kind_code),
    title               TEXT NOT NULL,
    amount_cents        INTEGER NOT NULL CHECK (amount_cents >= 0),
    expected_date       TEXT,
    notes               TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    created_by          INTEGER REFERENCES user_account (user_account_id)
);

CREATE INDEX IF NOT EXISTS ix_pipeline_node_award
    ON pipeline_node (award_id);
