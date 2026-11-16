"""Plugin tests. They run without the transcription app (python -m pytest -q)."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from analysis import analyse
from app import app
from card import build_card
from mock_app import check_card

SAMPLE = json.loads((Path(__file__).resolve().parents[1] / "sample_event.json").read_text())
client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_insight_returns_valid_card():
    r = client.post("/insight", json=SAMPLE)
    assert r.status_code == 200
    card = r.json()
    assert check_card(card) == []
    assert card["heading"] == "Conversation Insights"
    assert card["table"]["rows"] and card["series"]["points"]
    assert all(f["level"] in ("attention", "info", "good") for f in card["flags"])


def test_event_is_logged_on_status_page():
    client.post("/insight", json=SAMPLE)
    assert "campus_radio_sample.mp4" in client.get("/").text
    assert client.get("/health").json()["events_received"] >= 1


def test_analysis_numbers():
    a = analyse(SAMPLE)
    assert {s.speaker for s in a.speakers} == {"SPEAKER_00", "SPEAKER_01"}
    assert a.total_words == len(SAMPLE["words"])
    assert sum(s.fillers for s in a.speakers) >= 2          # um, uh, basically, like
    assert sum(s.questions for s in a.speakers) == 3
    assert a.interruptions == 1                              # turn 5 starts before turn 4 ends
    assert a.unsure_stretches and a.unsure_stretches[0]["speaker"] == "SPEAKER_01"
    assert "solar" in dict(a.keywords)


def test_empty_transcript_still_answers():
    ev = copy.deepcopy(SAMPLE)
    ev["turns"], ev["words"] = [], []
    card = build_card(analyse(ev))
    assert check_card(card) == [] and "No speech" in card["note"]


def test_single_speaker_has_no_balance_flag():
    ev = copy.deepcopy(SAMPLE)
    for t in ev["turns"]:
        t["speaker"] = "SPEAKER_00"
    for w in ev["words"]:
        w["speaker"] = "SPEAKER_00"
    card = build_card(analyse(ev))
    assert not any("talk time" in f["text"].lower() for f in card["flags"])


@pytest.mark.parametrize("bad, msg", [
    ({"heading": ""}, "heading"),
    ({"heading": "x", "flags": [{"level": "danger", "text": "t"}]}, "level"),
    ({"heading": "x", "stats": [{"name": "n", "value": 1}] * 7}, "stats"),
])
def test_contract_checker_catches_bad_cards(bad, msg):
    assert any(msg in e for e in check_card(bad))
