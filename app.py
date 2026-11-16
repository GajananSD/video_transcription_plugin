"""Conversation Insights: an extension (plugin) for the Video Transcription app.

The transcription app POSTs a transcript event to /insight; we answer with an insight
card that the app shows under "🧩 Extension insights" at the bottom of its page.

Run:  uvicorn app:app --host 0.0.0.0 --port 8300
"""
from __future__ import annotations

import logging
from collections import deque
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

import config
from analysis import analyse
from card import build_card

logging.basicConfig(level=logging.INFO, format="%(asctime)s [plugin] %(message)s")
log = logging.getLogger("plugin")

app = FastAPI(title=f"{config.PLUGIN_NAME} (Video Transcription extension)", version="1.0.0")

# The last events received, so you can see on this laptop that the app is really calling us.
RECENT: deque[dict] = deque(maxlen=20)


@app.post("/insight", summary="Receive a transcript event, answer with an insight card")
async def insight(request: Request) -> dict:
    event = await request.json()
    rec = event.get("recording") or {}
    card = build_card(analyse(event))
    RECENT.appendleft({
        "time": datetime.now(timezone.utc).astimezone().strftime("%H:%M:%S"),
        "from": request.client.host if request.client else "?",
        "event": event.get("event", "?"),
        "file": rec.get("filename", "?"),
        "words": len(event.get("words") or []),
        "flags": len(card.get("flags", [])),
    })
    log.info("%s from %s for '%s' (%d words) -> card with %d flags",
             event.get("event"), RECENT[0]["from"], rec.get("filename"), RECENT[0]["words"], RECENT[0]["flags"])
    return card


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "plugin": config.PLUGIN_NAME, "events_received": len(RECENT),
            "last_event": RECENT[0] if RECENT else None}


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def home() -> str:
    """A tiny status page: open http://<this-laptop-ip>:8300/ to watch events arrive."""
    rows = "".join(
        f"<tr><td>{e['time']}</td><td>{e['from']}</td><td>{e['event']}</td><td>{_esc(e['file'])}</td>"
        f"<td>{e['words']}</td><td>{e['flags']}</td></tr>" for e in RECENT
    ) or '<tr><td colspan="6">No events yet. Connect this plugin in the app\'s 🧩 Extensions tab.</td></tr>'
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="refresh" content="5">
<title>{config.PLUGIN_NAME}</title>
<style>body{{font-family:system-ui,sans-serif;margin:2rem;max-width:900px;background:#fff;color:#111}}
@media (prefers-color-scheme:dark){{body{{background:#161616;color:#eee}}}}
table{{border-collapse:collapse;width:100%}}td,th{{border-bottom:1px solid #8884;padding:.4rem;text-align:left}}
code{{background:#8882;padding:.1rem .3rem;border-radius:4px}}</style></head><body>
<h1>● {config.PLUGIN_NAME} is running</h1>
<p>Endpoint for the transcription app: <code>http://&lt;this-laptop-ip&gt;:{config.PORT}/insight</code>.
This page refreshes every 5 seconds.</p>
<h2>Events received</h2><table><tr><th>Time</th><th>From</th><th>Event</th><th>File</th><th>Words</th><th>Flags</th></tr>
{rows}</table></body></html>"""


def _esc(s: str) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
