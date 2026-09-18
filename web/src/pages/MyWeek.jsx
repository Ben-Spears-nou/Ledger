import { useEffect, useMemo, useState } from "react";
import { addDaysIso, api, mondayOnOrBefore, newLineKey, todayIso } from "../api.js";

const DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function emptyHours() {
  return ["", "", "", "", "", "", ""];
}

function emptyRow() {
  return {
    key: newLineKey(),
    time_code: "award",
    award_id: "",
    task_id: "",
    hours: emptyHours(),
  };
}

function dayIndex(workDate, weekStart) {
  const [y1, m1, d1] = weekStart.split("-").map(Number);
  const [y2, m2, d2] = workDate.split("-").map(Number);
  const start = Date.UTC(y1, m1 - 1, d1);
  const work = Date.UTC(y2, m2 - 1, d2);
  const index = Math.round((work - start) / 86400000);
  return index;
}

function rowIdentity(line) {
  const timeCode = line.time_code || "award";
  if (timeCode !== "award") {
    return `${timeCode}|`;
  }
  return `award|${line.award_id ?? ""}|${line.task_id ?? ""}`;
}

function rowsFromLines(lines, weekStart) {
  const byKey = new Map();
  for (const line of lines || []) {
    const identity = rowIdentity(line);
    if (!byKey.has(identity)) {
      byKey.set(identity, {
        key: newLineKey(),
        time_code: line.time_code || "award",
        award_id: line.award_id ?? "",
        task_id: line.task_id ?? "",
        hours: emptyHours(),
      });
    }
    const row = byKey.get(identity);
    const index = dayIndex(line.work_date, weekStart);
    if (index >= 0 && index < 7) {
      const previous = Number(row.hours[index]) || 0;
      const next = previous + Number(line.hours || 0);
      row.hours[index] = next ? String(next) : "";
    }
  }
  return byKey.size ? Array.from(byKey.values()) : [emptyRow()];
}

function roundHours(value) {
  return Math.round((Number(value) || 0) * 100) / 100;
}

export default function MyWeek() {
  const [weekStart, setWeekStart] = useState(() => mondayOnOrBefore(todayIso()));
  const [status, setStatus] = useState("draft");
  const [returnComment, setReturnComment] = useState("");
  const [rows, setRows] = useState(() => [emptyRow()]);
  const [awards, setAwards] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [timeCodes, setTimeCodes] = useState([]);
  const [planned, setPlanned] = useState([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const locked = status === "submitted" || status === "approved";

  const dayDates = useMemo(
    () => DAY_LABELS.map((label, index) => ({ label, date: addDaysIso(weekStart, index) })),
    [weekStart],
  );

  const hoursTotal = useMemo(
    () =>
      roundHours(
        rows.reduce(
          (sum, row) => sum + row.hours.reduce((rowSum, hours) => rowSum + (Number(hours) || 0), 0),
          0,
        ),
      ),
    [rows],
  );

  const dayTotals = useMemo(
    () =>
      DAY_LABELS.map((_, index) =>
        roundHours(rows.reduce((sum, row) => sum + (Number(row.hours[index]) || 0), 0)),
      ),
    [rows],
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
    setPlanned(week.planned || []);
    setRows(rowsFromLines(week.lines, week.week_start));
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

  function updateRow(key, patch) {
    setRows((current) => current.map((row) => (row.key === key ? { ...row, ...patch } : row)));
  }

  function updateHours(key, index, value) {
    setRows((current) =>
      current.map((row) => {
        if (row.key !== key) {
          return row;
        }
        const hours = row.hours.slice();
        hours[index] = value;
        return { ...row, hours };
      }),
    );
  }

  function payloadLines() {
    const lines = [];
    for (const row of rows) {
      const timeCode = row.time_code || "award";
      row.hours.forEach((value, index) => {
        const hours = Number(value);
        if (!(hours > 0)) {
          return;
        }
        const body = {
          work_date: addDaysIso(weekStart, index),
          hours,
          time_code: timeCode,
        };
        if (timeCode === "award") {
          body.award_id = row.award_id ? Number(row.award_id) : null;
          if (row.task_id) {
            body.task_id = Number(row.task_id);
          }
        }
        lines.push(body);
      });
    }
    return lines;
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
      setRows(rowsFromLines(week.lines, week.week_start));
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
      setRows(rowsFromLines(week.lines, week.week_start));
      setPlanned(week.planned || []);
      setNotice("Submitted.");
    } catch (err) {
      setError(err.message);
    }
  }

  const codes = timeCodes.length ? timeCodes : [{ time_code: "award", description: "Award" }];

  return (
    <>
      <h1>My week</h1>
      <p className="muted">
        Pick each award once, then type hours under the days you worked. Leave other days blank.
        Running total is informational.
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
        {planned.length ? (
          <div>
            <p className="muted">Planned this week (hours only):</p>
            <ul>
              {planned.map((row) => {
                const award = awards.find((item) => item.award_id === row.award_id);
                const logged = rows
                  .filter(
                    (item) =>
                      Number(item.award_id) === row.award_id &&
                      (row.task_id ? Number(item.task_id) === row.task_id : !item.task_id),
                  )
                  .reduce(
                    (sum, item) =>
                      sum + item.hours.reduce((rowSum, hours) => rowSum + (Number(hours) || 0), 0),
                    0,
                  );
                return (
                  <li key={`${row.award_id}-${row.task_id || "a"}`}>
                    {award ? award.short_code : `award ${row.award_id}`}: planned {row.hours_per_week}
                    h, logged {roundHours(logged)}h
                  </li>
                );
              })}
            </ul>
          </div>
        ) : null}
        {returnComment ? <p>Returned: {returnComment}</p> : null}
      </div>

      <div className="card week-grid-wrap">
        <table className="week-grid">
          <thead>
            <tr>
              <th>Time code</th>
              <th>Award</th>
              <th>Task</th>
              {dayDates.map((day) => (
                <th key={day.date} className={day.label === "Sat" || day.label === "Sun" ? "weekend" : ""}>
                  {day.label}
                  <div className="muted">{day.date.slice(5)}</div>
                </th>
              ))}
              <th>Total</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const rowTotal = roundHours(
                row.hours.reduce((sum, hours) => sum + (Number(hours) || 0), 0),
              );
              const awardTime = row.time_code === "award";
              return (
                <tr key={row.key}>
                  <td>
                    <select
                      disabled={locked}
                      value={row.time_code}
                      onChange={(event) => {
                        const timeCode = event.target.value;
                        updateRow(row.key, {
                          time_code: timeCode,
                          award_id: timeCode === "award" ? row.award_id : "",
                          task_id: timeCode === "award" ? row.task_id : "",
                        });
                      }}
                    >
                      {codes.map((code) => (
                        <option key={code.time_code} value={code.time_code}>
                          {code.time_code}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <select
                      disabled={locked || !awardTime}
                      value={row.award_id}
                      onChange={(event) =>
                        updateRow(row.key, { award_id: event.target.value, task_id: "" })
                      }
                    >
                      <option value="">{awardTime ? "Select award" : "—"}</option>
                      {awards.map((award) => (
                        <option key={award.award_id} value={award.award_id}>
                          {award.short_code} — {award.title}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <select
                      disabled={locked || !awardTime || !row.award_id}
                      value={row.task_id}
                      onChange={(event) => updateRow(row.key, { task_id: event.target.value })}
                    >
                      <option value="">No task</option>
                      {tasks
                        .filter(
                          (task) =>
                            String(task.award_id) === String(row.award_id) &&
                            (task.status_code === "open" ||
                              String(task.task_id) === String(row.task_id)),
                        )
                        .map((task) => (
                          <option key={task.task_id} value={task.task_id}>
                            {task.short_code}
                          </option>
                        ))}
                    </select>
                  </td>
                  {row.hours.map((value, index) => (
                    <td
                      key={dayDates[index].date}
                      className={
                        dayDates[index].label === "Sat" || dayDates[index].label === "Sun"
                          ? "weekend"
                          : ""
                      }
                    >
                      <input
                        className="hours"
                        type="number"
                        min="0"
                        step="0.25"
                        disabled={locked}
                        value={value}
                        onChange={(event) => updateHours(row.key, index, event.target.value)}
                      />
                    </td>
                  ))}
                  <td>{rowTotal}</td>
                  <td>
                    {!locked ? (
                      <button
                        type="button"
                        className="secondary"
                        onClick={() =>
                          setRows((current) => {
                            const next = current.filter((item) => item.key !== row.key);
                            return next.length ? next : [emptyRow()];
                          })
                        }
                      >
                        Remove
                      </button>
                    ) : null}
                  </td>
                </tr>
              );
            })}
          </tbody>
          <tfoot>
            <tr>
              <th colSpan={3}>Totals</th>
              {dayTotals.map((total, index) => (
                <th
                  key={dayDates[index].date}
                  className={
                    dayDates[index].label === "Sat" || dayDates[index].label === "Sun" ? "weekend" : ""
                  }
                >
                  {total}
                </th>
              ))}
              <th>{hoursTotal}</th>
              <th></th>
            </tr>
          </tfoot>
        </table>
      </div>

      {!locked ? (
        <p>
          <button type="button" className="secondary" onClick={() => setRows((current) => [...current, emptyRow()])}>
            Add award
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
