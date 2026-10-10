from fastapi.testclient import TestClient

from uspi.api.app import app


def test_healthz():
    client = TestClient(app)
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_text_event_end_to_end(stub_cline_client):
    stub_cline_client.canned_response["TEXT_SLM"] = {
        "chat_suspicion_probability": 0.75,
        "scam_type_guess": "job_scam",
        "per_message_scores": [{"message_index": 0, "suspicion": 0.8}],
        "confidence": 0.6,
        "calibration_status": "calibrated",
        "rationale": "Mentions urgent payment.",
    }
    client = TestClient(app)
    resp = client.post("/v1/text/event", json={
        "chat_id": "chat_e2e", "seq": 1, "ts_utc": 1000.0,
        "text": "Urgent! Pay now a processing fee to claim your job offer.",
        "event_flags": [],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "tier" in data
    assert "action" in data


def test_live_call_round_trip(stub_cline_client):
    stub_cline_client.canned_response["LIVE_ANALYSER"] = {
        "risk_score": 0.4, "confidence": 0.5, "scam_type_guess": "unknown",
        "novel_pattern": False, "matched_pattern_ids": [], "rationale": "Mild.",
    }
    client = TestClient(app)
    start_resp = client.post("/v1/live/start", json={})
    case_id = start_resp.json()["case_id"]
    chunk_resp = client.post("/v1/live/chunk", json={
        "case_id": case_id, "transcript_text": "hello there", "start_s": 0, "end_s": 12,
    })
    assert chunk_resp.status_code == 200
    end_resp = client.post(f"/v1/live/end?case_id={case_id}")
    assert end_resp.status_code == 200
    assert end_resp.json()["outcome"] in {"alert", "no_alert_raised"}
