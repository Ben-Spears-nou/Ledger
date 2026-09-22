import { NavLink, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { useState } from "react";
import { api, clearSession, getToken, getUser } from "./api.js";
import Alerts from "./pages/Alerts.jsx";
import Approvals from "./pages/Approvals.jsx";
import Audit from "./pages/Audit.jsx";
import Award from "./pages/Award.jsx";
import AwardNew from "./pages/AwardNew.jsx";
import Compliance from "./pages/Compliance.jsx";
import Forecast from "./pages/Forecast.jsx";
import Gantt from "./pages/Gantt.jsx";
import Help from "./pages/Help.jsx";
import Home from "./pages/Home.jsx";
import Instruments from "./pages/Instruments.jsx";
import Login from "./pages/Login.jsx";
import MyWeek from "./pages/MyWeek.jsx";
import Password from "./pages/Password.jsx";
import People from "./pages/People.jsx";
import Portfolio from "./pages/Portfolio.jsx";
import Staffing from "./pages/Staffing.jsx";
import WorkGantt from "./pages/WorkGantt.jsx";

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

const NAV_GROUPS = [
  { label: "", items: [{ to: "/home", text: "Home", admin: true }] },
  {
    label: "Me",
    items: [
      { to: "/me/week", text: "My week" },
      { to: "/me/password", text: "Password" },
    ],
  },
  {
    label: "Awards",
    items: [
      { to: "/approvals", text: "Approvals", admin: true },
      { to: "/portfolio", text: "Awards", admin: true },
      { to: "/staffing", text: "Staffing", admin: true },
      { to: "/people", text: "People", admin: true },
      { to: "/instruments", text: "Instruments", admin: true },
    ],
  },
  {
    label: "Charts",
    items: [
      { to: "/forecast", text: "Burn & Runway", admin: true },
      { to: "/gantt", text: "Gantt" },
      { to: "/work-gantt", text: "Work Gantt" },
    ],
  },
  {
    label: "Oversight",
    items: [
      { to: "/compliance", text: "Compliance", admin: true },
      { to: "/alerts", text: "Alerts", admin: true },
      { to: "/audit", text: "Audit", admin: true },
    ],
  },
  { label: "", items: [{ to: "/help", text: "Help" }] },
];

function Shell({ children }) {
  const navigate = useNavigate();
  const user = getUser();
  const isAdmin = user && user.role_code === "admin";
  const groups = NAV_GROUPS.map((group) => ({
    ...group,
    items: group.items.filter((item) => isAdmin || !item.admin),
  })).filter((group) => group.items.length);
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
    <div className="app-shell">
      <aside className="sidebar">
        <strong className="brand">Ledger</strong>
        {isAdmin ? (
          <form className="sidebar-search" onSubmit={onSearch}>
            <input
              aria-label="Search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search"
            />
            <button type="submit">Find</button>
          </form>
        ) : null}
        <nav>
          {groups.map((group, index) => (
            <div className="nav-group" key={group.label || `group-${index}`}>
              {group.label ? <p className="nav-heading">{group.label}</p> : null}
              {group.items.map((item) => (
                <NavLink key={item.to} to={item.to}>
                  {item.text}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <div className="sidebar-foot">
          <p>{user ? user.display_name : ""}</p>
          <button type="button" className="secondary" onClick={logout}>
            Log out
          </button>
        </div>
      </aside>
      <div className="app-main">
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
      </div>
    </div>
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
        path="/forecast"
        element={
          <RequireAdmin>
            <Shell>
              <Forecast />
            </Shell>
          </RequireAdmin>
        }
      />
      <Route
        path="/gantt"
        element={
          <RequireAuth>
            <Shell>
              <Gantt />
            </Shell>
          </RequireAuth>
        }
      />
      <Route
        path="/work-gantt"
        element={
          <RequireAuth>
            <Shell>
              <WorkGantt />
            </Shell>
          </RequireAuth>
        }
      />
      <Route
        path="/help"
        element={
          <RequireAuth>
            <Shell>
              <Help />
            </Shell>
          </RequireAuth>
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
