/** Finding a song: on the station (instant) and on YouTube (a moment later), as one list. A pasted link is a result
 * of its own. Used by the music sheet's search box. */

import { useEffect, useMemo, useState } from "react";
import { api, ApiError, StationHit, YouTubeHit } from "./api";
import { useDebounced } from "./hooks";
import { useStore } from "./store";
import { looksLikeLink, mmss } from "./util";

export interface Result {
  key: string;
  kind: "station" | "youtube" | "link";
  title: string;
  by: string;
  length: string;
  target: { url: string } | { track: number };
  why_not?: string;
}

export function useSongSearch(text: string) {
  const { state } = useStore();
  const [station, setStation] = useState<StationHit[]>([]);
  const [youtube, setYoutube] = useState<YouTubeHit[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const words = text.trim();
  const link = looksLikeLink(words);
  const quick = useDebounced(words, 150);
  const slow = useDebounced(words, 450);
  const accepting = state?.accepting ?? true;

  useEffect(() => {
    if (!quick || looksLikeLink(quick)) return setStation([]);
    const ac = new AbortController();
    api.search(quick, ac.signal).then(setStation).catch(() => {});
    return () => ac.abort();
  }, [quick]);

  useEffect(() => {
    setError("");
    if (slow.length < 2 || looksLikeLink(slow) || !accepting) { setYoutube([]); setBusy(false); return; }
    const ac = new AbortController();
    let retry = 0;
    const go = () => {
      setBusy(true);
      api.youtube(slow, ac.signal)
        .then((hits) => { setYoutube(hits); setBusy(false); })
        .catch((e) => {
          if (e.name === "AbortError") return;
          if (e instanceof ApiError && e.status === 429) { retry = window.setTimeout(go, 1000); return; }   // typing fast
          setBusy(false);
          setError(e instanceof ApiError ? e.message : "YouTube search didn't work");
        });
    };
    go();
    return () => { ac.abort(); clearTimeout(retry); };
  }, [slow, accepting]);

  const results: Result[] = useMemo(() => {
    if (link) return [{ key: "link", kind: "link", title: words, by: "", length: "", target: { url: words } }];
    if (!words) return [];
    return [
      ...station.slice(0, 5).map((h): Result => {
        const [title, ...by] = h.song.split(" - ");
        return { key: `s${h.id}`, kind: "station", title: by.length ? title : h.song, by: by.join(" - "), length: mmss(h.duration), target: { track: h.id } };
      }),
      ...youtube.map((h): Result => ({
        key: `y${h.vid}`, kind: "youtube", title: h.title, by: h.channel,
        length: h.duration ? mmss(h.duration) : h.live ? "live" : "",
        target: h.on_station !== null ? { track: h.on_station } : { url: h.url },
        why_not: h.why_not,
      })),
    ];
  }, [link, words, station, youtube]);

  /** Still looking: YouTube hasn't answered for what's in the box yet. */
  const waiting = !link && words.length >= 2 && accepting && (busy || slow !== words);
  return { results, busy, waiting, error, accepting, link, words };
}
