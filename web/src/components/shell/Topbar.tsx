/** The header: the menu button (phones), the app's name, the command palette, shortcuts, theme and account. */

import { useEffect, useRef, useState } from "react";
import { go } from "../../router";
import { Command, Dashboard, Keyboard, LogOut, Menu, Monitor, Moon, Music, Shield, Sun } from "../Icons";

export type Theme = "system" | "light" | "dark";
const NEXT: Record<Theme, Theme> = { system: "light", light: "dark", dark: "system" };

export function Topbar({ theme, onTheme, onMenu, onPalette, onHelp, musicBar, onMusicBar }: {
  theme: Theme; onTheme: (t: Theme) => void; onMenu: () => void; onPalette: () => void; onHelp: () => void;
  musicBar: boolean; onMusicBar: () => void;
}) {
  return (
    <header className="topbar glass">
      <button className="tool square only-narrow" onClick={onMenu} aria-label="Open the menu"><Menu /></button>
      <a className="brand" href="#/" aria-label="AB SMB: overview">
        <span className="brand-tile"><Dashboard /></span>
        <strong className="brand-text">AB SMB</strong>
      </a>
      <div className="topbar-right">
        <button className="tool" onClick={onPalette} title="Go to a page or report (Ctrl K)" aria-label="Go to a page or report">
          <Command /> <span className="label">Ctrl K</span>
        </button>
        <button className={`tool square ${musicBar ? "on" : ""}`} onClick={onMusicBar} aria-pressed={musicBar}
                title={musicBar ? "Hide the music bar (the music keeps playing)" : "Show the music bar"} aria-label="Music bar"><Music /></button>
        <button className="tool square hide-narrow" onClick={onHelp} title="Keyboard shortcuts (?)" aria-label="Keyboard shortcuts"><Keyboard /></button>
        <button className="tool square" onClick={() => onTheme(NEXT[theme])}
                title={`Theme: ${theme} (switch to ${NEXT[theme]})`} aria-label={`Theme: ${theme}. Switch to ${NEXT[theme]}`}>
          {theme === "system" ? <Monitor /> : theme === "light" ? <Sun /> : <Moon />}
        </button>
        <AccountMenu />
      </div>
    </header>
  );
}

/** The signed-in account. The demo has no sign-in, so this is a stand-in for the AB dashboard's menu. */
function AccountMenu() {
  const [open, setOpen] = useState(false);
  const wrap = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const away = (e: PointerEvent) => !wrap.current?.contains(e.target as Node) && setOpen(false);
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("pointerdown", away);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("pointerdown", away); document.removeEventListener("keydown", esc); };
  }, [open]);
  return (
    <div className="menu-wrap" ref={wrap}>
      <button className="avatar" onClick={() => setOpen(!open)} aria-haspopup="menu" aria-expanded={open} aria-label="Account">DA</button>
      {open && (
        <div className="menu account" role="menu">
          <div className="account-head">
            <strong>Demo Admin</strong>
            <span className="muted">Demand Gen · <span className="pill info">Admin</span></span>
          </div>
          <button role="menuitem" onClick={() => { setOpen(false); go({ page: "admin", tab: "users" }); }}><Shield /> <span>Admin console</span></button>
          <button role="menuitem" disabled title="The demo has no sign-in"><LogOut /> <span>Sign out</span></button>
        </div>
      )}
    </div>
  );
}
