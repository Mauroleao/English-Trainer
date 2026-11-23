"""Curso de gramática A1→C1, revisão de gramática e teste de nível."""
from __future__ import annotations

import random
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from ..course import loader, progress
from ..course.validate import LEVELS
from ..db import now_iso, set_setting
from ..deps import get_db
from ..vocab import add_words_from_text

router = APIRouter(prefix="/api", tags=["curso"])


class CheckIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=False)
    ex_id: str = Field(..., max_length=40)
    answer: Any = Field(None)


class QuizIn(BaseModel):
    answers: dict[str, Any] = Field(default_factory=dict)


class PlacementIn(BaseModel):
    answers: dict[str, Any] = Field(default_factory=dict)


def _lesson_or_404(lesson_id: str) -> dict:
    les = loader.content()["lesson_by_id"].get(lesson_id)
    if not les:
        raise HTTPException(404, "Lição não encontrada.")
    return les


def _touch(db, lesson_id: str) -> None:
    with db:
        db.execute("INSERT OR IGNORE INTO lesson_progress(lesson_id, status, started_at) VALUES(?, 'started', ?)", (lesson_id, now_iso()))


# --------------------------------------------------------------------------- currículo
@router.get("/course")
def curriculum(db=Depends(get_db)):
    st = progress.lesson_status(db)
    rec = progress.recommended_lesson(db)
    levels = []
    for lv in LEVELS:
        units: dict[str, list] = {}
        for les in loader.content()["lessons"]:
            if les["level"] != lv:
                continue
            s = st.get(les["id"])
            item = {**loader.lesson_summary(les), "status": (s or {}).get("status", "new"), "score": (s or {}).get("best_score", 0)}
            units.setdefault(les["unit"], []).append(item)
        lp = next(p for p in progress.level_progress(db) if p["level"] == lv)
        levels.append({**lp, "units": [{"name": n, "lessons": ls} for n, ls in units.items()]})
    return {"levels": levels, "recommended": rec["id"] if rec else None, "start_level": progress.start_level(db),
            "current_level": progress.current_level(db)}


@router.get("/course/lessons/{lesson_id}")
def get_lesson(lesson_id: str, db=Depends(get_db)):
    les = _lesson_or_404(lesson_id)
    _touch(db, lesson_id)
    ids = [l["id"] for l in loader.content()["lessons"]]
    i = ids.index(lesson_id)
    st = progress.lesson_status(db).get(lesson_id, {})
    return {**loader.public_lesson(les), "status": st.get("status", "started"), "best_score": st.get("best_score", 0),
            "prev": ids[i - 1] if i else None, "next": ids[i + 1] if i + 1 < len(ids) else None}


@router.post("/course/lessons/{lesson_id}/check")
def check_practice(lesson_id: str, body: CheckIn, db=Depends(get_db)):
    """Corrige um exercício da prática guiada (com explicação na hora)."""
    _lesson_or_404(lesson_id)
    ex = loader.content()["exercises"].get(body.ex_id)
    if not ex or ex["_lesson"] != lesson_id or ex["_part"] != "practice":
        raise HTTPException(404, "Exercício não encontrado.")
    res = loader.grade(ex, body.answer)
    with db:
        progress.count_stat(db, lesson_id, res["correct"])
        if not res["correct"] and not res.get("empty"):
            progress.add_grammar_item(db, ex["id"], lesson_id)
    progress.add_study(db, items=1)
    return res


def _install_words(db, les: dict) -> int:
    n = 0
    with db:
        for w in les["words"]:
            word = w["word"].strip().lower()
            cur = db.execute(
                "INSERT OR IGNORE INTO words(word, meaning_pt, is_common, in_review, created_at) VALUES(?,?,0,1,?)",
                (word, w["pt"], now_iso()),
            )
            n += cur.rowcount
            db.execute("UPDATE words SET meaning_pt = ? WHERE word = ? AND (meaning_pt IS NULL OR meaning_pt = '')", (w["pt"], word))
            wid = db.execute("SELECT id FROM words WHERE word = ?", (word,)).fetchone()["id"]
            sentence = next((e["en"] for s in les["steps"] for e in s.get("examples", []) if word in e["en"].lower()), None)
            if sentence:
                db.execute("INSERT OR IGNORE INTO word_contexts(word_id, source_type, source_id, sentence) VALUES(?, 'lesson', NULL, ?)", (wid, sentence))
    return n


@router.post("/course/lessons/{lesson_id}/quiz")
def submit_quiz(lesson_id: str, body: QuizIn, db=Depends(get_db)):
    les = _lesson_or_404(lesson_id)
    results, right = [], 0
    for ex in les["quiz"]:
        res = loader.grade(ex, body.answers.get(ex["id"]))
        right += res["correct"]
        results.append({"id": ex["id"], **res})
    total = len(les["quiz"])
    score = round(100 * right / total)
    passed = score >= loader.PASS_SCORE
    _touch(db, lesson_id)
    words_added = 0
    first_time = False
    with db:
        row = db.execute("SELECT status FROM lesson_progress WHERE lesson_id = ?", (lesson_id,)).fetchone()
        first_time = passed and row["status"] != "done"
        db.execute("UPDATE lesson_progress SET quiz_runs = quiz_runs + 1, best_score = MAX(best_score, ?) WHERE lesson_id = ?", (score, lesson_id))
        if passed:
            db.execute("UPDATE lesson_progress SET status = 'done', completed_at = COALESCE(completed_at, ?) WHERE lesson_id = ?", (now_iso(), lesson_id))
        for ex, r in zip(les["quiz"], results):
            progress.count_stat(db, lesson_id, r["correct"])
            if not r["correct"]:
                progress.add_grammar_item(db, ex["id"], lesson_id)
            elif passed and ex["type"] != "choice":  # acertou: revisita daqui a 2 dias
                progress.add_grammar_item(db, ex["id"], lesson_id, box=1, days=2)
    if first_time:
        words_added = _install_words(db, les)
    progress.add_study(db, items=total)
    ids = [l["id"] for l in loader.content()["lessons"]]
    i = ids.index(lesson_id)
    return {"score": score, "passed": passed, "right": right, "total": total, "needed": loader.PASS_SCORE,
            "results": results, "words_added": words_added, "next": ids[i + 1] if passed and i + 1 < len(ids) else None}


@router.post("/course/lessons/{lesson_id}/words")
def add_lesson_words(lesson_id: str, db=Depends(get_db)):
    return {"added": _install_words(db, _lesson_or_404(lesson_id))}


# --------------------------------------------------------------------------- revisão de gramática
@router.get("/grammar/stats")
def grammar_stats(db=Depends(get_db)):
    total = db.execute("SELECT COUNT(*) FROM grammar_items").fetchone()[0]
    mastered = db.execute("SELECT COUNT(*) FROM grammar_items WHERE box >= 4").fetchone()[0]
    return {"due": progress.due_grammar(db), "total": total, "mastered": mastered}


@router.get("/grammar/next")
def grammar_next(exclude: Optional[str] = None, db=Depends(get_db)):
    row = db.execute(
        "SELECT * FROM grammar_items WHERE next_review <= ? AND ex_id != ? ORDER BY wrong DESC, next_review LIMIT 1",
        (now_iso(), exclude or ""),
    ).fetchone()
    if not row:
        nxt = db.execute("SELECT MIN(next_review) FROM grammar_items").fetchone()[0]
        return {"item": None, "total": db.execute("SELECT COUNT(*) FROM grammar_items").fetchone()[0], "next_review": nxt}
    ex = loader.content()["exercises"].get(row["ex_id"])
    if not ex:
        raise HTTPException(500, "Exercício removido do curso.")
    les = loader.content()["lesson_by_id"][ex["_lesson"]]
    return {"item": {**loader.public_exercise(ex), "lesson_id": les["id"], "lesson_title": les["title"], "box": row["box"]},
            "due": progress.due_grammar(db)}


@router.post("/grammar/answer")
def grammar_answer(body: CheckIn, db=Depends(get_db)):
    ex = loader.content()["exercises"].get(body.ex_id)
    if not ex:
        raise HTTPException(404, "Exercício não encontrado.")
    res = loader.grade(ex, body.answer)
    with db:
        info = progress.grade_grammar_item(db, ex["id"], ex["_lesson"], res["correct"])
        progress.count_stat(db, ex["_lesson"], res["correct"])
    progress.add_study(db, items=1)
    return {**res, **info}


# --------------------------------------------------------------------------- teste de nível
@router.get("/placement")
def placement_items():
    return {"items": [{**loader.public_exercise(i), "level": i["level"]} for i in loader.content()["placement"]]}


@router.post("/placement")
def placement_submit(body: PlacementIn, db=Depends(get_db)):
    items = loader.content()["placement"]
    per: dict[str, list[bool]] = {lv: [] for lv in LEVELS}
    detail = []
    for it in items:
        res = loader.grade(it, body.answers.get(it["id"]))
        per[it["level"]].append(res["correct"])
        detail.append({"id": it["id"], "level": it["level"], "correct": res["correct"], "expected": res["expected"], "explain": res["explain"]})
    scores = {lv: sum(v) for lv, v in per.items()}
    totals = {lv: len(v) for lv, v in per.items()}
    passed_levels = []
    for lv in LEVELS:  # para no primeiro nível com menos de 4 acertos em 6
        if totals[lv] and scores[lv] >= 4:
            passed_levels.append(lv)
        else:
            break
    start = LEVELS[min(len(passed_levels), len(LEVELS) - 1)]
    estimated = passed_levels[-1] if passed_levels else "Iniciante"
    set_setting(db, "start_level", start)
    set_setting(db, "placement_level", estimated)
    set_setting(db, "placement_done", "1")
    return {"estimated_level": estimated, "start_level": start, "scores": scores, "totals": totals, "detail": detail,
            "all_passed": len(passed_levels) == len(LEVELS)}


@router.put("/course/start-level/{level}")
def set_start_level(level: str, db=Depends(get_db)):
    level = level.upper()
    if level not in LEVELS:
        raise HTTPException(422, "Nível inválido.")
    set_setting(db, "start_level", level)
    return {"start_level": level}


# --------------------------------------------------------------------------- leitura por nível
class ReadingCheckIn(BaseModel):
    answers: dict[str, Any] = Field(default_factory=dict)


@router.get("/reading")
def reading_list(db=Depends(get_db)):
    done = {r["reading_id"]: dict(r) for r in db.execute("SELECT * FROM reading_progress")}
    return {"texts": [
        {"id": r["id"], "level": r["level"], "title": r["title"], "topic": r["topic"],
         "done": bool(done.get(r["id"], {}).get("done_at")), "score": done.get(r["id"], {}).get("best_score", 0)}
        for r in loader.content()["readings"]], "current_level": progress.current_level(db)}


def _reading_or_404(rid: str) -> dict:
    r = loader.content()["reading_by_id"].get(rid)
    if not r:
        raise HTTPException(404, "Texto não encontrado.")
    return r


@router.get("/reading/{rid}")
def reading_get(rid: str):
    return loader.public_reading(_reading_or_404(rid))


@router.post("/reading/{rid}/check")
def reading_check(rid: str, body: ReadingCheckIn, db=Depends(get_db)):
    r = _reading_or_404(rid)
    results = []
    for q in r["questions"]:
        res = loader.grade(q, body.answers.get(q["id"]))
        results.append({"id": q["id"], **res})
    right = sum(x["correct"] for x in results)
    score = round(100 * right / len(results))
    with db:
        db.execute("INSERT OR IGNORE INTO reading_progress(reading_id) VALUES(?)", (rid,))
        db.execute("UPDATE reading_progress SET runs = runs + 1, best_score = MAX(best_score, ?), "
                   "done_at = COALESCE(done_at, ?) WHERE reading_id = ?", (score, now_iso() if score >= 60 else None, rid))
    progress.add_study(db, items=len(results))
    return {"score": score, "right": right, "total": len(results), "results": results, "pt": r["pt"]}


@router.post("/reading/{rid}/words")
def reading_words(rid: str, db=Depends(get_db)):
    """Separa todas as palavras do texto para a revisão (as do vocabulário do texto já vêm com tradução)."""
    r = _reading_or_404(rid)
    glossary = {v["word"]: v["pt"] for v in r["vocab"] if " " not in v["word"]}
    res = add_words_from_text(db, r["text"], "reading", None, glossary=glossary)
    with db:
        for v in r["vocab"]:  # expressões e palavras-chave: sempre na revisão, com tradução
            w = v["word"].strip().lower()
            db.execute("INSERT OR IGNORE INTO words(word, meaning_pt, is_common, in_review, created_at) VALUES(?,?,0,1,?)", (w, v["pt"], now_iso()))
            db.execute("UPDATE words SET in_review = 1 WHERE word = ?", (w,))
    return res
