let csrfToken = sessionStorage.getItem("csrf_token") || "";

export function setCsrfToken(token) {
  csrfToken = token || "";
  if (csrfToken) {
    sessionStorage.setItem("csrf_token", csrfToken);
  } else {
    sessionStorage.removeItem("csrf_token");
  }
}

export function createIdempotencyKey(prefix = "web") {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;
}

export async function apiFetch(path, options = {}) {
  const method = options.method || "GET";
  const headers = new Headers(options.headers || {});
  if (!(options.body instanceof FormData) && !headers.has("Content-Type") && method !== "GET") {
    headers.set("Content-Type", "application/json");
  }
  if (method !== "GET" && csrfToken) {
    headers.set("X-CSRF-Token", csrfToken);
  }
  const response = await fetch(path, {
    ...options,
    method,
    credentials: "include",
    headers,
  });
  const isJson = response.headers.get("content-type")?.includes("application/json");
  const payload = isJson ? await response.json() : null;
  if (!response.ok) {
    const fallbackMessage = response.status === 413 ? "上传文件过大，请压缩后重试（当前上限 64MB）" : "请求失败";
    const error = new Error(payload?.message || fallbackMessage);
    error.code = payload?.code || "REQUEST_FAILED";
    error.details = payload?.details || [];
    error.requestId = payload?.request_id || "";
    throw error;
  }
  return payload;
}
