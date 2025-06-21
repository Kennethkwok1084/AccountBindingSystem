import { describe, it, expect, vi } from "vitest";
import { fetchLogs, exportLogs, importLogs } from "./logs";

describe("fetchLogs", () => {
  it("calls backend", async () => {
    const json = vi.fn().mockResolvedValue({ total: 0, items: [] });
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve({ ok: true, json })),
    );
    const data = await fetchLogs({ page: 1 });
    expect(fetch).toHaveBeenCalledWith("/api/logs?page=1");
    expect(data.total).toBe(0);
    vi.unstubAllGlobals();
  });
});

describe("exportLogs", () => {
  it("opens window", () => {
    const open = vi.fn();
    vi.stubGlobal("window", { open });
    exportLogs();
    expect(open).toHaveBeenCalledWith("/api/export/logs", "_blank");
    vi.unstubAllGlobals();
  });
});

describe("importLogs", () => {
  it("posts file", async () => {
    const json = vi.fn().mockResolvedValue({ imported: 2 });
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve({ ok: true, json })),
    );
    const blob = new Blob(["x"]);
    blob.name = "log.xlsx";
    const count = await importLogs(blob);
    expect(count).toBe(2);
    vi.unstubAllGlobals();
  });
});
