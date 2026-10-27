/** Sample data for the demo: the AB demand-gen reports, accounts, users and export log. Seeded, so every
 * reload (and every demo) shows the same numbers; dates count back from today so nothing looks stale. */

import type { Cell, ColumnInfo, ExportEntry, SheetData, SheetSummary, UserRow } from "./types";

/** A small seeded PRNG (mulberry32): same seed, same sequence. */
export function rng(seed: number) {
  let a = seed >>> 0;
  const next = () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  const int = (lo: number, hi: number) => lo + Math.floor(next() * (hi - lo + 1));
  const pick = <T,>(xs: readonly T[]) => xs[Math.floor(next() * xs.length)];
  /** Earlier entries more likely: the head of a list is the common case. */
  const skew = <T,>(xs: readonly T[]) => xs[Math.floor(next() ** 1.6 * xs.length)];
  return { next, int, pick, skew };
}

/** A date `days` before today, as YYYY-MM-DD (the shape the AB backend serialises dates in). */
export function daysAgo(days: number, today = new Date()): string {
  const d = new Date(today.getFullYear(), today.getMonth(), today.getDate() - days);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

const STEMS = ["North", "Blue", "Iron", "Silver", "Bright", "Cedar", "Harbor", "Summit", "Lumen", "Vertex", "Orbit", "Granite",
  "Pioneer", "Atlas", "Willow", "Copper", "Nimbus", "Sable", "Keystone", "Meridian", "Falcon", "Evergreen", "Quartz", "Beacon"];
const ROOTS = ["wind", "peak", "gate", "field", "stone", "bridge", "line", "works", "path", "point", "wave", "crest"];
const KINDS = ["Systems", "Labs", "Health", "Logistics", "Analytics", "Foods", "Energy", "Financial", "Robotics", "Media", "Retail", "Software"];
export const INDUSTRIES = ["Software", "Healthcare", "Manufacturing", "Financial Services", "Retail", "Logistics", "Energy", "Media", "Education"];
export const REGIONS = ["North America", "EMEA", "APAC", "LATAM"];
const TIERS = ["Tier 1", "Tier 2", "Tier 3"];
const OWNERS = ["Priya Nair", "Marcus Lee", "Sofia Alvarez", "Daniel Okafor", "Hannah Weber", "Arjun Mehta", "Chloe Martin", "Kenji Sato"];
const ACCOUNT_STATUS = ["Prospecting", "Engaged", "Nurture", "Opportunity", "Closed Won", "Disqualified"];
const CAMPAIGNS = ["Q4 Webinar Series", "ABM Display – Tier 1", "Cloud Cost Guide", "Partner Co-marketing", "Events: SaaS Summit",
  "Intent Retargeting", "Product Tour Email", "Analyst Report Syndication"];
const CHANNELS = ["Email", "Paid Social", "Display", "Webinar", "Content Syndication", "Events", "Organic"];
const STAGES = ["New", "Working", "MQL", "SQL", "Recycled", "Disqualified"];
const TOPICS = ["Data warehousing", "Zero trust security", "Cloud migration", "Marketing automation", "ERP modernisation",
  "Supply chain visibility", "AI governance", "Customer data platform"];
const SOURCES = ["Bombora", "G2", "TechTarget", "Website visits", "6sense"];

interface Account { name: string; domain: string; industry: string; region: string; employees: number; tier: string; owner: string; status: string; last: number }

function accounts(): Account[] {
  const r = rng(7);
  const seen = new Set<string>();
  const out: Account[] = [];
  while (out.length < 1240) {
    const base = r.pick(STEMS) + r.pick(ROOTS);
    const name = `${base} ${r.pick(KINDS)}`;
    if (seen.has(name)) continue;
    seen.add(name);
    const employees = Math.round(10 ** (1.7 + r.next() * 3.2));
    out.push({
      name, domain: `${base.toLowerCase()}.${r.pick(["com", "com", "io", "co", "net"])}`,
      industry: r.pick(INDUSTRIES), region: r.skew(REGIONS), employees,
      tier: employees > 5000 ? "Tier 1" : employees > 800 ? r.pick(TIERS.slice(0, 2)) : r.pick(TIERS.slice(1)),
      owner: r.pick(OWNERS), status: r.skew(ACCOUNT_STATUS), last: r.int(0, 120),
    });
  }
  return out;
}

type Build = () => { columns: ColumnInfo[]; rows: Cell[][] };

const col = (name: string, kind: ColumnInfo["kind"] = "text", format?: ColumnInfo["format"]): ColumnInfo => ({ name, kind, format });

function sheets(today: Date): { summary: Omit<SheetSummary, "row_count">; build: Build; ageMin: number }[] {
  const acc = accounts();
  return [
    {
      summary: { id: 1, name: "TAL Master", description: "Every account on the target account list, with owner and stage" },
      ageMin: 18,
      build: () => ({
        columns: [col("Account"), col("Domain"), col("Industry"), col("Region"), col("Employees", "number"), col("Tier"),
          col("Owner"), col("Status"), col("Last activity", "date")],
        rows: acc.map((a) => [a.name, a.domain, a.industry, a.region, a.employees, a.tier, a.owner, a.status, daysAgo(a.last, today)]),
      }),
    },
    {
      summary: { id: 2, name: "Account Coverage", description: "Contacts found and engaged per target account" },
      ageMin: 74,
      build: () => {
        const r = rng(11);
        return {
          columns: [col("Account"), col("Region"), col("Tier"), col("Contacts", "number"), col("Engaged", "number"),
            col("Coverage", "number", "pct"), col("Owner")],
          rows: acc.filter((a) => a.tier !== "Tier 3").map((a) => {
            const contacts = r.int(2, a.tier === "Tier 1" ? 60 : 25);
            const engaged = r.int(0, contacts);
            return [a.name, a.region, a.tier, contacts, engaged, Math.round((engaged / contacts) * 1000) / 10, a.owner];
          }),
        };
      },
    },
    {
      summary: { id: 3, name: "Campaign Leads", description: "Leads by campaign and channel over the last 90 days" },
      ageMin: 140,
      build: () => {
        const r = rng(13);
        return {
          columns: [col("Lead ID"), col("Account"), col("Campaign"), col("Channel"), col("Created", "date"), col("Stage"),
            col("Score", "number")],
          rows: Array.from({ length: 2180 }, (_, i) => {
            const a = r.pick(acc);
            return [`L-${(48210 + i).toString()}`, a.name, r.skew(CAMPAIGNS), r.pick(CHANNELS), daysAgo(r.int(0, 90), today),
              r.skew(STAGES), r.int(5, 100)];
          }),
        };
      },
    },
    {
      summary: { id: 4, name: "MQL Weekly", description: "Leads, MQLs and SQLs per region, week by week" },
      ageMin: 9,
      build: () => {
        const rows: Cell[][] = [];
        for (const w of weekly(today)) {
          for (const [region, share] of REGION_SHARE) {
            const leads = Math.round(w.leads * share);
            const mqls = Math.round(w.mqls * share);
            const sqls = Math.round(mqls * (0.28 + (region.length % 4) * 0.03));
            rows.push([w.week, region, leads, mqls, sqls, Math.round((mqls / leads) * 1000) / 10]);
          }
        }
        return {
          columns: [col("Week of", "date"), col("Region"), col("Leads", "number"), col("MQLs", "number"), col("SQLs", "number"),
            col("Lead → MQL", "number", "pct")],
          rows: rows.reverse(),
        };
      },
    },
    {
      summary: { id: 5, name: "Intent Signals", description: "Accounts surging on topics we sell into" },
      ageMin: 260,
      build: () => {
        const r = rng(17);
        return {
          columns: [col("Account"), col("Topic"), col("Surge score", "number"), col("Source"), col("Detected", "date"), col("Owner")],
          rows: Array.from({ length: 860 }, () => {
            const a = r.pick(acc);
            return [a.name, r.pick(TOPICS), r.int(40, 100), r.pick(SOURCES), daysAgo(r.int(0, 30), today), a.owner];
          }),
        };
      },
    },
    {
      summary: { id: 6, name: "Pipeline by Region", description: "Opportunities, pipeline and wins per quarter" },
      ageMin: 35,
      build: () => {
        const r = rng(19);
        const rows: Cell[][] = [];
        const year = today.getFullYear();
        for (const y of [year - 1, year]) {
          for (let q = 1; q <= 4; q++) {
            if (y === year && q > Math.floor(today.getMonth() / 3) + 1) continue;
            for (const [region, share] of REGION_SHARE) {
              const opps = Math.round(r.int(60, 110) * share * 2);
              const pipeline = Math.round(opps * r.int(38, 62) * 1000);
              const won = Math.round(pipeline * (0.18 + r.next() * 0.14));
              rows.push([`${y} Q${q}`, region, opps, pipeline, won, Math.round((won / pipeline) * 1000) / 10]);
            }
          }
        }
        return {
          columns: [col("Quarter"), col("Region"), col("Opportunities", "number"), col("Pipeline", "number", "money"),
            col("Won", "number", "money"), col("Win rate", "number", "pct")],
          rows: rows.reverse(),
        };
      },
    },
  ];
}

const REGION_SHARE: [string, number][] = [["North America", 0.46], ["EMEA", 0.3], ["APAC", 0.17], ["LATAM", 0.07]];

/** Leads and MQLs for the last 26 weeks, oldest first, each labelled by its Monday. */
export function weekly(today = new Date()): { week: string; leads: number; mqls: number }[] {
  const r = rng(23);
  const monday = (today.getDay() + 6) % 7;
  return Array.from({ length: 26 }, (_, i) => {
    const trend = 1 + i * 0.012;
    const leads = Math.round((620 + r.int(-70, 90)) * trend);
    return { week: daysAgo(monday + (25 - i) * 7, today), leads, mqls: Math.round(leads * (0.17 + r.next() * 0.06)) };
  });
}

const FIRST = ["Aisha", "Ben", "Carla", "Dev", "Elena", "Farhan", "Grace", "Hiro", "Isabel", "Jonas", "Kavya", "Liam", "Mei",
  "Nikhil", "Olivia", "Pedro", "Quinn", "Rosa", "Sam", "Tara"];
const LAST = ["Khan", "Fischer", "Rossi", "Patel", "Novak", "Hughes", "Tanaka", "Silva", "Brown", "Iyer", "Dubois", "Kim"];
const DEPTS = ["Demand Gen", "Sales Ops", "Marketing Ops", "Inside Sales", "Leadership"];

export function users(today = new Date()): UserRow[] {
  const r = rng(29);
  return Array.from({ length: 22 }, (_, i) => {
    const status: UserRow["status"] = i < 3 ? "Pending" : i === 20 ? "Disabled" : i === 21 ? "Rejected" : "Active";
    const role: UserRow["role"] = i === 3 || i === 4 ? "Admin" : i % 6 === 0 && status === "Active" ? "Super User" : "User";
    return {
      emp_id: `E0${1400 + i * 7}`, name: `${FIRST[i % FIRST.length]} ${r.pick(LAST)}`, department: r.pick(DEPTS), role, status,
      since: daysAgo(i < 3 ? r.int(0, 2) : r.int(10, 400), today),
    };
  });
}

export function exportLog(names: string[], now = Date.now()): ExportEntry[] {
  const r = rng(31);
  const people = users().filter((u) => u.status === "Active");
  let t = now - r.int(5, 40) * 60_000;
  return Array.from({ length: 48 }, () => {
    const e: ExportEntry = {
      at: new Date(t).toISOString(), who: r.pick(people).name, sheet: r.skew(names), rows: r.int(40, 2200),
      scope: r.next() < 0.6 ? "Current view" : "Whole sheet",
    };
    t -= r.int(20, 9 * 60) * 60_000;
    return e;
  });
}

/** The six reports, built once per page load: summaries for the list, rows on demand. */
export function catalogue(today = new Date()) {
  const all = sheets(today);
  const built = new Map<number, ReturnType<Build>>();
  const data = (id: number) => {
    let b = built.get(id);
    if (!b) built.set(id, (b = all.find((s) => s.summary.id === id)!.build()));
    return b;
  };
  return {
    summaries: (): SheetSummary[] => all.map((s) => ({ ...s.summary, row_count: data(s.summary.id).rows.length })),
    has: (id: number) => all.some((s) => s.summary.id === id),
    ageMin: (id: number) => all.find((s) => s.summary.id === id)?.ageMin ?? 0,
    sheet: (id: number, executedAt: number): SheetData => {
      const s = all.find((x) => x.summary.id === id)!;
      const { columns, rows } = data(id);
      return { sheet_id: id, name: s.summary.name, columns, rows, row_count: rows.length, truncated: false,
               executed_at: new Date(executedAt).toISOString(), duration_ms: 180 + ((id * 137) % 900) };
    },
  };
}
