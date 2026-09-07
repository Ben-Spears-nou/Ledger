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
  const [awards, setAwards] = useState([]);
  const [actions, setActions] = useState([]);
  const [entityTypes, setEntityTypes] = useState([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [filters, setFilters] = useState({
    action: "",
    entity_type: "",
    occurred_from: "",
    occurred_to: "",
  });
  const [csvFilters, setCsvFilters] = useState({
    award_id: "",
    work_from: "",
    work_to: "",
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
    Promise.all([
      load(),
      api("/lookups"),
      api("/awards", { query: { as: "picker" } }),
    ])
      .then(([, lookups, awardList]) => {
        setActions(lookups.audit_actions || []);
        setEntityTypes(lookups.audit_entity_types || []);
        setAwards(awardList);
      })
      .catch((err) => setError(err.message));
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
      await downloadChargesCsv({
        award_id: csvFilters.award_id || undefined,
        work_from: csvFilters.work_from || undefined,
        work_to: csvFilters.work_to || undefined,
      });
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
        <h2>Charges CSV</h2>
        <div className="row">
          <div>
            <label>Award</label>
            <select
              value={csvFilters.award_id}
              onChange={(event) =>
                setCsvFilters((current) => ({ ...current, award_id: event.target.value }))
              }
            >
              <option value="">All awards</option>
              {awards.map((award) => (
                <option key={award.award_id} value={award.award_id}>
                  {award.short_code}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label>Work from</label>
            <input
              type="date"
              value={csvFilters.work_from}
              onChange={(event) =>
                setCsvFilters((current) => ({ ...current, work_from: event.target.value }))
              }
            />
          </div>
          <div>
            <label>Work to</label>
            <input
              type="date"
              value={csvFilters.work_to}
              onChange={(event) =>
                setCsvFilters((current) => ({ ...current, work_to: event.target.value }))
              }
            />
          </div>
        </div>
        <p>
          <button type="button" onClick={downloadCsv}>
            Download charges CSV
          </button>
        </p>
        <h2>Event log</h2>
        <form onSubmit={applyFilters}>
          <div className="row">
            <div>
              <label>Action</label>
              <select
                value={filters.action}
                onChange={(event) =>
                  setFilters((current) => ({ ...current, action: event.target.value }))
                }
              >
                <option value="">All actions</option>
                {actions.map((code) => (
                  <option key={code} value={code}>
                    {code}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label>Entity</label>
              <select
                value={filters.entity_type}
                onChange={(event) =>
                  setFilters((current) => ({ ...current, entity_type: event.target.value }))
                }
              >
                <option value="">All entities</option>
                {entityTypes.map((code) => (
                  <option key={code} value={code}>
                    {code}
                  </option>
                ))}
              </select>
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
