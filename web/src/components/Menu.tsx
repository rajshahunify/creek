import { useEffect, useRef, useState } from "react";
import { More } from "./Icons";

export interface MenuItem { icon: JSX.Element; text: string; run: () => void; danger?: boolean }

/** A ⋯ button with a small popover menu (Esc or a click elsewhere closes it). */
export function Menu({ label, items, icon = <More /> }: { label: string; items: (MenuItem | false)[]; icon?: JSX.Element }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const away = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    const esc = (e: globalThis.KeyboardEvent) => { if (e.key === "Escape") { e.stopPropagation(); setOpen(false); } };
    document.addEventListener("pointerdown", away);
    document.addEventListener("keydown", esc, true);
    ref.current?.querySelector<HTMLButtonElement>(".menu button")?.focus();
    return () => { document.removeEventListener("pointerdown", away); document.removeEventListener("keydown", esc, true); };
  }, [open]);
  return (
    <div className="menu-wrap" ref={ref}>
      <button className="icon small" aria-label={label} aria-haspopup="menu" aria-expanded={open}
              onClick={(e) => { e.stopPropagation(); setOpen(!open); }}>{icon}</button>
      {open && (
        <div className="menu" role="menu">
          {items.filter((x): x is MenuItem => !!x).map((x) => (
            <button key={x.text} role="menuitem" className={x.danger ? "danger" : ""}
                    onClick={(e) => { e.stopPropagation(); setOpen(false); x.run(); }}>
              {x.icon}<span>{x.text}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
