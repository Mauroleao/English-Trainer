"""Rotina de estudo: plano do dia, tempo ativo, sequência, painel de progresso e pronúncia."""
from __future__ import annotations

import random
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..course import loader, progress
from ..course.validate import LEVELS
from ..db import get_int, get_setting, now_iso, set_setting
from ..deps import get_db
from ..schemas import EarGymCheckIn
from ..textutil import check_answer

router = APIRouter(prefix="/api", tags=["rotina"])


class PingIn(BaseModel):
    seconds: int = Field(30, ge=1, le=120)
    tz_offset_min: Optional[int] = None


class PlanIn(BaseModel):
    daily_minutes: int = Field(..., ge=5, le=480)


class PronIn(BaseModel):
    target: str = Field(..., min_length=1, max_length=400)
    spoken: str = Field(..., max_length=400)


@router.post("/study/ping")
def study_ping(body: PingIn, db=Depends(get_db)):
    progress.set_tz_offset(db, body.tz_offset_min)
    progress.add_study(db, seconds=body.seconds)
    return {"ok": True}


@router.get("/plan")
def plan_get(db=Depends(get_db)):
    return {"daily_minutes": get_int(db, "daily_minutes", progress.DEFAULT_GOAL_MIN),
            "start_level": progress.start_level(db), "placement_done": get_setting(db, "placement_done") == "1",
            "placement_level": get_setting(db, "placement_level")}


@router.put("/plan")
def plan_put(body: PlanIn, db=Depends(get_db)):
    set_setting(db, "daily_minutes", body.daily_minutes)
    return {"daily_minutes": body.daily_minutes}


@router.get("/plan/today")
def plan_today(db=Depends(get_db)):
    goal = get_int(db, "daily_minutes", progress.DEFAULT_GOAL_MIN)
    day = progress.today(db)
    row = db.execute("SELECT * FROM study_days WHERE day = ?", (day,)).fetchone()
    done_min = round((row["seconds"] if row else 0) / 60)
    rec = progress.recommended_lesson(db)
    st = progress.lesson_status(db)
    tasks = []
    dg, dw = progress.due_grammar(db), progress.due_words(db)
    if dw:
        tasks.append({"kind": "words", "title": f"Revisar {dw} palavra(s)", "detail": "Revisão espaçada do vocabulário.", "minutes": min(10, max(3, dw // 3))})
    if dg:
        tasks.append({"kind": "grammar", "title": f"Revisar {dg} exercício(s) de gramática", "detail": "Itens que você errou ou já estudou.", "minutes": min(10, max(3, dg // 2))})
    if rec:
        tasks.append({"kind": "lesson", "title": f"Lição {rec['id'].upper()}: {rec['title']}", "detail": rec["goal"], "lesson_id": rec["id"], "minutes": rec["minutes"],
                      "started": rec["id"] in st})
    lvl = progress.current_level(db)
    rd = {r["reading_id"] for r in db.execute("SELECT reading_id FROM reading_progress WHERE done_at IS NOT NULL")}
    nxt = next((r for r in loader.content()["readings"] if r["level"] == lvl and r["id"] not in rd), None)
    if nxt:
        tasks.append({"kind": "reading", "title": f"Leitura: {nxt['title']}", "detail": nxt["topic"], "reading_id": nxt["id"], "minutes": 8})
    tasks.append({"kind": "pronunciation", "title": "Pronúncia: 5 frases", "detail": "Fale em voz alta e receba uma nota.", "minutes": 5})
    return {"goal_minutes": goal, "done_minutes": done_min, "percent": min(100, round(100 * done_min / goal)),
            "streak": progress.streak(db), "tasks": tasks, "level": lvl, "estimate": progress.estimate(db),
            "placement_done": get_setting(db, "placement_done") == "1"}


@router.get("/progress")
def progress_overview(db=Depends(get_db)):
    c = loader.content()
    levels = progress.level_progress(db)
    lessons_done = sum(p["done"] for p in levels)
    total_seconds = db.execute("SELECT COALESCE(SUM(seconds),0) FROM study_days").fetchone()[0]
    w = db.execute("SELECT COUNT(*) AS total, COALESCE(SUM(CASE WHEN box >= 4 THEN 1 ELSE 0 END),0) AS learned, "
                   "COALESCE(SUM(CASE WHEN correct + wrong > 0 THEN 1 ELSE 0 END),0) AS practiced FROM words WHERE in_review = 1").fetchone()
    g = db.execute("SELECT COUNT(*) AS total, COALESCE(SUM(CASE WHEN box >= 4 THEN 1 ELSE 0 END),0) AS mastered FROM grammar_items").fetchone()
    weak = []
    for r in db.execute("SELECT * FROM lesson_stats WHERE wrong > 0"):
        tot = r["correct"] + r["wrong"]
        if tot >= 3:
            les = c["lesson_by_id"].get(r["lesson_id"])
            if les:
                weak.append({"lesson_id": les["id"], "title": les["title"], "unit": les["unit"], "level": les["level"],
                             "accuracy": round(100 * r["correct"] / tot), "attempts": tot})
    weak.sort(key=lambda x: (x["accuracy"], -x["attempts"]))
    reads = db.execute("SELECT COUNT(*) FROM reading_progress WHERE done_at IS NOT NULL").fetchone()[0]
    pron = db.execute("SELECT COUNT(*) AS n, COALESCE(AVG(score),0) AS avg FROM pronunciation_log").fetchone()
    return {
        "levels": levels, "lessons_done": lessons_done, "lessons_total": len(c["lessons"]),
        "total_hours": round(total_seconds / 3600, 1), "streak": progress.streak(db),
        "words": {"total": w["total"], "learned": w["learned"], "practiced": w["practiced"]},
        "grammar": {"total": g["total"], "mastered": g["mastered"], "due": progress.due_grammar(db)},
        "weak": weak[:5], "days": progress.minutes_by_day(db, 14), "estimate": progress.estimate(db),
        "readings": {"done": reads, "total": len(c["readings"])},
        "pronunciation": {"attempts": pron["n"], "average": round(pron["avg"])},
        "current_level": progress.current_level(db),
    }


# --------------------------------------------------------------------------- pronúncia
@router.get("/pronunciation/next")
def pronunciation_next(level: Optional[str] = None, exclude: Optional[str] = None, db=Depends(get_db)):
    lv = (level or progress.current_level(db)).upper()
    if lv not in LEVELS:
        raise HTTPException(422, "Nível inválido.")
    pool = []
    for les in loader.content()["lessons"]:
        if les["level"] == lv:
            for s in les["steps"]:
                for e in s.get("examples", []):
                    n = len(e["en"].split())
                    if 3 <= n <= 14 and e["en"] != exclude:
                        pool.append({"en": e["en"], "pt": e["pt"], "lesson": les["title"]})
    if not pool:
        raise HTTPException(404, "Sem frases para este nível.")
    return {**random.choice(pool), "level": lv}


@router.post("/pronunciation/compare")
def pronunciation_compare(body: PronIn, db=Depends(get_db)):
    """Nota de 0 a 100 comparando o que o reconhecimento de voz entendeu com a frase-alvo."""
    chk = check_answer(body.spoken, [body.target], lang="en")
    score = 100 if chk.correct else int(round(chk.similarity * 100))
    if not body.spoken.strip():
        score = 0
    with db:
        db.execute("INSERT INTO pronunciation_log(target, spoken, score, created_at) VALUES(?,?,?,?)", (body.target, body.spoken, score, now_iso()))
    progress.add_study(db, items=1)
    verdict = "excelente" if score >= 90 else "bom" if score >= 75 else "quase" if score >= 50 else "tente de novo"
    return {"score": score, "verdict": verdict, "marks": [{"text": m.text, "status": m.status} for m in chk.marks],
            "missing": chk.missing, "perfect": chk.correct}


# --------------------------------------------------------------------------- Ear Gym
@router.get("/eargym/next")
def eargym_next(level: Optional[str] = None):
    """Retorna uma frase com uma palavra oculta para treino auditivo focado."""
    lv = level.upper() if level and level.upper() in LEVELS else "A1"
    pool = []
    for les in loader.content()["lessons"]:
        if les["level"] == lv:
            for s in les["steps"]:
                for e in s.get("examples", []):
                    words = [w for w in e["en"].split() if len(w.strip(".,?!\"'")) >= 3]
                    if len(words) >= 3:
                        pool.append((e["en"], e["pt"], les["title"]))
    if not pool:
        raise HTTPException(404, "Sem frases para este nível.")

    en, pt, lesson = random.choice(pool)
    tokens = en.split()
    valid_indices = [i for i, t in enumerate(tokens) if len(t.strip(".,?!\"'")) >= 3]
    chosen_idx = random.choice(valid_indices)
    raw_token = tokens[chosen_idx]
    clean_target = raw_token.strip(".,?!\"'")
    masked_token = raw_token.replace(clean_target, "______")
    masked_sentence = " ".join(tokens[:chosen_idx] + [masked_token] + tokens[chosen_idx + 1:])

    return {
        "level": lv,
        "en_full": en,
        "masked": masked_sentence,
        "target": clean_target,
        "pt": pt,
        "lesson": lesson,
        "hint": f"Palavra com {len(clean_target)} letras",
    }


@router.post("/eargym/check")
def eargym_check(body: EarGymCheckIn, db=Depends(get_db)):
    """Verifica a palavra digitada/falada no treino Ear Gym."""
    chk = check_answer(body.answer, [body.target], lang="en")
    progress.add_study(db, items=1)
    return {
        "correct": chk.correct,
        "target": body.target,
        "answer": body.answer,
        "verdict": "Certo! Ouvido de ouro! 🎯" if chk.correct else f"Não foi dessa vez. A palavra certa era '{body.target}'.",
    }


# --------------------------------------------------------------------------- Conquistas (Gamificação)
@router.get("/achievements")
def get_achievements(db=Depends(get_db)):
    """Retorna o quadro de conquistas desbloqueadas do aluno."""
    lessons_done = db.execute("SELECT COUNT(*) as c FROM lesson_progress WHERE status = 'done'").fetchone()["c"]
    pron_done = db.execute("SELECT COUNT(*) as c FROM pronunciation_log").fetchone()["c"]
    words_learned = db.execute("SELECT COUNT(*) as c FROM words WHERE correct > 0").fetchone()["c"]
    streak_data = progress.streak(db)
    streak_days = streak_data.get("current", 0) if isinstance(streak_data, dict) else int(streak_data or 0)
    dialogs_done = db.execute("SELECT COUNT(DISTINCT dialog_id) as c FROM phrases p JOIN phrase_progress pp ON p.id = pp.phrase_id WHERE pp.completed = 1").fetchone()["c"]



    badges = [
        {"id": "first_step", "title": "Primeiro Passo", "emoji": "🌱", "desc": "Completou sua primeira lição do curso.", "unlocked": lessons_done >= 1, "progress": f"{min(lessons_done, 1)}/1"},
        {"id": "ear_master", "title": "Ouvido Atento", "emoji": "🎧", "desc": "Treinou 5 frases no microfone ou no Ear Gym.", "unlocked": pron_done >= 5, "progress": f"{min(pron_done, 5)}/5"},
        {"id": "vocab_builder", "title": "Construtor de Vocabulário", "emoji": "📚", "desc": "Aprendeu 20 palavras na repetição espaçada.", "unlocked": words_learned >= 20, "progress": f"{min(words_learned, 20)}/20"},
        {"id": "dialog_pro", "title": "Dev Comunicativo", "emoji": "💬", "desc": "Concluiu todas as falas de pelo menos 1 diálogo.", "unlocked": dialogs_done >= 1, "progress": f"{min(dialogs_done, 1)}/1"},
        {"id": "streak_ninja", "title": "Constância Ninja", "emoji": "🔥", "desc": "Estudou por 3 dias seguidos.", "unlocked": streak_days >= 3, "progress": f"{min(streak_days, 3)}/3 dias"},
        {"id": "course_hero", "title": "Mestre da Gramática", "emoji": "🏆", "desc": "Concluiu 10 lições de gramática.", "unlocked": lessons_done >= 10, "progress": f"{min(lessons_done, 10)}/10"},
    ]
    return {"badges": badges, "total_unlocked": sum(1 for b in badges if b["unlocked"]), "total": len(badges)}

