import pytest
from app.ai import (
    BaseLLM,
    GeminiLLM,
    OllamaLLM,
    LMStudioLLM,
    OpenAILLM,
    AnthropicLLM,
    create_llm,
    get_llm_from_env_or_db,
)
from app.db import connect, init_db, set_setting


def test_create_llm_providers():
    gemini = create_llm("gemini", api_key="test-key-123", model="gemini-2.5-flash")
    assert isinstance(gemini, GeminiLLM)
    assert gemini.provider == "gemini"
    assert gemini.model == "gemini-2.5-flash"

    ollama = create_llm("ollama", endpoint="http://localhost:11434", model="llama3.2")
    assert isinstance(ollama, OllamaLLM)
    assert ollama.provider == "ollama"
    assert ollama.host == "http://localhost:11434"

    lmstudio = create_llm("lmstudio", endpoint="http://localhost:1234/v1", model="local-model")
    assert isinstance(lmstudio, LMStudioLLM)
    assert lmstudio.provider == "lmstudio"
    assert lmstudio.host == "http://localhost:1234/v1"

    openai = create_llm("openai", api_key="sk-test", model="gpt-4o-mini")
    assert isinstance(openai, OpenAILLM)
    assert openai.provider == "openai"


def test_get_llm_from_db(tmp_path):
    db_file = str(tmp_path / "test.db")
    init_db(db_file)
    conn = connect(db_file)
    set_setting(conn, "ai_provider", "ollama")
    set_setting(conn, "ai_model", "qwen2.5")
    set_setting(conn, "ai_endpoint", "http://127.0.0.1:11434")

    llm = get_llm_from_env_or_db(conn)
    assert isinstance(llm, OllamaLLM)
    assert llm.model == "qwen2.5"
    assert llm.host == "http://127.0.0.1:11434"


def test_api_ai_config_and_status(tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app

    db_file = str(tmp_path / "api_test.db")
    app = create_app(db_file, llm=None)
    client = TestClient(app)

    # Initial status: AI disabled
    r = client.get("/api/status")
    assert r.status_code == 200
    assert r.json()["ai_enabled"] is False

    # Get AI config
    r = client.get("/api/ai/config")
    assert r.status_code == 200
    assert "defaults" in r.json()

    # Save Ollama config
    r = client.post("/api/ai/config", json={
        "provider": "ollama",
        "api_key": "",
        "model": "llama3.2",
        "endpoint": "http://localhost:11434"
    })
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["ai_enabled"] is True
    assert data["provider"] == "ollama"

    # Status reflects change
    r = client.get("/api/status")
    assert r.status_code == 200
    assert r.json()["ai_enabled"] is True
    assert r.json()["provider"] == "ollama"

    # Disable AI
    r = client.post("/api/ai/config", json={"provider": "none"})
    assert r.status_code == 200
    assert r.json()["ai_enabled"] is False


def test_audio_cache_existing(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import create_app
    import app.routes.audio as audio_mod

    # Redirect cache dir to tmp_path
    monkeypatch.setattr(audio_mod, "CACHE_DIR", tmp_path / "audio_cache")
    db_file = str(tmp_path / "audio_test.db")
    app = create_app(db_file, llm=None)
    client = TestClient(app)

    # Seed an mp3 file in cache
    cache_dir = tmp_path / "audio_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = audio_mod._get_cache_path("hello world", 1.0)
    fake_mp3 = b"ID3\x03\x00\x00\x00" + b"\x00" * 300
    cache_file.write_bytes(fake_mp3)

    r = client.get("/api/audio/tts", params={"text": "Hello world", "speed": 1.0})
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/mpeg"
    assert r.content == fake_mp3


def test_eargym_and_achievements(tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app

    db_file = str(tmp_path / "study_test.db")
    app = create_app(db_file, llm=None)
    client = TestClient(app)

    # 1. Ear Gym next sentence
    r = client.get("/api/eargym/next?level=A1")
    assert r.status_code == 200
    data = r.json()
    assert "masked" in data
    assert "target" in data
    assert "______" in data["masked"]

    # 2. Ear Gym check
    check_r = client.post("/api/eargym/check", json={"target": data["target"], "answer": data["target"]})
    assert check_r.status_code == 200
    assert check_r.json()["correct"] is True

    # 3. Achievements
    ach_r = client.get("/api/achievements")
    assert ach_r.status_code == 200
    ach_data = ach_r.json()
    assert "badges" in ach_data
    assert len(ach_data["badges"]) >= 5


class _MockLLM(BaseLLM):
    def __init__(self, reply):
        self.provider = "mock"
        self.model = "mock"
        self.reply = reply

    def _ask(self, system, user, max_tokens=2000):
        return self.reply


def test_dialog_generation_and_coach_report(tmp_path):
    import json
    from fastapi.testclient import TestClient
    from app.main import create_app

    # Test dialog generation
    dialog_json = json.dumps({
        "title": "Code Review da API",
        "description": "Conversa sobre pull request em Python",
        "lines": [
            {"speaker": "Ana", "en": "Did you check the tests?", "pt": "Você conferiu os testes?"},
            {"speaker": "Mauro", "en": "Yes, all tests are passing.", "pt": "Sim, todos os testes estão passando."}
        ]
    })
    mock_llm = _MockLLM(dialog_json)

    db_file = str(tmp_path / "dialog_test.db")
    app = create_app(db_file, llm=mock_llm)
    client = TestClient(app)

    r = client.post("/api/conversation/generate-dialog", json={"topic": "Code Review", "level": "B1"})
    assert r.status_code == 200
    res = r.json()
    assert res["line_count"] == 2
    assert "Code Review" in res["title"]

    # Test coach report
    coach_json = json.dumps({
        "overall_score": 90,
        "summary": "Excelente resposta!",
        "kid_friendly_rule": "Regra simples do passado.",
        "vocabulary_upgrades": [{"you_said": "did", "better": "implemented", "why": "mais profissional"}],
        "star_method_coaching": {
            "situation": "S", "task": "T", "action": "A", "result": "R", "example_speech": "I implemented the fix."
        }
    })
    app.state.llm = _MockLLM(coach_json)

    cr = client.post("/api/conversation/coach-report", json={
        "scenario_id": "daily",
        "history": [
            {"role": "partner", "text": "What did you do yesterday?"},
            {"role": "learner", "text": "I fixed the bug in production."}
        ]
    })
    assert cr.status_code == 200
    coach_data = cr.json()
    assert coach_data["overall_score"] == 90
    assert len(coach_data["vocabulary_upgrades"]) == 1

