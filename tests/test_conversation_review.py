"""Conversação, revisão em três modos, filtros e conteúdo de TI."""
import sqlite3
from contextlib import closing

from app.db import connect, init_db
from app.seed import DIALOGS, _install_dialogs, _once, seed


def _dialog(client, title):
    return next(d for d in client.get("/api/dialogs").json() if d["title"] == title)


def _word(client, q, **params):
    items = client.get("/api/vocab", params={"q": q, "limit": 50, **params}).json()["items"]
    return next(w for w in items if w["word"] == q)


# --------------------------------------------------------------------------- conteúdo de TI
def test_it_content_is_installed_with_meanings_and_examples(client):
    stats = client.get("/api/vocab/stats").json()
    assert stats["ti_total"] >= 100 and stats["no_meaning"] == 0
    blocker = _word(client, "blocker", tag="ti")
    assert blocker["tag"] == "ti" and blocker["meaning_pt"].startswith("bloqueio")
    assert blocker["example"].startswith("I have a blocker")
    pr = _word(client, "pull request", tag="ti")  # expressões de duas palavras também entram
    assert "solicitação" in pr["meaning_pt"]
    only_ti = client.get("/api/vocab?tag=ti&limit=500").json()
    assert only_ti["total"] == stats["ti_total"] and all(w["tag"] == "ti" for w in only_ti["items"])


def test_existing_database_gets_it_pack_without_duplicating_core(tmp_path):
    path = str(tmp_path / "old.db")
    init_db(path)
    with closing(connect(path)) as db:  # usuário antigo: só tinha o conteúdo inicial
        _once(db, "seeded", lambda c: _install_dialogs(c, DIALOGS))
        before = db.execute("SELECT COUNT(*) FROM dialogs").fetchone()[0]
        assert before == 3
        seed(db)
        seed(db)  # repetir não duplica
        total = db.execute("SELECT COUNT(*) FROM dialogs").fetchone()[0]
        # 12 diálogos em inglês + 5 em alemão (seed_german_v1) = 17
        assert total >= 12, f"Esperado ≥12 diálogos, obteve {total}"
        assert db.execute("SELECT COUNT(*) FROM dialogs WHERE title = 'No restaurante'").fetchone()[0] == 1


def test_old_schema_is_migrated_keeping_data(tmp_path):
    path = str(tmp_path / "v1.db")
    init_db(path)
    with closing(connect(path)) as db:
        db.execute("ALTER TABLE words DROP COLUMN tag")  # simula o banco da versão anterior
        db.execute("INSERT INTO words(word, meaning_pt, created_at) VALUES('legado', 'x', '2026-01-01T00:00:00Z')")
        db.commit()
    init_db(path)
    with closing(connect(path)) as db:
        cols = {r["name"] for r in db.execute("PRAGMA table_info(words)")}
        assert "tag" in cols
        assert db.execute("SELECT meaning_pt FROM words WHERE word = 'legado'").fetchone()[0] == "x"


# --------------------------------------------------------------------------- role-play
def test_dialogs_list_reports_speakers(client):
    assert _dialog(client, "TI — Daily stand-up")["speakers"] == 2
    assert _dialog(client, "TI — Frases úteis para a daily")["speakers"] == 1


def test_roleplay_hides_my_lines_and_can_be_checked(client):
    d = _dialog(client, "TI — Daily stand-up")
    r = client.get(f"/api/roleplay/{d['id']}").json()
    assert r["speakers"] == ["Lead", "Developer"] and r["lines"] == []
    r = client.get(f"/api/roleplay/{d['id']}?role=Developer").json()
    assert [l["mine"] for l in r["lines"]] == [False, True, True, True, False, True]
    assert r["lines"][0]["en"] == "Good morning, everyone. Let's start the stand-up."
    mine = r["lines"][1]
    assert mine["en"] is None and mine["pt"].startswith("Ontem")  # só a dica em português
    # a fala do meu personagem é conferida digitando em inglês (pode usar contração)
    ok = client.post(f"/api/phrases/{mine['id']}/check", json={
        "direction": "pt_to_en", "answer": "yesterday i finished the login page and fixed two bugs"}).json()
    assert ok["correct"] is True
    bad = client.post(f"/api/phrases/{mine['id']}/check", json={
        "direction": "pt_to_en", "answer": "Yesterday I finish the login page and fixed two bugs."}).json()
    assert bad["correct"] is False


def test_roleplay_errors(client):
    d = _dialog(client, "TI — Daily stand-up")
    assert client.get(f"/api/roleplay/{d['id']}?role=Nobody").status_code == 422
    solo = _dialog(client, "TI — Frases úteis para a daily")
    assert client.get(f"/api/roleplay/{solo['id']}").status_code == 422
    assert client.get("/api/roleplay/99999").status_code == 404


# --------------------------------------------------------------------------- conversa livre com IA
def test_conversation_needs_ai(client):
    assert client.get("/api/conversation/scenarios").json()["ai_enabled"] is False
    r = client.post("/api/conversation/turn", json={"scenario_id": "daily"})
    assert r.status_code == 422 and "ANTHROPIC_API_KEY" in r.json()["detail"]


def test_conversation_flow_with_ai(ai_client, fake_llm):
    sc = ai_client.get("/api/conversation/scenarios").json()
    assert sc["ai_enabled"] is True and {"daily", "code_review", "incident", "interview"} <= {s["id"] for s in sc["scenarios"]}

    opening = ai_client.post("/api/conversation/turn", json={"scenario_id": "daily", "level": "A2"}).json()
    assert opening["reply"].startswith("Hi!") and opening["learned"] == 0
    call = fake_llm.chat_calls[-1]
    assert "stand-up" in call["role"] and call["level"] == "A2" and call["message"] == "" and call["history"] == []

    fake_llm.chat_result = {
        "reply": "Nice. Any blockers?", "reply_pt": "Legal. Algum bloqueio?",
        "correction": {"needs_fix": True, "corrected": "Yesterday I fixed a bug.", "summary": "Use o passado.",
                       "items": [{"you_wrote": "fix", "should_be": "fixed", "kind": "grammar", "explanation": "Passado."},
                                 {"you_wrote": "bug", "should_be": "bug", "kind": "portuguese", "explanation": ""}]},
    }
    history = [{"role": "partner", "text": opening["reply"]}]
    r = ai_client.post("/api/conversation/turn", json={
        "scenario_id": "daily", "history": history, "message": "Yesterday I fix a bug."}).json()
    assert r["correction"]["needs_fix"] is True and r["learned"] == 2
    assert fake_llm.chat_calls[-1]["history"] == history and fake_llm.chat_calls[-1]["message"] == "Yesterday I fix a bug."
    assert _word(ai_client, "fixed", filter="review")["in_review"] is True  # o que errou foi para a revisão


def test_conversation_errors(ai_client, fake_llm):
    assert ai_client.post("/api/conversation/turn", json={"scenario_id": "nope"}).status_code == 404
    h = [{"role": "partner", "text": "Hi!"}]
    assert ai_client.post("/api/conversation/turn", json={"scenario_id": "daily", "history": h}).status_code == 422
    big = [{"role": "partner", "text": "x"}] * 41
    assert ai_client.post("/api/conversation/turn", json={"scenario_id": "daily", "history": big, "message": "hi"}).status_code == 422
    assert ai_client.post("/api/conversation/turn", json={"scenario_id": "daily", "history": [{"role": "robot", "text": "x"}], "message": "hi"}).status_code == 422
    fake_llm.fail_chat = True
    assert ai_client.post("/api/conversation/turn", json={"scenario_id": "daily", "history": h, "message": "hi"}).status_code == 502


# --------------------------------------------------------------------------- revisão em 3 modos
def test_review_reverse_mode_shows_meaning_and_checks_word(client):
    w = _word(client, "blocker", tag="ti")
    nxt = client.get("/api/review/next?mode=reverse&tag=ti").json()
    assert nxt["mode"] == "reverse" and nxt["word"]["meaning_pt"] and nxt["word"]["tag"] == "ti"
    assert "meaning_pt" not in client.get("/api/review/next?mode=meaning").json()["word"]
    wrong = client.post(f"/api/review/{w['id']}/answer", json={"mode": "reverse", "answer": "blocked"}).json()
    assert wrong["correct"] is False and wrong["word"] == "blocker" and wrong["example"]
    ok = client.post(f"/api/review/{w['id']}/answer", json={"mode": "reverse", "answer": "  Blocker "}).json()
    assert ok["correct"] is True and ok["box"] == 1


def test_review_reverse_accepts_expressions(client):
    w = _word(client, "pull request", tag="ti")
    r = client.post(f"/api/review/{w['id']}/answer", json={"mode": "reverse", "answer": "Pull   request"}).json()
    assert r["correct"] is True


def test_review_listen_mode_works_without_a_saved_meaning(client):
    base = {m: client.get(f"/api/review/next?mode={m}").json()["remaining"] for m in ("meaning", "listen")}
    client.post("/api/vocab/import", json={"text": "Xylophone."})  # fora do glossário: sem significado
    after = {m: client.get(f"/api/review/next?mode={m}").json()["remaining"] for m in ("meaning", "listen")}
    assert after["meaning"] == base["meaning"] and after["listen"] == base["listen"] + 1
    w = _word(client, "xylophone")
    assert client.post(f"/api/review/{w['id']}/answer", json={"mode": "meaning", "answer": "x"}).status_code == 422
    assert client.post(f"/api/review/{w['id']}/answer", json={"mode": "listen", "answer": "xilophone"}).json()["correct"] is False
    assert client.post(f"/api/review/{w['id']}/answer", json={"mode": "listen", "answer": "Xylophone"}).json()["correct"] is True


def test_review_done_reports_words_missing_meaning(client):
    client.post("/api/vocab/import", json={"text": "Xylophone."})
    for w in client.get("/api/vocab?filter=review&limit=2000").json()["items"]:
        if w["word"] != "xylophone":
            client.patch(f"/api/vocab/{w['id']}", json={"in_review": False})
    done = client.get("/api/review/next?mode=meaning").json()
    assert done["done"] is True and done["pending_meanings"] == 1


def test_invalid_mode_is_rejected(client):
    assert client.get("/api/review/next?mode=banana").status_code == 422


def test_learning_and_learned_filters(client):
    w = _word(client, "blocker", tag="ti")
    assert w["word"] not in {x["word"] for x in client.get("/api/vocab?filter=learning&limit=500").json()["items"]}
    client.post(f"/api/review/{w['id']}/answer", json={"mode": "reverse", "answer": "blocker"})
    learning = {x["word"] for x in client.get("/api/vocab?filter=learning&limit=500").json()["items"]}
    assert "blocker" in learning
    for _ in range(3):
        client.post(f"/api/review/{w['id']}/answer", json={"mode": "reverse", "answer": "blocker"})
    learned = {x["word"] for x in client.get("/api/vocab?filter=learned&limit=500").json()["items"]}
    assert learned == {"blocker"}
    stats = client.get("/api/vocab/stats").json()
    assert stats["learned"] == 1 and stats["ti_learned"] == 1
    assert "blocker" not in {x["word"] for x in client.get("/api/vocab?filter=learning&limit=500").json()["items"]}
