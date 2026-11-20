"""Utilitários de texto: normalização, comparação palavra a palavra e extração de vocabulário.

A comparação funciona sobre "chaves" (palavras normalizadas). No inglês, contrações são
expandidas (I'm == I am, don't == do not), então o aluno pode escrever de qualquer um dos
dois jeitos. Maiúsculas e pontuação são ignoradas, a não ser que o modo "exato" esteja ligado.
Acentos importam por padrão (você != voce), a não ser que a configuração diga o contrário.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Callable, Iterable, Optional

_QUOTES = str.maketrans(
    {"’": "'", "‘": "'", "`": "'", "´": "'", "“": '"', "”": '"'}
)
# palavra = letras/dígitos, com apóstrofo ou hífen no meio (don't, mother-in-law, d'água)
_TOKEN_RE = re.compile(r"[^\W_]+(?:['\-][^\W_]+)*", re.UNICODE)
_PT_CHARS = set("ãõçáéíóúâêôà")


def prepare(text: str) -> str:
    """NFC + aspas tipográficas viram aspas simples (celulares costumam digitar ’)."""
    return unicodedata.normalize("NFC", text or "").translate(_QUOTES)


def collapse(text: str) -> str:
    return " ".join(prepare(text).split())


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(prepare(text))


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c))


# --------------------------------------------------------------------------- contrações
_SPECIAL = {
    "can't": ["can", "not"],
    "cannot": ["can", "not"],
    "won't": ["will", "not"],
    "let's": ["let", "us"],
    "i'm": ["i", "am"],
    "ain't": ["is", "not"],
}
_PRONOUNS = {"i", "you", "he", "she", "it", "we", "they", "that", "there", "who", "what", "where", "how", "here"}


def expand_contraction(low: str) -> list[str]:
    if low in _SPECIAL:
        return list(_SPECIAL[low])
    if low.endswith("n't") and len(low) > 3:
        return [low[:-3], "not"]
    for suf, word in (("'re", "are"), ("'ll", "will"), ("'ve", "have")):
        if low.endswith(suf) and len(low) > len(suf):
            return [low[: -len(suf)], word]
    for suf, word in (("'d", "would"), ("'s", "is")):
        if low.endswith(suf) and low[: -len(suf)] in _PRONOUNS:
            return [low[: -len(suf)], word]
    return [low]


@dataclass
class Keyed:
    surfaces: list[str]  # palavras como foram escritas
    keys: list[str]  # palavras normalizadas (contrações expandidas)
    owner: list[int]  # índice da key -> índice da surface de onde veio


def keyed(text: str, lang: str = "en", ignore_accents: bool = False) -> Keyed:
    surfaces = tokenize(text)
    keys: list[str] = []
    owner: list[int] = []
    for i, tok in enumerate(surfaces):
        low = tok.casefold()
        parts = expand_contraction(low) if lang == "en" else [low]
        for p in parts:
            keys.append(strip_accents(p) if ignore_accents else p)
            owner.append(i)
    return Keyed(surfaces, keys, owner)


# --------------------------------------------------------------------------- comparação
@dataclass
class Mark:
    text: str
    status: str  # ok | close | wrong


@dataclass
class Check:
    correct: bool
    marks: list[Mark]
    missing: int
    similarity: float
    best: str
    format_issue: bool = False
    corrections: list[dict] = field(default_factory=list)


def _close(x: str, y: str) -> bool:
    if strip_accents(x) == strip_accents(y):
        return True
    return SequenceMatcher(None, x, y).ratio() >= 0.75


def _span(k: Keyed, i1: int, i2: int) -> str:
    seen: list[int] = []
    for idx in range(i1, i2):
        o = k.owner[idx]
        if o not in seen:
            seen.append(o)
    return " ".join(k.surfaces[o] for o in seen)


def make_pt_flag(pt_text: str, en_text: str, ignore_accents: bool = False) -> Callable[[str], bool]:
    """Devolve uma função que diz se uma palavra (chave) parece português dentro de um texto em inglês."""
    pt_keys = set(keyed(pt_text, "pt", ignore_accents).keys)
    en_keys = set(keyed(en_text, "en", ignore_accents).keys)

    def flag(k: str) -> bool:
        if k in en_keys:
            return False
        return k in pt_keys or any(ch in _PT_CHARS for ch in k)

    return flag


def has_portuguese(attempt: str, flag: Callable[[str], bool]) -> bool:
    return any(flag(k) for k in keyed(attempt, "en").keys)


def _diff(a: Keyed, b: Keyed, pt_flag: Optional[Callable[[str], bool]]):
    sm = SequenceMatcher(a=a.keys, b=b.keys, autojunk=False)
    status = ["wrong"] * len(a.keys)
    missing = 0
    corrections: list[dict] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for i in range(i1, i2):
                status[i] = "ok"
            continue
        if tag == "replace":
            for i in range(i1, i2):
                if any(_close(a.keys[i], b.keys[j]) for j in range(j1, j2)):
                    status[i] = "close"
            missing += max(0, (j2 - j1) - (i2 - i1))
        elif tag == "insert":
            missing += j2 - j1
        wrote, should = _span(a, i1, i2), _span(b, j1, j2)
        if tag == "insert":
            kind = "missing"
        elif tag == "delete":
            kind = "extra"
        else:
            keys = a.keys[i1:i2]
            if pt_flag and sum(1 for k in keys if pt_flag(k)) * 2 >= len(keys):
                kind = "portuguese"
            elif len(keys) == j2 - j1 and all(_close(x, y) for x, y in zip(keys, b.keys[j1:j2])):
                kind = "spelling"
            else:
                kind = "wrong"
        corrections.append({"you_wrote": wrote, "should_be": should, "kind": kind, "explanation": ""})
    return sm, status, missing, corrections


def _marks(a: Keyed, status: list[str]) -> list[Mark]:
    order = {"ok": 0, "close": 1, "wrong": 2}
    res = ["ok"] * len(a.surfaces)
    for k, s in enumerate(status):
        o = a.owner[k]
        if order[s] > order[res[o]]:
            res[o] = s
    return [Mark(t, s) for t, s in zip(a.surfaces, res)]


def check_answer(
    answer: str,
    accepted: Iterable[str],
    *,
    lang: str = "en",
    ignore_accents: bool = False,
    strict_exact: bool = False,
    pt_flag: Optional[Callable[[str], bool]] = None,
) -> Check:
    """Compara a resposta com as versões aceitas e devolve marcações palavra a palavra."""
    variants = [v for v in accepted if v and v.strip()]
    a = keyed(answer, lang, ignore_accents)

    format_variant: Optional[str] = None
    for v in variants:
        b = keyed(v, lang, ignore_accents)
        if a.keys and a.keys == b.keys:
            if not strict_exact or collapse(answer) == collapse(v):
                return Check(True, [Mark(s, "ok") for s in a.surfaces], 0, 1.0, v)
            format_variant = format_variant or v
    if format_variant is not None:
        return Check(False, [Mark(s, "ok") for s in a.surfaces], 0, 1.0, format_variant, format_issue=True)

    best = None
    for v in variants:
        b = keyed(v, lang, ignore_accents)
        score = SequenceMatcher(a=a.keys, b=b.keys, autojunk=False).ratio()
        if best is None or score > best[0]:
            best = (score, v, b)
    if best is None:
        return Check(False, [Mark(s, "wrong") for s in a.surfaces], 0, 0.0, "")
    score, v, b = best
    _, status, missing, corrections = _diff(a, b, pt_flag)
    return Check(False, _marks(a, status), missing, round(score, 3), v, corrections=corrections)


# --------------------------------------------------------------------------- vocabulário
STOPWORDS = frozenset(
    """a an the and or but if of to in on at by for with from as is am are was were be been being
    do does did have has had i you he she it we they me him her us them my your his its our their
    this that these those there here not no yes so than then too very can will would could should
    may might must just also what when where who how why which""".split()
)

_SENT_SPLIT = re.compile(r"(?<=[.!?…])\s+|\n+")


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT_SPLIT.split(prepare(text)) if s.strip()]


def extract_words(text: str) -> list[tuple[str, str]]:
    """Palavras únicas (minúsculas) na ordem em que aparecem, cada uma com a frase da 1ª ocorrência."""
    seen: dict[str, str] = {}
    for sent in split_sentences(text):
        for tok in _TOKEN_RE.findall(sent):
            w = tok.casefold()
            if w.isdigit():
                continue
            # tira o 's de possessivos (John's -> john), mas preserva contrações (let's, it's, that's)
            if w.endswith("'s") and len(w) > 2 and w != "let's" and w[:-2] not in _PRONOUNS:
                w = w[:-2]
            if w not in seen:
                seen[w] = sent
    return list(seen.items())


def is_common(word: str) -> bool:
    return word in STOPWORDS
