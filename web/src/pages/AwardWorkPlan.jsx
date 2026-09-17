import { useState } from "react";
import { Link } from "react-router-dom";
import { api, todayIso } from "../api.js";
import { WorkGanttChart } from "./WorkGantt.jsx";

const emptyManual = {
  requirement_code: "",
  title: "",
  start_date: todayIso(),
  due_date: todayIso(),
  percent_complete: "0",
};

export default function AwardWorkPlan({
  awardId,
  documents,
  items,
  chart,
  onReload,
  onError,
  onNotice,
}) {
  const [documentId, setDocumentId] = useState("");
  const [paste, setPaste] = useState("");
  const [draft, setDraft] = useState(null);
  const [notes, setNotes] = useState([]);
  const [manual, setManual] = useState(emptyManual);
  const [editingId, setEditingId] = useState(null);
  const [edit, setEdit] = useState(null);

  async function propose(event) {
    event.preventDefault();
    onError("");
    onNotice("");
    try {
      const body = { text: paste || null };
      if (documentId) {
        body.document_id = Number(documentId);
      }
      const data = await api(`/awards/${awardId}/work-plan/propose`, {
        method: "POST",
        body,
      });
      setNotes(data.notes || []);
      setDraft((data.items || []).map((row) => ({ ...row, keep: true })));
    } catch (err) {
      onError(err.message);
    }
  }

  async function confirm(event) {
    event.preventDefault();
    onError("");
    onNotice("");
    try {
      await api(`/awards/${awardId}/work-plan/confirm`, {
        method: "POST",
        body: { items: draft },
      });
      setDraft(null);
      setNotes([]);
      onNotice("Work plan saved. Update percent complete as work progresses.");
      await onReload();
    } catch (err) {
      onError(err.message);
    }
  }

  async function addManual(event) {
    event.preventDefault();
    onError("");
    onNotice("");
    try {
      await api(`/awards/${awardId}/work-plan`, {
        method: "POST",
        body: {
          requirement_code: manual.requirement_code || null,
          title: manual.title,
          start_date: manual.start_date,
          due_date: manual.due_date,
          percent_complete_bp: Math.round(Number(manual.percent_complete) * 100),
          origin_code: "manual",
        },
      });
      setManual(emptyManual);
      onNotice("Work-plan row added.");
      await onReload();
    } catch (err) {
      onError(err.message);
    }
  }

  function beginEdit(row) {
    setEditingId(row.work_plan_item_id);
    setEdit({
      requirement_code: row.requirement_code || "",
      title: row.title,
      start_date: row.start_date,
      due_date: row.due_date,
      percent_complete: String(row.percent_complete_bp / 100),
      notes: row.notes || "",
      sort_order: row.sort_order,
    });
  }

  async function saveEdit() {
    onError("");
    onNotice("");
    try {
      await api(`/work-plan/${editingId}`, {
        method: "PATCH",
        body: {
          ...edit,
          percent_complete_bp: Math.round(Number(edit.percent_complete) * 100),
        },
      });
      setEditingId(null);
      setEdit(null);
      onNotice("Work-plan row updated.");
      await onReload();
    } catch (err) {
      onError(err.message);
    }
  }

  async function remove(itemId) {
    onError("");
    onNotice("");
    try {
      await api(`/work-plan/${itemId}`, { method: "DELETE" });
      onNotice("Work-plan row removed.");
      await onReload();
    } catch (err) {
      onError(err.message);
    }
  }

  return (
    <div className="card">
      <h2>SOW work plan</h2>
      <p className="muted">
        Track technical requirements separately from contract deliverables and
        timesheet tasks. Maintain percent complete for the presentation-ready{" "}
        <Link to="/work-gantt">work progress Gantt</Link>.
      </p>
      <form onSubmit={propose}>
        <div className="row">
          <div>
            <label>Contract / SOW document</label>
            <select value={documentId} onChange={(event) => setDocumentId(event.target.value)}>
              <option value="">Pasted text only</option>
              {documents.map((document) => (
                <option key={document.document_id} value={document.document_id}>
                  {document.title}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label>Paste numbered requirements (optional)</label>
            <textarea
              rows={3}
              value={paste}
              onChange={(event) => setPaste(event.target.value)}
              placeholder="4.1 Kickoff Meeting&#10;4.2 Procure Materials"
            />
          </div>
          <div>
            <button type="submit">Propose work plan</button>
          </div>
        </div>
      </form>
      {notes.map((note) => (
        <p className="muted" key={note}>{note}</p>
      ))}
      {draft ? (
        <form onSubmit={confirm}>
          <table>
            <thead>
              <tr>
                <th>Keep</th>
                <th>Req.</th>
                <th>Title</th>
                <th>Start</th>
                <th>Due</th>
              </tr>
            </thead>
            <tbody>
              {draft.map((row, index) => (
                <tr key={`${row.requirement_code}-${index}`}>
                  <td>
                    <input
                      type="checkbox"
                      checked={row.keep}
                      onChange={(event) =>
                        setDraft((current) =>
                          current.map((item, itemIndex) =>
                            itemIndex === index ? { ...item, keep: event.target.checked } : item,
                          ),
                        )
                      }
                    />
                  </td>
                  <td>{row.requirement_code}</td>
                  <td>
                    <input
                      value={row.title}
                      onChange={(event) =>
                        setDraft((current) =>
                          current.map((item, itemIndex) =>
                            itemIndex === index ? { ...item, title: event.target.value } : item,
                          ),
                        )
                      }
                    />
                  </td>
                  <td>
                    <input
                      type="date"
                      value={row.start_date}
                      onChange={(event) =>
                        setDraft((current) =>
                          current.map((item, itemIndex) =>
                            itemIndex === index
                              ? { ...item, start_date: event.target.value }
                              : item,
                          ),
                        )
                      }
                    />
                  </td>
                  <td>
                    <input
                      type="date"
                      value={row.due_date}
                      onChange={(event) =>
                        setDraft((current) =>
                          current.map((item, itemIndex) =>
                            itemIndex === index ? { ...item, due_date: event.target.value } : item,
                          ),
                        )
                      }
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p><button type="submit">Confirm kept requirements</button></p>
        </form>
      ) : null}

      <form onSubmit={addManual}>
        <h3>Add requirement</h3>
        <div className="row">
          <div>
            <label>Requirement</label>
            <input
              value={manual.requirement_code}
              onChange={(event) =>
                setManual((current) => ({ ...current, requirement_code: event.target.value }))
              }
              placeholder="4.11"
            />
          </div>
          <div>
            <label>Start</label>
            <input
              type="date"
              value={manual.start_date}
              onChange={(event) =>
                setManual((current) => ({ ...current, start_date: event.target.value }))
              }
              required
            />
          </div>
          <div>
            <label>Due</label>
            <input
              type="date"
              value={manual.due_date}
              onChange={(event) =>
                setManual((current) => ({ ...current, due_date: event.target.value }))
              }
              required
            />
          </div>
          <div>
            <label>% complete</label>
            <input
              type="number"
              min="0"
              max="100"
              step="1"
              value={manual.percent_complete}
              onChange={(event) =>
                setManual((current) => ({ ...current, percent_complete: event.target.value }))
              }
              required
            />
          </div>
        </div>
        <label>Title</label>
        <input
          value={manual.title}
          onChange={(event) =>
            setManual((current) => ({ ...current, title: event.target.value }))
          }
          required
        />
        <p><button type="submit">Add</button></p>
      </form>

      <table>
        <thead>
          <tr>
            <th>Req.</th>
            <th>Title</th>
            <th>Start</th>
            <th>Due</th>
            <th>%</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {items.map((row) =>
            editingId === row.work_plan_item_id ? (
              <tr key={row.work_plan_item_id}>
                <td>
                  <input
                    value={edit.requirement_code}
                    onChange={(event) =>
                      setEdit((current) => ({ ...current, requirement_code: event.target.value }))
                    }
                  />
                </td>
                <td>
                  <input
                    value={edit.title}
                    onChange={(event) =>
                      setEdit((current) => ({ ...current, title: event.target.value }))
                    }
                  />
                </td>
                <td>
                  <input
                    type="date"
                    value={edit.start_date}
                    onChange={(event) =>
                      setEdit((current) => ({ ...current, start_date: event.target.value }))
                    }
                  />
                </td>
                <td>
                  <input
                    type="date"
                    value={edit.due_date}
                    onChange={(event) =>
                      setEdit((current) => ({ ...current, due_date: event.target.value }))
                    }
                  />
                </td>
                <td>
                  <input
                    className="percent-input"
                    type="number"
                    min="0"
                    max="100"
                    step="1"
                    value={edit.percent_complete}
                    onChange={(event) =>
                      setEdit((current) => ({ ...current, percent_complete: event.target.value }))
                    }
                  />
                </td>
                <td className="actions">
                  <button type="button" onClick={saveEdit}>Save</button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => {
                      setEditingId(null);
                      setEdit(null);
                    }}
                  >
                    Cancel
                  </button>
                </td>
              </tr>
            ) : (
              <tr key={row.work_plan_item_id}>
                <td>{row.requirement_code || "—"}</td>
                <td>{row.title}</td>
                <td>{row.start_date}</td>
                <td>{row.due_date}</td>
                <td>{(row.percent_complete_bp / 100).toFixed(0)}%</td>
                <td className="actions">
                  <button type="button" className="secondary" onClick={() => beginEdit(row)}>
                    Edit
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => remove(row.work_plan_item_id)}
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ),
          )}
        </tbody>
      </table>
      <WorkGanttChart chart={chart} />
    </div>
  );
}
