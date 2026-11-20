import pytest

from app.ai import AnthropicLLM, LLMError, clean_evaluation, extract_json


def test_extract_json_from_fenced_block_and_chatter():
    raw = 'Claro!\n```json\n{"accepted": true, "items": []}\n```\nEspero ter ajudado.'
    assert extract_json(raw) == {"accepted": True, "items": []}


def test_extract_json_errors():
    for bad in ("", "sem json aqui", '{"quebrado": '):
        with pytest.raises(LLMError):
            extract_json(bad)


def test_clean_evaluation_sanitizes_fields():
    data = clean_evaluation({
        "accepted": "true",  # string não conta: só o booleano true aceita
        "corrected_text": None,
        "items": [{"you_wrote": "mesa", "should_be": "table", "kind": "PORTUGUESE", "explanation": "x"},
                  {"kind": "inventado"}, "lixo"],
    })
    assert data["accepted"] is False and data["corrected_text"] == ""
    assert [i["kind"] for i in data["items"]] == ["portuguese", "wrong"]
    with pytest.raises(LLMError):
        clean_evaluation(["não é objeto"])


class _Stub(AnthropicLLM):
    def __init__(self, replies):  # sem rede e sem chave
        self.replies, self.model = list(replies), "stub"
        self.prompts = []

    def _ask(self, system, user, max_tokens=2000):
        self.prompts.append(user)
        return self.replies.pop(0)


def test_evaluate_and_word_meanings_use_parsed_json():
    llm = _Stub(['{"accepted": false, "corrected_text": "I like it.", "summary": "Quase", "items": []}'])
    out = llm.evaluate("Eu gosto.", "I like it.", "I gosto")
    assert out["corrected_text"] == "I like it." and out["accepted"] is False
    assert "<tentativa>\nI gosto\n</tentativa>" in llm.prompts[0]  # texto do aluno vai como dado, em tags

    llm = _Stub(['```json\n{"fox": "raposa", "lazy": " preguiçoso ", "dog": 5}\n```'])
    assert llm.word_meanings([("fox", "a fox"), ("lazy", "x"), ("dog", "y")]) == {"fox": "raposa", "lazy": "preguiçoso"}
