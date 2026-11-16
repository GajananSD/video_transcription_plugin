"""Stand-in for the transcription app, for testing the plugin alone (no Whisper, no GPU).

It sends sample_event.json to the plugin, like the real app does, checks that the answer
follows the insight-card contract, and prints a text preview of the card.

Usage:
    python mock_app.py                                   # plugin on this laptop
    python mock_app.py --plugin http://192.168.1.30:8300/insight
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

import config

SYMBOL = {"attention": "▲", "info": "■", "good": "●"}


def check_card(card: dict) -> list[str]:
    """The same limits the real app enforces (a short version of its Pydantic model)."""
    errs = []
    if not isinstance(card.get("heading"), str) or not card["heading"].strip() or len(card["heading"]) > 80:
        errs.append("heading: required text, 1–80 characters")
    if len(card.get("note") or "") > 600:
        errs.append("note: at most 600 characters")
    if len(card.get("stats", [])) > 6:
        errs.append("stats: at most 6")
    if len(card.get("flags", [])) > 40:
        errs.append("flags: at most 40")
    for f in card.get("flags", []):
        if f.get("level", "info") not in SYMBOL:
            errs.append(f"flag level '{f.get('level')}' must be attention, info or good")
        if len(f.get("text", "")) > 300:
            errs.append("flag text: at most 300 characters")
    if (s := card.get("series")) and not (1 <= len(s.get("points", [])) <= 1000):
        errs.append("series.points: 1–1000 points")
    if (t := card.get("table")) and (len(t.get("columns", [])) > 8 or len(t.get("rows", [])) > 200):
        errs.append("table: at most 8 columns and 200 rows")
    return errs


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--plugin", default=f"http://127.0.0.1:{config.PORT}/insight")
    p.add_argument("--event", default=str(Path(__file__).with_name("sample_event.json")))
    args = p.parse_args()

    body = Path(args.event).read_bytes()
    req = urllib.request.Request(args.plugin, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            card = json.loads(r.read())
    except OSError as exc:
        print(f"✗ Could not reach the plugin at {args.plugin}: {exc}")
        return 1

    errs = check_card(card)
    print(f"\n┌─ {card.get('heading')}")
    if card.get("note"):
        print(f"│  {card['note']}")
    for s in card.get("stats", []):
        print(f"│  {s['name']:<18} {s['value']}")
    for f in card.get("flags", []):
        where = " · ".join(x for x in [f"{int(f['at'] // 60)}:{int(f['at'] % 60):02d}" if f.get("at") is not None else "",
                                       f.get("speaker") or ""] if x)
        print(f"│  {SYMBOL.get(f.get('level'), '?')} {f['text']}" + (f"  [{where}]" if where else ""))
    if card.get("table"):
        print("│  " + " | ".join(card["table"]["columns"]))
        for row in card["table"]["rows"]:
            print("│  " + " | ".join(str(c) for c in row))
    print("└─")
    if errs:
        print("✗ The real app would reject this card:\n  - " + "\n  - ".join(errs))
        return 2
    print("✓ Valid insight card. The real app will accept it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
