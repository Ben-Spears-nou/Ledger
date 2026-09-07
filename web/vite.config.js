import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const API = "http://127.0.0.1:8000";

function spaPage(req) {
  if (req.headers.accept && req.headers.accept.includes("text/html")) {
    return "/index.html";
  }
}

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/auth": API,
      "/awards": { target: API, bypass: spaPage },
      "/me": { target: API, bypass: spaPage },
      "/approvals": { target: API, bypass: spaPage },
      "/lookups": API,
      "/admin": API,
      "/people": { target: API, bypass: spaPage },
      "/tasks": API,
      "/assignments": API,
      "/capacity": API,
      "/purchases": API,
      "/travel": API,
      "/commitments": API,
      "/instruments": { target: API, bypass: spaPage },
      "/documents": API,
      "/compliance": { target: API, bypass: spaPage },
      "/pipeline": API,
      "/alerts": { target: API, bypass: spaPage },
      "/home": { target: API, bypass: spaPage },
      "/staffing": { target: API, bypass: spaPage },
      "/search": API,
      "/health": API,
    },
  },
});
