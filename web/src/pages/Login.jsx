import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { api, getToken, setSession } from "../api.js";

export default function Login() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  if (getToken()) {
    return <Navigate to="/me/week" replace />;
  }

  async function onSubmit(event) {
    event.preventDefault();
    setError("");
    try {
      const data = await api("/auth/login", {
        method: "POST",
        body: { username, password },
      });
      setSession(data.access_token, data.user);
      navigate("/me/week");
    } catch (err) {
      setError(err.message || "login failed");
    }
  }

  return (
    <main>
      <div className="card" style={{ maxWidth: 360, margin: "3rem auto" }}>
        <h1>Ledger</h1>
        <p className="muted">Sign in to log time. Dollars stay on admin screens.</p>
        <form onSubmit={onSubmit}>
          <label htmlFor="username">Username</label>
          <input
            id="username"
            autoComplete="username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
          />
          <label htmlFor="password" style={{ marginTop: "0.7rem" }}>
            Password
          </label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          {error ? <p className="error">{error}</p> : null}
          <p>
            <button type="submit">Log in</button>
          </p>
        </form>
      </div>
    </main>
  );
}
