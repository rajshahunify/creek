/** The AB SMB shell: header, side rail, the page the URL names, and the music bar along the bottom. The music
 * stream belongs to the shell, so it carries on wherever you go; its queue is TAL Master's grid (MusicSheet). */

import { useCallback, useEffect, useState } from "react";
import { Shortcuts, Toasts } from "./components/Dialogs";
import { CommandPalette } from "./components/shell/CommandPalette";
import { MusicBar } from "./components/shell/MusicBar";
import { Rail } from "./components/shell/Rail";
import { Theme, Topbar } from "./components/shell/Topbar";
import { useStored } from "./hooks";
import { Admin } from "./pages/Admin";
import { Overview } from "./pages/Overview";
import { MusicSheet, requestSearch } from "./pages/MusicSheet";
import { Report } from "./pages/Report";
import { player } from "./player";
import { go, href, MUSIC_SHEET, useRoute } from "./router";
import { connect, control, seek, seekBy, useStore } from "./store";

type Dialog = "palette" | "help" | null;

export function App() {
  const route = useRoute();
  const [dialog, setDialog] = useState<Dialog>(null);
  const [drawer, setDrawer] = useState(false);
  const [collapsed, setCollapsed] = useStored("abdg.railCollapsed", "0");
  const [stored, setTheme] = useStored("creek.theme", "system");
  const [bar, setBar] = useStored("creek.musicBar", "1");          // the bottom music bar: shown or hidden, per browser
  const toggleBar = () => setBar(bar === "1" ? "0" : "1");
  const theme: Theme = stored === "light" || stored === "dark" ? stored : "system";
  const close = useCallback(() => setDialog(null), []);
  const closeDrawer = useCallback(() => setDrawer(false), []);
  const openMusic = useCallback(() => go({ page: "report", id: MUSIC_SHEET }), []);
  const musicSearch = useCallback(() => { openMusic(); requestSearch(); }, []);
  const onMusic = route.page === "report" && route.id === MUSIC_SHEET;

  useEffect(() => {
    connect();
    if (player.wasTuned) player.tuneIn();          // the browser may insist on a click first: then the button shows
    const oldLink = () => {                        // a link to the old music page: the queue sheet instead
      if (location.hash.startsWith("#/music")) location.replace(href({ page: "report", id: MUSIC_SHEET }));
    };
    oldLink();
    window.addEventListener("hashchange", oldLink);
    return () => window.removeEventListener("hashchange", oldLink);
  }, []);
  useEffect(() => {
    if (theme === "system") delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = theme;
  }, [theme]);
  useEffect(() => { document.querySelector(".content")?.scrollTo(0, 0); }, [route.page, route.page === "report" && route.id]);

  // the tab title stays "AB SMB": song names in window titles end up in activity logs and screen shares

  useMediaSession();

  // the keys that work on every page; TAL Master (the music) adds its own
  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.defaultPrevented) return;
      if ((e.ctrlKey || e.metaKey) && !e.altKey && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setDialog((d) => (d === "palette" ? null : "palette"));
        return;
      }
      if (e.key !== "?" || dialog || (e.target as HTMLElement).closest("input, textarea, select, [contenteditable=true]")) return;
      if (document.querySelector(".backdrop")) return;          // some page's dialog is up
      e.preventDefault();
      setDialog("help");
    };
    window.addEventListener("keydown", down);
    return () => window.removeEventListener("keydown", down);
  }, [dialog]);

  return (
    <div className="shell">
      <Topbar theme={theme} onTheme={setTheme} onMenu={() => setDrawer(true)} onPalette={() => setDialog("palette")}
              onHelp={() => setDialog("help")} musicBar={bar === "1"} onMusicBar={toggleBar} />
      <div className="body">
        <Rail route={route} collapsed={collapsed === "1"} onToggle={() => setCollapsed(collapsed === "1" ? "0" : "1")}
              drawer={drawer} onCloseDrawer={closeDrawer} />
        <main className="content" id="content">
          {route.page === "overview" && <Overview />}
          {onMusic && <MusicSheet blocked={dialog !== null} />}
          {route.page === "report" && !onMusic && <Report key={route.id} id={route.id} />}
          {route.page === "admin" && <Admin tab={route.tab} />}
        </main>
      </div>
      {bar === "1" && <MusicBar here={onMusic} />}

      <Toasts />
      {dialog === "palette" && <CommandPalette onClose={close} onMusicSearch={musicSearch} musicBar={bar === "1"} onMusicBar={toggleBar} />}
      {dialog === "help" && <Shortcuts onClose={close} />}
    </div>
  );
}

/** Media keys, headphone buttons and the lock screen drive the shared controls, from any page. */
function useMediaSession() {
  const { state, at } = useStore();
  useEffect(() => {
    if (!("mediaSession" in navigator)) return;
    const handlers: [MediaSessionAction, MediaSessionActionHandler][] = [
      ["play", () => control("resume")],
      ["pause", () => control("pause")],
      ["nexttrack", () => control("next")],
      ["previoustrack", () => control("prev")],
      ["seekbackward", () => seekBy(-5)],
      ["seekforward", () => seekBy(5)],
      ["seekto", (d) => d.seekTime != null && seek(d.seekTime)],
    ];
    for (const [action, f] of handlers) {
      try { navigator.mediaSession.setActionHandler(action, f); } catch { /* not supported here */ }
    }
  }, []);
  // (no song details for the system's media overlay either: the keys work, the overlay just says "AB SMB")
  useEffect(() => {
    if ("mediaSession" in navigator) navigator.mediaSession.metadata = new MediaMetadata({ title: "AB SMB" });
  }, []);
  useEffect(() => {
    if (!("mediaSession" in navigator) || !state?.dur) return;
    navigator.mediaSession.playbackState = state.paused ? "paused" : "playing";
    try {
      navigator.mediaSession.setPositionState({ duration: state.dur, position: Math.min(state.pos, state.dur), playbackRate: 1 });
    } catch { /* ignore */ }
  }, [state, at]);
}
