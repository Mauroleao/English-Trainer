"""Rotas de idiomas suportados (Inglês, Alemão, etc.) e seleção do idioma ativo."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..db import SUPPORTED_LANGUAGES, get_active_language, set_active_language
from ..deps import get_db

router = APIRouter(prefix="/api/languages", tags=["idiomas"])


class SetLanguageIn(BaseModel):
    language: str


@router.get("")
def list_languages(db=Depends(get_db)):
    """Retorna os idiomas disponíveis, o idioma ativo e estatísticas por idioma."""
    active = get_active_language(db)
    result = []

    for code, info in SUPPORTED_LANGUAGES.items():
        dialog_cnt = db.execute("SELECT COUNT(*) FROM dialogs WHERE language = ?", (code,)).fetchone()[0]
        word_cnt = db.execute("SELECT COUNT(*) FROM words WHERE language = ?", (code,)).fetchone()[0]
        result.append({
            **info,
            "dialog_count": dialog_cnt,
            "word_count": word_cnt,
            "is_active": (code == active),
        })

    return {
        "active": active,
        "languages": result,
    }


@router.post("/active")
def switch_active_language(body: SetLanguageIn, db=Depends(get_db)):
    """Alterna o idioma de estudo ativo (ex: 'en' ou 'de')."""
    code = body.language.strip().lower()
    if code not in SUPPORTED_LANGUAGES:
        raise HTTPException(400, f"Idioma não suportado: {code}. Disponíveis: {list(SUPPORTED_LANGUAGES.keys())}")

    set_active_language(db, code)
    info = SUPPORTED_LANGUAGES[code]
    return {
        "ok": True,
        "active": code,
        "message": f"Idioma ativo alterado para {info['name']} ({info['native']}) {info['flag']}.",
    }
