"""Textos: você coloca um texto em português, tenta escrevê-lo em inglês e só passa ao acertar."""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from ..db import Settings, get_active_language, now_iso
from ..deps import get_db, get_db_path, get_llm, get_settings
from ..evaluation import evaluate_attempt
from ..schemas import AttemptIn, TextIn, TextPatch
from ..seed import GLOSSARY
from ..vocab import add_words_from_text, fill_missing_meanings, mark_difficult

router = APIRouter(prefix="/api/texts", tags=["textos"])

# tipos de correção que indicam que o aluno não sabia a palavra -> vão para a revisão
_LEARN_KINDS = {"portuguese", "wrong", "vocabulary", "spelling", "missing", "grammar", "meaning"}


def _text_or_404(db, text_id: int):
    row = db.execute("SELECT * FROM texts WHERE id = ?", (text_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Texto não encontrado.")
    return row


def _summary(row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"] or row["pt_text"][:40],
        "status": row["status"],
        "attempts": row["attempts"],
        "created_at": row["created_at"],
        "solved_at": row["solved_at"],
        "snippet": row["pt_text"][:140],
    }


@router.get("")
def list_texts(db=Depends(get_db)):
    active = get_active_language(db)
    return [_summary(r) for r in db.execute(
        "SELECT * FROM texts WHERE language = ? ORDER BY id DESC",
        (active,),
    )]


@router.post("", status_code=201)
def create_text(body: TextIn, db=Depends(get_db), llm=Depends(get_llm)):
    active = get_active_language(db)
    en_text = (body.en_reference or "").strip()
    if not en_text:
        if llm is None:
            raise HTTPException(
                422,
                "Para criar a correção preciso de uma versão em inglês. Informe-a no campo de referência "
                "ou configure ANTHROPIC_API_KEY para eu traduzir o texto por você.",
            )
        try:
            en_text = llm.translate(body.pt_text).strip()
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(502, f"Não consegui traduzir o texto agora ({exc}). Tente de novo ou informe a referência.") from exc
    with db:
        text_id = db.execute(
            "INSERT INTO texts(title, pt_text, en_text, status, created_at, language) VALUES(?,?,?,'pending',?,?)",
            (body.title, body.pt_text, en_text, now_iso(), active),
        ).lastrowid
    return _summary(_text_or_404(db, text_id))


@router.get("/{text_id}")
def get_text(text_id: int, db=Depends(get_db)):
    row = _text_or_404(db, text_id)
    last = db.execute(
        "SELECT attempt FROM text_attempts WHERE text_id = ? ORDER BY id DESC LIMIT 1", (text_id,)
    ).fetchone()
    return {
        **_summary(row),
        "pt_text": row["pt_text"],
        "last_attempt": last["attempt"] if last else "",
        # a versão correta só aparece depois que o texto foi resolvido
        "solved_text": row["solved_text"] if row["status"] == "solved" else None,
    }


@router.patch("/{text_id}")
def patch_text(text_id: int, body: TextPatch, db=Depends(get_db)):
    """Troca a versão de referência (útil no modo sem IA, para aceitar outra tradução correta)."""
    _text_or_404(db, text_id)
    with db:
        db.execute("UPDATE texts SET en_text = ? WHERE id = ?", (body.en_reference, text_id))
    return {"ok": True}


@router.delete("/{text_id}", status_code=204)
def delete_text(text_id: int, db=Depends(get_db)):
    _text_or_404(db, text_id)
    with db:
        db.execute("DELETE FROM texts WHERE id = ?", (text_id,))


@router.post("/{text_id}/attempt")
def attempt_text(
    text_id: int,
    body: AttemptIn,
    background: BackgroundTasks,
    db=Depends(get_db),
    db_path: str = Depends(get_db_path),
    settings: Settings = Depends(get_settings),
    llm=Depends(get_llm),
):
    row = _text_or_404(db, text_id)
    result = evaluate_attempt(
        pt_text=row["pt_text"], en_text=row["en_text"], attempt=body.attempt, settings=settings, llm=llm
    )
    accepted = result["accepted"]
    first_solve = accepted and row["status"] != "solved"
    with db:
        db.execute("UPDATE texts SET attempts = attempts + 1 WHERE id = ?", (text_id,))
        db.execute(
            "INSERT INTO text_attempts(text_id, attempt, accepted, feedback, created_at) VALUES(?,?,?,?,?)",
            (text_id, body.attempt, int(accepted), json.dumps(result, ensure_ascii=False), now_iso()),
        )
        if first_solve:
            db.execute(
                "UPDATE texts SET status = 'solved', solved_at = ?, solved_text = ? WHERE id = ?",
                (now_iso(), body.attempt, text_id),
            )

    # o que o aluno errou/não sabia entra direto na revisão
    if not accepted:
        learn = [c["should_be"] for c in result["corrections"] if c["kind"] in _LEARN_KINDS and c["should_be"]]
        if learn:
            mark_difficult(db, learn, text_id)
    # texto resolvido: todas as palavras do texto em inglês são separadas para o vocabulário
    words: Optional[dict] = None
    if first_solve:
        words = add_words_from_text(db, body.attempt, "text", text_id, glossary=GLOSSARY)
    if llm is not None and (first_solve or not accepted):
        background.add_task(fill_missing_meanings, db_path, llm)

    return {**result, "words": words, "solved_text": body.attempt if accepted else None}
