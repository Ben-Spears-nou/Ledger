import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, formatCents, mondayOnOrBefore, todayIso } from "../api.js";
import CollapsibleSection from "../components/CollapsibleSection.jsx";

export default function Staffing() {
  const [weekStart, setWeekStart] = useState(() => mondayOnOrBefore(todayIso()));
  const [weeks, setWeeks] = useState(8);
  const [board, setBoard] = useState(null);
  const [people, setPeople] = useState([]);
  const [awards, setAwards] = useState([]);
  const [scenario, setScenario] = useState({
    person_id: "",
    award_id: "",
    hours_per_month: "32",
    months: "1",
  });
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function load(start = weekStart, count = weeks) {
    const monday = mondayOnOrBefore(start);
    const [data, personList, awardList] = await Promise.all([
      api("/staffing", { query: { week_start: monday, weeks: count } }),
      api("/people"),
      api("/awards", { query: { as: "picker" } }),
    ]);
    setBoard(data);
    setWeekStart(data.week_start);
    setPeople(personList);
    setAwards(awardList.filter((award) => award.status_code !== "closed"));
    setScenario((current) => ({
      ...current,
      person_id: current.person_id || (personList[0] ? String(personList[0].person_id) : ""),
      award_id: current.award_id || (awardList[0] ? String(awardList[0].award_id) : ""),
    }));
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function apply(event) {
    event.preventDefault();
    setError("");
    try {
      await load(weekStart, Number(weeks) || 8);
    } catch (err) {
      setError(err.message);
    }
  }

  async function runScenario(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    try {
      const data = await api("/staffing/scenario", {
        method: "POST",
        body: {
          person_id: Number(scenario.person_id),
          award_id: Number(scenario.award_id),
          hours_per_month: Number(scenario.hours_per_month),
          week_start: weekStart,
          months: Number(scenario.months) || 1,
        },
      });
      setResult(data);
      setNotice("Scenario is a preview. It did not add an assignment.");
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <>
      <h1>Staffing</h1>
      <p className="muted">
        Assignments are monthly and do not post. Weekly assigned hours are working-day
        projections; plan dollars are a preview against remaining personnel and funded.
      </p>
      {error ? <p className="error">{error}</p> : null}
      {notice ? <p>{notice}</p> : null}
      <CollapsibleSection title="Staffing window">
        <form onSubmit={apply}>
          <div className="row">
            <div>
              <label>Week start</label>
              <input
                type="date"
                value={weekStart}
                onChange={(event) => setWeekStart(mondayOnOrBefore(event.target.value))}
              />
            </div>
            <div>
              <label>Weeks</label>
              <input
                type="number"
                min="1"
                max="12"
                value={weeks}
                onChange={(event) => setWeeks(Number(event.target.value) || 1)}
              />
            </div>
          </div>
          <p>
            <button type="submit">Show</button>
          </p>
        </form>
      </CollapsibleSection>
      {(board?.people || []).map((person) => (
        <CollapsibleSection
          key={person.person_id}
          title={
            <>
            {person.display_name}{" "}
            {person.overload ? <span className="status">overload</span> : null}
            </>
          }
        >
          <table>
            <thead>
              <tr>
                <th>Week</th>
                <th>Capacity</th>
                <th>Assigned</th>
                <th>Logged</th>
                <th>Slack</th>
              </tr>
            </thead>
            <tbody>
              {person.weeks.map((week) => (
                <tr key={week.week_start}>
                  <td>{week.week_start}</td>
                  <td>{week.capacity_hours}</td>
                  <td>{week.assigned_hours}</td>
                  <td>{week.logged_hours}</td>
                  <td>
                    {week.slack_hours}
                    {week.overload ? " !" : ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {person.assignments.length ? (
            <table>
              <thead>
                <tr>
                  <th>Award</th>
                  <th>Hours/month</th>
                  <th>Projected this week</th>
                  <th>Plan / month</th>
                  <th>Personnel left</th>
                  <th>Funded left</th>
                </tr>
              </thead>
              <tbody>
                {person.assignments.map((row) => (
                  <tr key={`${row.award_id}-${row.task_id || "a"}`}>
                    <td>
                      <Link to={`/awards/${row.award_id}`}>{row.short_code}</Link>
                      {row.task_short_code ? ` / ${row.task_short_code}` : ""}
                    </td>
                    <td>{row.hours_per_month}</td>
                    <td>{row.projected_hours}</td>
                    <td>{row.plan_cents == null ? "—" : formatCents(row.plan_cents)}</td>
                    <td>
                      {row.remaining_personnel_cents == null
                        ? "—"
                        : formatCents(row.remaining_personnel_cents)}
                      {row.personnel_fit === false ? " over" : ""}
                    </td>
                    <td>
                      {row.remaining_funded_cents == null
                        ? "—"
                        : formatCents(row.remaining_funded_cents)}
                      {row.funded_fit === false ? " over" : ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="muted">No assignments this week.</p>
          )}
          {person.tasks.length ? (
            <table>
              <thead>
                <tr>
                  <th>Task</th>
                  <th>Assigned</th>
                  <th>Logged</th>
                </tr>
              </thead>
              <tbody>
                {person.tasks.map((row) => (
                  <tr key={`${row.award_id}-${row.task_id || "none"}`}>
                    <td>
                      {row.short_code}
                      {row.task_short_code ? ` / ${row.task_short_code}` : " (award)"}
                    </td>
                    <td>{row.assigned_hours}</td>
                    <td>{row.logged_hours}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
        </CollapsibleSection>
      ))}
      <CollapsibleSection title="Utilization">
        <p className="muted">Hours by time code in this window. Direct is award hours. Not payroll.</p>
        <table>
          <thead>
            <tr>
              <th>Person</th>
              <th>Direct</th>
              <th>Total</th>
              <th>Direct %</th>
            </tr>
          </thead>
          <tbody>
            {(board?.utilization || []).map((row) => (
              <tr key={row.person_id}>
                <td>{row.display_name}</td>
                <td>{row.direct_hours}</td>
                <td>{row.total_hours}</td>
                <td>{row.direct_pct == null ? "—" : `${row.direct_pct}%`}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </CollapsibleSection>
      <CollapsibleSection title="What if">
        <form onSubmit={runScenario}>
          <div className="row">
            <div>
              <label>Person</label>
              <select
                value={scenario.person_id}
                onChange={(event) =>
                  setScenario((current) => ({ ...current, person_id: event.target.value }))
                }
              >
                {people.map((person) => (
                  <option key={person.person_id} value={person.person_id}>
                    {person.display_name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label>Award</label>
              <select
                value={scenario.award_id}
                onChange={(event) =>
                  setScenario((current) => ({ ...current, award_id: event.target.value }))
                }
              >
                {awards.map((award) => (
                  <option key={award.award_id} value={award.award_id}>
                    {award.short_code}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label>Hours / month</label>
              <input
                value={scenario.hours_per_month}
                onChange={(event) =>
                  setScenario((current) => ({ ...current, hours_per_month: event.target.value }))
                }
              />
            </div>
            <div>
              <label>Months</label>
              <input
                value={scenario.months}
                onChange={(event) =>
                  setScenario((current) => ({ ...current, months: event.target.value }))
                }
              />
            </div>
          </div>
          <p>
            <button type="submit">Preview</button>
          </p>
        </form>
        {result ? (
          <p>
            {formatCents(result.plan_cents)} over {result.months} month(s)
            {result.personnel_fit === false ? " · over remaining personnel" : ""}
            {result.funded_fit === false ? " · over remaining funded" : ""}
          </p>
        ) : null}
      </CollapsibleSection>
    </>
  );
}
