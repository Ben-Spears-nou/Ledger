import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  api,
  formatCents,
  parseDollarsToCents,
  todayIso,
} from "../api.js";

function emptyShare() {
  return { award_id: "", percent: "" };
}

function cents(value) {
  return parseDollarsToCents(value) ?? 0;
}

export default function Expenses() {
  const [commitments, setCommitments] = useState([]);
  const [instruments, setInstruments] = useState([]);
  const [awards, setAwards] = useState([]);
  const [categories, setCategories] = useState([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [filters, setFilters] = useState({ award_id: "", category_code: "", status_code: "" });
  const [form, setForm] = useState({
    award_id: "",
    category_code: "odc",
    dollars: "",
    vendor: "",
    description: "",
    effective_date: todayIso(),
    expected_date: "",
    post_immediately: false,
  });
  const [shared, setShared] = useState({
    short_code: "",
    title: "",
    dollars: "",
    category_code: "equipment",
    effective_from: todayIso(),
    shares: [emptyShare(), emptyShare()],
  });

  async function load() {
    const [expenseRows, instrumentRows, awardRows, lookups] = await Promise.all([
      api("/commitments"),
      api("/instruments"),
      api("/awards", { query: { as: "picker" } }),
      api("/lookups"),
    ]);
    const openAwards = awardRows.filter(
      (award) => !["closed", "pipeline"].includes(award.status_code),
    );
    setCommitments(expenseRows);
    setInstruments(instrumentRows);
    setAwards(awardRows);
    setCategories(lookups.budget_categories || []);
    setForm((current) => ({
      ...current,
      award_id: current.award_id || String(openAwards[0]?.award_id || ""),
      category_code:
        current.category_code || lookups.budget_categories?.[0]?.category_code || "",
    }));
    setShared((current) => ({
      ...current,
      shares: current.shares.map((share, index) => ({
        ...share,
        award_id:
          share.award_id ||
          String(openAwards[Math.min(index, Math.max(openAwards.length - 1, 0))]?.award_id || ""),
      })),
    }));
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
  }, []);

  const awardById = useMemo(
    () => Object.fromEntries(awards.map((award) => [award.award_id, award])),
    [awards],
  );
  const openAwards = awards.filter(
    (award) => !["closed", "pipeline"].includes(award.status_code),
  );
  const visible = commitments.filter(
    (row) =>
      (!filters.award_id || String(row.award_id) === filters.award_id) &&
      (!filters.category_code || row.category_code === filters.category_code) &&
      (!filters.status_code || row.status_code === filters.status_code),
  );

  async function createExpense(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    try {
      const created = await api("/purchases", {
        method: "POST",
        body: {
          award_id: Number(form.award_id),
          category_code: form.category_code,
          amount_cents: cents(form.dollars),
          description: form.description || null,
          vendor: form.vendor || null,
          effective_date: form.effective_date,
          expected_date: form.expected_date || null,
        },
      });
      if (form.post_immediately) {
        await api(`/commitments/${created.commitment_id}/post`, { method: "POST" });
      }
      setNotice(
        form.post_immediately
          ? "Expense posted to actuals."
          : "Expense saved as an open commitment.",
      );
      setForm((current) => ({
        ...current,
        dollars: "",
        vendor: "",
        description: "",
        expected_date: "",
        post_immediately: false,
      }));
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function act(path, message) {
    setError("");
    setNotice("");
    try {
      await api(path, { method: "POST" });
      setNotice(message);
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function removeCommitment(row) {
    setError("");
    setNotice("");
    const posted = row.status_code === "posted";
    const shared = row.instrument_id != null;
    const ok = window.confirm(
      shared
        ? "Remove this shared expense from every award? Posted amounts will be reversed."
        : posted
          ? "Remove this posted expense? The charge will be reversed so remaining is restored."
          : "Remove this expense?",
    );
    if (!ok) {
      return;
    }
    try {
      await api(`/commitments/${row.commitment_id}`, { method: "DELETE" });
      setNotice(posted ? "Expense reversed and removed." : "Expense removed.");
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function saveExpectedDate(row, expectedDate) {
    setError("");
    try {
      await api(`/commitments/${row.commitment_id}`, {
        method: "PATCH",
        body: { expected_date: expectedDate || null },
      });
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  function updateShare(index, field, value) {
    setShared((current) => ({
      ...current,
      shares: current.shares.map((share, shareIndex) =>
        shareIndex === index ? { ...share, [field]: value } : share,
      ),
    }));
  }

  async function createShared(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    try {
      await api("/instruments", {
        method: "POST",
        body: {
          short_code: shared.short_code,
          title: shared.title,
          amount_cents: cents(shared.dollars),
          category_code: shared.category_code,
          effective_from: shared.effective_from,
          shares: shared.shares
            .filter((share) => share.award_id && share.percent !== "")
            .map((share) => ({
              award_id: Number(share.award_id),
              share_pct: Math.round(Number(share.percent) * 100),
            })),
        },
      });
      setNotice("Shared expense saved as commitments on each award.");
      setShared((current) => ({
        ...current,
        short_code: "",
        title: "",
        dollars: "",
        shares: current.shares.map((share) => ({ ...share, percent: "" })),
      }));
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function removeInstrument(instrumentId) {
    setError("");
    setNotice("");
    if (
      !window.confirm(
        "Remove this shared expense from every award? Posted amounts will be reversed.",
      )
    ) {
      return;
    }
    try {
      await api(`/instruments/${instrumentId}`, { method: "DELETE" });
      setNotice("Shared expense removed.");
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <>
      <h1>Expenses</h1>
      <p className="muted">
        Record purchases, travel, equipment, subcontracts, and other costs by category.
        Save an expected cost as a commitment or post an incurred cost directly to actuals.
      </p>
      <div className="page-status" aria-live="polite">
        {notice ? <p>{notice}</p> : null}
        {error ? <p className="error">{error}</p> : null}
      </div>

      <div className="card">
        <h2>New expense</h2>
        <form onSubmit={createExpense}>
          <div className="row">
            <div>
              <label>Award</label>
              <select
                required
                value={form.award_id}
                onChange={(event) =>
                  setForm((current) => ({ ...current, award_id: event.target.value }))
                }
              >
                {openAwards.map((award) => (
                  <option key={award.award_id} value={award.award_id}>
                    {award.short_code}: {award.title}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label>Category</label>
              <select
                value={form.category_code}
                onChange={(event) =>
                  setForm((current) => ({ ...current, category_code: event.target.value }))
                }
              >
                {categories.map((row) => (
                  <option key={row.category_code} value={row.category_code}>
                    {row.category_code}: {row.description}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label>Amount (USD)</label>
              <input
                required
                type="number"
                min="0"
                step="0.01"
                value={form.dollars}
                onChange={(event) =>
                  setForm((current) => ({ ...current, dollars: event.target.value }))
                }
              />
            </div>
            <div>
              <label>Vendor / payee</label>
              <input
                value={form.vendor}
                onChange={(event) =>
                  setForm((current) => ({ ...current, vendor: event.target.value }))
                }
              />
            </div>
            <div>
              <label>Expense date</label>
              <input
                type="date"
                value={form.effective_date}
                onChange={(event) =>
                  setForm((current) => ({ ...current, effective_date: event.target.value }))
                }
              />
            </div>
            <div>
              <label>Expected invoice</label>
              <input
                type="date"
                value={form.expected_date}
                onChange={(event) =>
                  setForm((current) => ({ ...current, expected_date: event.target.value }))
                }
              />
            </div>
          </div>
          <label>Description</label>
          <input
            value={form.description}
            onChange={(event) =>
              setForm((current) => ({ ...current, description: event.target.value }))
            }
          />
          <p>
            <label className="inline-check">
              <input
                type="checkbox"
                checked={form.post_immediately}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    post_immediately: event.target.checked,
                  }))
                }
              />{" "}
              Post immediately as an incurred actual
            </label>
          </p>
          <button type="submit">
            {form.post_immediately ? "Post expense" : "Save commitment"}
          </button>
        </form>
      </div>

      <div className="card">
        <h2>Expense register</h2>
        <div className="row">
          <div>
            <label>Award</label>
            <select
              value={filters.award_id}
              onChange={(event) =>
                setFilters((current) => ({ ...current, award_id: event.target.value }))
              }
            >
              <option value="">All awards</option>
              {awards.map((award) => (
                <option key={award.award_id} value={award.award_id}>
                  {award.short_code}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label>Category</label>
            <select
              value={filters.category_code}
              onChange={(event) =>
                setFilters((current) => ({ ...current, category_code: event.target.value }))
              }
            >
              <option value="">All categories</option>
              {categories.map((row) => (
                <option key={row.category_code} value={row.category_code}>
                  {row.category_code}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label>Status</label>
            <select
              value={filters.status_code}
              onChange={(event) =>
                setFilters((current) => ({ ...current, status_code: event.target.value }))
              }
            >
              <option value="">All statuses</option>
              <option value="open">Open</option>
              <option value="posted">Posted</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </div>
        </div>
        <table>
          <thead>
            <tr>
              <th>Award</th>
              <th>Category</th>
              <th>Status</th>
              <th>Amount</th>
              <th>Date</th>
              <th>Expected</th>
              <th>Description</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {visible.map((row) => {
              const award = awardById[row.award_id];
              return (
                <tr key={row.commitment_id}>
                  <td>
                    <Link to={`/awards/${row.award_id}`}>
                      {award?.short_code || `#${row.award_id}`}
                    </Link>
                  </td>
                  <td>{row.category_code}</td>
                  <td><span className="status">{row.status_code}</span></td>
                  <td>{formatCents(row.amount_cents)}</td>
                  <td>{row.effective_date}</td>
                  <td>
                    {row.status_code === "open" ? (
                      <input
                        type="date"
                        defaultValue={row.expected_date || ""}
                        onBlur={(event) => {
                          if (event.target.value !== (row.expected_date || "")) {
                            saveExpectedDate(row, event.target.value);
                          }
                        }}
                      />
                    ) : row.expected_date || "—"}
                  </td>
                  <td>{row.description || row.vendor || "—"}</td>
                  <td className="actions">
                    {row.status_code === "open" ? (
                      <>
                        <button
                          type="button"
                          onClick={() =>
                            act(`/commitments/${row.commitment_id}/post`, "Expense posted.")
                          }
                        >
                          Post
                        </button>
                        <button
                          type="button"
                          className="secondary"
                          onClick={() =>
                            act(`/commitments/${row.commitment_id}/cancel`, "Expense cancelled.")
                          }
                        >
                          Cancel
                        </button>
                      </>
                    ) : null}
                    <button
                      type="button"
                      className="secondary"
                      onClick={() => removeCommitment(row)}
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

      <details className="card collapsible-section">
        <summary><span>Shared expense split across awards</span></summary>
        <div className="collapsible-section-body">
          <p className="muted">
            Use this when one invoice must be allocated across multiple awards by fixed percentages.
          </p>
          <form onSubmit={createShared}>
            <div className="row">
              <div>
                <label>Reference</label>
                <input
                  required
                  value={shared.short_code}
                  onChange={(event) =>
                    setShared((current) => ({ ...current, short_code: event.target.value }))
                  }
                />
              </div>
              <div>
                <label>Title</label>
                <input
                  required
                  value={shared.title}
                  onChange={(event) =>
                    setShared((current) => ({ ...current, title: event.target.value }))
                  }
                />
              </div>
              <div>
                <label>Amount (USD)</label>
                <input
                  required
                  type="number"
                  min="0"
                  step="0.01"
                  value={shared.dollars}
                  onChange={(event) =>
                    setShared((current) => ({ ...current, dollars: event.target.value }))
                  }
                />
              </div>
              <div>
                <label>Category</label>
                <select
                  value={shared.category_code}
                  onChange={(event) =>
                    setShared((current) => ({ ...current, category_code: event.target.value }))
                  }
                >
                  {categories.map((row) => (
                    <option key={row.category_code} value={row.category_code}>
                      {row.category_code}: {row.description}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label>Expense date</label>
                <input
                  type="date"
                  value={shared.effective_from}
                  onChange={(event) =>
                    setShared((current) => ({ ...current, effective_from: event.target.value }))
                  }
                />
              </div>
            </div>
            <h3>Award shares (must total 100%)</h3>
            {shared.shares.map((share, index) => (
              <div className="row" key={`share-${index}`}>
                <div>
                  <label>Award</label>
                  <select
                    value={share.award_id}
                    onChange={(event) => updateShare(index, "award_id", event.target.value)}
                  >
                    {openAwards.map((award) => (
                      <option key={award.award_id} value={award.award_id}>
                        {award.short_code}: {award.title}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label>Share %</label>
                  <input
                    type="number"
                    min="0.01"
                    step="0.01"
                    value={share.percent}
                    onChange={(event) => updateShare(index, "percent", event.target.value)}
                  />
                </div>
              </div>
            ))}
            <p>
              <button
                type="button"
                className="secondary"
                onClick={() =>
                  setShared((current) => ({
                    ...current,
                    shares: [...current.shares, emptyShare()],
                  }))
                }
              >
                Add share
              </button>{" "}
              <button type="submit">Save shared expense</button>
            </p>
          </form>
          {instruments.map((row) => (
            <div className="expense-shared-row" key={row.instrument_id}>
              <div>
                <strong>{row.short_code}: {row.title}</strong>{" "}
                <span className="status">{row.status_code}</span>
                <div className="muted">
                  {formatCents(row.amount_cents)} · {row.category_code}
                </div>
              </div>
              <div className="actions">
                {row.status_code === "open" ? (
                  <button
                    type="button"
                    onClick={() =>
                      act(`/instruments/${row.instrument_id}/post`, "Shared expense posted.")
                    }
                  >
                    Post all
                  </button>
                ) : null}
                <button
                  type="button"
                  className="secondary"
                  onClick={() => removeInstrument(row.instrument_id)}
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      </details>
    </>
  );
}
