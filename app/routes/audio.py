"""Rotas de áudio: TTS (Text-to-Speech) com cache local no disco."""
from __future__ import annotations

import hashlib
import os
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Response

router = APIRouter(prefix="/api/audio", tags=["audio"])

CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "audio_cache"


def _get_cache_path(text: str, speed: float) -> Path:
    key = hashlib.md5(f"{text.strip().lower()}_{speed:.2f}".encode("utf-8")).hexdigest()
    return CACHE_DIR / f"{key}.mp3"


@router.get("/tts")
def get_tts(text: str = Query(..., min_length=1, max_length=600), speed: float = Query(1.0, ge=0.5, le=1.5)):
    """Gera ou recupera do cache o áudio MP3 em inglês natural para a frase solicitada."""
    cleaned = text.strip()
    if not cleaned:
        raise HTTPException(400, "Texto vazio.")

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = _get_cache_path(cleaned, speed)

    # 1. Se já está no cache local, retorna imediatamente sem chamada de rede
    if cache_file.is_file():
        try:
            data = cache_file.read_bytes()
            if len(data) > 200:
                return Response(content=data, media_type="audio/mpeg", headers={"Cache-Control": "public, max-age=604800"})
        except Exception:
            pass

    # 2. Busca do serviço TTS
    url = f"https://translate.google.com/translate_tts?ie=UTF-8&tl=en&client=tw-ob&q={urllib.parse.quote(cleaned)}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko)"})
    try:
        with urllib.request.urlopen(req, timeout=8.0) as resp:
            data = resp.read()
            if len(data) > 200:
                try:
                    cache_file.write_bytes(data)
                except Exception:
                    pass
                return Response(content=data, media_type="audio/mpeg", headers={"Cache-Control": "public, max-age=604800"})
            raise HTTPException(502, "Áudio inválido retornado pelo serviço.")
    except Exception as exc:
        raise HTTPException(503, f"Serviço de áudio indisponível ({exc}).") from exc
