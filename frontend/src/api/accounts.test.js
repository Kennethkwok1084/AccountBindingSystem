import { describe, it, expect, vi } from "vitest";
import { fetchAccounts } from "./accounts";

describe("fetchAccounts", () => {
  it("calls backend", async () => {
    const json = vi.fn().mockResolvedValue({ total: 0, items: [] });
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve({ ok: true, json })),
    );
    const data = await fetchAccounts({ page: 1 });
    expect(fetch).toHaveBeenCalledWith("/api/accounts?page=1");
    expect(data.total).toBe(0);
    vi.unstubAllGlobals();
  });
});
