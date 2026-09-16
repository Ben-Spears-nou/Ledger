import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, todayIso } from "../api.js";

function GanttChart({ chart }) {
  if (!chart || !chart.bars?.length) {
    return <p className="muted">No confirmed schedule rows yet.</p>;
  }
  return (
    <div className="gantt">
      <p className="muted">
        {chart.chart_start} → {chart.chart_end} · as of {chart.as_of}
      </p>
      {chart.bars.map((bar) => (
        <div className="gantt-row" key={bar.schedule_item_id}>
          <div className="gantt-label">
            <strong>{bar.award_short_code}</strong> {bar.title}
            <span className={`gantt-lane ${bar.lane}`}>{bar.lane}</span>
          </div>
          <div className="gantt-track">
            <div
              className={`gantt-bar ${bar.lane}`}
              style={{ marginLeft: `${bar.offset_pct}%`, width: `${bar.width_pct}%` }}
              title={`${bar.start_date} – ${bar.due_date}`}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

export default function Gantt() {
  const [chart, setChart] = useState(null);
  const [error, setError] = useState("");
  const [asOf, setAsOf] = useState(todayIso());

  async function load(nextAsOf = asOf) {
    const data = await api("/gantt", { query: { as_of: nextAsOf } });
    setChart(data);
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

  const grouped = { behind: 0, remaining: 0, completed: 0 };
  for (const bar of chart?.bars || []) {
    grouped[bar.lane] = (grouped[bar.lane] || 0) + 1;
  }

  return (
    <>
      <h1>Gantt</h1>
      <p className="muted">
        Confirmed contract milestones and deliverables. Completed, remaining, and
        behind are as-of the date you pick. Print this page for a snapshot.
      </p>
      {error ? <p className="error">{error}</p> : null}
      <div className="card gantt-toolbar">
        <form onSubmit={apply} className="row">
          <div>
            <label>As of</label>
            <input type="date" value={asOf} onChange={(event) => setAsOf(event.target.value)} />
          </div>
          <div>
            <button type="submit">Update</button>{" "}
            <button type="button" className="secondary" onClick={() => window.print()}>
              Print
            </button>
          </div>
        </form>
        <p className="muted">
          Behind {grouped.behind} · remaining {grouped.remaining} · completed {grouped.completed}
        </p>
      </div>
      <div className="card">
        <GanttChart chart={chart} />
        <ul>
          {(chart?.bars || []).map((bar) => (
            <li key={`link-${bar.schedule_item_id}`}>
              <Link to={`/awards/${bar.award_id}`}>
                {bar.award_short_code}: {bar.title}
              </Link>{" "}
              ({bar.due_date}, {bar.lane})
            </li>
          ))}
        </ul>
      </div>
    </>
  );
}

export { GanttChart };
