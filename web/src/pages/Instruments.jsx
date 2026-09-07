import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, formatCents, todayIso } from "../api.js";

function dollarsToCents(value) {
  return Math.round(Number(value) * 100);
}

function percentToSharePct(value) {
  return Math.round(Number(value) * 100);
}

function emptyShare() {
  return { award_id: "", percent: "" };
}

export default function Instruments() {
  const [rows, setRows] = useState([]);
  const [awards, setAwards] = useState([]);
  const [categories, setCategories] = useState([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [form, setForm] = useState({
    short_code: "",
    title: "",
    dollars: "",
    category_code: "equipment",
    effective_from: todayIso(),
    shares: [emptyShare(), emptyShare()],
  });

  async function load() {
    const [list, awardList, lookups] = await Promise.all([
      api("/instruments"),
      api("/awards", { query: { as: "picker" } }),
      api("/lookups"),
    ]);
    setRows(list);
    const openAwards = awardList.filter((award) => award.status_code !== "closed");
    setAwards(openAwards);
    setCategories(lookups.budget_categories || []);
    setForm((current) => {
      const next = { ...current };
      if (!next.category_code && lookups.budget_categories?.length) {
        next.category_code = lookups.budget_categories[0].category_code;
      }
      if (openAwards.length) {
        next.shares = current.shares.map((share, index) => ({
          ...share,
          award_id: share.award_id || String(openAwards[Math.min(index, openAwards.length - 1)].award_id),
        }));
      }
      return next;
    });
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
  }, []);

  function updateShare(index, field, value) {
    setForm((current) => {
      const shares = current.shares.map((share, i) =>
        i === index ? { ...share, [field]: value } : share
      );
      return { ...current, shares };
    });
  }

  async function createInstrument(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    try {
      await api("/instruments", {
        method: "POST",
        body: {
          short_code: form.short_code,
          title: form.title,
          amount_cents: dollarsToCents(form.dollars),
          category_code: form.category_code,
          effective_from: form.effective_from,
          shares: form.shares
            .filter((share) => share.award_id && share.percent !== "")
            .map((share) => ({
              award_id: Number(share.award_id),
              share_pct: percentToSharePct(share.percent),
            })),
        },
      });
      setNotice("Instrument saved. Open commitments were created for each share.");
      setForm((current) => ({
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

  async function postInstrument(instrumentId) {
    setError("");
    setNotice("");
    try {
      await api(`/instruments/${instrumentId}/post`, { method: "POST" });
      setNotice("Instrument posted.");
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function deleteInstrument(instrumentId) {
    setError("");
    setNotice("");
    try {
      await api(`/instruments/${instrumentId}`, { method: "DELETE" });
      setNotice("Instrument removed.");
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  const awardLabel = Object.fromEntries(
    awards.map((award) => [award.award_id, `${award.short_code} — ${award.title}`])
  );

  return (
    <>
      <h1>Instruments</h1>
      <p className="muted">
        Shared costs split by fixed percents. Creating a row opens a commitment on each
        award. Posting turns those commitments into charges.
      </p>
      {notice ? <p>{notice}</p> : null}
      {error ? <p className="error">{error}</p> : null}

      <div className="card">
        <h2>New split cost</h2>
        <form onSubmit={createInstrument}>
          <div className="row">
            <div>
              <label>Short code</label>
              <input
                value={form.short_code}
                onChange={(event) =>
                  setForm((current) => ({ ...current, short_code: event.target.value }))
                }
              />
            </div>
            <div>
              <label>Title</label>
              <input
                value={form.title}
                onChange={(event) =>
                  setForm((current) => ({ ...current, title: event.target.value }))
                }
              />
            </div>
            <div>
              <label>Amount (USD)</label>
              <input
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
              <label>Category</label>
              <select
                value={form.category_code}
                onChange={(event) =>
                  setForm((current) => ({ ...current, category_code: event.target.value }))
                }
              >
                {categories.map((row) => (
                  <option key={row.category_code} value={row.category_code}>
                    {row.category_code}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label>Effective from</label>
              <input
                type="date"
                value={form.effective_from}
                onChange={(event) =>
                  setForm((current) => ({ ...current, effective_from: event.target.value }))
                }
              />
            </div>
          </div>
          <h3>Shares (must total 100%)</h3>
          {form.shares.map((share, index) => (
            <div className="row" key={`share-${index}`}>
              <div>
                <label>Award</label>
                <select
                  value={share.award_id}
                  onChange={(event) => updateShare(index, "award_id", event.target.value)}
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
                setForm((current) => ({ ...current, shares: [...current.shares, emptyShare()] }))
              }
            >
              Add share
            </button>{" "}
            <button type="submit">Create instrument</button>
          </p>
        </form>
      </div>

      {rows.map((row) => (
        <div className="card" key={row.instrument_id}>
          <h2>
            {row.short_code}{" "}
            <span className="status">{row.status_code}</span>
          </h2>
          <p>
            {row.title} — {formatCents(row.amount_cents)} ({row.category_code})
          </p>
          <table>
            <thead>
              <tr>
                <th>Award</th>
                <th>Share</th>
                <th>Amount</th>
                <th>Commitment</th>
              </tr>
            </thead>
            <tbody>
              {row.shares.map((share) => {
                const commitment = (row.commitments || []).find(
                  (item) => item.award_id === share.award_id
                );
                return (
                  <tr key={share.instrument_share_id}>
                    <td>
                      <Link to={`/awards/${share.award_id}`}>
                        {awardLabel[share.award_id] || `#${share.award_id}`}
                      </Link>
                    </td>
                    <td>{(share.share_pct / 100).toFixed(2)}%</td>
                    <td>{formatCents(share.amount_cents)}</td>
                    <td>{commitment ? commitment.status_code : "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {row.status_code === "open" ? (
            <p>
              <button type="button" onClick={() => postInstrument(row.instrument_id)}>
                Post
              </button>{" "}
              <button
                type="button"
                className="secondary"
                onClick={() => deleteInstrument(row.instrument_id)}
              >
                Delete
              </button>
            </p>
          ) : null}
        </div>
      ))}
    </>
  );
}
