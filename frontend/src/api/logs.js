export async function fetchLogs(params = {}) {
  const qs = new URLSearchParams(params).toString();
  const resp = await fetch(`/api/logs?${qs}`);
  if (!resp.ok) {
    throw new Error("failed");
  }
  return await resp.json();
}

export function exportLogs() {
  window.open("/api/export/logs", "_blank");
}
