import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, formatCents } from "../api.js";

function WeekCard({
  week,
  comment,
  setComment,
  onApprove,
  onReturn,
  onUnapprove,
}) {
  const approved = week.status_code === "approved";
  return (
    <div className="card">
      <h2>
        {week.display_name} · week of {week.week_start}{" "}
        <span className="status">{formatCents(week.amount_cents)}</span>
      </h2>
      <p className="muted">
        {week.hours_total} hours
        {approved ? " · approved" : ""}
      </p>
      {week.return_comment ? <p>Returned: {week.return_comment}</p> : null}
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
          <label htmlFor={`week-comment-${week.timesheet_period_id}`}>
            {approved ? "Unapprove comment (required)" : "Return comment"}
          </label>
          <input
            id={`week-comment-${week.timesheet_period_id}`}
            value={comment[week.timesheet_period_id] || ""}
            required={approved}
            onChange={(event) =>
              setComment((current) => ({
                ...current,
                [week.timesheet_period_id]: event.target.value,
              }))
            }
          />
        </div>
        <div>
          {approved ? (
            <button type="button" className="secondary" onClick={() => onUnapprove(week.timesheet_period_id)}>
              Unapprove week
            </button>
          ) : (
            <>
              <button type="button" onClick={() => onApprove(week.timesheet_period_id)}>
                Approve
              </button>{" "}
              <button
                type="button"
                className="secondary"
                onClick={() => onReturn(week.timesheet_period_id)}
              >
                Return
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default function Approvals() {
  const [weeks, setWeeks] = useState([]);
  const [approvedWeeks, setApprovedWeeks] = useState([]);
  const [comment, setComment] = useState({});
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function load() {
    const [submitted, approved] = await Promise.all([
      api("/approvals"),
      api("/approvals", { query: { status: "approved" } }),
    ]);
    setWeeks(submitted);
    setApprovedWeeks(approved);
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
  }, []);

  async function approve(periodId) {
    setError("");
    setNotice("");
    try {
      await api(`/approvals/${periodId}/approve`, { method: "POST" });
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function bounce(periodId) {
    setError("");
    setNotice("");
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

  async function unapprove(periodId) {
    setError("");
    setNotice("");
    const note = (comment[periodId] || "").trim();
    if (!note) {
      setError("Enter a comment so the person knows why the week was unapproved.");
      return;
    }
    if (
      !window.confirm(
        "Unapprove this week? Posted labor will be reversed (not deleted) and the person can recode hours.",
      )
    ) {
      return;
    }
    try {
      await api(`/approvals/${periodId}/unapprove`, {
        method: "POST",
        body: { comment: note },
      });
      setNotice("Week unapproved. Posted labor was reversed; they can recode hours on My week.");
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <>
      <h1>Approvals</h1>
      <p className="muted">
        Approve posts labor. Unapprove reverses those charges and returns the week so hours can
        be moved to the right award.
      </p>
      {error ? <p className="error">{error}</p> : null}
      {notice ? <p>{notice}</p> : null}
      <h2>Waiting</h2>
      {weeks.length === 0 ? <p className="muted">No submitted weeks.</p> : null}
      {weeks.map((week) => (
        <WeekCard
          key={week.timesheet_period_id}
          week={week}
          comment={comment}
          setComment={setComment}
          onApprove={approve}
          onReturn={bounce}
          onUnapprove={unapprove}
        />
      ))}
      <h2>Approved</h2>
      {approvedWeeks.length === 0 ? <p className="muted">No approved weeks to reverse.</p> : null}
      {approvedWeeks.map((week) => (
        <WeekCard
          key={week.timesheet_period_id}
          week={week}
          comment={comment}
          setComment={setComment}
          onApprove={approve}
          onReturn={bounce}
          onUnapprove={unapprove}
        />
      ))}
    </>
  );
}
