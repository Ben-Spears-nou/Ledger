import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, formatCents } from "../api.js";

export default function Approvals() {
  const [weeks, setWeeks] = useState([]);
  const [comment, setComment] = useState({});
  const [error, setError] = useState("");

  async function load() {
    const data = await api("/approvals");
    setWeeks(data);
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
  }, []);

  async function approve(periodId) {
    setError("");
    try {
      await api(`/approvals/${periodId}/approve`, { method: "POST" });
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function bounce(periodId) {
    setError("");
    try {
      await api(`/approvals/${periodId}/return`, {
        method: "POST",
        body: { comment: comment[periodId] || "Please revise." },
      });
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <>
      <h1>Approvals</h1>
      {error ? <p className="error">{error}</p> : null}
      {weeks.length === 0 ? <p className="muted">No submitted weeks.</p> : null}
      {weeks.map((week) => (
        <div className="card" key={week.timesheet_period_id}>
          <h2>
            {week.display_name} · week of {week.week_start}{" "}
            <span className="status">{formatCents(week.amount_cents)}</span>
          </h2>
          <p className="muted">{week.hours_total} hours</p>
          {(week.warnings || []).length ? (
            <ul>
              {week.warnings.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          ) : null}
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Hours</th>
                <th>Award</th>
                <th>Task</th>
                <th>Amount</th>
              </tr>
            </thead>
            <tbody>
              {week.lines.map((line) => (
                <tr key={line.timesheet_line_id}>
                  <td>{line.work_date}</td>
                  <td>{line.hours}</td>
                  <td>
                    {line.award_id ? (
                      <Link to={`/awards/${line.award_id}`}>#{line.award_id}</Link>
                    ) : (
                      line.time_code
                    )}
                  </td>
                  <td>{line.task_id ? `#${line.task_id}` : "—"}</td>
                  <td>{line.amount_cents == null ? "—" : formatCents(line.amount_cents)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="row" style={{ marginTop: "0.8rem" }}>
            <div>
              <label>Return comment</label>
              <input
                value={comment[week.timesheet_period_id] || ""}
                onChange={(event) =>
                  setComment((current) => ({
                    ...current,
                    [week.timesheet_period_id]: event.target.value,
                  }))
                }
              />
            </div>
            <div>
              <button type="button" onClick={() => approve(week.timesheet_period_id)}>
                Approve
              </button>{" "}
              <button
                type="button"
                className="secondary"
                onClick={() => bounce(week.timesheet_period_id)}
              >
                Return
              </button>
            </div>
          </div>
        </div>
      ))}
    </>
  );
}
