import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, formatCents } from "../api.js";

export default function Portfolio() {
  const [awards, setAwards] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/awards")
      .then(setAwards)
      .catch((err) => setError(err.message));
  }, []);

  return (
    <>
      <h1>Awards</h1>
      {error ? <p className="error">{error}</p> : null}
      {awards.map((award) => (
        <div className="card" key={award.award_id}>
          <h2>
            <Link to={`/awards/${award.award_id}`}>{award.short_code}</Link>{" "}
            <span className="status">{award.status_code}</span>
          </h2>
          <p>{award.title}</p>
          {award.remaining ? (
            <p>
              Remaining {formatCents(award.remaining.remaining_approved_cents)} · actual{" "}
              {formatCents(award.remaining.actual_cents)}
            </p>
          ) : null}
        </div>
      ))}
    </>
  );
}
