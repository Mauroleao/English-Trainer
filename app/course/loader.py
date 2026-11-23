"""Carrega o conteúdo do curso (JSON) uma vez e corrige exercícios no servidor.

O navegador nunca recebe gabarito: `public_exercise` remove respostas e explicações,
e `grade` devolve o resultado só depois que o aluno responde.
"""
from __future__ import annotations

import hashlib
import json
import random
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from ..db import Settings
from ..textutil import check_answer
from .validate import CONTENT_DIR, LEVELS

PASS_SCORE = 80  # nota mínima (%) do mini-teste para concluir a lição


def _load_dir(sub: str) -> list[dict]:
    out = []
    for p in sorted((CONTENT_DIR / sub).glob("*.json")):
        out.append(json.loads(p.read_text(encoding="utf-8")))
    return out


@lru_cache(maxsize=1)
def content() -> dict[str, Any]:
    lessons = sorted(_load_dir("lessons"), key=lambda d: (LEVELS.index(d["level"]), d["id"]))
    readings = sorted(_load_dir("reading"), key=lambda d: (LEVELS.index(d["level"]), d["id"]))
    pl_path = CONTENT_DIR / "placement.json"
    placement = json.loads(pl_path.read_text(encoding="utf-8"))["items"] if pl_path.exists() else []
    exercises: dict[str, dict] = {}
    for les in lessons:
        for part in ("practice", "quiz"):
            for ex in les[part]:
                exercises[ex["id"]] = {**ex, "_lesson": les["id"], "_part": part}
    return {
        "lessons": lessons,
        "lesson_by_id": {d["id"]: d for d in lessons},
        "readings": readings,
        "reading_by_id": {d["id"]: d for d in readings},
        "placement": placement,
        "placement_by_id": {d["id"]: d for d in placement},
        "exercises": exercises,
    }


# --------------------------------------------------------------------------- exercícios
def public_exercise(ex: dict) -> dict:
    """Versão do exercício que vai para o navegador (sem gabarito nem explicação)."""
    out: dict[str, Any] = {"id": ex["id"], "type": ex["type"]}
    t = ex["type"]
    if t == "choice":
        out.update(prompt=ex["prompt"], options=ex["options"])
    elif t == "order":
        words = list(ex["words"])
        rnd = random.Random(int(hashlib.sha1(ex["id"].encode()).hexdigest()[:8], 16))
        for _ in range(10):  # embaralhamento estável; garante que não saia já na ordem certa
            rnd.shuffle(words)
            if words != ex["words"]:
                break
        out.update(prompt=ex["prompt"], words=words)
    elif t == "listen":
        out.update(speak=ex["en"], prompt="Ouça a frase e escreva o que ouviu.")
    else:  # fill, translate, fix
        out.update(prompt=ex["prompt"])
    return out


def accepted_answers(ex: dict) -> list[str]:
    t = ex["type"]
    if t == "order":
        return [" ".join(ex["words"]), *ex.get("answers", [])]
    if t == "listen":
        return [ex["en"], *ex.get("answers", [])]
    return list(ex.get("answers", []))


def grade(ex: dict, answer: Any, settings: Optional[Settings] = None) -> dict:
    """Corrige uma resposta. Devolve correct, esperado, explicação e marcações palavra a palavra."""
    res: dict[str, Any] = {"correct": False, "explain": ex["explain"]}
    if ex["type"] == "choice":
        try:
            idx = int(answer)
        except (TypeError, ValueError):
            idx = -1
        res["correct"] = idx == ex["answer"]
        res["expected"] = ex["options"][ex["answer"]]
        if not res["correct"] and str(idx) in (ex.get("why_not") or {}):
            res["why_not"] = ex["why_not"][str(idx)]
        return res
    text = answer if isinstance(answer, str) else ""
    answers = accepted_answers(ex)
    chk = check_answer(text, answers, lang="en", strict_exact=False)
    res["correct"] = chk.correct
    res["expected"] = answers[0] if chk.correct else (chk.best or answers[0])
    res["marks"] = [{"text": m.text, "status": m.status} for m in chk.marks]
    res["corrections"] = chk.corrections
    res["empty"] = not text.strip()
    return res


# --------------------------------------------------------------------------- currículo
def lesson_summary(les: dict) -> dict:
    return {"id": les["id"], "level": les["level"], "unit": les["unit"], "title": les["title"],
            "minutes": les["minutes"], "goal": les["goal"]}


def public_lesson(les: dict) -> dict:
    out = {k: les[k] for k in ("id", "level", "unit", "title", "goal", "minutes", "steps", "summary", "words")}
    out["practice"] = [public_exercise(e) for e in les["practice"]]
    out["quiz"] = [public_exercise(e) for e in les["quiz"]]
    return out


def public_reading(r: dict, with_pt: bool = False) -> dict:
    out = {k: r[k] for k in ("id", "level", "title", "topic", "text", "vocab")}
    out["questions"] = [public_exercise(q) for q in r["questions"]]
    if with_pt:
        out["pt"] = r["pt"]
    return out


def level_after(level: str) -> Optional[str]:
    i = LEVELS.index(level)
    return LEVELS[i + 1] if i + 1 < len(LEVELS) else None
