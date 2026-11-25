"use strict";
// ============================================================== LIVE CONVERSATION (LIVE VOICE TUTOR)
// Conversação em tempo real com tutor bilíngue via WebSocket (Gemini Multimodal Live / Duplex Fallback).
// Suporta Ephemeral Token seguro, visualizador de ondas sonoras, detecção de barge-in e cards de recasting.

const LiveVoiceTutor = (() => {
  let ws = null;
  let audioCtx = null;
  let micStream = null;
  let micSource = null;
  let micProcessor = null;
  let analyser = null;
  let animFrameId = null;

  let activeSources = [];
  let nextStartTime = 0;
  let isCallActive = false;
  let tutorSpeaking = false;
  let currentScenario = "daily";
  let sessionMode = "duplex_agent";

  let speechRec = null;

  // Utilitários de áudio PCM
  function floatTo16BitPCM(float32Array) {
    const buffer = new ArrayBuffer(float32Array.length * 2);
    const view = new DataView(buffer);
    let offset = 0;
    for (let i = 0; i < float32Array.length; i++, offset += 2) {
      let s = Math.max(-1, Math.min(1, float32Array[i]));
      view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
    }
    return buffer;
  }

  function arrayBufferToBase64(buffer) {
    let binary = "";
    const bytes = new Uint8Array(buffer);
    for (let i = 0; i < bytes.byteLength; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    return window.btoa(binary);
  }

  function base64ToFloat32Array(base64) {
    const binary = window.atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i);
    }
    const int16 = new Int16Array(bytes.buffer);
    const float32 = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i++) {
      float32[i] = int16[i] / 32768.0;
    }
    return float32;
  }

  function stopAllPlayback() {
    for (const src of activeSources) {
      try { src.stop(); src.disconnect(); } catch (_) {}
    }
    activeSources.length = 0;
    nextStartTime = 0;
    tutorSpeaking = false;
    Voice.stop();
  }

  function playPcmChunk(float32, sampleRate = 24000) {
    if (!audioCtx) return;
    const audioBuffer = audioCtx.createBuffer(1, float32.length, sampleRate);
    audioBuffer.getChannelData(0).set(float32);

    const source = audioCtx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(audioCtx.destination);

    const now = audioCtx.currentTime;
    if (nextStartTime < now) {
      nextStartTime = now;
    }
    source.start(nextStartTime);
    nextStartTime += audioBuffer.duration;
    activeSources.push(source);
    tutorSpeaking = true;

    source.onended = () => {
      const idx = activeSources.indexOf(source);
      if (idx !== -1) activeSources.splice(idx, 1);
      if (activeSources.length === 0) {
        tutorSpeaking = false;
        updateStatus("listening");
      }
    };
  }

  let statusEl = null;
  let canvasEl = null;
  let transcriptFeedEl = null;
  let callBtnEl = null;

  function updateStatus(state, customText) {
    if (!statusEl) return;
    statusEl.className = "live-status-pill " + state;
    const texts = {
      ready: "📞 Pronto para conectar",
      connecting: "⏳ Conectando ao tutor ao vivo...",
      connected: "🟢 Conectado · Fale à vontade!",
      listening: "👂 Ouvindo você... (fale em inglês ou tire dúvidas)",
      speaking: "🗣️ Tutor falando... (interrompa a qualquer momento)",
      disconnected: "⚪ Chamada encerrada",
    };
    statusEl.textContent = customText || texts[state] || texts.ready;
  }

  // Visualizador em tempo real (Canvas 60fps)
  function startVisualizer() {
    if (!canvasEl) return;
    const ctx = canvasEl.getContext("2d");
    const dataArray = new Uint8Array(analyser ? analyser.frequencyBinCount : 64);
    let waveOffset = 0;

    function draw() {
      if (!isCallActive) {
        // Desenha estado neutro/inativo
        ctx.clearRect(0, 0, canvasEl.width, canvasEl.height);
        ctx.fillStyle = "rgba(150, 160, 180, 0.2)";
        ctx.fillRect(0, canvasEl.height / 2 - 1, canvasEl.width, 2);
        return;
      }

      animFrameId = requestAnimationFrame(draw);

      const width = canvasEl.width;
      const height = canvasEl.height;
      ctx.clearRect(0, 0, width, height);

      let micEnergy = 0;
      if (analyser) {
        analyser.getByteFrequencyData(dataArray);
        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) sum += dataArray[i];
        micEnergy = sum / dataArray.length;
      }

      // Barge-in natural: se o tutor está falando e o usuário fala alto no microfone
      if (tutorSpeaking && micEnergy > 28) {
        stopAllPlayback();
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "interrupt" }));
        }
        updateStatus("listening", "👂 Interrompido (Barge-in)! Ouvindo você...");
      }

      // Desenha ondas sonoras
      waveOffset += 0.08;
      ctx.lineWidth = 3;
      ctx.beginPath();

      if (tutorSpeaking) {
        // Onda do Tutor (Azul / Accent)
        updateStatus("speaking");
        ctx.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue("--accent").trim() || "#1f5fd6";
        for (let x = 0; x < width; x++) {
          const y = height / 2 + Math.sin(x * 0.05 + waveOffset * 2) * (height * 0.3) * Math.sin(x / width * Math.PI);
          if (x === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
      } else {
        // Onda do Usuário (Verde / Ok quando fala; Linha suave quando em silêncio)
        const intensity = Math.min(1.0, micEnergy / 70);
        ctx.strokeStyle = intensity > 0.15 ? "#17794a" : "rgba(100, 120, 150, 0.4)";
        const amp = Math.max(3, intensity * (height * 0.42));

        for (let x = 0; x < width; x++) {
          const y = height / 2 + Math.sin(x * 0.06 + waveOffset) * amp * Math.sin(x / width * Math.PI);
          if (x === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
      }
      ctx.stroke();
    }

    draw();
  }

  // Transcrição Dinâmica e Cards de Feedback
  let currentTutorBubble = null;

  function appendMessage(sender, text, isContinuation = false) {
    if (!transcriptFeedEl) return;

    if (sender === "tutor" && isContinuation && currentTutorBubble) {
      currentTutorBubble.textContent += text;
      transcriptFeedEl.scrollTop = transcriptFeedEl.scrollHeight;
      return;
    }

    const isMe = sender === "user";
    const bubble = h("div", { class: `live-msg-bubble ${isMe ? "user" : "tutor"}` },
      h("div", { class: "live-msg-author" }, isMe ? "Você" : "Tutor Ao Vivo"),
      text
    );
    if (sender === "tutor") {
      currentTutorBubble = bubble.lastChild;
    } else {
      currentTutorBubble = null;
    }

    const row = h("div", { class: `live-msg-row ${isMe ? "me" : "tutor"}` },
      h("div", { class: "live-avatar" }, isMe ? "🧑" : "🤖"),
      bubble
    );

    transcriptFeedEl.append(row);
    transcriptFeedEl.scrollTop = transcriptFeedEl.scrollHeight;
  }

  function appendRecastCard(youSaid, natural) {
    if (!transcriptFeedEl) return;
    const card = h("div", { class: "recast-card" },
      h("div", { class: "recast-header" },
        h("span", {}, "💡 Dica de Expressão Natural"),
        h("button", {
          class: "recast-speak-btn",
          type: "button",
          title: "Ouvir pronúncia natural",
          onclick: () => Voice.speak(natural)
        }, "🔊")
      ),
      h("div", { class: "recast-grid" },
        h("div", { class: "recast-label" }, "Você disse:"),
        h("div", {}, h("span", { class: "recast-original" }, youSaid)),
        h("div", { class: "recast-label" }, "Forma natural:"),
        h("div", {}, h("span", { class: "recast-natural" }, natural))
      )
    );
    transcriptFeedEl.append(card);
    transcriptFeedEl.scrollTop = transcriptFeedEl.scrollHeight;
  }

  // Inicializa reconhecimento de voz auxiliar para transcrição instantânea
  function setupSpeechRecognition() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return;
    try {
      const r = new SR();
      speechRec = r;
      r.lang = "en-US";
      r.continuous = true;
      r.interimResults = false;

      r.onresult = (ev) => {
        const last = ev.results[ev.results.length - 1];
        if (last && last.isFinal) {
          const text = last[0].transcript.trim();
          if (text) {
            appendMessage("user", text);
            // Se estiver em modo duplex_agent, envia o texto reconhecido para o WebSocket
            if (ws && ws.readyState === WebSocket.OPEN && sessionMode === "duplex_agent") {
              ws.send(JSON.stringify({ type: "text", text: text }));
            }
          }
        }
      };

      r.onerror = () => {};
      r.onend = () => {
        if (isCallActive && speechRec === r) {
          try { r.start(); } catch (_) {}
        }
      };
      r.start();
    } catch (_) {}
  }

  // Iniciar chamada
  async function startCall() {
    if (isCallActive) return;

    try {
      updateStatus("connecting");
      if (callBtnEl) {
        callBtnEl.disabled = true;
        callBtnEl.textContent = "⏳";
      }

      // 1. Gera Ephemeral Token no backend para proteger a chave de API
      const session = await api("/api/live/session", {
        method: "POST",
        body: { scenario: currentScenario, language: (typeof LangSwitcher !== "undefined" ? LangSwitcher.get() : "en") },
      });

      if (!session || !session.token) {
        throw new Error("Não foi possível gerar sessão de conversação ao vivo.");
      }

      sessionMode = session.mode || "duplex_agent";

      // 2. Inicializa Web Audio Context & Microfone
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      audioCtx = new AudioCtx({ sampleRate: 16000 });
      if (audioCtx.state === "suspended") {
        await audioCtx.resume();
      }

      micStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      micSource = audioCtx.createMediaStreamSource(micStream);
      micSource.connect(analyser);

      // ScriptProcessor para capturar PCM 16kHz e enviar via WebSocket
      micProcessor = audioCtx.createScriptProcessor(4096, 1, 1);
      analyser.connect(micProcessor);
      micProcessor.connect(audioCtx.destination);

      micProcessor.onaudioprocess = (e) => {
        if (!isCallActive || !ws || ws.readyState !== WebSocket.OPEN) return;
        const inputData = e.inputBuffer.getChannelData(0);
        // Se estiver em modo Gemini Live, faz streaming de chunks PCM16
        if (sessionMode === "gemini_live") {
          const pcmBuffer = floatTo16BitPCM(inputData);
          const b64 = arrayBufferToBase64(pcmBuffer);
          ws.send(JSON.stringify({ type: "audio", data: b64 }));
        }
      };

      // 3. Conecta WebSocket
      const protocol = location.protocol === "https:" ? "wss:" : "ws:";
      const wsUrl = `${protocol}//${location.host}${session.ws_path}`;
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        isCallActive = true;
        updateStatus("connected");
        if (callBtnEl) {
          callBtnEl.disabled = false;
          callBtnEl.className = "live-call-btn end";
          callBtnEl.textContent = "🛑";
          callBtnEl.title = "Encerrar Chamada";
        }
        setupSpeechRecognition();
        startVisualizer();
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          const t = data.type;

          if (t === "ready") {
            updateStatus("connected", data.message || "Tutor conectado!");
          } else if (t === "session_started") {
            updateStatus("listening", "Tutor ao vivo pronto. Fale à vontade!");
          } else if (t === "audio") {
            // Reproduz áudio do tutor em streaming (PCM 24kHz do Gemini)
            if (data.data) {
              const float32 = base64ToFloat32Array(data.data);
              playPcmChunk(float32, 24000);
            }
          } else if (t === "text") {
            const isTutor = data.sender === "tutor";
            appendMessage(isTutor ? "tutor" : "user", data.text, !data.is_intro);
            // Em modo duplex fallback, pronuncia a fala via Voice se não veio PCM
            if (isTutor && sessionMode === "duplex_agent") {
              tutorSpeaking = true;
              updateStatus("speaking");
              Voice.speak(data.text, {
                onEnd: () => {
                  tutorSpeaking = false;
                  updateStatus("listening");
                },
              });
            }
          } else if (t === "recast") {
            appendRecastCard(data.you_said, data.natural);
          } else if (t === "interrupted") {
            stopAllPlayback();
            updateStatus("listening", "👂 Interrompido. Ouvindo você...");
          } else if (t === "turn_complete") {
            currentTutorBubble = null;
            if (!tutorSpeaking) {
              updateStatus("listening");
            }
          } else if (t === "fallback_notice") {
            sessionMode = "duplex_agent";
            toast(data.message || "Modo alternativo duplex ativado.");
          } else if (t === "error") {
            toast(data.message || "Erro na conexão com o tutor.");
          }
        } catch (err) {
          console.error("Erro ao processar mensagem do tutor:", err);
        }
      };

      ws.onerror = (e) => {
        console.error("Erro no WebSocket Live:", e);
        toast("Falha na conexão com o tutor ao vivo.");
      };

      ws.onclose = () => {
        endCall();
      };

    } catch (err) {
      console.error("Erro ao iniciar chamada:", err);
      toast("Não foi possível iniciar a chamada: " + (err.message || err));
      endCall();
    }
  }

  // Encerrar chamada
  function endCall() {
    isCallActive = false;
    tutorSpeaking = false;
    stopAllPlayback();

    if (speechRec) {
      try { speechRec.stop(); } catch (_) {}
      speechRec = null;
    }

    if (micProcessor) {
      try { micProcessor.disconnect(); } catch (_) {}
      micProcessor = null;
    }

    if (micSource) {
      try { micSource.disconnect(); } catch (_) {}
      micSource = null;
    }

    if (micStream) {
      micStream.getTracks().forEach((track) => track.stop());
      micStream = null;
    }

    if (audioCtx) {
      try { audioCtx.close(); } catch (_) {}
      audioCtx = null;
    }

    if (ws) {
      try { ws.close(); } catch (_) {}
      ws = null;
    }

    if (animFrameId) {
      cancelAnimationFrame(animFrameId);
      animFrameId = null;
    }

    updateStatus("disconnected");
    if (callBtnEl) {
      callBtnEl.disabled = false;
      callBtnEl.className = "live-call-btn start";
      callBtnEl.textContent = "📞";
      callBtnEl.title = "Iniciar Chamada";
    }

    if (canvasEl) {
      const ctx = canvasEl.getContext("2d");
      ctx.clearRect(0, 0, canvasEl.width, canvasEl.height);
    }
  }

  // Render da view
  function renderView() {
    const scenarios = [
      { id: "daily", icon: "💼", label: "Daily Stand-up", desc: "Reunião tech com seu Tech Lead" },
      { id: "interview", icon: "🎯", label: "Entrevista de Emprego", desc: "Perguntas de entrevista internacional" },
      { id: "casual", icon: "☕", label: "Conversa Casual", desc: "Coffee break descontraído com colega" },
    ];

    const scenarioBtns = scenarios.map((s) => {
      const btn = h("button", {
        type: "button",
        class: `live-scenario-btn ${s.id === currentScenario ? "active" : ""}`,
        title: s.desc,
        onclick: () => {
          if (isCallActive) {
            toast("Encerre a chamada atual antes de mudar de cenário.");
            return;
          }
          currentScenario = s.id;
          scenarioBtns.forEach((b) => b.classList.toggle("active", b.dataset.sc === s.id));
        },
      }, s.icon, " ", h("b", {}, s.label));
      btn.dataset.sc = s.id;
      return btn;
    });

    statusEl = h("div", { class: "live-status-pill ready" }, "📞 Pronto para conectar");

    canvasEl = h("canvas", { class: "live-wave-canvas", width: 440, height: 90 });

    callBtnEl = h("button", {
      type: "button",
      class: "live-call-btn start",
      title: "Iniciar Chamada com Tutor Ao Vivo",
      onclick: () => {
        if (isCallActive) {
          endCall();
        } else {
          startCall();
        }
      },
    }, "📞");

    transcriptFeedEl = h("div", { class: "live-transcript-feed" });

    // Mensagem de boas-vindas
    appendMessage(
      "tutor",
      "Welcome to Live Conversation! Escolha um cenário acima e clique no botão verde para iniciar a chamada de voz em tempo real com seu tutor nativo. Sinta-se 100% à vontade para errar, misturar português ou perguntar 'como se diz X?'. Let's talk!"
    );

    // Entrada rápida de texto (caso o usuário prefira digitar)
    const textInput = h("input", {
      type: "text",
      placeholder: "Digite aqui caso prefira não falar agora e aperte Enter...",
      style: "flex:1;padding:10px 14px;font-size:14px;border-radius:12px;border:1px solid var(--line);background:var(--bg);color:var(--ink);",
    });

    const sendMsg = () => {
      const val = textInput.value.trim();
      if (!val) return;
      textInput.value = "";
      appendMessage("user", val);
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "text", text: val }));
      } else {
        toast("Inicie a chamada para conversar com o tutor.");
      }
    };

    textInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") sendMsg();
    });

    const sendBtn = h("button", {
      type: "button",
      class: "btn primary",
      style: "padding:10px 16px;border-radius:12px;",
      onclick: sendMsg,
    }, "Enviar");

    const root = h("div", { class: "live-container" },
      h("h2", { style: "margin-bottom:4px;" }, "🎙️ Live Conversation (Tutor Ao Vivo)"),
      h("p", { class: "muted", style: "margin-bottom:12px;" },
        "Pratique conversação em tempo real via WebSocket com feedback imediato, recasting gentil e interrupção natural."
      ),
      h("div", { class: "live-scenario-selector" }, scenarioBtns),
      h("div", { class: "live-hero-card" },
        statusEl,
        h("div", { class: "live-wave-wrapper" }, canvasEl),
        callBtnEl,
        h("div", { class: "live-bargein-tip" }, "💡 Dica: Você pode interromper o tutor a qualquer momento falando naturalmente (barge-in).")
      ),
      h("div", { class: "row", style: "gap:8px;margin-bottom:14px;" }, textInput, sendBtn),
      h("h3", { style: "font-size:16px;margin:18px 0 6px;" }, "Transcrição e Dicas de Expressão"),
      transcriptFeedEl
    );

    return root;
  }

  return {
    render: renderView,
    endCall,
  };
})();

async function viewLiveConversation() {
  put(view, LiveVoiceTutor.render());
}
