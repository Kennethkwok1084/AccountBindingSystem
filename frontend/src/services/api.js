let csrfToken = sessionStorage.getItem("csrf_token") || "";
const API_ERROR_EVENT = "abs-api-error";

function emitApiError(detail) {
  if (typeof window === "undefined") {
    return;
  }
  window.dispatchEvent(new CustomEvent(API_ERROR_EVENT, { detail }));
}

export function reportGlobalError(detail = {}) {
  emitApiError({
    source: "manual",
    path: detail.path || "",
    method: detail.method || "",
    status: detail.status || 0,
    code: detail.code || "MANUAL_ERROR",
    message: detail.message || "发生未知错误",
    requestId: detail.requestId || "",
    details: Array.isArray(detail.details) ? detail.details : [],
  });
}

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
  try {
    const response = await fetch(path, {
      ...options,
      method,
      credentials: "include",
      headers,
    });
    const isJson = response.headers.get("content-type")?.includes("application/json");
    let payload = null;
    if (isJson) {
      try {
        payload = await response.json();
      } catch (_error) {
        payload = null;
      }
    }

    if (!response.ok) {
      const fallbackMessage = response.status === 413 ? "上传文件过大，请压缩后重试（当前上限 64MB）" : "请求失败";
      const error = new Error(payload?.message || fallbackMessage);
      error.code = payload?.code || "REQUEST_FAILED";
      error.details = payload?.details || [];
      error.requestId = payload?.request_id || "";
      error.status = response.status;
      emitApiError({
        source: "api",
        path,
        method,
        status: response.status,
        code: error.code,
        message: error.message,
        requestId: error.requestId,
        details: error.details,
      });
      throw error;
    }

    return payload;
  } catch (caught) {
    if (caught && typeof caught === "object" && "code" in caught) {
      throw caught;
    }
    const error = caught instanceof Error ? caught : new Error("网络异常，请稍后重试");
    if (!error.message) {
      error.message = "网络异常，请稍后重试";
    }
    error.code = error.code || "NETWORK_ERROR";
    emitApiError({
      source: "network",
      path,
      method,
      code: error.code,
      message: error.message,
      details: [],
      requestId: "",
    });
    throw error;
  }
}
