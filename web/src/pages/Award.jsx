import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  api,
  centsToDollarInput,
  downloadDocumentFile,
  formatCents,
  parseDollarsToCents,
  parsePctToHundredths,
  pctToInput,
  todayIso,
  uploadDocumentFile,
} from "../api.js";

function dollarsToCents(value) {
  return Math.round(Number(value) * 100);
}

function headerFromAward(detail) {
  return {
    title: detail.title || "",
    agency: detail.agency || "",
    status_code: detail.status_code || "active",
    funded_through: detail.funded_through || "",
  };
}

function policyFromAward(detail) {
  const policy = detail.current_policy;
  return {
    template_code: "",
    cost_basis_code: policy?.cost_basis_code || "fully_burdened",
    fringe_pct: pctToInput(policy?.fringe_pct ?? 0),
    oh_pct: pctToInput(policy?.oh_pct ?? 0),
    ga_pct: pctToInput(policy?.ga_pct ?? 0),
    fee_pct: pctToInput(policy?.fee_pct ?? 0),
    fee_in_burden: Boolean(policy?.fee_in_burden),
    effective_from: todayIso(),
  };
}

function modFromAward(detail) {
  return {
    mod_number: "",
    effective_date: todayIso(),
    description: "",
    awarded_dollars: centsToDollarInput(detail.awarded_cost_cents),
    funded_dollars: centsToDollarInput(detail.funded_amount_cents),
    fee_pot_dollars: centsToDollarInput(detail.fee_pot_cents),
    pop_start: detail.pop_start || "",
    pop_end: detail.pop_end || "",
    funded_through: detail.funded_through || "",
    budget_lines: (detail.budget_lines || []).map((line) => ({
      category_code: line.category_code,
      label: line.label,
      dollars: centsToDollarInput(line.approved_cents),
    })),
  };
}

export default function Award() {
  const { id } = useParams();
  const [award, setAward] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [assignments, setAssignments] = useState([]);
  const [people, setPeople] = useState([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [taskForm, setTaskForm] = useState({ short_code: "", title: "" });
  const [commitments, setCommitments] = useState([]);
  const [categories, setCategories] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [compliance, setCompliance] = useState([]);
  const [documentKinds, setDocumentKinds] = useState([]);
  const [complianceKinds, setComplianceKinds] = useState([]);
  const [pipelineKinds, setPipelineKinds] = useState([]);
  const [pipeline, setPipeline] = useState([]);
  const [burn, setBurn] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [pipeForm, setPipeForm] = useState({
    kind_code: "next_phase",
    title: "",
    dollars: "",
    expected_date: "",
    notes: "",
  });
  const [docFileKey, setDocFileKey] = useState(0);
  const [docForm, setDocForm] = useState({
    kind_code: "report",
    title: "",
    document_date: todayIso(),
    notes: "",
    file: null,
  });
  const [compForm, setCompForm] = useState({
    kind_code: "technical_report",
    title: "",
    due_date: todayIso(),
    notes: "",
  });
  const [assignForm, setAssignForm] = useState({
    person_id: "",
    task_id: "",
    hours_per_week: "",
    effective_from: todayIso(),
  });
  const [purchaseForm, setPurchaseForm] = useState({
    category_code: "equipment",
    dollars: "",
    description: "",
    vendor: "",
    effective_date: todayIso(),
  });
  const [travelForm, setTravelForm] = useState({
    dollars: "",
    description: "",
    person_id: "",
    effective_date: todayIso(),
    trip_end: "",
  });
  const [statuses, setStatuses] = useState([]);
  const [agencies, setAgencies] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [costBases, setCostBases] = useState([]);
  const [headerForm, setHeaderForm] = useState({
    title: "",
    agency: "",
    status_code: "active",
    funded_through: "",
  });
  const [policyForm, setPolicyForm] = useState({
    template_code: "",
    cost_basis_code: "fully_burdened",
    fringe_pct: "",
    oh_pct: "",
    ga_pct: "",
    fee_pct: "",
    fee_in_burden: false,
    effective_from: todayIso(),
  });
  const [modForm, setModForm] = useState({
    mod_number: "",
    effective_date: todayIso(),
    description: "",
    awarded_dollars: "",
    funded_dollars: "",
    fee_pot_dollars: "",
    pop_start: "",
    pop_end: "",
    funded_through: "",
    budget_lines: [],
  });

  async function load() {
    const [detail, taskList, assignList, personList, commitmentList, lookups] = await Promise.all([
      api(`/awards/${id}`),
      api(`/awards/${id}/tasks`),
      api("/assignments", { query: { award_id: id } }),
      api("/people"),
      api(`/awards/${id}/commitments`),
      api("/lookups"),
    ]);
    setAward(detail);
    setHeaderForm(headerFromAward(detail));
    setPolicyForm(policyFromAward(detail));
    setModForm(modFromAward(detail));
    setTasks(taskList);
    setAssignments(assignList);
    setPeople(personList);
    setCommitments(commitmentList);
    setCategories(lookups.budget_categories || []);
    setDocumentKinds(lookups.document_kinds || []);
    setComplianceKinds(lookups.compliance_kinds || []);
    setPipelineKinds(lookups.pipeline_kinds || []);
    setStatuses(lookups.statuses || []);
    setAgencies(lookups.agencies || []);
    setTemplates(lookups.rate_policy_templates || []);
    setCostBases(lookups.cost_bases || []);
    if (!assignForm.person_id && personList.length) {
      setAssignForm((current) => ({ ...current, person_id: String(personList[0].person_id) }));
    }
    try {
      const [documentList, complianceList] = await Promise.all([
        api(`/awards/${id}/documents`),
        api(`/awards/${id}/compliance`),
      ]);
      setDocuments(documentList);
      setCompliance(complianceList);
    } catch (err) {
      setDocuments([]);
      setCompliance([]);
      throw err;
    }
    try {
      const [pipelineList, burnData, alertList] = await Promise.all([
        api(`/awards/${id}/pipeline`),
        api(`/awards/${id}/burn`, { query: { as_of: todayIso() } }),
        api("/alerts", { query: { award_id: id, as_of: todayIso() } }),
      ]);
      setPipeline(pipelineList);
      setBurn(burnData);
      setAlerts(alertList);
    } catch (err) {
      setPipeline([]);
      setBurn(null);
      setAlerts([]);
      throw err;
    }
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function saveHeader(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    try {
      await api(`/awards/${id}`, {
        method: "PATCH",
        body: {
          title: headerForm.title,
          agency: headerForm.agency,
          status_code: headerForm.status_code,
          funded_through: headerForm.funded_through || null,
        },
      });
      setNotice("Award header saved.");
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function savePolicy(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    try {
      await api(`/awards/${id}/rate-policies`, {
        method: "POST",
        body: {
          template_code: policyForm.template_code || null,
          cost_basis_code: policyForm.cost_basis_code,
          fringe_pct: parsePctToHundredths(policyForm.fringe_pct) ?? 0,
          oh_pct: parsePctToHundredths(policyForm.oh_pct) ?? 0,
          ga_pct: parsePctToHundredths(policyForm.ga_pct) ?? 0,
          fee_pct: parsePctToHundredths(policyForm.fee_pct) ?? 0,
          fee_in_burden: policyForm.fee_in_burden,
          effective_from: policyForm.effective_from,
        },
      });
      setNotice("Rate policy revised. Already-posted charges are unchanged.");
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  function applyPolicyTemplate(templateCode) {
    const template = templates.find((row) => row.template_code === templateCode);
    if (!template) {
      setPolicyForm((current) => ({ ...current, template_code: templateCode }));
      return;
    }
    setPolicyForm((current) => ({
      ...current,
      template_code: templateCode,
      cost_basis_code: template.cost_basis_code,
      fringe_pct: pctToInput(template.fringe_pct),
      oh_pct: pctToInput(template.oh_pct),
      ga_pct: pctToInput(template.ga_pct),
      fee_pct: pctToInput(template.fee_pct),
      fee_in_burden: Boolean(template.fee_in_burden),
    }));
  }

  async function saveMod(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    try {
      const body = {
        mod_number: modForm.mod_number,
        effective_date: modForm.effective_date,
        description: modForm.description || null,
        awarded_cost_cents: parseDollarsToCents(modForm.awarded_dollars),
        funded_amount_cents: parseDollarsToCents(modForm.funded_dollars),
        pop_start: modForm.pop_start || null,
        pop_end: modForm.pop_end || null,
        funded_through: modForm.funded_through || null,
        budget_line_changes: modForm.budget_lines.map((line) => ({
          category_code: line.category_code,
          label: line.label,
          approved_cents: parseDollarsToCents(line.dollars) ?? 0,
        })),
      };
      if (award?.fee_engine === "fixed_pot") {
        body.fee_pot_cents = parseDollarsToCents(modForm.fee_pot_dollars) ?? 0;
      }
      await api(`/awards/${id}/mods`, { method: "POST", body });
      setNotice("Modification saved.");
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function addTask(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    try {
      await api(`/awards/${id}/tasks`, {
        method: "POST",
        body: { short_code: taskForm.short_code, title: taskForm.title },
      });
      setTaskForm({ short_code: "", title: "" });
      setNotice("Task saved.");
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function closeTask(taskId) {
    setError("");
    try {
      await api(`/awards/${id}/tasks/${taskId}`, {
        method: "PATCH",
        body: { status_code: "closed" },
      });
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function addAssignment(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    try {
      const body = {
        person_id: Number(assignForm.person_id),
        award_id: Number(id),
        hours_per_week: Number(assignForm.hours_per_week),
        effective_from: assignForm.effective_from,
      };
      if (assignForm.task_id) {
        body.task_id = Number(assignForm.task_id);
      }
      await api("/assignments", { method: "POST", body });
      setNotice("Assignment saved.");
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function addPurchase(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    try {
      await api("/purchases", {
        method: "POST",
        body: {
          award_id: Number(id),
          category_code: purchaseForm.category_code,
          amount_cents: dollarsToCents(purchaseForm.dollars),
          description: purchaseForm.description || null,
          vendor: purchaseForm.vendor || null,
          effective_date: purchaseForm.effective_date,
        },
      });
      setPurchaseForm((current) => ({ ...current, dollars: "", description: "", vendor: "" }));
      setNotice("Purchase committed.");
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function addTravel(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    try {
      const body = {
        award_id: Number(id),
        amount_cents: dollarsToCents(travelForm.dollars),
        description: travelForm.description || null,
        effective_date: travelForm.effective_date,
      };
      if (travelForm.person_id) {
        body.person_id = Number(travelForm.person_id);
      }
      if (travelForm.trip_end) {
        body.trip_end = travelForm.trip_end;
      }
      await api("/travel", { method: "POST", body });
      setTravelForm((current) => ({ ...current, dollars: "", description: "", trip_end: "" }));
      setNotice("Travel committed.");
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function postCommitment(commitmentId) {
    setError("");
    setNotice("");
    try {
      await api(`/commitments/${commitmentId}/post`, { method: "POST" });
      setNotice("Commitment posted.");
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function cancelCommitment(commitmentId) {
    setError("");
    setNotice("");
    try {
      await api(`/commitments/${commitmentId}/cancel`, { method: "POST" });
      setNotice("Commitment cancelled.");
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function addDocument(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    try {
      const created = await api(`/awards/${id}/documents`, {
        method: "POST",
        body: {
          kind_code: docForm.kind_code,
          title: docForm.title,
          document_date: docForm.document_date || null,
          notes: docForm.notes || null,
        },
      });
      if (docForm.file) {
        await uploadDocumentFile(created.document_id, docForm.file);
      }
      setDocForm({
        kind_code: docForm.kind_code,
        title: "",
        document_date: todayIso(),
        notes: "",
        file: null,
      });
      setDocFileKey((current) => current + 1);
      setNotice("Document saved.");
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function addCompliance(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    try {
      await api(`/awards/${id}/compliance`, {
        method: "POST",
        body: {
          kind_code: compForm.kind_code,
          title: compForm.title,
          due_date: compForm.due_date,
          notes: compForm.notes || null,
        },
      });
      setCompForm({
        kind_code: compForm.kind_code,
        title: "",
        due_date: todayIso(),
        notes: "",
      });
      setNotice("Compliance item saved.");
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function setComplianceStatus(itemId, statusCode) {
    setError("");
    setNotice("");
    try {
      await api(`/compliance/${itemId}`, {
        method: "PATCH",
        body: { status_code: statusCode },
      });
      setNotice("Compliance updated.");
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function addPipeline(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    try {
      await api(`/awards/${id}/pipeline`, {
        method: "POST",
        body: {
          kind_code: pipeForm.kind_code,
          title: pipeForm.title,
          amount_cents: dollarsToCents(pipeForm.dollars),
          expected_date: pipeForm.expected_date || null,
          notes: pipeForm.notes || null,
        },
      });
      setPipeForm({
        kind_code: pipeForm.kind_code,
        title: "",
        dollars: "",
        expected_date: "",
        notes: "",
      });
      setNotice("Pipeline node saved.");
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function removePipeline(nodeId) {
    setError("");
    setNotice("");
    try {
      await api(`/pipeline/${nodeId}`, { method: "DELETE" });
      setNotice("Pipeline node removed.");
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  if (!award) {
    if (error) {
      return <p className="error">{error}</p>;
    }
    return <p className="muted">Loading…</p>;
  }

  const remaining = award.remaining || {};

  return (
    <>
      <p>
        <Link to="/portfolio">All awards</Link>
      </p>
      <h1>
        {award.short_code}{" "}
        <span className="status">{award.status_code}</span>
      </h1>
      <p>{award.title}</p>
      {error ? <p className="error">{error}</p> : null}
      {notice ? <p>{notice}</p> : null}
      <div className="card">
        <h2>Remaining</h2>
        <table>
          <tbody>
            <tr>
              <th>Approved remaining</th>
              <td>{formatCents(remaining.remaining_approved_cents)}</td>
            </tr>
            <tr>
              <th>Funded remaining</th>
              <td>{formatCents(remaining.remaining_funded_cents)}</td>
            </tr>
            <tr>
              <th>Committed (open)</th>
              <td>{formatCents(remaining.committed_cents)}</td>
            </tr>
            <tr>
              <th>Actuals</th>
              <td>{formatCents(remaining.actual_cents)}</td>
            </tr>
            <tr>
              <th>Unexercised options</th>
              <td>{formatCents(remaining.unexercised_option_cents)}</td>
            </tr>
            <tr>
              <th>Pipeline (forecast)</th>
              <td>{formatCents(remaining.pipeline_cents)}</td>
            </tr>
            <tr>
              <th>Fee pot</th>
              <td>{formatCents(award.fee_pot_cents)}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div className="card">
        <h2>Award header</h2>
        <p className="muted">
          Status and title. Money and PoP changes belong on a modification.
        </p>
        <form onSubmit={saveHeader}>
          <div className="row">
            <div>
              <label>Title</label>
              <input
                value={headerForm.title}
                onChange={(event) =>
                  setHeaderForm((current) => ({ ...current, title: event.target.value }))
                }
              />
            </div>
            <div>
              <label>Agency</label>
              <input
                list="award-agency-list"
                value={headerForm.agency}
                onChange={(event) =>
                  setHeaderForm((current) => ({ ...current, agency: event.target.value }))
                }
              />
              <datalist id="award-agency-list">
                {agencies.map((name) => (
                  <option key={name} value={name} />
                ))}
              </datalist>
            </div>
            <div>
              <label>Status</label>
              <select
                value={headerForm.status_code}
                onChange={(event) =>
                  setHeaderForm((current) => ({ ...current, status_code: event.target.value }))
                }
              >
                {statuses.map((code) => (
                  <option key={code} value={code}>
                    {code}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label>Funded through</label>
              <input
                type="date"
                value={headerForm.funded_through}
                onChange={(event) =>
                  setHeaderForm((current) => ({ ...current, funded_through: event.target.value }))
                }
              />
            </div>
          </div>
          <p>
            <button type="submit">Save header</button>
          </p>
        </form>
      </div>
      <div className="card">
        <h2>Rate policy</h2>
        <p className="muted">
          A revision is a new dated row. Already-posted charges keep the old stack.
        </p>
        {award.current_policy ? (
          <p>
            Current: {award.current_policy.cost_basis_code} · fringe{" "}
            {pctToInput(award.current_policy.fringe_pct)}% · OH{" "}
            {pctToInput(award.current_policy.oh_pct)}% · G&A{" "}
            {pctToInput(award.current_policy.ga_pct)}% · fee{" "}
            {pctToInput(award.current_policy.fee_pct)}%
            {award.current_policy.fee_in_burden ? " (fee in burden)" : ""} · from{" "}
            {award.current_policy.effective_from}
          </p>
        ) : (
          <p className="muted">No current policy.</p>
        )}
        <form onSubmit={savePolicy}>
          <div className="row">
            <div>
              <label>Template (optional)</label>
              <select
                value={policyForm.template_code}
                onChange={(event) => applyPolicyTemplate(event.target.value)}
              >
                <option value="">Keep numbers below</option>
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
                value={policyForm.cost_basis_code}
                onChange={(event) =>
                  setPolicyForm((current) => ({ ...current, cost_basis_code: event.target.value }))
                }
              >
                {costBases.map((code) => (
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
                value={policyForm.fringe_pct}
                onChange={(event) =>
                  setPolicyForm((current) => ({ ...current, fringe_pct: event.target.value }))
                }
              />
            </div>
            <div>
              <label>OH %</label>
              <input
                type="number"
                min="0"
                step="0.01"
                value={policyForm.oh_pct}
                onChange={(event) =>
                  setPolicyForm((current) => ({ ...current, oh_pct: event.target.value }))
                }
              />
            </div>
            <div>
              <label>G&A %</label>
              <input
                type="number"
                min="0"
                step="0.01"
                value={policyForm.ga_pct}
                onChange={(event) =>
                  setPolicyForm((current) => ({ ...current, ga_pct: event.target.value }))
                }
              />
            </div>
            <div>
              <label>Fee %</label>
              <input
                type="number"
                min="0"
                step="0.01"
                value={policyForm.fee_pct}
                onChange={(event) =>
                  setPolicyForm((current) => ({ ...current, fee_pct: event.target.value }))
                }
              />
            </div>
            <div>
              <label>Effective from</label>
              <input
                type="date"
                value={policyForm.effective_from}
                onChange={(event) =>
                  setPolicyForm((current) => ({ ...current, effective_from: event.target.value }))
                }
              />
            </div>
          </div>
          <p>
            <label>
              <input
                type="checkbox"
                checked={policyForm.fee_in_burden}
                onChange={(event) =>
                  setPolicyForm((current) => ({
                    ...current,
                    fee_in_burden: event.target.checked,
                  }))
                }
              />{" "}
              Include fee in the hourly burden
            </label>
          </p>
          <p>
            <button type="submit">Revise rate policy</button>
          </p>
        </form>
      </div>
      <div className="card">
        <h2>Record a modification</h2>
        <p className="muted">
          New funded amount, PoP, or budget line totals. Prefill is the current award.
        </p>
        <form onSubmit={saveMod}>
          <div className="row">
            <div>
              <label>Mod number</label>
              <input
                required
                value={modForm.mod_number}
                onChange={(event) =>
                  setModForm((current) => ({ ...current, mod_number: event.target.value }))
                }
              />
            </div>
            <div>
              <label>Effective date</label>
              <input
                type="date"
                required
                value={modForm.effective_date}
                onChange={(event) =>
                  setModForm((current) => ({ ...current, effective_date: event.target.value }))
                }
              />
            </div>
            <div>
              <label>Description</label>
              <input
                value={modForm.description}
                onChange={(event) =>
                  setModForm((current) => ({ ...current, description: event.target.value }))
                }
              />
            </div>
          </div>
          <div className="row">
            <div>
              <label>Awarded ($)</label>
              <input
                type="number"
                min="0"
                step="0.01"
                value={modForm.awarded_dollars}
                onChange={(event) =>
                  setModForm((current) => ({ ...current, awarded_dollars: event.target.value }))
                }
              />
            </div>
            <div>
              <label>Funded ($)</label>
              <input
                type="number"
                min="0"
                step="0.01"
                value={modForm.funded_dollars}
                onChange={(event) =>
                  setModForm((current) => ({ ...current, funded_dollars: event.target.value }))
                }
              />
            </div>
            {award.fee_engine === "fixed_pot" ? (
              <div>
                <label>Fee pot ($)</label>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={modForm.fee_pot_dollars}
                  onChange={(event) =>
                    setModForm((current) => ({ ...current, fee_pot_dollars: event.target.value }))
                  }
                />
              </div>
            ) : null}
            <div>
              <label>PoP start</label>
              <input
                type="date"
                value={modForm.pop_start}
                onChange={(event) =>
                  setModForm((current) => ({ ...current, pop_start: event.target.value }))
                }
              />
            </div>
            <div>
              <label>PoP end</label>
              <input
                type="date"
                value={modForm.pop_end}
                onChange={(event) =>
                  setModForm((current) => ({ ...current, pop_end: event.target.value }))
                }
              />
            </div>
            <div>
              <label>Funded through</label>
              <input
                type="date"
                value={modForm.funded_through}
                onChange={(event) =>
                  setModForm((current) => ({ ...current, funded_through: event.target.value }))
                }
              />
            </div>
          </div>
          <table>
            <thead>
              <tr>
                <th>Budget line</th>
                <th>Approved ($)</th>
              </tr>
            </thead>
            <tbody>
              {modForm.budget_lines.map((line, index) => (
                <tr key={line.category_code}>
                  <td>{line.label || line.category_code}</td>
                  <td>
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={line.dollars}
                      onChange={(event) => {
                        const dollars = event.target.value;
                        setModForm((current) => ({
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
          <p>
            <button type="submit">Save modification</button>
          </p>
        </form>
      </div>
      {alerts.length ? (
        <div className="card">
          <h2>Alerts</h2>
          <ul>
            {alerts.map((row) => (
              <li key={`${row.alert_code}-${row.award_id}`}>
                {row.alert_code === "burn_ceiling"
                  ? `Spent ${formatCents(row.actual_cents)} of ${formatCents(row.basis_cents)} (${row.ceiling_warn_pct}% warn).`
                  : `PoP ends ${row.pop_end} (${row.days_to_pop_end} days).`}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {burn ? (
        <div className="card">
          <h2>Burn</h2>
          <p className="muted">
            Daily {formatCents(burn.daily_burn_cents)} · EAC {formatCents(burn.eac_cents)} · runway{" "}
            {burn.runway_days === null || burn.runway_days === undefined
              ? "n/a"
              : `${burn.runway_days} days`}{" "}
            · as of {burn.as_of}
          </p>
          <table>
            <thead>
              <tr>
                <th>Month</th>
                <th>Actual</th>
              </tr>
            </thead>
            <tbody>
              {(burn.months || []).map((row) => (
                <tr key={row.year_month}>
                  <td>{row.year_month}</td>
                  <td>{formatCents(row.actual_cents)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      <div className="card">
        <h2>Pipeline</h2>
        <p className="muted">Forecast only. This is not remaining to spend.</p>
        <form onSubmit={addPipeline}>
          <div className="row">
            <div>
              <label>Kind</label>
              <select
                value={pipeForm.kind_code}
                onChange={(event) =>
                  setPipeForm((current) => ({ ...current, kind_code: event.target.value }))
                }
              >
                {pipelineKinds.map((row) => (
                  <option key={row.kind_code} value={row.kind_code}>
                    {row.kind_code}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label>Amount</label>
              <input
                type="number"
                step="0.01"
                min="0"
                value={pipeForm.dollars}
                onChange={(event) =>
                  setPipeForm((current) => ({ ...current, dollars: event.target.value }))
                }
                required
              />
            </div>
            <div>
              <label>Expected</label>
              <input
                type="date"
                value={pipeForm.expected_date}
                onChange={(event) =>
                  setPipeForm((current) => ({ ...current, expected_date: event.target.value }))
                }
              />
            </div>
          </div>
          <label>Title</label>
          <input
            value={pipeForm.title}
            onChange={(event) => setPipeForm((current) => ({ ...current, title: event.target.value }))}
            required
          />
          <label>Notes</label>
          <input
            value={pipeForm.notes}
            onChange={(event) => setPipeForm((current) => ({ ...current, notes: event.target.value }))}
          />
          <p>
            <button type="submit">Add forecast</button>
          </p>
        </form>
        <table>
          <thead>
            <tr>
              <th>Kind</th>
              <th>Title</th>
              <th>Amount</th>
              <th>Expected</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {pipeline.map((row) => (
              <tr key={row.pipeline_node_id}>
                <td>{row.kind_code}</td>
                <td>{row.title}</td>
                <td>{formatCents(row.amount_cents)}</td>
                <td>{row.expected_date || "—"}</td>
                <td>
                  <button type="button" className="secondary" onClick={() => removePipeline(row.pipeline_node_id)}>
                    Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="card">
        <h2>Budget lines</h2>
        <table>
          <thead>
            <tr>
              <th>Category</th>
              <th>Approved</th>
              <th>Committed</th>
              <th>Actual</th>
              <th>Remaining</th>
            </tr>
          </thead>
          <tbody>
            {(award.budget_lines || []).map((line) => (
              <tr key={line.budget_line_id}>
                <td>{line.label || line.category_code}</td>
                <td>{formatCents(line.approved_cents)}</td>
                <td>{formatCents(line.committed_cents)}</td>
                <td>{formatCents(line.actual_cents)}</td>
                <td>{formatCents(line.remaining_cents)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h2>Tasks</h2>
        <table>
          <thead>
            <tr>
              <th>Code</th>
              <th>Title</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {tasks.map((task) => (
              <tr key={task.task_id}>
                <td>{task.short_code}</td>
                <td>{task.title}</td>
                <td>
                  <span className="status">{task.status_code}</span>
                </td>
                <td>
                  {task.status_code === "open" ? (
                    <button type="button" className="secondary" onClick={() => closeTask(task.task_id)}>
                      Close
                    </button>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <form onSubmit={addTask}>
          <div className="row">
            <div>
              <label>Short code</label>
              <input
                value={taskForm.short_code}
                onChange={(event) =>
                  setTaskForm((current) => ({ ...current, short_code: event.target.value }))
                }
              />
            </div>
            <div>
              <label>Title</label>
              <input
                value={taskForm.title}
                onChange={(event) =>
                  setTaskForm((current) => ({ ...current, title: event.target.value }))
                }
              />
            </div>
          </div>
          <p>
            <button type="submit">Add task</button>
          </p>
        </form>
      </div>

      <div className="card">
        <h2>Assignments</h2>
        <table>
          <thead>
            <tr>
              <th>Person</th>
              <th>Task</th>
              <th>Hours/week</th>
              <th>From</th>
              <th>To</th>
            </tr>
          </thead>
          <tbody>
            {assignments.map((row) => {
              const person = people.find((item) => item.person_id === row.person_id);
              const task = tasks.find((item) => item.task_id === row.task_id);
              return (
                <tr key={row.assignment_id}>
                  <td>{person ? person.display_name : row.person_id}</td>
                  <td>{task ? task.short_code : "—"}</td>
                  <td>{row.hours_per_week}</td>
                  <td>{row.effective_from}</td>
                  <td>{row.effective_to || "open"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <form onSubmit={addAssignment}>
          <div className="row">
            <div>
              <label>Person</label>
              <select
                value={assignForm.person_id}
                onChange={(event) =>
                  setAssignForm((current) => ({ ...current, person_id: event.target.value }))
                }
              >
                {people.map((person) => (
                  <option key={person.person_id} value={person.person_id}>
                    {person.display_name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label>Task (optional)</label>
              <select
                value={assignForm.task_id}
                onChange={(event) =>
                  setAssignForm((current) => ({ ...current, task_id: event.target.value }))
                }
              >
                <option value="">No task</option>
                {tasks
                  .filter((task) => task.status_code === "open")
                  .map((task) => (
                    <option key={task.task_id} value={task.task_id}>
                      {task.short_code} — {task.title}
                    </option>
                  ))}
              </select>
            </div>
            <div>
              <label>Hours / week</label>
              <input
                type="number"
                min="0.01"
                step="0.25"
                value={assignForm.hours_per_week}
                onChange={(event) =>
                  setAssignForm((current) => ({ ...current, hours_per_week: event.target.value }))
                }
              />
            </div>
            <div>
              <label>Effective from</label>
              <input
                type="date"
                value={assignForm.effective_from}
                onChange={(event) =>
                  setAssignForm((current) => ({ ...current, effective_from: event.target.value }))
                }
              />
            </div>
          </div>
          <p>
            <button type="submit">Add assignment</button>
          </p>
        </form>
      </div>

      <div className="card">
        <h2>Purchases</h2>
        <form onSubmit={addPurchase}>
          <div className="row">
            <div>
              <label>Category</label>
              <select
                value={purchaseForm.category_code}
                onChange={(event) =>
                  setPurchaseForm((current) => ({ ...current, category_code: event.target.value }))
                }
              >
                {categories.map((row) => (
                  <option key={row.category_code} value={row.category_code}>
                    {row.category_code}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label>Amount (USD)</label>
              <input
                type="number"
                min="0"
                step="0.01"
                value={purchaseForm.dollars}
                onChange={(event) =>
                  setPurchaseForm((current) => ({ ...current, dollars: event.target.value }))
                }
              />
            </div>
            <div>
              <label>Vendor</label>
              <input
                value={purchaseForm.vendor}
                onChange={(event) =>
                  setPurchaseForm((current) => ({ ...current, vendor: event.target.value }))
                }
              />
            </div>
            <div>
              <label>Date</label>
              <input
                type="date"
                value={purchaseForm.effective_date}
                onChange={(event) =>
                  setPurchaseForm((current) => ({ ...current, effective_date: event.target.value }))
                }
              />
            </div>
          </div>
          <label>Description</label>
          <input
            value={purchaseForm.description}
            onChange={(event) =>
              setPurchaseForm((current) => ({ ...current, description: event.target.value }))
            }
          />
          <p>
            <button type="submit">Commit purchase</button>
          </p>
        </form>
      </div>

      <div className="card">
        <h2>Travel</h2>
        <form onSubmit={addTravel}>
          <div className="row">
            <div>
              <label>Amount (USD)</label>
              <input
                type="number"
                min="0"
                step="0.01"
                value={travelForm.dollars}
                onChange={(event) =>
                  setTravelForm((current) => ({ ...current, dollars: event.target.value }))
                }
              />
            </div>
            <div>
              <label>Person (optional)</label>
              <select
                value={travelForm.person_id}
                onChange={(event) =>
                  setTravelForm((current) => ({ ...current, person_id: event.target.value }))
                }
              >
                <option value="">None</option>
                {people.map((person) => (
                  <option key={person.person_id} value={person.person_id}>
                    {person.display_name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label>Start</label>
              <input
                type="date"
                value={travelForm.effective_date}
                onChange={(event) =>
                  setTravelForm((current) => ({ ...current, effective_date: event.target.value }))
                }
              />
            </div>
            <div>
              <label>End</label>
              <input
                type="date"
                value={travelForm.trip_end}
                onChange={(event) =>
                  setTravelForm((current) => ({ ...current, trip_end: event.target.value }))
                }
              />
            </div>
          </div>
          <label>Description</label>
          <input
            value={travelForm.description}
            onChange={(event) =>
              setTravelForm((current) => ({ ...current, description: event.target.value }))
            }
          />
          <p>
            <button type="submit">Commit travel</button>
          </p>
        </form>
      </div>

      <div className="card">
        <h2>Commitments</h2>
        <table>
          <thead>
            <tr>
              <th>Kind</th>
              <th>Status</th>
              <th>Category</th>
              <th>Amount</th>
              <th>Description</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {commitments.map((row) => (
              <tr key={row.commitment_id}>
                <td>{row.kind}</td>
                <td>
                  <span className="status">{row.status_code}</span>
                </td>
                <td>{row.category_code}</td>
                <td>{formatCents(row.amount_cents)}</td>
                <td>{row.description || row.vendor || "—"}</td>
                <td>
                  {row.status_code === "open" ? (
                    <>
                      <button type="button" onClick={() => postCommitment(row.commitment_id)}>
                        Post
                      </button>{" "}
                      <button
                        type="button"
                        className="secondary"
                        onClick={() => cancelCommitment(row.commitment_id)}
                      >
                        Cancel
                      </button>
                    </>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h2>Documents</h2>
        <form onSubmit={addDocument}>
          <div className="row">
            <div>
              <label>Kind</label>
              <select
                value={docForm.kind_code}
                onChange={(event) =>
                  setDocForm((current) => ({ ...current, kind_code: event.target.value }))
                }
              >
                {documentKinds.map((row) => (
                  <option key={row.kind_code} value={row.kind_code}>
                    {row.kind_code}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label>Date</label>
              <input
                type="date"
                value={docForm.document_date}
                onChange={(event) =>
                  setDocForm((current) => ({ ...current, document_date: event.target.value }))
                }
              />
            </div>
          </div>
          <label>Title</label>
          <input
            value={docForm.title}
            onChange={(event) => setDocForm((current) => ({ ...current, title: event.target.value }))}
            required
          />
          <label>Notes</label>
          <input
            value={docForm.notes}
            onChange={(event) => setDocForm((current) => ({ ...current, notes: event.target.value }))}
          />
          <label>File (optional)</label>
          <input
            key={docFileKey}
            type="file"
            onChange={(event) =>
              setDocForm((current) => ({
                ...current,
                file: event.target.files && event.target.files[0] ? event.target.files[0] : null,
              }))
            }
          />
          <p>
            <button type="submit">Save document</button>
          </p>
        </form>
        <table>
          <thead>
            <tr>
              <th>Kind</th>
              <th>Title</th>
              <th>Date</th>
              <th>File</th>
            </tr>
          </thead>
          <tbody>
            {documents.map((row) => (
              <tr key={row.document_id}>
                <td>{row.kind_code}</td>
                <td>{row.title}</td>
                <td>{row.document_date || "—"}</td>
                <td>
                  {row.has_file ? (
                    <button
                      type="button"
                      className="secondary"
                      onClick={() =>
                        downloadDocumentFile(row.document_id, row.original_filename).catch((err) =>
                          setError(err.message),
                        )
                      }
                    >
                      Download
                    </button>
                  ) : (
                    "—"
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h2>Compliance</h2>
        <form onSubmit={addCompliance}>
          <div className="row">
            <div>
              <label>Kind</label>
              <select
                value={compForm.kind_code}
                onChange={(event) =>
                  setCompForm((current) => ({ ...current, kind_code: event.target.value }))
                }
              >
                {complianceKinds.map((row) => (
                  <option key={row.kind_code} value={row.kind_code}>
                    {row.kind_code}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label>Due</label>
              <input
                type="date"
                value={compForm.due_date}
                onChange={(event) =>
                  setCompForm((current) => ({ ...current, due_date: event.target.value }))
                }
                required
              />
            </div>
          </div>
          <label>Title</label>
          <input
            value={compForm.title}
            onChange={(event) => setCompForm((current) => ({ ...current, title: event.target.value }))}
            required
          />
          <label>Notes</label>
          <input
            value={compForm.notes}
            onChange={(event) => setCompForm((current) => ({ ...current, notes: event.target.value }))}
          />
          <p>
            <button type="submit">Add due date</button>
          </p>
        </form>
        <table>
          <thead>
            <tr>
              <th>Due</th>
              <th>Kind</th>
              <th>Title</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {compliance.map((row) => (
              <tr key={row.compliance_item_id}>
                <td>{row.due_date}</td>
                <td>{row.kind_code}</td>
                <td>{row.title}</td>
                <td>
                  <span className="status">{row.status_code}</span>
                </td>
                <td>
                  {row.status_code === "open" ? (
                    <>
                      <button type="button" onClick={() => setComplianceStatus(row.compliance_item_id, "done")}>
                        Done
                      </button>{" "}
                      <button
                        type="button"
                        className="secondary"
                        onClick={() => setComplianceStatus(row.compliance_item_id, "waived")}
                      >
                        Waive
                      </button>
                    </>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
