import { NavLink, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { useState } from "react";
import { api, clearSession, getToken, getUser } from "./api.js";
import Alerts from "./pages/Alerts.jsx";
import Approvals from "./pages/Approvals.jsx";
import Audit from "./pages/Audit.jsx";
import Award from "./pages/Award.jsx";
import AwardNew from "./pages/AwardNew.jsx";
import Compliance from "./pages/Compliance.jsx";
import Home from "./pages/Home.jsx";
import Instruments from "./pages/Instruments.jsx";
import Login from "./pages/Login.jsx";
import MyWeek from "./pages/MyWeek.jsx";
import Password from "./pages/Password.jsx";
import People from "./pages/People.jsx";
import Portfolio from "./pages/Portfolio.jsx";
import Staffing from "./pages/Staffing.jsx";

function RequireAuth({ children }) {
  if (!getToken()) {
    return <Navigate to="/login" replace />;
  }
  return children;
}

function RequireAdmin({ children }) {
  const user = getUser();
  if (!getToken()) {
    return <Navigate to="/login" replace />;
  }
  if (!user || user.role_code !== "admin") {
    return <Navigate to="/me/week" replace />;
  }
  return children;
}

function Shell({ children }) {
  const navigate = useNavigate();
  const user = getUser();
  const isAdmin = user && user.role_code === "admin";
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState([]);
  const [searchError, setSearchError] = useState("");

  function logout() {
    clearSession();
    navigate("/login");
  }

  async function onSearch(event) {
    event.preventDefault();
    setSearchError("");
    if (!query.trim()) {
      setHits([]);
      return;
    }
    try {
      const data = await api("/search", { query: { q: query.trim() } });
      setHits(data.hits || []);
    } catch (err) {
      setSearchError(err.message);
      setHits([]);
    }
  }

  return (
    <>
      <header className="app">
        <strong>Ledger</strong>
        <nav>
          {isAdmin ? <NavLink to="/home">Home</NavLink> : null}
          <NavLink to="/me/week">My week</NavLink>
          <NavLink to="/me/password">Password</NavLink>
          {isAdmin ? <NavLink to="/approvals">Approvals</NavLink> : null}
          {isAdmin ? <NavLink to="/portfolio">Awards</NavLink> : null}
          {isAdmin ? <NavLink to="/staffing">Staffing</NavLink> : null}
          {isAdmin ? <NavLink to="/people">People</NavLink> : null}
          {isAdmin ? <NavLink to="/instruments">Instruments</NavLink> : null}
          {isAdmin ? <NavLink to="/compliance">Compliance</NavLink> : null}
          {isAdmin ? <NavLink to="/alerts">Alerts</NavLink> : null}
          {isAdmin ? <NavLink to="/audit">Audit</NavLink> : null}
        </nav>
        <span>
          {isAdmin ? (
            <form className="header-search" onSubmit={onSearch}>
              <input
                aria-label="Search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search"
              />
              <button type="submit">Find</button>
            </form>
          ) : null}{" "}
          {user ? user.display_name : ""}{" "}
          <button type="button" className="secondary" onClick={logout}>
            Log out
          </button>
        </span>
      </header>
      {searchError ? <p className="error">{searchError}</p> : null}
      {hits.length ? (
        <div className="card search-hits">
          <h2>Search</h2>
          <ul>
            {hits.map((hit) => (
              <li key={`${hit.kind}-${hit.id}`}>
                <NavLink to={hit.href} onClick={() => setHits([])}>
                  {hit.kind}: {hit.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      <main>{children}</main>
    </>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/home"
        element={
          <RequireAdmin>
            <Shell>
              <Home />
            </Shell>
          </RequireAdmin>
        }
      />
      <Route
        path="/me/week"
        element={
          <RequireAuth>
            <Shell>
              <MyWeek />
            </Shell>
          </RequireAuth>
        }
      />
      <Route
        path="/me/password"
        element={
          <RequireAuth>
            <Shell>
              <Password />
            </Shell>
          </RequireAuth>
        }
      />
      <Route
        path="/approvals"
        element={
          <RequireAdmin>
            <Shell>
              <Approvals />
            </Shell>
          </RequireAdmin>
        }
      />
      <Route
        path="/portfolio"
        element={
          <RequireAdmin>
            <Shell>
              <Portfolio />
            </Shell>
          </RequireAdmin>
        }
      />
      <Route
        path="/staffing"
        element={
          <RequireAdmin>
            <Shell>
              <Staffing />
            </Shell>
          </RequireAdmin>
        }
      />
      <Route
        path="/people"
        element={
          <RequireAdmin>
            <Shell>
              <People />
            </Shell>
          </RequireAdmin>
        }
      />
      <Route
        path="/instruments"
        element={
          <RequireAdmin>
            <Shell>
              <Instruments />
            </Shell>
          </RequireAdmin>
        }
      />
      <Route
        path="/compliance"
        element={
          <RequireAdmin>
            <Shell>
              <Compliance />
            </Shell>
          </RequireAdmin>
        }
      />
      <Route
        path="/alerts"
        element={
          <RequireAdmin>
            <Shell>
              <Alerts />
            </Shell>
          </RequireAdmin>
        }
      />
      <Route
        path="/audit"
        element={
          <RequireAdmin>
            <Shell>
              <Audit />
            </Shell>
          </RequireAdmin>
        }
      />
      <Route
        path="/awards/new"
        element={
          <RequireAdmin>
            <Shell>
              <AwardNew />
            </Shell>
          </RequireAdmin>
        }
      />
      <Route
        path="/awards/:id"
        element={
          <RequireAdmin>
            <Shell>
              <Award />
            </Shell>
          </RequireAdmin>
        }
      />
      <Route path="/" element={<Navigate to="/me/week" replace />} />
      <Route path="*" element={<Navigate to="/me/week" replace />} />
    </Routes>
  );
}
