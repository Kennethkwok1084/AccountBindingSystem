import { apiFetch, setCsrfToken } from "./api";

let authModeCache = null;

export async function fetchAuthMode({ force = false } = {}) {
  if (authModeCache && !force) {
    return authModeCache;
  }
  const payload = await apiFetch("/api/v1/auth/mode");
  authModeCache = payload.data;
  return authModeCache;
}

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
  if (payload.data.auth_mode) {
    authModeCache = {
      ...(authModeCache || {}),
      mode: payload.data.auth_mode,
      local_login_enabled: payload.data.auth_mode === "local",
      logout_supported: payload.data.auth_mode === "local",
    };
  }
  return payload.data.user;
}

export async function logout() {
  await apiFetch("/api/v1/auth/logout", { method: "POST" });
  setCsrfToken("");
}
