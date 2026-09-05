import { useEffect, useMemo, useState } from "react";
import { api, mondayOnOrBefore, newLineKey, todayIso } from "../api.js";

function emptyLine(weekStart) {
  return {
    key: newLineKey(),
    work_date: weekStart,
    hours: "",
    award_id: "",
    task_id: "",
    time_code: "award",
  };
}

function lineFromApi(row, weekStart) {
  return {
    key: row.timesheet_line_id != null ? `id-${row.timesheet_line_id}` : newLineKey(),
    work_date: row.work_date || weekStart,
    hours: row.hours ?? "",
    award_id: row.award_id ?? "",
    task_id: row.task_id ?? "",
    time_code: row.time_code || "award",
  };
}

export default function MyWeek() {
  const [weekStart, setWeekStart] = useState(() => mondayOnOrBefore(todayIso()));
  const [status, setStatus] = useState("draft");
  const [returnComment, setReturnComment] = useState("");
  const [lines, setLines] = useState(() => [emptyLine(mondayOnOrBefore(todayIso()))]);
  const [awards, setAwards] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [timeCodes, setTimeCodes] = useState([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const locked = status === "submitted" || status === "approved";

  const hoursTotal = useMemo(
    () => lines.reduce((sum, line) => sum + (Number(line.hours) || 0), 0),
    [lines],
  );

  async function load(start) {
    setError("");
    const monday = mondayOnOrBefore(start);
    const [week, picker, lookups, taskList] = await Promise.all([
      api("/me/week", { query: { week_start: monday } }),
      api("/awards", { query: { as: "picker" } }),
      api("/lookups"),
      api("/tasks"),
    ]);
    setWeekStart(week.week_start);
    setStatus(week.status_code);
    setReturnComment(week.return_comment || "");
    const openAwards = picker.filter((award) => award.status_code !== "closed");
    setAwards(openAwards);
    setTasks(taskList || []);
    setTimeCodes(lookups.time_codes || []);
    const next = (week.lines || []).map((row) => lineFromApi(row, week.week_start));
    setLines(next.length ? next : [emptyLine(week.week_start)]);
  }

  useEffect(() => {
    load(weekStart).catch((err) => setError(err.message));
    // weekStart is the controlled picker; load is invoked on change via onWeekChange.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function onWeekChange(value) {
    const monday = mondayOnOrBefore(value);
    setWeekStart(monday);
    load(monday).catch((err) => setError(err.message));
  }

  function updateLine(key, patch) {
    setLines((current) => current.map((line) => (line.key === key ? { ...line, ...patch } : line)));
  }

  function payloadLines() {
    return lines
      .filter((line) => Number(line.hours) > 0)
      .map((line) => {
        const timeCode = line.time_code || "award";
        const body = {
          work_date: line.work_date,
          hours: Number(line.hours),
          time_code: timeCode,
        };
        if (timeCode === "award") {
          body.award_id = line.award_id ? Number(line.award_id) : null;
          if (line.task_id) {
            body.task_id = Number(line.task_id);
          }
        }
        return body;
      });
  }

  async function save() {
    setError("");
    setNotice("");
    try {
      const week = await api("/me/week", {
        method: "PUT",
        body: { week_start: weekStart, lines: payloadLines() },
      });
      setStatus(week.status_code);
      setReturnComment(week.return_comment || "");
      const next = (week.lines || []).map((row) => lineFromApi(row, week.week_start));
      setLines(next.length ? next : [emptyLine(week.week_start)]);
      setNotice("Saved.");
    } catch (err) {
      setError(err.message);
    }
  }

  async function submit() {
    setError("");
    setNotice("");
    try {
      await api("/me/week", {
        method: "PUT",
        body: { week_start: weekStart, lines: payloadLines() },
      });
      const week = await api("/me/week/submit", {
        method: "POST",
        query: { week_start: weekStart },
      });
      setStatus(week.status_code);
      setNotice("Submitted.");
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <>
      <h1>My week</h1>
      <p className="muted">
        Hours only. A new empty week may prefill from your assignments — edit freely. Running total
        is informational.
      </p>
      <div className="card">
        <div className="row">
          <div>
            <label htmlFor="week">Week of (Monday)</label>
            <input
              id="week"
              type="date"
              value={weekStart}
              onChange={(event) => onWeekChange(event.target.value)}
            />
          </div>
          <div>
            <label>Status</label>
            <div>
              <span className="status">{status}</span>
            </div>
          </div>
          <div>
            <label>Hours this week</label>
            <div>{hoursTotal}</div>
          </div>
        </div>
        {returnComment ? <p>Returned: {returnComment}</p> : null}
      </div>

      {lines.map((line) => (
        <div className="card" key={line.key}>
          <div className="row">
            <div>
              <label>Date</label>
              <input
                type="date"
                disabled={locked}
                value={line.work_date}
                onChange={(event) => updateLine(line.key, { work_date: event.target.value })}
              />
            </div>
            <div>
              <label>Hours</label>
              <input
                type="number"
                min="0"
                step="0.25"
                disabled={locked}
                value={line.hours}
                onChange={(event) => updateLine(line.key, { hours: event.target.value })}
              />
            </div>
            <div>
              <label>Time code</label>
              <select
                disabled={locked}
                value={line.time_code}
                onChange={(event) => updateLine(line.key, { time_code: event.target.value })}
              >
                {(timeCodes.length ? timeCodes : [{ time_code: "award", description: "Award" }]).map(
                  (code) => (
                    <option key={code.time_code} value={code.time_code}>
                      {code.time_code}
                    </option>
                  ),
                )}
              </select>
            </div>
            <div>
              <label>Award</label>
              <select
                disabled={locked || line.time_code !== "award"}
                value={line.award_id}
                onChange={(event) =>
                  updateLine(line.key, { award_id: event.target.value, task_id: "" })
                }
              >
                <option value="">Select award</option>
                {awards.map((award) => (
                  <option key={award.award_id} value={award.award_id}>
                    {award.short_code} — {award.title}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label>Task</label>
              <select
                disabled={locked || line.time_code !== "award" || !line.award_id}
                value={line.task_id}
                onChange={(event) => updateLine(line.key, { task_id: event.target.value })}
              >
                <option value="">No task</option>
                {tasks
                  .filter(
                    (task) =>
                      String(task.award_id) === String(line.award_id) &&
                      (task.status_code === "open" || String(task.task_id) === String(line.task_id)),
                  )
                  .map((task) => (
                    <option key={task.task_id} value={task.task_id}>
                      {task.short_code} — {task.title}
                    </option>
                  ))}
              </select>
            </div>
          </div>
          {!locked ? (
            <p>
              <button
                type="button"
                className="secondary"
                onClick={() => setLines((current) => current.filter((item) => item.key !== line.key))}
              >
                Remove line
              </button>
            </p>
          ) : null}
        </div>
      ))}

      {!locked ? (
        <p>
          <button type="button" className="secondary" onClick={() => setLines((current) => [...current, emptyLine(weekStart)])}>
            Add line
          </button>{" "}
          <button type="button" onClick={save}>
            Save
          </button>{" "}
          <button type="button" onClick={submit}>
            Submit
          </button>
        </p>
      ) : (
        <p className="muted">This week is {status} and cannot be edited here.</p>
      )}
      {notice ? <p>{notice}</p> : null}
      {error ? <p className="error">{error}</p> : null}
    </>
  );
}
