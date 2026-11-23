"use strict";
// ============================================================== HOJE, PROGRESSO, LEITURA, PRONÚNCIA, METAS, tempo ativo

// ---------------------------------------------------------------- tempo ativo (só conta com a aba visível e atividade recente)
(function trackTime() {
  let lastAct = Date.now();
  ["pointerdown", "keydown", "scroll", "touchstart"].forEach((e) => window.addEventListener(e, () => { lastAct = Date.now(); }, { passive: true }));
  setInterval(() => {
    if (document.visibilityState !== "visible" || Date.now() - lastAct > 90000) return;
    api("/api/study/ping", { method: "POST", body: { seconds: 30, tz_offset_min: -new Date().getTimezoneOffset() } }).catch(() => {});
  }, 30000);
})();

function fmtDays(d) {
  if (d == null) return "—";
  if (d < 45) return `${d} dias`;
  const m = d / 30;
  return m < 24 ? `${m.toFixed(1).replace(".", ",")} meses` : `${(m / 12).toFixed(1).replace(".", ",")} anos`;
}

function scenariosTable(est) {
  return h("div", { class: "tbl" }, h("table", {}, h("thead", {}, h("tr", {}, ["Estudando por dia", "Até o C1"].map((x) => h("th", {}, x)))),
    h("tbody", {}, est.scenarios.map((s) => h("tr", {}, h("td", {}, s.minutes >= 60 ? `${s.minutes / 60} h` : `${s.minutes} min`), h("td", {}, fmtDays(s.days_to_c1)))))));
}

// ---------------------------------------------------------------- HOJE
const TASK_ICON = { words: "🔤", grammar: "🧩", lesson: "📘", reading: "📖", pronunciation: "🎤" };
async function viewToday() {
  const p = await api("/api/plan/today");
  const goals = [15, 30, 60, 90, 120, 180];
  const goalSel = h("select", { "aria-label": "Meta diária", style: "width:auto" }, goals.map((g) => h("option", { value: g, selected: g === p.goal_minutes }, g >= 60 ? `${g / 60} h por dia` : `${g} min por dia`)));
  goalSel.addEventListener("change", async () => { await api("/api/plan", { method: "PUT", body: { daily_minutes: Number(goalSel.value) } }); viewToday(); });
  const open = (t) => {
    if (t.kind === "words") go("review");
    else if (t.kind === "grammar") go("grammar");
    else if (t.kind === "lesson") openLesson(t.lesson_id);
    else if (t.kind === "reading") { state.readingId = t.reading_id; go("reading"); }
    else go("pronounce");
  };
  const e = p.estimate;
  put(view,
    !p.placement_done ? h("div", { class: "card" }, h("h2", {}, "Descubra seu nível"),
      h("p", {}, "Faça o teste de nível (30 perguntas, ~10 min) e o curso começa no ponto certo para você."),
      h("div", { class: "row" }, h("button", { class: "btn primary", onclick: () => go("placement") }, "Fazer o teste"))) : null,
    h("div", { class: "card" },
      h("div", { class: "row" }, h("h2", { style: "margin:0" }, "Plano de hoje"), h("span", { class: "lvl" }, p.level), h("div", { class: "grow" }), goalSel),
      h("div", { class: "kpis" },
        h("div", { class: "kpi" }, h("b", {}, `${p.done_minutes} / ${p.goal_minutes} min`), h("span", {}, "tempo de estudo hoje"), bar(p.percent, p.percent >= 100 ? "ok" : "")),
        h("div", { class: "kpi" }, h("b", {}, `🔥 ${p.streak.current} ${p.streak.current === 1 ? "dia" : "dias"}`), h("span", {}, p.streak.studied_today ? "sequência — hoje já valeu!" : "sequência — estude hoje para mantê-la")),
        h("div", { class: "kpi" }, h("b", {}, e.next_level ? fmtDays(e.days_to_next) : "—"), h("span", {}, e.next_level ? `até o ${e.next_level}, no seu ritmo` : "nível máximo"))),
      p.tasks.map((t) => h("div", { class: "task" }, h("div", { class: "ico" }, TASK_ICON[t.kind]),
        h("div", { class: "body" }, h("b", {}, t.title), h("small", {}, `${t.detail} · ~${t.minutes} min`)),
        h("button", { class: "btn" + (t.kind === "lesson" ? " primary" : ""), onclick: () => open(t) }, t.kind === "lesson" && t.started ? "Continuar" : "Começar")))),
    h("div", { class: "card" }, h("h3", {}, "Quanto tempo falta até o C1?"),
      h("p", { class: "muted" }, `No ritmo atual (${e.pace_minutes} min/dia): cerca de ${e.hours_to_c1} h de estudo restantes, ou ${fmtDays(e.days_to_c1)}.`),
      scenariosTable(e), h("p", { class: "muted" }, e.note)));
}

// ---------------------------------------------------------------- PROGRESSO
async function viewProgress() {
  const p = await api("/api/progress");
  const max = Math.max(30, ...p.days.map((d) => d.minutes));
  put(view,
    h("div", { class: "card" }, h("h2", {}, "Seu progresso"),
      h("div", { class: "kpis" },
        h("div", { class: "kpi" }, h("b", {}, `${p.lessons_done}/${p.lessons_total}`), h("span", {}, "lições concluídas")),
        h("div", { class: "kpi" }, h("b", {}, p.total_hours + " h"), h("span", {}, "tempo de estudo ativo")),
        h("div", { class: "kpi" }, h("b", {}, `🔥 ${p.streak.current}`), h("span", {}, `dias seguidos (recorde ${p.streak.best})`)),
        h("div", { class: "kpi" }, h("b", {}, `${p.words.learned}/${p.words.total}`), h("span", {}, "palavras bem aprendidas")),
        h("div", { class: "kpi" }, h("b", {}, `${p.grammar.mastered}/${p.grammar.total}`), h("span", {}, "itens de gramática dominados")),
        h("div", { class: "kpi" }, h("b", {}, `${p.readings.done}/${p.readings.total}`), h("span", {}, "textos lidos")),
        h("div", { class: "kpi" }, h("b", {}, p.pronunciation.attempts ? p.pronunciation.average + "%" : "—"), h("span", {}, "nota média de pronúncia"))),
      h("h3", {}, "Por nível"),
      p.levels.map((l) => h("div", { class: "row", style: "margin:6px 0" }, h("span", { class: "lvl" }, l.level), h("span", { style: "min-width:150px" }, LEVEL_NAMES[l.level]),
        h("div", { class: "grow" }, bar(l.percent, l.percent === 100 ? "ok" : "")), h("span", { class: "muted", style: "min-width:48px;text-align:right" }, `${l.done}/${l.total}`)))),
    h("div", { class: "card" }, h("h3", {}, "Minutos estudados nos últimos 14 dias"),
      h("div", { class: "bars", role: "img", "aria-label": "Minutos por dia" }, p.days.map((d) =>
        h("div", { title: `${d.day}: ${d.minutes} min` }, d.minutes ? h("span", {}, d.minutes) : null, h("i", { class: d.minutes ? "" : "zero", style: `height:${Math.max(2, 100 * d.minutes / max)}%` })))),
      h("div", { class: "muted" }, "Cada barra é um dia (o último é hoje).")),
    h("div", { class: "card" }, h("h3", {}, "Pontos fracos"),
      p.weak.length ? [h("p", { class: "muted" }, "Assuntos em que você mais erra. Reveja a lição e faça a revisão de gramática."),
        p.weak.map((w) => h("button", { class: "list-row", type: "button", onclick: () => openLesson(w.lesson_id) }, h("span", { class: "lvl" }, w.level), h("span", { style: "flex:1" }, h("b", {}, w.title), h("div", { class: "muted" }, w.unit)), h("span", { class: "muted" }, `${w.accuracy}% de acerto`)))]
        : h("p", { class: "muted" }, "Ainda sem dados suficientes. Conforme você praticar, os assuntos com mais erros aparecem aqui.")),
    h("div", { class: "card" }, h("h3", {}, "Previsão"),
      h("p", { class: "muted" }, `Nível atual: ${p.current_level}. Faltam cerca de ${p.estimate.hours_to_c1} h de estudo para o C1.`), scenariosTable(p.estimate), h("p", { class: "muted" }, p.estimate.note)));
}

// ---------------------------------------------------------------- LEITURA E ESCUTA
async function viewReading() {
  if (state.readingId) { const id = state.readingId; state.readingId = null; return readingPlayer(id); }
  const r = await api("/api/reading");
  const lv = state.readLevel || r.current_level;
  const draw = (level) => {
    state.readLevel = level;
    put(card, h("h2", {}, "Leitura e escuta por nível"),
      h("p", { class: "muted" }, "Leia ou só ouça o texto, responda às perguntas e mande todas as palavras para a revisão."),
      h("div", { class: "levels" }, ["A1", "A2", "B1", "B2", "C1"].map((l) => h("button", { type: "button", "aria-current": l === level ? "true" : null, onclick: () => draw(l) }, h("b", {}, l), h("small", {}, `${r.texts.filter((t) => t.level === l && t.done).length}/${r.texts.filter((t) => t.level === l).length}`)))),
      r.texts.filter((t) => t.level === level).map((t) => h("button", { class: "list-row", type: "button", onclick: () => readingPlayer(t.id) },
        h("span", { class: "st" }, t.done ? "✓" : ""), h("span", { style: "flex:1" }, h("b", {}, t.title), h("div", { class: "muted" }, t.topic)), h("span", { class: "muted" }, t.done ? `${t.score}%` : ""))));
  };
  const card = h("div", { class: "card" });
  put(view, card);
  draw(lv);
}

async function readingPlayer(id) {
  const r = await api(`/api/reading/${id}`);
  const card = h("div", { class: "card" });
  put(view, card);
  let listenOnly = false;
  const paras = r.text.split(/\n\n+/);

  function show() {
    const textEl = h("div", { class: "reading-text" + (listenOnly ? " hidden" : "") }, paras.map((p) => h("p", {}, p, " ", speakBtn(p))));
    const only = h("input", { type: "checkbox", checked: listenOnly });
    only.addEventListener("change", () => { listenOnly = only.checked; show(); });
    put(card, h("div", { class: "lesson-head" }, h("span", { class: "lvl" }, r.level), h("span", { class: "muted" }, r.topic),
      h("button", { class: "linkbtn", style: "margin-left:auto", onclick: () => go("reading") }, "← Textos")),
      h("h2", {}, r.title),
      h("div", { class: "row" }, h("button", { class: "btn", onclick: () => Voice.speak(r.text.replace(/\n\n+/g, " ... ")) }, "🔊 Ouvir tudo"),
        h("button", { class: "btn", onclick: () => Voice.speak(r.text.replace(/\n\n+/g, " ... "), { rate: 0.7 }) }, "🐢 Devagar"), h("button", { class: "btn", onclick: () => Voice.stop() }, "■ Parar"),
        h("label", { class: "chk", style: "padding:0" }, only, "Só escutar (esconde o texto)")),
      textEl,
      h("h3", {}, "Vocabulário do texto"), h("div", { class: "vocab-grid" }, r.vocab.map((v) => h("button", { type: "button", onclick: () => Voice.speak(v.word) }, h("b", {}, v.word, " 🔊"), h("small", {}, v.pt)))),
      h("div", { class: "row", style: "margin-top:16px" }, h("button", { class: "btn primary", onclick: questions }, "Responder às perguntas →")));
  }

  function questions() {
    const holder = h("div", {});
    put(card, h("h2", {}, r.title), h("div", { class: "muted" }, "Compreensão do texto"), holder);
    runSequence(holder, r.questions, {
      label: "Pergunta",
      onFinish: async (answers) => {
        try { done(await api(`/api/reading/${id}/check`, { method: "POST", body: { answers } })); } catch (e) { put(holder, errBox(e)); }
      },
    });
  }

  function done(res) {
    const byId = Object.fromEntries(r.questions.map((q) => [q.id, q]));
    const added = h("div", {});
    put(card, h("h2", {}, r.title), h("div", { class: "score " + (res.score >= 60 ? "ok" : "bad") }, res.score + "%"),
      h("p", { class: "center" }, `${res.right} de ${res.total} certas.`),
      res.results.map((x, i) => h("div", { class: "qreview" }, h("span", { class: x.correct ? "yes" : "no" }, (x.correct ? "✔ " : "✘ ") + (i + 1) + ". "), byId[x.id].prompt,
        !x.correct ? h("div", {}, "Certa: ", h("b", {}, x.expected)) : null, h("div", { class: "muted" }, inline(x.explain)))),
      h("details", { open: true, style: "margin-top:10px" }, h("summary", {}, "Tradução do texto"), res.pt.split(/\n\n+/).map((p) => h("p", {}, p))),
      h("div", { class: "row", style: "margin-top:12px" },
        h("button", { class: "btn primary", onclick: async (ev) => {
          ev.target.disabled = true;
          try { const a = await api(`/api/reading/${id}/words`, { method: "POST" }); put(added, h("div", { class: "box ok" }, `${a.added} palavra(s) nova(s) adicionadas à revisão (${a.total} no texto).`)); } catch (e) { put(added, errBox(e)); }
        } }, "➕ Mandar as palavras do texto para a revisão"),
        h("button", { class: "btn", onclick: () => go("reading") }, "Outros textos")), added);
  }
  show();
}

// ---------------------------------------------------------------- PRONÚNCIA
async function viewPronounce() {
  const card = h("div", { class: "card" });
  put(view, card);
  const lvSel = h("select", { "aria-label": "Nível", style: "width:auto" }, ["A1", "A2", "B1", "B2", "C1"].map((l) => h("option", { value: l, selected: l === state.pronLevel }, l)));
  const session = [];
  let sentence = null;

  async function load() {
    const s = await api(`/api/pronunciation/next?level=${state.pronLevel || ""}${sentence ? "&exclude=" + encodeURIComponent(sentence.en) : ""}`);
    sentence = s; state.pronLevel = s.level; lvSel.value = s.level;
    draw();
    if (Voice.prefs.auto) Voice.speak(s.en);
  }
  lvSel.addEventListener("change", () => { state.pronLevel = lvSel.value; sentence = null; load(); });
  const out = h("div", {});

  async function evaluate(spoken) {
    try {
      const r = await api("/api/pronunciation/compare", { method: "POST", body: { target: sentence.en, spoken } });
      session.push(r.score);
      put(out, h("div", { class: "score " + (r.score >= 75 ? "ok" : "bad") }, r.score + "%"), h("p", { class: "center" }, r.verdict[0].toUpperCase() + r.verdict.slice(1) + (r.perfect ? " — perfeito!" : ".")),
        h("div", { class: "box info" }, h("div", { class: "muted" }, "O que o navegador entendeu:"), marksEl(r.marks, r.missing)),
        h("p", { class: "muted" }, "A nota compara o que o reconhecimento de voz entendeu com a frase. Palavras em vermelho foram entendidas errado ou não foram ouvidas: ouça de novo e repita mais devagar."),
        h("div", { class: "row end" }, h("button", { class: "btn primary", onclick: load }, "Próxima frase →")));
    } catch (e) { put(out, errBox(e)); }
  }

  function draw() {
    const mic = h("button", { class: "mic-big", type: "button", "aria-label": "Falar", title: "Clique, fale a frase e aguarde" }, "🎤");
    mic.addEventListener("click", async () => {
      if (mic.classList.contains("rec")) { Voice.stopListening(); return; }
      mic.classList.add("rec"); put(out, h("p", { class: "muted center" }, "Estou ouvindo… fale a frase."));
      try { await evaluate(await Voice.listen("en-US")); } catch (e) { put(out, h("div", { class: "box warn" }, e.message)); } finally { mic.classList.remove("rec"); }
    });
    const typed = h("input", { type: "text", placeholder: "Sem microfone? Digite o que você falaria…", "aria-label": "Texto falado" });
    typed.addEventListener("keydown", (e) => { if (e.key === "Enter" && typed.value.trim()) evaluate(typed.value); });
    put(card, h("div", { class: "row" }, h("h2", { style: "margin:0" }, "Pronúncia com nota"), h("div", { class: "grow" }), lvSel),
      h("p", { class: "muted" }, "Ouça, depois fale a frase no microfone. Você recebe uma nota de 0 a 100. Funciona melhor no Chrome ou no Edge."),
      h("div", { class: "big", style: "font-size:26px" }, sentence.en), h("div", { class: "row", style: "justify-content:center" }, speakBtn(sentence.en), speakBtn(sentence.en, { slow: true })),
      h("p", { class: "center muted" }, sentence.pt + " · " + sentence.lesson),
      h("div", { class: "row", style: "justify-content:center;margin:12px 0" }, Voice.SR ? mic : h("div", { class: "box warn" }, "Este navegador não reconhece fala. Use o Chrome/Edge ou digite abaixo.")),
      Voice.SR ? null : h("div", { class: "row" }, h("div", { class: "grow" }, typed)),
      out, session.length ? h("p", { class: "muted center" }, `Nesta sessão: ${session.length} frase(s), média ${Math.round(session.reduce((a, b) => a + b, 0) / session.length)}%`) : null);
  }
  await load();
}

// ---------------------------------------------------------------- Ajustes: meta e nível inicial
async function planSettingsCard() {
  const p = await api("/api/plan");
  const goal = h("select", { "aria-label": "Meta diária" }, [15, 30, 45, 60, 90, 120, 180].map((g) => h("option", { value: g, selected: g === p.daily_minutes }, g >= 60 ? `${g / 60} h por dia` : `${g} min por dia`)));
  goal.addEventListener("change", () => api("/api/plan", { method: "PUT", body: { daily_minutes: Number(goal.value) } }).then(() => toast("Meta salva.")));
  const lv = h("select", { "aria-label": "Nível inicial" }, ["A1", "A2", "B1", "B2", "C1"].map((l) => h("option", { value: l, selected: l === p.start_level }, l + " — " + LEVEL_NAMES[l])));
  lv.addEventListener("change", () => api(`/api/course/start-level/${lv.value}`, { method: "PUT" }).then(() => toast("Nível inicial salvo.")));
  return h("div", { class: "card" }, h("h3", {}, "Meta e nível"),
    h("div", { class: "row" }, h("span", {}, "Meta diária"), h("div", { class: "grow" }, goal)),
    h("div", { class: "row", style: "margin-top:8px" }, h("span", {}, "Começar o curso em"), h("div", { class: "grow" }, lv)),
    h("p", { class: "muted" }, p.placement_level ? `Resultado do último teste de nível: ${p.placement_level}.` : "Você ainda não fez o teste de nível."),
    h("button", { class: "btn", onclick: () => go("placement") }, "Fazer o teste de nível"));
}
