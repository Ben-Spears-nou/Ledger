import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, mondayOnOrBefore, todayIso } from "../api.js";

export default function People() {
  const [weekStart, setWeekStart] = useState(() => mondayOnOrBefore(todayIso()));
  const [people, setPeople] = useState([]);
  const [awards, setAwards] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [rows, setRows] = useState([]);
  const [assignments, setAssignments] = useState([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [capacityForm, setCapacityForm] = useState({
    person_id: "",
    effective_from: todayIso(),
    hours_per_week: "40",
  });
  const [assignForm, setAssignForm] = useState({
    person_id: "",
    award_id: "",
    task_id: "",
    hours_per_week: "",
    effective_from: todayIso(),
  });

  async function load(start) {
    const monday = mondayOnOrBefore(start);
    const [personList, awardList, taskList, capacity, assignList] = await Promise.all([
      api("/people"),
      api("/awards", { query: { as: "picker" } }),
      api("/tasks"),
      api("/capacity", { query: { week_start: monday } }),
      api("/assignments"),
    ]);
    setPeople(personList);
    setAwards(awardList.filter((award) => award.status_code !== "closed"));
    setTasks(taskList);
    setRows(capacity);
    setAssignments(assignList);
    setWeekStart(monday);
    if (!capacityForm.person_id && personList.length) {
      setCapacityForm((current) => ({ ...current, person_id: String(personList[0].person_id) }));
    }
    if (!assignForm.person_id && personList.length) {
      setAssignForm((current) => ({ ...current, person_id: String(personList[0].person_id) }));
    }
  }

  useEffect(() => {
    load(weekStart).catch((err) => setError(err.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function addCapacity(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    try {
      await api(`/people/${capacityForm.person_id}/capacity`, {
        method: "POST",
        body: {
          effective_from: capacityForm.effective_from,
          hours_per_week: Number(capacityForm.hours_per_week),
        },
      });
      setNotice("Capacity saved.");
      await load(weekStart);
    } catch (err) {
      setError(err.message);
    }
  }

  async function addAssignment(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    try {
      const body = {
        person_id: Number(assignForm.person_id),
        award_id: Number(assignForm.award_id),
        hours_per_week: Number(assignForm.hours_per_week),
        effective_from: assignForm.effective_from,
      };
      if (assignForm.task_id) {
        body.task_id = Number(assignForm.task_id);
      }
      await api("/assignments", { method: "POST", body });
      setNotice("Assignment saved.");
      await load(weekStart);
    } catch (err) {
      setError(err.message);
    }
  }

  const personName = Object.fromEntries(people.map((row) => [row.person_id, row.display_name]));
  const awardCode = Object.fromEntries(awards.map((row) => [row.award_id, row.short_code]));
  const taskCode = Object.fromEntries(tasks.map((row) => [row.task_id, row.short_code]));
  const assignTasks = tasks.filter(
    (task) =>
      !assignForm.award_id ||
      (String(task.award_id) === String(assignForm.award_id) && task.status_code === "open"),
  );

  return (
    <>
      <h1>People</h1>
      <p className="muted">
        Capacity and planned hours are informational. They never block a timesheet.
      </p>
      {error ? <p className="error">{error}</p> : null}
      {notice ? <p>{notice}</p> : null}

      <div className="card">
        <div className="row">
          <div>
            <label htmlFor="cap-week">Week of (Monday)</label>
            <input
              id="cap-week"
              type="date"
              value={weekStart}
              onChange={(event) => {
                const monday = mondayOnOrBefore(event.target.value);
                setWeekStart(monday);
                load(monday).catch((err) => setError(err.message));
              }}
            />
          </div>
        </div>
        <h2>Planned vs capacity</h2>
        <table>
          <thead>
            <tr>
              <th>Person</th>
              <th>Capacity</th>
              <th>Planned</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.person_id}>
                <td>{row.display_name}</td>
                <td>{row.capacity_hours}</td>
                <td>{row.planned_hours}</td>
                <td>{row.over_capacity ? <span className="status">over</span> : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h2>Set capacity</h2>
        <form onSubmit={addCapacity}>
          <div className="row">
            <div>
              <label>Person</label>
              <select
                value={capacityForm.person_id}
                onChange={(event) =>
                  setCapacityForm((current) => ({ ...current, person_id: event.target.value }))
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
              <label>Effective from</label>
              <input
                type="date"
                value={capacityForm.effective_from}
                onChange={(event) =>
                  setCapacityForm((current) => ({ ...current, effective_from: event.target.value }))
                }
              />
            </div>
            <div>
              <label>Hours / week</label>
              <input
                type="number"
                min="0"
                step="0.25"
                value={capacityForm.hours_per_week}
                onChange={(event) =>
                  setCapacityForm((current) => ({ ...current, hours_per_week: event.target.value }))
                }
              />
            </div>
          </div>
          <p>
            <button type="submit">Save capacity</button>
          </p>
        </form>
      </div>

      <div className="card">
        <h2>New assignment</h2>
        <form onSubmit={addAssignment}>
          <div className="row">
            <div>
              <label>Person</label>
              <select
                value={assignForm.person_id}
                onChange={(event) =>
                  setAssignForm((current) => ({ ...current, person_id: event.target.value }))
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
                value={assignForm.award_id}
                onChange={(event) =>
                  setAssignForm((current) => ({
                    ...current,
                    award_id: event.target.value,
                    task_id: "",
                  }))
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
              <label>Task (optional)</label>
              <select
                value={assignForm.task_id}
                onChange={(event) =>
                  setAssignForm((current) => ({ ...current, task_id: event.target.value }))
                }
              >
                <option value="">No task</option>
                {assignTasks.map((task) => (
                  <option key={task.task_id} value={task.task_id}>
                    {task.short_code} — {task.title}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label>Hours / week</label>
              <input
                type="number"
                min="0.01"
                step="0.25"
                value={assignForm.hours_per_week}
                onChange={(event) =>
                  setAssignForm((current) => ({ ...current, hours_per_week: event.target.value }))
                }
              />
            </div>
            <div>
              <label>Effective from</label>
              <input
                type="date"
                value={assignForm.effective_from}
                onChange={(event) =>
                  setAssignForm((current) => ({ ...current, effective_from: event.target.value }))
                }
              />
            </div>
          </div>
          <p>
            <button type="submit">Save assignment</button>
          </p>
        </form>
      </div>

      <div className="card">
        <h2>Assignments</h2>
        <table>
          <thead>
            <tr>
              <th>Person</th>
              <th>Award</th>
              <th>Task</th>
              <th>Hours/week</th>
              <th>From</th>
              <th>To</th>
            </tr>
          </thead>
          <tbody>
            {assignments.map((row) => (
              <tr key={row.assignment_id}>
                <td>{personName[row.person_id] || row.person_id}</td>
                <td>
                  <Link to={`/awards/${row.award_id}`}>
                    {awardCode[row.award_id] || `#${row.award_id}`}
                  </Link>
                </td>
                <td>{row.task_id ? taskCode[row.task_id] || row.task_id : "—"}</td>
                <td>{row.hours_per_week}</td>
                <td>{row.effective_from}</td>
                <td>{row.effective_to || "open"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
