import { useState } from "react";
import { Link } from "react-router-dom";
import { api, uploadDocumentFile } from "../api.js";
import { GanttChart } from "./Gantt.jsx";

export default function AwardSchedule({
  awardId,
  documents,
  scheduleKinds,
  items,
  chart,
  onReload,
  onError,
  onNotice,
}) {
  const [draft, setDraft] = useState(null);
  const [notes, setNotes] = useState([]);
  const [documentId, setDocumentId] = useState("");
  const [paste, setPaste] = useState("");
  const [contractFile, setContractFile] = useState(null);
  const [fileInputKey, setFileInputKey] = useState(0);
  const [manual, setManual] = useState({
    kind_code: scheduleKinds[0]?.kind_code || "deliverable",
    title: "",
    start_date: "",
    due_date: "",
  });

  async function propose(event) {
    event.preventDefault();
    onError("");
    onNotice("");
    try {
      const body = { text: paste || null };
      if (documentId) {
        body.document_id = Number(documentId);
      }
      const data = await api(`/awards/${awardId}/schedule/propose`, { method: "POST", body });
      setNotes(data.notes || []);
      setDraft((data.items || []).map((row) => ({ ...row, keep: true })));
    } catch (err) {
      onError(err.message);
    }
  }

  async function uploadContract() {
    if (!contractFile) {
      return;
    }
    onError("");
    onNotice("");
    try {
      const created = await api(`/awards/${awardId}/documents`, {
        method: "POST",
        body: {
          kind_code: "contract",
          title: contractFile.name,
          notes: "Uploaded for contract schedule review.",
        },
      });
      await uploadDocumentFile(created.document_id, contractFile);
      setDocumentId(String(created.document_id));
      setContractFile(null);
      setFileInputKey((current) => current + 1);
      onNotice("Contract uploaded. Select Propose draft when ready.");
      await onReload();
    } catch (err) {
      onError(err.message);
    }
  }

  async function confirm(event) {
    event.preventDefault();
    if (!draft) {
      return;
    }
    onError("");
    onNotice("");
    try {
      await api(`/awards/${awardId}/schedule/confirm`, {
        method: "POST",
        body: {
          items: draft.map((row) => ({
            kind_code: row.kind_code,
            title: row.title,
            start_date: row.start_date || null,
            due_date: row.due_date,
            notes: row.notes,
            origin_code: row.origin_code,
            source_document_id: row.source_document_id,
            keep: row.keep,
          })),
        },
      });
      setDraft(null);
      setNotes([]);
      onNotice("Schedule saved. Review the Gantt, then mark work done as it finishes.");
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
      await api(`/awards/${awardId}/schedule`, {
        method: "POST",
        body: {
          kind_code: manual.kind_code,
          title: manual.title,
          start_date: manual.start_date || null,
          due_date: manual.due_date,
          origin_code: "manual",
        },
      });
      setManual((current) => ({ ...current, title: "" }));
      onNotice("Schedule row added.");
      await onReload();
    } catch (err) {
      onError(err.message);
    }
  }

  async function setStatus(itemId, statusCode) {
    onError("");
    onNotice("");
    try {
      await api(`/schedule/${itemId}`, { method: "PATCH", body: { status_code: statusCode } });
      await onReload();
    } catch (err) {
      onError(err.message);
    }
  }

  async function removeItem(itemId) {
    onError("");
    onNotice("");
    try {
      await api(`/schedule/${itemId}`, { method: "DELETE" });
      onNotice("Schedule row removed.");
      await onReload();
    } catch (err) {
      onError(err.message);
    }
  }

  const kinds = scheduleKinds.length ? scheduleKinds : [{ kind_code: "deliverable" }];

  return (
    <div className="card">
      <h2>Contract schedule</h2>
      <p className="muted">
        Propose a starter plan from the award PoP and optional contract text. Confirm
        what is right. This is not remaining money and not a timesheet task.{" "}
        <Link to="/gantt">Open Gantt</Link>
      </p>
      <form onSubmit={propose}>
        <div className="row">
          <div>
            <label>Contract document (optional)</label>
            <select value={documentId} onChange={(event) => setDocumentId(event.target.value)}>
              <option value="">Phase template only</option>
              {documents.map((doc) => (
                <option key={doc.document_id} value={doc.document_id}>
                  {doc.title}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label>Upload a contract</label>
            <input
              key={fileInputKey}
              type="file"
              accept=".pdf,.doc,.docx,.txt,.csv"
              onChange={(event) =>
                setContractFile(
                  event.target.files && event.target.files[0] ? event.target.files[0] : null,
                )
              }
            />
          </div>
          <div>
            <button type="button" className="secondary" disabled={!contractFile} onClick={uploadContract}>
              Upload file
            </button>
          </div>
        </div>
        <p className="muted">
          PDF, Word (.doc/.docx), text, and CSV files can be stored. Automatic
          milestone extraction currently reads text and CSV; for PDF or Word,
          paste the relevant SOW text below before proposing.
        </p>
        <label>Paste SOW / milestone text (optional)</label>
        <textarea
          rows={4}
          value={paste}
          onChange={(event) => setPaste(event.target.value)}
          placeholder="Deliverable 1: Prototype due 2026-06-01"
        />
        <p>
          <button type="submit">Propose draft</button>
        </p>
      </form>
      {notes.map((line) => (
        <p className="muted" key={line}>
          {line}
        </p>
      ))}
      {draft ? (
        <form onSubmit={confirm}>
          <table>
            <thead>
              <tr>
                <th>Keep</th>
                <th>Kind</th>
                <th>Title</th>
                <th>Start</th>
                <th>Due</th>
              </tr>
            </thead>
            <tbody>
              {draft.map((row, index) => (
                <tr key={`${row.origin_code}-${index}`}>
                  <td>
                    <input
                      type="checkbox"
                      checked={row.keep}
                      onChange={(event) =>
                        setDraft((current) =>
                          current.map((item, i) =>
                            i === index ? { ...item, keep: event.target.checked } : item,
                          ),
                        )
                      }
                      aria-label={`Keep ${row.title}`}
                    />
                  </td>
                  <td>{row.kind_code}</td>
                  <td>
                    <input
                      value={row.title}
                      onChange={(event) =>
                        setDraft((current) =>
                          current.map((item, i) =>
                            i === index ? { ...item, title: event.target.value } : item,
                          ),
                        )
                      }
                    />
                  </td>
                  <td>
                    <input
                      type="date"
                      value={row.start_date || ""}
                      onChange={(event) =>
                        setDraft((current) =>
                          current.map((item, i) =>
                            i === index ? { ...item, start_date: event.target.value } : item,
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
                          current.map((item, i) =>
                            i === index ? { ...item, due_date: event.target.value } : item,
                          ),
                        )
                      }
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p>
            <button type="submit">Confirm kept rows</button>
          </p>
        </form>
      ) : null}

      <form onSubmit={addManual}>
        <h3>Add one row</h3>
        <div className="row">
          <div>
            <label>Kind</label>
            <select
              value={manual.kind_code}
              onChange={(event) =>
                setManual((current) => ({ ...current, kind_code: event.target.value }))
              }
            >
              {kinds.map((row) => (
                <option key={row.kind_code} value={row.kind_code}>
                  {row.kind_code}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label>Start</label>
            <input
              type="date"
              value={manual.start_date}
              onChange={(event) =>
                setManual((current) => ({ ...current, start_date: event.target.value }))
              }
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
        </div>
        <label>Title</label>
        <input
          value={manual.title}
          onChange={(event) => setManual((current) => ({ ...current, title: event.target.value }))}
          required
        />
        <p>
          <button type="submit">Add</button>
        </p>
      </form>

      <table>
        <thead>
          <tr>
            <th>Kind</th>
            <th>Title</th>
            <th>Due</th>
            <th>Status</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {items.map((row) => (
            <tr key={row.schedule_item_id}>
              <td>{row.kind_code}</td>
              <td>{row.title}</td>
              <td>{row.due_date}</td>
              <td>{row.status_code}</td>
              <td className="actions">
                {row.status_code === "open" ? (
                  <button type="button" onClick={() => setStatus(row.schedule_item_id, "done")}>
                    Done
                  </button>
                ) : (
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => setStatus(row.schedule_item_id, "open")}
                  >
                    Reopen
                  </button>
                )}
                <button
                  type="button"
                  className="secondary"
                  onClick={() => removeItem(row.schedule_item_id)}
                >
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <GanttChart chart={chart} />
    </div>
  );
}
