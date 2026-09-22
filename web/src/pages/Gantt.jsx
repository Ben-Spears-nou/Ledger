import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, getUser, todayIso } from "../api.js";
import { MonthGantt } from "./MonthGantt.jsx";

function GanttChart({ chart, title = "Contract schedule", colorByAward = false }) {
  return (
    <MonthGantt
      chart={chart}
      title={title}
      empty="No confirmed schedule rows yet."
      colorByAward={colorByAward}
      rows={(chart?.bars || []).map((bar) => ({
        key: bar.schedule_item_id,
        label: `${bar.award_short_code} ${bar.title}`,
        colorKey: bar.award_id,
        colorLabel: bar.award_short_code,
        lane: bar.lane,
        startDate: bar.start_date,
        dueDate: bar.due_date,
        tooltip: `${bar.start_date} – ${bar.due_date}`,
      }))}
    />
  );
}

export default function Gantt() {
  const [chart, setChart] = useState(null);
  const [awards, setAwards] = useState([]);
  const [awardId, setAwardId] = useState("");
  const [error, setError] = useState("");
  const [asOf, setAsOf] = useState(todayIso());

  async function load(nextAsOf = asOf, nextAwardId = awardId) {
    const data = await api("/gantt", {
      query: { as_of: nextAsOf, award_id: nextAwardId || undefined },
    });
    setChart(data);
  }

  useEffect(() => {
    Promise.all([load(), api("/awards", { query: { as: "picker" } })])
      .then(([, awardList]) => setAwards(awardList))
      .catch((err) => setError(err.message));
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

  async function selectAward(event) {
    const nextAwardId = event.target.value;
    setAwardId(nextAwardId);
    setError("");
    try {
      await load(asOf, nextAwardId);
    } catch (err) {
      setError(err.message);
    }
  }

  const grouped = { behind: 0, remaining: 0, completed: 0 };
  for (const bar of chart?.bars || []) {
    grouped[bar.lane] = (grouped[bar.lane] || 0) + 1;
  }
  const selectedAward = awards.find((award) => String(award.award_id) === awardId);
  const isAdmin = getUser()?.role_code === "admin";

  return (
    <>
      <h1>Gantt</h1>
      <p className="muted">
        Confirmed contract milestones and deliverables. All awards are colored
        per award; pick one award for lane colors. Completed, remaining, and
        behind are as-of the date you pick. Print this page for a snapshot.
      </p>
      {error ? <p className="error">{error}</p> : null}
      <div className="card gantt-toolbar">
        <form onSubmit={apply} className="row">
          <div>
            <label>Award</label>
            <select value={awardId} onChange={selectAward}>
              <option value="">All awards</option>
              {awards.map((award) => (
                <option key={award.award_id} value={award.award_id}>
                  {award.short_code}: {award.title}
                </option>
              ))}
            </select>
          </div>
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
        <GanttChart
          chart={chart}
          colorByAward={!awardId}
          title={
            selectedAward
              ? `${selectedAward.short_code} — Contract schedule`
              : "Portfolio contract schedule"
          }
        />
        <ul>
          {(chart?.bars || []).map((bar) => {
            const label = `${bar.award_short_code}: ${bar.title}`;
            return (
              <li key={`link-${bar.schedule_item_id}`}>
                {isAdmin ? <Link to={`/awards/${bar.award_id}`}>{label}</Link> : label}{" "}
                ({bar.due_date}, {bar.lane})
              </li>
            );
          })}
        </ul>
      </div>
    </>
  );
}

export { GanttChart };
