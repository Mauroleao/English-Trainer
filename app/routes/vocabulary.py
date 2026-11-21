"""Vocabulário (palavras separadas dos textos em inglês) e revisão espaçada."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from ..db import Settings, now_iso
from ..deps import get_db, get_db_path, get_llm, get_settings
from ..schemas import ImportIn, ReviewAnswerIn, WordPatch
from ..seed import GLOSSARY
from ..vocab import add_words_from_text, check_meaning, check_word, fill_missing_meanings, grade_word

router = APIRouter(prefix="/api", tags=["vocabulario"])

_EXAMPLE = "(SELECT sentence FROM word_contexts c WHERE c.word_id = w.id ORDER BY c.id LIMIT 1)"


def _word_dict(r) -> dict:
    return {
        "id": r["id"],
        "word": r["word"],
        "meaning_pt": r["meaning_pt"] or "",
        "is_common": bool(r["is_common"]),
        "in_review": bool(r["in_review"]),
        "box": r["box"],
        "correct": r["correct"],
        "wrong": r["wrong"],
        "next_review": r["next_review"],
        "tag": r["tag"],
        "example": r["example"] if "example" in r.keys() else None,
    }


@router.post("/vocab/import", status_code=201)
def import_text(body: ImportIn, background: BackgroundTasks, db=Depends(get_db),
                db_path: str = Depends(get_db_path), llm=Depends(get_llm)):
    """Cola um texto em inglês: todas as palavras são separadas e ficam disponíveis para revisão."""
    res = add_words_from_text(db, body.text, "import", None, glossary=GLOSSARY)
    if res["total"] == 0:
        raise HTTPException(422, "Não encontrei palavras nesse texto.")
    if llm is not None:
        background.add_task(fill_missing_meanings, db_path, llm)
    missing = db.execute("SELECT COUNT(*) FROM words WHERE meaning_pt IS NULL OR meaning_pt = ''").fetchone()[0]
    return {**res, "without_meaning": missing, "ai_will_translate": llm is not None}


@router.get("/vocab")
def list_words(
    q: str = "",
    filter: str = Query("all", pattern="^(all|review|common|due|no_meaning|hard|learned|learning)$"),
    tag: Optional[str] = Query(None, pattern="^ti$"),
    limit: int = Query(500, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    db=Depends(get_db),
):
    where, args = [], []
    if q.strip():
        where.append("w.word LIKE ?")
        args.append(f"{q.strip().lower()}%")
    if filter == "review":
        where.append("w.in_review = 1")
    elif filter == "common":
        where.append("w.is_common = 1")
    elif filter == "due":
        where.append("w.in_review = 1 AND (w.next_review IS NULL OR w.next_review <= ?)")
        args.append(now_iso())
    elif filter == "no_meaning":
        where.append("(w.meaning_pt IS NULL OR w.meaning_pt = '')")
    elif filter == "hard":
        where.append("w.wrong > w.correct")
    elif filter == "learned":  # acertou várias vezes seguidas (caixa 4 em diante = revisão a cada 8+ dias)
        where.append("w.box >= 4")
    elif filter == "learning":  # já treinou, mas ainda não dominou
        where.append("w.in_review = 1 AND w.box < 4 AND (w.correct > 0 OR w.wrong > 0)")
    if tag:
        where.append("w.tag = 'ti'")
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    total = db.execute(f"SELECT COUNT(*) FROM words w{clause}", args).fetchone()[0]
    rows = db.execute(
        f"SELECT w.*, {_EXAMPLE} AS example FROM words w{clause} ORDER BY w.word LIMIT ? OFFSET ?",
        [*args, limit, offset],
    ).fetchall()
    return {"total": total, "items": [_word_dict(r) for r in rows]}


@router.get("/vocab/stats")
def vocab_stats(db=Depends(get_db)):
    now = now_iso()
    row = db.execute(
        "SELECT COUNT(*) AS total, "
        "COALESCE(SUM(in_review), 0) AS in_review, "
        "COALESCE(SUM(CASE WHEN in_review = 1 AND meaning_pt IS NOT NULL AND meaning_pt != '' "
        "AND (next_review IS NULL OR next_review <= ?) THEN 1 ELSE 0 END), 0) AS due, "
        "COALESCE(SUM(CASE WHEN box >= 4 THEN 1 ELSE 0 END), 0) AS learned, "
        "COALESCE(SUM(CASE WHEN meaning_pt IS NULL OR meaning_pt = '' THEN 1 ELSE 0 END), 0) AS no_meaning, "
        "COALESCE(SUM(CASE WHEN in_review = 1 AND box < 4 AND (correct > 0 OR wrong > 0) THEN 1 ELSE 0 END), 0) AS learning, "
        "COALESCE(SUM(CASE WHEN tag = 'ti' THEN 1 ELSE 0 END), 0) AS ti_total, "
        "COALESCE(SUM(CASE WHEN tag = 'ti' AND box >= 4 THEN 1 ELSE 0 END), 0) AS ti_learned "
        "FROM words",
        (now,),
    ).fetchone()
    return dict(row)


@router.patch("/vocab/{word_id}")
def patch_word(word_id: int, body: WordPatch, db=Depends(get_db)):
    row = db.execute("SELECT id FROM words WHERE id = ?", (word_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Palavra não encontrada.")
    with db:
        if body.in_review is not None:
            db.execute("UPDATE words SET in_review = ? WHERE id = ?", (int(body.in_review), word_id))
        if body.meaning_pt is not None:
            db.execute("UPDATE words SET meaning_pt = ? WHERE id = ?", (body.meaning_pt or None, word_id))
    return _word_dict(db.execute(f"SELECT w.*, {_EXAMPLE} AS example FROM words w WHERE w.id = ?", (word_id,)).fetchone())


@router.post("/vocab/fill-meanings")
def fill_meanings(db_path: str = Depends(get_db_path), llm=Depends(get_llm)):
    if llm is None:
        raise HTTPException(422, "A tradução automática precisa de ANTHROPIC_API_KEY configurada.")
    return {"filled": fill_missing_meanings(db_path, llm)}


# --------------------------------------------------------------------------- revisão
# modos: meaning = vê a palavra, digita o significado | reverse = vê o significado, digita a palavra
#        listen  = ouve a palavra (o navegador fala) e digita o que ouviu
def _reviewable(mode: str, tag: Optional[str]) -> str:
    cond = "w.in_review = 1 AND (w.next_review IS NULL OR w.next_review <= ?)"
    if mode != "listen":  # ouvir e digitar não precisa de significado salvo
        cond += " AND w.meaning_pt IS NOT NULL AND w.meaning_pt != ''"
    if tag:
        cond += " AND w.tag = 'ti'"
    return cond


_MODE = Query("meaning", pattern="^(meaning|reverse|listen)$")
_TAG = Query(None, pattern="^ti$")


@router.get("/review/next")
def review_next(mode: str = _MODE, tag: Optional[str] = _TAG, db=Depends(get_db)):
    now = now_iso()
    cond = _reviewable(mode, tag)
    remaining = db.execute(f"SELECT COUNT(*) FROM words w WHERE {cond}", (now,)).fetchone()[0]
    row = db.execute(
        f"SELECT w.*, {_EXAMPLE} AS example FROM words w WHERE {cond} "
        "ORDER BY (w.next_review IS NULL), w.next_review, w.wrong DESC, w.id LIMIT 1",
        (now,),
    ).fetchone()
    if row is None:
        later = _reviewable(mode, tag).replace("(w.next_review IS NULL OR w.next_review <= ?)", "w.next_review > ?")
        nxt = db.execute(f"SELECT MIN(w.next_review) FROM words w WHERE {later}", (now,)).fetchone()[0]
        pending = db.execute(
            "SELECT COUNT(*) FROM words WHERE in_review = 1 AND (meaning_pt IS NULL OR meaning_pt = '')"
        ).fetchone()[0]
        return {"done": True, "next_due": nxt, "remaining": 0, "pending_meanings": pending}
    word = {"id": row["id"], "word": row["word"], "example": row["example"], "box": row["box"], "tag": row["tag"]}
    if mode == "reverse":  # aqui o significado é o enunciado
        word["meaning_pt"] = row["meaning_pt"]
    return {"done": False, "remaining": remaining, "mode": mode, "word": word}


@router.post("/review/{word_id}/answer")
def review_answer(word_id: int, body: ReviewAnswerIn, db=Depends(get_db), settings: Settings = Depends(get_settings)):
    row = db.execute(
        f"SELECT w.*, {_EXAMPLE} AS example FROM words w WHERE w.id = ?", (word_id,)
    ).fetchone()
    if not row:
        raise HTTPException(404, "Palavra não encontrada.")
    if body.mode != "listen" and not (row["meaning_pt"] or "").strip():
        raise HTTPException(422, "Essa palavra ainda não tem significado salvo.")
    if body.mode == "meaning":
        correct = check_meaning(body.answer, row["meaning_pt"], settings)
    else:
        correct = check_word(body.answer, row["word"])
    with db:
        updated = grade_word(db, word_id, correct)
    return {
        "correct": correct,
        "word": row["word"],
        "meaning_pt": row["meaning_pt"] or "",
        "example": row["example"],
        "box": updated["box"],
        "next_review": updated["next_review"],
    }
