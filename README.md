# English Trainer

Aplicativo (Python + FastAPI + SQLite) para aprender inglês digitando.

## Como rodar

Se você já usava uma versão anterior, extraia o zip por cima da pasta (`unzip -o english_trainer.zip -d ~`):
a pasta `data/` com seus textos, palavras e progresso não é tocada, e o conteúdo novo é instalado sozinho.

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

**Novidades (áudio, conversação e TI):** ouvir e falar (voz do navegador), aba **Conversação**
(interpretar diálogos e conversar com a IA), revisão em 3 modos e vocabulário de desenvolvimento
de software. Detalhes nas seções 4 a 7 abaixo.

**1. Frases e diálogos.** Aparece a frase em inglês e você digita em português. Ao acertar, ela
inverte: aparece em português e você digita em inglês. A frase só conta como concluída quando
as duas etapas estão certas. Vêm 12 diálogos prontos (3 do dia a dia e 9 de TI), e você pode criar os seus
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

**4. Áudio.** Usa a voz e o microfone do próprio navegador (sem serviço externo, sem custo).
Há botões 🔊 (normal) e 🐢 (devagar) nas frases, diálogos, textos aprovados, palavras e exemplos, e
o botão 🎤 para responder falando. O modo **Ditado** (aba Frases) fala a frase e você digita o que
ouviu. Em Ajustes → Áudio você escolhe a voz, a velocidade e se o app fala sozinho.
- Voz: usa a síntese de fala dos navegadores modernos. No **Linux** o navegador precisa de uma voz do sistema:
  `sudo apt install speech-dispatcher espeak-ng` e reiniciar o navegador.
- Microfone (reconhecimento de fala): só **Chrome ou Edge**, precisa de internet e de permissão do
  microfone. Funciona em `http://localhost`; por outro endereço (ex.: IP da rede) o navegador bloqueia.

**5. Conversação.**
- *Interpretar um diálogo* (funciona sem IA): escolha um diálogo e seu personagem. As falas dos
  outros são faladas em inglês e, nas suas, você vê a dica em português e responde em inglês
  (digitando ou falando). Só avança quando acerta.
- *Conversar com a IA* (precisa de `ANTHROPIC_API_KEY`): cenários de empresa de TI (daily, code
  review, incidente, planejamento, entrevista, demo para cliente, café com colegas e conversa
  livre), com nível A2, B1 ou B2. A IA responde, você pode ver a tradução, e cada mensagem sua
  recebe correção. O que você errou vai para a revisão. A conversa fica só no navegador.

**6. Revisão em 3 modos.** Ver a palavra e digitar o significado; ver o significado e escrever a
palavra; ou ouvir e digitar a palavra (este não precisa de significado salvo). Dá para treinar só o
vocabulário de TI. No Vocabulário há filtros *Em aprendizado* e *Aprendidas* (acertou várias vezes).
Palavras de textos novos já vêm com significado quando estão no glossário embutido (cerca de 490
palavras); as demais você preenche na aba Vocabulário (filtro *Sem significado*) ou a IA traduz.

**7. Conteúdo de TI.** 9 diálogos (daily stand-up, code review, reportar bug, incidente em produção,
planejamento de sprint, entrevista técnica, deploy, pedir ajuda, frases úteis para a daily) e
121 termos de desenvolvimento (sprint, backlog, blocker, pull request, rollback, root cause…)
com significado e frase de exemplo, marcados com a etiqueta **TI**. Quem já usava o app recebe tudo
automaticamente ao iniciar, sem perder dados.

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
app/routes/conversation.py  role-play e conversa com a IA
app/scenarios.py     cenários da conversa livre
app/content_it.py    diálogos, termos e glossário de TI
app/seed.py          diálogos e glossário iniciais
app/static/index.html  interface
```

## Limitações conhecidas

- Sem login: é um app de uso pessoal (um usuário por banco de dados).
- No modo sem IA, uma tradução correta diferente da referência é recusada. Use o
  `PATCH /api/texts/{id}` para trocar a referência, ou ligue a IA.
- A integração com a API da Anthropic foi testada com respostas simuladas, não com chamadas reais.
- Áudio e microfone foram testados com a fala simulada; a qualidade da voz depende do seu sistema/navegador.
- O microfone transcreve o que ouve, então números ("10" x "ten") e sotaque podem gerar diferenças:
  você pode editar o texto antes de verificar.
