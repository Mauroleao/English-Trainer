"""Rotas de configuração e gerenciamento de provedores de IA (Gemini, Ollama, LM Studio, etc.)."""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from ..ai import (
    DEFAULT_ANTHROPIC_MODEL,
    DEFAULT_GEMINI_MODEL,
    DEFAULT_LMSTUDIO_MODEL,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_OPENAI_MODEL,
    LLMError,
    create_llm,
)
from ..db import get_setting, set_setting
from ..deps import get_db, get_llm
from ..schemas import AIConfigIn

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai", tags=["ia"])


def _mask_key(key: Optional[str]) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return key[:4] + "…" + key[-4:]


@router.get("/config")
def get_ai_config(request: Request, db=Depends(get_db), llm=Depends(get_llm)):
    """Retorna a configuração atual de IA."""
    db_prov = get_setting(db, "ai_provider")
    db_model = get_setting(db, "ai_model")
    db_endpoint = get_setting(db, "ai_endpoint")
    db_key = get_setting(db, "ai_api_key")

    current_provider = db_prov or (getattr(llm, "provider", None) if llm else "none")
    current_model = db_model or (getattr(llm, "model", "") if llm else "")
    current_endpoint = db_endpoint or ""
    has_key = bool(db_key) or bool(os.getenv("GEMINI_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY"))

    return {
        "ai_enabled": llm is not None,
        "provider": current_provider,
        "model": current_model,
        "endpoint": current_endpoint,
        "masked_key": _mask_key(db_key),
        "has_key": has_key,
        "defaults": {
            "gemini": {"model": DEFAULT_GEMINI_MODEL, "endpoint": ""},
            "ollama": {"model": DEFAULT_OLLAMA_MODEL, "endpoint": "http://localhost:11434"},
            "lmstudio": {"model": DEFAULT_LMSTUDIO_MODEL, "endpoint": "http://localhost:1234/v1"},
            "anthropic": {"model": DEFAULT_ANTHROPIC_MODEL, "endpoint": ""},
            "openai": {"model": DEFAULT_OPENAI_MODEL, "endpoint": "https://api.openai.com/v1"},
        },
    }


@router.post("/config")
def save_ai_config(body: AIConfigIn, request: Request, db=Depends(get_db)):
    """Salva a configuração de IA no banco e atualiza o estado em memória sem reiniciar o servidor."""
    prov = body.provider.strip().lower()

    if prov == "none":
        set_setting(db, "ai_provider", "none")
        request.app.state.llm = None
        return {"ok": True, "ai_enabled": False, "provider": "none", "message": "IA desativada com sucesso."}

    # Se a chave enviada for vazia ou máscara, mantém a chave anterior gravada no banco ou variável de ambiente
    api_key = (body.api_key or "").strip()
    if not api_key or "…" in api_key or "****" in api_key:
        existing_key = get_setting(db, "ai_api_key", "")
        if existing_key:
            api_key = existing_key
        elif prov == "gemini":
            api_key = os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")
        elif prov == "anthropic":
            api_key = os.getenv("ANTHROPIC_API_KEY", "")
        elif prov == "openai":
            api_key = os.getenv("OPENAI_API_KEY", "")

    endpoint = (body.endpoint or "").strip()
    model = (body.model or "").strip()

    try:
        new_llm = create_llm(prov, api_key=api_key, model=model, endpoint=endpoint)
    except Exception as exc:
        raise HTTPException(400, f"Configuração inválida: {exc}") from exc

    if new_llm is None:
        raise HTTPException(400, f"Provedor '{prov}' não suportado.")

    # Salva no banco de dados SQLite
    set_setting(db, "ai_provider", prov)
    set_setting(db, "ai_api_key", api_key)
    set_setting(db, "ai_model", model or getattr(new_llm, "model", ""))
    set_setting(db, "ai_endpoint", endpoint or getattr(new_llm, "host", "") or getattr(new_llm, "base_url", ""))

    # Atualiza o estado da aplicação em tempo de execução
    request.app.state.llm = new_llm

    return {
        "ok": True,
        "ai_enabled": True,
        "provider": prov,
        "model": new_llm.model,
        "message": f"IA configurada com sucesso ({prov.upper()}: {new_llm.model}).",
    }


@router.post("/test")
def test_ai_connection(request: Request, llm=Depends(get_llm)):
    """Testa a conexão e resposta do provedor de IA ativo."""
    if llm is None:
        raise HTTPException(400, "Nenhum provedor de IA está configurado no momento.")

    start = time.perf_counter()
    try:
        translated = llm.translate("Pronto para acelerar meu inglês!")
        elapsed_ms = round((time.perf_counter() - start) * 1000)
        return {
            "ok": True,
            "provider": getattr(llm, "provider", "desconhecido"),
            "model": getattr(llm, "model", "padrão"),
            "test_output": translated,
            "latency_ms": elapsed_ms,
            "message": f"Conexão com IA OK em {elapsed_ms} ms! Resposta: '{translated}'",
        }
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - start) * 1000)
        raise HTTPException(502, f"Falha no teste com {getattr(llm, 'provider', 'IA')} ({elapsed_ms}ms): {exc}") from exc


@router.get("/ollama/models")
def get_ollama_models(host: str = "http://localhost:11434"):
    """Detecta automaticamente os modelos instalados no Ollama local."""
    clean_host = host.rstrip("/")
    if not clean_host.startswith("http://") and not clean_host.startswith("https://"):
        clean_host = f"http://{clean_host}"
    url = f"{clean_host}/api/tags"

    req = urllib.request.Request(url, headers={"User-Agent": "EnglishTrainer"})
    try:
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = [m.get("name") for m in data.get("models", []) if m.get("name")]
            return {"ok": True, "host": clean_host, "models": models}
    except Exception as exc:
        return {"ok": False, "host": clean_host, "models": [], "error": f"Não foi possível conectar ao Ollama em {clean_host} ({exc}). Certifique-se de que o Ollama está rodando ('ollama serve')."}


@router.get("/lmstudio/models")
def get_lmstudio_models(host: str = "http://localhost:1234/v1"):
    """Detecta automaticamente os modelos disponíveis no LM Studio local."""
    clean_host = host.rstrip("/")
    if not clean_host.startswith("http://") and not clean_host.startswith("https://"):
        clean_host = f"http://{clean_host}"
    if not clean_host.endswith("/v1"):
        clean_host = f"{clean_host}/v1"
    url = f"{clean_host}/models"

    req = urllib.request.Request(url, headers={"User-Agent": "EnglishTrainer"})
    try:
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = [m.get("id") for m in data.get("data", []) if m.get("id")]
            return {"ok": True, "host": clean_host, "models": models}
    except Exception as exc:
        return {"ok": False, "host": clean_host, "models": [], "error": f"Não foi possível conectar ao LM Studio em {clean_host} ({exc}). Certifique-se de que o LM Studio está aberto com o servidor local ativo ('Start Server')."}
