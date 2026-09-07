import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, formatCents, mondayOnOrBefore, parseDollarsToCents, todayIso } from "../api.js";

const emptyPersonForm = {
  display_name: "",
  email: "",
  hire_date: "",
  labor_category: "",
  create_login: true,
  username: "",
  password: "",
  role_code: "employee",
  rate_kind: "hourly",
  hourly_dollars: "",
  salary_dollars: "",
  hours_per_year: "2080",
  rate_effective_from: todayIso(),
};

export default function People() {
  const [weekStart, setWeekStart] = useState(() => mondayOnOrBefore(todayIso()));
  const [people, setPeople] = useState([]);
  const [awards, setAwards] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [rows, setRows] = useState([]);
  const [assignments, setAssignments] = useState([]);
  const [ratesByPerson, setRatesByPerson] = useState({});
  const [capacityByPerson, setCapacityByPerson] = useState({});
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [personForm, setPersonForm] = useState(emptyPersonForm);
  const [rateForm, setRateForm] = useState({
    person_id: "",
    rate_kind: "hourly",
    hourly_dollars: "",
    salary_dollars: "",
    hours_per_year: "2080",
    effective_from: todayIso(),
  });
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
  const [loginForm, setLoginForm] = useState({
    person_id: "",
    role_code: "employee",
    is_active: true,
    new_password: "",
  });
  const [factsForm, setFactsForm] = useState({
    person_id: "",
    display_name: "",
    email: "",
    hire_date: "",
    term_date: "",
    labor_category: "",
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
    const rateEntries = await Promise.all(
      personList.map(async (person) => [
        person.person_id,
        await api(`/people/${person.person_id}/rates`),
      ]),
    );
    const capacityEntries = await Promise.all(
      personList.map(async (person) => [
        person.person_id,
        await api(`/people/${person.person_id}/capacity`),
      ]),
    );
    setPeople(personList);
    setRatesByPerson(Object.fromEntries(rateEntries));
    setCapacityByPerson(Object.fromEntries(capacityEntries));
    setAwards(awardList.filter((award) => award.status_code !== "closed"));
    setTasks(taskList);
    setRows(capacity);
    setAssignments(assignList);
    setWeekStart(monday);
    const firstId = personList.length ? String(personList[0].person_id) : "";
    setCapacityForm((current) => ({
      ...current,
      person_id: current.person_id || firstId,
    }));
    setAssignForm((current) => ({
      ...current,
      person_id: current.person_id || firstId,
    }));
    setRateForm((current) => ({
      ...current,
      person_id: current.person_id || firstId,
    }));
    const withLogin = personList.filter((person) => person.username);
    const loginId = loginForm.person_id || (withLogin[0] ? String(withLogin[0].person_id) : "");
    if (loginId) {
      const selected = personList.find((person) => String(person.person_id) === String(loginId));
      setLoginForm((current) => ({
        ...current,
        person_id: loginId,
        role_code: selected?.role_code || "employee",
        is_active: selected?.is_active !== false,
      }));
    }
    const factsId = factsForm.person_id || firstId;
    if (factsId) {
      const selected = personList.find((person) => String(person.person_id) === String(factsId));
      setFactsForm({
        person_id: String(factsId),
        display_name: selected?.display_name || "",
        email: selected?.email || "",
        hire_date: selected?.hire_date || "",
        term_date: selected?.term_date || "",
        labor_category: selected?.labor_category || "",
      });
    }
  }

  useEffect(() => {
    load(weekStart).catch((err) => setError(err.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function openRate(personId) {
    const rates = ratesByPerson[personId] || [];
    const current = [...rates].reverse().find((row) => !row.effective_to) || rates[rates.length - 1];
    return current || null;
  }

  async function addPerson(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    try {
      const body = {
        display_name: personForm.display_name,
        email: personForm.email || null,
        hire_date: personForm.hire_date || null,
        labor_category: personForm.labor_category || null,
      };
      if (personForm.create_login) {
        body.username = personForm.username;
        body.password = personForm.password;
        body.role_code = personForm.role_code;
      }
      const created = await api("/people", { method: "POST", body });
      const personId = created.person_id;
      const rateBody = ratePayload(personForm);
      if (rateBody) {
        await api(`/people/${personId}/rates`, { method: "POST", body: rateBody });
      }
      setPersonForm({ ...emptyPersonForm, rate_effective_from: todayIso() });
      setRateForm((current) => ({ ...current, person_id: String(personId) }));
      setNotice(rateBody ? "Person, login, and base rate saved." : "Person saved.");
      await load(weekStart);
    } catch (err) {
      setError(err.message);
    }
  }

  function ratePayload(form) {
    if (form.rate_kind === "salary") {
      const salary = parseDollarsToCents(form.salary_dollars);
      if (salary === undefined) {
        return null;
      }
      return {
        effective_from: form.rate_effective_from || form.effective_from,
        salary_cents: salary,
        hours_per_year: Number(form.hours_per_year) || 2080,
      };
    }
    const hourly = parseDollarsToCents(form.hourly_dollars);
    if (hourly === undefined) {
      return null;
    }
    return {
      effective_from: form.rate_effective_from || form.effective_from,
      base_rate_cents: hourly,
    };
  }

  async function addRate(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    try {
      const body = ratePayload(rateForm);
      if (!body) {
        setError("Enter an hourly rate or an annual salary.");
        return;
      }
      await api(`/people/${rateForm.person_id}/rates`, { method: "POST", body });
      setRateForm((current) => ({
        ...current,
        hourly_dollars: "",
        salary_dollars: "",
        effective_from: todayIso(),
      }));
      setNotice("Base rate saved.");
      await load(weekStart);
    } catch (err) {
      setError(err.message);
    }
  }

  const logins = people.filter((person) => person.username);
  const selectedLogin = logins.find(
    (person) => String(person.person_id) === String(loginForm.person_id),
  );
  const activeAdminCount = people.filter(
    (person) => person.role_code === "admin" && person.is_active,
  ).length;
  const selectedIsLastAdmin =
    selectedLogin &&
    selectedLogin.role_code === "admin" &&
    selectedLogin.is_active &&
    activeAdminCount <= 1;

  async function saveLogin(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    try {
      await api(`/people/${loginForm.person_id}`, {
        method: "PATCH",
        body: {
          role_code: loginForm.role_code,
          is_active: loginForm.is_active,
        },
      });
      setNotice("Login saved.");
      await load(weekStart);
    } catch (err) {
      setError(err.message);
    }
  }

  async function resetPassword(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    try {
      await api(`/people/${loginForm.person_id}/password`, {
        method: "POST",
        body: { new_password: loginForm.new_password },
      });
      setLoginForm((current) => ({ ...current, new_password: "" }));
      setNotice("Password reset. They must log in with the new password.");
      await load(weekStart);
    } catch (err) {
      setError(err.message);
    }
  }

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

  function endDateFor(from) {
    const today = todayIso();
    return today < from ? from : today;
  }

  function fillFacts(person) {
    setFactsForm({
      person_id: person ? String(person.person_id) : "",
      display_name: person?.display_name || "",
      email: person?.email || "",
      hire_date: person?.hire_date || "",
      term_date: person?.term_date || "",
      labor_category: person?.labor_category || "",
    });
  }

  async function saveFacts(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    try {
      await api(`/people/${factsForm.person_id}`, {
        method: "PATCH",
        body: {
          display_name: factsForm.display_name,
          email: factsForm.email || null,
          hire_date: factsForm.hire_date || null,
          term_date: factsForm.term_date || null,
          labor_category: factsForm.labor_category || null,
        },
      });
      setNotice("Person saved.");
      await load(weekStart);
    } catch (err) {
      setError(err.message);
    }
  }

  async function removePerson(personId) {
    const id = personId ?? factsForm.person_id;
    setError("");
    setNotice("");
    try {
      await api(`/people/${id}`, { method: "DELETE" });
      setNotice("Person removed.");
      if (String(factsForm.person_id) === String(id)) {
        setFactsForm({
          person_id: "",
          display_name: "",
          email: "",
          hire_date: "",
          term_date: "",
          labor_category: "",
        });
      }
      await load(weekStart);
    } catch (err) {
      setError(err.message);
    }
  }

  async function endAssignment(row) {
    setError("");
    setNotice("");
    try {
      await api(`/assignments/${row.assignment_id}`, {
        method: "PATCH",
        body: { effective_to: endDateFor(row.effective_from) },
      });
      setNotice("Assignment ended.");
      await load(weekStart);
    } catch (err) {
      setError(err.message);
    }
  }

  async function removeAssignment(row) {
    setError("");
    setNotice("");
    try {
      await api(`/assignments/${row.assignment_id}`, { method: "DELETE" });
      setNotice("Assignment removed.");
      await load(weekStart);
    } catch (err) {
      setError(err.message);
    }
  }

  async function removeRate(row) {
    setError("");
    setNotice("");
    try {
      await api(`/people/${row.person_id}/rates/${row.person_rate_id}`, { method: "DELETE" });
      setNotice("Base rate removed.");
      await load(weekStart);
    } catch (err) {
      setError(err.message);
    }
  }

  async function removeCapacity(row) {
    setError("");
    setNotice("");
    try {
      await api(`/people/${row.person_id}/capacity/${row.person_capacity_id}`, { method: "DELETE" });
      setNotice("Capacity row removed.");
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
  const allRates = people.flatMap((person) =>
    (ratesByPerson[person.person_id] || []).map((row) => ({
      ...row,
      display_name: person.display_name,
    })),
  );
  const allCapacity = people.flatMap((person) =>
    (capacityByPerson[person.person_id] || []).map((row) => ({
      ...row,
      display_name: person.display_name,
    })),
  );
  const selectedFacts = people.find(
    (person) => String(person.person_id) === String(factsForm.person_id),
  );

  return (
    <>
      <h1>People</h1>
      <p className="muted">
        Delete is on each row. End stops a real assignment. If Delete fails, that row already
        posted or is still in use — deactivate or add a new dated row instead.
      </p>
      {error ? <p className="error">{error}</p> : null}
      {notice ? <p>{notice}</p> : null}

      <div className="card">
        <h2>New person</h2>
        <form onSubmit={addPerson}>
          <div className="row">
            <div>
              <label>Display name</label>
              <input
                required
                value={personForm.display_name}
                onChange={(event) =>
                  setPersonForm((current) => ({ ...current, display_name: event.target.value }))
                }
              />
            </div>
            <div>
              <label>Email (optional)</label>
              <input
                type="email"
                value={personForm.email}
                onChange={(event) =>
                  setPersonForm((current) => ({ ...current, email: event.target.value }))
                }
              />
            </div>
            <div>
              <label>Hire date (optional)</label>
              <input
                type="date"
                value={personForm.hire_date}
                onChange={(event) =>
                  setPersonForm((current) => ({ ...current, hire_date: event.target.value }))
                }
              />
            </div>
            <div>
              <label>Labor category (optional)</label>
              <input
                value={personForm.labor_category}
                onChange={(event) =>
                  setPersonForm((current) => ({ ...current, labor_category: event.target.value }))
                }
              />
            </div>
          </div>
          <p>
            <label>
              <input
                type="checkbox"
                checked={personForm.create_login}
                onChange={(event) =>
                  setPersonForm((current) => ({ ...current, create_login: event.target.checked }))
                }
              />{" "}
              Create a login
            </label>
          </p>
          {personForm.create_login ? (
            <div className="row">
              <div>
                <label>Username</label>
                <input
                  required
                  value={personForm.username}
                  onChange={(event) =>
                    setPersonForm((current) => ({ ...current, username: event.target.value }))
                  }
                />
              </div>
              <div>
                <label>Temporary password</label>
                <input
                  type="password"
                  required
                  value={personForm.password}
                  onChange={(event) =>
                    setPersonForm((current) => ({ ...current, password: event.target.value }))
                  }
                />
              </div>
              <div>
                <label>Role</label>
                <select
                  value={personForm.role_code}
                  onChange={(event) =>
                    setPersonForm((current) => ({ ...current, role_code: event.target.value }))
                  }
                >
                  <option value="employee">employee</option>
                  <option value="admin">admin</option>
                </select>
              </div>
            </div>
          ) : null}
          <h3>Base rate (optional)</h3>
          <p className="muted">Approve cannot post labor dollars until a dated base rate exists.</p>
          <div className="row">
            <div>
              <label>Kind</label>
              <select
                value={personForm.rate_kind}
                onChange={(event) =>
                  setPersonForm((current) => ({ ...current, rate_kind: event.target.value }))
                }
              >
                <option value="hourly">Hourly</option>
                <option value="salary">Annual salary</option>
              </select>
            </div>
            {personForm.rate_kind === "salary" ? (
              <>
                <div>
                  <label>Annual salary ($)</label>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={personForm.salary_dollars}
                    onChange={(event) =>
                      setPersonForm((current) => ({
                        ...current,
                        salary_dollars: event.target.value,
                      }))
                    }
                  />
                </div>
                <div>
                  <label>Hours / year</label>
                  <input
                    type="number"
                    min="1"
                    step="1"
                    value={personForm.hours_per_year}
                    onChange={(event) =>
                      setPersonForm((current) => ({
                        ...current,
                        hours_per_year: event.target.value,
                      }))
                    }
                  />
                </div>
              </>
            ) : (
              <div>
                <label>Hourly rate ($)</label>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={personForm.hourly_dollars}
                  onChange={(event) =>
                    setPersonForm((current) => ({ ...current, hourly_dollars: event.target.value }))
                  }
                />
              </div>
            )}
            <div>
              <label>Rate effective from</label>
              <input
                type="date"
                value={personForm.rate_effective_from}
                onChange={(event) =>
                  setPersonForm((current) => ({
                    ...current,
                    rate_effective_from: event.target.value,
                  }))
                }
              />
            </div>
          </div>
          <p>
            <button type="submit">Save person</button>
          </p>
        </form>
      </div>

      <div className="card">
        <h2>Roster</h2>
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Username</th>
              <th>Role</th>
              <th>Active</th>
              <th>Current hourly</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {people.map((person) => {
              const rate = openRate(person.person_id);
              return (
                <tr key={person.person_id}>
                  <td>{person.display_name}</td>
                  <td>{person.username || "—"}</td>
                  <td>{person.role_code || "—"}</td>
                  <td>
                    {person.username
                      ? person.is_active
                        ? "yes"
                        : "no"
                      : "—"}
                  </td>
                  <td>
                    {rate ? formatCents(rate.base_rate_cents) : "—"}
                    {rate && rate.effective_from ? (
                      <span className="muted"> from {rate.effective_from}</span>
                    ) : null}
                  </td>
                  <td className="actions">
                    <button type="button" className="secondary" onClick={() => fillFacts(person)}>
                      Edit
                    </button>
                    {rate ? (
                      <button type="button" className="secondary" onClick={() => removeRate(rate)}>
                        Delete rate
                      </button>
                    ) : null}
                    <button
                      type="button"
                      className="secondary"
                      onClick={() => removePerson(person.person_id)}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
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
              <th></th>
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
                <td className="actions">
                  {row.effective_to ? null : (
                    <button type="button" className="secondary" onClick={() => endAssignment(row)}>
                      End
                    </button>
                  )}
                  <button type="button" className="secondary" onClick={() => removeAssignment(row)}>
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {assignments.length === 0 ? <p className="muted">No assignments yet.</p> : null}
      </div>

      <div className="card">
        <h2>Person facts</h2>
        <p className="muted">Correct name, email, hire/term, or labor category. Unused people can be deleted.</p>
        {people.length ? (
          <form onSubmit={saveFacts}>
            <div className="row">
              <div>
                <label>Person</label>
                <select
                  value={factsForm.person_id}
                  onChange={(event) => {
                    const selected = people.find(
                      (person) => String(person.person_id) === event.target.value,
                    );
                    fillFacts(selected);
                  }}
                >
                  {people.map((person) => (
                    <option key={person.person_id} value={person.person_id}>
                      {person.display_name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label>Display name</label>
                <input
                  required
                  value={factsForm.display_name}
                  onChange={(event) =>
                    setFactsForm((current) => ({ ...current, display_name: event.target.value }))
                  }
                />
              </div>
              <div>
                <label>Email</label>
                <input
                  type="email"
                  value={factsForm.email}
                  onChange={(event) =>
                    setFactsForm((current) => ({ ...current, email: event.target.value }))
                  }
                />
              </div>
            </div>
            <div className="row">
              <div>
                <label>Hire date</label>
                <input
                  type="date"
                  value={factsForm.hire_date}
                  onChange={(event) =>
                    setFactsForm((current) => ({ ...current, hire_date: event.target.value }))
                  }
                />
              </div>
              <div>
                <label>Term date</label>
                <input
                  type="date"
                  value={factsForm.term_date}
                  onChange={(event) =>
                    setFactsForm((current) => ({ ...current, term_date: event.target.value }))
                  }
                />
              </div>
              <div>
                <label>Labor category</label>
                <input
                  value={factsForm.labor_category}
                  onChange={(event) =>
                    setFactsForm((current) => ({ ...current, labor_category: event.target.value }))
                  }
                />
              </div>
            </div>
            <p>
              <button type="submit">Save person</button>{" "}
              <button type="button" className="secondary" onClick={() => removePerson()}>
                Delete person
              </button>
            </p>
            {selectedFacts && !selectedFacts.can_delete ? (
              <p className="muted">
                Delete will fail if this person has timesheets, charges, or audit history.
                Deactivate the login instead.
              </p>
            ) : null}
          </form>
        ) : (
          <p className="muted">No people yet.</p>
        )}
      </div>

      <div className="card">
        <h2>Login</h2>
        <p className="muted">
          Reset password, change role, or deactivate. You cannot remove the last active admin.
        </p>
        {logins.length ? (
          <>
            <form onSubmit={saveLogin}>
              <div className="row">
                <div>
                  <label>Person</label>
                  <select
                    value={loginForm.person_id}
                    onChange={(event) => {
                      const id = event.target.value;
                      const selected = people.find((person) => String(person.person_id) === id);
                      setLoginForm((current) => ({
                        ...current,
                        person_id: id,
                        role_code: selected?.role_code || "employee",
                        is_active: selected?.is_active !== false,
                      }));
                    }}
                  >
                    {logins.map((person) => (
                      <option key={person.person_id} value={person.person_id}>
                        {person.display_name} ({person.username})
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label>Role</label>
                  <select
                    value={loginForm.role_code}
                    disabled={Boolean(selectedIsLastAdmin)}
                    onChange={(event) =>
                      setLoginForm((current) => ({ ...current, role_code: event.target.value }))
                    }
                  >
                    <option value="employee">employee</option>
                    <option value="admin">admin</option>
                  </select>
                </div>
                <div>
                  <label>Active</label>
                  <select
                    value={loginForm.is_active ? "1" : "0"}
                    disabled={Boolean(selectedIsLastAdmin)}
                    onChange={(event) =>
                      setLoginForm((current) => ({
                        ...current,
                        is_active: event.target.value === "1",
                      }))
                    }
                  >
                    <option value="1">yes</option>
                    <option value="0">no</option>
                  </select>
                </div>
              </div>
              {selectedIsLastAdmin ? (
                <p className="muted">This is the last active admin. Add another admin before changing this login.</p>
              ) : null}
              <p>
                <button type="submit">Save login</button>
              </p>
            </form>
            <form onSubmit={resetPassword}>
              <div className="row">
                <div>
                  <label>New temporary password</label>
                  <input
                    type="password"
                    required
                    value={loginForm.new_password}
                    onChange={(event) =>
                      setLoginForm((current) => ({ ...current, new_password: event.target.value }))
                    }
                  />
                </div>
              </div>
              <p>
                <button type="submit">Reset password</button>
              </p>
            </form>
          </>
        ) : (
          <p className="muted">No logins yet. Create a person with a login above.</p>
        )}
      </div>

      <div className="card">
        <h2>Set base rate</h2>
        <p className="muted">A new row closes the previous open rate. Delete a typo on the row. Posted labor keeps the old row (you will see an error).</p>
        <form onSubmit={addRate}>
          <div className="row">
            <div>
              <label>Person</label>
              <select
                value={rateForm.person_id}
                onChange={(event) =>
                  setRateForm((current) => ({ ...current, person_id: event.target.value }))
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
              <label>Kind</label>
              <select
                value={rateForm.rate_kind}
                onChange={(event) =>
                  setRateForm((current) => ({ ...current, rate_kind: event.target.value }))
                }
              >
                <option value="hourly">Hourly</option>
                <option value="salary">Annual salary</option>
              </select>
            </div>
            {rateForm.rate_kind === "salary" ? (
              <>
                <div>
                  <label>Annual salary ($)</label>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={rateForm.salary_dollars}
                    onChange={(event) =>
                      setRateForm((current) => ({ ...current, salary_dollars: event.target.value }))
                    }
                  />
                </div>
                <div>
                  <label>Hours / year</label>
                  <input
                    type="number"
                    min="1"
                    value={rateForm.hours_per_year}
                    onChange={(event) =>
                      setRateForm((current) => ({ ...current, hours_per_year: event.target.value }))
                    }
                  />
                </div>
              </>
            ) : (
              <div>
                <label>Hourly rate ($)</label>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={rateForm.hourly_dollars}
                  onChange={(event) =>
                    setRateForm((current) => ({ ...current, hourly_dollars: event.target.value }))
                  }
                />
              </div>
            )}
            <div>
              <label>Effective from</label>
              <input
                type="date"
                value={rateForm.effective_from}
                onChange={(event) =>
                  setRateForm((current) => ({ ...current, effective_from: event.target.value }))
                }
              />
            </div>
          </div>
          <p>
            <button type="submit">Save base rate</button>
          </p>
        </form>
        <table>
          <thead>
            <tr>
              <th>Person</th>
              <th>From</th>
              <th>To</th>
              <th>Hourly</th>
              <th>Hours/year</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {allRates.map((row) => (
              <tr key={row.person_rate_id}>
                <td>{row.display_name}</td>
                <td>{row.effective_from}</td>
                <td>{row.effective_to || "open"}</td>
                <td>{formatCents(row.base_rate_cents)}</td>
                <td>{row.hours_per_year || "—"}</td>
                <td className="actions">
                  <button type="button" className="secondary" onClick={() => removeRate(row)}>
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

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
        <table>
          <thead>
            <tr>
              <th>Person</th>
              <th>From</th>
              <th>To</th>
              <th>Hours/week</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {allCapacity.map((row) => (
              <tr key={row.person_capacity_id}>
                <td>{row.display_name}</td>
                <td>{row.effective_from}</td>
                <td>{row.effective_to || "open"}</td>
                <td>{row.hours_per_week}</td>
                <td className="actions">
                  <button type="button" className="secondary" onClick={() => removeCapacity(row)}>
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
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
    </>
  );
}
