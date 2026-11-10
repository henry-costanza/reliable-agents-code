import json

import pytest

from agentkit.cassette import (
    CassetteMismatch,
    RecordingProvider,
    ReplayProvider,
    current_mode,
    open_provider,
    request_fingerprint,
)
from agentkit.messages import Message, Opaque, Request, Response, StopReason, Text, Usage
from agentkit.provider import ScriptedProvider

FIRST = Request((Message.user("one"),))
SECOND = Request((Message.user("two"),), system="s")
REPLIES = [
    Response(
        Message("assistant", (Opaque("anthropic", {"type": "thinking", "thinking": "", "signature": "s"}), Text("1"))),
        StopReason.END_TURN,
        Usage(5, 1),
        model="m",
    ),
    Response(Message("assistant", (Text("2"),)), StopReason.END_TURN, Usage(6, 1), model="m"),
]


def record(path, requests=(FIRST, SECOND)):
    recorder = RecordingProvider(ScriptedProvider(REPLIES), path)
    return [recorder.complete(r) for r in requests]


def test_record_then_replay_gives_the_same_responses(tmp_path):
    path = tmp_path / "c.json"
    recorded = record(path)
    replay = ReplayProvider(path)
    assert [replay.complete(FIRST), replay.complete(SECOND)] == recorded
    assert replay.unused == 0


def test_cassette_holds_only_requests_responses_and_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-a-real-key")
    path = tmp_path / "c.json"
    record(path)
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    assert set(data) == {"format", "recorded_with", "interactions"}
    assert set(data["interactions"][0]) == {"request", "response"}
    assert "sk-ant" not in text and "api_key" not in text.lower()


def test_cassette_is_written_after_each_call(tmp_path):
    path = tmp_path / "c.json"
    record(path, requests=(FIRST,))
    assert len(json.loads(path.read_text(encoding="utf-8"))["interactions"]) == 1


def test_changed_request_fails_with_a_diff(tmp_path):
    path = tmp_path / "c.json"
    record(path)
    replay = ReplayProvider(path)
    with pytest.raises(CassetteMismatch, match=r"request #1 differs") as caught:
        replay.complete(Request((Message.user("ONE"),)))
    assert '-          "text": "one"' in str(caught.value)
    assert '+          "text": "ONE"' in str(caught.value)


def test_extra_request_fails(tmp_path):
    path = tmp_path / "c.json"
    record(path, requests=(FIRST,))
    replay = ReplayProvider(path)
    replay.complete(FIRST)
    with pytest.raises(CassetteMismatch, match=r"request #2 was not recorded \(the cassette holds 1\)"):
        replay.complete(SECOND)


def test_missing_cassette_says_how_to_record(tmp_path):
    with pytest.raises(CassetteMismatch, match="AGENTKIT_MODE=record"):
        ReplayProvider(tmp_path / "absent.json")


def test_replay_is_the_default_and_never_builds_a_live_provider(tmp_path, monkeypatch):
    monkeypatch.delenv("AGENTKIT_MODE", raising=False)
    path = tmp_path / "c.json"
    record(path)

    def no_live():
        raise AssertionError("replay must not build a live provider")

    assert isinstance(open_provider(path, live=no_live), ReplayProvider)


def test_record_and_live_modes(tmp_path):
    live = ScriptedProvider(REPLIES)
    recorder = open_provider(tmp_path / "c.json", mode="record", live=lambda: live)
    assert isinstance(recorder, RecordingProvider) and recorder.inner is live
    assert open_provider(tmp_path / "c.json", mode="live", live=lambda: live) is live


LONG = Request((Message.user("filler " * 5000 + "What is the key?"),))


def record_fingerprints(path, requests=(LONG, SECOND)):
    recorder = RecordingProvider(ScriptedProvider(REPLIES), path, store="fingerprint")
    return [recorder.complete(r) for r in requests]


def test_fingerprint_cassette_replays(tmp_path):
    path = tmp_path / "c.json"
    recorded = record_fingerprints(path)
    replay = ReplayProvider(path)
    assert [replay.complete(LONG), replay.complete(SECOND)] == recorded
    assert replay.unused == 0


def test_fingerprint_cassette_stores_no_request_text(tmp_path):
    path = tmp_path / "c.json"
    record_fingerprints(path)
    first = json.loads(path.read_text(encoding="utf-8"))["interactions"][0]
    assert set(first) == {"request_fingerprint", "request_summary", "response"}
    assert first["request_fingerprint"] == request_fingerprint(LONG)
    assert first["request_summary"]["chars"] == len(LONG.messages[0].text)
    assert path.stat().st_size < 3000  # the 40,000-character prompt is not in it


def test_fingerprint_cassette_fails_on_any_change(tmp_path):
    path = tmp_path / "c.json"
    record_fingerprints(path)
    changed = Request((Message.user("filler " * 5000 + "What is the key!"),))
    with pytest.raises(CassetteMismatch, match="fingerprints differ") as caught:
        ReplayProvider(path).complete(changed)
    assert "What is the key?" in str(caught.value) and "What is the key!" in str(caught.value)


def test_fingerprint_is_stable_and_sensitive():
    assert request_fingerprint(LONG) == request_fingerprint(Request((Message.user(LONG.messages[0].text),)))
    assert request_fingerprint(LONG) != request_fingerprint(SECOND)


def test_open_provider_records_fingerprints_when_asked(tmp_path):
    live = ScriptedProvider(REPLIES)
    recorder = open_provider(tmp_path / "c.json", mode="record", live=lambda: live, store="fingerprint")
    assert recorder.store == "fingerprint"


def test_unknown_store_is_refused(tmp_path):
    with pytest.raises(ValueError, match="store must be one of full, fingerprint"):
        RecordingProvider(ScriptedProvider(REPLIES), tmp_path / "c.json", store="zip")


def test_bad_mode_is_refused(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENTKIT_MODE", "fake")
    with pytest.raises(ValueError, match="AGENTKIT_MODE must be one of replay, record, live"):
        current_mode()
    with pytest.raises(ValueError, match="mode must be one of"):
        open_provider(tmp_path / "c.json", mode="fake")
