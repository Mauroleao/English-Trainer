"""Conteúdo inicial em Alemão (Deutsch): diálogos práticos, glossário offline e termos de TI."""
from __future__ import annotations

import json
import sqlite3
from typing import Optional

from .db import now_iso
from .vocab import add_words_from_text

# Diálogos em Alemão (A1 ao B2): (falante, alemão, português, [outras traduções aceitas em português])
DIALOGS_DE = [
    {
        "title": "Jemanden kennenlernen (Conhecendo alguém)",
        "level": "A1",
        "description": "Apresentação, de onde você vem no Brasil e profissão.",
        "lines": [
            ("Lukas", "Hallo! Mein Name ist Lukas. Wie heißt du?",
             "Olá! Meu nome é Lukas. Como você se chama?",
             ["Olá! O meu nome é Lukas. Como você se chama?", "Oi! Meu nome é Lukas. Qual é o seu nome?"]),
            ("Ana", "Hallo Lukas. Ich bin Ana. Freut mich, dich kennenzulernen.",
             "Olá Lukas. Eu sou a Ana. Prazer em te conhecer.",
             ["Oi Lukas. Eu sou Ana. Prazer em conhecer você.", "Olá Lukas. Sou a Ana. Muito prazer em conhecê-lo."]),
            ("Lukas", "Woher kommst du, Ana?",
             "De onde você vem, Ana?",
             ["De onde você é, Ana?"]),
            ("Ana", "Ich komme aus Brasilien, aber ich wohne jetzt in Berlin.",
             "Eu venho do Brasil, mas moro em Berlim agora.",
             ["Eu sou do Brasil, mas agora moro em Berlim.", "Sou do Brasil, mas moro agora em Berlim."]),
            ("Lukas", "Was machst du beruflich?",
             "O que você faz profissionalmente?",
             ["Qual é a sua profissão?", "Com o que você trabalha?", "O que você faz da vida?"]),
            ("Ana", "Ich arbeite als Softwareentwicklerin. Ich mag meinen Job sehr.",
             "Eu trabalho como desenvolvedora de software. Eu gosto muito do meu trabalho.",
             ["Trabalho como desenvolvedora de software. Gosto muito do meu trabalho."]),
            ("Lukas", "Das ist super! Willkommen in Deutschland.",
             "Isso é ótimo! Seja bem-vinda à Alemanha.",
             ["Isso é maravilhoso! Bem-vinda à Alemanha.", "Que ótimo! Bem-vinda à Alemanha."]),
        ],
    },
    {
        "title": "Im Restaurant & Café (No restaurante)",
        "level": "A2",
        "description": "Fazer pedido, pedir água, prato típico e a conta.",
        "lines": [
            ("Kellner", "Guten Abend! Haben Sie eine Reservierung?",
             "Boa noite! Você tem uma reserva?",
             ["Boa noite! Vocês têm uma reserva?", "Boa noite! Tem reserva?"]),
            ("Gast", "Ja, einen Tisch für zwei Personen auf den Namen Silva.",
             "Sim, uma mesa para duas pessoas no nome Silva.",
             ["Sim, uma mesa para dois no nome Silva.", "Sim, uma mesa para duas pessoas em nome de Silva."]),
            ("Kellner", "Sehr gerne. Hier ist die Speisekarte. Möchten Sie schon etwas trinken?",
             "Com prazer. Aqui está o cardápio. Gostaria de beber algo já?",
             ["Com certeza. Aqui está o cardápio. Gostariam de beber algo já?"]),
            ("Gast", "Ja, eine Flasche Mineralwasser ohne Kohlensäure, bitte.",
             "Sim, uma garrafa de água mineral sem gás, por favor.",
             ["Sim, uma garrafa de água sem gás, por favor."]),
            ("Gast", "Ich hätte gerne das Schnitzel mit Kartoffelsalat, bitte.",
             "Eu gostaria do schnitzel com salada de batata, por favor.",
             ["Eu queria o schnitzel com salada de batatas, por favor."]),
            ("Gast", "Könnten wir bitte zahlen? Zusammen, bitte.",
             "Poderíamos pagar, por favor? Junto, por favor.",
             ["Podemos pagar, por favor? Tudo junto, por favor."]),
        ],
    },
    {
        "title": "Am Flughafen & Bahnhof (Viagem e Transporte)",
        "level": "A2",
        "description": "Check-in, despacho de malas e encontrar o trem / portão.",
        "lines": [
            ("Mitarbeiter", "Guten Tag. Darf ich bitte Ihren Reisepass sehen?",
             "Bom dia. Posso ver o seu passaporte, por favor?",
             ["Olá. Posso ver seu passaporte, por favor?"]),
            ("Reisender", "Natürlich, hier ist er. Ich fliege nach Frankfurt.",
             "Claro, aqui está ele. Eu vou voar para Frankfurt.",
             ["Com certeza, aqui está. Eu viajo para Frankfurt."]),
            ("Mitarbeiter", "Geben Sie heute Gepäck auf?",
             "Você vai despachar bagagem hoje?",
             ["Vai despachar alguma mala hoje?", "O senhor despacha bagagem hoje?"]),
            ("Reisender", "Ja, nur einen Koffer. Wo ist das Abfluggate?",
             "Sim, apenas uma mala. Onde fica o portão de embarque?",
             ["Sim, só uma mala. Onde é o portão de embarque?"]),
            ("Mitarbeiter", "Gate B14. Der Flug startet pünktlich um zehn Uhr.",
             "Portão B14. O voo parte pontualmente às dez horas.",
             ["Portão B14. O voo decola pontualmente às dez horas."]),
            ("Reisender", "Vielen Dank für Ihre Hilfe!",
             "Muito obrigado pela sua ajuda!",
             ["Muito obrigada pela sua ajuda!"]),
        ],
    },
    {
        "title": "TI — Daily Stand-up auf Deutsch",
        "level": "B1",
        "description": "Reportar o que fez ontem, planos para hoje e pull requests.",
        "lines": [
            ("Tech Lead", "Guten Morgen Team! Lass uns mit dem Stand-up beginnen. Wer möchte anfangen?",
             "Bom dia, equipe! Vamos começar com o stand-up. Quem gostaria de começar?",
             ["Bom dia time! Vamos começar a reunião. Quem quer começar?"]),
            ("Entwickler", "Ich kann anfangen. Gestern habe ich den Authentifizierungs-Bug im Backend behoben.",
             "Eu posso começar. Ontem eu corrigi o bug de autenticação no backend.",
             ["Posso começar. Ontem corrigi o bug de autenticação no backend."]),
            ("Tech Lead", "Sehr gut. Und woran arbeitest du heute?",
             "Muito bom. E no que você está trabalhando hoje?",
             ["Muito bem. E com o que você trabalha hoje?"]),
            ("Entwickler", "Heute schreibe ich Unit-Tests für den neuen Service und optimiere die Datenbankabfragen.",
             "Hoje estou escrevendo testes unitários para o novo serviço e otimizando as consultas ao banco de dados.",
             ["Hoje vou escrever testes unitários para o novo serviço e otimizar as queries do banco."]),
            ("Tech Lead", "Hast du irgendwelche Blocker?",
             "Você tem algum impedimento?",
             ["Tem algum blocker?", "Existe algum impedimento?"]),
            ("Entwickler", "Nein, keine Blocker. Mein Pull Request ist bereit für das Code Review.",
             "Não, nenhum impedimento. Meu pull request está pronto para o code review.",
             ["Não, sem blockers. Meu pull request está pronto para revisão."]),
        ],
    },
    {
        "title": "TI — Code Review & Architektur",
        "level": "B1",
        "description": "Discussão de arquitetura técnica e refatoração de código.",
        "lines": [
            ("Senior Dev", "Ich habe eine Frage zu dieser Funktion. Warum hast du dich für diese Lösung entschieden?",
             "Tenho uma pergunta sobre esta função. Por que você decidiu por esta solução?",
             ["Tenho uma dúvida sobre essa função. Por que escolheu essa solução?"]),
            ("Entwickler", "Diese Lösung reduziert die Latenz und verbessert die Skalierbarkeit des Systems deutlich.",
             "Esta solução reduz a latência e melhora a escalabilidade do sistema significativamente.",
             ["Essa solução reduz o tempo de resposta e melhora muito a escalabilidade."]),
            ("Senior Dev", "Guter Punkt! Die Logik ist sehr sauber und gut dokumentiert.",
             "Bom ponto! A lógica está muito limpa e bem documentada.",
             ["Ótimo ponto! A lógica está muito limpa e bem documentada."]),
            ("Entwickler", "Danke! Ich habe auch zusätzliche Tests für die Edge Cases hinzugefügt.",
             "Obrigado! Eu também adicionei testes adicionais para os casos de borda.",
             ["Obrigada! Também adicionei testes extras para os edge cases."]),
            ("Senior Dev", "Perfekt. Ich genehmige den Pull Request jetzt.",
             "Perfeito. Eu aprovo o pull request agora.",
             ["Perfeito. Estou aprovando o pull request agora."]),
        ],
    },
]

# Glossário offline Alemão -> Português do Brasil
GLOSSARY_DE = {
    "hallo": "olá; oi", "mein": "meu; minha", "name": "nome", "ist": "é; está", "lukas": "Lukas",
    "wie": "como; quão", "heißt": "chama-se; chama", "du": "você; tu", "ich": "eu", "bin": "sou; estou",
    "ana": "Ana", "freut": "alegra; dá prazer", "mich": "me; a mim", "dich": "te; a ti; você",
    "kennenzulernen": "conhecer", "woher": "de onde", "kommst": "vem", "aus": "de; fora de",
    "brasilien": "Brasil", "aber": "mas; porém", "wohne": "moro; resido", "jetzt": "agora",
    "in": "em; dentro de", "berlin": "Berlim", "was": "o que; qual", "machst": "faz",
    "beruflich": "profissionalmente; no trabalho", "arbeite": "trabalho", "als": "como; enquanto",
    "softwareentwicklerin": "desenvolvedora de software", "mag": "gosto de; aprecio", "job": "trabalho; emprego",
    "sehr": "muito", "das": "isso; o; a", "super": "ótimo; super", "willkommen": "bem-vindo; bem-vinda",
    "deutschland": "Alemanha", "guten": "bom; boa", "abend": "noite; fim de tarde", "haben": "ter",
    "sie": "o senhor; a senhora; eles; elas", "eine": "uma", "reservierung": "reserva", "ja": "sim",
    "einen": "um", "tisch": "mesa", "für": "para; por", "zwei": "dois; duas", "personen": "pessoas",
    "auf": "em; sobre", "den": "o; a; ao", "silva": "Silva", "gerne": "com prazer; de bom grado",
    "hier": "aqui", "speisekarte": "cardápio; menu", "möchten": "gostaria; gostariam", "schon": "já",
    "etwas": "algo; um pouco", "trinken": "beber; bebida", "flasche": "garrafa", "mineralwasser": "água mineral",
    "ohne": "sem", "kohlensäure": "gás carbônico; gás", "bitte": "por favor; de nada", "hätte": "teria; gostaria de ter",
    "schnitzel": "schnitzel (filé empanado)", "mit": "com", "kartoffelsalat": "salada de batatas",
    "könnten": "poderíamos; poderia", "wir": "nós", "zahlen": "pagar; números", "zusammen": "junto; juntos",
    "tag": "dia", "darf": "posso; é permitido", "ihren": "seu; sua", "reisepass": "passaporte",
    "sehen": "ver", "natürlich": "naturalmente; claro", "er": "ele", "fliege": "voo; viajo",
    "nach": "para; depois de", "frankfurt": "Frankfurt", "geben": "dar; despachar", "heute": "hoje",
    "gepäck": "bagagem; malas", "nur": "apenas; só", "koffer": "mala", "wo": "onde",
    "abfluggate": "portão de embarque", "gate": "portão", "flug": "voo", "startet": "parte; decola",
    "pünktlich": "pontualmente", "um": "às; em volta de", "zehn": "dez", "uhr": "horas; relógio",
    "vielen": "muitos; muito", "dank": "obrigado; agradecimento", "ihre": "sua; seu", "hilfe": "ajuda",
    "morgen": "manhã; amanhã", "team": "equipe; time", "lass": "deixe; vamos", "uns": "nos",
    "beginnen": "começar; iniciar", "wer": "quem", "anfangen": "começar", "kann": "posso; pode",
    "gestern": "ontem", "habe": "tenho; conjugação de ter", "authentifizierungs-bug": "bug de autenticação",
    "backend": "backend", "behoben": "corrigido; resolvido", "gut": "bom; bem", "und": "e",
    "woran": "no que; em quê", "arbeitest": "trabalha", "schreibe": "escrevo", "unit-tests": "testes unitários",
    "neuen": "novo", "service": "serviço", "optimiere": "otimizo", "datenbankabfragen": "consultas ao banco de dados",
    "hast": "tem", "irgendwelche": "quaisquer; algum", "blocker": "impedimento; blocker", "nein": "não",
    "keine": "nenhum; nenhuma", "pull": "pull", "request": "request", "bereit": "pronto; preparado",
    "code": "código; code", "review": "revisão; review", "frage": "pergunta; dúvida", "zu": "a; para; sobre",
    "dieser": "esta; este", "funktion": "função", "warum": "por que", "dich": "se; a ti",
    "diese": "esta; este", "lösung": "solução", "entschieden": "decidido; escolheu", "reduziert": "reduz",
    "latenz": "latência; tempo de resposta", "verbessert": "melhora", "skalierbarkeit": "escalabilidade",
    "systems": "do sistema", "deutlich": "claramente; significativamente", "guter": "bom",
    "punkt": "ponto", "die": "a; as; o (acusativo neutro/feminino)", "logik": "lógica",
    "sauber": "limpo; limpa", "dokumentiert": "documentado; documentada", "danke": "obrigado",
    "auch": "também", "zusätzliche": "adicionais; extras", "tests": "testes", "edge": "edge",
    "cases": "cases", "hinzugefügt": "adicionado; acrescentado", "perfekt": "perfeito",
    "genehmige": "aprovo; autorizo",
}

# Vocabulário técnico alemão para desenvolvedores e profissionais de TI
IT_TERMS_DE = [
    ("die Bereitstellung", "o deploy / publicação em produção", "Die Bereitstellung der neuen Version verlief erfolgreich."),
    ("der Fehler", "o bug / erro no sistema", "Ich habe den Fehler im Frontend behoben."),
    ("die Abfrage", "a query / consulta ao banco de dados", "Diese Datenbankabfrage ist sehr schnell."),
    ("die Schnittstelle", "a interface / API", "Die REST-Schnittstelle liefert JSON-Daten zurück."),
    ("die Fehlerbehebung", "a depuração / resolução de problemas", "Die Fehlerbehebung hat zwei Stunden gedauert."),
    ("die Leistung", "o desempenho / performance", "Wir müssen die Leistung der Web-App verbessern."),
    ("die Quellcodeverwaltung", "o controle de versão / Git", "Wir nutzen Git für die Quellcodeverwaltung."),
    ("die Skalierbarkeit", "a escalabilidade", "Microservices verbessern die Skalierbarkeit unserer Plattform."),
    ("die Refaktorisierung", "a refatoração de código", "Nach der Refaktorisierung ist der Code viel sauberer."),
    ("die Datenbanksicherung", "o backup do banco de dados", "Die Datenbanksicherung läuft jede Nacht automatisch."),
]


def install_german_content(db: sqlite3.Connection) -> None:
    """Instala os diálogos e termos técnicos de Alemão no banco de dados com language='de'."""
    # 1. Instala diálogos em Alemão
    for d in DIALOGS_DE:
        dialog_id = db.execute(
            "INSERT INTO dialogs(title, level, description, builtin, created_at, language) VALUES(?,?,?,1,?,'de')",
            (d["title"], d["level"], d["description"], now_iso()),
        ).lastrowid

        for pos, (speaker, de_txt, pt, pt_alt) in enumerate(d["lines"]):
            db.execute(
                "INSERT INTO phrases(dialog_id, position, speaker, en, pt, en_alt, pt_alt, language) VALUES(?,?,?,?,?,?,?,'de')",
                (dialog_id, pos, speaker, de_txt, pt, "[]", json.dumps(pt_alt, ensure_ascii=False)),
            )

        # Adiciona palavras do diálogo ao vocabulário com language='de'
        add_words_from_text(
            db,
            "\n".join(line[1] for line in d["lines"]),
            "dialog",
            dialog_id,
            glossary=GLOSSARY_DE,
            language="de",
        )

    # 2. Instala termos técnicos de TI em Alemão
    for term, meaning, example in IT_TERMS_DE:
        word = term.casefold()
        cur = db.execute(
            "INSERT OR IGNORE INTO words(word, meaning_pt, is_common, in_review, tag, created_at, language) VALUES(?,?,0,1,'ti',?,'de')",
            (word, meaning, now_iso()),
        )
        word_row = db.execute("SELECT id FROM words WHERE word = ? AND language = 'de'", (word,)).fetchone()
        if word_row:
            word_id = word_row["id"]
            if not cur.rowcount:
                db.execute("UPDATE words SET tag = 'ti' WHERE id = ?", (word_id,))
                db.execute("UPDATE words SET meaning_pt = ? WHERE id = ? AND (meaning_pt IS NULL OR meaning_pt = '')", (meaning, word_id))
            db.execute(
                "INSERT OR IGNORE INTO word_contexts(word_id, source_type, source_id, sentence) VALUES(?, 'pack', NULL, ?)",
                (word_id, example),
            )
