export async function fetchAccounts(params = {}) {
  const qs = new URLSearchParams(params).toString();
  const resp = await fetch(`/api/accounts?${qs}`);
  if (!resp.ok) {
    throw new Error("failed");
  }
  return await resp.json();
}

export async function bindAccount(data) {
  const resp = await fetch("/api/accounts/bind", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!resp.ok) {
    throw new Error("failed");
  }
  return await resp.json();
}

export async function importAccounts(file) {
  const fd = new FormData();
  fd.append("file", file);
  const resp = await fetch("/api/accounts/import", {
    method: "POST",
    body: fd,
  });
  if (!resp.ok) {
    throw new Error("failed");
  }
  const data = await resp.json();
  return data.imported;
}

export function exportAccounts() {
  window.open("/api/export/accounts", "_blank");
}

export async function triggerAutoRelease(days = 32) {
  const resp = await fetch("/api/auto-release", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ days }),
  });
  if (!resp.ok) {
    throw new Error("failed");
  }
  return await resp.json();
}
