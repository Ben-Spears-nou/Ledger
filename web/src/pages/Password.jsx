import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, clearSession } from "../api.js";

export default function Password() {
  const navigate = useNavigate();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");

  async function onSubmit(event) {
    event.preventDefault();
    setError("");
    if (newPassword !== confirmPassword) {
      setError("New password and confirmation do not match.");
      return;
    }
    try {
      await api("/auth/password", {
        method: "POST",
        body: {
          current_password: currentPassword,
          new_password: newPassword,
        },
      });
      clearSession();
      navigate("/login", { replace: true, state: { notice: "Password changed. Log in with the new password." } });
    } catch (err) {
      setError(err.message || "Could not change password.");
    }
  }

  return (
    <>
      <h1>Change password</h1>
      <p className="muted">
        After you save, you will be signed out and must log in again. Changing your password
        does not use the <code>.env</code> file.
      </p>
      <div className="card" style={{ maxWidth: 420 }}>
        <form onSubmit={onSubmit}>
          <label htmlFor="current-password">Current password</label>
          <input
            id="current-password"
            type="password"
            autoComplete="current-password"
            required
            value={currentPassword}
            onChange={(event) => setCurrentPassword(event.target.value)}
          />
          <label htmlFor="new-password" style={{ marginTop: "0.7rem" }}>
            New password
          </label>
          <input
            id="new-password"
            type="password"
            autoComplete="new-password"
            required
            value={newPassword}
            onChange={(event) => setNewPassword(event.target.value)}
          />
          <label htmlFor="confirm-password" style={{ marginTop: "0.7rem" }}>
            Confirm new password
          </label>
          <input
            id="confirm-password"
            type="password"
            autoComplete="new-password"
            required
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
          />
          {error ? <p className="error">{error}</p> : null}
          <p>
            <button type="submit">Save password</button>
          </p>
        </form>
      </div>
    </>
  );
}
