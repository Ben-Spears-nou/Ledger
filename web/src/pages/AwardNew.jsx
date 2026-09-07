import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  api,
  parseDollarsToCents,
  parsePctToHundredths,
  pctToInput,
  todayIso,
} from "../api.js";

const STEPS = ["Identity", "Classification", "Dates", "Money", "Rates", "Budget"];

function linesForType(lookups, typeCode) {
  return (lookups.budget_templates || [])
    .filter((row) => row.award_type_code === typeCode)
    .map((row) => ({
      category_code: row.category_code,
      label: row.label || row.category_code,
      dollars: "",
      sort_order: row.sort_order,
    }));
}

function templatesForType(lookups, typeCode) {
  const all = lookups.rate_policy_templates || [];
  const matched = all.filter((row) => row.award_type_code === typeCode);
  return matched.length ? matched : all;
}

function emptyForm(lookups) {
  const typeCode = lookups.award_types?.[0]?.type_code || "CPFF";
  const templates = templatesForType(lookups, typeCode);
  const template = templates[0];
  return {
    short_code: "",
    title: "",
    agency: lookups.agencies?.[0] || "",
    instrument_code: lookups.instruments?.[0] || "grant",
    mechanism_code: lookups.mechanisms?.[0] || "SBIR",
    phase_code: lookups.phases?.[0] || "I",
    type_code: typeCode,
    status_code: "active",
    pop_start: todayIso(),
    pop_end: todayIso(),
    funded_through: "",
    awarded_dollars: "",
    funded_dollars: "",
    fee_pot_dollars: "",
    template_code: template?.template_code || "",
    cost_basis_code: template?.cost_basis_code || "fully_burdened",
    fringe_pct: pctToInput(template?.fringe_pct ?? 0),
    oh_pct: pctToInput(template?.oh_pct ?? 0),
    ga_pct: pctToInput(template?.ga_pct ?? 0),
    fee_pct: pctToInput(template?.fee_pct ?? 0),
    fee_in_burden: Boolean(template?.fee_in_burden),
    budget_lines: linesForType(lookups, typeCode),
  };
}

function applyType(lookups, form, typeCode) {
  const templates = templatesForType(lookups, typeCode);
  const template = templates.find((row) => row.template_code === form.template_code) || templates[0];
  return {
    ...form,
    type_code: typeCode,
    template_code: template?.template_code || "",
    cost_basis_code: template?.cost_basis_code || form.cost_basis_code,
    fringe_pct: pctToInput(template?.fringe_pct ?? 0),
    oh_pct: pctToInput(template?.oh_pct ?? 0),
    ga_pct: pctToInput(template?.ga_pct ?? 0),
    fee_pct: pctToInput(template?.fee_pct ?? 0),
    fee_in_burden: Boolean(template?.fee_in_burden),
    budget_lines: linesForType(lookups, typeCode),
  };
}

function applyTemplate(lookups, form, templateCode) {
  const template = (lookups.rate_policy_templates || []).find(
    (row) => row.template_code === templateCode,
  );
  if (!template) {
    return { ...form, template_code: templateCode };
  }
  return {
    ...form,
    template_code: templateCode,
    cost_basis_code: template.cost_basis_code,
    fringe_pct: pctToInput(template.fringe_pct),
    oh_pct: pctToInput(template.oh_pct),
    ga_pct: pctToInput(template.ga_pct),
    fee_pct: pctToInput(template.fee_pct),
    fee_in_burden: Boolean(template.fee_in_burden),
  };
}

export default function AwardNew() {
  const navigate = useNavigate();
  const [lookups, setLookups] = useState(null);
  const [form, setForm] = useState(null);
  const [step, setStep] = useState(0);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api("/lookups")
      .then((data) => {
        setLookups(data);
        setForm(emptyForm(data));
      })
      .catch((err) => setError(err.message));
  }, []);

  const selectedType = useMemo(
    () => (lookups?.award_types || []).find((row) => row.type_code === form?.type_code),
    [lookups, form],
  );
  const templates = useMemo(
    () => (lookups && form ? templatesForType(lookups, form.type_code) : []),
    [lookups, form],
  );
  const showFeePot = selectedType?.fee_engine === "fixed_pot";

  function setField(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function validateStep() {
    if (!form) {
      return "Still loading.";
    }
    if (step === 0) {
      if (!form.short_code.trim() || !form.title.trim() || !form.agency.trim()) {
        return "Short code, title, and agency are required.";
      }
    }
    if (step === 2) {
      if (!form.pop_start || !form.pop_end) {
        return "PoP start and end are required.";
      }
    }
    if (step === 4) {
      if (!form.cost_basis_code) {
        return "Pick a rate template or cost basis.";
      }
    }
    return "";
  }

  function goNext(event) {
    event.preventDefault();
    const message = validateStep();
    if (message) {
      setError(message);
      return;
    }
    setError("");
    setStep((current) => Math.min(current + 1, STEPS.length - 1));
  }

  async function onSubmit(event) {
    event.preventDefault();
    const message = validateStep();
    if (message) {
      setError(message);
      return;
    }
    setError("");
    setSaving(true);
    try {
      const awarded = parseDollarsToCents(form.awarded_dollars) ?? 0;
      const funded = parseDollarsToCents(form.funded_dollars) ?? 0;
      const feePot = showFeePot ? (parseDollarsToCents(form.fee_pot_dollars) ?? 0) : 0;
      const budgetLines = form.budget_lines.map((line) => {
        let approved = parseDollarsToCents(line.dollars) ?? 0;
        if (line.category_code === "fee" && approved === 0 && feePot) {
          approved = feePot;
        }
        return {
          category_code: line.category_code,
          label: line.label,
          approved_cents: approved,
          sort_order: line.sort_order,
        };
      });
      const created = await api("/awards", {
        method: "POST",
        body: {
          short_code: form.short_code.trim(),
          title: form.title.trim(),
          agency: form.agency.trim(),
          instrument_code: form.instrument_code,
          mechanism_code: form.mechanism_code,
          phase_code: form.phase_code,
          type_code: form.type_code,
          status_code: form.status_code,
          pop_start: form.pop_start,
          pop_end: form.pop_end,
          funded_through: form.funded_through || null,
          awarded_cost_cents: awarded,
          funded_amount_cents: funded,
          fee_pot_cents: feePot,
          rate_policy: {
            template_code: form.template_code || null,
            cost_basis_code: form.cost_basis_code,
            fringe_pct: parsePctToHundredths(form.fringe_pct) ?? 0,
            oh_pct: parsePctToHundredths(form.oh_pct) ?? 0,
            ga_pct: parsePctToHundredths(form.ga_pct) ?? 0,
            fee_pct: parsePctToHundredths(form.fee_pct) ?? 0,
            fee_in_burden: form.fee_in_burden,
            effective_from: form.pop_start,
          },
          budget_lines: budgetLines,
        },
      });
      navigate(`/awards/${created.award_id}`);
    } catch (err) {
      setError(err.message);
      setSaving(false);
    }
  }

  if (!form || !lookups) {
    if (error) {
      return <p className="error">{error}</p>;
    }
    return <p className="muted">Loading…</p>;
  }

  return (
    <>
      <p>
        <Link to="/portfolio">All awards</Link>
      </p>
      <h1>New award</h1>
      <p className="muted">Money is dollars here. Ledger stores integer cents. This is not QuickBooks.</p>
      {error ? <p className="error">{error}</p> : null}
      <ol className="steps">
        {STEPS.map((label, index) => (
          <li key={label} className={index === step ? "current" : ""}>
            {index + 1}. {label}
          </li>
        ))}
      </ol>
      <form onSubmit={step === STEPS.length - 1 ? onSubmit : goNext} className="card">
        {step === 0 ? (
          <div className="row">
            <div>
              <label>Short code</label>
              <input
                required
                value={form.short_code}
                onChange={(event) => setField("short_code", event.target.value)}
              />
            </div>
            <div>
              <label>Title</label>
              <input
                required
                value={form.title}
                onChange={(event) => setField("title", event.target.value)}
              />
            </div>
            <div>
              <label>Agency</label>
              <input
                required
                list="agency-list"
                value={form.agency}
                onChange={(event) => setField("agency", event.target.value)}
              />
              <datalist id="agency-list">
                {(lookups.agencies || []).map((name) => (
                  <option key={name} value={name} />
                ))}
              </datalist>
            </div>
          </div>
        ) : null}
        {step === 1 ? (
          <div className="row">
            <div>
              <label>Instrument</label>
              <select
                value={form.instrument_code}
                onChange={(event) => setField("instrument_code", event.target.value)}
              >
                {(lookups.instruments || []).map((code) => (
                  <option key={code} value={code}>
                    {code}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label>Mechanism</label>
              <select
                value={form.mechanism_code}
                onChange={(event) => setField("mechanism_code", event.target.value)}
              >
                {(lookups.mechanisms || []).map((code) => (
                  <option key={code} value={code}>
                    {code}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label>Phase</label>
              <select
                value={form.phase_code}
                onChange={(event) => setField("phase_code", event.target.value)}
              >
                {(lookups.phases || []).map((code) => (
                  <option key={code} value={code}>
                    {code}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label>Type</label>
              <select
                value={form.type_code}
                onChange={(event) =>
                  setForm((current) => applyType(lookups, current, event.target.value))
                }
              >
                {(lookups.award_types || []).map((row) => (
                  <option key={row.type_code} value={row.type_code}>
                    {row.type_code}
                    {row.enforce_ceiling ? " (ceiling)" : ""}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label>Status</label>
              <select
                value={form.status_code}
                onChange={(event) => setField("status_code", event.target.value)}
              >
                {(lookups.statuses || []).map((code) => (
                  <option key={code} value={code}>
                    {code}
                  </option>
                ))}
              </select>
            </div>
          </div>
        ) : null}
        {step === 2 ? (
          <div className="row">
            <div>
              <label>PoP start</label>
              <input
                type="date"
                required
                value={form.pop_start}
                onChange={(event) => setField("pop_start", event.target.value)}
              />
            </div>
            <div>
              <label>PoP end</label>
              <input
                type="date"
                required
                value={form.pop_end}
                onChange={(event) => setField("pop_end", event.target.value)}
              />
            </div>
            <div>
              <label>Funded through (optional)</label>
              <input
                type="date"
                value={form.funded_through}
                onChange={(event) => setField("funded_through", event.target.value)}
              />
            </div>
          </div>
        ) : null}
        {step === 3 ? (
          <>
            <p className="muted">
              {selectedType?.enforce_ceiling
                ? "This type treats remaining as a ceiling."
                : "This type does not treat remaining as a contractual ceiling."}
            </p>
            <div className="row">
              <div>
                <label>Awarded ($)</label>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={form.awarded_dollars}
                  onChange={(event) => setField("awarded_dollars", event.target.value)}
                />
              </div>
              <div>
                <label>Funded ($)</label>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={form.funded_dollars}
                  onChange={(event) => setField("funded_dollars", event.target.value)}
                />
              </div>
              {showFeePot ? (
                <div>
                  <label>Fee pot ($)</label>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={form.fee_pot_dollars}
                    onChange={(event) => setField("fee_pot_dollars", event.target.value)}
                  />
                </div>
              ) : null}
            </div>
          </>
        ) : null}
        {step === 4 ? (
          <>
            <p className="muted">
              Templates seed the form only. Percents are percent points (32.15 means 32.15%).
            </p>
            <div className="row">
              <div>
                <label>Template</label>
                <select
                  value={form.template_code}
                  onChange={(event) =>
                    setForm((current) => applyTemplate(lookups, current, event.target.value))
                  }
                >
                  {templates.map((row) => (
                    <option key={row.template_code} value={row.template_code}>
                      {row.template_code}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label>Cost basis</label>
                <select
                  value={form.cost_basis_code}
                  onChange={(event) => setField("cost_basis_code", event.target.value)}
                >
                  {(lookups.cost_bases || []).map((code) => (
                    <option key={code} value={code}>
                      {code}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label>Fringe %</label>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={form.fringe_pct}
                  onChange={(event) => setField("fringe_pct", event.target.value)}
                />
              </div>
              <div>
                <label>OH %</label>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={form.oh_pct}
                  onChange={(event) => setField("oh_pct", event.target.value)}
                />
              </div>
              <div>
                <label>G&A %</label>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={form.ga_pct}
                  onChange={(event) => setField("ga_pct", event.target.value)}
                />
              </div>
              <div>
                <label>Fee % (in burden only if checked)</label>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={form.fee_pct}
                  onChange={(event) => setField("fee_pct", event.target.value)}
                />
              </div>
            </div>
            <p>
              <label>
                <input
                  type="checkbox"
                  checked={form.fee_in_burden}
                  onChange={(event) => setField("fee_in_burden", event.target.checked)}
                />{" "}
                Include fee in the hourly burden
              </label>
            </p>
          </>
        ) : null}
        {step === 5 ? (
          <>
            <p className="muted">Leave a line blank for $0. Fee can inherit the fee pot.</p>
            <table>
              <thead>
                <tr>
                  <th>Category</th>
                  <th>Approved ($)</th>
                </tr>
              </thead>
              <tbody>
                {form.budget_lines.map((line, index) => (
                  <tr key={line.category_code}>
                    <td>{line.label}</td>
                    <td>
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={line.dollars}
                        onChange={(event) => {
                          const dollars = event.target.value;
                          setForm((current) => ({
                            ...current,
                            budget_lines: current.budget_lines.map((item, i) =>
                              i === index ? { ...item, dollars } : item,
                            ),
                          }));
                        }}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        ) : null}
        <p>
          {step > 0 ? (
            <button
              type="button"
              className="secondary"
              onClick={() => {
                setError("");
                setStep((current) => Math.max(0, current - 1));
              }}
            >
              Back
            </button>
          ) : null}{" "}
          <button type="submit" disabled={saving}>
            {step === STEPS.length - 1 ? "Create award" : "Next"}
          </button>
        </p>
      </form>
    </>
  );
}
