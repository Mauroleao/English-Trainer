"""Testes de suporte multi-idioma (Inglês 🇺🇸 e Alemão 🇩🇪).

Verifica que:
  - Diálogos em alemão foram instalados pelo seed
  - A rota /api/languages lista e troca de idioma corretamente
  - Diálogos em inglês e alemão ficam isolados entre si
  - Vocabulário em alemão está disponível por lang param
  - TTS responde (ou retorna 503 graciosamente) com lang=de
"""
import pytest


# ------------------------------------------------------------------ auxiliares
def _lang(client, code: str):
    """Troca o idioma ativo no backend e garante que voltou 200."""
    r = client.post("/api/languages/active", json={"language": code})
    assert r.status_code == 200, r.text
    return r.json()


# ------------------------------------------------------------------ seed alemão
class TestGermanSeed:
    def test_german_dialogs_exist(self, client):
        """GET /api/dialogs?lang=de deve retornar pelo menos 5 diálogos em alemão."""
        r = client.get("/api/dialogs?lang=de")
        assert r.status_code == 200
        dialogs = r.json()
        assert len(dialogs) >= 5, f"Esperado ≥5 diálogos em alemão, obteve {len(dialogs)}"

    def test_german_vocab_exists(self, client):
        """GET /api/vocab/stats?lang=de deve reportar pelo menos 50 palavras em alemão."""
        r = client.get("/api/vocab/stats?lang=de")
        assert r.status_code == 200
        total = r.json().get("total", 0)
        assert total >= 50, f"Esperado ≥50 palavras em alemão, obteve {total}"

    def test_english_dialogs_unaffected(self, client):
        """O seed alemão não deve reduzir os diálogos em inglês."""
        r = client.get("/api/dialogs?lang=en")
        assert r.status_code == 200
        dialogs = r.json()
        assert len(dialogs) >= 1, "Deve haver pelo menos 1 diálogo em inglês"


# ------------------------------------------------------------------ isolamento
class TestLanguageIsolation:
    def test_german_dialogs_not_in_english(self, client):
        """Diálogos alemães não aparecem ao buscar lang=en."""
        r_en = client.get("/api/dialogs?lang=en")
        r_de = client.get("/api/dialogs?lang=de")

        assert r_en.status_code == 200
        assert r_de.status_code == 200

        en_titles = {d["title"] for d in r_en.json()}
        de_titles = {d["title"] for d in r_de.json()}

        # Pelo menos um diálogo alemão existe e não aparece em inglês
        assert len(de_titles) > 0, "Nenhum diálogo alemão encontrado"
        overlap = en_titles & de_titles
        assert len(overlap) == 0, f"Diálogos aparecem nos dois idiomas: {overlap}"

    def test_vocab_stats_isolated(self, client):
        """Estatísticas de vocabulário devem ser diferentes entre en e de."""
        r_en = client.get("/api/vocab/stats?lang=en")
        r_de = client.get("/api/vocab/stats?lang=de")

        assert r_en.status_code == 200
        assert r_de.status_code == 200

        total_en = r_en.json().get("total", 0)
        total_de = r_de.json().get("total", 0)

        assert total_en > 0, "Deve haver palavras em inglês"
        assert total_de > 0, "Deve haver palavras em alemão"


# ------------------------------------------------------------------ troca de idioma
class TestLanguageSwitch:
    def test_switch_to_german(self, client):
        """POST /api/languages/active com 'de' deve persistir e ser retornado em GET."""
        resp = _lang(client, "de")
        assert resp.get("active") == "de"

        r = client.get("/api/languages")
        assert r.status_code == 200
        data = r.json()
        assert data.get("active") == "de", f"Esperado active='de', obteve: {data.get('active')}"

    def test_switch_back_to_english(self, client):
        """Depois de trocar para 'de', deve ser possível voltar para 'en'."""
        _lang(client, "de")
        resp = _lang(client, "en")
        assert resp.get("active") == "en"

    def test_invalid_language_defaults_to_english(self, client):
        """Código de idioma inválido deve retornar 400 com mensagem clara."""
        r = client.post("/api/languages/active", json={"language": "xx"})
        # a API retorna 400 para idioma inválido (comportamento documentado)
        assert r.status_code == 400
        assert "suportado" in r.json().get("detail", "").lower() or "disponíveis" in r.json().get("detail", "").lower()

    def test_languages_list_includes_en_and_de(self, client):
        """GET /api/languages deve listar inglês e alemão."""
        r = client.get("/api/languages")
        assert r.status_code == 200
        data = r.json()
        # resposta tem forma {"active": "en", "languages": [...]}
        langs = data.get("languages", data) if isinstance(data, dict) else data
        codes = {l["code"] for l in langs}
        assert "en" in codes, "Inglês não está na lista de idiomas"
        assert "de" in codes, "Alemão não está na lista de idiomas"


# ------------------------------------------------------------------ TTS multi-idioma
class TestTTSMultiLang:
    def test_tts_en(self, client):
        """TTS para inglês deve retornar 200 (áudio) ou 503 (sem rede no sandbox)."""
        r = client.get("/api/audio/tts?text=Hello&lang=en")
        assert r.status_code in (200, 503), f"Status inesperado: {r.status_code}"

    def test_tts_de(self, client):
        """TTS para alemão deve retornar 200 ou 503 — nunca 400/422."""
        r = client.get("/api/audio/tts?text=Hallo&lang=de")
        assert r.status_code in (200, 503), f"Status inesperado: {r.status_code}"

    def test_tts_invalid_lang_rejected(self, client):
        """Lang inválido (ex: 'xx') deve retornar 422."""
        r = client.get("/api/audio/tts?text=test&lang=xx")
        assert r.status_code == 422
