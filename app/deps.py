"""Dependências compartilhadas pelas rotas."""
from __future__ import annotations

from fastapi import Depends, Request

from .db import Settings, connect, load_settings


def get_db(request: Request):
    conn = connect(request.app.state.db_path)
    try:
        yield conn
    finally:
        conn.close()


def get_db_path(request: Request) -> str:
    return request.app.state.db_path


def get_llm(request: Request):
    return request.app.state.llm


def get_settings(db=Depends(get_db)) -> Settings:
    return load_settings(db)
