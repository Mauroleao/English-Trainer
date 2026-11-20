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


class SettingsIn(_In):
    ignore_accents: bool = False
    strict_exact: bool = False
