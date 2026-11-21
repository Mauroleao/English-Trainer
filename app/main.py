"""English Trainer: pratique inglês com frases, diálogos e textos (FastAPI + SQLite).

Rodar:  uvicorn app.main:app --reload
"""
from __future__ import annotations

import os
from contextlib import closing
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .ai import get_llm_from_env
from .db import Settings, connect, init_db, load_settings, save_settings
from .deps import get_db, get_llm
from .routes import conversation, phrases, texts, vocabulary
from .schemas import SettingsIn
from .seed import seed

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DEFAULT_DB = BASE_DIR.parent / "data" / "english_trainer.db"

_AUTO = object()


def create_app(db_path: Optional[str] = None, llm=_AUTO) -> FastAPI:
    """Cria a aplicação. `llm=None` força o modo sem IA (útil em testes)."""
    path = str(db_path or os.getenv("ENGLISH_APP_DB") or DEFAULT_DB)
    init_db(path)
    with closing(connect(path)) as db:
        seed(db)

    app = FastAPI(title="English Trainer", version="1.0.0")
    app.state.db_path = path
    app.state.llm = get_llm_from_env() if llm is _AUTO else llm

    app.include_router(phrases.router)
    app.include_router(conversation.router)
    app.include_router(texts.router)
    app.include_router(vocabulary.router)

    @app.get("/api/status", tags=["geral"])
    def status(llm=Depends(get_llm)):
        return {"ai_enabled": llm is not None, "model": getattr(llm, "model", None)}

    @app.get("/api/settings", tags=["geral"])
    def read_settings(db=Depends(get_db)):
        s = load_settings(db)
        return {"ignore_accents": s.ignore_accents, "strict_exact": s.strict_exact}

    @app.put("/api/settings", tags=["geral"])
    def write_settings(body: SettingsIn, db=Depends(get_db)):
        save_settings(db, Settings(ignore_accents=body.ignore_accents, strict_exact=body.strict_exact))
        return body

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"})

    return app


app = create_app()
