from app.course import loader
from app.course.validate import validate_dir, CONTENT_DIR


def test_all_course_content_is_valid():
    errs, stats = validate_dir(CONTENT_DIR)
    assert errs == []
    assert stats["lessons"] == 72


def test_content_counts():
    c = loader.content()
    assert len(c["lessons"]) == 72
    assert len(c["readings"]) == 20
    assert len(c["placement"]) == 30


def test_curriculum_and_lesson_hide_answers(client):
    cur = client.get("/api/course").json()
    assert [l["total"] for l in cur["levels"]] == [12, 14, 16, 16, 14]
    assert cur["recommended"] == "a1-01"
    les = client.get("/api/course/lessons/a1-01").json()
    blob = str(les["practice"]) + str(les["quiz"])
    assert "explain" not in blob and "answers" not in blob and "'answer'" not in blob
    assert client.get("/api/course/lessons/zz-99").status_code == 404


def test_order_exercise_is_shuffled_but_stable(client):
    a = client.get("/api/course/lessons/a1-01").json()["quiz"]
    b = client.get("/api/course/lessons/a1-01").json()["quiz"]
    order = next(q for q in a if q["type"] == "order")
    assert sorted(order["words"]) == sorted(["We", "are", "at", "work"])
    assert order["words"] != ["We", "are", "at", "work"]
    assert a == b


def _correct(ex):
    t = ex["type"]
    return ex["answer"] if t == "choice" else " ".join(ex["words"]) if t == "order" else ex["en"] if t == "listen" else ex["answers"][0]


def test_practice_wrong_answer_goes_to_grammar_review(client):
    ex = loader.content()["exercises"]["a1-01-p8"]
    r = client.post("/api/course/lessons/a1-01/check", json={"ex_id": ex["id"], "answer": "He are a tester"}).json()
    assert not r["correct"] and r["expected"] == "He is a tester." and r["explain"]
    nxt = client.get("/api/grammar/next").json()["item"]
    assert nxt["id"] == "a1-01-p8"
    ok = client.post("/api/grammar/answer", json={"ex_id": "a1-01-p8", "answer": "He is a tester."}).json()
    assert ok["correct"] and ok["box"] == 1
    # acertou: sai da fila de hoje
    assert client.get("/api/grammar/next").json()["item"] is None


def test_practice_rejects_quiz_exercise(client):
    r = client.post("/api/course/lessons/a1-01/check", json={"ex_id": "a1-01-q1", "answer": 2})
    assert r.status_code == 404


def test_quiz_pass_completes_lesson_and_adds_words(client):
    les = loader.content()["lesson_by_id"]["a1-01"]
    answers = {ex["id"]: _correct(ex) for ex in les["quiz"]}
    r = client.post("/api/course/lessons/a1-01/quiz", json={"answers": answers}).json()
    assert r["passed"] and r["score"] == 100 and r["next"] == "a1-02" and r["words_added"] > 0
    cur = client.get("/api/course").json()
    assert cur["recommended"] == "a1-02"
    first = cur["levels"][0]["units"][0]["lessons"][0]
    assert first["status"] == "done" and first["score"] == 100
    words = client.get("/api/vocab?q=developer").json()
    assert any(w["word"] == "developer" and w["meaning_pt"] for w in (words if isinstance(words, list) else words["items"]))
    again = client.post("/api/course/lessons/a1-01/quiz", json={"answers": answers}).json()
    assert again["words_added"] == 0  # só instala na primeira aprovação


def test_quiz_fail_keeps_lesson_open(client):
    r = client.post("/api/course/lessons/a1-02/quiz", json={"answers": {}}).json()
    assert not r["passed"] and r["score"] == 0
    assert client.get("/api/course").json()["recommended"] == "a1-01"
    assert client.get("/api/grammar/stats").json()["total"] > 0


def test_placement_levels(client):
    items = loader.content()["placement"]
    answers = {i["id"]: _correct(i) for i in items if i["level"] in ("A1", "A2")}
    r = client.post("/api/placement", json={"answers": answers}).json()
    assert r["estimated_level"] == "A2" and r["start_level"] == "B1"
    assert client.get("/api/course").json()["recommended"] == "b1-01"
    allr = client.post("/api/placement", json={"answers": {i["id"]: _correct(i) for i in items}}).json()
    assert allr["all_passed"] and allr["start_level"] == "C1"
    none = client.post("/api/placement", json={"answers": {}}).json()
    assert none["estimated_level"] == "Iniciante" and none["start_level"] == "A1"
    assert "answer" not in str(client.get("/api/placement").json())


def test_reading_flow(client):
    lst = client.get("/api/reading").json()["texts"]
    assert len(lst) == 20
    r = client.get("/api/reading/r-a1-01").json()
    assert "pt" not in r and "answer" not in str(r["questions"])
    full = loader.content()["reading_by_id"]["r-a1-01"]
    res = client.post("/api/reading/r-a1-01/check", json={"answers": {q["id"]: q["answer"] for q in full["questions"]}}).json()
    assert res["score"] == 100 and res["pt"]
    assert any(t["id"] == "r-a1-01" and t["done"] for t in client.get("/api/reading").json()["texts"])
    w = client.post("/api/reading/r-a1-01/words").json()
    assert w["total"] > 0


def test_pronunciation_score(client):
    ok = client.post("/api/pronunciation/compare", json={"target": "I am a developer.", "spoken": "i am a developer"}).json()
    assert ok["score"] == 100 and ok["perfect"]
    part = client.post("/api/pronunciation/compare", json={"target": "I am a developer.", "spoken": "i am developer"}).json()
    assert 50 <= part["score"] < 100
    assert client.post("/api/pronunciation/compare", json={"target": "I am a developer.", "spoken": ""}).json()["score"] == 0
    s = client.get("/api/pronunciation/next?level=A1").json()
    assert s["en"] and s["level"] == "A1"
    assert client.get("/api/pronunciation/next?level=Z9").status_code == 422


def test_plan_streak_and_progress(client):
    p = client.get("/api/plan/today").json()
    assert p["goal_minutes"] == 30 and p["streak"]["current"] == 0 and any(t["kind"] == "lesson" for t in p["tasks"])
    client.put("/api/plan", json={"daily_minutes": 60})
    assert client.get("/api/plan").json()["daily_minutes"] == 60
    assert client.put("/api/plan", json={"daily_minutes": 1}).status_code == 422
    client.post("/api/study/ping", json={"seconds": 120, "tz_offset_min": -180})
    p = client.get("/api/plan/today").json()
    assert p["done_minutes"] == 2 and p["streak"]["current"] == 1 and p["streak"]["studied_today"]
    prog = client.get("/api/progress").json()
    assert prog["lessons_total"] == 72 and len(prog["days"]) == 14 and prog["days"][-1]["minutes"] == 2
    assert prog["estimate"]["hours_to_c1"] > 0 and len(prog["estimate"]["scenarios"]) == 4
    assert client.post("/api/study/ping", json={"seconds": 9999}).status_code == 422


def test_start_level_setting(client):
    assert client.put("/api/course/start-level/b2").json()["start_level"] == "B2"
    assert client.get("/api/course").json()["recommended"] == "b2-01"
    assert client.put("/api/course/start-level/zz").status_code == 422
