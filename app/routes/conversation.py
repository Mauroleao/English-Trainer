"""Conversação: interpretar um diálogo (sem IA) e conversar livremente com a IA."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from ..deps import get_db, get_db_path, get_llm
from ..scenarios import BY_ID, SCENARIOS
from ..schemas import ChatTurnIn
from ..vocab import fill_missing_meanings, mark_difficult

router = APIRouter(prefix="/api", tags=["conversacao"])

# correções que indicam palavra/expressão que o aluno não sabia: entram na revisão
_LEARN_KINDS = {"portuguese", "vocabulary", "spelling", "missing", "grammar", "wrong"}


# --------------------------------------------------------------------------- interpretar um diálogo
@router.get("/roleplay/{dialog_id}")
def roleplay(dialog_id: int, role: Optional[str] = None, db=Depends(get_db)):
    """Escolha seu personagem: as falas dos outros são mostradas/ouvidas e as suas você responde em inglês.

    As falas do seu personagem vêm só com a dica em português (a resposta correta não é enviada).
    """
    d = db.execute("SELECT id, title FROM dialogs WHERE id = ?", (dialog_id,)).fetchone()
    if not d:
        raise HTTPException(404, "Diálogo não encontrado.")
    rows = db.execute(
        "SELECT id, speaker, en, pt FROM phrases WHERE dialog_id = ? ORDER BY position, id", (dialog_id,)
    ).fetchall()
    speakers = list(dict.fromkeys(r["speaker"] for r in rows if r["speaker"]))
    if len(speakers) < 2:
        raise HTTPException(422, "Este diálogo tem só um personagem. Use a aba Frases para praticá-lo.")
    if role is None:
        return {"dialog_id": d["id"], "title": d["title"], "speakers": speakers, "role": None, "lines": []}
    if role not in speakers:
        raise HTTPException(422, "Personagem inválido para este diálogo.")
    lines = []
    for r in rows:
        mine = r["speaker"] == role
        lines.append({"id": r["id"], "speaker": r["speaker"], "mine": mine, "pt": r["pt"], "en": None if mine else r["en"]})
    return {"dialog_id": d["id"], "title": d["title"], "speakers": speakers, "role": role, "lines": lines}


# --------------------------------------------------------------------------- conversa livre com a IA
@router.get("/conversation/scenarios")
def scenarios(llm=Depends(get_llm)):
    return {
        "ai_enabled": llm is not None,
        "scenarios": [{"id": s["id"], "title": s["title"], "description": s["description"]} for s in SCENARIOS],
    }


@router.post("/conversation/turn")
def conversation_turn(
    body: ChatTurnIn,
    background: BackgroundTasks,
    db=Depends(get_db),
    db_path: str = Depends(get_db_path),
    llm=Depends(get_llm),
):
    """Um turno: você escreve (ou fala), a IA responde em inglês e corrige o que você escreveu.

    O histórico fica no navegador; o servidor não guarda a conversa, só manda para a revisão o que você errou.
    """
    if llm is None:
        raise HTTPException(
            422,
            "A conversa livre precisa da IA. Defina ANTHROPIC_API_KEY e reinicie o servidor. "
            "Sem IA, use \"Interpretar diálogo\".",
        )
    scenario = BY_ID.get(body.scenario_id)
    if scenario is None:
        raise HTTPException(404, "Cenário não encontrado.")
    message = body.message.strip()
    if not message and body.history:
        raise HTTPException(422, "Escreva uma mensagem.")
    history = [m.model_dump() for m in body.history]
    try:
        result = llm.chat(scenario["role"], body.level, history, message)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"A IA não respondeu agora ({exc}). Tente de novo.") from exc

    learned = 0
    if message:
        words = [c["should_be"] for c in result["correction"]["items"] if c["kind"] in _LEARN_KINDS and c["should_be"]]
        if words:
            learned = mark_difficult(db, words)
            background.add_task(fill_missing_meanings, db_path, llm)
    return {**result, "learned": learned}
