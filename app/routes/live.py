"""Módulo Live Voice Tutor (Conversação Ao Vivo Bidirecional).

Suporte a WebSocket em tempo real:
- Gemini Multimodal Live API (gemini-2.0-flash-exp / gemini-live-2.5-flash-native-audio)
  com autenticação via Ephemeral Token gerado no backend para proteger a API Key.
- Fallback Duplex Agent para modelos locais (Ollama, LM Studio) ou modo sem chave Gemini.
- Barge-in natural (interrupção do áudio ao falar).
- Detecção e extração de cards de Recasting ("Você disse" vs "Forma natural").
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import secrets
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from ..ai import LLMError
from ..db import get_setting
from ..deps import get_db

log = logging.getLogger(__name__)

router = APIRouter(tags=["live"])

# Armazenamento em memória de tokens efêmeros de sessão
_SESSIONS: dict[str, dict] = {}
SESSION_TTL_SECONDS = 900  # 15 minutos


def _clean_expired_sessions():
    now = time.time()
    expired = [k for k, v in _SESSIONS.items() if now - v.get("created_at", 0) > SESSION_TTL_SECONDS]
    for k in expired:
        _SESSIONS.pop(k, None)


SCENARIO_PROMPTS = {
    "daily": (
        "Context: Daily Stand-up / Tech Meeting.\n"
        "You are the Tech Lead hosting the daily stand-up meeting with your software engineering team.\n"
        "Ask the developer (student) what they worked on yesterday, what they are focusing on today, "
        "and if they have any blockers or pull requests needing review. Use natural agile/tech terminology."
    ),
    "interview": (
        "Context: Job Interview (Entrevista de Emprego).\n"
        "You are a friendly hiring manager conducting a technical job interview for a software developer position.\n"
        "Ask about their background, their experience with modern tech stacks, projects they are proud of, "
        "and how they handle technical challenges. Be encouraging and realistic."
    ),
    "casual": (
        "Context: Casual Coffee Break (Conversa Casual).\n"
        "You are an international teammate grabbing a coffee together.\n"
        "Talk casually about how their day is going, hobbies, weekend plans, music, travel, or movies. "
        "Keep the tone warm, friendly, and relaxed."
    ),
}

# Cenários em alemão para o tutor de conversação
SCENARIO_PROMPTS_DE = {
    "daily": (
        "Kontext: Tägliches Stand-up / Tech-Meeting.\n"
        "Du bist der Tech Lead, der das tägliche Stand-up mit dem Softwareentwicklungsteam leitet.\n"
        "Frage den Entwickler (Lernenden), woran er gestern gearbeitet hat, worauf er sich heute konzentriert "
        "und ob er Blocker oder Pull Requests hat, die überprüft werden müssen. Verwende natürliche Agile/Tech-Terminologie."
    ),
    "interview": (
        "Kontext: Vorstellungsgespräch (Entrevista de Emprego).\n"
        "Du bist ein freundlicher Personalleiter, der ein technisches Vorstellungsgespräch für eine Softwareentwicklerposition führt.\n"
        "Frage nach dem Hintergrund des Bewerbers, seiner Erfahrung mit modernen Tech-Stacks, Projekten, auf die er stolz ist, "
        "und wie er mit technischen Herausforderungen umgeht. Sei ermutigend und realistisch."
    ),
    "casual": (
        "Kontext: Entspannte Kaffeepause.\n"
        "Du bist ein internationaler Teamkollege, der zusammen Kaffee trinkt.\n"
        "Rede locker darüber, wie der Tag läuft, über Hobbys, Wochenendbpläne, Musik, Reisen oder Filme. "
        "Bleibe warmherzig, freundlich und entspannt."
    ),
}

TUTOR_SYSTEM_INSTRUCTION = """You are a friendly, patient, and encouraging English conversation tutor for a Brazilian Portuguese speaker.
1. Natural Flow: Keep the conversation engaging and natural in English, adapting to the user's proficiency level.
2. Seamless Portuguese Fallback (Code-Switching): If the user speaks in Portuguese, mixes Portuguese words into English, or asks 'como se diz X?', understand them completely without breaking immersion. Acknowledge their thought, naturally provide the best English phrasing for what they wanted to say, and continue the conversation in English.
3. Gentle Recasting & Correction: If the user makes a grammar or pronunciation mistake in English that affects clarity or sounds unnatural, gently model the correct phrase first (e.g., 'Good point! Just a quick tip, we usually say [correct phrase]'), briefly explain why in 1 short sentence if helpful, and immediately ask a follow-up question to keep them talking. Never lecture or overwhelm them with multiple corrections at once.

{scenario_section}

Format Rule for Recasting / Corrections:
Whenever you gently recast or correct the learner, in addition to your spoken English answer, insert a tagged marker in the text stream:
[RECAST: <user_phrase> || <natural_phrase>]
Example: [RECAST: I have 28 years || I am 28 years old]
Always continue speaking your full conversational response naturally in English."""

# Instrução de sistema do tutor em alemão
TUTOR_SYSTEM_INSTRUCTION_DE = """Du bist ein freundlicher, geduldiger und aufmunternder Deutschlehrer für einen brasilianischen Portugiesischsprecher.
1. Natürlicher Gesprächsfluss: Halte das Gespräch auf Deutsch engagiert und natürlich, angepasst an das Sprachniveau des Lernenden.
2. Nahtloser Portugiesisch-Rückgriff (Code-Switching): Wenn der Lernende auf Portugiesisch spricht, portugiesische Wörter auf Deutsch einmischt oder fragt 'wie sagt man X auf Deutsch?', verstehe ihn vollständig ohne den Fluss zu unterbrechen. Bestätige seinen Gedanken, liefere natürlich die beste deutsche Formulierung und führe das Gespräch auf Deutsch weiter.
3. Sanfte Korrektur: Wenn der Lernende einen Grammatik- oder Aussprachefehler macht, der unnatürlich klingt, modelliere sanft die korrekte Formulierung (z.B. 'Guter Punkt! Kurzer Tipp: Wir sagen auf Deutsch besser [korrekte Formulierung]'), erkläre kurz warum in einem Satz, und stelle sofort eine Anschlussfrage, damit der Lernende weiterredet. Niemals mit mehreren Korrekturen auf einmal überwältigen.

{scenario_section}

Format-Regel für Korrekturen:
Wenn du sanft korrigierst, füge zusätzlich zu deiner Antwort auf Deutsch ein markiertes Tag in den Textstream ein:
[RECAST: <was_der_Lernende_sagte> || <natürliche_Formulierung>]
Beispiel: [RECAST: Ich habe 28 Jahre || Ich bin 28 Jahre alt]
Führe immer deine vollständige Gesprächsantwort auf Deutsch natürlich weiter."""


class SessionRequest(BaseModel):
    scenario: Optional[str] = "daily"
    language: Optional[str] = "en"


def _get_gemini_api_key(db=None) -> str:
    if db is not None:
        try:
            prov = get_setting(db, "ai_provider", "").strip().lower()
            if prov == "gemini":
                k = get_setting(db, "ai_api_key", "").strip()
                if k:
                    return k
        except Exception:
            pass
    return (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()


@router.post("/api/live/session")
def create_live_session(req: SessionRequest, db=Depends(get_db)):
    """Gera um Ephemeral Token de sessão de curta duração para WebSocket seguro sem expor chaves de API."""
    _clean_expired_sessions()

    lang = (req.language or "en").strip().lower()
    if lang not in ("en", "de"):
        lang = "en"

    scenario_key = (req.scenario or "daily").strip().lower()
    # escolhe banco de cenários conforme idioma
    scenario_bank = SCENARIO_PROMPTS_DE if lang == "de" else SCENARIO_PROMPTS
    if scenario_key not in scenario_bank:
        scenario_key = "daily"

    token = secrets.token_urlsafe(32)
    gemini_key = _get_gemini_api_key(db)

    mode = "gemini_live" if gemini_key else "duplex_agent"

    _SESSIONS[token] = {
        "created_at": time.time(),
        "scenario": scenario_key,
        "language": lang,
        "mode": mode,
        "gemini_key": gemini_key,
    }

    return {
        "ok": True,
        "token": token,
        "ws_path": f"/ws/live-conversation?token={token}",
        "scenario": scenario_key,
        "language": lang,
        "mode": mode,
        "has_gemini_live": bool(gemini_key),
    }


RECAST_REGEX = re.compile(r"\[RECAST:\s*(.*?)\s*\|\|\s*(.*?)\s*\]", re.IGNORECASE)


def parse_recast_tags(text: str) -> tuple[str, list[dict]]:
    """Extrai marcações [RECAST: você disse || forma natural] e limpa o texto para exibição."""
    recasts = []
    for match in RECAST_REGEX.finditer(text):
        you_said = match.group(1).strip()
        natural = match.group(2).strip()
        if you_said or natural:
            recasts.append({"you_said": you_said, "natural": natural})

    cleaned = RECAST_REGEX.sub("", text).strip()
    return cleaned, recasts


@router.websocket("/ws/live-conversation")
async def websocket_live_conversation(websocket: WebSocket, token: str = Query(...)):
    """Conexão WebSocket duplex em tempo real com o tutor de conversação ao vivo."""
    _clean_expired_sessions()
    session = _SESSIONS.get(token)

    if not session:
        await websocket.close(code=4001, reason="Token de sessão inválido ou expirado.")
        return

    await websocket.accept()

    scenario_key = session.get("scenario", "daily")
    lang = session.get("language", "en")

    # seleciona banco de cenários e instrução de sistema conforme idioma
    if lang == "de":
        scenario_bank = SCENARIO_PROMPTS_DE
        base_instruction = TUTOR_SYSTEM_INSTRUCTION_DE
    else:
        scenario_bank = SCENARIO_PROMPTS
        base_instruction = TUTOR_SYSTEM_INSTRUCTION

    scenario_desc = scenario_bank.get(scenario_key, scenario_bank["daily"])
    system_instruction = base_instruction.format(scenario_section=scenario_desc)

    gemini_key = session.get("gemini_key", "")
    mode = session.get("mode", "gemini_live")

    # Notifica o cliente que a sessão iniciou
    await websocket.send_json({
        "type": "ready",
        "scenario": scenario_key,
        "mode": mode,
        "message": "Sessão conectada. Tutor ao vivo pronto!",
    })

    if mode == "gemini_live" and gemini_key:
        await _run_gemini_live_session(websocket, gemini_key, system_instruction, scenario_key)
    else:
        await _run_duplex_fallback_session(websocket, system_instruction, scenario_key)


async def _run_gemini_live_session(client_ws: WebSocket, api_key: str, system_instruction: str, scenario: str):
    """Ponte WebSocket bidirecional com a Gemini Multimodal Live API oficial."""
    import websockets

    # Gemini 2.0 Flash Multimodal Live API WebSocket Endpoint
    model_name = os.getenv("GEMINI_LIVE_MODEL", "models/gemini-2.0-flash-exp")
    if not model_name.startswith("models/"):
        model_name = f"models/{model_name}"

    upstream_url = (
        f"wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta."
        f"GenerativeService.BidiGenerateContent?key={api_key}"
    )

    try:
        async with websockets.connect(upstream_url, ping_interval=20, ping_timeout=20) as gemini_ws:
            # 1. Envia a mensagem inicial de Setup para o Gemini
            setup_msg = {
                "setup": {
                    "model": model_name,
                    "generationConfig": {
                        "responseModalities": ["AUDIO"],
                        "speechConfig": {
                            "voiceConfig": {
                                "prebuiltVoiceConfig": {
                                    "voiceName": os.getenv("GEMINI_VOICE", "Puck")
                                }
                            }
                        },
                    },
                    "systemInstruction": {
                        "parts": [{"text": system_instruction}]
                    },
                }
            }
            await gemini_ws.send(json.dumps(setup_msg))

            async def client_to_gemini():
                """Lê mensagens do navegador e repassa para a Gemini Live API."""
                try:
                    while True:
                        msg = await client_ws.receive_json()
                        msg_type = msg.get("type")

                        if msg_type == "audio":
                            # Áudio PCM 16kHz do microfone do usuário
                            raw_base64 = msg.get("data", "")
                            if raw_base64:
                                gemini_chunk = {
                                    "realtimeInput": {
                                        "mediaChunks": [
                                            {
                                                "mimeType": "audio/pcm;rate=16000",
                                                "data": raw_base64,
                                            }
                                        ]
                                    }
                                }
                                await gemini_ws.send(json.dumps(gemini_chunk))

                        elif msg_type == "text":
                            # Texto direto do usuário (ex: se digitar ou via Speech Recognition)
                            text = msg.get("text", "").strip()
                            if text:
                                gemini_text = {
                                    "clientContent": {
                                        "turns": [
                                            {
                                                "role": "user",
                                                "parts": [{"text": text}],
                                            }
                                        ],
                                        "turnComplete": True,
                                    }
                                }
                                await gemini_ws.send(json.dumps(gemini_text))

                        elif msg_type == "interrupt":
                            # Barge-in manual acionado pelo cliente
                            interrupt_sig = {"clientContent": {"turnComplete": True}}
                            try:
                                await gemini_ws.send(json.dumps(interrupt_sig))
                            except Exception:
                                pass
                except WebSocketDisconnect:
                    pass
                except Exception as exc:
                    log.info("Encerrando client_to_gemini: %s", exc)

            async def gemini_to_client():
                """Lê respostas em streaming (áudio e texto) do Gemini e repassa ao navegador."""
                try:
                    text_buffer = ""
                    async for raw_msg in gemini_ws:
                        data = json.loads(raw_msg)

                        # Verifica confirmação de setup
                        if "setupComplete" in data:
                            await client_ws.send_json({
                                "type": "session_started",
                                "message": "Gemini Live Audio conectado com sucesso!",
                            })
                            continue

                        server_content = data.get("serverContent")
                        if not server_content:
                            continue

                        # Suporte a barge-in detectado nativamente pelo Gemini
                        if server_content.get("interrupted"):
                            await client_ws.send_json({"type": "interrupted"})
                            text_buffer = ""
                            continue

                        model_turn = server_content.get("modelTurn")
                        if model_turn:
                            parts = model_turn.get("parts", [])
                            for part in parts:
                                # 1. Áudio PCM 24kHz vindo do Gemini
                                inline_data = part.get("inlineData")
                                if inline_data:
                                    mime = inline_data.get("mimeType", "")
                                    audio_b64 = inline_data.get("data", "")
                                    if audio_b64:
                                        await client_ws.send_json({
                                            "type": "audio",
                                            "data": audio_b64,
                                            "mimeType": mime or "audio/pcm;rate=24000",
                                        })

                                # 2. Texto da transcrição do tutor
                                part_text = part.get("text")
                                if part_text:
                                    text_buffer += part_text
                                    clean_txt, recasts = parse_recast_tags(part_text)
                                    if clean_txt:
                                        await client_ws.send_json({
                                            "type": "text",
                                            "sender": "tutor",
                                            "text": clean_txt,
                                        })
                                    for rc in recasts:
                                        await client_ws.send_json({
                                            "type": "recast",
                                            "you_said": rc["you_said"],
                                            "natural": rc["natural"],
                                        })

                        if server_content.get("turnComplete"):
                            # Verifica se sobrou algum recast no text_buffer
                            _, recasts = parse_recast_tags(text_buffer)
                            for rc in recasts:
                                await client_ws.send_json({
                                    "type": "recast",
                                    "you_said": rc["you_said"],
                                    "natural": rc["natural"],
                                })
                            text_buffer = ""
                            await client_ws.send_json({"type": "turn_complete"})

                except WebSocketDisconnect:
                    pass
                except Exception as exc:
                    log.warning("Erro no loop gemini_to_client: %s", exc)
                    try:
                        await client_ws.send_json({"type": "error", "message": f"Erro na conexão Gemini: {exc}"})
                    except Exception:
                        pass

            # Roda as duas direções simultaneamente até desconexão
            done, pending = await asyncio.wait(
                [asyncio.create_task(client_to_gemini()), asyncio.create_task(gemini_to_client())],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for t in pending:
                t.cancel()

    except Exception as exc:
        log.warning("Falha ao conectar com Gemini Live WebSocket: %s. Alternando para modo duplex fallback.", exc)
        await client_ws.send_json({
            "type": "fallback_notice",
            "message": f"Gemini Live indisponível ({exc}). Alternando para modo Duplex Inteligente.",
        })
        await _run_duplex_fallback_session(client_ws, system_instruction, scenario)


async def _run_duplex_fallback_session(client_ws: WebSocket, system_instruction: str, scenario: str):
    """Sessão duplex inteligente para uso local (Ollama / LM Studio) ou fallback offline."""
    history: list[dict] = []

    # Saudação inicial do tutor conforme o cenário
    opening_messages = {
        "daily": "Hi there! Welcome to our daily stand-up. What did you work on yesterday, and what are you planning for today?",
        "interview": "Hello! Thank you for joining our interview today. To get started, could you briefly introduce yourself and tell me about your background in software engineering?",
        "casual": "Hey! Great to see you. How is your day going so far? Grabbing a coffee break?",
    }
    intro = opening_messages.get(scenario, opening_messages["daily"])
    history.append({"role": "partner", "text": intro})

    await client_ws.send_json({
        "type": "text",
        "sender": "tutor",
        "text": intro,
        "is_intro": True,
    })
    await client_ws.send_json({"type": "turn_complete"})

    try:
        while True:
            msg = await client_ws.receive_json()
            msg_type = msg.get("type")

            if msg_type == "interrupt":
                await client_ws.send_json({"type": "interrupted"})
                continue

            user_text = msg.get("text", "").strip()
            if not user_text and msg_type == "audio":
                # Em modo fallback sem transcrever áudio no servidor, o cliente Web Speech envia texto
                continue

            if not user_text:
                continue

            history.append({"role": "user", "text": user_text})

            # Monta histórico para a IA
            llm = client_ws.app.state.llm
            if llm:
                try:
                    # Executa chamada de chat com o prompt do tutor bilíngue
                    prompt_history = "\n".join(
                        f"{'Tutor' if h['role'] == 'partner' else 'Student'}: {h['text']}"
                        for h in history[-8:]
                    )
                    prompt_input = (
                        f"<instruction>\n{system_instruction}\n</instruction>\n"
                        f"<history>\n{prompt_history}\n</history>\n"
                        f"Student's latest reply: {user_text}\n"
                        f"Reply as the tutor. If the student made an error, include [RECAST: student error || natural phrase] in your text."
                    )
                    raw_reply = await asyncio.to_thread(llm._ask, system_instruction, prompt_input, 800)
                except Exception as exc:
                    log.warning("Erro no fallback LLM: %s", exc)
                    raw_reply = "I understand! Let's keep practicing. Could you tell me more about that?"
            else:
                raw_reply = "Great job practicing! Keep going! Tell me more about your project."

            clean_text, recasts = parse_recast_tags(raw_reply)
            history.append({"role": "partner", "text": clean_text})

            # Envia cards de recasting se houver
            for rc in recasts:
                await client_ws.send_json({
                    "type": "recast",
                    "you_said": rc["you_said"],
                    "natural": rc["natural"],
                })

            # Envia resposta textual do tutor
            await client_ws.send_json({
                "type": "text",
                "sender": "tutor",
                "text": clean_text,
            })
            await client_ws.send_json({"type": "turn_complete"})

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        log.info("Sessão duplex fallback encerrada: %s", exc)
