import { describe, expect, it } from "vitest";
import { href, parseRoute } from "./router";

describe("routes", () => {
  it("reads each page from the hash", () => {
    expect(parseRoute("")).toEqual({ page: "overview" });
    expect(parseRoute("#/")).toEqual({ page: "overview" });
    expect(parseRoute("#/music")).toEqual({ page: "overview" });          // music lives in a sheet, not a page of its own
    expect(parseRoute("#/reports/3")).toEqual({ page: "report", id: 3 });
    expect(parseRoute("#/admin")).toEqual({ page: "admin", tab: "users" });
    expect(parseRoute("#/admin/log")).toEqual({ page: "admin", tab: "log" });
  });

  it("falls back to the overview for anything it doesn't know", () => {
    expect(parseRoute("#/reports/abc")).toEqual({ page: "overview" });
    expect(parseRoute("#/reports")).toEqual({ page: "overview" });
    expect(parseRoute("#/nope")).toEqual({ page: "overview" });
    expect(parseRoute("#/admin/whatever")).toEqual({ page: "admin", tab: "users" });
  });

  it("writes links that read back the same", () => {
    for (const r of [{ page: "overview" }, { page: "report", id: 12 }, { page: "admin", tab: "log" }] as const) {
      expect(parseRoute(href(r))).toEqual(r);
    }
  });
});
