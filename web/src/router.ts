/** Which page of the dashboard is showing. Lives in the URL's hash, so the station serves one page at `/`
 * and Back, Forward, reload and shared links all just work. The music lives in the TAL Master sheet,
 * so the URL never says "music". Covered by router.test.ts. */

import { useSyncExternalStore } from "react";

export type AdminTab = "users" | "log";

/** The report whose grid is the office's music (TAL Master): pages/MusicSheet.tsx draws it, not pages/Report.tsx. */
export const MUSIC_SHEET = 1;

export type Route =
  | { page: "overview" }
  | { page: "report"; id: number }
  | { page: "admin"; tab: AdminTab };

export function parseRoute(hash: string): Route {
  const [page, arg] = hash.replace(/^#\/?/, "").split("/");
  if (page === "reports" && /^\d+$/.test(arg ?? "")) return { page: "report", id: Number(arg) };
  if (page === "admin") return { page: "admin", tab: arg === "log" ? "log" : "users" };
  return { page: "overview" };
}

export function href(r: Route): string {
  switch (r.page) {
    case "overview": return "#/";
    case "report": return `#/reports/${r.id}`;
    case "admin": return r.tab === "users" ? "#/admin" : `#/admin/${r.tab}`;
  }
}

export function go(r: Route) {
  location.hash = href(r);
}

const subscribe = (f: () => void) => (window.addEventListener("hashchange", f), () => window.removeEventListener("hashchange", f));

export function useRoute(): Route {
  const hash = useSyncExternalStore(subscribe, () => location.hash);
  return parseRoute(hash);
}
