import { useEffect, useState } from "react";
import { api, todayIso } from "../api.js";
import { awardBarColors } from "../awardColors.js";
import BurnForecast from "../components/BurnForecast.jsx";
import PortfolioForecast from "../components/PortfolioForecast.jsx";

export default function Forecast() {
  const [awards, setAwards] = useState([]);
  const [burns, setBurns] = useState([]);
  const [awardId, setAwardId] = useState("");
  const [asOf, setAsOf] = useState(todayIso());
  const [windowDays, setWindowDays] = useState(90);
  const [error, setError] = useState("");

  async function load(nextAwardId = awardId, nextAsOf = asOf, nextWindow = windowDays) {
    const query = { as_of: nextAsOf, window_days: nextWindow };
    const data = nextAwardId
      ? [await api(`/awards/${nextAwardId}/burn`, { query })]
      : await api("/forecast", { query });
    setBurns(data);
    setAwardId(nextAwardId);
    setAsOf(nextAsOf);
    setWindowDays(nextWindow);
  }

  useEffect(() => {
    Promise.all([api("/awards", { query: { as: "picker" } }), load()])
      .then(([awardList]) => setAwards(awardList))
      .catch((err) => setError(err.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function reload(nextAwardId, nextAsOf, nextWindow) {
    setError("");
    try {
      await load(nextAwardId, nextAsOf, nextWindow);
    } catch (err) {
      setError(err.message);
    }
  }

  const selectedAward = awards.find((award) => String(award.award_id) === awardId);
  const selectedBurn = awardId ? burns[0] : null;

  return (
    <>
      <h1>Burn and runway</h1>
      <p className="muted">
        Forecast actual, planned, committed, and expected funding across the portfolio or for one
        award. All Awards uses one color per project; one award uses one consistent color.
      </p>
      {error ? <p className="error">{error}</p> : null}
      <div className="card gantt-toolbar">
        <div className="row">
          <div>
            <label>Award</label>
            <select
              value={awardId}
              onChange={(event) => reload(event.target.value, asOf, windowDays)}
            >
              <option value="">All awards</option>
              {awards.map((award) => (
                <option key={award.award_id} value={award.award_id}>
                  {award.short_code}: {award.title}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label>Forecast as of</label>
            <input
              type="date"
              value={asOf}
              onChange={(event) => reload(awardId, event.target.value, windowDays)}
            />
          </div>
          <div>
            <label>Projection window</label>
            <select
              value={windowDays}
              onChange={(event) => reload(awardId, asOf, Number(event.target.value))}
            >
              <option value={30}>30 days</option>
              <option value={60}>60 days</option>
              <option value={90}>90 days</option>
            </select>
          </div>
          <div>
            <button type="button" className="secondary" onClick={() => window.print()}>
              Print
            </button>
          </div>
        </div>
      </div>
      <div className="card">
        <h2>{selectedAward ? `${selectedAward.short_code} forecast` : "All Awards forecast"}</h2>
        {selectedBurn ? (
          <BurnForecast
            burn={selectedBurn}
            asOf={asOf}
            onAsOfChange={(value) => reload(awardId, value, windowDays)}
            onWindowSelect={(days) => reload(awardId, asOf, days)}
            color={awardBarColors(0).fill}
            showDateControl={false}
          />
        ) : (
          <PortfolioForecast burns={burns} />
        )}
      </div>
    </>
  );
}
