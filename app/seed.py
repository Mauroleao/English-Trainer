"""Conteúdo inicial: diálogos prontos e um glossário offline (inglês -> português) das palavras deles."""
from __future__ import annotations

import json
import sqlite3

from .content_it import EXTRA_GLOSSARY, IT_DIALOGS, IT_TERMS
from .db import now_iso
from .vocab import add_words_from_text

# (falante, inglês, português, [outras traduções aceitas em português])
DIALOGS = [
    {
        "title": "No restaurante",
        "level": "A2",
        "description": "Chegar, pedir a comida e pedir a conta.",
        "lines": [
            ("Waiter", "Good evening. Do you have a reservation?",
             "Boa noite. Você tem uma reserva?", ["Boa noite. Vocês têm uma reserva?", "Boa noite. Tem reserva?"]),
            ("Customer", "Yes, a table for two under the name Silva.",
             "Sim, uma mesa para dois no nome de Silva.", ["Sim, uma mesa para duas pessoas no nome de Silva."]),
            ("Waiter", "Right this way. Here is the menu.",
             "Por aqui. Aqui está o cardápio.", ["Por aqui. Aqui está o menu."]),
            ("Customer", "I would like the chicken with rice, please.",
             "Eu gostaria do frango com arroz, por favor.", ["Eu queria o frango com arroz, por favor.", "Gostaria do frango com arroz, por favor."]),
            ("Waiter", "Would you like something to drink?",
             "Você gostaria de algo para beber?", ["Você quer algo para beber?", "Gostaria de algo para beber?"]),
            ("Customer", "Just water, thank you. Could we have the bill later?",
             "Só água, obrigado. Poderíamos pedir a conta depois?",
             ["Só água, obrigada. Poderíamos pedir a conta depois?", "Apenas água, obrigado. Poderíamos pedir a conta mais tarde?"]),
        ],
    },
    {
        "title": "No aeroporto",
        "level": "A2",
        "description": "Check-in, bagagem e portão de embarque.",
        "lines": [
            ("Agent", "Hello. May I see your passport?",
             "Olá. Posso ver o seu passaporte?", ["Olá. Posso ver seu passaporte?"]),
            ("Traveler", "Of course. Here it is.",
             "Claro. Aqui está.", ["Claro. Aqui está ele.", "Claro. Está aqui."]),
            ("Agent", "Are you checking any bags today?",
             "Você vai despachar alguma bagagem hoje?", ["Você vai despachar alguma mala hoje?", "Vai despachar alguma bagagem hoje?"]),
            ("Traveler", "Yes, just one suitcase.",
             "Sim, apenas uma mala.", ["Sim, só uma mala."]),
            ("Agent", "Your flight leaves from gate twelve at six thirty.",
             "Seu voo sai do portão doze às seis e meia.", ["O seu voo sai do portão doze às seis e meia.", "Seu voo parte do portão doze às seis e trinta."]),
            ("Traveler", "Thank you. Where can I find a coffee shop?",
             "Obrigado. Onde posso encontrar uma cafeteria?", ["Obrigada. Onde posso encontrar uma cafeteria?", "Obrigado. Onde eu posso encontrar uma cafeteria?"]),
        ],
    },
    {
        "title": "Conhecendo alguém",
        "level": "A1",
        "description": "Apresentações, origem e profissão.",
        "lines": [
            ("Ana", "Hi, my name is Ana. Nice to meet you.",
             "Oi, meu nome é Ana. Prazer em conhecer você.", ["Oi, meu nome é Ana. Prazer em te conhecer.", "Oi, o meu nome é Ana. Prazer em conhecê-lo."]),
            ("Paulo", "Nice to meet you too. I'm Paulo. Where are you from?",
             "Prazer em conhecer você também. Eu sou o Paulo. De onde você é?",
             ["Prazer em te conhecer também. Eu sou o Paulo. De onde você é?", "Prazer em conhecer você também. Eu sou Paulo. De onde você é?"]),
            ("Ana", "I'm from Brazil, but I live in Canada now.",
             "Eu sou do Brasil, mas moro no Canadá agora.", ["Eu sou do Brasil, mas eu moro no Canadá agora.", "Sou do Brasil, mas moro no Canadá agora."]),
            ("Paulo", "What do you do for a living?",
             "O que você faz da vida?", ["Qual é a sua profissão?", "O que você faz para viver?", "Com o que você trabalha?"]),
            ("Ana", "I work as a teacher. I love my job.",
             "Eu trabalho como professora. Eu amo o meu trabalho.", ["Eu trabalho como professora. Eu amo meu trabalho.", "Trabalho como professora. Amo o meu trabalho."]),
            ("Paulo", "That sounds great. Let's keep in touch!",
             "Que legal. Vamos manter contato!", ["Isso parece ótimo. Vamos manter contato!", "Parece ótimo. Vamos manter contato!"]),
        ],
    },
]

# significados curtos (português do Brasil) das palavras dos diálogos acima, separados por ";"
GLOSSARY = {
    "good": "bom; boa", "evening": "noite; fim de tarde", "do": "fazer", "you": "você; vocês",
    "have": "ter", "a": "um; uma", "reservation": "reserva", "yes": "sim", "table": "mesa",
    "for": "para; por", "two": "dois; duas", "under": "sob; embaixo de", "the": "o; a; os; as",
    "name": "nome", "silva": "Silva", "right": "certo; direito; exatamente", "this": "este; esta; isto",
    "way": "caminho; jeito", "here": "aqui", "is": "é; está", "menu": "cardápio; menu",
    "i": "eu", "would": "iria; gostaria; seria", "like": "gostar; como", "chicken": "frango; galinha",
    "with": "com", "rice": "arroz", "please": "por favor", "something": "algo; alguma coisa",
    "to": "para; a", "drink": "beber; bebida", "just": "apenas; só", "water": "água",
    "thank": "agradecer", "could": "poderia; podia", "we": "nós", "bill": "conta",
    "later": "mais tarde; depois", "hello": "olá", "may": "poder; posso", "see": "ver",
    "your": "seu; sua; seus; suas", "passport": "passaporte", "of": "de", "course": "curso; percurso",
    "it": "isso; ele; ela", "are": "são; estão; é; está", "checking": "verificando; despachando",
    "any": "algum; alguma; qualquer", "bags": "bolsas; malas; bagagens", "today": "hoje",
    "one": "um; uma", "suitcase": "mala", "flight": "voo", "leaves": "sai; parte; folhas",
    "from": "de; a partir de", "gate": "portão", "twelve": "doze", "at": "em; às; a",
    "six": "seis", "thirty": "trinta", "where": "onde", "can": "poder; conseguir; lata",
    "find": "encontrar", "coffee": "café", "shop": "loja", "hi": "oi",
    "my": "meu; minha; meus; minhas", "nice": "legal; agradável; bom", "meet": "conhecer; encontrar",
    "too": "também; demais", "i'm": "eu sou; eu estou", "paulo": "Paulo", "ana": "Ana",
    "brazil": "Brasil", "but": "mas", "live": "morar; viver", "in": "em; dentro de",
    "canada": "Canadá", "now": "agora", "what": "o que; qual", "living": "vida; sustento",
    "work": "trabalhar; trabalho", "as": "como; enquanto", "teacher": "professor; professora",
    "love": "amar; amor; adorar", "job": "trabalho; emprego", "that": "aquele; aquela; isso; que",
    "sounds": "soa; parece", "great": "ótimo; excelente; grande", "let's": "vamos",
    "keep": "manter; continuar", "touch": "contato; toque",
}


# glossário offline = diálogos iniciais + palavras comuns + termos de TI de uma palavra só
for _k, _v in EXTRA_GLOSSARY.items():
    GLOSSARY.setdefault(_k, _v)
for _term, _meaning, _ in IT_TERMS:
    if " " not in _term:
        GLOSSARY.setdefault(_term.casefold(), _meaning)


def _install_dialogs(db: sqlite3.Connection, dialogs: list[dict]) -> None:
    for d in dialogs:
        dialog_id = db.execute(
            "INSERT INTO dialogs(title, level, description, builtin, created_at) VALUES(?,?,?,1,?)",
            (d["title"], d["level"], d["description"], now_iso()),
        ).lastrowid
        for pos, (speaker, en, pt, pt_alt) in enumerate(d["lines"]):
            db.execute(
                "INSERT INTO phrases(dialog_id, position, speaker, en, pt, en_alt, pt_alt) VALUES(?,?,?,?,?,?,?)",
                (dialog_id, pos, speaker, en, pt, "[]", json.dumps(pt_alt, ensure_ascii=False)),
            )
        add_words_from_text(db, "\n".join(line[1] for line in d["lines"]), "dialog", dialog_id, glossary=GLOSSARY)


def install_it_terms(db: sqlite3.Connection) -> int:
    """Vocabulário de desenvolvimento: já com significado e frase de exemplo, marcado com a tag 'ti'."""
    for term, meaning, example in IT_TERMS:
        word = term.casefold()
        cur = db.execute(
            "INSERT OR IGNORE INTO words(word, meaning_pt, is_common, in_review, tag, created_at) VALUES(?,?,0,1,'ti',?)",
            (word, meaning, now_iso()),
        )
        if not cur.rowcount:  # a palavra já existia (veio de um diálogo ou texto): só marca como TI
            db.execute("UPDATE words SET tag = 'ti' WHERE word = ?", (word,))
            db.execute("UPDATE words SET meaning_pt = ? WHERE word = ? AND (meaning_pt IS NULL OR meaning_pt = '')", (meaning, word))
        word_id = db.execute("SELECT id FROM words WHERE word = ?", (word,)).fetchone()["id"]
        db.execute(
            "INSERT OR IGNORE INTO word_contexts(word_id, source_type, source_id, sentence) VALUES(?, 'pack', NULL, ?)",
            (word_id, example),
        )
    return len(IT_TERMS)


def _once(db: sqlite3.Connection, key: str, install) -> None:
    """Instala um pacote de conteúdo uma única vez (mesmo que o usuário apague partes depois)."""
    if db.execute("SELECT 1 FROM settings WHERE key = ?", (key,)).fetchone():
        return
    with db:
        install(db)
        db.execute("INSERT INTO settings(key, value) VALUES(?, '1')", (key,))


def seed(db: sqlite3.Connection) -> None:
    _once(db, "seeded", lambda c: _install_dialogs(c, DIALOGS))
    _once(db, "seed_it_v1", lambda c: (_install_dialogs(c, IT_DIALOGS), install_it_terms(c)))
