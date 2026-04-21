import { apiFetch, setCsrfToken } from "./api";

export async function login(username, password) {
  const payload = await apiFetch("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  setCsrfToken(payload.data.csrf_token);
  return payload.data.user;
}

export async function fetchCurrentUser() {
  const payload = await apiFetch("/api/v1/auth/me");
  setCsrfToken(payload.data.csrf_token);
  return payload.data.user;
}

export async function logout() {
  await apiFetch("/api/v1/auth/logout", { method: "POST" });
  setCsrfToken("");
}

