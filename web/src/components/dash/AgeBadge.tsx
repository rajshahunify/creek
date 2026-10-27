import { useNow } from "../../hooks";
import { relativeAge } from "../../dashboard/table";
import { Clock } from "../Icons";

/** "Data as of 14:32 · 2 h ago", turning amber once the snapshot is over an hour old (as on the AB dashboard). */
export function AgeBadge({ at }: { at: string | null }) {
  useNow(30_000);
  if (!at) return null;
  const t = new Date(at);
  const old = Date.now() - t.getTime() > 3_600_000;
  return (
    <span className={`age ${old ? "old" : ""}`} title={old ? "Over an hour old: refresh for the latest" : t.toLocaleString()}>
      <Clock /> Data as of {t.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })} · {relativeAge(Date.now() - t.getTime())}
    </span>
  );
}
