import { useEffect, useState } from "react";
import { api, todayIso } from "../api.js";
import { progressColor } from "../progress.js";

export function WorkGanttChart({ chart }) {
  if (!chart || !chart.bars?.length) {
    return <p className="muted">No confirmed work-plan rows yet.</p>;
  }
  return (
    <div className="gantt work-gantt">
      <p className="muted">
        {chart.chart_start} → {chart.chart_end} · as of {chart.as_of}
      </p>
      {chart.bars.map((bar) => (
        <div className="gantt-row" key={bar.work_plan_item_id}>
          <div className="gantt-label">
            <strong>{bar.award_short_code}</strong>{" "}
            {bar.requirement_code ? `${bar.requirement_code} ` : ""}
            {bar.title}
            <span className={`gantt-lane ${bar.lane}`}>
              {(bar.percent_complete_bp / 100).toFixed(0)}%
            </span>
          </div>
          <div className="gantt-track">
            <div
              className={`gantt-bar work-gantt-bar ${bar.lane}`}
              style={{ marginLeft: `${bar.offset_pct}%`, width: `${bar.width_pct}%` }}
              title={`${bar.start_date} – ${bar.due_date}; ${(
                bar.percent_complete_bp / 100
              ).toFixed(0)}% complete`}
            >
              <span
                className="work-gantt-progress"
                style={{
                  width: `${bar.complete_width_pct}%`,
                  background: progressColor(bar.percent_complete_bp),
                }}
              />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

export default function WorkGantt() {
  const [chart, setChart] = useState(null);
  const [error, setError] = useState("");
  const [asOf, setAsOf] = useState(todayIso());

  async function load(nextAsOf = asOf) {
    setChart(await api("/work-gantt", { query: { as_of: nextAsOf } }));
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
      <h1>Work progress Gantt</h1>
      <p className="muted">
        SOW requirements with operator-maintained percent complete. Print this
        view for monthly reports and presentations.
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
      </div>
      <div className="card">
        <WorkGanttChart chart={chart} />
      </div>
    </>
  );
}
