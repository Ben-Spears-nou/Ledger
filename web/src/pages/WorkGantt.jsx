import { useEffect, useState } from "react";
import { api, todayIso } from "../api.js";
import CollapsibleSection from "../components/CollapsibleSection.jsx";
import { MonthGantt } from "./MonthGantt.jsx";

export function WorkGanttChart({ chart, title = "SOW work progress" }) {
  return (
    <MonthGantt
      chart={chart}
      title={title}
      empty="No confirmed work-plan rows yet."
      rows={(chart?.bars || []).map((bar) => ({
        key: bar.work_plan_item_id,
        label: `${bar.award_short_code} ${
          bar.requirement_code ? `${bar.requirement_code}: ` : ""
        }${bar.title}`,
        lane: bar.lane,
        percentBp: bar.percent_complete_bp,
        startDate: bar.start_date,
        dueDate: bar.due_date,
        tooltip: `${bar.start_date} – ${bar.due_date}; ${(
          bar.percent_complete_bp / 100
        ).toFixed(0)}% complete`,
      }))}
    />
  );
}

export default function WorkGantt() {
  const [chart, setChart] = useState(null);
  const [awards, setAwards] = useState([]);
  const [awardId, setAwardId] = useState("");
  const [error, setError] = useState("");
  const [asOf, setAsOf] = useState(todayIso());

  async function load(nextAsOf = asOf, nextAwardId = awardId) {
    setChart(
      await api("/work-gantt", {
        query: { as_of: nextAsOf, award_id: nextAwardId || undefined },
      }),
    );
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

  const selectedAward = awards.find((award) => String(award.award_id) === awardId);

  return (
    <>
      <h1>Work progress Gantt</h1>
      <p className="muted">
        SOW requirements with operator-maintained percent complete. Print this
        view for monthly reports and presentations.
      </p>
      {error ? <p className="error">{error}</p> : null}
      <CollapsibleSection title="Chart controls" className="gantt-toolbar">
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
      </CollapsibleSection>
      <CollapsibleSection title="SOW work progress chart">
        <WorkGanttChart
          chart={chart}
          title={
            selectedAward
              ? `${selectedAward.short_code} — SOW work progress`
              : "Portfolio SOW work progress"
          }
        />
      </CollapsibleSection>
    </>
  );
}
