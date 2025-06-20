export async function fetchAccounts(params = {}) {
  const qs = new URLSearchParams(params).toString();
  const resp = await fetch(`/api/accounts?${qs}`);
  if (!resp.ok) {
    throw new Error("failed");
  }
  return await resp.json();
}
