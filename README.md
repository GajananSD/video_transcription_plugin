# Conversation Insights — Video Transcription plugin

A plugin (an "extension") for the **Video Transcription with Confidence Analytics** app.
It runs as its **own small web service**, on the same laptop or on another one. When the app
has a transcript, it POSTs the transcript to this plugin. The plugin answers with an
**insight card**, and the app shows it under **🧩 Extension insights** at the bottom of its page.

## What it shows

| Part | What you see in the app |
|---|---|
| Note | Number of speakers, who talked most, top topic words |
| Stats | Speaking pace (wpm), longest turn, silence %, questions asked, filler words, unsure stretches |
| Flags | ▲ one speaker dominates / clusters of low-confidence words to re-listen (with time + speaker), ■ talking over each other / many fillers / fast speech, ● balanced talk / reliable transcript |
| Chart | Words per 15-second window, per speaker |
| Table | Per speaker: talk time, share, turns, words/min, fillers, average confidence |

## Files

| File | What it does |
|---|---|
| `app.py` | FastAPI service: `POST /insight` (the hook), `GET /health`, and a status page at `/` |
| `analysis.py` | Counts everything from word timings, speakers and confidence (no ML libraries needed) |
| `card.py` | Builds the insight card JSON (the contract the app expects) |
| `register.py` | Connects the plugin to a running app over the network and runs a test (standard library only) |
| `mock_app.py` | Pretends to be the app: sends `sample_event.json` and checks the answer |
| `sample_event.json` | A made-up 2-speaker transcript in the app's exact event format |
| `config.py`, `.env.example` | Settings (port, thresholds) |
| `tests/` | `python -m pytest -q` |

## Setup (on the plugin laptop)

Python 3.10+ only. No GPU, Whisper or the transcription app is needed.

```bash
cd video_transcription_plugin
python3 -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Check it on its own (no app needed):

```bash
uvicorn app:app --host 0.0.0.0 --port 8300     # terminal 1
python mock_app.py                             # terminal 2: prints the card and "✓ Valid insight card"
python -m pytest -q
```

## Demo on two laptops

Both laptops must be on the **same network**. Campus Wi-Fi often blocks laptop-to-laptop traffic.
If the steps below fail, connect both laptops to one **phone hotspot**.

**Laptop A: the transcription app.** Start the backend so other laptops can reach it (`--host 0.0.0.0`):

```bash
cd Video-Transcription-with-Confidence-Analytics/app
source .venv/bin/activate
uvicorn backend.main:app --host 0.0.0.0 --port 8000
streamlit run frontend/streamlit_app.py        # second terminal
```

Find laptop A's IP address: Linux `hostname -I`, macOS `ipconfig getifaddr en0`, Windows `ipconfig` (the IPv4 address).

**Laptop B: this plugin.**

```bash
uvicorn app:app --host 0.0.0.0 --port 8300
python register.py --app http://<laptop-A-ip>:8000      # second terminal
```

`register.py` connects the plugin and then asks the app to send a test event. Expected output:

```
✓ Registered 'Conversation Insights' → http://<laptop-B-ip>:8300/insight
✓ The app reached this plugin and got a valid card in 12 ms.
```

**See it working:**

- On laptop A, open a recording in the app and scroll to the bottom: the **Conversation Insights** card is there. The 🧩 Extensions tab lists the plugin with its laptop-B URL.
- On laptop B, open `http://localhost:8300/` in a browser. The page lists every event received, with laptop A's IP. The terminal also logs each call.
- Correct a turn in the app (✏️ Correct the transcript). The plugin is called again with `transcript.updated`, and its card updates.

**Without the command line:** in the app's **🧩 Extensions** tab, enter the name and `http://<laptop-B-ip>:8300/insight`, then click **Connect** and **Send test**. With this way, laptop A's backend does not need `--host 0.0.0.0`.

To disconnect: `python register.py --app http://<laptop-A-ip>:8000 --remove`, or click **Remove** in the tab.

## Firewall

| OS | Open the port (8300 on laptop B; 8000 on laptop A if you use `register.py`) |
|---|---|
| Fedora | `sudo firewall-cmd --add-port=8300/tcp` (Fedora Workstation already allows 1025–65535) |
| Ubuntu | `sudo ufw allow 8300/tcp` (only needed if ufw is enabled) |
| Windows | Click **Allow** when Windows asks about Python; or `New-NetFirewallRule -DisplayName "plugin 8300" -Direction Inbound -Protocol TCP -LocalPort 8300 -Action Allow` (admin PowerShell) |
| macOS | Click **Allow incoming connections** when asked |

## Troubleshooting

| Message | Cause / fix |
|---|---|
| `register.py`: *Cannot reach the app* | Laptop A's backend isn't started with `--host 0.0.0.0`, port 8000 is blocked, or the laptops are on different networks. Test with `curl http://<laptop-A-ip>:8000/api/v1/health` from laptop B. |
| App: *Could not connect. Is the extension service running?* | The plugin isn't running with `--host 0.0.0.0`, port 8300 is blocked on laptop B, or laptop B's IP changed (re-run `register.py`). Test with `curl http://<laptop-B-ip>:8300/health` from laptop A. |
| App: *No answer within 8 seconds* | Network too slow or blocked. Try a phone hotspot. |
| App: *The answer is not a valid insight card* | Only if you changed `card.py`. Run `python mock_app.py` to see which rule fails. |
| Card shows "From an earlier version of the transcript" | Click **↻ Ask again** in the app. |

## The contract (`cia-extension/1`)

**The app sends** (POST, JSON): `event` (`transcript.ready` or `transcript.updated`), `recording`
(id, filename, duration), `speakers`, `summary`, `turns` (speaker, start, end, text,
avg_confidence) and `words` (word, start, end, speaker, confidence). See `sample_event.json`.

**The plugin answers within 8 s** with a card. Only `heading` is required:

```json
{
  "heading": "Conversation Insights",
  "note": "2 speakers over 0:48 ...",
  "stats":  [{"name": "Speaking pace", "value": "195 wpm", "hint": "optional"}],
  "flags":  [{"level": "attention", "text": "...", "at": 23.4, "speaker": "SPEAKER_01"}],
  "series": {"title": "...", "kind": "bar", "x_label": "Time (seconds)", "y_label": "Words",
             "points": [{"x": 0, "y": 21, "group": "SPEAKER_00"}]},
  "table":  {"columns": ["Speaker", "Talk time"], "rows": [["SPEAKER_00", "0:17"]]}
}
```

The limits are: heading ≤ 80 characters, note ≤ 600, ≤ 6 stats, ≤ 40 flags (`attention` / `info` / `good`), ≤ 1000 chart points, and a table of ≤ 8 columns × 200 rows.
Send data only. The app picks colours from its colourblind-safe palette and ignores any HTML, Markdown or colour fields.
The live version of the contract is at `GET http://<laptop-A-ip>:8000/api/v1/extensions/contract`.
