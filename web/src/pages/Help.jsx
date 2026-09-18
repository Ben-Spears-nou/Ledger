import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { api } from "../api.js";
import CollapsibleSection from "../components/CollapsibleSection.jsx";

export default function Help() {
  const [terms, setTerms] = useState([]);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("");
  const location = useLocation();

  useEffect(() => {
    api("/glossary")
      .then(setTerms)
      .catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    const id = location.hash.replace("#", "");
    if (!id) {
      return;
    }
    const node = document.getElementById(id);
    if (node) {
      node.open = true;
      node.scrollIntoView();
    }
  }, [location.hash, terms]);

  const needle = filter.trim().toLowerCase();
  const shown = terms.filter((term) => {
    if (!needle) {
      return true;
    }
    const blob = [term.term_code, term.title, term.definition, ...(term.aliases || [])]
      .join(" ")
      .toLowerCase();
    return blob.includes(needle);
  });

  return (
    <>
      <h1>Help</h1>
      <p className="muted">
        Ledger words and the everyday phrases they match. Search in the header also
        uses this list.
      </p>
      {error ? <p className="error">{error}</p> : null}
      <CollapsibleSection title="Glossary search">
        <label htmlFor="glossary-filter">Look up a phrase</label>
        <input
          id="glossary-filter"
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
          placeholder="remaining, CLIN, Gantt, SOW…"
        />
      </CollapsibleSection>
      {shown.map((term) => (
        <CollapsibleSection title={term.title} id={term.term_code} key={term.term_code}>
          <p>{term.definition}</p>
          {term.aliases?.length ? (
            <p className="muted">Also: {term.aliases.join(", ")}</p>
          ) : null}
          <p>
            <Link to={term.href}>Open {term.href}</Link>
          </p>
        </CollapsibleSection>
      ))}
    </>
  );
}
