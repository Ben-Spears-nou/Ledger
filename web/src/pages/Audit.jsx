import { useEffect, useState } from "react";
import { api, downloadChargesCsv } from "../api.js";

function detailText(detail) {
  if (detail === null || detail === undefined || detail === "") {
    return "—";
  }
  if (typeof detail === "string") {
    return detail;
  }
  try {
    return JSON.stringify(detail);
  } catch {
    return String(detail);
  }
}

export default function Audit() {
  const [rows, setRows] = useState([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [filters, setFilters] = useState({
    action: "",
    entity_type: "",
    occurred_from: "",
    occurred_to: "",
  });

  async function load(next = filters) {
    const query = {};
    if (next.action) {
      query.action = next.action;
    }
    if (next.entity_type) {
      query.entity_type = next.entity_type;
    }
    if (next.occurred_from) {
      query.occurred_from = next.occurred_from;
    }
    if (next.occurred_to) {
      query.occurred_to = next.occurred_to;
    }
    const list = await api("/admin/audit", { query });
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

  async function downloadCsv() {
    setError("");
    setNotice("");
    try {
      await downloadChargesCsv();
      setNotice("Download started.");
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <>
      <h1>Audit</h1>
      <p className="muted">
        Append-only events. This is not QuickBooks. The CSV is posted charges in integer cents.
      </p>
      {error ? <p className="error">{error}</p> : null}
      {notice ? <p>{notice}</p> : null}
      <div className="card">
        <p>
          <button type="button" onClick={downloadCsv}>
            Download charges CSV
          </button>
        </p>
        <form onSubmit={applyFilters}>
          <div className="row">
            <div>
              <label>Action</label>
              <input
                value={filters.action}
                onChange={(event) =>
                  setFilters((current) => ({ ...current, action: event.target.value }))
                }
                placeholder="week_approve"
              />
            </div>
            <div>
              <label>Entity</label>
              <input
                value={filters.entity_type}
                onChange={(event) =>
                  setFilters((current) => ({ ...current, entity_type: event.target.value }))
                }
                placeholder="award"
              />
            </div>
            <div>
              <label>From</label>
              <input
                type="date"
                value={filters.occurred_from}
                onChange={(event) =>
                  setFilters((current) => ({ ...current, occurred_from: event.target.value }))
                }
              />
            </div>
            <div>
              <label>To</label>
              <input
                type="date"
                value={filters.occurred_to}
                onChange={(event) =>
                  setFilters((current) => ({ ...current, occurred_to: event.target.value }))
                }
              />
            </div>
          </div>
          <p>
            <button type="submit">Show</button>
          </p>
        </form>
        <table>
          <thead>
            <tr>
              <th>When</th>
              <th>Who</th>
              <th>Action</th>
              <th>Entity</th>
              <th>Id</th>
              <th>Detail</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.audit_event_id}>
                <td>{row.occurred_at}</td>
                <td>{row.actor_display_name || row.actor_user_id || "—"}</td>
                <td>
                  <span className="status">{row.action}</span>
                </td>
                <td>{row.entity_type}</td>
                <td>{row.entity_id || "—"}</td>
                <td>{detailText(row.detail)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
