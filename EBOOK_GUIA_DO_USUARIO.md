# 📘 English Trainer: O Guia Definitivo
### *Como ir do Zero à Fluência no Menor Tempo Possível com Inteligência Artificial e Repetição Espaçada*

---

## 📑 Sumário

1. [A Filosofia: Por que este método funciona?](#1-a-filosofia-por-que-este-método-funciona)
2. [Instalação e Primeiros Passos](#2-instalação-e-primeiros-passos)
3. [Configurando a Inteligência Artificial Gratuita](#3-configurando-a-inteligência-artificial-gratuita)
   - [Google Gemini (Recomendado — Oficial e Gratuito)](#google-gemini-oficial-e-gratuito)
   - [Ollama (100% Local e Sem Internet)](#ollama-local-e-sem-internet)
   - [LM Studio (Local com Interface Gráfica)](#lm-studio-local-com-interface)
4. [A Trilha Estruturada de Gramática (A1 ao C1)](#4-a-trilha-estruturada-de-gramática-a1-ao-c1)
5. [Prática Ativa: As Ferramentas do App](#5-prática-ativa-as-ferramentas-do-app)
   - [Frases e Diálogos Bidirecionais](#frases-e-diálogos-bidirecionais)
   - [Escrita de Textos com Correção Inteligente](#escrita-de-textos-com-correção-inteligente)
   - [Vocabulário e Repetição Espaçada (SRS)](#vocabulário-e-repetição-espaçada-srs)
6. [Recursos de Alta Aceleração de Fluência](#6-recursos-de-alta-aceleração-de-fluência)
   - [Live Conversation: Tutor Bilíngue Ao Vivo (Tempo Real)](#live-conversation-tutor-bilíngue-ao-vivo-tempo-real)
   - [Conversação por Voz Contínua (Hands-Free)](#conversação-por-voz-contínua-hands-free)
   - [Cenários de Trabalho para TI](#cenários-de-trabalho-para-ti)
   - [Relatório do Coach de Carreira e Método STAR](#relatório-do-coach-de-carreira-e-método-star)
   - [Criador de Diálogos sob Demanda com IA](#criador-de-diálogos-sob-demanda-com-ia)
   - [Ear Gym (Academia de Escuta)](#ear-gym-academia-de-escuta)
   - [Modo Shadowing e Sons Conectados (Connected Speech)](#modo-shadowing-e-sons-conectados)
7. [A Rotina de Ouro: Como Estudar no Dia a Dia](#7-a-rotina-de-ouro-como-estudar-no-dia-a-dia)
8. [Segurança e Privacidade](#8-segurança-e-privacidade)

---

## 1. A Filosofia: Por que este método funciona?

A maioria dos cursos tradicionais ensina inglês através de **memorização passiva de regras gramaticais**. O aluno passa anos estudando, mas na hora de uma reunião em inglês (uma *Daily* ou entrevista de emprego), o cérebro trava porque tenta **pensar em português primeiro e depois traduzir palavra por palavra**.

O **English Trainer** foi projetado com base em 4 pilares da ciência da aquisição de linguagem:

1. **Active Recall (Recuperação Ativa):** Você digita ou fala a resposta antes de vê-la. Não existe adivinhação passiva.
2. **Spaced Repetition (SRS):** O que você erra volta em intervalos calculados (1, 2, 4, 8, 16 e 32 dias). Você só revisa o que está prestes a esquecer.
3. **Fluency Latency (Redução da Latência de Resposta):** O app mede em quantos segundos você responde para treinar seu cérebro a pensar direto em inglês.
4. **Contexto Real de Carreira:** Em vez de aprender frases inúteis ("*The book is on the table*"), você aprende o vocabulário de quem trabalha com tecnologia (*deploy, blocker, pull request, code review, root cause*).

---

## 2. Instalação e Primeiros Passos

### Como rodar no seu computador

Abra o terminal na pasta do projeto:

```bash
# 1. Ativar o ambiente virtual Python
source .venv/bin/activate          # No Windows: .venv\Scripts\activate

# 2. Iniciar o servidor local
uvicorn app.main:app --reload
```

Abra o seu navegador em: **`http://localhost:8000`**

### Escolhendo seu Tema (Claro / Escuro)
No canto superior direito, clique no botão **`🌓 Auto`** para alternar entre:
- **☀️ Claro:** Visual limpo e nítido para estudos durante o dia.
- **🌙 Escuro:** Fundo escuro repousante para programar e estudar à noite sem cansar os olhos.
- **🌓 Auto:** Acompanha a preferência do seu sistema operacional.

---

## 3. Configurando a Inteligência Artificial Gratuita

O aplicativo funciona perfeitamente sem IA (modo offline), mas ao ativar um dos motores gratuitos abaixo, o app passa a:
- Traduzir textos instantaneamente.
- Aceitar sinônimos e traduções equivalentes.
- Explicar seus erros com dicas amigáveis em português.
- Conversar por voz com você em reuniões simuladas de TI.

Para configurar, vá na aba **Ajustes** $\rightarrow$ **Inteligência Artificial**.

### Google Gemini (Oficial e Gratuito)
*A opção mais rápida e recomendada para a maioria das pessoas.*
1. Acesse o [Google AI Studio](https://aistudio.google.com/app/apikey) com sua conta Google.
2. Clique em **Create API Key** e copie sua chave gratuita.
3. No app, selecione o provedor **Google Gemini**, cole a chave e deixe o modelo padrão (`gemini-2.5-flash`).
4. Clique em **Salvar Configuração** e depois em **⚡ Testar Conexão**.

### Ollama (Local e Sem Internet)
*Ideal para quem quer privacidade total e não quer gastar internet.*
1. Instale o Ollama no seu Linux/Mac/Windows: `curl -fsSL https://ollama.com/install.sh | sh`.
2. No terminal, baixe um modelo leve e moderno: `ollama run llama3.2`.
3. No app em Ajustes, selecione **Ollama**, clique em **🔍 Detectar modelos** e salve.

### LM Studio (Local com Interface)
1. Baixe o [LM Studio](https://lmstudio.ai/) e abra o app.
2. Baixe qualquer modelo (ex: Llama 3 ou Mistral) e clique na aba com ícone de terminal (**Local Server**) $\rightarrow$ **Start Server**.
3. No app em Ajustes, selecione **LM Studio**, clique em **🔍 Detectar modelos** e salve.

---

## 4. A Trilha Estruturada de Gramática (A1 ao C1)

A aba **Curso** contém 72 lições completas cobrindo todo o Quadro Comum Europeu de Referência (CEFR):

* **A1 (12 lições):** Fundações básicas, verbo to be, presente simples, rotina e perguntas essenciais.
* **A2 (14 lições):** Passado simples, comparativos, planos futuros e situações do dia a dia.
* **B1 (16 lições):** Present Perfect, verbos modais, voz passiva e vocabulário profissional independente.
* **B2 (16 lições):** Condicionais avançadas, phrasal verbs complexos, discurso indireto e reuniões técnicas.
* **C1 (14 lições):** Inversões enfáticas, nuances de linguagem de liderança e fluência sofisticada.

### Como funciona cada lição:
1. **Passo a passo mastigado:** 6 a 8 etapas com explicações simples, analogias do cotidiano e tabelas visuais.
2. **Exemplos com áudio duplo:** Botão `🔊` (velocidade normal) e `🐢` (devagar) para treinar o ouvido.
3. **Exercícios interativos:** Múltipla escolha, ordenar palavras, tradução e ditado.
4. **Mini-teste:** Você precisa atingir **80% de acerto** para concluir a lição. O que você errar entra automaticamente na fila de **Revisão de Gramática**.

---

## 5. Prática Ativa: As Ferramentas do App

### Frases e Diálogos Bidirecionais (Aba Praticar $\rightarrow$ Frases)
- **Fase 1 (Inglês $\rightarrow$ Português):** A frase em inglês aparece (com áudio). Você digita o significado em português.
- **Fase 2 (Português $\rightarrow$ Inglês):** Assim que você acerta, a frase inverte. Ela aparece em português e você precisa digitá-la em inglês correto.
- *Por que isso é poderoso:* Obriga o cérebro a dominar a frase nos dois sentidos, não apenas reconhecer passivamente.

### Escrita de Textos com Correção Inteligente (Aba Praticar $\rightarrow$ Meus Textos)
- Escreva parágrafos sobre seus projetos, seu trabalho ou sua rotina.
- O que você não souber, pode deixar a palavra em português!
- A IA identifica:
  - 🟩 **Verde:** Palavras corretas.
  - 🟨 **Amarelo:** Quase lá (erro leve de digitação ou acento).
  - 🟥 **Vermelho:** Palavras em português ou com erro gramatical.
- As palavras que você errou vão automaticamente para a repetição espaçada.

### Vocabulário e Repetição Espaçada (SRS) (Aba Revisão)
- O app armazena todas as palavras novas que você encontra nos textos, frases e conversas.
- O algoritmo de repetição distribui as revisões no tempo exato em que a curva do esquecimento de Ebbinghaus começaria a apagar a memória:
  - **Caixa 1:** volta em 1 dia
  - **Caixa 2:** volta em 2 dias
  - **Caixa 3:** volta em 4 dias
  - **Caixa 4:** volta em 8 dias
  - **Caixa 5:** volta em 16 dias
  - **Caixa 6:** volta em 32 dias (Palavra dominada!)

---

## 6. Recursos de Alta Aceleração de Fluência

### Live Conversation: Tutor Bilíngue Ao Vivo (Tempo Real)
Aba **Praticar $\rightarrow$ Live Voice Tutor 🎙️** (ou clique no card da aba **Hoje**).

Esta é a ferramenta mais avançada do aplicativo: uma chamada de voz duplex em tempo real com um tutor nativo e paciente, operando via **WebSocket** de baixa latência (integrado à **Gemini Multimodal Live API** com autenticação protegida por **Token Efêmero** gerado no backend, sem nunca expor suas chaves de API no navegador).

#### Principais Recursos do Live Voice Tutor:
1. **Controles Centrais de Chamada:** Um botão elegante de iniciar/encerrar chamada telefônica (`📞 Iniciar` e `🛑 Encerrar`).
2. **Visualizador de Ondas Sonoras (Soundwave):** Canvas responsivo de 60 FPS que reflete a intensidade da sua voz no microfone em tempo real e pulsa na frequência da voz do tutor quando ele estiver falando.
3. **Barge-in Natural (Interrupção Espontânea):** Em uma conversa humana real, não esperamos o outro terminar 100% de falar para intervir. O app detecta quando você começa a falar e **interrompe o áudio do tutor instantaneamente**, exatamente como em uma reunião de trabalho real no Zoom ou Google Meet.
4. **Cards Discretos de Recasting:** Quando você cometer um erro de gramática ou usar uma expressão pouco natural, o tutor não interrompe a conversa com broncas chatas. Ele continua o diálogo normalmente e a interface exibe um card visual discreto:
   - **Você disse:** (seu texto original riscado)
   - **Forma natural:** (a expressão recomendada em inglês)
   - Botão **🔊 Ouvir** para escutar a pronúncia nativa da forma correta.
5. **Seletor de Cenários Profissionais:**
   - 💼 **Daily Stand-up:** Reunião matinal de alinhamento com seu Tech Lead.
   - 🎯 **Entrevista de Emprego:** Perguntas sobre sua carreira técnica, projetos e desafios.
   - ☕ **Conversa Casual:** Bate-papo informal de *coffee break* sobre hobbies, viagens e cotidiano.
6. **Suporte Total a Código Misto (Code-Switching):** Se você esquecer uma palavra e falar em português (ou perguntar *"como se diz deploy em português?"*), o tutor entende perfeitamente e responde naturalmente em inglês ajudando você a continuar o raciocínio.
7. **Modo Duplex Offline / Local:** Se você estiver usando Ollama, LM Studio ou não possuir chave da Gemini Live, o sistema chaveia automaticamente para o modo duplex local garantindo que o recurso nunca fique fora do ar.

### Conversação por Voz Contínua (Hands-Free)
Na aba **Conversação** $\rightarrow$ **Conversar com a IA**, marque a caixinha:
> **`🎙️ Modo Conversa Contínua (Hands-Free)`**

1. A IA fala a resposta dela em inglês.
2. Assim que o áudio da IA termina, **o microfone abre sozinho**.
3. Você responde falando em inglês.
4. A IA processa, corrige seus deslizes e responde de volta em áudio.
*Resultado:* Você treina conversação como em uma chamada real do Google Meet ou Slack Huddle.

### Cenários de Trabalho para TI
Pratique com papéis pré-configurados:
* **Daily Stand-up:** Reportar o que fez ontem, o que fará hoje e impedimentos.
* **Code Review:** Discutir decisões de arquitetura e comentários em um Pull Request.
* **Incidente em Produção:** Explicar para o Engineering Manager a causa raiz e o plano de mitigação.
* **Entrevista Técnica:** Responder sobre sua stack, projetos passados e tomadas de decisão.
* **Demo para o Cliente:** Apresentar uma funcionalidade sem usar jargões excessivos.

### Relatório do Coach de Carreira e Método STAR
Ao final de qualquer conversa com a IA, clique no botão **`📊 Relatório do Coach`**:
1. **Nota Geral de Fluência (0 a 100).**
2. **💎 Upgrades de Vocabulário:** Mostra como trocar verbos básicos por vocabulário mais sênior (ex: em vez de *"I did the database change"*, usar *"I migrated and optimized the database schema"*).
3. **⭐ Estrutura STAR:** Como organizar sua fala no padrão gringo:
   - **S (Situation):** O contexto inicial.
   - **T (Task):** O desafio que você tinha.
   - **A (Action):** O que você fez tecnicamente.
   - **R (Result):** O resultado em métricas e estabilidade.

### Criador de Diálogos sob Demanda com IA
Na aba **Conversação** $\rightarrow$ **✨ Criar Diálogo sob Demanda**:
- Digite qualquer situação que você precise enfrentar:
  > *"Conversa em inglês pedindo aumento salarial em dólar"* ou *"Alinhamento com DevOps sobre Kubernetes e CI/CD"*.
- A IA cria na hora um diálogo de 6 a 8 falas com áudio e vocabulário e salva no seu banco para você praticar imediatamente!

### Ear Gym (Academia de Escuta)
Na aba **Praticar** $\rightarrow$ **Ear Gym (Escuta)**:
- Você ouve a frase em velocidade real e vê a frase com uma lacuna (`______`).
- Seu trabalho é preencher a palavra que falta (digitando ou falando no microfone).
- Treina especificamente a audição para entender nativos falando rápido.

### Modo Shadowing e Sons Conectados
Na aba **Praticar** $\rightarrow$ **Pronúncia**:
- Clique em **`🔄 Treinar Shadowing (Loop)`**: o app toca a frase, espera 2 segundos para você falar por cima imitando a entonação e ritmo, e toca de novo em loop.
- O app exibe o card **`⚡ Dica de ritmo nativo (Connected Speech)`** ensinando as ligações de som (ex: *going to $\rightarrow$ gonna*, *did you $\rightarrow$ did-ja*).

---

## 7. A Rotina de Ouro: Como Estudar no Dia a Dia

Para acelerar ao máximo sem se sobrecarregar, siga este plano diário:

| Tempo | O que fazer no app |
|---|---|
| **Primeiros 10 min** | Fazer a fila da aba **Revisão** (Palavras pendentes do SRS para não esquecer o vocabulário). |
| **Próximos 15 min** | Fazer 1 lição nova da aba **Curso** (Teoria mastigada + exercícios + mini-teste). |
| **Próximos 15 min** | Ir na aba **Conversação** e fazer 1 simulação de TI por voz (Daily ou Entrevista) com o microfone ativo. |
| **Últimos 5 min** | Fazer 3 rodadas no **Ear Gym** para afiar os ouvidos para a fala rápida. |

> [!TIP]
> **Total: 45 minutos por dia.** Com essa consistência diária, você sai do zero para o nível conversacional independente em **6 a 9 meses**.

---

## 8. Segurança e Privacidade

O repositório do seu projeto é aberto e público no GitHub. Para proteger seus dados:
- O arquivo `.gitignore` foi configurado para **nunca subir**:
  - Seu banco de dados SQLite (`data/english_trainer.db`), onde ficam seu progresso, histórico de estudo e chaves de API salvas.
  - Arquivos de áudio gerados em cache local (`data/audio_cache/`).
  - Arquivos de variáveis de ambiente (`.env`).
  - Arquivos de compilação do Python (`__pycache__`).
- Tudo o que você faz no app fica armazenado **apenas no seu computador pessoal**.

---

*English Trainer — Bons estudos e rumo à sua carreira internacional!* 🚀
