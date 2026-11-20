"""Avaliação do texto digitado em inglês (com trechos em português para o que o aluno não sabe).

Regras:
1. Igual à referência (palavra por palavra) -> aceito, sem gastar chamada de IA.
2. Com IA: ela julga se é uma tradução correta equivalente e explica os erros. Mesmo assim,
   qualquer palavra que ainda esteja em português impede a aprovação.
3. Sem IA (ou se ela falhar): comparação local com a referência, apontando o que está em
   português, errado, faltando ou sobrando.
"""
from __future__ import annotations

import logging
from typing import Optional

from .db import Settings
from .textutil import Check, check_answer, has_portuguese, make_pt_flag

log = logging.getLogger(__name__)


def _result(check: Check, *, accepted: bool, engine: str, summary: str = "", note: str = "", corrections=None) -> dict:
    return {
        "accepted": accepted,
        "marks": [{"text": m.text, "status": m.status} for m in check.marks],
        "corrections": check.corrections if corrections is None else corrections,
        "missing": check.missing,
        "similarity": check.similarity,
        "format_issue": check.format_issue,
        "engine": engine,
        "summary": summary,
        "note": note,
    }


def evaluate_attempt(
    *, pt_text: str, en_text: str, attempt: str, settings: Settings, llm: Optional[object]
) -> dict:
    flag = make_pt_flag(pt_text, en_text, settings.ignore_accents)
    local = check_answer(
        attempt,
        [en_text],
        lang="en",
        ignore_accents=settings.ignore_accents,
        strict_exact=settings.strict_exact,
        pt_flag=flag,
    )
    if local.correct:
        return _result(local, accepted=True, engine="local", summary="Perfeito! Texto correto.")
    if local.format_issue:
        return _result(local, accepted=False, engine="local", summary="Quase! As palavras estão certas, confira maiúsculas, pontuação e espaços.")

    if llm is None:
        return _result(
            local,
            accepted=False,
            engine="local",
            note="Modo sem IA: só aceito a versão de referência. Com ANTHROPIC_API_KEY, traduções equivalentes também são aceitas.",
        )

    try:
        ai = llm.evaluate(pt_text, en_text, attempt)
    except Exception as exc:  # noqa: BLE001
        log.warning("IA indisponível na correção, usando comparação local: %s", exc)
        return _result(
            local,
            accepted=False,
            engine="local",
            note="A IA não respondeu agora; usei a comparação local com a referência.",
        )

    still_portuguese = has_portuguese(attempt, flag)
    accepted = ai["accepted"] and not still_portuguese

    variants = [en_text] + ([ai["corrected_text"]] if ai["corrected_text"] else [])
    shown = check_answer(
        attempt, variants, lang="en", ignore_accents=settings.ignore_accents, pt_flag=flag
    )
    if accepted:
        for m in shown.marks:
            m.status = "ok"
        return _result(shown, accepted=True, engine="ai", summary=ai["summary"] or "Correto!", corrections=[])

    corrections = ai["items"] or shown.corrections
    summary = ai["summary"]
    if ai["accepted"] and still_portuguese:
        summary = "Ainda há palavras em português no texto. Troque-as pelo inglês correto."
    return _result(shown, accepted=False, engine="ai", summary=summary, corrections=corrections)
