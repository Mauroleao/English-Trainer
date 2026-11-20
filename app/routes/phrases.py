"""Diálogos e frases: mostra em inglês -> acertar em português -> inverte -> acertar em inglês."""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from ..db import Settings, now_iso
from ..deps import get_db, get_db_path, get_llm, get_settings
from ..schemas import CheckIn, DialogIn, PhraseIn, RevealIn
from ..seed import GLOSSARY
from ..textutil import check_answer
from ..vocab import add_words_from_text, fill_missing_meanings

router = APIRouter(prefix="/api", tags=["frases"])

MY_PHRASES_TITLE = "Minhas frases"


def _phrase_or_404(db, phrase_id: int):
    row = db.execute(
        "SELECT p.*, d.title AS dialog_title FROM phrases p JOIN dialogs d ON d.id = p.dialog_id WHERE p.id = ?",
        (phrase_id,),
    ).fetchone()
    if not row:
        raise HTTPException(404, "Frase não encontrada.")
    return row


def _variants(row, direction: str) -> tuple[list[str], str, str]:
    """(respostas aceitas, idioma da resposta, texto canônico)."""
    if direction == "en_to_pt":
        return [row["pt"], *json.loads(row["pt_alt"])], "pt", row["pt"]
    return [row["en"], *json.loads(row["en_alt"])], "en", row["en"]


def _bump(db, phrase_id: int, *, completed: int = 0, mistakes: int = 0) -> None:
    with db:
        db.execute(
            "INSERT INTO phrase_progress(phrase_id, completed, mistakes, last_completed) VALUES(?,?,?,?) "
            "ON CONFLICT(phrase_id) DO UPDATE SET completed = completed + excluded.completed, "
            "mistakes = mistakes + excluded.mistakes, "
            "last_completed = COALESCE(excluded.last_completed, last_completed)",
            (phrase_id, completed, mistakes, now_iso() if completed else None),
        )


# --------------------------------------------------------------------------- diálogos
@router.get("/dialogs")
def list_dialogs(db=Depends(get_db)):
    rows = db.execute(
        "SELECT d.id, d.title, d.level, d.description, d.builtin, COUNT(p.id) AS phrase_count, "
        "COALESCE(SUM(CASE WHEN pp.completed > 0 THEN 1 ELSE 0 END), 0) AS done "
        "FROM dialogs d LEFT JOIN phrases p ON p.dialog_id = d.id "
        "LEFT JOIN phrase_progress pp ON pp.phrase_id = p.id GROUP BY d.id ORDER BY d.id"
    ).fetchall()
    return [dict(r) for r in rows]


@router.get("/dialogs/{dialog_id}")
def get_dialog(dialog_id: int, db=Depends(get_db)):
    d = db.execute("SELECT * FROM dialogs WHERE id = ?", (dialog_id,)).fetchone()
    if not d:
        raise HTTPException(404, "Diálogo não encontrado.")
    lines = db.execute(
        "SELECT p.id, p.position, p.speaker, p.en, p.pt, COALESCE(pp.completed, 0) AS completed, "
        "COALESCE(pp.mistakes, 0) AS mistakes FROM phrases p "
        "LEFT JOIN phrase_progress pp ON pp.phrase_id = p.id WHERE p.dialog_id = ? ORDER BY p.position, p.id",
        (dialog_id,),
    ).fetchall()
    return {**dict(d), "lines": [dict(r) for r in lines]}


@router.post("/dialogs", status_code=201)
def create_dialog(
    body: DialogIn,
    background: BackgroundTasks,
    db=Depends(get_db),
    db_path: str = Depends(get_db_path),
    llm=Depends(get_llm),
):
    with db:
        cur = db.execute(
            "INSERT INTO dialogs(title, level, description, builtin, created_at) VALUES(?,?,?,0,?)",
            (body.title, body.level, body.description, now_iso()),
        )
        dialog_id = cur.lastrowid
        for pos, line in enumerate(body.lines):
            db.execute(
                "INSERT INTO phrases(dialog_id, position, speaker, en, pt, en_alt, pt_alt) VALUES(?,?,?,?,?,?,?)",
                (
                    dialog_id, pos, line.speaker or None, line.en, line.pt,
                    json.dumps([x for x in line.en_alt if x.strip()], ensure_ascii=False),
                    json.dumps([x for x in line.pt_alt if x.strip()], ensure_ascii=False),
                ),
            )
    words = add_words_from_text(db, "\n".join(l.en for l in body.lines), "dialog", dialog_id, glossary=GLOSSARY)
    if llm is not None:
        background.add_task(fill_missing_meanings, db_path, llm)
    return {"id": dialog_id, "phrases": len(body.lines), "words": words}


@router.delete("/dialogs/{dialog_id}", status_code=204)
def delete_dialog(dialog_id: int, db=Depends(get_db)):
    with db:
        cur = db.execute("DELETE FROM dialogs WHERE id = ?", (dialog_id,))
    if not cur.rowcount:
        raise HTTPException(404, "Diálogo não encontrado.")


@router.post("/phrases", status_code=201)
def add_phrase(
    body: PhraseIn,
    background: BackgroundTasks,
    db=Depends(get_db),
    db_path: str = Depends(get_db_path),
    llm=Depends(get_llm),
):
    """Adiciona uma frase solta (vai para 'Minhas frases' se nenhum diálogo for indicado)."""
    dialog_id: Optional[int] = body.dialog_id
    if dialog_id is None:
        row = db.execute("SELECT id FROM dialogs WHERE title = ? AND builtin = 0", (MY_PHRASES_TITLE,)).fetchone()
        if row:
            dialog_id = row["id"]
        else:
            with db:
                dialog_id = db.execute(
                    "INSERT INTO dialogs(title, level, description, builtin, created_at) VALUES(?,?,?,0,?)",
                    (MY_PHRASES_TITLE, None, "Frases que você adicionou.", now_iso()),
                ).lastrowid
    elif not db.execute("SELECT 1 FROM dialogs WHERE id = ?", (dialog_id,)).fetchone():
        raise HTTPException(404, "Diálogo não encontrado.")
    pos = db.execute("SELECT COALESCE(MAX(position), -1) + 1 FROM phrases WHERE dialog_id = ?", (dialog_id,)).fetchone()[0]
    with db:
        phrase_id = db.execute(
            "INSERT INTO phrases(dialog_id, position, speaker, en, pt) VALUES(?,?,?,?,?)",
            (dialog_id, pos, None, body.en, body.pt),
        ).lastrowid
    words = add_words_from_text(db, body.en, "dialog", dialog_id, glossary=GLOSSARY)
    if llm is not None:
        background.add_task(fill_missing_meanings, db_path, llm)
    return {"id": phrase_id, "dialog_id": dialog_id, "words": words}


# --------------------------------------------------------------------------- prática
@router.get("/practice/next")
def next_phrase(dialog_id: Optional[int] = None, exclude: Optional[int] = None, db=Depends(get_db)):
    """Escolhe a próxima frase: as menos praticadas primeiro (em ordem no diálogo, ou sorteadas em 'todas')."""
    where, args = [], []
    if dialog_id is not None:
        where.append("p.dialog_id = ?")
        args.append(dialog_id)
    base = (
        "SELECT p.id, p.dialog_id, p.speaker, p.en, d.title AS dialog_title, "
        "COALESCE(pp.completed, 0) AS completed FROM phrases p JOIN dialogs d ON d.id = p.dialog_id "
        "LEFT JOIN phrase_progress pp ON pp.phrase_id = p.id"
    )
    order = " ORDER BY COALESCE(pp.completed, 0) ASC, " + ("p.position ASC" if dialog_id is not None else "RANDOM()")
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    row = None
    if exclude is not None:
        row = db.execute(base + clause + (" AND" if where else " WHERE") + " p.id != ?" + order + " LIMIT 1", [*args, exclude]).fetchone()
    if row is None:
        row = db.execute(base + clause + order + " LIMIT 1", args).fetchone()
    if row is None:
        raise HTTPException(404, "Nenhuma frase encontrada. Escolha outro diálogo ou adicione frases.")
    return {
        "id": row["id"],
        "dialog_id": row["dialog_id"],
        "dialog_title": row["dialog_title"],
        "speaker": row["speaker"],
        "prompt": row["en"],
        "direction": "en_to_pt",
        "times_completed": row["completed"],
    }


@router.post("/phrases/{phrase_id}/check")
def check_phrase(phrase_id: int, body: CheckIn, db=Depends(get_db), settings: Settings = Depends(get_settings)):
    row = _phrase_or_404(db, phrase_id)
    accepted, lang, canonical = _variants(row, body.direction)
    res = check_answer(
        body.answer, accepted, lang=lang,
        ignore_accents=settings.ignore_accents, strict_exact=settings.strict_exact,
    )
    if res.correct:
        if body.direction == "pt_to_en":
            _bump(db, phrase_id, completed=1)
    else:
        _bump(db, phrase_id, mistakes=1)
    out = {
        "correct": res.correct,
        "marks": [{"text": m.text, "status": m.status} for m in res.marks],
        "missing": res.missing,
        "similarity": res.similarity,
        "format_issue": res.format_issue,
        "stage_complete": res.correct and body.direction == "pt_to_en",
    }
    if res.correct:
        out["canonical"] = canonical
        out["en"] = row["en"]
        out["pt"] = row["pt"]
    return out


@router.post("/phrases/{phrase_id}/reveal")
def reveal_phrase(phrase_id: int, body: RevealIn, db=Depends(get_db)):
    """Mostra a resposta (conta como erro). O aluno ainda precisa digitá-la para avançar."""
    row = _phrase_or_404(db, phrase_id)
    _, _, canonical = _variants(row, body.direction)
    _bump(db, phrase_id, mistakes=1)
    return {"answer": canonical}
