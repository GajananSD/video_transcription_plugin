# Conversation Insights — Video Transcription plugin

A plugin (an "extension") for the **Video Transcription with Confidence Analytics** app.

It runs as its **own small web service** on a second laptop. When the app has a transcript,
it POSTs the transcript to this plugin. The plugin answers with an **insight card**, and the
app shows it under **🧩 Extension insights** at the bottom of its page.

```
 Laptop A (the app)                              Laptop B (this plugin)
 ┌────────────────────────────┐                  ┌──────────────────────────┐
 │ Streamlit frontend  :8501  │                  │                          │
 │ FastAPI backend     :8000  │ ── POST event ─▶ │ uvicorn app:app   :8300  │
 │                            │ ◀── insight card │   /insight  /health  /   │
 └────────────────────────────┘                  └──────────────────────────┘
```

> **This README assumes laptop A is already running** the app's backend and frontend.
> Every step below is done on **laptop B**, the laptop with this code.

---

## Contents

1. [What the plugin shows](#what-the-plugin-shows)
2. [Before you start](#before-you-start)
3. [Step 1 — Install](#step-1--install)
4. [Step 2 — Start the plugin](#step-2--start-the-plugin)
5. [Step 3 — Check the connection with `/health`](#step-3--check-the-connection-with-health)
6. [Step 4 — Register the plugin (two ways)](#step-4--register-the-plugin-two-ways)
7. [Step 5 — See it working](#step-5--see-it-working)
8. [Disconnect](#disconnect)
9. [Firewall](#firewall)
10. [Troubleshooting](#troubleshooting)
11. [Settings](#settings)
12. [Files](#files)
13. [The contract (`cia-extension/1`)](#the-contract-cia-extension1)

---

## What the plugin shows

| Part | What you see in the app |
|---|---|
| Note | Number of speakers, who talked most, top topic words |
| Stats | Speaking pace (wpm), longest turn, silence %, questions asked, filler words, unsure stretches |
| Flags | ▲ one speaker dominates / clusters of low-confidence words to re-listen (with time + speaker), ■ talking over each other / many fillers / fast speech, ● balanced talk / reliable transcript |
| Chart | Words per 15-second window, per speaker |
| Table | Per speaker: talk time, share, turns, words/min, fillers, average confidence |

---

## Before you start

You need:

- **Python 3.10+** on laptop B. No GPU, Whisper or copy of the transcription app is needed.
- **Laptop A's IP address.** Ask whoever runs laptop A, or run on laptop A:
  Linux `hostname -I` · macOS `ipconfig getifaddr en0` · Windows `ipconfig` (the IPv4 address).
- **Both laptops on the same network.** Campus Wi-Fi often blocks laptop-to-laptop traffic.
  If the checks in Step 3 fail, connect both laptops to one **phone hotspot**.
- Laptop A's backend started with `--host 0.0.0.0` (needed for `/health` checks and for `register.py`):
  ```bash
  uvicorn backend.main:app --host 0.0.0.0 --port 8000
  ```

Find **laptop B's own IP** (you will need it too):

```bash
hostname -I            # Linux
ipconfig getifaddr en0 # macOS
ipconfig               # Windows (IPv4 address)
```

In the commands below, replace `<laptop-A-ip>` and `<laptop-B-ip>` with these addresses,
e.g. `192.168.1.20` and `192.168.1.30`.

---

## Step 1 — Install

```bash
cd video_transcription_plugin
python3 -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Optional: set your team name so the app shows it next to the plugin.

```bash
cp .env.example .env               # then edit TEAM_NAME=... in .env
```

---

## Step 2 — Start the plugin

**Terminal 1** (leave it running):

```bash
source .venv/bin/activate
uvicorn app:app --host 0.0.0.0 --port 8300
```

`--host 0.0.0.0` is required: without it, laptop A cannot reach the plugin.

Quick self-test, no app needed (**terminal 2**):

```bash
python mock_app.py       # sends sample_event.json, prints the card and "✓ Valid insight card"
python -m pytest -q      # unit tests
```

---

## Step 3 — Check the connection with `/health`

Do these checks **before registering**. They tell you exactly which side is blocked.

### 3a. The plugin is running (on laptop B)

```bash
curl http://localhost:8300/health
```

Expected:

```json
{"status":"ok","plugin":"Conversation Insights","events_received":0,"last_event":null}
```

### 3b. Laptop B can reach laptop A's app

```bash
curl http://<laptop-A-ip>:8000/api/v1/health
```

Any JSON answer means the app is reachable. If it hangs or says *Connection refused*: laptop A's
backend was not started with `--host 0.0.0.0`, port 8000 is blocked on laptop A, or the laptops
are on different networks.

> No `curl`? Open the same URLs in a browser on laptop B.

### 3c. Laptop A can reach this plugin

This is the direction the app actually uses. Ask the person on laptop A to run (or open in a browser):

```bash
curl http://<laptop-B-ip>:8300/health
```

It must return the same `{"status":"ok", ...}` as in 3a. If it fails, open port 8300 in
laptop B's [firewall](#firewall).

| 3a | 3b | 3c | Meaning |
|---|---|---|---|
| ✓ | ✓ | ✓ | All good — continue to Step 4 (either way works) |
| ✓ | ✗ | ✓ | Use **Way 1** (the app's Extensions tab); `register.py` won't work |
| ✓ | any | ✗ | Fix laptop B's firewall / network first — the app cannot call the plugin |
| ✗ | — | — | The plugin is not running — go back to Step 2 |

---

## Step 4 — Register the plugin (two ways)

Registering tells the app *where* to send transcripts. Pick **one** of the two ways.

### Way 1 — From the app's 🧩 Extensions tab (no command line)

On **laptop A**, in the app's web page (Streamlit frontend):

1. Open the **🧩 Extensions** tab.
2. Fill in:
   - **Name:** `Conversation Insights`
   - **Team:** your team name (if the form has this field)
   - **URL:** `http://<laptop-B-ip>:8300/insight`  ← note the `/insight` at the end
3. Click **Connect**.
4. Click **Send test**. You should see a success message with the reply time.

With this way, laptop A's backend does **not** need `--host 0.0.0.0`, because only the app calls
the plugin (check 3c must still pass).

### Way 2 — From laptop B's terminal with `register.py`

On **laptop B**, in a second terminal (the plugin from Step 2 must still be running):

```bash
source .venv/bin/activate
python register.py --app http://<laptop-A-ip>:8000 --team "Your Team"
```

`register.py` does three things:

1. Finds laptop B's IP and builds the plugin URL `http://<laptop-B-ip>:8300/insight`.
2. Registers it with the app (`POST /api/v1/extensions`). An old entry with the same name is
   replaced, so it is safe to run again (e.g. after your IP changes).
3. Asks the app to send a **test event** to the plugin, which proves laptop A can reach laptop B.

Expected output:

```
✓ Registered 'Conversation Insights' from Your Team → http://<laptop-B-ip>:8300/insight  (id ...)
… asking the app to send us a test event
✓ The app reached this plugin and got a valid card in 12 ms.
```

Options:

| Option | Use |
|---|---|
| `--app URL` | **Required.** Laptop A's backend, e.g. `http://192.168.1.20:8000` |
| `--team NAME` | Team name shown in the app (default: `TEAM_NAME` from `.env`) |
| `--name NAME` | Plugin name (default: `Conversation Insights`) |
| `--url URL` | Set the plugin URL yourself, if the auto-detected IP is wrong (e.g. VPN or several networks): `--url http://<laptop-B-ip>:8300/insight` |
| `--remove` | Disconnect the plugin (see [Disconnect](#disconnect)) |

This way needs check **3b** to pass (laptop A's backend on `--host 0.0.0.0`, port 8000 open).

---

## Step 5 — See it working

- **On laptop A:** transcribe or open a recording and scroll to the bottom of the page. The
  **Conversation Insights** card appears under **🧩 Extension insights**. The 🧩 Extensions tab lists
  the plugin with its laptop-B URL.
- **On laptop B:** open `http://localhost:8300/` in a browser. This status page refreshes every
  5 seconds and lists every event received, with laptop A's IP. Terminal 1 also logs each call:
  ```
  [plugin] transcript.ready from 192.168.1.20 for 'meeting.mp4' (812 words) -> card with 4 flags
  ```
- **Edit a transcript:** correct a turn in the app (✏️ Correct the transcript). The app calls the
  plugin again with `transcript.updated`, and the card updates.
- `curl http://localhost:8300/health` now shows `events_received` > 0 and the `last_event`.

---

## Disconnect

- **Terminal:** `python register.py --app http://<laptop-A-ip>:8000 --remove`
- **App:** click **Remove** next to the plugin in the 🧩 Extensions tab.

Then stop the plugin with `Ctrl+C` in terminal 1.

---

## Firewall

Open port **8300 on laptop B** (always) and port **8000 on laptop A** (only for `register.py` / check 3b).

| OS | Command |
|---|---|
| Fedora | `sudo firewall-cmd --add-port=8300/tcp` (Fedora Workstation already allows 1025–65535) |
| Ubuntu | `sudo ufw allow 8300/tcp` (only needed if ufw is enabled) |
| Windows | Click **Allow** when Windows asks about Python, or in an admin PowerShell: `New-NetFirewallRule -DisplayName "plugin 8300" -Direction Inbound -Protocol TCP -LocalPort 8300 -Action Allow` |
| macOS | Click **Allow incoming connections** when asked |

---

## Troubleshooting

| Message | Cause / fix |
|---|---|
| `register.py`: *Cannot reach the app* | Check 3b fails. Laptop A's backend isn't started with `--host 0.0.0.0`, port 8000 is blocked, or the laptops are on different networks. Or use **Way 1** instead. |
| `register.py`: *The app could not use this plugin* | Check 3c fails. The plugin isn't running with `--host 0.0.0.0`, or port 8300 is blocked on laptop B. |
| App: *Could not connect. Is the extension service running?* | Same as above, or laptop B's IP changed — re-run `register.py` or update the URL in the Extensions tab. |
| App: *No answer within 8 seconds* | Network too slow or blocked. Try a phone hotspot. |
| App: *The answer is not a valid insight card* | Only if you changed `card.py`. Run `python mock_app.py` to see which rule fails. |
| Card shows "From an earlier version of the transcript" | Click **↻ Ask again** in the app. |
| Wrong IP in the registered URL | Laptop B has several networks (VPN, Docker…). Pass it yourself: `--url http://<laptop-B-ip>:8300/insight`. |

---

## Settings

Copy `.env.example` to `.env` and change what you need (all optional). Restart the plugin after editing.

| Variable | Default | Meaning |
|---|---|---|
| `PLUGIN_NAME` | `Conversation Insights` | Name shown in the app |
| `TEAM_NAME` | *(empty)* | Team name shown next to the plugin |
| `PLUGIN_PORT` | `8300` | Port used by `register.py` / `mock_app.py` (also pass it to `uvicorn --port`) |
| `LOW_CONFIDENCE` | `0.30` | A word below this confidence counts as "unsure" |
| `UNSURE_MIN_WORDS` | `3` | Unsure words needed to flag a stretch to re-listen… |
| `UNSURE_WINDOW_S` | `5` | …within this many seconds |
| `DOMINANCE_SHARE` | `0.70` | Talk-time share above which a speaker gets an "attention" flag |
| `WINDOW_S` | `15` | Chart bucket size in seconds |

---

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

---

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

Limits: heading ≤ 80 characters, note ≤ 600, ≤ 6 stats, ≤ 40 flags (`attention` / `info` / `good`),
≤ 1000 chart points, and a table of ≤ 8 columns × 200 rows.
Send data only: the app picks colours from its colourblind-safe palette and ignores any HTML,
Markdown or colour fields.
The live version of the contract is at `GET http://<laptop-A-ip>:8000/api/v1/extensions/contract`.
