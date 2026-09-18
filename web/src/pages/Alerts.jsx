import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, formatCents, todayIso } from "../api.js";

export default function Alerts() {
  const [rows, setRows] = useState([]);
  const [error, setError] = useState("");
  const [asOf, setAsOf] = useState(todayIso());

  async function load(nextAsOf = asOf) {
    const list = await api("/alerts", { query: { as_of: nextAsOf } });
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
      await load(asOf);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <>
      <h1>Alerts</h1>
      <p className="muted">
        75% of funded (or approved, if not a ceiling) and PoP within 30 days. Not email. Not the
        compliance calendar.
      </p>
      {error ? <p className="error">{error}</p> : null}
      <div className="card">
        <form onSubmit={applyFilters}>
          <label>As of</label>
          <input type="date" value={asOf} onChange={(event) => setAsOf(event.target.value)} />
          <p>
            <button type="submit">Show</button>
          </p>
        </form>
        <table>
          <thead>
            <tr>
              <th>Kind</th>
              <th>Award</th>
              <th>Detail</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={`${row.alert_code}-${row.award_id}`}>
                <td>
                  <span className="status">{row.alert_code}</span>
                </td>
                <td>
                  <Link to={`/awards/${row.award_id}`}>{row.award_short_code}</Link>
                </td>
                <td>
                  {row.alert_code === "burn_ceiling"
                    ? `${formatCents(row.actual_cents)} of ${formatCents(row.basis_cents)} at ${row.ceiling_warn_pct}%`
                    : `PoP ${row.pop_end} (${row.days_to_pop_end} days)`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
