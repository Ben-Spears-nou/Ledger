import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, formatCents, todayIso } from "../api.js";

export default function Portfolio() {
  const [asOf, setAsOf] = useState(todayIso());
  const [rows, setRows] = useState([]);
  const [error, setError] = useState("");

  async function load(nextAsOf = asOf) {
    const home = await api("/home", { query: { as_of: nextAsOf } });
    setRows(home.portfolio || []);
    setAsOf(home.as_of);
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function apply(event) {
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
      <h1>Awards</h1>
      <p>
        <Link to="/awards/new">New award</Link>
      </p>
      {error ? <p className="error">{error}</p> : null}
      <div className="card">
        <form onSubmit={apply}>
          <label>As of</label>
          <input type="date" value={asOf} onChange={(event) => setAsOf(event.target.value)} />
          <p>
            <button type="submit">Show</button>
          </p>
        </form>
        <table>
          <thead>
            <tr>
              <th>Award</th>
              <th>Status</th>
              <th>Funded remaining</th>
              <th>Approved remaining</th>
              <th>Runway</th>
              <th>Next due</th>
              <th>Alerts</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((award) => (
              <tr key={award.award_id}>
                <td>
                  <Link to={`/awards/${award.award_id}`}>{award.short_code}</Link>
                  <div className="muted">{award.title}</div>
                </td>
                <td>
                  <span className="status">{award.status_code}</span>
                </td>
                <td>{formatCents(award.remaining_funded_cents)}</td>
                <td>{formatCents(award.remaining_approved_cents)}</td>
                <td>{award.runway_days == null ? "—" : `${award.runway_days}d`}</td>
                <td>{award.next_compliance_due || "—"}</td>
                <td>{(award.alert_codes || []).join(", ") || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
