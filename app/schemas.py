"""Modelos de entrada da API (validação e limites de tamanho)."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class _In(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


class LineIn(_In):
    speaker: Optional[str] = Field(None, max_length=60)
    en: str = Field(..., min_length=1, max_length=600)
    pt: str = Field(..., min_length=1, max_length=600)
    en_alt: list[str] = Field(default_factory=list, max_length=10)
    pt_alt: list[str] = Field(default_factory=list, max_length=10)


class DialogIn(_In):
    title: str = Field(..., min_length=1, max_length=120)
    level: Optional[str] = Field(None, max_length=10)
    description: Optional[str] = Field(None, max_length=300)
    lines: list[LineIn] = Field(..., min_length=1, max_length=200)


class PhraseIn(_In):
    en: str = Field(..., min_length=1, max_length=600)
    pt: str = Field(..., min_length=1, max_length=600)
    dialog_id: Optional[int] = None


class CheckIn(_In):
    direction: Literal["en_to_pt", "pt_to_en"]
    answer: str = Field(..., max_length=1000)


class RevealIn(_In):
    direction: Literal["en_to_pt", "pt_to_en"]


class TextIn(_In):
    title: Optional[str] = Field(None, max_length=120)
    pt_text: str = Field(..., min_length=1, max_length=6000)
    en_reference: Optional[str] = Field(None, max_length=8000)


class TextPatch(_In):
    en_reference: str = Field(..., min_length=1, max_length=8000)


class AttemptIn(_In):
    attempt: str = Field(..., min_length=1, max_length=8000)


class ImportIn(_In):
    title: Optional[str] = Field(None, max_length=120)
    text: str = Field(..., min_length=1, max_length=30000)


class WordPatch(_In):
    in_review: Optional[bool] = None
    meaning_pt: Optional[str] = Field(None, max_length=200)


class ReviewAnswerIn(_In):
    answer: str = Field(..., max_length=200)
    mode: Literal["meaning", "reverse", "listen"] = "meaning"


class ChatMessage(_In):
    role: Literal["partner", "learner"]
    text: str = Field(..., min_length=1, max_length=1500)


class ChatTurnIn(_In):
    scenario_id: str = Field(..., max_length=40)
    level: Literal["A2", "B1", "B2"] = "B1"
    history: list[ChatMessage] = Field(default_factory=list, max_length=40)
    message: str = Field("", max_length=1500)
    response_time_seconds: Optional[float] = None


class SettingsIn(_In):
    ignore_accents: bool = False
    strict_exact: bool = False


class AIConfigIn(_In):
    provider: Literal["gemini", "ollama", "lmstudio", "anthropic", "openai", "none"]
    api_key: Optional[str] = Field("", max_length=500)
    model: Optional[str] = Field("", max_length=100)
    endpoint: Optional[str] = Field("", max_length=500)


class CoachReportIn(_In):
    scenario_id: str = Field(..., max_length=40)
    history: list[ChatMessage] = Field(..., min_length=1, max_length=50)


class GenerateDialogIn(_In):
    topic: str = Field(..., min_length=2, max_length=200)
    level: Literal["A1", "A2", "B1", "B2", "C1"] = "B1"


class EarGymCheckIn(_In):
    target: str = Field(..., min_length=1, max_length=100)
    answer: str = Field(..., max_length=100)


