"""The analysis: turns a transcript event into plain numbers and findings.

No machine-learning libraries are needed: everything is counted from the word
timings, speakers and confidence scores the transcription app sends us.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

import config

FILLERS = {"um", "uh", "erm", "er", "hmm", "mm", "uhm", "ah", "like", "basically", "actually", "literally"}
STOPWORDS = set("""
a an the and or but if so of to in on at for with from by as is are was were be been being it its this that these
those i you he she we they me him her us them my your his our their what which who whom when where why how not no yes
do does did done have has had will would can could should shall may might must just very really also then than there
here about into over out up down off again more most some any all each other such only own same too s t don ok okay
oh well yeah gonna get got go going know think one two lot thing things let let's i'm you're it's that's we're
""".split()) | FILLERS


def clean(word: str) -> str:
    return re.sub(r"[^\w'-]", "", word.lower()).strip("-'")


@dataclass
class SpeakerStats:
    speaker: str
    talk_s: float = 0.0
    turns: int = 0
    words: int = 0
    fillers: int = 0
    questions: int = 0
    conf_sum: float = 0.0

    @property
    def wpm(self) -> float:
        return 60.0 * self.words / self.talk_s if self.talk_s > 0 else 0.0

    @property
    def mean_conf(self) -> float:
        return self.conf_sum / self.words if self.words else 0.0


@dataclass
class Analysis:
    speakers: list[SpeakerStats]
    total_talk_s: float
    duration_s: float
    total_words: int
    longest_turn: dict | None
    unsure_stretches: list[dict] = field(default_factory=list)
    keywords: list[tuple[str, int]] = field(default_factory=list)
    words_per_window: list[dict] = field(default_factory=list)
    interruptions: int = 0

    @property
    def silence_share(self) -> float:
        return max(0.0, 1.0 - self.total_talk_s / self.duration_s) if self.duration_s > 0 else 0.0


def analyse(event: dict) -> Analysis:
    turns = event.get("turns") or []
    words = event.get("words") or []
    duration = float((event.get("recording") or {}).get("duration") or 0.0)

    stats: dict[str, SpeakerStats] = {}

    def s(spk: str) -> SpeakerStats:
        return stats.setdefault(spk, SpeakerStats(spk))

    for t in turns:
        st = s(t["speaker"])
        st.talk_s += max(0.0, t["end"] - t["start"])
        st.turns += 1
        st.questions += t.get("text", "").count("?")

    for w in words:
        st = s(w["speaker"])
        st.words += 1
        st.conf_sum += float(w.get("confidence") or 0.0)
        if clean(w["word"]) in FILLERS:
            st.fillers += 1

    # A new turn that starts before the previous speaker's turn ended = talking over each other.
    interruptions = sum(
        1 for a, b in zip(turns, turns[1:]) if b["speaker"] != a["speaker"] and b["start"] < a["end"] - 0.2
    )

    total_talk = sum(x.talk_s for x in stats.values())
    longest = max(turns, key=lambda t: t["end"] - t["start"]) if turns else None

    return Analysis(
        speakers=sorted(stats.values(), key=lambda x: x.talk_s, reverse=True),
        total_talk_s=total_talk,
        duration_s=duration or (max((t["end"] for t in turns), default=0.0)),
        total_words=len(words),
        longest_turn=longest,
        unsure_stretches=_unsure_stretches(words),
        keywords=_keywords(words),
        words_per_window=_per_window(words),
        interruptions=interruptions,
    )


def _unsure_stretches(words: list[dict]) -> list[dict]:
    """Groups of low-confidence words close together: the places worth listening to again."""
    low = [w for w in words if float(w.get("confidence") or 0) < config.LOW_CONFIDENCE]
    out, i = [], 0
    while i < len(low):
        j = i
        while j + 1 < len(low) and low[j + 1]["start"] - low[i]["start"] <= config.UNSURE_WINDOW_S:
            j += 1
        if j - i + 1 >= config.UNSURE_MIN_WORDS:
            out.append({"at": round(low[i]["start"], 1), "speaker": low[i]["speaker"], "count": j - i + 1,
                        "words": " ".join(w["word"] for w in low[i:j + 1])[:120]})
            i = j + 1
        else:
            i += 1
    return out


def _keywords(words: list[dict], n: int = 8) -> list[tuple[str, int]]:
    counts = Counter(c for c in (clean(w["word"]) for w in words) if len(c) > 2 and c not in STOPWORDS
                     and not c.isdigit())
    return [(k, v) for k, v in counts.most_common(n) if v > 1]


def _per_window(words: list[dict]) -> list[dict]:
    buckets: dict[tuple[float, str], int] = defaultdict(int)
    for w in words:
        buckets[(int(w["start"] // config.WINDOW_S) * config.WINDOW_S, w["speaker"])] += 1
    return [{"x": x, "y": y, "group": spk} for (x, spk), y in sorted(buckets.items())]
