"""Vocabulário: separa as palavras de qualquer texto em inglês e controla a revisão espaçada (Leitner)."""
from __future__ import annotations

import logging
import re
import sqlite3
from contextlib import closing
from typing import Optional

from .db import Settings, connect, iso_in, now_iso
from .textutil import extract_words, is_common, keyed

log = logging.getLogger(__name__)

# dias até a próxima revisão, por caixa (box 0 = errou / novo)
BOX_DAYS = [0, 1, 2, 4, 8, 16, 32]
MAX_BOX = len(BOX_DAYS) - 1
MAX_CONTEXTS_PER_WORD = 3


def add_words_from_text(
    db: sqlite3.Connection,
    text: str,
    source_type: str,
    source_id: Optional[int] = None,
    *,
    glossary: Optional[dict[str, str]] = None,
) -> dict:
    """Separa todas as palavras do texto e grava as que ainda não existem.

    Palavras muito comuns (the, is, you...) ficam salvas, mas fora da fila de revisão por padrão.
    """
    glossary = glossary or {}
    added = existing = 0
    with db:
        for word, sentence in extract_words(text):
            cur = db.execute(
                "INSERT OR IGNORE INTO words(word, meaning_pt, is_common, in_review, created_at) VALUES(?,?,?,?,?)",
                (word, glossary.get(word), int(is_common(word)), int(not is_common(word)), now_iso()),
            )
            if cur.rowcount:
                added += 1
            else:
                existing += 1
                if word in glossary:
                    db.execute(
                        "UPDATE words SET meaning_pt = ? WHERE word = ? AND (meaning_pt IS NULL OR meaning_pt = '')",
                        (glossary[word], word),
                    )
            word_id = db.execute("SELECT id FROM words WHERE word = ?", (word,)).fetchone()["id"]
            n = db.execute("SELECT COUNT(*) FROM word_contexts WHERE word_id = ?", (word_id,)).fetchone()[0]
            if n < MAX_CONTEXTS_PER_WORD:
                db.execute(
                    "INSERT OR IGNORE INTO word_contexts(word_id, source_type, source_id, sentence) VALUES(?,?,?,?)",
                    (word_id, source_type, source_id, sentence),
                )
    return {"added": added, "existing": existing, "total": added + existing}


def mark_difficult(db: sqlite3.Connection, phrases: list[str], source_id: Optional[int] = None) -> int:
    """Palavras que o aluno errou/não soube: entram na revisão (mesmo as comuns) e contam um erro."""
    count = 0
    with db:
        for text in phrases:
            for word, sentence in extract_words(text):
                db.execute(
                    "INSERT OR IGNORE INTO words(word, is_common, in_review, created_at) VALUES(?,?,1,?)",
                    (word, int(is_common(word)), now_iso()),
                )
                db.execute("UPDATE words SET in_review = 1, wrong = wrong + 1 WHERE word = ?", (word,))
                word_id = db.execute("SELECT id FROM words WHERE word = ?", (word,)).fetchone()["id"]
                db.execute(
                    "INSERT OR IGNORE INTO word_contexts(word_id, source_type, source_id, sentence) "
                    "SELECT ?, 'text', ?, ? WHERE (SELECT COUNT(*) FROM word_contexts WHERE word_id = ?) < ?",
                    (word_id, source_id, sentence, word_id, MAX_CONTEXTS_PER_WORD),
                )
                count += 1
    return count


def fill_missing_meanings(db_path: str, llm, limit: int = 120) -> int:
    """Pede à IA o significado das palavras sem tradução. Roda em segundo plano, com conexão própria."""
    if llm is None:
        return 0
    with closing(connect(db_path)) as db:
        rows = db.execute(
            "SELECT w.id, w.word, "
            "(SELECT sentence FROM word_contexts c WHERE c.word_id = w.id ORDER BY c.id LIMIT 1) AS sentence "
            "FROM words w WHERE w.meaning_pt IS NULL OR w.meaning_pt = '' ORDER BY w.is_common, w.id LIMIT ?",
            (limit,),
        ).fetchall()
        if not rows:
            return 0
        try:
            meanings = llm.word_meanings([(r["word"], r["sentence"] or "") for r in rows])
        except Exception as exc:  # noqa: BLE001 - falha da IA não pode derrubar nada
            log.warning("Não foi possível traduzir palavras: %s", exc)
            return 0
        filled = 0
        with db:
            for r in rows:
                m = (meanings.get(r["word"]) or "").strip()
                if m:
                    db.execute("UPDATE words SET meaning_pt = ? WHERE id = ?", (m, r["id"]))
                    filled += 1
        return filled


# --------------------------------------------------------------------------- revisão espaçada
_ARTICLES = {"o", "a", "os", "as", "um", "uma", "uns", "umas"}


def meaning_variants(meaning: str) -> list[str]:
    parts = re.split(r"[;,/]|\bou\b", meaning or "")
    return [p.strip() for p in parts if p.strip()]


def _key_without_article(text: str, settings: Settings) -> str:
    keys = keyed(text, "pt", settings.ignore_accents).keys
    if len(keys) > 1 and keys[0] in _ARTICLES:
        keys = keys[1:]
    return " ".join(keys)


def check_meaning(answer: str, meaning: str, settings: Settings) -> bool:
    """Acerta se o aluno digitou qualquer um dos significados salvos (artigo inicial é opcional)."""
    target = _key_without_article(answer, settings)
    if not target:
        return False
    return any(_key_without_article(v, settings) == target for v in meaning_variants(meaning))


def check_word(answer: str, word: str) -> bool:
    """Acerta se a palavra (ou expressão) em inglês foi digitada certa. Maiúsculas e pontuação não contam."""
    typed = keyed(answer, "en").keys
    return bool(typed) and typed == keyed(word, "en").keys


def grade_word(db: sqlite3.Connection, word_id: int, correct: bool) -> sqlite3.Row:
    row = db.execute("SELECT box FROM words WHERE id = ?", (word_id,)).fetchone()
    if correct:
        box = min(row["box"] + 1, MAX_BOX)
        next_review = iso_in(days=BOX_DAYS[box])
        db.execute(
            "UPDATE words SET box = ?, next_review = ?, correct = correct + 1 WHERE id = ?",
            (box, next_review, word_id),
        )
    else:
        db.execute(
            "UPDATE words SET box = 0, next_review = ?, wrong = wrong + 1 WHERE id = ?",
            (iso_in(minutes=5), word_id),
        )
    return db.execute("SELECT * FROM words WHERE id = ?", (word_id,)).fetchone()
