/** The ways listeners find out what creek can do: the first-visit welcome, What's new, and the shortcuts. */

import { FormEvent, useEffect, useState } from "react";
import { api, NewsItem } from "../api";
import { player } from "../player";
import { giveKey, useStore } from "../store";
import { SHORTCUTS } from "../util";
import { Headphones, ListPlus, Search, Users } from "./Icons";
import { Modal } from "./Modal";

export function Welcome({ onClose, onSearch }: { onClose: () => void; onSearch: () => void }) {
  const { state } = useStore();
  return (
    <Modal title="The office music lives here" onClose={onClose} className="welcome">
      <p className="lede">
        TAL Master's grid is one stream of music for everyone in the office: the song playing now, then what's up next. Everybody hears the same song at the same moment.
        {state && state.here > 0 && <> Right now <strong>{state.here}</strong> {state.here === 1 ? "person is" : "people are"} listening.</>}
      </p>
      <ul className="tour">
        <li><Search /><div><strong>Search, then play</strong>Type a song name in the sheet's search box (“Search every column”). You'll get matches on the station and on YouTube; pick one to play it next, add it to the queue, or play it now. Press <kbd>/</kbd> anytime.</div></li>
        <li><ListPlus /><div><strong>The queue is everyone's</strong>Drag rows to reorder them (or <kbd>Shift</kbd>+<kbd>↑</kbd>/<kbd>↓</kbd> on a row), slot one in after any song, or take one out. When the queue is empty, the shuffle picks.</div></li>
        <li><Users /><div><strong>Controls are shared</strong>Pause, skip, and the progress bar work for everyone, and others see a short anonymous note. Your volume is just yours.</div></li>
      </ul>
      <div className="dialog-actions">
        <button className="btn" onClick={() => { onClose(); onSearch(); }}>Find a song</button>
        <button className="btn primary" onClick={() => { player.tuneIn(); onClose(); }}><Headphones /> Tune in</button>
      </div>
      <p className="fine">It keeps playing while you work: the bar at the bottom of every page has the controls, and <strong>Up next</strong> brings you back here.
        Press <kbd>?</kbd> for keyboard shortcuts. Prefer the terminal? <code>curl -s http://{location.host}/join | sh</code></p>
    </Modal>
  );
}

/** The station's passcode box. `onLeave` is the way out for someone who came for the rest of the dashboard. */
export function KeyPrompt({ onLeave }: { onLeave: () => void }) {
  const [key, setKey] = useState("");
  const [wrong, setWrong] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setWrong(!(await giveKey(key)));
  };
  return (
    <Modal title="The music station has a key" onClose={onLeave} className="key">
      <form onSubmit={submit}>
        <p className="lede">Ask whoever runs it for the key, or for the link that has it built in.</p>
        <input className="key-input" autoFocus value={key} onChange={(e) => { setKey(e.target.value); setWrong(false); }}
               placeholder="Station key" aria-label="Station key" aria-invalid={wrong} autoComplete="current-password" />
        {wrong && <p className="hint error">That isn't this station's key.</p>}
        <div className="dialog-actions">
          <button className="btn" type="button" onClick={onLeave}>Back to the dashboard</button>
          <button className="btn primary" type="submit" disabled={!key.trim()}>Come in</button>
        </div>
      </form>
    </Modal>
  );
}

export function WhatsNew({ seen, onClose }: { seen: number; onClose: () => void }) {
  const [news, setNews] = useState<NewsItem[] | null>(null);
  useEffect(() => { api.news(0).then((r) => setNews(r.news.slice().reverse())).catch(() => setNews([])); }, []);
  return (
    <Modal title="What's new" onClose={onClose} className="news">
      {news === null ? <p className="muted">Loading…</p> : news.map((n) => (
        <article key={n.n} className={n.n > seen ? "unseen" : ""}>
          <h3>{n.title} {n.n > seen && <span className="badge">new</span>}</h3>
          <time dateTime={n.date}>{new Date(n.date + "T12:00:00").toLocaleDateString(undefined, { day: "numeric", month: "long", year: "numeric" })}</time>
          <ul>{n.lines.map((l) => <li key={l}>{l}</li>)}</ul>
        </article>
      ))}
    </Modal>
  );
}

export function Shortcuts({ onClose }: { onClose: () => void }) {
  return (
    <Modal title="Keyboard shortcuts" onClose={onClose} className="shortcuts">
      {SHORTCUTS.map(([group, keys]) => (
        <section key={group}>
          <h3>{group}</h3>
          <dl>
            {keys.map(([ks, what]) => (
              <div key={what}>
                <dt>{ks.map((k, i) => <span key={k}>{i > 0 && <span className="or">or</span>}<kbd>{k}</kbd></span>)}</dt>
                <dd>{what}</dd>
              </div>
            ))}
          </dl>
        </section>
      ))}
      <p className="fine">In TAL Master's search: <kbd>Enter</kbd> play next · <kbd>Shift</kbd>+<kbd>Enter</kbd> add to the queue · <kbd>Ctrl</kbd>+<kbd>Enter</kbd> play now.
        Your keyboard's media keys and headphone buttons work too.</p>
    </Modal>
  );
}

export function Toasts() {
  const { toasts } = useStore();
  return (
    <div className="toasts" role="status" aria-live="polite">
      {toasts.map((t) => <div key={t.key} className={`toast ${t.tone}`}>{t.text}</div>)}
    </div>
  );
}
