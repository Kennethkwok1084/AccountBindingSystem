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

export async function importLogs(file) {
  const fd = new FormData();
  fd.append("file", file);
  const resp = await fetch("/api/logs/import", {
    method: "POST",
    body: fd,
  });
  if (!resp.ok) {
    throw new Error("failed");
  }
  const data = await resp.json();
  return data.imported;
}
