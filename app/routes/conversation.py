"""Conversação: interpretar um diálogo (sem IA) e conversar livremente com a IA."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from ..ai import extract_json
from ..db import get_active_language
from ..deps import get_db, get_db_path, get_llm
from ..scenarios import BY_ID, SCENARIOS
from ..schemas import ChatTurnIn, CoachReportIn, GenerateDialogIn
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
        language = get_active_language(db)
        result = llm.chat(scenario["role"], body.level, history, message, lang=language)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"A IA não respondeu agora ({exc}). Tente de novo.") from exc

    learned = 0
    if message:
        words = [c["should_be"] for c in result["correction"]["items"] if c["kind"] in _LEARN_KINDS and c["should_be"]]
        if words:
            learned = mark_difficult(db, words)
            background.add_task(fill_missing_meanings, db_path, llm)

    fluency_feedback = None
    if body.response_time_seconds is not None and body.response_time_seconds > 0:
        sec = round(body.response_time_seconds, 1)
        if sec < 3.5:
            verdict = "⚡ Excelente agilidade! Resposta rápida e fluente."
            badge = "fast"
        elif sec < 8.0:
            verdict = "👍 Bom tempo de reação."
            badge = "good"
        else:
            verdict = "⏱️ Tente formular a frase direto em inglês para diminuir pausas e acelerar a fluência."
            badge = "slow"
        fluency_feedback = {"seconds": sec, "verdict": verdict, "badge": badge}

    return {**result, "learned": learned, "fluency": fluency_feedback}


COACH_SYSTEM = (
    "You are an encouraging English coach for software developers. "
    "Analyze the conversation history. Explain everything in simple, practical, kid-friendly Brazilian Portuguese "
    "(lúdico e mastigado, super acessível e encorajador). "
    "Reply with ONE JSON object and nothing else:\n"
    "{\n"
    '  "overall_score": 85,\n'
    '  "summary": "parágrafo encorajador e amigável em português",\n'
    '  "kid_friendly_rule": "uma regra de ouro explicada com uma analogia simples e divertida do cotidiano",\n'
    '  "vocabulary_upgrades": [\n'
    '    {"you_said": "palavra básica usada", "better": "opção mais sênior e natural", "why": "explicação curta em português"}\n'
    "  ],\n"
    '  "star_method_coaching": {\n'
    '    "situation": "como contextualizar",\n'
    '    "task": "o desafio a ser resolvido",\n'
    '    "action": "a ação tomada",\n'
    '    "result": "o impacto / resultado positivo",\n'
    '    "example_speech": "frase modelo completa e fluente em inglês"\n'
    "  }\n"
    "}"
)


@router.post("/conversation/coach-report")
def coach_report(body: CoachReportIn, llm=Depends(get_llm)):
    """Gera um relatório de desempenho com método STAR, upgrades de vocabulário e dicas lúdicas."""
    if llm is None:
        raise HTTPException(
            422,
            "O relatório do coach precisa de um provedor de IA configurado em Ajustes.",
        )
    lines = [f"{'Partner' if h.role == 'partner' else 'Learner'}: {h.text}" for h in body.history]
    user_prompt = f"<scenario>{body.scenario_id}</scenario>\n<history>\n" + "\n".join(lines) + "\n</history>"
    try:
        raw = llm._ask(COACH_SYSTEM, user_prompt, max_tokens=1500)
        return extract_json(raw)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"Não foi possível gerar o relatório do coach ({exc}).") from exc


DIALOG_GEN_SYSTEM = (
    "You generate realistic, friendly English dialogues for Brazilian learners. "
    "Generate a 6 to 8 line dialogue about the requested topic. "
    "Language must be natural English at CEFR level {level}. "
    "Reply with ONE JSON object and nothing else:\n"
    "{\n"
    '  "title": "título curto e chamativo em português",\n'
    '  "description": "uma frase em português descrevendo a situação de forma simples",\n'
    '  "lines": [\n'
    '    {"speaker": "Alex", "en": "...", "pt": "..."},\n'
    '    {"speaker": "Sam", "en": "...", "pt": "..."}\n'
    "  ]\n"
    "}"
)


@router.post("/conversation/generate-dialog")
def generate_dialog(body: GenerateDialogIn, db=Depends(get_db), llm=Depends(get_llm)):
    """Gera um diálogo sob demanda sobre qualquer assunto e salva no banco de dados."""
    if llm is None:
        raise HTTPException(
            422,
            "A criação de diálogos precisa de uma IA configurada em Ajustes.",
        )
    language = get_active_language(db)
    if language == "de":
        system = (
            "You generate realistic, friendly German dialogues for Brazilian learners. "
            f"Generate a 6 to 8 line dialogue about the requested topic at CEFR level {body.level}. "
            'Reply with ONE JSON object and nothing else: '
            '{"title":"título curto em português","description":"descrição curta em português","lines":[{"speaker":"Name","en":"fala em alemão","pt":"tradução em português"}]}'
        )
    else:
        system = DIALOG_GEN_SYSTEM.replace("{level}", body.level)
    prompt = f"Topic to generate: {body.topic}"
    try:
        raw = llm._ask(system, prompt, max_tokens=1500)
        data = extract_json(raw)
        title = str(data.get("title") or body.topic).strip()
        desc = str(data.get("description") or f"Diálogo sobre {body.topic}").strip()
        lines = data.get("lines") or []
        if not lines:
            raise ValueError("Nenhuma linha gerada.")

        with db:
            cur = db.execute(
                "INSERT INTO dialogs(title, level, description, builtin, created_at, language) VALUES(?,?,?,0,datetime('now'),?)",
                (f"✨ {title}", body.level, desc, language),
            )
            dialog_id = cur.lastrowid
            for i, line in enumerate(lines):
                db.execute(
                    "INSERT INTO phrases(dialog_id, position, speaker, en, pt, language) VALUES(?,?,?,?,?,?)",
                    (dialog_id, i, line.get("speaker", "Colega"), line["en"].strip(), line["pt"].strip(), language),
                )
        return {"dialog_id": dialog_id, "title": f"✨ {title}", "line_count": len(lines)}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"Erro ao gerar diálogo sob demanda ({exc}).") from exc

