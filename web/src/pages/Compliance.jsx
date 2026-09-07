import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";

export default function Compliance() {
  const [rows, setRows] = useState([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [filters, setFilters] = useState({
    due_from: "",
    due_to: "",
    status_code: "",
  });

  async function load(next = filters) {
    const query = {};
    if (next.due_from) {
      query.due_from = next.due_from;
    }
    if (next.due_to) {
      query.due_to = next.due_to;
    }
    if (next.status_code) {
      query.status_code = next.status_code;
    }
    const list = await api("/compliance", { query });
    setRows(list);
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function applyFilters(event) {
    event.preventDefault();
    setError("");
    try {
      await load(filters);
    } catch (err) {
      setError(err.message);
    }
  }

  async function setStatus(itemId, statusCode) {
    setError("");
    setNotice("");
    try {
      await api(`/compliance/${itemId}`, {
        method: "PATCH",
        body: { status_code: statusCode },
      });
      setNotice("Updated.");
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function removeItem(itemId) {
    setError("");
    setNotice("");
    try {
      await api(`/compliance/${itemId}`, { method: "DELETE" });
      setNotice("Due date removed.");
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <>
      <h1>Compliance</h1>
      <p className="muted">Due dates across awards. This is not remaining money and not an alert engine.</p>
      {error ? <p className="error">{error}</p> : null}
      {notice ? <p>{notice}</p> : null}
      <div className="card">
        <form onSubmit={applyFilters}>
          <div className="row">
            <div>
              <label>From</label>
              <input
                type="date"
                value={filters.due_from}
                onChange={(event) =>
                  setFilters((current) => ({ ...current, due_from: event.target.value }))
                }
              />
            </div>
            <div>
              <label>To</label>
              <input
                type="date"
                value={filters.due_to}
                onChange={(event) =>
                  setFilters((current) => ({ ...current, due_to: event.target.value }))
                }
              />
            </div>
            <div>
              <label>Status</label>
              <select
                value={filters.status_code}
                onChange={(event) =>
                  setFilters((current) => ({ ...current, status_code: event.target.value }))
                }
              >
                <option value="">Any</option>
                <option value="open">open</option>
                <option value="done">done</option>
                <option value="waived">waived</option>
              </select>
            </div>
          </div>
          <p>
            <button type="submit">Show</button>
          </p>
        </form>
        <table>
          <thead>
            <tr>
              <th>Due</th>
              <th>Award</th>
              <th>Kind</th>
              <th>Title</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.compliance_item_id}>
                <td>{row.due_date}</td>
                <td>
                  <Link to={`/awards/${row.award_id}`}>{row.award_short_code || row.award_id}</Link>
                </td>
                <td>{row.kind_code}</td>
                <td>{row.title}</td>
                <td>
                  <span className="status">{row.status_code}</span>
                </td>
                <td className="actions">
                  {row.status_code === "open" ? (
                    <>
                      <button type="button" onClick={() => setStatus(row.compliance_item_id, "done")}>
                        Done
                      </button>
                      <button
                        type="button"
                        className="secondary"
                        onClick={() => setStatus(row.compliance_item_id, "waived")}
                      >
                        Waive
                      </button>
                    </>
                  ) : null}
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => removeItem(row.compliance_item_id)}
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
