"""Testes do módulo Live Voice Tutor (Conversação Ao Vivo bidirecional)."""
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.routes.live import parse_recast_tags


def test_parse_recast_tags_single():
    text = "Good job! Just a quick tip, we say this: [RECAST: I have 25 years || I am 25 years old] Let's continue!"
    clean, recasts = parse_recast_tags(text)
    assert "[RECAST:" not in clean
    assert "Good job! Just a quick tip, we say this:" in clean
    assert "Let's continue!" in clean
    assert len(recasts) == 1
    assert recasts[0]["you_said"] == "I have 25 years"
    assert recasts[0]["natural"] == "I am 25 years old"


def test_parse_recast_tags_multiple():
    text = "Notice: [RECAST: she go || she goes] and also [RECAST: in monday || on Monday]! How was your weekend?"
    clean, recasts = parse_recast_tags(text)
    assert "[RECAST:" not in clean
    assert len(recasts) == 2
    assert recasts[0]["you_said"] == "she go"
    assert recasts[0]["natural"] == "she goes"
    assert recasts[1]["you_said"] == "in monday"
    assert recasts[1]["natural"] == "on Monday"


def test_parse_recast_tags_none():
    text = "Everything sounded totally natural and fluent! Keep going."
    clean, recasts = parse_recast_tags(text)
    assert clean == text
    assert recasts == []


def test_create_live_session_default(client):
    res = client.post("/api/live/session", json={})
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert "token" in data and len(data["token"]) >= 20
    assert data["scenario"] == "daily"
    assert f"/ws/live-conversation?token={data['token']}" == data["ws_path"]
    assert "mode" in data


def test_create_live_session_scenarios(client):
    # Entrevista de emprego
    res = client.post("/api/live/session", json={"scenario": "interview"})
    assert res.status_code == 200
    assert res.json()["scenario"] == "interview"

    # Conversa casual
    res = client.post("/api/live/session", json={"scenario": "casual"})
    assert res.status_code == 200
    assert res.json()["scenario"] == "casual"

    # Cenário inválido cai no padrão (daily)
    res = client.post("/api/live/session", json={"scenario": "unknown_scenario"})
    assert res.status_code == 200
    assert res.json()["scenario"] == "daily"


def test_websocket_live_invalid_token(client):
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/live-conversation?token=token_invalido_123"):
            pass


def test_websocket_live_duplex_conversation(client):
    # Gera sessão
    sess = client.post("/api/live/session", json={"scenario": "daily"}).json()
    token = sess["token"]
    ws_path = sess["ws_path"]

    with client.websocket_connect(ws_path) as ws:
        # 1. Mensagem de pronto
        ready_msg = ws.receive_json()
        assert ready_msg["type"] == "ready"
        assert ready_msg["scenario"] == "daily"

        # 2. Mensagem de introdução do tutor
        intro_msg = ws.receive_json()
        assert intro_msg["type"] == "text"
        assert intro_msg["sender"] == "tutor"
        assert "stand-up" in intro_msg["text"].lower()

        # 3. Turn complete da introdução
        turn_comp = ws.receive_json()
        assert turn_comp["type"] == "turn_complete"

        # 4. Envia fala do aluno
        ws.send_json({"type": "text", "text": "Yesterday I worked on the login endpoint, today I am writing unit tests."})

        # 5. Recebe resposta do tutor
        reply_msg = ws.receive_json()
        assert reply_msg["type"] in ("text", "recast")
        if reply_msg["type"] == "recast":
            reply_msg = ws.receive_json()
        assert reply_msg["type"] == "text"
        assert reply_msg["sender"] == "tutor"
        assert len(reply_msg["text"]) > 0

        turn_comp2 = ws.receive_json()
        assert turn_comp2["type"] == "turn_complete"

        # 6. Teste de Barge-in (Interrupção)
        ws.send_json({"type": "interrupt"})
        interrupt_msg = ws.receive_json()
        assert interrupt_msg["type"] == "interrupted"
