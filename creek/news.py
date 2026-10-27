"""What's new on the station: the web player's "What's new" panel and the terminal's "new on creek" lines both
read this list. Add an entry (with the next number) whenever listeners get something new to try."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class News:
    n: int
    date: str
    title: str
    lines: tuple[str, ...]


NEWS = [
    News(1, "2026-10-20", "Play next, jumping within a song, emoji everywhere", (
        "a plays a song next, ahead of the queue; e adds one to the end",
        "← / → jump back / ahead 5 s in the song, for everyone",
        "the emoji show up even in the classic Windows console",
    )),
    News(2, "2026-10-27", "A web player, YouTube search, and a queue you can rearrange", (
        "open the station's address in a browser: buttons, a progress bar you can drag, the whole queue",
        "search YouTube by words, then play next, add to the queue, or play now - no more copying links",
        "the queue can be rearranged by anyone: m moves a song, x takes one out (drag and drop on the web)",
        "g jumps to a time in the song; Ctrl+← / → also go back / ahead a song",
        "w shows this list again; ? shows every key",
    )),
    News(3, "2026-10-27", "The music moves into the AB SMB dashboard", (
        "in a browser the station is now the AB SMB dashboard; the bar along the bottom of every page has play/pause, skip and your volume",
        "the queue is the TAL Master sheet: drag a row (or Shift+up/down) to reorder it, and its search box finds songs on the station and YouTube",
        "the music button in the header hides the bar; the music keeps playing",
        "emoji are switched off for now",
    )),
]
NEWS_VERSION = NEWS[-1].n


def news_since(seen: int) -> list[dict]:
    return [asdict(x) for x in NEWS if x.n > seen]
