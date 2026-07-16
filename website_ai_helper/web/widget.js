/* Website AI Helper — self-injecting chat widget.
 * Loaded via a single async <script> tag (see README "Embedding the widget"):
 *   <script>
 *   !function(d,u,i,l){
 *       var s=d.createElement("script");s.async=1;s.src=u+"?client_id="+i+"&language="+l;
 *       var h=d.getElementsByTagName("script")[0];h.parentNode.insertBefore(s,h);
 *   }(document,"https://your-backend/widget.js","your-client-id","en");
 *   </script>
 * client_id selects which site's knowledge base to use (it's the Qdrant
 * collection name from `website-ai-helper ingest --collection <client_id>`).
 * language only picks the widget's UI strings below — the assistant itself
 * already answers in whatever language the visitor types in.
 */
(function () {
  "use strict";

  var thisScript = document.currentScript ||
    (function () { var s = document.getElementsByTagName("script"); return s[s.length - 1]; })();
  var scriptUrl = new URL(thisScript.src, window.location.href);
  var BACKEND = scriptUrl.origin;
  var CLIENT_ID = scriptUrl.searchParams.get("client_id") || "";
  var LANG = (scriptUrl.searchParams.get("language") || "en").toLowerCase();

  var STRINGS = {
    en: { title: "Assistant", subtitle: "Ask about this site", placeholder: "Type your question...",
          send: "Send", unreachable: "Could not reach the assistant. Is the backend running?" },
    it: { title: "Assistente", subtitle: "Chiedi informazioni su questo sito", placeholder: "Scrivi la tua domanda...",
          send: "Invia", unreachable: "Impossibile contattare l'assistente. Il servizio è attivo?" },
    sl: { title: "Pomočnik", subtitle: "Vprašaj o tej spletni strani", placeholder: "Vnesite vprašanje...",
          send: "Pošlji", unreachable: "Pomočnika ni mogoče doseči. Ali strežnik deluje?" },
  };
  var t = STRINGS[LANG] || STRINGS.en;

  var css = ""
    + ":root{--wah-accent:#3b5bdb;--wah-bg:#fff;--wah-fg:#1a1a2e;--wah-muted:#6b7280;--wah-panel:#f7f8fa;}"
    + "#wah-toggle{position:fixed;bottom:24px;right:24px;width:60px;height:60px;border-radius:50%;"
    + "background:var(--wah-accent);color:#fff;border:none;font-size:26px;cursor:pointer;"
    + "box-shadow:0 6px 20px rgba(0,0,0,.25);z-index:999999;font-family:system-ui,sans-serif;}"
    + "#wah-panel{position:fixed;bottom:96px;right:24px;width:380px;max-width:calc(100vw - 32px);"
    + "height:560px;max-height:calc(100vh - 120px);background:var(--wah-bg);border-radius:16px;"
    + "box-shadow:0 12px 40px rgba(0,0,0,.28);display:none;flex-direction:column;overflow:hidden;"
    + "z-index:999999;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:var(--wah-fg);}"
    + "#wah-panel.open{display:flex;}"
    + "#wah-panel .wah-hdr{background:var(--wah-accent);color:#fff;padding:14px 16px;font-weight:600;}"
    + "#wah-panel .wah-hdr small{display:block;font-weight:400;opacity:.85;font-size:12px;}"
    + "#wah-panel .wah-msgs{flex:1;overflow-y:auto;padding:16px;background:var(--wah-panel);}"
    + "#wah-panel .wah-msg{margin-bottom:14px;display:flex;}"
    + "#wah-panel .wah-msg .wah-bubble{padding:10px 13px;border-radius:14px;max-width:82%;"
    + "line-height:1.45;white-space:pre-wrap;word-wrap:break-word;}"
    + "#wah-panel .wah-msg.user{justify-content:flex-end;}"
    + "#wah-panel .wah-msg.user .wah-bubble{background:var(--wah-accent);color:#fff;border-bottom-right-radius:4px;}"
    + "#wah-panel .wah-msg.bot .wah-bubble{background:#fff;border:1px solid #e5e7eb;border-bottom-left-radius:4px;}"
    + "#wah-panel .wah-msg.bot .wah-bubble a{color:var(--wah-accent);text-decoration:underline;word-break:break-all;}"
    + "#wah-panel .wah-sources{font-size:11px;color:var(--wah-muted);margin-top:6px;}"
    + "#wah-panel .wah-sources a{color:var(--wah-accent);text-decoration:none;}"
    + "#wah-panel .wah-composer{display:flex;border-top:1px solid #e5e7eb;padding:10px;gap:8px;background:#fff;}"
    + "#wah-panel .wah-composer input{flex:1;border:1px solid #d1d5db;border-radius:10px;padding:10px 12px;"
    + "font-size:14px;outline:none;}"
    + "#wah-panel .wah-composer button{background:var(--wah-accent);color:#fff;border:none;border-radius:10px;"
    + "padding:0 16px;cursor:pointer;font-size:14px;}"
    + "#wah-panel .wah-composer button:disabled{opacity:.5;cursor:default;}";
  var styleEl = document.createElement("style");
  styleEl.textContent = css;
  document.head.appendChild(styleEl);

  var toggle = document.createElement("button");
  toggle.id = "wah-toggle";
  toggle.title = "Chat";
  toggle.textContent = "💬"; // 💬

  var panel = document.createElement("div");
  panel.id = "wah-panel";
  panel.innerHTML =
    '<div class="wah-hdr">' + t.title + '<small>' + t.subtitle + '</small></div>'
    + '<div class="wah-msgs"></div>'
    + '<form class="wah-composer">'
    + '<input autocomplete="off" placeholder="' + t.placeholder + '" />'
    + '<button type="submit">' + t.send + '</button>'
    + '</form>';

  document.body.appendChild(toggle);
  document.body.appendChild(panel);

  var els = {
    msgs: panel.querySelector(".wah-msgs"),
    form: panel.querySelector(".wah-composer"),
    input: panel.querySelector("input"),
    send: panel.querySelector("button"),
  };
  var history = [];
  var conversationId = (crypto.randomUUID && crypto.randomUUID())
    || (Date.now().toString(36) + Math.random().toString(36).slice(2));

  toggle.onclick = function () { panel.classList.toggle("open"); };

  function addMsg(role, text) {
    var wrap = document.createElement("div");
    wrap.className = "wah-msg " + role;
    var bubble = document.createElement("div");
    bubble.className = "wah-bubble";
    bubble.textContent = text;
    wrap.appendChild(bubble);
    els.msgs.appendChild(wrap);
    els.msgs.scrollTop = els.msgs.scrollHeight;
    return bubble;
  }

  function escapeHtml(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;")
            .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function stripSourcesLine(s) {
    return s.replace(/[\s\n]*(?:Sources|Viri|Fonti)\s*:?\s*(?:\[\d+\][\s,;]*)+[\s.]*$/i, "");
  }

  function renderMessage(raw) {
    var text = stripSourcesLine(raw);
    var linkRe = /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)|<(https?:\/\/[^>\s]+)>|(https?:\/\/[^\s<>"')\]]+)/g;
    var parts = [];
    var last = 0, m;
    while ((m = linkRe.exec(text)) !== null) {
      parts.push(escapeHtml(text.slice(last, m.index)));
      var label, url, trailing = "";
      if (m[1]) { label = m[1]; url = m[2]; }
      else { url = m[3] || m[4]; label = url; }
      var punct = url.match(/[.,;:!?]+$/);
      if (punct) { trailing = punct[0]; url = url.slice(0, -trailing.length); if (!m[1]) label = url; }
      parts.push('<a href="' + escapeHtml(url) + '" target="_blank" rel="noopener">'
                 + escapeHtml(label) + '</a>' + escapeHtml(trailing));
      last = m.index + m[0].length;
    }
    parts.push(escapeHtml(text.slice(last)));
    // Runs on already-escaped text, so it can only produce the <strong> tag itself.
    return parts.join("").replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>");
  }

  function currentPage() {
    return {
      url: location.href,
      title: document.title,
      text: (document.body.innerText || "").slice(0, 4000),
    };
  }

  function renderSources(bubble, sources) {
    var valid = (sources || []).filter(function (s) { return s.url; });
    if (!valid.length) return;
    var div = document.createElement("div");
    div.className = "wah-sources";
    div.innerHTML = "Sources: " + valid.map(function (s) {
      return '<a href="' + s.url + '" target="_blank" rel="noopener">[' + s.n + ']</a>';
    }).join(" ");
    bubble.parentElement.appendChild(div);
  }

  els.form.onsubmit = function (e) {
    e.preventDefault();
    var message = els.input.value.trim();
    if (!message) return;
    els.input.value = "";
    els.send.disabled = true;
    addMsg("user", message);

    var bubble = addMsg("bot", "");
    var answer = "";

    fetch(BACKEND + "/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: message, history: history, current_page: currentPage(),
        conversation_id: conversationId, client_id: CLIENT_ID,
      }),
    }).then(function (resp) {
      var reader = resp.body.getReader();
      var decoder = new TextDecoder();
      var buffer = "";
      function pump() {
        return reader.read().then(function (r) {
          if (r.done) return;
          buffer += decoder.decode(r.value, { stream: true });
          var parts = buffer.split("\n\n");
          buffer = parts.pop();
          parts.forEach(function (part) {
            var line = part.replace(/^data: /, "").trim();
            if (!line) return;
            var evt = JSON.parse(line);
            if (evt.type === "token") { answer += evt.text; bubble.innerHTML = renderMessage(answer); }
            else if (evt.type === "sources") { renderSources(bubble, evt.sources); }
            else if (evt.type === "error") { bubble.textContent = "⚠️ " + evt.message; }
            els.msgs.scrollTop = els.msgs.scrollHeight;
          });
          return pump();
        });
      }
      return pump();
    }).then(function () {
      history.push({ role: "user", content: message });
      history.push({ role: "assistant", content: answer });
    }).catch(function () {
      bubble.textContent = t.unreachable;
    }).finally(function () {
      els.send.disabled = false;
      els.input.focus();
    });
  };
})();
