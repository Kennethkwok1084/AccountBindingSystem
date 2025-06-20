import { describe, it, expect, vi } from "vitest";
import {
  fetchAccounts,
  bindAccount,
  importAccounts,
  exportAccounts,
  triggerAutoRelease,
} from "./accounts";

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

describe("bindAccount", () => {
  it("posts data", async () => {
    const json = vi.fn().mockResolvedValue({ status: "ok" });
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve({ ok: true, json })),
    );
    await bindAccount({ username: "u", student_id: "s" });
    expect(fetch).toHaveBeenCalledWith(
      "/api/accounts/bind",
      expect.any(Object),
    );
    vi.unstubAllGlobals();
  });
});

describe("importAccounts", () => {
  it("uploads file", async () => {
    const json = vi.fn().mockResolvedValue({ imported: 1 });
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve({ ok: true, json })),
    );
    const blob = new Blob(["a"]);
    blob.name = "a.xlsx";
    const count = await importAccounts(blob);
    expect(count).toBe(1);
    vi.unstubAllGlobals();
  });
});

describe("exportAccounts", () => {
  it("opens window", () => {
    const open = vi.fn();
    vi.stubGlobal("window", { open });
    exportAccounts();
    expect(open).toHaveBeenCalledWith("/api/export/accounts", "_blank");
    vi.unstubAllGlobals();
  });
});

describe("triggerAutoRelease", () => {
  it("posts", async () => {
    const json = vi.fn().mockResolvedValue({ released: 1 });
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve({ ok: true, json })),
    );
    const data = await triggerAutoRelease();
    expect(data.released).toBe(1);
    vi.unstubAllGlobals();
  });
});
