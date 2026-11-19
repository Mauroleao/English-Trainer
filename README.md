# English Trainer

Aplicativo (Python + FastAPI + SQLite) para aprender inglês digitando.

## Como rodar

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Abra http://localhost:8000. O banco é criado sozinho em `data/english_trainer.db`.
A documentação automática da API fica em http://localhost:8000/docs.

### Ligando a IA (opcional)

```bash
export ANTHROPIC_API_KEY="sua-chave"      # Windows (PowerShell): $env:ANTHROPIC_API_KEY="sua-chave"
export ANTHROPIC_MODEL="claude-sonnet-5-5"  # opcional; este já é o padrão
uvicorn app.main:app --reload
```

Sem a chave tudo funciona, com as diferenças da tabela:

| | Sem IA | Com IA |
|---|---|---|
| Frases e diálogos | igual | igual |
| Criar texto | você informa a versão correta em inglês | a IA traduz o texto para você |
| Corrigir texto | só vale a versão de referência | aceita traduções equivalentes e explica cada erro em português |
| Significado das palavras | glossário embutido + você preenche | a IA traduz as palavras novas |

## O que o app faz

**1. Frases e diálogos.** Aparece a frase em inglês e você digita em português. Ao acertar, ela
inverte: aparece em português e você digita em inglês. A frase só conta como concluída quando
as duas etapas estão certas. Vêm 3 diálogos prontos, e você pode criar os seus
(formato `inglês | português`, uma frase por linha). "Mostrar resposta" mostra a resposta, conta
como erro e você ainda precisa digitá-la.

**2. Textos.** Você coloca um texto em português e tenta escrevê-lo em inglês. O que não souber,
deixe em português. O app marca palavra por palavra (verde certa, amarelo quase, vermelho errada),
mostra as correções (palavra em português, ortografia, gramática, faltou, sobrou) e **só aceita o
texto quando está totalmente correto**. Palavras ainda em português nunca são aceitas, nem pela IA.
As palavras que você errou vão direto para a revisão.

**3. Vocabulário e revisão.** Todo texto em inglês (frases dos diálogos, textos resolvidos ou
qualquer texto colado na aba Vocabulário) tem as palavras separadas, cada uma com a frase de
exemplo. A revisão usa repetição espaçada (1, 2, 4, 8, 16 e 32 dias; errou, volta em 5 minutos).
Palavras muito comuns (the, is, you...) ficam salvas, mas fora da fila de revisão.

## Regras de digitação

- Maiúsculas e pontuação são ignoradas; ligue o **Modo exato** em Ajustes para exigi-las.
- **Acentos precisam estar certos** (`voce` ≠ `você`); desligue isso em Ajustes se preferir.
- Contrações valem dos dois jeitos: `I'm` = `I am`, `don't` = `do not`.
- Uma frase pode ter várias traduções aceitas (campo `pt_alt` / `en_alt` no banco).

## Testes

```bash
pip install -r requirements-dev.txt
pytest
```

## Estrutura

```
app/main.py          aplicação e rotas gerais
app/routes/          phrases.py, texts.py, vocabulary.py
app/textutil.py      normalização, comparação palavra a palavra, extração de vocabulário
app/evaluation.py    correção do texto (IA + comparação local)
app/ai.py            integração opcional com a API da Anthropic
app/vocab.py         vocabulário e repetição espaçada
app/seed.py          diálogos e glossário iniciais
app/static/index.html  interface
```

## Limitações conhecidas

- Sem login: é um app de uso pessoal (um usuário por banco de dados).
- No modo sem IA, uma tradução correta diferente da referência é recusada. Use o
  `PATCH /api/texts/{id}` para trocar a referência, ou ligue a IA.
- A integração com a API da Anthropic foi testada com respostas simuladas, não com chamadas reais.
# English-Trainer
