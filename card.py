"""Builds the insight card (the JSON the transcription app draws at the bottom of its page).

Contract (cia-extension/1): only `heading` is required. Optional: `note`, up to 6 `stats`,
up to 40 `flags` (level attention / info / good, optional `at` seconds and `speaker`),
one `series` (line or bar chart) and one `table` (up to 8 columns, 200 rows).
Send data only: no HTML, Markdown or colours. The app chooses the colours.
"""
from __future__ import annotations

import config
from analysis import Analysis


def mmss(seconds: float) -> str:
    s = max(0, int(round(seconds)))
    return f"{s // 60}:{s % 60:02d}"


def build_card(a: Analysis) -> dict:
    if not a.speakers or a.total_words == 0:
        return {"heading": config.PLUGIN_NAME, "note": "No speech in this transcript yet, so there is nothing to analyse."}

    lead = a.speakers[0]
    lead_share = lead.talk_s / a.total_talk_s if a.total_talk_s else 0.0
    overall_wpm = 60.0 * a.total_words / a.total_talk_s if a.total_talk_s else 0.0
    total_fillers = sum(s.fillers for s in a.speakers)
    total_questions = sum(s.questions for s in a.speakers)

    note = (f"{len(a.speakers)} speaker{'s' if len(a.speakers) != 1 else ''} over {mmss(a.duration_s)}. "
            f"The most active one spoke for {mmss(lead.talk_s)} ({lead_share:.0%} of all speech)")
    note += f"; the top topic words are {', '.join(k for k, _ in a.keywords[:3])}." if a.keywords else "."

    stats = [
        {"name": "Speaking pace", "value": f"{overall_wpm:.0f} wpm", "hint": "Words per minute while speaking"},
        {"name": "Longest turn", "value": mmss(a.longest_turn["end"] - a.longest_turn["start"]),
         "hint": f"Starts at {mmss(a.longest_turn['start'])}"},
        {"name": "Silence", "value": f"{a.silence_share:.0%}", "hint": "Share of the recording with no speech"},
        {"name": "Questions asked", "value": total_questions},
        {"name": "Filler words", "value": total_fillers, "hint": "um, uh, like, …"},
        {"name": "Unsure stretches", "value": len(a.unsure_stretches), "hint": "Worth re-listening"},
    ]

    flags: list[dict] = []
    if len(a.speakers) > 1:
        if lead_share > config.DOMINANCE_SHARE:
            flags.append({"level": "attention", "speaker": lead.speaker,
                          "text": f"One speaker holds {lead_share:.0%} of the talk time."})
        else:
            flags.append({"level": "good", "text": "Talk time is shared fairly evenly between speakers."})
    if a.interruptions:
        flags.append({"level": "info", "text": f"Speakers talked over each other {a.interruptions} time(s)."})
    for s in a.speakers:
        if s.words >= 20 and s.fillers / s.words > 0.05:
            flags.append({"level": "info", "speaker": s.speaker,
                          "text": f"Uses many filler words: {s.fillers} ({s.fillers / s.words:.0%} of their words)."})
        if s.wpm > 190 and s.words >= 20:
            flags.append({"level": "info", "speaker": s.speaker, "text": f"Speaks fast ({s.wpm:.0f} words per minute)."})
    for u in a.unsure_stretches[:8]:
        flags.append({"level": "attention", "at": u["at"], "speaker": u["speaker"],
                      "text": f"{u['count']} low-confidence words close together (“{u['words']}”). Worth re-listening."})
    if not a.unsure_stretches:
        flags.append({"level": "good", "text": "No clusters of low-confidence words. The transcript looks reliable."})

    card = {
        "heading": config.PLUGIN_NAME,
        "note": note[:600],
        "stats": stats[:6],
        "flags": flags[:40],
        "table": {
            "columns": ["Speaker", "Talk time", "Share", "Turns", "Words/min", "Fillers", "Avg confidence"],
            "rows": [
                [s.speaker, mmss(s.talk_s), f"{(s.talk_s / a.total_talk_s if a.total_talk_s else 0):.0%}",
                 s.turns, round(s.wpm), s.fillers, f"{s.mean_conf:.0%}"]
                for s in a.speakers
            ][:200],
        },
    }
    if a.words_per_window:
        card["series"] = {
            "title": f"Words spoken per {config.WINDOW_S:.0f}-second window",
            "kind": "bar",
            "x_label": "Time (seconds)",
            "y_label": "Words",
            "points": a.words_per_window[:1000],
        }
    return card
