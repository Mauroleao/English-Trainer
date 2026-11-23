"""Rotina de estudo: tempo ativo, sequência (streak), revisão de gramática, estimativas."""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from ..db import get_int, iso_in, now_iso, set_setting
from ..vocab import BOX_DAYS, MAX_BOX
from .loader import content, level_after
from .validate import LEVELS

DEFAULT_GOAL_MIN = 30
# horas de estudo total (curso + revisão + leitura + prática) para consolidar cada nível
LEVEL_HOURS = {"A1": 80, "A2": 100, "B1": 150, "B2": 200, "C1": 250}


# --------------------------------------------------------------------------- datas
def local_now(db: sqlite3.Connection) -> datetime:
    off = get_int(db, "tz_offset_min", -180)  # padrão: horário de Brasília
    return datetime.now(timezone.utc) + timedelta(minutes=off)


def today(db: sqlite3.Connection) -> str:
    return local_now(db).strftime("%Y-%m-%d")


def set_tz_offset(db: sqlite3.Connection, minutes: Optional[int]) -> None:
    if minutes is not None and -840 <= minutes <= 840:
        set_setting(db, "tz_offset_min", minutes)


# --------------------------------------------------------------------------- tempo e atividade
def add_study(db: sqlite3.Connection, *, seconds: int = 0, items: int = 0) -> None:
    day = today(db)
    with db:
        db.execute("INSERT OR IGNORE INTO study_days(day) VALUES(?)", (day,))
        db.execute("UPDATE study_days SET seconds = seconds + ?, items = items + ? WHERE day = ?", (seconds, items, day))


def minutes_by_day(db: sqlite3.Connection, days: int) -> list[dict]:
    end = local_now(db).date()
    rows = {r["day"]: r for r in db.execute("SELECT * FROM study_days")}
    out = []
    for i in range(days - 1, -1, -1):
        d = (end - timedelta(days=i)).isoformat()
        r = rows.get(d)
        out.append({"day": d, "minutes": round((r["seconds"] if r else 0) / 60), "items": r["items"] if r else 0})
    return out


def streak(db: sqlite3.Connection) -> dict:
    """Dias seguidos com estudo. Hoje ainda sem estudo não quebra a sequência."""
    active = {r["day"] for r in db.execute("SELECT day FROM study_days WHERE seconds >= 60 OR items >= 3")}
    d = local_now(db).date()
    studied_today = d.isoformat() in active
    if not studied_today:
        d -= timedelta(days=1)
    n = 0
    while d.isoformat() in active:
        n += 1
        d -= timedelta(days=1)
    best = 0
    run = 0
    prev: Optional[date] = None
    for s in sorted(active):
        cur = date.fromisoformat(s)
        run = run + 1 if prev and (cur - prev).days == 1 else 1
        best = max(best, run)
        prev = cur
    return {"current": n, "best": max(best, n), "studied_today": studied_today}


# --------------------------------------------------------------------------- lições
def lesson_status(db: sqlite3.Connection) -> dict[str, dict]:
    return {r["lesson_id"]: dict(r) for r in db.execute("SELECT * FROM lesson_progress")}


def start_level(db: sqlite3.Connection) -> str:
    from ..db import get_setting
    lv = get_setting(db, "start_level", "A1")
    return lv if lv in LEVELS else "A1"


def recommended_lesson(db: sqlite3.Connection) -> Optional[dict]:
    """Primeira lição não concluída a partir do nível inicial (o aluno pode estudar em qualquer ordem)."""
    st = lesson_status(db)
    c = content()
    start = LEVELS.index(start_level(db))
    for les in c["lessons"]:
        if LEVELS.index(les["level"]) >= start and st.get(les["id"], {}).get("status") != "done":
            return les
    for les in c["lessons"]:
        if st.get(les["id"], {}).get("status") != "done":
            return les
    return None


def level_progress(db: sqlite3.Connection) -> list[dict]:
    st = lesson_status(db)
    out = []
    for lv in LEVELS:
        ls = [l for l in content()["lessons"] if l["level"] == lv]
        done = sum(1 for l in ls if st.get(l["id"], {}).get("status") == "done")
        out.append({"level": lv, "done": done, "total": len(ls), "percent": round(100 * done / len(ls)) if ls else 0})
    return out


def current_level(db: sqlite3.Connection) -> str:
    """Nível em que o aluno está estudando agora: o do primeiro nível a partir do inicial ainda incompleto."""
    prog = {p["level"]: p for p in level_progress(db)}
    for lv in LEVELS[LEVELS.index(start_level(db)):]:
        if prog[lv]["done"] < prog[lv]["total"]:
            return lv
    return "C1"


# --------------------------------------------------------------------------- revisão de gramática (Leitner)
def add_grammar_item(db: sqlite3.Connection, ex_id: str, lesson_id: str, *, box: int = 0, days: float = 0, minutes: float = 0) -> None:
    db.execute(
        "INSERT OR IGNORE INTO grammar_items(ex_id, lesson_id, box, next_review) VALUES(?,?,?,?)",
        (ex_id, lesson_id, box, iso_in(days=days, minutes=minutes)),
    )


def grade_grammar_item(db: sqlite3.Connection, ex_id: str, lesson_id: str, correct: bool) -> dict:
    add_grammar_item(db, ex_id, lesson_id)
    row = db.execute("SELECT * FROM grammar_items WHERE ex_id = ?", (ex_id,)).fetchone()
    if correct:
        box = min(row["box"] + 1, MAX_BOX)
        db.execute("UPDATE grammar_items SET box=?, next_review=?, correct=correct+1 WHERE ex_id=?",
                   (box, iso_in(days=BOX_DAYS[box]), ex_id))
    else:
        db.execute("UPDATE grammar_items SET box=0, next_review=?, wrong=wrong+1 WHERE ex_id=?", (iso_in(minutes=5), ex_id))
    row = db.execute("SELECT * FROM grammar_items WHERE ex_id = ?", (ex_id,)).fetchone()
    return {"box": row["box"], "next_review": row["next_review"]}


def count_stat(db: sqlite3.Connection, lesson_id: str, correct: bool) -> None:
    db.execute("INSERT OR IGNORE INTO lesson_stats(lesson_id) VALUES(?)", (lesson_id,))
    db.execute(f"UPDATE lesson_stats SET {'correct' if correct else 'wrong'} = {'correct' if correct else 'wrong'} + 1 WHERE lesson_id = ?", (lesson_id,))


def due_grammar(db: sqlite3.Connection) -> int:
    return db.execute("SELECT COUNT(*) FROM grammar_items WHERE next_review <= ?", (now_iso(),)).fetchone()[0]


def due_words(db: sqlite3.Connection) -> int:
    return db.execute(
        "SELECT COUNT(*) FROM words WHERE in_review = 1 AND meaning_pt IS NOT NULL AND meaning_pt != '' AND (next_review IS NULL OR next_review <= ?)",
        (now_iso(),),
    ).fetchone()[0]


# --------------------------------------------------------------------------- estimativa
def estimate(db: sqlite3.Connection) -> dict:
    """Quanto falta para o próximo nível e para o C1, no ritmo atual (ou na meta diária)."""
    lp = {p["level"]: p for p in level_progress(db)}
    goal = get_int(db, "daily_minutes", DEFAULT_GOAL_MIN)
    last7 = minutes_by_day(db, 7)
    avg = sum(d["minutes"] for d in last7) / 7
    pace = max(avg, 0) if avg >= 5 else goal  # sem histórico suficiente, usa a meta
    cur = current_level(db)
    rem_cur = (1 - lp[cur]["done"] / lp[cur]["total"]) * LEVEL_HOURS[cur] if lp[cur]["total"] else 0
    rem_all = rem_cur
    for lv in LEVELS[LEVELS.index(cur) + 1:]:
        rem_all += LEVEL_HOURS[lv]
    def days(h): return int(round(h * 60 / pace)) if pace > 0 else None
    nxt = level_after(cur)
    return {
        "current_level": cur, "next_level": nxt, "pace_minutes": round(pace), "goal_minutes": goal,
        "hours_to_next": round(rem_cur), "days_to_next": days(rem_cur) if nxt else 0,
        "hours_to_c1": round(rem_all), "days_to_c1": days(rem_all),
        "scenarios": [{"minutes": m, "days_to_c1": int(round(rem_all * 60 / m)), "months_to_c1": round(rem_all * 60 / m / 30, 1)} for m in (30, 60, 120, 180)],
        "note": "As lições levam cerca de 30 horas no total; o restante das horas vem de revisão, leitura, escuta e prática diária. Estudar mais minutos por dia é o que encurta o prazo.",
    }
