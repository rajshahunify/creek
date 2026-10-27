/** The admin area, read-only in the demo: who has an account (and who's waiting), and who exported what. */

import { useEffect, useState } from "react";
import { DataTable } from "../components/dash/DataTable";
import { listExports, listUsers } from "../dashboard/data";
import type { ColumnInfo, ExportEntry, UserRow } from "../dashboard/types";
import { AdminTab, href } from "../router";

const USER_COLS: ColumnInfo[] = [
  { name: "Employee ID", kind: "text" }, { name: "Name", kind: "text" }, { name: "Department", kind: "text" },
  { name: "Role", kind: "text" }, { name: "Status", kind: "text" }, { name: "Since", kind: "date" },
];
const LOG_COLS: ColumnInfo[] = [
  { name: "When", kind: "text" }, { name: "Who", kind: "text" }, { name: "Report", kind: "text" },
  { name: "Rows", kind: "number" }, { name: "Scope", kind: "text" },
];

export function Admin({ tab }: { tab: AdminTab }) {
  const [users, setUsers] = useState<UserRow[] | null>(null);
  const [log, setLog] = useState<ExportEntry[] | null>(null);
  useEffect(() => { listUsers().then(setUsers); listExports().then(setLog); }, []);
  const pending = users?.filter((u) => u.status === "Pending").length ?? 0;

  return (
    <div className="page page-fill">
      <div className="page-bar">
        <div className="page-title">
          <h1>Admin</h1>
          <p>Accounts and exports · demo data, read-only</p>
        </div>
      </div>
      <nav className="tabs" aria-label="Admin sections">
        <a href={href({ page: "admin", tab: "users" })} aria-current={tab === "users" ? "page" : undefined}>
          Users {pending > 0 && <span className="count" title={`${pending} waiting for approval`}>{pending}</span>}
        </a>
        <a href={href({ page: "admin", tab: "log" })} aria-current={tab === "log" ? "page" : undefined}>Export log</a>
      </nav>
      {tab === "users" ? (
        users ? (
          <DataTable label="Users" columns={USER_COLS} pills={["Role", "Status"]} pageSize={25}
                     rows={users.map((u) => [u.emp_id, u.name, u.department, u.role, u.status, u.since])} />
        ) : <Loading />
      ) : log ? (
        <DataTable label="Export log" columns={LOG_COLS} pills={["Scope"]} pageSize={25}
                   rows={log.map((e) => [stamp(e.at), e.who, e.sheet, e.rows, e.scope])} />
      ) : <Loading />}
    </div>
  );
}

/** Local "2026-10-27 14:32": reads plainly and sorts as text. */
const stamp = (iso: string) => {
  const d = new Date(iso), p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
};

const Loading = () => <div className="table-card"><div className="table-loading">{Array.from({ length: 8 }, (_, i) => <span key={i} className="shimmer" />)}</div></div>;
