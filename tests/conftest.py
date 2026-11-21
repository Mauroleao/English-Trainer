import os
import tempfile

# Precisa vir antes de importar app.main (que cria um app padrão ao ser importado)
os.environ["ENGLISH_APP_DB"] = os.path.join(tempfile.mkdtemp(), "default.db")
os.environ.pop("ANTHROPIC_API_KEY", None)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import create_app  # noqa: E402


class FakeLLM:
    """IA de mentira: respostas controláveis pelos testes."""

    model = "fake"

    def __init__(self):
        self.translation = "I would like a table for two."
        self.evaluation = {"accepted": False, "corrected_text": "", "summary": "", "items": []}
        self.fail_evaluate = False
        self.meanings = {}
        self.evaluate_calls = 0
        self.chat_result = {
            "reply": "Hi! What did you do yesterday?",
            "reply_pt": "Oi! O que você fez ontem?",
            "correction": {"needs_fix": False, "corrected": "", "summary": "", "items": []},
        }
        self.fail_chat = False
        self.chat_calls = []

    def translate(self, pt_text):
        return self.translation

    def evaluate(self, pt_text, en_reference, attempt):
        self.evaluate_calls += 1
        if self.fail_evaluate:
            raise RuntimeError("fora do ar")
        return self.evaluation

    def chat(self, role, level, history, message):
        self.chat_calls.append({"role": role, "level": level, "history": history, "message": message})
        if self.fail_chat:
            raise RuntimeError("fora do ar")
        return self.chat_result

    def word_meanings(self, items):
        return {w: self.meanings[w] for w, _ in items if w in self.meanings}


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(str(tmp_path / "t.db"), llm=None))


@pytest.fixture
def fake_llm():
    return FakeLLM()


@pytest.fixture
def ai_client(tmp_path, fake_llm):
    return TestClient(create_app(str(tmp_path / "ai.db"), llm=fake_llm))
