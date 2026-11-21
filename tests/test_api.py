"""Testes de ponta a ponta da API (SQLite temporário, IA simulada)."""


def _dialog(client, title):
    return next(d for d in client.get("/api/dialogs").json() if d["title"] == title)


# --------------------------------------------------------------------------- frases / diálogos
def test_seed_dialogs_and_glossary(client):
    dialogs = client.get("/api/dialogs").json()
    titles = [d["title"] for d in dialogs]
    assert titles[:3] == ["No restaurante", "No aeroporto", "Conhecendo alguém"]
    assert len(titles) == 12 and sum(t.startswith("TI — ") for t in titles) == 9
    assert all(d["done"] == 0 and d["phrase_count"] >= 6 for d in dialogs)
    # todas as palavras dos diálogos iniciais já vêm separadas e com significado (funciona offline)
    stats = client.get("/api/vocab/stats").json()
    assert stats["total"] > 350
    assert stats["no_meaning"] == 0  # nenhuma palavra dos diálogos fica sem significado


def test_phrase_flow_flips_and_requires_correct_typing(client):
    d = _dialog(client, "No restaurante")
    p = client.get(f"/api/practice/next?dialog_id={d['id']}").json()
    assert p["prompt"] == "Good evening. Do you have a reservation?"
    assert p["direction"] == "en_to_pt"
    assert "pt" not in p  # a resposta não vaza

    # errado: nada avança e as palavras vêm marcadas
    r = client.post(f"/api/phrases/{p['id']}/check", json={"direction": "en_to_pt", "answer": "Boa noite. Você tem uma mesa?"}).json()
    assert r["correct"] is False and "canonical" not in r
    assert {"text": "mesa", "status": "wrong"} in r["marks"]

    # sem acento não vale
    r = client.post(f"/api/phrases/{p['id']}/check", json={"direction": "en_to_pt", "answer": "Boa noite. Voce tem uma reserva?"}).json()
    assert r["correct"] is False

    # certo (uma das traduções alternativas): inverte, devolvendo o português para virar o novo enunciado
    r = client.post(f"/api/phrases/{p['id']}/check", json={"direction": "en_to_pt", "answer": "boa noite. tem reserva?"}).json()
    assert r["correct"] is True and r["stage_complete"] is False
    assert r["canonical"] == "Boa noite. Você tem uma reserva?"

    # agora é português -> inglês
    r = client.post(f"/api/phrases/{p['id']}/check", json={"direction": "pt_to_en", "answer": "Good evening. Do you have a reservation"}).json()
    assert r["correct"] is True and r["stage_complete"] is True

    d = _dialog(client, "No restaurante")
    assert d["done"] == 1
    # a próxima frase do diálogo é outra (as menos praticadas vêm primeiro)
    nxt = client.get(f"/api/practice/next?dialog_id={d['id']}").json()
    assert nxt["id"] != p["id"]


def test_contractions_accepted_in_english_answer(client):
    d = _dialog(client, "Conhecendo alguém")
    lines = client.get(f"/api/dialogs/{d['id']}").json()["lines"]
    phrase = next(l for l in lines if l["en"].startswith("Nice to meet you too"))
    ok = client.post(
        f"/api/phrases/{phrase['id']}/check",
        json={"direction": "pt_to_en", "answer": "Nice to meet you too. I am Paulo. Where are you from?"},
    ).json()
    assert ok["correct"] is True


def test_reveal_counts_as_mistake_and_does_not_advance(client):
    d = _dialog(client, "No aeroporto")
    p = client.get(f"/api/practice/next?dialog_id={d['id']}").json()
    r = client.post(f"/api/phrases/{p['id']}/reveal", json={"direction": "en_to_pt"}).json()
    assert r["answer"] == "Olá. Posso ver o seu passaporte?"
    lines = client.get(f"/api/dialogs/{d['id']}").json()["lines"]
    assert lines[0]["mistakes"] == 1 and lines[0]["completed"] == 0


def test_settings_ignore_accents(client):
    d = _dialog(client, "No restaurante")
    p = client.get(f"/api/practice/next?dialog_id={d['id']}").json()
    body = {"direction": "en_to_pt", "answer": "Boa noite. Voce tem uma reserva?"}
    assert client.post(f"/api/phrases/{p['id']}/check", json=body).json()["correct"] is False
    client.put("/api/settings", json={"ignore_accents": True, "strict_exact": False})
    assert client.get("/api/settings").json()["ignore_accents"] is True
    assert client.post(f"/api/phrases/{p['id']}/check", json=body).json()["correct"] is True


def test_create_custom_dialog_extracts_words(client):
    r = client.post("/api/dialogs", json={
        "title": "Na farmácia",
        "lines": [{"speaker": "A", "en": "I need some aspirin.", "pt": "Eu preciso de aspirina."}],
    })
    assert r.status_code == 201
    assert r.json()["words"]["added"] >= 1
    words = {w["word"] for w in client.get("/api/vocab?q=asp").json()["items"]}
    assert "aspirin" in words
    assert client.delete(f"/api/dialogs/{r.json()['id']}").status_code == 204


def test_add_loose_phrase_goes_to_my_phrases(client):
    r = client.post("/api/phrases", json={"en": "See you tomorrow.", "pt": "Até amanhã."}).json()
    again = client.post("/api/phrases", json={"en": "Good luck!", "pt": "Boa sorte!"}).json()
    assert r["dialog_id"] == again["dialog_id"]
    assert _dialog(client, "Minhas frases")["phrase_count"] == 2


def test_validation_errors(client):
    assert client.post("/api/phrases", json={"en": "", "pt": "x"}).status_code == 422
    assert client.get("/api/practice/next?dialog_id=9999").status_code == 404
    assert client.post("/api/phrases/9999/check", json={"direction": "en_to_pt", "answer": "x"}).status_code == 404


# --------------------------------------------------------------------------- textos
PT = "Eu gostaria de uma mesa para dois."
EN = "I would like a table for two."


def test_text_requires_reference_without_ai(client):
    r = client.post("/api/texts", json={"pt_text": PT})
    assert r.status_code == 422
    assert "ANTHROPIC_API_KEY" in r.json()["detail"]


def test_text_flow_without_ai(client):
    t = client.post("/api/texts", json={"pt_text": PT, "en_reference": EN, "title": "Mesa"}).json()
    assert t["status"] == "pending"
    detail = client.get(f"/api/texts/{t['id']}").json()
    assert detail["solved_text"] is None and "en_text" not in detail  # a resposta não vaza

    # mistura inglês com português onde não sabia
    r = client.post(f"/api/texts/{t['id']}/attempt", json={"attempt": "I would like a mesa for two."}).json()
    assert r["accepted"] is False
    assert r["engine"] == "local" and "sem IA" in r["note"]
    assert r["corrections"] == [{"you_wrote": "mesa", "should_be": "table", "kind": "portuguese", "explanation": ""}]
    assert [m["status"] for m in r["marks"]][4] == "wrong"
    # a palavra que não sabia vai direto para a revisão
    table = next(w for w in client.get("/api/vocab?q=table").json()["items"] if w["word"] == "table")
    assert table["in_review"] is True and table["wrong"] == 1
    assert client.get(f"/api/texts/{t['id']}").json()["status"] == "pending"

    # só é aceito quando está tudo certo
    r = client.post(f"/api/texts/{t['id']}/attempt", json={"attempt": "i would like a table for two"}).json()
    assert r["accepted"] is True and r["solved_text"] == "i would like a table for two"
    assert r["words"]["total"] > 0
    detail = client.get(f"/api/texts/{t['id']}").json()
    assert detail["status"] == "solved" and detail["attempts"] == 2
    assert detail["solved_text"] == "i would like a table for two"
    assert {w["word"] for w in client.get("/api/vocab?q=would").json()["items"]} == {"would"}


def test_text_with_ai_generates_reference_and_accepts_equivalent_translation(ai_client, fake_llm):
    t = ai_client.post("/api/texts", json={"pt_text": PT}).json()
    assert ai_client.get("/api/status").json()["ai_enabled"] is True

    # tradução equivalente (não é igual à referência): quem decide é a IA
    fake_llm.evaluation = {"accepted": True, "corrected_text": "", "summary": "Ótimo!", "items": []}
    r = ai_client.post(f"/api/texts/{t['id']}/attempt", json={"attempt": "I'd love a table for two people."}).json()
    assert r["accepted"] is True and r["engine"] == "ai" and r["summary"] == "Ótimo!"
    assert all(m["status"] == "ok" for m in r["marks"])


def test_ai_acceptance_is_overridden_when_portuguese_remains(ai_client, fake_llm):
    t = ai_client.post("/api/texts", json={"pt_text": PT}).json()
    fake_llm.evaluation = {"accepted": True, "corrected_text": "", "summary": "", "items": []}  # IA "distraída"
    r = ai_client.post(f"/api/texts/{t['id']}/attempt", json={"attempt": "I would like a mesa for two."}).json()
    assert r["accepted"] is False
    assert "português" in r["summary"]


def test_ai_corrections_are_returned_and_words_go_to_review(ai_client, fake_llm):
    t = ai_client.post("/api/texts", json={"pt_text": PT}).json()
    fake_llm.evaluation = {
        "accepted": False,
        "corrected_text": EN,
        "summary": "Quase lá!",
        "items": [{"you_wrote": "want", "should_be": "would like", "kind": "vocabulary", "explanation": "Mais educado."}],
    }
    r = ai_client.post(f"/api/texts/{t['id']}/attempt", json={"attempt": "I want a table for two."}).json()
    assert r["accepted"] is False
    assert r["corrections"][0]["explanation"] == "Mais educado."
    review_words = {w["word"] for w in ai_client.get("/api/vocab?filter=review&q=would").json()["items"]}
    assert "would" in review_words


def test_exact_match_does_not_call_ai(ai_client, fake_llm):
    t = ai_client.post("/api/texts", json={"pt_text": PT}).json()
    r = ai_client.post(f"/api/texts/{t['id']}/attempt", json={"attempt": EN}).json()
    assert r["accepted"] is True and fake_llm.evaluate_calls == 0


def test_ai_failure_falls_back_to_local(ai_client, fake_llm):
    t = ai_client.post("/api/texts", json={"pt_text": PT}).json()
    fake_llm.fail_evaluate = True
    r = ai_client.post(f"/api/texts/{t['id']}/attempt", json={"attempt": "I would like a mesa for two"}).json()
    assert r["accepted"] is False and r["engine"] == "local" and "IA não respondeu" in r["note"]
    assert r["corrections"][0]["kind"] == "portuguese"


def test_patch_reference_to_accept_another_translation(client):
    t = client.post("/api/texts", json={"pt_text": PT, "en_reference": EN}).json()
    alt = "I would love a table for two."
    assert client.post(f"/api/texts/{t['id']}/attempt", json={"attempt": alt}).json()["accepted"] is False
    client.patch(f"/api/texts/{t['id']}", json={"en_reference": alt})
    assert client.post(f"/api/texts/{t['id']}/attempt", json={"attempt": alt}).json()["accepted"] is True


# --------------------------------------------------------------------------- vocabulário / revisão
def test_import_english_text_separates_all_words(client):
    text = "The zebra gallops over the sleepy hippo. The hippo yawns."
    r = client.post("/api/vocab/import", json={"text": text}).json()
    assert r["total"] == 7 and r["added"] >= 5 and r["ai_will_translate"] is False  # the, zebra, gallops, over, sleepy, hippo, yawns
    items = client.get("/api/vocab?q=gall").json()["items"]
    assert [w["word"] for w in items] == ["gallops"]
    assert items[0]["example"] == "The zebra gallops over the sleepy hippo."
    assert items[0]["in_review"] is True
    common = {w["word"] for w in client.get("/api/vocab?filter=common&limit=2000").json()["items"]}
    assert "the" in common
    assert "the" not in {w["word"] for w in client.get("/api/vocab?filter=review&q=the").json()["items"]}
    assert client.post("/api/vocab/import", json={"text": "123 456"}).status_code == 422


def test_import_fills_meanings_with_ai_in_background(ai_client, fake_llm):
    fake_llm.meanings = {"fox": "raposa", "lazy": "preguiçoso"}
    ai_client.post("/api/vocab/import", json={"text": "The lazy fox."})
    got = {w["word"]: w["meaning_pt"] for w in ai_client.get("/api/vocab?q=f").json()["items"]}
    assert got["fox"] == "raposa"
    assert ai_client.get("/api/vocab?q=lazy").json()["items"][0]["meaning_pt"] == "preguiçoso"


def test_review_flow_and_spacing(client):
    client.post("/api/vocab/import", json={"text": "Zebra."})
    z = client.get("/api/vocab?q=zebra").json()["items"][0]
    # sem significado salvo a palavra não entra na revisão
    assert client.post(f"/api/review/{z['id']}/answer", json={"answer": "zebra"}).status_code == 422
    client.patch(f"/api/vocab/{z['id']}", json={"meaning_pt": "zebra; zebras"})

    # esvazia a fila de palavras iniciais para testar só a nossa
    for w in client.get("/api/vocab?filter=review&limit=2000").json()["items"]:
        if w["word"] != "zebra":
            client.patch(f"/api/vocab/{w['id']}", json={"in_review": False})

    nxt = client.get("/api/review/next").json()
    assert nxt["done"] is False and nxt["word"]["word"] == "zebra" and "meaning_pt" not in nxt["word"]

    wrong = client.post(f"/api/review/{z['id']}/answer", json={"answer": "cavalo"}).json()
    assert wrong["correct"] is False and wrong["box"] == 0 and wrong["meaning_pt"] == "zebra; zebras"
    # errou: só volta em alguns minutos
    assert client.get("/api/review/next").json()["done"] is True

    # força a palavra a ficar vencida de novo e acerta (artigo inicial é opcional)
    import sqlite3
    con = sqlite3.connect(client.app.state.db_path)
    con.execute("UPDATE words SET next_review = '2000-01-01T00:00:00Z' WHERE id = ?", (z["id"],))
    con.commit(); con.close()
    ok = client.post(f"/api/review/{z['id']}/answer", json={"answer": "a zebra"}).json()
    assert ok["correct"] is True and ok["box"] == 1 and ok["next_review"] > "2026"
    stats = client.get("/api/vocab/stats").json()
    assert stats["in_review"] == 1 and stats["due"] == 0


def test_toggle_review_and_hard_filter(client):
    w = client.get("/api/vocab?q=reserv").json()["items"][0]
    assert client.patch(f"/api/vocab/{w['id']}", json={"in_review": False}).json()["in_review"] is False
    assert client.patch("/api/vocab/99999", json={"in_review": True}).status_code == 404
    assert client.post("/api/vocab/fill-meanings").status_code == 422  # sem IA


def test_index_page_is_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "<html" in r.text.lower()
