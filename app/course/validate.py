"""Validador do conteúdo do curso (lições, textos de leitura e teste de nível).

Uso:  python -m app.course.validate [pasta_de_conteudo]
Sai com código 1 se houver erros. Também é usado pelos testes automáticos.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from ..textutil import check_answer, keyed

LEVELS = ["A1", "A2", "B1", "B2", "C1"]
TYPES = {"choice", "fill", "translate", "order", "fix", "listen"}
TYPED = {"fill", "translate", "order", "fix", "listen"}
CONTENT_DIR = Path(__file__).resolve().parent / "content"

LESSON_ID = re.compile(r"^(a1|a2|b1|b2|c1)-(\d{2})$")
READING_ID = re.compile(r"^r-(a1|a2|b1|b2|c1)-(\d{2})$")
PLACEMENT_ID = re.compile(r"^p-(a1|a2|b1|b2|c1)-([1-6])$")
BAD_WORDS = ("TODO", "XXX", "lorem", "FIXME")

# faixa de palavras do texto em inglês, por nível, nos textos de leitura
READING_WORDS = {"A1": (35, 90), "A2": (70, 150), "B1": (120, 240), "B2": (190, 330), "C1": (260, 450)}


def _s(v: Any, minlen: int = 1) -> bool:
    return isinstance(v, str) and len(v.strip()) >= minlen


def _words(text: str) -> int:
    return len(re.findall(r"[A-Za-z']+", text))


def validate_exercise(ex: Any, expected_id: str, errs: list[str], *, allowed: set[str] = TYPES) -> None:
    where = f"{expected_id}"
    if not isinstance(ex, dict):
        errs.append(f"{where}: exercício não é objeto")
        return
    if ex.get("id") != expected_id:
        errs.append(f"{where}: id deveria ser '{expected_id}' (veio {ex.get('id')!r})")
    t = ex.get("type")
    if t not in allowed:
        errs.append(f"{where}: type inválido {t!r} (permitidos: {sorted(allowed)})")
        return
    if not _s(ex.get("explain"), 20):
        errs.append(f"{where}: 'explain' obrigatório (mín. 20 caracteres, em português, explicando o porquê)")
    for k in ("prompt", "explain"):
        if isinstance(ex.get(k), str) and any(b in ex[k] for b in BAD_WORDS):
            errs.append(f"{where}: texto de rascunho em '{k}'")

    if t == "choice":
        opts = ex.get("options")
        if not (isinstance(opts, list) and 2 <= len(opts) <= 4 and all(_s(o) for o in opts)):
            errs.append(f"{where}: 'options' deve ter de 2 a 4 textos")
            return
        if len({o.strip().lower() for o in opts}) != len(opts):
            errs.append(f"{where}: opções repetidas")
        a = ex.get("answer")
        if not (isinstance(a, int) and not isinstance(a, bool) and 0 <= a < len(opts)):
            errs.append(f"{where}: 'answer' deve ser o índice (0..{len(opts) - 1}) da opção certa")
        if not _s(ex.get("prompt"), 5):
            errs.append(f"{where}: 'prompt' obrigatório")
        wn = ex.get("why_not")
        if wn is not None and not (isinstance(wn, dict) and all(k.isdigit() and int(k) < len(opts) and _s(v) for k, v in wn.items())):
            errs.append(f"{where}: 'why_not' deve ser {{\"indice\": \"motivo\"}} com índices válidos")
        return

    answers = ex.get("answers")
    if t == "order":
        words = ex.get("words")
        if not (isinstance(words, list) and 3 <= len(words) <= 14 and all(_s(w) and " " not in w.strip() for w in words)):
            errs.append(f"{where}: 'words' deve ter de 3 a 14 palavras (sem espaços), na ordem CORRETA")
            return
        if not _s(ex.get("prompt"), 5):
            errs.append(f"{where}: 'prompt' (dica em português) obrigatório")
        answers = [" ".join(words)] + [a for a in (answers or []) if _s(a)]
        ex = {**ex, "answers": answers}
    elif t == "listen":
        if not _s(ex.get("en"), 5):
            errs.append(f"{where}: 'en' (frase falada) obrigatório")
            return
        answers = [ex["en"]] + [a for a in (answers or []) if _s(a)]
        ex = {**ex, "answers": answers}
    else:
        if not _s(ex.get("prompt"), 5):
            errs.append(f"{where}: 'prompt' obrigatório")
        if not (isinstance(answers, list) and answers and all(_s(a) for a in answers)):
            errs.append(f"{where}: 'answers' deve ser lista não vazia de textos")
            return

    if t == "fill":
        p = ex.get("prompt", "")
        if p.count("___") != 1:
            errs.append(f"{where}: o prompt de 'fill' deve ter exatamente um '___'")
        if any(a.strip().startswith("'") or "'" in a for a in answers):
            errs.append(f"{where}: respostas de 'fill' não podem ter apóstrofo (use 'translate' ou 'fix' para contrações)")
    if t == "fix":
        if keyed(ex.get("prompt", ""), "en").keys == keyed(answers[0], "en").keys:
            errs.append(f"{where}: em 'fix', a primeira resposta deve ser diferente da frase errada do prompt")
    if t in {"translate", "fix", "order", "listen"}:
        if any(re.search(r"[À-ÿ]", a) and t != "translate" for a in answers):
            errs.append(f"{where}: respostas de '{t}' devem estar em inglês")
    # o gabarito precisa passar no próprio corretor (e a 2ª resposta também)
    for a in answers:
        if not check_answer(a, answers, lang="en").correct:
            errs.append(f"{where}: a resposta {a!r} não passa no corretor")


def validate_lesson(d: Any, filename: str) -> list[str]:
    errs: list[str] = []
    if not isinstance(d, dict):
        return [f"{filename}: raiz não é objeto"]
    lid = d.get("id", "")
    m = LESSON_ID.match(lid if isinstance(lid, str) else "")
    if not m:
        return [f"{filename}: id inválido {lid!r} (esperado ex.: 'a1-01')"]
    if Path(filename).stem != lid:
        errs.append(f"{filename}: o nome do arquivo deve ser {lid}.json")
    if d.get("level") != m.group(1).upper():
        errs.append(f"{lid}: 'level' deve ser {m.group(1).upper()}")
    for k, n in (("unit", 3), ("title", 5), ("goal", 15)):
        if not _s(d.get(k), n):
            errs.append(f"{lid}: '{k}' obrigatório")
    mins = d.get("minutes")
    if not (isinstance(mins, int) and 10 <= mins <= 45):
        errs.append(f"{lid}: 'minutes' deve ser inteiro de 10 a 45")

    steps = d.get("steps")
    total_examples, traps = 0, 0
    if not (isinstance(steps, list) and 5 <= len(steps) <= 9):
        errs.append(f"{lid}: 'steps' deve ter de 5 a 9 etapas")
    else:
        for i, st in enumerate(steps, 1):
            w = f"{lid} step {i}"
            if not isinstance(st, dict):
                errs.append(f"{w}: não é objeto")
                continue
            if not _s(st.get("title"), 3):
                errs.append(f"{w}: 'title' obrigatório")
            if not _s(st.get("text"), 200):
                errs.append(f"{w}: 'text' deve explicar com pelo menos 200 caracteres")
            if any(b in str(st.get("text", "")) for b in BAD_WORDS):
                errs.append(f"{w}: texto de rascunho")
            ex = st.get("examples", [])
            if not isinstance(ex, list):
                errs.append(f"{w}: 'examples' deve ser lista")
                ex = []
            for e in ex:
                if not (isinstance(e, dict) and _s(e.get("en")) and _s(e.get("pt"))):
                    errs.append(f"{w}: cada exemplo precisa de 'en' e 'pt'")
                elif e["en"].strip() == e["pt"].strip():
                    errs.append(f"{w}: exemplo com en igual a pt")
            total_examples += len(ex)
            tb = st.get("table")
            if tb is not None:
                if not (isinstance(tb, dict) and isinstance(tb.get("headers"), list) and isinstance(tb.get("rows"), list) and tb["rows"]
                        and all(isinstance(r, list) and len(r) == len(tb["headers"]) for r in tb["rows"])):
                    errs.append(f"{w}: 'table' inválida (headers + rows com o mesmo número de colunas)")
            for k in ("tip", "trap"):
                if k in st and not _s(st[k], 10):
                    errs.append(f"{w}: '{k}' vazio")
            traps += _s(st.get("trap"), 10)
        if total_examples < 10:
            errs.append(f"{lid}: poucos exemplos ({total_examples}); mínimo 10 no total, com áudio")
        if traps < 1:
            errs.append(f"{lid}: inclua ao menos uma 'trap' (armadilha comum de quem fala português)")
    summ = d.get("summary")
    if not (isinstance(summ, list) and 3 <= len(summ) <= 6 and all(_s(x, 8) for x in summ)):
        errs.append(f"{lid}: 'summary' deve ter de 3 a 6 itens")

    for key, lo, hi, tag in (("practice", 8, 12, "p"), ("quiz", 6, 8, "q")):
        lst = d.get(key)
        if not (isinstance(lst, list) and lo <= len(lst) <= hi):
            errs.append(f"{lid}: '{key}' deve ter de {lo} a {hi} exercícios")
            continue
        for i, ex in enumerate(lst, 1):
            validate_exercise(ex, f"{lid}-{tag}{i}", errs)
        types = {e.get("type") for e in lst if isinstance(e, dict)}
        if key == "practice" and len(types & TYPES) < 3:
            errs.append(f"{lid}: 'practice' deve misturar ao menos 3 tipos de exercício")
        if key == "quiz" and sum(1 for e in lst if isinstance(e, dict) and e.get("type") in TYPED) < 3:
            errs.append(f"{lid}: 'quiz' deve ter ao menos 3 exercícios digitados (fill/translate/order/fix/listen)")
    prompts = [str(e.get("prompt", e.get("en", ""))).strip().lower() for k in ("practice", "quiz") for e in (d.get(k) or []) if isinstance(e, dict)]
    if len(set(prompts)) != len(prompts):
        errs.append(f"{lid}: há exercícios com enunciado repetido")

    words = d.get("words")
    if not (isinstance(words, list) and 5 <= len(words) <= 14):
        errs.append(f"{lid}: 'words' deve ter de 5 a 14 palavras-chave")
    else:
        for w in words:
            if not (isinstance(w, dict) and _s(w.get("word")) and _s(w.get("pt"))):
                errs.append(f"{lid}: cada item de 'words' precisa de 'word' e 'pt'")
            elif w["word"] != w["word"].strip().lower():
                errs.append(f"{lid}: palavra {w['word']!r} deve estar em minúsculas e sem espaços nas pontas")
    return errs


def validate_reading(d: Any, filename: str) -> list[str]:
    errs: list[str] = []
    rid = d.get("id", "") if isinstance(d, dict) else ""
    m = READING_ID.match(rid if isinstance(rid, str) else "")
    if not m:
        return [f"{filename}: id inválido {rid!r} (esperado ex.: 'r-a1-01')"]
    if Path(filename).stem != rid:
        errs.append(f"{filename}: o nome do arquivo deve ser {rid}.json")
    level = m.group(1).upper()
    if d.get("level") != level:
        errs.append(f"{rid}: 'level' deve ser {level}")
    for k, n in (("title", 3), ("topic", 3), ("text", 40), ("pt", 40)):
        if not _s(d.get(k), n):
            errs.append(f"{rid}: '{k}' obrigatório")
    n = _words(d.get("text", ""))
    lo, hi = READING_WORDS[level]
    if not lo <= n <= hi:
        errs.append(f"{rid}: texto com {n} palavras; para {level} use de {lo} a {hi}")
    if _s(d.get("text")) and _s(d.get("pt")) and d["text"].count("\n\n") != d["pt"].count("\n\n"):
        errs.append(f"{rid}: 'pt' deve ter o mesmo número de parágrafos que 'text' (separados por linha em branco)")
    vocab = d.get("vocab")
    if not (isinstance(vocab, list) and 6 <= len(vocab) <= 14 and all(isinstance(v, dict) and _s(v.get("word")) and _s(v.get("pt")) for v in vocab)):
        errs.append(f"{rid}: 'vocab' deve ter de 6 a 14 itens {{word, pt}}")
    else:
        text_l = d["text"].lower()
        for v in vocab:
            if v["word"] != v["word"].strip().lower():
                errs.append(f"{rid}: vocab {v['word']!r} deve estar em minúsculas")
            elif v["word"].split()[0][:4] not in text_l:
                errs.append(f"{rid}: vocab {v['word']!r} não aparece no texto")
    qs = d.get("questions")
    if not (isinstance(qs, list) and 3 <= len(qs) <= 5):
        errs.append(f"{rid}: 'questions' deve ter de 3 a 5 perguntas")
    else:
        for i, q in enumerate(qs, 1):
            validate_exercise(q, f"{rid}-q{i}", errs, allowed={"choice"})
    return errs


def validate_placement(d: Any, filename: str) -> list[str]:
    errs: list[str] = []
    items = d.get("items") if isinstance(d, dict) else None
    if not (isinstance(items, list) and len(items) == 30):
        return [f"{filename}: 'items' deve ter exatamente 30 itens (6 por nível)"]
    expected = [f"p-{lv.lower()}-{n}" for lv in LEVELS for n in range(1, 7)]
    for it, eid in zip(items, expected):
        validate_exercise(it, eid, errs, allowed={"choice", "fill"})
        if isinstance(it, dict) and it.get("level") != eid.split("-")[1].upper():
            errs.append(f"{eid}: 'level' deve ser {eid.split('-')[1].upper()}")
    return errs


def load_json(path: Path) -> tuple[Any, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:  # noqa: BLE001
        return None, f"{path.name}: JSON inválido ({exc})"


def validate_dir(root: Path = CONTENT_DIR) -> tuple[list[str], dict]:
    errs: list[str] = []
    stats = {"lessons": 0, "reading": 0, "placement": 0, "exercises": 0}
    seen: set[str] = set()
    for p in sorted((root / "lessons").glob("*.json")):
        d, e = load_json(p)
        if e:
            errs.append(e)
            continue
        errs += validate_lesson(d, p.name)
        stats["lessons"] += 1
        stats["exercises"] += len(d.get("practice", [])) + len(d.get("quiz", []))
        for k in ("practice", "quiz"):
            for ex in d.get(k, []):
                if ex.get("id") in seen:
                    errs.append(f"id de exercício duplicado: {ex.get('id')}")
                seen.add(ex.get("id"))
    for p in sorted((root / "reading").glob("*.json")):
        d, e = load_json(p)
        if e:
            errs.append(e)
            continue
        errs += validate_reading(d, p.name)
        stats["reading"] += 1
    pp = root / "placement.json"
    if pp.exists():
        d, e = load_json(pp)
        errs += [e] if e else validate_placement(d, pp.name)
        stats["placement"] = 1
    return errs, stats


def main(argv: list[str]) -> int:
    """python -m app.course.validate [pasta] [prefixo]  (prefixo ex.: a2 ou r-b1 mostra só esses erros)"""
    root = Path(argv[1]) if len(argv) > 1 and argv[1] != "-" else CONTENT_DIR
    errs, stats = validate_dir(root)
    if len(argv) > 2:
        errs = [e for e in errs if e.startswith(argv[2])]
    for e in errs:
        print("ERRO:", e)
    print(f"{stats['lessons']} lições, {stats['exercises']} exercícios, {stats['reading']} textos, placement={stats['placement']} — {len(errs)} erro(s)")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
