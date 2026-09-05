import { NavLink, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { clearSession, getToken, getUser } from "./api.js";
import Approvals from "./pages/Approvals.jsx";
import Award from "./pages/Award.jsx";
import Instruments from "./pages/Instruments.jsx";
import Login from "./pages/Login.jsx";
import MyWeek from "./pages/MyWeek.jsx";
import People from "./pages/People.jsx";
import Portfolio from "./pages/Portfolio.jsx";

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

  function logout() {
    clearSession();
    navigate("/login");
  }

  return (
    <>
      <header className="app">
        <strong>Ledger</strong>
        <nav>
          <NavLink to="/me/week">My week</NavLink>
          {isAdmin ? <NavLink to="/approvals">Approvals</NavLink> : null}
          {isAdmin ? <NavLink to="/portfolio">Awards</NavLink> : null}
          {isAdmin ? <NavLink to="/people">People</NavLink> : null}
          {isAdmin ? <NavLink to="/instruments">Instruments</NavLink> : null}
        </nav>
        <span>
          {user ? user.display_name : ""}{" "}
          <button type="button" className="secondary" onClick={logout}>
            Log out
          </button>
        </span>
      </header>
      <main>{children}</main>
    </>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
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
