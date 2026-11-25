"use strict";
// ============================================================== CURSO: aulas, exercícios, revisão de gramática, teste de nível
// Usa h(), put(), api(), Voice, speakBtn(), micBtn(), marksEl(), errBox(), go(), view, state do index.html.

// markdown mínimo e seguro (negrito, itálico, parágrafos) — monta nós, nunca usa innerHTML
function inline(text) {
  const out = [];
  const re = /\*\*(.+?)\*\*|\*(.+?)\*/g;
  let last = 0, m;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    out.push(m[1] !== undefined ? h("b", {}, m[1]) : h("i", {}, m[2]));
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}
function md(text) {
  return h("div", { class: "prose" }, String(text || "").split(/\n\n+/).map((p) => h("p", {}, inline(p))));
}
function bar(pct, cls = "") { return h("div", { class: "pbar " + cls }, h("i", { style: `width:${Math.max(0, Math.min(100, pct))}%` })); }
const LEVEL_NAMES = { A1: "Iniciante", A2: "Básico", B1: "Intermediário", B2: "Intermediário superior", C1: "Avançado" };

// ---------------------------------------------------------------- exercício genérico
// ex: exercício público. opts.check(answer) -> Promise<resultado|null> (null = sem feedback imediato).
// opts.onDone(answer, result) é chamado ao avançar. Devolve o elemento.
function exerciseView(ex, opts) {
  const root = h("div", { class: "exercise", "data-ex": ex.id });
  const target = LangSwitcher.target();
  const out = h("div", {});
  let answer = null, locked = false;

  async function submit(value) {
    if (locked) return;
    locked = true;
    answer = value;
    let res = null;
    try { res = opts.check ? await opts.check(value) : null; } catch (e) { locked = false; put(out, errBox(e)); return; }
    if (!res) { opts.onDone(value, null); return; }
    lock(res);
    showResult(res);
  }
  let lock = () => {};

  function showResult(res) {
    const kids = [h("div", { class: "box " + (res.correct ? "ok" : "bad") }, res.correct ? "✔ Certo!" : "✘ Não foi dessa vez.")];
    if (ex.type !== "choice" && res.marks && res.marks.length) kids.push(marksEl(res.marks));
    if (!res.correct) kids.push(h("div", { class: "box info" }, "Resposta esperada: ", h("b", {}, res.expected), " ", speakBtn(res.expected)));
    if (res.why_not) kids.push(h("div", { class: "box warn" }, inline(res.why_not)));
    kids.push(h("div", { class: "box info explain" }, h("b", {}, "Por quê? "), inline(res.explain)));
    if (ex.type === "listen" || ex.type === "translate") { /* áudio da resposta certa já está no botão acima */ }
    kids.push(h("div", { class: "row end", style: "margin-top:10px" },
      h("button", { class: "btn primary", id: "ex-next", onclick: () => opts.onDone(answer, res) }, opts.nextLabel || "Continuar →")));
    put(out, kids);
    const b = out.querySelector("#ex-next"); if (b) b.focus();
  }

  const prompt = h("div", { class: "ex-prompt" }, ex.prompt ? inline(ex.prompt) : "");
  const body = h("div", {});
  const t = ex.type;
  if (t === "choice") {
    const buttons = ex.options.map((o, i) => h("button", { class: "opt", type: "button", onclick: () => submit(i) }, o));
    put(body, h("div", { class: "opts" }, buttons));
    lock = (res) => {
      buttons.forEach((b, i) => {
        b.disabled = true;
        if (res.expected === ex.options[i]) b.classList.add("right");
        else if (i === answer) b.classList.add("wrong");
      });
    };
  } else if (t === "order") {
    const bank = h("div", { class: "chips", "aria-label": "Palavras disponíveis" });
    const line = h("div", { class: "chips", "aria-label": "Sua frase" });
    const chips = ex.words.map((w) => {
      const c = h("button", { class: "chip", type: "button" }, w);
      c.addEventListener("click", () => {
        if (locked) return;
        if (c.parentElement === bank) { line.append(c); c.classList.add("sel"); } else { bank.append(c); c.classList.remove("sel"); }
      });
      return c;
    });
    bank.append(...chips);
    const send = h("button", { class: "btn primary", type: "button", onclick: () => { const v = [...line.children].map((c) => c.textContent).join(" "); if (v) submit(v); } }, "Verificar");
    put(body, h("div", { class: "muted" }, "Toque nas palavras na ordem certa:"), line, bank, h("div", { class: "row end" }, send));
    lock = () => { chips.forEach((c) => { c.disabled = true; }); send.disabled = true; };
  } else {
    const input = h("input", { type: "text", autocomplete: "off", autocapitalize: "off", spellcheck: "false", "aria-label": "Sua resposta",
      placeholder: t === "listen" ? "Digite o que você ouviu…" : t === "fix" ? "Escreva a frase corrigida…" : t === "fill" ? "Palavra que falta…" : `Escreva em ${target.name}…` });
    const send = h("button", { class: "btn primary", type: "button", onclick: () => { if (input.value.trim()) submit(input.value); } }, "Verificar");
    input.addEventListener("keydown", (e) => { if (e.key === "Enter" && input.value.trim()) submit(input.value); });
    const mic = t === "translate" || t === "listen" || t === "fix" ? micBtn((txt) => { input.value = txt; input.focus(); }) : null;
    const listenRow = t === "listen" ? h("div", { class: "row", style: "justify-content:center;margin:6px 0 12px" }, speakBtn(ex.speak), speakBtn(ex.speak, { slow: true })) : null;
    put(body, listenRow, h("div", { class: "row" }, h("div", { class: "grow" }, input), mic, send));
    lock = () => { input.disabled = true; send.disabled = true; };
    setTimeout(() => { if (root.isConnected) input.focus(); }, 30);
    if (t === "listen" && Voice.prefs.auto) setTimeout(() => Voice.speak(ex.speak), 150);
  }
  const hint = { fill: "Complete a frase", translate: `Traduza para o ${target.name}`, fix: "Corrija a frase", order: `Monte a frase em ${target.name}`, listen: "Ditado", choice: "Escolha a opção certa" }[t];
  put(root, h("div", { class: "stage" }, hint), prompt, body, out);
  return root;
}

// roda uma lista de exercícios um a um. opts: {check(ex, answer), title, onFinish(answers), showCount}
function runSequence(container, exercises, opts) {
  let i = 0;
  const answers = {};
  const results = {};
  function step() {
    if (i >= exercises.length) { opts.onFinish(answers, results); return; }
    const ex = exercises[i];
    const head = h("div", { class: "row", style: "margin-bottom:6px" },
      h("span", { class: "muted" }, `${opts.label || "Exercício"} ${i + 1} de ${exercises.length}`), h("div", { class: "grow" }, bar(100 * i / exercises.length, "thin")));
    put(container, head, exerciseView(ex, {
      check: opts.check ? (a) => opts.check(ex, a) : null,
      nextLabel: i + 1 === exercises.length ? "Concluir →" : "Continuar →",
      onDone: (a, r) => { answers[ex.id] = a; results[ex.id] = r; i++; step(); },
    }));
    if (opts.skip) container.append(h("div", { class: "row end", style: "margin-top:12px" },
      h("button", { class: "linkbtn", type: "button", onclick: () => { answers[ex.id] = null; i++; step(); } }, "Não sei — pular")));
  }
  step();
}

// ---------------------------------------------------------------- mapa do curso
async function viewCourse() {
  const c = await api("/api/course");
  const target = LangSwitcher.target();
  const lvlSel = state.courseLevel && c.levels.some((l) => l.level === state.courseLevel) ? state.courseLevel : c.current_level;
  const wrap = h("div", { class: "card" });
  const list = h("div", {});

  function render(level) {
    state.courseLevel = level;
    const L = c.levels.find((l) => l.level === level);
    const tabsEl = h("div", { class: "levels" }, c.levels.map((l) =>
      h("button", { type: "button", "aria-current": l.level === level ? "true" : null, onclick: () => render(l.level) },
        h("b", {}, l.level), h("small", {}, `${l.done}/${l.total} lições`))));
    put(list, tabsEl,
      h("div", { class: "row" }, h("span", { class: "lvl" }, L.level), h("b", {}, LEVEL_NAMES[L.level]), h("div", { class: "grow" }, bar(L.percent, L.percent === 100 ? "ok" : "")), h("span", { class: "muted" }, L.percent + "%")),
      L.units.map((u) => [h("div", { class: "unit" }, u.name),
        u.lessons.map((les) => h("button", { class: `lesson-row ${les.status} ${les.id === c.recommended ? "rec" : ""}`, type: "button", onclick: () => openLesson(les.id) },
          h("span", { class: "st" }, les.status === "done" ? "✓" : les.status === "started" ? "▶" : ""),
          h("span", { class: "t" }, h("b", {}, les.id.toUpperCase() + " · "), les.title,
            les.id === c.recommended ? h("span", { class: "tag", style: "margin-left:8px" }, "recomendada") : null),
          h("span", { class: "m" }, les.status === "done" ? `nota ${les.score}%` : les.minutes + " min")))]));
  }
  put(view, wrap);
  put(wrap, h("h2", {}, target.native === "Deutsch" ? "Grammatikkurs: von Null bis C1" : "Curso de gramática: do zero ao C1"),
    h("p", { class: "muted" }, target.native === "Deutsch"
      ? "Jede Lektion erklärt den Stoff Schritt für Schritt, bietet Übungen mit Korrektur und einen Mini-Test (80 % zum Abschluss)."
      : "Cada lição explica passo a passo, tem prática com correção e um mini-teste (80% para concluir). Você pode estudar em qualquer ordem, mas a recomendada vem destacada."),
    h("div", { class: "row" },
      h("button", { class: "btn primary", onclick: () => c.recommended && openLesson(c.recommended) }, "▶ Continuar de onde parei"),
      h("button", { class: "btn", onclick: () => go("placement") }, "Fazer teste de nível")),
    list);
  render(lvlSel);
}

function openLesson(id) { state.lessonId = id; go("lesson"); }

// ---------------------------------------------------------------- player de lição
async function viewLesson() {
  if (!state.lessonId) { go("course"); return; }
  const les = await api(`/api/course/lessons/${state.lessonId}`);
  const card = h("div", { class: "card" });
  put(view, card);
  const totalSteps = les.steps.length;
  let hidePt = false;

  const header = (phase, pct) => h("div", {},
    h("div", { class: "lesson-head" }, h("span", { class: "lvl" }, les.level), h("span", { class: "muted" }, les.unit + " · " + les.minutes + " min"),
      h("button", { class: "linkbtn", style: "margin-left:auto", onclick: () => go("course") }, "← Mapa do curso")),
    h("h2", {}, les.id.toUpperCase() + " · " + les.title), bar(pct), h("div", { class: "stage", style: "margin-top:6px" }, phase));

  function showStep(i) {
    const s = les.steps[i];
    card.classList.toggle("hide-pt", hidePt);
    put(card, header(`Explicação · passo ${i + 1} de ${totalSteps}`, 100 * i / (totalSteps + 2)),
      i === 0 ? h("div", { class: "box info" }, h("b", {}, "Objetivo: "), les.goal) : null,
      h("div", { class: "step-title" }, s.title), md(s.text),
      s.table ? h("div", { class: "tbl" }, h("table", {}, h("thead", {}, h("tr", {}, s.table.headers.map((x) => h("th", {}, x)))),
        h("tbody", {}, s.table.rows.map((r) => h("tr", {}, r.map((x) => h("td", {}, inline(String(x))))))))) : null,
      s.examples && s.examples.length ? h("div", { class: "examples" }, s.examples.map((e) =>
        h("div", { class: "exr" }, h("span", { class: "en" }, e.en), speakBtn(e.en), speakBtn(e.en, { slow: true }), h("span", { class: "pt" }, e.pt)))) : null,
      s.tip ? h("div", { class: "callout tip" }, h("b", { class: "lead" }, "💡 Dica"), inline(s.tip)) : null,
      s.trap ? h("div", { class: "callout trap" }, h("b", { class: "lead" }, "⚠ Armadilha para quem fala português"), inline(s.trap)) : null,
      h("div", { class: "nav-row" },
        h("button", { class: "btn", disabled: i === 0, onclick: () => showStep(i - 1) }, "← Anterior"),
        h("button", { class: "linkbtn", onclick: () => { hidePt = !hidePt; showStep(i); } }, hidePt ? "Mostrar traduções" : "Esconder traduções"),
        i + 1 < totalSteps ? h("button", { class: "btn primary", id: "next", onclick: () => showStep(i + 1) }, "Próximo →")
          : h("button", { class: "btn primary", id: "next", onclick: startPractice }, "Praticar →")));
    window.scrollTo({ top: 0 });
  }

  function startPractice() {
    const holder = h("div", {});
    put(card, header("Prática guiada · com explicação a cada resposta", 100 * totalSteps / (totalSteps + 2)), holder);
    runSequence(holder, les.practice, {
      label: "Prática",
      check: (ex, a) => api(`/api/course/lessons/${les.id}/check`, { method: "POST", body: { ex_id: ex.id, answer: a } }),
      onFinish: (answers, results) => {
        const right = Object.values(results).filter((r) => r && r.correct).length;
        showSummary(right);
      },
    });
  }

  function showSummary(right) {
    put(card, header("Resumo da lição", 100 * (totalSteps + 1) / (totalSteps + 2)),
      h("div", { class: "box info" }, `Prática: ${right} de ${les.practice.length} corretas. O que você errou foi guardado na Revisão de gramática.`),
      h("h3", { style: "margin-top:14px" }, "Para levar com você"), h("ul", { class: "summary" }, les.summary.map((s) => h("li", {}, inline(s)))),
      h("h3", {}, "Palavras desta lição"), h("div", { class: "vocab-grid" }, les.words.map((w) => h("button", { type: "button", onclick: () => Voice.speak(w.word) }, h("b", {}, w.word, " 🔊"), h("small", {}, w.pt)))),
      h("p", { class: "muted" }, "Elas entram na sua revisão de palavras quando você passar no mini-teste."),
      h("div", { class: "nav-row" }, h("button", { class: "btn", onclick: () => showStep(0) }, "↺ Reler a lição"),
        h("button", { class: "btn primary", onclick: startQuiz }, `Fazer o mini-teste (${les.quiz.length} questões) →`)));
    window.scrollTo({ top: 0 });
  }

  function startQuiz() {
    const holder = h("div", {});
    put(card, header("Mini-teste · sem dica durante as questões · precisa de 80%", 100 * (totalSteps + 1.5) / (totalSteps + 2)), holder);
    runSequence(holder, les.quiz, {
      label: "Questão", skip: true,
      onFinish: async (answers) => {
        put(holder, h("p", { class: "muted" }, "Corrigindo…"));
        try { showResult(await api(`/api/course/lessons/${les.id}/quiz`, { method: "POST", body: { answers } })); } catch (e) { put(holder, errBox(e)); }
      },
    });
  }

  function showResult(r) {
    const byId = Object.fromEntries(les.quiz.map((q) => [q.id, q]));
    put(card, header("Resultado do mini-teste", 100),
      h("div", { class: "score " + (r.passed ? "ok" : "bad") }, r.score + "%"),
      h("p", { class: "center" }, r.passed ? `Aprovado! ${r.right} de ${r.total} certas. Lição concluída.` : `${r.right} de ${r.total} certas. Você precisa de ${r.needed}% — releia os pontos errados e tente de novo.`),
      r.words_added ? h("div", { class: "box ok" }, `${r.words_added} palavra(s) nova(s) entraram na sua revisão de vocabulário.`) : null,
      h("h3", {}, "Correção"),
      r.results.map((x, i) => h("div", { class: "qreview" },
        h("span", { class: x.correct ? "yes" : "no" }, (x.correct ? "✔ " : "✘ ") + (i + 1) + ". "), inline(byId[x.id].prompt || byId[x.id].speak || ""),
        !x.correct ? h("div", {}, "Esperado: ", h("b", {}, x.expected)) : null,
        h("div", { class: "muted" }, inline(x.explain)))),
      h("div", { class: "nav-row" },
        h("button", { class: "btn", onclick: () => showStep(0) }, "↺ Reler a lição"),
        r.passed ? h("button", { class: "btn primary", onclick: () => (r.next ? openLesson(r.next) : go("course")) }, r.next ? "Próxima lição →" : "Voltar ao mapa")
          : h("button", { class: "btn primary", onclick: startQuiz }, "Tentar o mini-teste de novo")));
    window.scrollTo({ top: 0 });
  }

  showStep(0);
}

// ---------------------------------------------------------------- revisão de gramática
async function viewGrammar() {
  const card = h("div", { class: "card" });
  put(view, card);
  const st = await api("/api/grammar/stats");
  let exclude = "";
  async function next() {
    const r = await api("/api/grammar/next" + (exclude ? `?exclude=${encodeURIComponent(exclude)}` : ""));
    if (!r.item) {
      put(card, h("h2", {}, "Revisão de gramática"),
        h("div", { class: "box ok" }, r.total ? "Nada para revisar agora. Bom trabalho!" : "Ainda não há itens. Faça lições do curso: o que você errar (e os testes aprovados) voltam aqui na hora certa."),
        r.next_review ? h("p", { class: "muted" }, "Próximo item volta em " + new Date(r.next_review).toLocaleString("pt-BR") + ".") : null,
        h("button", { class: "btn primary", onclick: () => go("course") }, "Ir para o curso"));
      return;
    }
    const it = r.item;
    exclude = it.id;
    put(card, h("div", { class: "row" }, h("h2", { style: "margin:0" }, "Revisão de gramática"), h("span", { class: "pill-lv" }, `${r.due} para hoje`)),
      h("p", { class: "muted" }, "Da lição: ", h("button", { class: "linkbtn", onclick: () => openLesson(it.lesson_id) }, it.lesson_title)),
      exerciseView(it, { check: (a) => api("/api/grammar/answer", { method: "POST", body: { ex_id: it.id, answer: a } }), onDone: () => next() }));
  }
  await next();
}

// ---------------------------------------------------------------- teste de nível
async function viewPlacement() {
  const card = h("div", { class: "card" });
  put(view, card);
  const { items } = await api("/api/placement");
  put(card, h("h2", {}, "Teste de nível"),
    h("p", {}, `${items.length} perguntas de gramática, do A1 ao C1. Leva uns 10 minutos. Responda sozinho, sem consultar nada; se não souber, use “Não sei” — chutar atrapalha o resultado.`),
    h("p", { class: "muted" }, "Com o resultado, o curso começa no nível certo para você. Dá para mudar depois em Ajustes."),
    h("div", { class: "row" }, h("button", { class: "btn primary", id: "go-test", onclick: start }, "Começar o teste"),
      h("button", { class: "btn", onclick: async () => { await api("/api/course/start-level/A1", { method: "PUT" }); go("today"); } }, "Pular e começar do A1")));

  function start() {
    const holder = h("div", {});
    put(card, holder);
    runSequence(holder, items, {
      label: "Pergunta", skip: true,
      onFinish: async (answers) => {
        put(holder, h("p", { class: "muted" }, "Calculando seu nível…"));
        try { result(await api("/api/placement", { method: "POST", body: { answers } })); } catch (e) { put(holder, errBox(e)); }
      },
    });
  }
  function result(r) {
    put(card, h("h2", {}, "Seu resultado"),
      h("div", { class: "score ok" }, r.all_passed ? "C1" : r.estimated_level),
      h("p", { class: "center" }, r.all_passed ? "Você acertou o suficiente em todos os níveis. O curso vai refinar o C1."
        : `Você domina bem até o nível ${r.estimated_level}. O curso vai começar em ${r.start_level}.`),
      Object.keys(r.scores).map((lv) => h("div", { class: "row", style: "margin:6px 0" }, h("span", { class: "lvl" }, lv), h("div", { class: "grow" }, bar(100 * r.scores[lv] / r.totals[lv], r.scores[lv] >= 4 ? "ok" : "")), h("span", { class: "muted" }, `${r.scores[lv]}/${r.totals[lv]}`))),
      h("div", { class: "row", style: "margin-top:14px" }, h("button", { class: "btn primary", onclick: () => go("today") }, "Ver meu plano de hoje"),
        h("button", { class: "btn", onclick: () => go("course") }, "Ver o curso")),
      h("details", { style: "margin-top:12px" }, h("summary", {}, "Ver as respostas e explicações"),
        r.detail.map((d) => h("div", { class: "qreview" }, h("span", { class: d.correct ? "yes" : "no" }, (d.correct ? "✔ " : "✘ ") + d.level + " · "), "Certa: ", h("b", {}, d.expected), h("div", { class: "muted" }, inline(d.explain))))));
  }
}
