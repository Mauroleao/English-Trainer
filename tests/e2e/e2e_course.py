"""Teste ponta a ponta do curso no navegador (Playwright). Rodar:  python tests/e2e/e2e_course.py
Usa um banco temporário, uma porta livre e voz/microfone simulados."""
import json, os, socket, subprocess, sys, tempfile, time
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
CONTENT = ROOT / "app/course/content"
LES = {p.stem: json.loads(p.read_text()) for p in (CONTENT / "lessons").glob("*.json")}

def answer_for(ex):
    t = ex["type"]
    if t == "choice": return ex["answer"]
    if t == "order": return " ".join(ex["words"])
    if t == "listen": return ex["en"]
    return ex["answers"][0]

MOCK = """
window.__spoken = [];
Object.defineProperty(window, 'speechSynthesis', {value: { getVoices: () => [{name:'Mock', lang:'en-US'}], speak: u => window.__spoken.push(u.text), cancel(){} }, configurable:true});
Object.defineProperty(window, 'SpeechSynthesisUtterance', {value: function(t){ this.text = t; }, configurable:true});
window.SpeechRecognition = function(){ this.start = () => setTimeout(() => this.onresult({results:[[{transcript: window.__heard || 'i am a developer'}]]}), 50); this.stop=()=>{}; this.abort=()=>{}; };
"""

def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p

def main():
    port = free_port()
    env = {**os.environ, "ENGLISH_APP_DB": os.path.join(tempfile.mkdtemp(), "e2e.db")}
    env.pop("ANTHROPIC_API_KEY", None)
    srv = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    for _ in range(60):
        try: socket.create_connection(("127.0.0.1", port), 0.2).close(); break
        except OSError: time.sleep(0.25)
    errors = []
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(); ctx = b.new_context(viewport={"width": 420, "height": 900}); ctx.add_init_script(MOCK)
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: errors.append(str(e)))
            pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            pg.goto(base)
            pg.wait_for_selector("text=Plano de hoje")
            assert pg.locator("text=Descubra seu nível").count() == 1
            # --- curso e lição a1-01
            pg.click("#nav [data-group=course]"); pg.wait_for_selector("text=Curso de gramática")
            assert pg.locator(".lesson-row").count() == 12
            pg.click(".lesson-row.rec")
            pg.wait_for_selector("text=Para que serve o verbo to be")
            for _ in range(len(LES["a1-01"]["steps"]) - 1): pg.click("#next")
            pg.click("#next")  # Praticar
            def run(exs):
                for ex in exs:
                    a = answer_for(ex); root = pg.locator(f"[data-ex={ex['id']}]"); root.wait_for()
                    if ex["type"] == "choice": root.locator(".opt").nth(a).click()
                    elif ex["type"] == "order":
                        for w in a.split(): root.locator(".chips .chip", has_text=w).first.click()
                        root.get_by_text("Verificar").click()
                    else:
                        root.locator("input").fill(a); root.locator("input").press("Enter")
                    yield ex
            for ex in run(LES["a1-01"]["practice"]):
                pg.wait_for_selector(".box.ok"); pg.click("#ex-next")
            pg.wait_for_selector("text=Resumo da lição")
            pg.click("text=Fazer o mini-teste")
            for ex in run(LES["a1-01"]["quiz"][:0]): pass
            for ex in LES["a1-01"]["quiz"]:
                a = answer_for(ex); root = pg.locator(f"[data-ex={ex['id']}]"); root.wait_for()
                if ex["type"] == "choice": root.locator(".opt").nth(a).click()
                elif ex["type"] == "order":
                    for w in a.split(): root.locator(".chips .chip", has_text=w).first.click()
                    root.get_by_text("Verificar").click()
                else: root.locator("input").fill(a); root.locator("input").press("Enter")
            pg.wait_for_selector("text=Lição concluída")
            assert "100%" in pg.locator(".score").inner_text()
            # --- gramática (itens dos testes aprovados voltam em 2 dias; erros imediatamente): força um erro na prática da a1-02
            pg.goto(base + "/#course"); pg.reload(); pg.click(".lesson-row >> nth=1")
            pg.wait_for_selector("#next")
            for _ in range(len(LES["a1-02"]["steps"])): pg.click("#next")
            ex = LES["a1-02"]["practice"][0]
            root = pg.locator(f"[data-ex={ex['id']}]"); root.wait_for()
            if ex["type"] == "choice": root.locator(".opt").nth((ex["answer"] + 1) % len(ex["options"])).click()
            else: root.locator("input").fill("zzz"); root.locator("input").press("Enter")
            pg.wait_for_selector(".box.bad")
            pg.click("#nav [data-group=review]"); pg.click("#subnav [data-tab=grammar]")
            pg.wait_for_selector(f"[data-ex={ex['id']}]")
            # --- teste de nível
            pg.click("#nav [data-group=course]"); pg.click("text=Fazer teste de nível"); pg.click("#go-test")
            items = json.loads((CONTENT / "placement.json").read_text())["items"]
            for it in items:
                root = pg.locator(f"[data-ex={it['id']}]"); root.wait_for()
                a = answer_for(it) if it["level"] in ("A1", "A2", "B1") else None
                if a is None: pg.click("text=Não sei"); continue
                if it["type"] == "choice": root.locator(".opt").nth(a).click()
                else: root.locator("input").fill(a); root.locator("input").press("Enter")
            pg.wait_for_selector("text=Seu resultado")
            assert pg.locator(".score").first.inner_text() == "B1", pg.locator(".score").first.inner_text()
            # --- leitura
            pg.click("#nav [data-group=practice]"); pg.click("#subnav [data-tab=reading]")
            pg.wait_for_selector("text=Leitura e escuta por nível"); pg.click(".list-row >> nth=0")
            pg.wait_for_selector("text=Vocabulário do texto"); pg.click("text=Responder às perguntas")
            rd = json.loads(next((CONTENT / "reading").glob("r-b2-01.json")).read_text())
            for q in rd["questions"]:
                pg.locator(f"[data-ex={q['id']}] .opt").nth(q["answer"]).click()
                pg.click("#ex-next") if pg.locator("#ex-next").count() else None
            pg.wait_for_selector("text=Tradução do texto")
            pg.click("text=Mandar as palavras do texto"); pg.wait_for_selector("text=adicionadas à revisão")
            # --- pronúncia (microfone simulado)
            pg.click("#subnav [data-tab=pronounce]"); pg.wait_for_timeout(800); pg.wait_for_selector(".mic-big")
            pg.evaluate("window.__heard = ''")
            target = pg.locator(".big").inner_text()
            pg.evaluate("t => window.__heard = t", target)
            pg.click(".mic-big"); pg.wait_for_selector(".score")
            assert pg.locator(".score").inner_text() == "100%"
            # --- progresso e ajustes
            pg.click("#nav [data-group=progress]"); pg.wait_for_selector("text=Seu progresso")
            assert "1/72" in pg.locator("body").inner_text()
            pg.click("#nav [data-group=settings]"); pg.wait_for_selector("text=Meta e nível")
            # --- telas antigas continuam funcionando
            pg.click("#nav [data-group=practice]"); pg.wait_for_selector("text=Frases e diálogos")
            pg.click("#nav [data-group=vocab]"); pg.wait_for_selector("text=Vocabulário")
            b.close()
        real = [e for e in errors if "favicon" not in e]
        assert not real, real
        print("E2E OK")
    finally:
        srv.terminate()

main()
