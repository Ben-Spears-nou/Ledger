import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, formatCents, todayIso } from "../api.js";

export default function Home() {
  const [asOf, setAsOf] = useState(todayIso());
  const [home, setHome] = useState(null);
  const [error, setError] = useState("");

  async function load(nextAsOf = asOf) {
    const data = await api("/home", { query: { as_of: nextAsOf } });
    setHome(data);
    setAsOf(data.as_of);
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

  if (!home && !error) {
    return <p className="muted">Loading…</p>;
  }

  const close = home?.close;

  return (
    <>
      <h1>Home</h1>
      <p className="muted">
        This week’s decisions. Not email. Close is a checklist, not the books.
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
      </div>
      {close ? (
        <div className="card">
          <h2>Close through {close.week_start}</h2>
          <p>
            Missing weeks {close.missing_week_count} · drafts {close.draft_count} · submitted{" "}
            {close.submitted_count} · open commitments {close.open_commitment_count}
          </p>
          <p>
            <Link to="/audit">Charges CSV</Link>
          </p>
        </div>
      ) : null}
      <div className="card">
        <h2>Missing timesheets</h2>
        {(home?.missing_weeks || []).length ? (
          <ul>
            {home.missing_weeks.map((row) => (
              <li key={row.person_id}>
                {row.display_name}
                {row.status_code ? ` (${row.status_code})` : " (none)"}
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">Everyone with a login has submitted or been approved.</p>
        )}
      </div>
      <div className="card">
        <h2>Approvals</h2>
        {(home?.approvals || []).length ? (
          <ul>
            {home.approvals.map((row) => (
              <li key={row.timesheet_period_id}>
                <Link to="/approvals">
                  {row.display_name} · {row.week_start} · {row.hours_total}h
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">None waiting.</p>
        )}
      </div>
      <div className="card">
        <h2>Compliance due in 14 days</h2>
        {(home?.compliance_due || []).length ? (
          <table>
            <thead>
              <tr>
                <th>Due</th>
                <th>Award</th>
                <th>Title</th>
              </tr>
            </thead>
            <tbody>
              {home.compliance_due.map((row) => (
                <tr key={row.compliance_item_id}>
                  <td>{row.due_date}</td>
                  <td>
                    <Link to={`/awards/${row.award_id}`}>{row.award_short_code}</Link>
                  </td>
                  <td>{row.title}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="muted">None due.</p>
        )}
      </div>
      <div className="card">
        <h2>Aging open commitments</h2>
        {(home?.aging_commitments || []).length ? (
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Award</th>
                <th>Amount</th>
                <th>Age</th>
              </tr>
            </thead>
            <tbody>
              {home.aging_commitments.map((row) => (
                <tr key={row.commitment_id}>
                  <td>{row.aging_date}</td>
                  <td>
                    <Link to={`/awards/${row.award_id}`}>{row.award_short_code}</Link>
                  </td>
                  <td>{formatCents(row.amount_cents)}</td>
                  <td>{row.age_days}d</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="muted">None older than 14 days.</p>
        )}
      </div>
      <div className="card">
        <h2>Portfolio</h2>
        <p className="muted">
          Remaining and runway as of this date.{" "}
          <Link to="/portfolio">Open the awards table</Link>
        </p>
        {(home?.portfolio || []).length ? (
          <table>
            <thead>
              <tr>
                <th>Award</th>
                <th>Funded remaining</th>
                <th>Runway</th>
                <th>Next due</th>
                <th>Alerts</th>
              </tr>
            </thead>
            <tbody>
              {home.portfolio.map((award) => (
                <tr key={award.award_id}>
                  <td>
                    <Link to={`/awards/${award.award_id}`}>{award.short_code}</Link>
                  </td>
                  <td>{formatCents(award.remaining_funded_cents)}</td>
                  <td>{award.runway_days == null ? "—" : `${award.runway_days}d`}</td>
                  <td>{award.next_compliance_due || "—"}</td>
                  <td>{(award.alert_codes || []).join(", ") || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="muted">No awards.</p>
        )}
      </div>
    </>
  );
}
