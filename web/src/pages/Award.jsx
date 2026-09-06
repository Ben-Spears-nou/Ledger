import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, downloadDocumentFile, formatCents, todayIso, uploadDocumentFile } from "../api.js";

function dollarsToCents(value) {
  return Math.round(Number(value) * 100);
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
    setTasks(taskList);
    setAssignments(assignList);
    setPeople(personList);
    setCommitments(commitmentList);
    setCategories(lookups.budget_categories || []);
    setDocumentKinds(lookups.document_kinds || []);
    setComplianceKinds(lookups.compliance_kinds || []);
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
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

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
              <th>Fee pot</th>
              <td>{formatCents(award.fee_pot_cents)}</td>
            </tr>
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
      {notice ? <p>{notice}</p> : null}
      {error ? <p className="error">{error}</p> : null}
    </>
  );
}
